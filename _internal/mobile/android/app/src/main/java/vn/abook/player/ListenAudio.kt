package vn.abook.player

import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import vn.abook.player.readaloud.Wav
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Phần Android của "Xuất sách nói" ([ListenExport]): giải mã clip giọng đọc, ghi từng chương thành AAC và nối các chương thành luồng M4B.
 *
 * - [Clips]: clip của giọng đọc là WAV (giọng của máy, VieNeu, Supertonic - đọc thẳng) hay MP3 (Edge và giọng trực tuyến - bộ giải mã của Android, dùng lại của
 *   "Xuất M4B": [M4bAudio.decodeFile]); ra PCM mono ở tần số chung của cuốn.
 * - [outputs]: mỗi chương một bộ mã hoá AAC-LC 64 kb/s mono ([M4bAudio.AacSink], đúng số của M4B Studio), ghi `<mã chương>.m4a`.
 * - [ListenAudio]: bước cuối của [M4bExport.run]: chép nguyên các mẫu AAC của từng chương nối nhau vào MỘT luồng MP4 (MediaMuxer) - không mã hoá lại nên cả cuốn chỉ qua đúng một
 *   lần mã hoá. Mỗi chương mở đầu bằng độ trễ của bộ mã hoá (2048 mẫu, im lặng) và kết thúc bằng phần đệm tới khung 1024: giữa hai chương có chừng 0,1 giây lặng. Mốc chương
 *   là chỗ chương bắt đầu trong luồng (sau khi file cuối cắt độ trễ ở đầu - [delay], như M4B Studio), nên trình phát nhảy tới chương là nghe ngay chữ đầu.
 */
object Clips : ListenExport.Decoder {
    private const val BLOCK_FRAMES = 8192

    override fun rate(file: File): Int = Wav.format(file)?.sampleRate ?: M4bAudio.layout(file).first

    override fun decode(file: File, rate: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) {
        val wav = Wav.format(file)
        if (wav != null && wav.bitsPerSample == 16) decodeWav(file, wav, rate, stopped, write)
        else M4bAudio.decodeFile(file, rate, ListenExport.CHANNELS, stopped, write = write)
    }

    /** WAV 16-bit: độ dài lấy từ cỡ file (cỡ `data` trong đầu file không đáng tin khi ghi theo dòng - xem [Wav]). */
    internal fun decodeWav(file: File, wav: Wav.Format, rate: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) {
        val converter = M4bExport.PcmConverter(wav.sampleRate, wav.channels, rate, ListenExport.CHANNELS)
        val frameBytes = wav.channels * 2
        val bytes = ByteArray(BLOCK_FRAMES * frameBytes)
        var left = ((file.length() - wav.dataOffset).coerceAtLeast(0) / frameBytes) * frameBytes
        RandomAccessFile(file, "r").use { input ->
            input.seek(wav.dataOffset.toLong())
            while (left > 0) {
                if (stopped()) throw Mp3Export.Stopped()
                val take = minOf(left, bytes.size.toLong()).toInt()
                input.readFully(bytes, 0, take)
                left -= take
                val samples = ShortArray(take / 2)
                ByteBuffer.wrap(bytes, 0, take).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(samples)
                val converted = converter.convert(samples, samples.size)
                if (converted.isNotEmpty()) write(converted, converted.size)
            }
        }
    }
}

object ListenAudio : M4bExport.AudioEncoder {
    private const val BUFFER = 256 * 1024

    val outputs = ListenExport.Outputs { file, rate -> M4bAudio.AacSink(file, rate, ListenExport.CHANNELS) }

    override val delay: Int get() = M4bAudio.delay

    override fun encode(plan: Mp3Export.Plan, target: File, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit): List<Mp4Finish.Mark> {
        val muxer = MediaMuxer(target.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        var started = false
        var rate = 0
        var channels = 0
        var offset = 0L // khung AAC đã ghi
        val starts = ArrayList<Long>()
        try {
            progress(0, plan.chapters.size, 0.0)
            val track = ByteBuffer.allocate(BUFFER)
            var trackIndex = -1
            plan.chapters.forEachIndexed { index, chapter ->
                if (stopped()) throw Mp3Export.Stopped()
                val extractor = MediaExtractor()
                try {
                    extractor.setDataSource(chapter.file.absolutePath)
                    val source = (0 until extractor.trackCount).firstOrNull { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME) == MediaFormat.MIMETYPE_AUDIO_AAC }
                        ?: throw Mp3Export.Refused("Không đọc được file tạm của “${chapter.fullTitle}” - xuất lại để làm lại chương này")
                    val format = extractor.getTrackFormat(source)
                    val chapterRate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                    val chapterChannels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                    if (!started) {
                        rate = chapterRate
                        channels = chapterChannels
                        trackIndex = muxer.addTrack(format)
                        muxer.start()
                        started = true
                    } else if (chapterRate != rate || chapterChannels != channels) {
                        throw Mp3Export.Refused("Các chương làm ở hai lần khác nhau không cùng tần số - xuất lại từ đầu")
                    }
                    extractor.selectTrack(source)
                    starts += offset
                    val info = MediaCodec.BufferInfo()
                    var frames = 0L
                    while (true) {
                        track.clear()
                        val size = extractor.readSampleData(track, 0)
                        if (size < 0) break
                        if (frames % 256 == 0L && stopped()) throw Mp3Export.Stopped()
                        val flags = if (extractor.sampleFlags and MediaExtractor.SAMPLE_FLAG_SYNC != 0) MediaCodec.BUFFER_FLAG_KEY_FRAME else 0
                        // Mốc giờ đếm theo khung (mỗi khung AAC-LC đúng 1024 mẫu): các chương nối liền nhau, không phụ thuộc mốc giờ trong từng file chương.
                        info.set(0, size, (offset + frames) * ListenExport.AAC_FRAME * 1_000_000L / rate, flags)
                        muxer.writeSampleData(trackIndex, track, info)
                        frames += 1
                        extractor.advance()
                    }
                    if (frames == 0L) throw Mp3Export.Refused("File tạm của “${chapter.fullTitle}” rỗng - xuất lại để làm lại chương này")
                    offset += frames
                } finally {
                    runCatching { extractor.release() }
                }
                progress(index + 1, plan.chapters.size, (index + 1.0) / plan.chapters.size)
            }
            muxer.stop()
        } catch (error: Throwable) {
            runCatching { if (started) muxer.stop() }
            runCatching { muxer.release() }
            target.delete()
            throw error
        }
        muxer.release()
        return marks(plan.chapters.map { it.fullTitle }, starts, offset, rate, delay)
    }

    /** Mốc chương: chương i bắt đầu ở `starts[i]` khung AAC, mốc cuối là hết luồng (`total` khung); cả luồng bị cắt `delay` mẫu ở đầu. */
    fun marks(titles: List<String>, starts: List<Long>, total: Long, rate: Int, delay: Int): List<Mp4Finish.Mark> {
        fun ms(samples: Long) = Math.round(samples.coerceAtLeast(0) * 1000.0 / rate)
        val frame = ListenExport.AAC_FRAME.toLong()
        return titles.mapIndexed { index, title ->
            val end = if (index + 1 < starts.size) starts[index + 1] * frame else total * frame - delay
            Mp4Finish.Mark(title, ms(starts[index] * frame), ms(end))
        }
    }
}
