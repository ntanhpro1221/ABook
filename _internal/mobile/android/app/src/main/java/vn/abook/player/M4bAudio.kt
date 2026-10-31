package vn.abook.player

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import org.json.JSONObject
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.roundToLong

/**
 * Mã hoá âm thanh của "Xuất M4B" bằng chính bộ giải mã / mã hoá AAC của Android (MediaExtractor + MediaCodec + MediaMuxer): từng chương
 * giải mã ra PCM 16-bit, đổi về định dạng chung của cuốn (theo chương đầu: cùng tần số, 1 hay 2 kênh - như máy tính), mã hoá AAC-LC
 * (64 kb/s mono, 96 kb/s stereo - số của máy tính). Không kèm nhạc: đổ liên tục vào MỘT bộ mã hoá, đếm số khung PCM đã đổ nên mốc mỗi
 * chương đúng tới từng mẫu (như trước khi có nhạc nền). Kèm nhạc nền: mỗi chương một bộ mã hoá rồi nối khung thành một luồng liền
 * ([AacJoin]: lưới khung chung, đỉnh thật kiểm sau mã hoá, chương vượt trần mã hoá lại riêng).
 */
object M4bAudio : M4bExport.AudioEncoder {
    private const val TIMEOUT_US = 10_000L
    private const val BITRATE_MONO = 64_000
    private const val BITRATE_STEREO = 96_000
    private const val MONO_SIDECAR = ".mono.json" // music_export.MONO_SIDECAR

    /**
     * Độ trễ của bộ mã hoá AAC-LC phần mềm của Android (c2.android.aac.encoder, thư viện FDK): đo trên máy ảo - tiếng ra khỏi bộ giải mã
     * trễ đúng 2048 mẫu so với tiếng vào, như độ trễ chuẩn của AAC-LC (khung 1024 x 2).
     */
    override val delay = 2048

    override fun encode(plan: Mp3Export.Plan, target: File, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit): List<Mp4Finish.Mark> =
        encoder({ _, _, _, _ -> }, {}).encode(plan, target, stopped, progress)

    /**
     * Như [encode] nhưng báo pha (trộn nhạc, kiểm đỉnh, mã hoá lại) cho `watch` và kết quả đo đỉnh cho `done` - việc nền của "Xuất M4B".
     * Kế hoạch không nhạc, không kiểm đỉnh (`plan.music` / `plan.guard` null) đi đường một bộ mã hoá như cũ.
     */
    fun encoder(watch: AacJoin.Watch, done: (AacJoin.Encoded) -> Unit): M4bExport.AudioEncoder = object : M4bExport.AudioEncoder {
        override val delay = M4bAudio.delay
        override fun encode(plan: Mp3Export.Plan, target: File, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit): List<Mp4Finish.Mark> =
            if (plan.music == null && plan.guard == null) whole(plan, target, stopped, progress)
            else AacJoin.encode(plan, target, Codec(), stopped, progress, watch).also(done).marks
    }

    /** Cả cuốn qua MỘT bộ mã hoá AAC (đường không kèm nhạc). */
    private fun whole(plan: Mp3Export.Plan, target: File, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit): List<Mp4Finish.Mark> {
        val (rate, channels) = layout(plan.chapters.first().file)
        // Phần của cả cuốn mỗi chương chiếm (theo thời lượng trong sách; không có thì chia đều) - để thanh tiến độ chạy đều.
        val weights = plan.chapters.map { it.duration.coerceAtLeast(0.0) }
        val weighted = weights.sum() > 0.0
        val total = if (weighted) weights.sum() else plan.chapters.size.toDouble()
        val shares = weights.map { (if (weighted) it else 1.0) / total }
        val sink = AacSink(target, rate, channels)
        val marks = ArrayList<Mp4Finish.Mark>()
        try {
            var start = 0L
            var before = 0.0
            progress(0, plan.chapters.size, 0.0)
            plan.chapters.forEachIndexed { index, chapter ->
                if (stopped()) throw Mp3Export.Stopped()
                val base = before
                val frames = decodeInto(chapter, sink, stopped) { fraction ->
                    progress(index, plan.chapters.size, (base + shares[index] * fraction).coerceAtMost(0.99))
                }
                marks += Mp4Finish.Mark(chapter.fullTitle, millis(start, rate), millis(start + frames, rate))
                start += frames
                before += shares[index]
                progress(index + 1, plan.chapters.size, before.coerceAtMost(0.99))
            }
            sink.finish()
        } catch (error: Throwable) {
            sink.abort()
            target.delete()
            throw error
        }
        return marks
    }

    private fun millis(frames: Long, rate: Int) = (frames * 1000.0 / rate).roundToLong()

    /** Giải mã một chương đổ vào `sink`; trả số khung PCM (theo tần số chung) đã đổ. `fraction(0..1)` theo vị trí đọc trong chương. */
    private fun decodeInto(chapter: Mp3Export.Chapter, sink: AacSink, stopped: () -> Boolean, fraction: (Double) -> Unit): Long {
        val before = sink.frames
        decodeFile(chapter.file, sink.rate, sink.channels, stopped, fraction) { pcm, count -> sink.write(pcm, count) }
        return sink.frames - before
    }

    /**
     * MediaCodec cho [AacJoin] (một lượt xuất): mỗi chương một [AacEncoder]; cấu hình luồng (csd) lấy từ bộ mã hoá đầu tiên - mọi bộ mã hoá
     * cùng cấu hình nên cùng csd - để giải mã lại khung bất kỳ và ghi MP4.
     */
    class Codec : AacJoin.Codec {
        @Volatile private var format: MediaFormat? = null

        override val delay: Int get() = M4bAudio.delay

        override fun layout(file: File): Pair<Int, Int> = M4bAudio.layout(file)

        override fun decode(file: File, rate: Int, channels: Int, stopped: () -> Boolean, fraction: (Double) -> Unit, write: (ShortArray, Int) -> Unit) =
            decodeFile(file, rate, channels, stopped, fraction, write)

        override fun encoder(rate: Int, channels: Int, unit: (ByteArray) -> Unit): ListenExport.PcmOutput =
            AacEncoder(rate, channels, { if (format == null) format = it }) { data, info ->
                unit(ByteArray(info.size).also { data.get(it) })
            }

        override fun decodeUnits(units: Iterator<ByteArray>, rate: Int, channels: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) =
            M4bAudio.decodeUnits(format ?: throw Mp3Export.Refused("Bộ mã hoá AAC chưa ra cấu hình"), units, rate, channels, stopped, write)

        override fun mux(target: File, rate: Int, channels: Int, units: Iterator<ByteArray>, stopped: () -> Boolean) {
            val track = AacTrack(target, format ?: throw Mp3Export.Refused("Không có âm thanh nào để ghi"), rate)
            try {
                var index = 0L
                for (unit in units) {
                    if (index % 256 == 0L && stopped()) throw Mp3Export.Stopped()
                    track.write(ByteBuffer.wrap(unit), unit.size, index++)
                }
                track.finish()
            } catch (error: Throwable) {
                track.abort()
                target.delete()
                throw error
            }
        }
    }

    /** Đỉnh thật (dBTP) của một file âm thanh đã mã hoá - bản tạm một chương kèm nhạc của "Xuất sách nói" (đo sau AAC như máy tính). */
    fun truePeak(file: File, guard: MusicRender.Params, stopped: () -> Boolean): Double {
        val (rate, channels) = layout(file)
        val meter = TruePeak(guard, channels)
        decodeFile(file, rate, channels, stopped) { pcm, count -> meter.feed(pcm, count) }
        return meter.finish()[0]
    }

    /**
     * Giải mã các khung AAC `units` (cấu hình `format` của bộ mã hoá đã ra chúng) ra PCM 16-bit ở `rate`/`channels`: đúng [AacJoin.FRAME]
     * khung PCM mỗi khung AAC - bộ giải mã ra thừa thì cắt, thiếu thì đệm lặng ở cuối, để độ dài giữ đúng lưới khung.
     */
    internal fun decodeUnits(format: MediaFormat, units: Iterator<ByteArray>, rate: Int, channels: Int, stopped: () -> Boolean, write: (ShortArray, Int) -> Unit) {
        val input = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, channels)
        format.getByteBuffer("csd-0")?.let { input.setByteBuffer("csd-0", it.duplicate()) }
        val codec = MediaCodec.createDecoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
        val info = MediaCodec.BufferInfo()
        var fed = 0L    // khung AAC đã nạp
        var given = 0L  // mẫu (xen kẽ kênh) đã đưa ra
        try {
            codec.configure(input, null, null, 0)
            codec.start()
            var inputDone = false
            var idle = 0
            while (true) {
                if (stopped()) throw Mp3Export.Stopped()
                if (!inputDone) {
                    val slot = codec.dequeueInputBuffer(TIMEOUT_US)
                    if (slot >= 0) {
                        if (!units.hasNext()) {
                            codec.queueInputBuffer(slot, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            val unit = units.next()
                            codec.getInputBuffer(slot)!!.apply { clear(); put(unit) }
                            codec.queueInputBuffer(slot, 0, unit.size, fed * AacJoin.FRAME * 1_000_000L / rate, 0)
                            fed++
                        }
                    }
                }
                val out = codec.dequeueOutputBuffer(info, TIMEOUT_US)
                if (out >= 0) {
                    idle = 0
                    if (info.size > 0) {
                        val shorts = codec.getOutputBuffer(out)!!.apply { position(info.offset); limit(info.offset + info.size) }
                            .order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
                        val room = fed * AacJoin.FRAME * channels - given
                        val take = minOf(shorts.remaining().toLong(), maxOf(0L, room)).toInt()
                        if (take > 0) {
                            val pcm = ShortArray(take).also { shorts.get(it) }
                            write(pcm, take)
                            given += take
                        }
                    }
                    codec.releaseOutputBuffer(out, false)
                    if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                } else if (out < 0 && out != MediaCodec.INFO_OUTPUT_FORMAT_CHANGED && inputDone && ++idle > 500) {
                    throw Mp3Export.Refused("Chưa giải mã lại được âm thanh vừa mã hoá")
                }
            }
            val owed = fed * AacJoin.FRAME * channels - given
            if (owed > 0) write(ShortArray(owed.toInt()), owed.toInt())
        } catch (error: Mp3Export.Stopped) {
            throw error
        } catch (error: Mp3Export.Refused) {
            throw error
        } catch (error: Exception) {
            throw Mp3Export.Refused("Chưa giải mã lại được âm thanh vừa mã hoá")
        } finally {
            runCatching { codec.stop() }
            runCatching { codec.release() }
        }
    }

    private fun audioTrack(extractor: MediaExtractor): Int =
        (0 until extractor.trackCount).firstOrNull { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true } ?: -1

    /** (tần số, số kênh 1|2) của một file - như `_audio_layout` của máy tính. */
    internal fun layout(file: File): Pair<Int, Int> {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(file.absolutePath)
            val index = audioTrack(extractor)
            if (index < 0) throw Mp3Export.Refused("Chưa đọc được âm thanh của ${file.name}")
            val format = extractor.getTrackFormat(index)
            return format.getInteger(MediaFormat.KEY_SAMPLE_RATE) to if (format.getInteger(MediaFormat.KEY_CHANNEL_COUNT) == 1) 1 else 2
        } catch (error: Mp3Export.Refused) {
            throw error
        } catch (error: Exception) {
            throw Mp3Export.Refused("Chưa đọc được âm thanh của ${file.name}")
        } finally {
            extractor.release()
        }
    }

    /**
     * Giải mã MỘT file âm thanh (MP3 của chương, hay clip giọng đọc của "Xuất sách nói") ra PCM 16-bit xen kẽ ở (`toRate`, `toChannels`), từng khối đưa cho `write(mẫu, số mẫu)`.
     * Lỗi của `write` (hết chỗ...) ném ra nguyên văn, không bị nhầm với lỗi giải mã. Độ trễ / đệm của bộ mã hoá (`encoder-delay` /
     * `encoder-padding` mà `MediaExtractor` đọc từ thẻ LAME/iTunSMPB) do chính MediaCodec bỏ (SkipCutBuffer của CCodec, cấu hình bằng
     * format của extractor) - như ffmpeg của máy tính tự bỏ; không cắt thêm ở đây.
     */
    internal fun decodeFile(file: File, toRate: Int, toChannels: Int, stopped: () -> Boolean, fraction: (Double) -> Unit = {}, write: (ShortArray, Int) -> Unit) {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(file.absolutePath)
            val index = audioTrack(extractor)
            if (index < 0) throw Mp3Export.Refused("Chưa đọc được âm thanh của ${file.name}")
            extractor.selectTrack(index)
            val format = extractor.getTrackFormat(index)
            val length = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION).toDouble() else 0.0
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
            codec.configure(format, null, null, 0)
            codec.start()
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var converter = M4bExport.PcmConverter(format.getInteger(MediaFormat.KEY_SAMPLE_RATE), channels, toRate, toChannels)
            var float = false
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var idle = 0
            while (true) {
                if (stopped()) throw Mp3Export.Stopped()
                if (!inputDone) {
                    val slot = codec.dequeueInputBuffer(TIMEOUT_US)
                    if (slot >= 0) {
                        val size = extractor.readSampleData(codec.getInputBuffer(slot)!!, 0)
                        if (size < 0) {
                            codec.queueInputBuffer(slot, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            if (length > 0) fraction((extractor.sampleTime / length).coerceIn(0.0, 1.0))
                            codec.queueInputBuffer(slot, 0, size, extractor.sampleTime, 0)
                            extractor.advance()
                        }
                    }
                }
                val out = codec.dequeueOutputBuffer(info, TIMEOUT_US)
                when {
                    out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        val shown = codec.outputFormat
                        channels = shown.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
                        converter = M4bExport.PcmConverter(shown.getInteger(MediaFormat.KEY_SAMPLE_RATE), channels, toRate, toChannels)
                        float = shown.containsKey(MediaFormat.KEY_PCM_ENCODING) && shown.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                    }
                    out >= 0 -> {
                        idle = 0
                        if (info.size > 0) {
                            val buffer = codec.getOutputBuffer(out)!!
                            buffer.position(info.offset).limit(info.offset + info.size)
                            buffer.order(ByteOrder.LITTLE_ENDIAN)
                            val samples = if (float) {
                                val floats = buffer.asFloatBuffer()
                                ShortArray(floats.remaining()) { (floats.get() * 32767f).toInt().coerceIn(-32768, 32767).toShort() }
                            } else {
                                val shorts = buffer.asShortBuffer()
                                ShortArray(shorts.remaining()).also { shorts.get(it) }
                            }
                            val usable = samples.size / channels * channels
                            if (usable > 0) {
                                val converted = converter.convert(samples, usable)
                                try {
                                    write(converted, converted.size)
                                } catch (error: Exception) {
                                    throw SinkError(error) // lỗi ghi (hết chỗ...) không phải lỗi giải mã chương
                                }
                            }
                        }
                        codec.releaseOutputBuffer(out, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                    }
                    else -> if (inputDone && ++idle > 500) throw Mp3Export.Refused("Chưa giải mã được ${file.name}") // 5 giây không ra gì: codec treo
                }
            }
        } catch (error: SinkError) {
            throw error.cause as Exception
        } catch (error: Mp3Export.Refused) {
            throw error
        } catch (error: Mp3Export.Stopped) {
            throw error
        } catch (error: Exception) {
            throw Mp3Export.Refused("Chưa giải mã được ${file.name}")
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { extractor.release() }
        }
    }

    /**
     * Bộ giải mã bài nhạc của [TrackPcmCache]: `file(track)` = file bài trong sách (null = không có), giải mã về tần số/kênh của chương,
     * ghi PCM 16-bit LE.
     */
    fun trackDecoder(file: (String) -> File?, stopped: () -> Boolean): TrackPcmCache.TrackDecoder =
        TrackPcmCache.TrackDecoder { track, rate, channels, out ->
            val source = file(track)?.takeIf { it.isFile } ?: throw Mp3Export.Refused("Thiếu bài nhạc $track")
            var bytes = ByteArray(0)
            decodeFile(source, rate, channels, stopped) { pcm, count ->
                if (bytes.size < 2 * count) bytes = ByteArray(2 * count)
                for (i in 0 until count) {
                    val v = pcm[i].toInt()
                    bytes[2 * i] = v.toByte()
                    bytes[2 * i + 1] = (v shr 8).toByte()
                }
                out.write(bytes, 0, 2 * count)
            }
        }

    /**
     * `music_export.mono_offset_db`: dB bù cho bản gộp một kênh `pcm` (đúng PCM sẽ trộn) của bài `source`, đo trên ĐOẠN PHÁT
     * [start, end) giây = độ to đoạn ấy phát hai loa - độ to cùng đoạn của bản gộp (dualmono), kẹp <= [Lufs.MONO_MAX_DB]. Bài một kênh
     * -> 0. Đo một lần mỗi đoạn, ghi `<tên>.mono.json` cạnh bài ({"spans": {"đầu-cuối": {offsetDb, stereoLufs, foldedLufs}}}, như máy
     * tính) rồi đọc lại; không đo được -> 0, không ghi.
     */
    fun foldOffset(stopped: () -> Boolean): MusicExport.FoldOffset = MusicExport.FoldOffset { source, pcm, rate, start, end ->
        val sidecar = File(source.parentFile, source.nameWithoutExtension + MONO_SIDECAR)
        val key = "$start-$end"
        val spans = runCatching { JSONObject(sidecar.readText()).getJSONObject("spans") }.getOrNull() ?: JSONObject()
        spans.optJSONObject(key)?.optDouble("offsetDb", Double.NaN)?.takeIf { !it.isNaN() }?.let { return@FoldOffset it }
        val sourceChannels = runCatching { layout(source).second }.getOrNull() ?: return@FoldOffset 0.0
        if (sourceChannels < 2) return@FoldOffset 0.0 // bài một kênh: trình phát cũng phát một kênh ra hai loa, không mất gì khi gộp
        val lo = start.toLong() * rate
        val hi = minOf(end.toLong() * rate, pcm.frames.toLong())
        val folded = Lufs(rate, 1, dualMono = true)
        val block = ShortArray(4096)
        var at = lo
        while (at < hi) {
            val n = minOf(block.size.toLong(), hi - at).toInt()
            for (i in 0 until n) block[i] = MusicRender.toInt16(pcm.sample((at + i).toInt(), 0))
            folded.feed(block, n)
            at += n
        }
        val stereo = Lufs(rate, 2)
        var frame = 0L
        try {
            decodeFile(source, rate, 2, stopped) { samples, count ->
                val a = (maxOf(lo, frame) - frame).toInt()
                val b = (minOf(end.toLong() * rate, frame + count / 2) - frame).toInt()
                if (a < b) stereo.feed(samples.copyOfRange(2 * a, 2 * b))
                frame += count / 2
            }
        } catch (error: Mp3Export.Stopped) {
            throw error
        } catch (error: Exception) {
            return@FoldOffset 0.0
        }
        val s = stereo.integrated() ?: return@FoldOffset 0.0
        val f = folded.integrated() ?: return@FoldOffset 0.0
        val offset = Lufs.monoOffsetDb(s, f)
        runCatching {
            spans.put(key, JSONObject().put("offsetDb", offset).put("stereoLufs", s).put("foldedLufs", f))
            val part = File(sidecar.path + ".part")
            part.writeText(JSONObject().put("spans", spans).toString())
            if (!(sidecar.delete() || !sidecar.exists()) || !part.renameTo(sidecar)) part.delete()
        }
        offset
    }

    private class SinkError(override val cause: Exception) : RuntimeException(cause)

    /**
     * Bộ mã hoá AAC-LC (64 kb/s mono, 96 kb/s stereo - số của máy tính): `write` nhận PCM 16-bit xen kẽ, mỗi khung AAC ra `unit(dữ liệu, cỡ)`
     * theo thứ tự (khối cấu hình không tính - nó nằm trong định dạng, `format` báo một lần trước khung đầu).
     */
    internal class AacEncoder(val rate: Int, val channels: Int, private val format: (MediaFormat) -> Unit,
                              private val unit: (ByteBuffer, MediaCodec.BufferInfo) -> Unit) :
        ListenExport.PcmOutput {
        private val encoder: MediaCodec
        private var ended = false
        private val info = MediaCodec.BufferInfo()

        /** Số khung PCM đã nhận. */
        override var frames = 0L
            private set

        init {
            val wanted = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, channels).apply {
                setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC)
                setInteger(MediaFormat.KEY_BIT_RATE, if (channels == 1) BITRATE_MONO else BITRATE_STEREO)
                setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 64 * 1024)
            }
            encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
            try {
                encoder.configure(wanted, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
                encoder.start()
            } catch (error: Exception) {
                runCatching { encoder.release() }
                throw error
            }
        }

        override fun write(pcm: ShortArray, count: Int) {
            var offset = 0
            while (offset < count) {
                val slot = encoder.dequeueInputBuffer(TIMEOUT_US)
                if (slot < 0) {
                    drain()
                    continue
                }
                val buffer = encoder.getInputBuffer(slot)!!
                buffer.clear()
                buffer.order(ByteOrder.LITTLE_ENDIAN)
                val take = minOf(count - offset, buffer.capacity() / 2 / channels * channels)
                buffer.asShortBuffer().put(pcm, offset, take)
                encoder.queueInputBuffer(slot, 0, take * 2, frames * 1_000_000L / rate, 0)
                frames += take / channels
                offset += take
                drain()
            }
        }

        /** Hết đầu vào: xả nốt các khung còn trong bộ mã hoá rồi giải phóng nó. */
        override fun finish() {
            var queued = false
            var waited = 0
            while (!queued) {
                val slot = encoder.dequeueInputBuffer(TIMEOUT_US)
                if (slot >= 0) {
                    encoder.queueInputBuffer(slot, 0, 0, frames * 1_000_000L / rate, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                    queued = true
                } else {
                    drain()
                    if (++waited > 500) throw Mp3Export.Refused("Bộ mã hoá AAC không nhận thêm dữ liệu")
                }
            }
            waited = 0
            while (!ended) {
                drain(TIMEOUT_US)
                if (++waited > 1000) throw Mp3Export.Refused("Bộ mã hoá AAC không kết thúc")
            }
            encoder.stop()
            encoder.release()
        }

        override fun abort() {
            runCatching { encoder.stop() }
            runCatching { encoder.release() }
        }

        private fun drain(wait: Long = 0) {
            while (true) {
                val out = encoder.dequeueOutputBuffer(info, wait)
                when {
                    out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> format(encoder.outputFormat)
                    out >= 0 -> {
                        val data = encoder.getOutputBuffer(out)!!
                        if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) info.size = 0 // cấu hình đã nằm trong định dạng
                        if (info.size > 0) {
                            data.position(info.offset).limit(info.offset + info.size)
                            unit(data, info)
                        }
                        encoder.releaseOutputBuffer(out, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) {
                            ended = true
                            return
                        }
                    }
                    else -> return
                }
            }
        }
    }

    /** Một track AAC trong file MP4 (MediaMuxer): khung thứ `index` ở mốc index * 1024 mẫu - các khung nối liền, không phụ thuộc mốc gốc. */
    internal class AacTrack(target: File, format: MediaFormat, private val rate: Int) {
        private val muxer = MediaMuxer(target.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
        private val track: Int
        private val info = MediaCodec.BufferInfo()

        init {
            try {
                track = muxer.addTrack(format)
                muxer.start()
            } catch (error: Exception) {
                runCatching { muxer.release() }
                throw error
            }
        }

        fun write(data: ByteBuffer, size: Int, index: Long) {
            info.set(data.position(), size, index * AacJoin.FRAME * 1_000_000L / rate, MediaCodec.BUFFER_FLAG_KEY_FRAME)
            write(data, info)
        }

        /** Khung với mốc / cờ có sẵn (của chính bộ mã hoá - [AacSink]). */
        fun write(data: ByteBuffer, info: MediaCodec.BufferInfo) = muxer.writeSampleData(track, data, info)

        fun finish() {
            muxer.stop()
            muxer.release()
        }

        fun abort() {
            runCatching { muxer.stop() }
            runCatching { muxer.release() }
        }
    }

    /** Bộ mã hoá AAC-LC ghi thẳng một file MP4 (`target`), mốc theo chính bộ mã hoá: M4B không kèm nhạc, bản tạm từng chương của "Xuất sách nói". */
    internal class AacSink(target: File, val rate: Int, val channels: Int) : ListenExport.PcmOutput {
        private var track: AacTrack? = null
        private val encoder = AacEncoder(rate, channels, { format -> track = AacTrack(target, format, rate) }) { data, info ->
            track!!.write(data, info)
        }

        override val frames: Long get() = encoder.frames

        override fun write(pcm: ShortArray, count: Int) = encoder.write(pcm, count)

        /** Hết đầu vào: xả nốt bộ mã hoá, đóng file. */
        override fun finish() {
            encoder.finish()
            val closing = track ?: throw Mp3Export.Refused("Không có âm thanh nào để ghi")
            track = null
            closing.finish()
        }

        override fun abort() {
            encoder.abort()
            track?.abort()
            track = null
        }
    }
}
