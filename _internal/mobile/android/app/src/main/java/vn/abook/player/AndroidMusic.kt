package vn.abook.player

import android.media.AudioFormat
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import java.io.File
import java.nio.ByteOrder

/**
 * Đọc thẻ + độ dài một bản nhạc bằng MediaMetadataRetriever của Android (máy tính dùng ffmpeg - music_local.read_tags): tên bài,
 * nghệ sĩ, album, thể loại. Thẻ có thể vắng; không có thẻ thì tên bài là tên file (MusicStore.info). File không đọc được như âm
 * thanh hay không biết độ dài -> [MusicStore.ImportError] với đúng lý do bên Python.
 */
object AndroidMusicTags : MusicStore.TagReader {
    override fun read(file: File): MusicStore.Tags {
        val retriever = MediaMetadataRetriever()
        try {
            retriever.setDataSource(file.absolutePath)
            val audio = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_HAS_AUDIO)
            if (audio != null && audio != "yes") throw MusicStore.ImportError("không đọc được như một bản nhạc")
            val millis = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()
            if (millis == null || millis <= 0) throw MusicStore.ImportError("không biết bài dài bao lâu")
            return MusicStore.Tags(
                millis / 1000.0,
                retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_TITLE)?.trim(),
                retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ARTIST)?.trim(),
                retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_ALBUM)?.trim(),
                retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_GENRE)?.trim(),
            )
        } catch (error: MusicStore.ImportError) {
            throw error
        } catch (error: RuntimeException) {
            throw MusicStore.ImportError("không đọc được như một bản nhạc")
        } finally {
            runCatching { retriever.release() }
        }
    }
}

/**
 * Độ to LUFS của một bản nhạc trên điện thoại: giải mã bằng MediaCodec rồi đo [Bs1770] (cùng phép đo với máy tính). Chỉ giải mã tối
 * đa [MAX_SECONDS] đầu bài - một bản mix dài cả giờ không bắt người dùng chờ, và độ to của vài phút đầu đã đại diện cho cả bài.
 * Không giải mã được hay quá ngắn -> null (bài dùng độ to trung vị của danh mục, `MusicGain.DEFAULT_TRACK_LUFS`).
 */
object AndroidLoudness : MusicStore.LoudnessMeter {
    const val MAX_SECONDS = 480.0

    override fun measure(file: File): Double? {
        val extractor = MediaExtractor()
        var codec: MediaCodec? = null
        try {
            extractor.setDataSource(file.absolutePath)
            val index = (0 until extractor.trackCount).firstOrNull { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
                ?: return null
            extractor.selectTrack(index)
            val format = extractor.getTrackFormat(index)
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME) ?: return null)
            codec.configure(format, null, null, 0)
            codec.start()
            var meter: Bs1770? = null
            var channels = 2
            var rate = 0
            var float = false
            var frames = 0L
            val info = MediaCodec.BufferInfo()
            var inputDone = false
            var outputDone = false
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
                        float = shown.containsKey(MediaFormat.KEY_PCM_ENCODING) &&
                            shown.getInteger(MediaFormat.KEY_PCM_ENCODING) == AudioFormat.ENCODING_PCM_FLOAT
                        meter = Bs1770(rate)
                    }
                    out >= 0 -> {
                        val buffer = codec.getOutputBuffer(out)!!
                        val active = meter
                        if (info.size > 0 && active != null) {
                            buffer.position(info.offset).limit(info.offset + info.size)
                            buffer.order(ByteOrder.LITTLE_ENDIAN)
                            if (float) {
                                val samples = buffer.asFloatBuffer()
                                while (samples.remaining() >= channels) {
                                    val first = samples.get().toDouble()
                                    val second = if (channels > 1) samples.get().toDouble() else first
                                    repeat(channels - 2) { samples.get() }
                                    active.push(first, second)
                                    frames++
                                }
                            } else {
                                val samples = buffer.asShortBuffer()
                                while (samples.remaining() >= channels) {
                                    val first = samples.get() / 32768.0
                                    val second = if (channels > 1) samples.get() / 32768.0 else first
                                    repeat(channels - 2) { samples.get() }
                                    active.push(first, second)
                                    frames++
                                }
                            }
                        }
                        codec.releaseOutputBuffer(out, false)
                        if (info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0 || (rate > 0 && frames >= MAX_SECONDS * rate)) outputDone = true
                    }
                }
            }
            return meter?.integrated()?.let { Math.round(it * 100) / 100.0 }
        } catch (error: Exception) {
            return null
        } finally {
            runCatching { codec?.stop() }
            runCatching { codec?.release() }
            runCatching { extractor.release() }
        }
    }
}
