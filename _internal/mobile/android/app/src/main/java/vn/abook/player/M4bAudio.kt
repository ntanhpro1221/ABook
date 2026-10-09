package vn.abook.player

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMuxer
import java.io.File
import java.nio.ByteOrder
import kotlin.math.roundToLong

/**
 * Mã hoá âm thanh của "Xuất M4B" bằng chính bộ giải mã / mã hoá AAC của Android (MediaExtractor + MediaCodec + MediaMuxer): từng chương
 * giải mã ra PCM 16-bit, đổi về định dạng chung của cuốn (theo chương đầu: cùng tần số, 1 hay 2 kênh - như máy tính), rồi đổ liên tục
 * vào MỘT bộ mã hoá AAC-LC (64 kb/s mono, 96 kb/s stereo - số của máy tính). Đếm số khung PCM đã đổ vào nên mốc mỗi chương đúng tới từng mẫu.
 */
object M4bAudio : M4bExport.AudioEncoder {
    private const val TIMEOUT_US = 10_000L
    private const val BITRATE_MONO = 64_000
    private const val BITRATE_STEREO = 96_000

    /**
     * Độ trễ của bộ mã hoá AAC-LC phần mềm của Android (c2.android.aac.encoder, thư viện FDK): đo trên máy ảo - tiếng ra khỏi bộ giải mã
     * trễ đúng 2048 mẫu so với tiếng vào, như độ trễ chuẩn của AAC-LC (khung 1024 x 2).
     */
    override val delay = 2048

    override fun encode(plan: Mp3Export.Plan, target: File, stopped: () -> Boolean, progress: (Int, Int, Double) -> Unit): List<Mp4Finish.Mark> {
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

    private fun audioTrack(extractor: MediaExtractor): Int =
        (0 until extractor.trackCount).firstOrNull { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true } ?: -1

    /** (tần số, số kênh 1|2) của một file - như `_audio_layout` của máy tính. */
    private fun layout(file: File): Pair<Int, Int> {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(file.absolutePath)
            val index = audioTrack(extractor)
            if (index < 0) throw Mp3Export.Refused("Không đọc được âm thanh của ${file.name}")
            val format = extractor.getTrackFormat(index)
            return format.getInteger(MediaFormat.KEY_SAMPLE_RATE) to if (format.getInteger(MediaFormat.KEY_CHANNEL_COUNT) == 1) 1 else 2
        } catch (error: Mp3Export.Refused) {
            throw error
        } catch (error: Exception) {
            throw Mp3Export.Refused("Không đọc được âm thanh của ${file.name}")
        } finally {
            extractor.release()
        }
    }

    /** Giải mã một chương đổ vào `sink`; trả số khung PCM (theo tần số chung) đã đổ. `fraction(0..1)` theo vị trí đọc trong chương. */
    private fun decodeInto(chapter: Mp3Export.Chapter, sink: AacSink, stopped: () -> Boolean, fraction: (Double) -> Unit): Long {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(chapter.file.absolutePath)
            val index = audioTrack(extractor)
            if (index < 0) throw Mp3Export.Refused("Không đọc được âm thanh của ${chapter.file.name}")
            extractor.selectTrack(index)
            val format = extractor.getTrackFormat(index)
            val length = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION).toDouble() else 0.0
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME)!!)
            codec.configure(format, null, null, 0)
            codec.start()
            var channels = format.getInteger(MediaFormat.KEY_CHANNEL_COUNT)
            var converter = M4bExport.PcmConverter(format.getInteger(MediaFormat.KEY_SAMPLE_RATE), channels, sink.rate, sink.channels)
            var float = false
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var idle = 0
            val before = sink.frames
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
                        converter = M4bExport.PcmConverter(shown.getInteger(MediaFormat.KEY_SAMPLE_RATE), channels, sink.rate, sink.channels)
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
                                    sink.write(converted, converted.size)
                                } catch (error: Exception) {
                                    throw SinkError(error) // lỗi ghi (hết chỗ...) không phải lỗi giải mã chương
                                }
                            }
                        }
                        codec.releaseOutputBuffer(out, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0) break
                    }
                    else -> if (inputDone && ++idle > 500) throw Mp3Export.Refused("Không giải mã được ${chapter.file.name}") // 5 giây không ra gì: codec treo
                }
            }
            return sink.frames - before
        } catch (error: SinkError) {
            throw error.cause as Exception
        } catch (error: Mp3Export.Refused) {
            throw error
        } catch (error: Mp3Export.Stopped) {
            throw error
        } catch (error: Exception) {
            throw Mp3Export.Refused("Không giải mã được ${chapter.file.name}")
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { extractor.release() }
        }
    }

    private class SinkError(override val cause: Exception) : RuntimeException(cause)

    /** Bộ mã hoá AAC-LC + MediaMuxer vào file `target`. `write` nhận PCM 16-bit xen kẽ đã ở định dạng chung. */
    private class AacSink(target: File, val rate: Int, val channels: Int) {
        private val encoder: MediaCodec
        private var muxer: MediaMuxer? = null
        private var track = -1
        private var started = false
        private var ended = false
        private val info = MediaCodec.BufferInfo()

        /** Số khung PCM đã nhận. */
        var frames = 0L
            private set

        init {
            val format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_AAC, rate, channels).apply {
                setInteger(MediaFormat.KEY_AAC_PROFILE, MediaCodecInfo.CodecProfileLevel.AACObjectLC)
                setInteger(MediaFormat.KEY_BIT_RATE, if (channels == 1) BITRATE_MONO else BITRATE_STEREO)
                setInteger(MediaFormat.KEY_MAX_INPUT_SIZE, 64 * 1024)
            }
            encoder = MediaCodec.createEncoderByType(MediaFormat.MIMETYPE_AUDIO_AAC)
            try {
                encoder.configure(format, null, null, MediaCodec.CONFIGURE_FLAG_ENCODE)
                encoder.start()
                muxer = MediaMuxer(target.absolutePath, MediaMuxer.OutputFormat.MUXER_OUTPUT_MPEG_4)
            } catch (error: Exception) {
                runCatching { encoder.release() }
                throw error
            }
        }

        fun write(pcm: ShortArray, count: Int) {
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

        /** Hết đầu vào: xả nốt bộ mã hoá, đóng file. */
        fun finish() {
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
            if (!started) throw Mp3Export.Refused("Không có âm thanh nào để ghi")
            val closing = muxer!!
            muxer = null
            closing.stop()
            closing.release()
            encoder.stop()
            encoder.release()
        }

        fun abort() {
            runCatching { encoder.stop() }
            runCatching { encoder.release() }
            runCatching { if (started) muxer?.stop() }
            runCatching { muxer?.release() }
            muxer = null
        }

        private fun drain(wait: Long = 0) {
            val owner = muxer ?: return
            while (true) {
                val out = encoder.dequeueOutputBuffer(info, wait)
                when {
                    out == MediaCodec.INFO_OUTPUT_FORMAT_CHANGED -> {
                        track = owner.addTrack(encoder.outputFormat)
                        owner.start()
                        started = true
                    }
                    out >= 0 -> {
                        val data = encoder.getOutputBuffer(out)!!
                        if (info.flags and MediaCodec.BUFFER_FLAG_CODEC_CONFIG != 0) info.size = 0 // cấu hình đã nằm trong định dạng track
                        if (info.size > 0 && started) {
                            data.position(info.offset).limit(info.offset + info.size)
                            owner.writeSampleData(track, data, info)
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
}
