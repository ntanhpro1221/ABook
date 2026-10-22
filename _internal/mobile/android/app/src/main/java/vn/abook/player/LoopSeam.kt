package vn.abook.player

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.SystemClock
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.MediaItem
import androidx.media3.common.StreamKey
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.decoder.DecoderInputBuffer
import androidx.media3.exoplayer.FormatHolder
import androidx.media3.exoplayer.LoadingInfo
import androidx.media3.exoplayer.SeekParameters
import androidx.media3.exoplayer.drm.DrmSessionManagerProvider
import androidx.media3.exoplayer.source.MediaPeriod
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.exoplayer.source.SampleStream
import androidx.media3.exoplayer.source.TrackGroupArray
import androidx.media3.exoplayer.source.WrappingMediaSource
import androidx.media3.exoplayer.trackselection.ExoTrackSelection
import androidx.media3.exoplayer.upstream.Allocator
import androidx.media3.exoplayer.upstream.LoadErrorHandlingPolicy
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.roundToInt
import kotlin.math.roundToLong

/**
 * Phép thử khả thi P3 (PLAN_loop §41, SPEC_loop_p3.md): MỘT ExoPlayer phát [Clip(audibleStart', loopEnd' - X'), Nối, Clip(loopStart' + X', loopEnd' - X'), Nối, ...]
 * trong đó Nối là đoạn mờ chéo [loopEnd' - X', loopEnd'] -> [loopStart', loopStart' + X'] dựng SẴN thành WAV. CHƯA nối vào [MusicBed]: chỉ bài thử
 * `MusicLoopSeamTest` dùng.
 *
 * Trục thời gian: ExoPlayer phát Clip với `startPositionMs != 0` thì ClippingMediaPeriod xoá encoderDelay của Format (và endPositionMs thì xoá encoderPadding), nên
 * KHÔNG cắt mẫu nào của bộ giải mã: mẫu n của Clip (tính từ khung đầu sau khung Xing/Info) là mẫu n của bộ giải mã chạy liền từ đầu file. Vì thế
 * [decode] gỡ `encoder-delay` / `encoder-padding` khỏi định dạng nạp cho MediaCodec (không thì codec tự cắt ~1105 mẫu đầu và lệch trục với ExoPlayer), rồi đếm mẫu từ đầu,
 * KHÔNG tua (MediaExtractor tua theo mục lục Xing thì lệch 0,3-2,2 s, xem [ExactSeekMp3Extractor]). Clip đầu bắt đầu ở 0 thì ExoPlayer lại cắt encoderDelay: [build] đẩy
 * audibleStart' lên một khung trong trường hợp ấy.
 *
 * Đo trên máy ảo (PLAN_loop §41, lượt thử p3thu1): bộ giải mã mp3 của Android (c2.android.mp3.decoder) mỗi lần khởi động bỏ 529 mẫu đầu của đầu ra
 * (độ trễ bộ giải mã; vì thế R = đầu ra liền cũng đã ở trục "đã bỏ 529") rồi khi hết dòng thì đệm 529 mẫu 0 ở cuối. Hai hệ quả ở mỗi Clip:
 * (1) Clip bắt đầu giữa file thì bộ giải mã chạy nguội (không có khung trước: chồng MDCT = 0, bể bit rỗng), ~350 mẫu đầu sai (khuếch đại 0,5 -> 1);
 * (2) 529 mẫu CUỐI Clip là số 0 thay vì tiếng. Cách chữa (`prerollFrames` > 0): Clip mở sớm [prerollFrames] khung và đóng muộn một khung, rồi
 * [mediaSourceFactory] ghi đè `Format.encoderDelay` = prerollFrames * khung và `encoderPadding` = khung (sau khi ClippingMediaPeriod đã tự xoá về 0) để
 * TrimmingAudioProcessor của sink cắt đúng ngần ấy mẫu ở đầu và cuối. Trục đầu ra của codec đã bỏ 529 nên số cắt là bội đúng của khung, không có 529.
 */
@OptIn(UnstableApi::class)
object LoopSeam {
    class Bounds(val audibleStart: Double, val loopStart: Double, val loopEnd: Double)

    /** Mọi vị trí tính bằng MẪU (mỗi mẫu = một khung PCM của mọi kênh) trên trục giải mã liền; đều là bội của [frameSamples]. */
    class Seam(
        val file: File,
        val wav: File,
        val audibleStartSamples: Long,
        val loopStartSamples: Long,
        val loopEndSamples: Long,
        val xFrames: Int,
        val sampleRate: Int,
        val channels: Int,
        val frameSamples: Int,
        val buildMs: Long,
        /** Số khung mở sớm ở đầu Clip lặp (và cũng là cờ: 0 = bản gốc của SPEC, không chữa; > 0 thì đóng muộn một khung ở cuối mọi Clip). */
        val prerollFrames: Int = 0,
    ) {
        val prerollSamples get() = prerollFrames * frameSamples
        /** Khung đóng muộn ở cuối Clip (đệm 0 của bộ giải mã rơi vào đó rồi bị cắt). */
        val tailSamples get() = if (prerollFrames > 0) frameSamples else 0
        val audibleStart get() = audibleStartSamples.toDouble() / sampleRate
        val loopStart get() = loopStartSamples.toDouble() / sampleRate
        val loopEnd get() = loopEndSamples.toDouble() / sampleRate

        /** Mili giây làm tròn XUỐNG như [MusicBed.open]: khung ấy vẫn được giữ (ExoPlayer bỏ khung có nhãn trước chỗ bắt đầu). Số nguyên: 48 kHz thì mọi khung là bội 24 ms đúng. */
        fun ms(samples: Long): Long = samples * 1000 / sampleRate

        val clip0StartMs get() = ms(audibleStartSamples)
        val clip0EndMs get() = ms(loopEndSamples - xFrames + tailSamples)
        val loopClipStartMs get() = ms(loopStartSamples + xFrames - prerollSamples)
        val loopClipEndMs get() = ms(loopEndSamples - xFrames + tailSamples)
        /** Khoảng (ms) giữa mốc Clip lặp mở sớm (trục cửa sổ ExoPlayer, 0 = [loopClipStartMs]) và mẫu đầu sau khi cắt preroll: vị trí cửa sổ t ứng với vị trí danh nghĩa t - lead. */
        val loopClipLeadMs get() = (loopStartSamples + xFrames) * 1000.0 / sampleRate - loopClipStartMs
        val clip0Ms get() = clip0EndMs - clip0StartMs
        val loopClipMs get() = loopClipEndMs - loopClipStartMs
        val seamMs get() = xFrames * 1000L / sampleRate
    }

    /** Số khung mở sớm mặc định. Đo của Music (ffmpeg): sai tối đa 2107 mẫu sau khởi động nguội = 1,83 khung. */
    const val PREROLL_FRAMES = 3

    /** Số mẫu cắt đầu / cuối của một mục (ghi đè Format; xem đầu lớp). Gắn vào MediaItem làm tag. */
    internal class Trim(val delay: Int, val padding: Int)

    class Decoded(val sampleRate: Int, val channels: Int, val samples: Long, val firstPtsUs: Long, val maxSkewSamples: Long)

    /** Tần số + số kênh mà MediaExtractor báo cho file (= đầu ra bộ giải mã mp3). */
    fun probeFormat(file: File): Pair<Int, Int> {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(file.absolutePath)
            val index = (0 until extractor.trackCount).first { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
            val format = extractor.getTrackFormat(index)
            return format.getInteger(MediaFormat.KEY_SAMPLE_RATE) to format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
        } finally {
            extractor.release()
        }
    }

    /**
     * Giải mã LIỀN MỘT MẠCH từ đầu file (không tua, không cắt encoderDelay / encoderPadding) ra PCM16 LE; `onPcm(mẫu đầu, bộ đệm)` mỗi khối ra (bộ đệm chỉ hợp lệ trong lệnh gọi).
     * Dừng khi đã đủ `stopAt` mẫu. `maxSkewSamples` = độ lệch lớn nhất giữa nhãn thời gian của codec và số mẫu đã đếm (0 khi trục khớp).
     */
    fun decode(file: File, stopAt: Long = Long.MAX_VALUE, onPcm: (Long, ByteBuffer) -> Unit): Decoded {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(file.absolutePath)
            val index = (0 until extractor.trackCount).first { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
            extractor.selectTrack(index)
            val format = extractor.getTrackFormat(index)
            // ExoPlayer không cắt gì ở Clip có mốc đầu/cuối (xem đầu lớp); codec nhận hai khoá này thì tự cắt (SkipCutBuffer) -> đặt 0.
            format.setInteger("encoder-delay", 0)
            format.setInteger("encoder-padding", 0)
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
            codec.configure(format, null, null, 0)
            codec.start()
            var rate = format.getInteger(MediaFormat.KEY_SAMPLE_RATE)
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var count = 0L
            var firstPts = -1L
            var skew = 0L
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var idle = 0
            while (count < stopAt) {
                if (!inputDone) {
                    val slot = codec.dequeueInputBuffer(10_000)
                    if (slot >= 0) {
                        val size = extractor.readSampleData(codec.getInputBuffer(slot)!!, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(slot, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(slot, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val out = codec.dequeueOutputBuffer(info, 10_000)
                when {
                    out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val shown = codec.outputFormat
                        rate = shown.getInteger(MediaFormat.KEY_SAMPLE_RATE)
                        channels = shown.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        val encoding = if (shown.containsKey(MediaFormat.KEY_PCM_ENCODING)) shown.getInteger(MediaFormat.KEY_PCM_ENCODING) else android.media.AudioFormat.ENCODING_PCM_16BIT
                        check(encoding == android.media.AudioFormat.ENCODING_PCM_16BIT) { "bộ giải mã ra PCM định dạng $encoding, không phải 16 bit" }
                    }
                    out >= 0 -> {
                        idle = 0
                        if (info.size > 0) {
                            val buffer = codec.getOutputBuffer(out)!!
                            buffer.position(info.offset)
                            buffer.limit(info.offset + info.size)
                            if (firstPts < 0) firstPts = info.presentationTimeUs
                            skew = maxOf(skew, Math.abs((info.presentationTimeUs * rate / 1_000_000.0).roundToLong() - count))
                            onPcm(count, buffer.slice().order(ByteOrder.LITTLE_ENDIAN))
                            count += info.size / (2 * channels)
                        }
                        val end = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                        codec.releaseOutputBuffer(out, false)
                        if (end) break
                    }
                    out == MediaCodec.INFO_TRY_AGAIN_LATER -> if (inputDone && ++idle > 300) break // codec không trả EOS: 3 giây im thì thôi
                }
            }
            return Decoded(rate, channels, count, firstPts, skew)
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            extractor.release()
        }
    }

    /**
     * Dựng Nối của `file`: biên căn khung mp3 ([ExactSeekMp3Extractor.frameBoundarySeconds]), X' = X làm tròn về bội số khung gần nhất, hai vùng
     * [loopEnd' - X', loopEnd'] và [loopStart', loopStart' + X'] lấy từ MỘT lần giải mã liền ([decode]), trộn tuyến tính theo mẫu ([mix]), ghi WAV PCM16 cùng tần số / kênh
     * vào `cacheDir/loopseam/<khoá>.wav`.
     */
    fun build(context: Context, file: File, bounds: Bounds, xSeconds: Double, prerollFrames: Int = PREROLL_FRAMES): Seam {
        val began = SystemClock.elapsedRealtime()
        val (rate, channels) = probeFormat(file)
        val spf = if (rate >= 32000) 1152 else 576 // như ExactSeekMp3Extractor.frameBoundarySeconds
        fun frames(seconds: Double) = (ExactSeekMp3Extractor.frameBoundarySeconds(seconds, rate) * rate / spf).roundToLong()
        val kx = maxOf(1L, (xSeconds * rate / spf).roundToLong())
        // Clip đầu bắt đầu ở 0 thì ExoPlayer còn cắt encoderDelay (lệch trục 1105 mẫu so với các Clip khác): dời một khung.
        val ka = maxOf(1L, frames(bounds.audibleStart))
        val ks = frames(bounds.loopStart)
        val ke = frames(bounds.loopEnd)
        require(ks >= 0 && ke - ks > 2 * kx + 8 && ke - kx > ka) { "vòng quá ngắn cho Nối ($kx khung): audible=$ka loopStart=$ks loopEnd=$ke (khung)" }
        val n = (kx * spf).toInt()
        val oldStart = (ke - kx) * spf
        val newStart = ks * spf
        val old = ShortArray(n * channels)
        val new = ShortArray(n * channels)
        var filled = 0L
        val decoded = decode(file, stopAt = ke * spf) { first, pcm ->
            filled += copyInto(first, pcm, channels, oldStart, old) + copyInto(first, pcm, channels, newStart, new)
        }
        check(decoded.sampleRate == rate && decoded.channels == channels) { "đầu ra bộ giải mã ${decoded.sampleRate}/${decoded.channels} khác định dạng đầu vào $rate/$channels" }
        check(filled == 2L * n) { "giải mã thiếu: được $filled / ${2L * n} mẫu (file ngắn hơn loopEnd'?)" }
        val mixed = mix(old, new, channels)
        val dir = File(context.cacheDir, "loopseam").apply { mkdirs() }
        val wav = File(dir, "%08x.wav".format((file.absolutePath + file.length() + "/" + ka + "/" + ks + "/" + ke + "/" + kx).hashCode()))
        writeWav(wav, mixed, rate, channels)
        return Seam(file, wav, ka * spf, ks * spf, ke * spf, n, rate, channels, spf, SystemClock.elapsedRealtime() - began, prerollFrames)
    }

    /** Chép phần của khối `pcm` (mẫu đầu `first`) rơi vào vùng [start, start + dest.size / channels); trả số mẫu đã chép. */
    private fun copyInto(first: Long, pcm: ByteBuffer, channels: Int, start: Long, dest: ShortArray): Int {
        val count = pcm.remaining() / (2 * channels)
        val from = maxOf(first, start)
        val to = minOf(first + count, start + dest.size / channels)
        if (to <= from) return 0
        val shorts = pcm.asShortBuffer()
        shorts.position(((from - first) * channels).toInt())
        shorts.get(dest, ((from - start) * channels).toInt(), ((to - from) * channels).toInt())
        return (to - from).toInt()
    }

    /** out[n] = (1 - n/N) * old[n] + (n/N) * new[n], n = 0..N-1 (N = số mẫu mỗi kênh), làm tròn và kẹp về PCM16. */
    internal fun mix(old: ShortArray, new: ShortArray, channels: Int): ShortArray {
        require(old.size == new.size && old.size % channels == 0)
        val n = old.size / channels
        val out = ShortArray(old.size)
        for (i in 0 until n) {
            val w = i.toDouble() / n
            for (c in 0 until channels) {
                val k = i * channels + c
                out[k] = ((1 - w) * old[k] + w * new[k]).roundToInt().coerceIn(-32768, 32767).toShort()
            }
        }
        return out
    }

    internal fun wavHeader(sampleRate: Int, channels: Int, dataBytes: Int): ByteArray {
        val b = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        b.put("RIFF".toByteArray()).putInt(36 + dataBytes).put("WAVE".toByteArray())
        b.put("fmt ".toByteArray()).putInt(16).putShort(1).putShort(channels.toShort()).putInt(sampleRate)
        b.putInt(sampleRate * channels * 2).putShort((channels * 2).toShort()).putShort(16)
        b.put("data".toByteArray()).putInt(dataBytes)
        return b.array()
    }

    private fun writeWav(file: File, samples: ShortArray, rate: Int, channels: Int) {
        val data = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        data.asShortBuffer().put(samples)
        FileOutputStream(file).use {
            it.write(wavHeader(rate, channels, samples.size * 2))
            it.write(data.array())
        }
    }

    private fun item(file: File, id: String, startMs: Long? = null, endMs: Long? = null, trim: Trim? = null): MediaItem {
        val builder = MediaItem.Builder().setUri(Uri.fromFile(file)).setMediaId(id)
        if (trim != null) builder.setTag(trim)
        if (startMs != null && endMs != null) {
            builder.setClippingConfiguration(MediaItem.ClippingConfiguration.Builder().setStartPositionMs(startMs).setEndPositionMs(endMs).build())
        }
        return builder.build()
    }

    private fun seamItem(seam: Seam) = item(seam.wav, "seam")
    private fun loopClip(seam: Seam) = item(seam.file, "loop", seam.loopClipStartMs, seam.loopClipEndMs, trimOf(seam, seam.prerollSamples))
    private fun trimOf(seam: Seam, delay: Int) = if (seam.prerollFrames > 0) Trim(delay, seam.tailSamples) else null

    /** Danh sách đầu cho MỘT ExoPlayer: [Clip(audibleStart', loopEnd' - X'), Nối, Clip(loopStart' + X', loopEnd' - X'), Nối]; phần sau do [attach] thêm. */
    fun mediaItems(seam: Seam): List<MediaItem> =
        listOf(item(seam.file, "first", seam.clip0StartMs, seam.clip0EndMs, trimOf(seam, 0)), seamItem(seam)) + loopPair(seam)

    /** Một vòng lặp: [Clip(loopStart' + X', loopEnd' - X'), Nối]. */
    fun loopPair(seam: Seam): List<MediaItem> = listOf(loopClip(seam), seamItem(seam))

    /**
     * Cơ chế lặp: THÊM MỤC ĐỘNG. Mỗi lần ExoPlayer chuyển mục (kể cả tua sang mục khác) mà sau mục hiện tại còn < `ahead` mục thì nối thêm vòng [loopPair].
     * Chọn cách này thay vì lặp nguồn vì mỗi mục có Clip mốc riêng nên Nối-rồi-Clip giữ nguyên bảng mục (index lẻ = Nối, index chẵn >= 2 = Clip lặp) cho bộ đo, và
     * vòng dài vô hạn mà bộ nhớ chỉ đổi theo số vòng đã qua (bản app thật sẽ bỏ mục đã qua bằng removeMediaItems). Gọi `removeListener` khi đổi bài.
     */
    fun attach(player: Player, seam: Seam, ahead: Int = 3): Player.Listener {
        fun top() {
            while (player.mediaItemCount - 1 - player.currentMediaItemIndex < ahead) player.addMediaItems(loopPair(seam))
        }
        val listener = object : Player.Listener {
            override fun onMediaItemTransition(mediaItem: MediaItem?, reason: Int) = top()
        }
        player.addListener(listener)
        top()
        return listener
    }

    /**
     * Bọc `inner`: mục có tag [Trim] (Clip của [mediaItems]) được ghi đè `Format.encoderDelay` / `encoderPadding` SAU ClippingMediaPeriod (nó tự đặt cả hai về 0 khi mốc đầu /
     * cuối khác mặc định). TrimmingAudioProcessor của sink cắt đúng số mẫu ấy ở đầu / cuối mục. Cắt đầu chỉ chạy ở lần cấu hình sink đầu tiên của mục (chuyển mục liền
     * hay tua sang MỤC khác): tua trong cùng mục không cắt lại.
     * Lưu ý cho app thật: tua THẲNG vào giữa một Clip lặp từ mục khác cũng bị cắt `prerollSamples` đầu tiên (âm đi trước vị trí báo ~78 ms ở 44,1 kHz) - cần mục không preroll
     * cho cú tua, hay bù vị trí.
     */
    fun mediaSourceFactory(inner: MediaSource.Factory): MediaSource.Factory = object : MediaSource.Factory {
        override fun setDrmSessionManagerProvider(drmSessionManagerProvider: DrmSessionManagerProvider): MediaSource.Factory = apply { inner.setDrmSessionManagerProvider(drmSessionManagerProvider) }
        override fun setLoadErrorHandlingPolicy(loadErrorHandlingPolicy: LoadErrorHandlingPolicy): MediaSource.Factory = apply { inner.setLoadErrorHandlingPolicy(loadErrorHandlingPolicy) }
        override fun getSupportedTypes(): IntArray = inner.supportedTypes
        override fun createMediaSource(mediaItem: MediaItem): MediaSource {
            val source = inner.createMediaSource(mediaItem)
            val trim = mediaItem.localConfiguration?.tag as? Trim ?: return source
            return TrimSource(source, trim)
        }
    }

    private class TrimSource(source: MediaSource, val trim: Trim) : WrappingMediaSource(source) {
        override fun createPeriod(id: MediaSource.MediaPeriodId, allocator: Allocator, startPositionUs: Long): MediaPeriod =
            TrimPeriod(super.createPeriod(id, allocator, startPositionUs), trim)

        override fun releasePeriod(mediaPeriod: MediaPeriod) = super.releasePeriod((mediaPeriod as TrimPeriod).inner)
    }

    /** MediaPeriod chuyển mọi lệnh cho `inner`, chỉ bọc SampleStream để sửa Format (và đổi chủ trong callback: ExoPlayer so sánh MediaPeriod theo địa chỉ). */
    private class TrimPeriod(val inner: MediaPeriod, val trim: Trim) : MediaPeriod {
        private class Stream(val inner: SampleStream, val trim: Trim) : SampleStream by inner {
            override fun readData(formatHolder: FormatHolder, buffer: DecoderInputBuffer, readFlags: Int): Int {
                val result = inner.readData(formatHolder, buffer, readFlags)
                if (result == C.RESULT_FORMAT_READ) {
                    formatHolder.format = formatHolder.format!!.buildUpon().setEncoderDelay(trim.delay).setEncoderPadding(trim.padding).build()
                }
                return result
            }
        }

        override fun prepare(callback: MediaPeriod.Callback, positionUs: Long) = inner.prepare(object : MediaPeriod.Callback {
            override fun onPrepared(mediaPeriod: MediaPeriod) = callback.onPrepared(this@TrimPeriod)
            override fun onContinueLoadingRequested(source: MediaPeriod) = callback.onContinueLoadingRequested(this@TrimPeriod)
        }, positionUs)

        override fun maybeThrowPrepareError() = inner.maybeThrowPrepareError()
        override fun getTrackGroups(): TrackGroupArray = inner.trackGroups
        override fun getStreamKeys(trackSelections: List<ExoTrackSelection>): List<StreamKey> = inner.getStreamKeys(trackSelections)

        override fun selectTracks(selections: Array<ExoTrackSelection?>, mayRetainStreamFlags: BooleanArray, streams: Array<SampleStream?>, streamResetFlags: BooleanArray, positionUs: Long): Long {
            val raw = Array(streams.size) { (streams[it] as? Stream)?.inner ?: streams[it] }
            val result = inner.selectTracks(selections, mayRetainStreamFlags, raw, streamResetFlags, positionUs)
            for (i in streams.indices) {
                val s = raw[i]
                val old = streams[i] as? Stream
                streams[i] = if (s == null) null else if (old != null && old.inner === s) old else Stream(s, trim)
            }
            return result
        }

        override fun discardBuffer(positionUs: Long, toKeyframe: Boolean) = inner.discardBuffer(positionUs, toKeyframe)
        override fun readDiscontinuity(): Long = inner.readDiscontinuity()
        override fun setUsesStreamPrerollFlags() = inner.setUsesStreamPrerollFlags()
        override fun seekToUs(positionUs: Long): Long = inner.seekToUs(positionUs)
        override fun getAdjustedSeekPositionUs(positionUs: Long, seekParameters: SeekParameters): Long = inner.getAdjustedSeekPositionUs(positionUs, seekParameters)
        override fun getBufferedPositionUs(): Long = inner.bufferedPositionUs
        override fun getNextLoadPositionUs(): Long = inner.nextLoadPositionUs
        override fun continueLoading(loadingInfo: LoadingInfo): Boolean = inner.continueLoading(loadingInfo)
        override fun isLoading(): Boolean = inner.isLoading
        override fun reevaluateBuffer(positionUs: Long) = inner.reevaluateBuffer(positionUs)
        override fun setEndPositionUs(endPositionUs: Long): Long = inner.setEndPositionUs(endPositionUs)
    }
}
