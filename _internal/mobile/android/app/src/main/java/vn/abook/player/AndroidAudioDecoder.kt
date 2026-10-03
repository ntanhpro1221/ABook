package vn.abook.player

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import java.io.File
import java.nio.ByteOrder
import kotlin.math.sqrt

/**
 * Giải mã một bản nhạc cho bộ phân tích: MediaExtractor + MediaCodec -> PCM -> mono float ở tần số gốc, ghi vào file tạm
 * ([PcmSpool], trong `cacheDir`); việc đổi sang 48 kHz làm sau, chỉ cho ba cửa sổ ([Resampler]). Xin codec trả float (API 24+); codec
 * chỉ trả 16-bit thì chia 32768. Tối đa [MAX_SECONDS] đầu bài (như `music_mel.MAX_SECONDS`). Nhiều kênh -> mono như ffmpeg `-ac 1`:
 * stereo cộng L+R rồi nhân căn(1/2) (KHÔNG lấy trung bình: ffmpeg không chuẩn hoá và độ to tuyệt đối đổi dB của log-mel); nhiều
 * hơn hai kênh thì chỉ dùng L và R.
 */
class AndroidAudioDecoder(private val cacheDir: File) : AudioDecoder {
    override fun decode(file: File): PcmSource? {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        var spool: PcmSpool? = null
        try {
            extractor.setDataSource(file.absolutePath)
            val index = (0 until extractor.trackCount).firstOrNull { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
                ?: return null
            extractor.selectTrack(index)
            val format = extractor.getTrackFormat(index)
            format.setInteger(MediaFormat.KEY_PCM_ENCODING, AudioFormat.ENCODING_PCM_FLOAT)
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME) ?: return null)
            codec.configure(format, null, null, 0)
            codec.start()
            var rate = format.getIntegerOrNull(MediaFormat.KEY_SAMPLE_RATE) ?: 0
            var channels = format.getIntegerOrNull(MediaFormat.KEY_CHANNEL_COUNT) ?: 0
            var float = false
            var limit = 0L
            cacheDir.mkdirs()
            val chunk = FloatArray(1 shl 14)
            var filled = 0
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
            var idle = 0
            fun flush() {
                if (filled > 0) spool?.append(chunk, filled)
                filled = 0
            }
            while (!outputDone) {
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
                        val encoding = shown.getIntegerOrNull(MediaFormat.KEY_PCM_ENCODING) ?: AudioFormat.ENCODING_PCM_16BIT
                        if (encoding != AudioFormat.ENCODING_PCM_16BIT && encoding != AudioFormat.ENCODING_PCM_FLOAT) return null
                        float = encoding == AudioFormat.ENCODING_PCM_FLOAT
                        if (spool == null) {
                            spool = PcmSpool(File.createTempFile("pcm-", ".f32", cacheDir), rate)
                            limit = (MAX_SECONDS * rate).toLong()
                        }
                    }
                    out >= 0 -> {
                        idle = 0
                        val active = spool
                        if (info.size > 0 && active != null && channels > 0) {
                            val buffer = codec.getOutputBuffer(out)!!
                            buffer.position(info.offset).limit(info.offset + info.size)
                            buffer.order(ByteOrder.LITTLE_ENDIAN)
                            val floats = if (float) buffer.asFloatBuffer() else null
                            val shorts = if (float) null else buffer.asShortBuffer()
                            fun next(): Float = if (floats != null) floats.get() else shorts!!.get() / 32768f
                            val remaining = { if (floats != null) floats.remaining() else shorts!!.remaining() }
                            while (remaining() >= channels && active.frames + filled < limit) {
                                val left = next()
                                val mono = if (channels > 1) (left + next()) * HALF_ROOT else left
                                repeat(channels - 2) { next() }
                                chunk[filled++] = mono
                                if (filled == chunk.size) flush()
                            }
                        }
                        codec.releaseOutputBuffer(out, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0 || (active != null && active.frames + filled >= limit)) outputDone = true
                    }
                    else -> if (inputDone && ++idle > 500) return null // 5 giây không ra gì sau khi đã hết đầu vào: codec treo
                }
            }
            flush()
            val done = spool ?: return null
            if (done.frames <= 0) return null
            spool = null
            return done
        } catch (error: Exception) {
            return null
        } finally {
            spool?.close() // chỉ còn khi lỗi giữa chừng: bản trả về cho người gọi thì người gọi đóng
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { extractor.release() }
        }
    }

    private fun MediaFormat.getIntegerOrNull(key: String): Int? = if (containsKey(key)) getInteger(key) else null

    companion object {
        const val MAX_SECONDS = 1800
        private val HALF_ROOT = sqrt(0.5).toFloat()
    }
}
