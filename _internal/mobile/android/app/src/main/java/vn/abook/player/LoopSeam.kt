package vn.abook.player

import android.content.Context
import android.media.MediaCodec
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.SystemClock
import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.Format
import androidx.media3.common.MediaItem
import androidx.media3.common.StreamKey
import androidx.media3.common.Player
import androidx.media3.common.util.UnstableApi
import androidx.media3.common.util.Util
import androidx.media3.decoder.DecoderInputBuffer
import androidx.media3.exoplayer.FormatHolder
import androidx.media3.exoplayer.LoadingInfo
import androidx.media3.exoplayer.SeekParameters
import androidx.media3.exoplayer.audio.AudioSink
import androidx.media3.exoplayer.audio.ForwardingAudioSink
import androidx.media3.exoplayer.drm.DrmSessionManagerProvider
import androidx.media3.exoplayer.source.MediaPeriod
import androidx.media3.exoplayer.source.MediaSource
import androidx.media3.exoplayer.source.SampleStream
import androidx.media3.exoplayer.source.TrackGroupArray
import androidx.media3.exoplayer.source.WrappingMediaSource
import androidx.media3.exoplayer.trackselection.ExoTrackSelection
import androidx.media3.exoplayer.upstream.Allocator
import androidx.media3.exoplayer.upstream.LoadErrorHandlingPolicy
import androidx.media3.extractor.MpegAudioUtil
import java.io.File
import java.io.FileOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.atomic.AtomicReference
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
 * [LoopSink] cắt đúng ngần ấy mẫu ở đầu (TrimmingAudioProcessor cắt padding ở cuối). Trục đầu ra của codec đã bỏ 529 nên số cắt là bội đúng của khung, không có 529.
 *
 * Vòng 2 (PLAN_loop §42): TUA phải chính xác từng mẫu tại mốc tuỳ ý. Ba nguyên nhân đo được khiến tua lệch, [seekToSample] xử lý cả ba:
 * (1) Clip mp3: ExoPlayer bỏ nguyên khung có nhãn trước vị trí tua nên tiếng vào ở khung đầu tiên >= mốc, trễ 0-1 khung (tới 26 ms);
 * (2) tua sang MỤC khác thì encoderDelay (preroll) của Clip lặp bị cắt luôn: trễ thêm 78 ms ở 44,1 kHz;
 * (3) Nối WAV đã được đọc trước: ExoPlayer tua trong bộ đệm, khối WAV 100 ms chứa mốc bị bỏ cả khối, tiếng vào ở khối sau (+95 ms; lúc có lúc không: đây là lỗi R4 của §41).
 * Cách chữa: đáp ở ranh khung / khối dưới mốc rồi [LoopSink] cắt phần dư theo số mẫu báo trước. Nối dựng bằng giải mã riêng từng vùng ([decodeRegion]) và đệm theo khoá file + mốc.
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
        /** Nối lấy từ bộ nhớ đệm (không giải mã lại). */
        val cached: Boolean = false,
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

    /** Nguồn khung nén cho [pump]: MediaExtractor (giải mã liền từ đầu file) hoặc danh sách khung tự quét ([decodeRegion]). */
    private interface FrameSource {
        /** Chép khung kế vào `into` (từ vị trí 0), trả cỡ; -1 = hết. */
        fun read(into: ByteBuffer): Int
        fun timeUs(): Long
        fun advance()
    }

    /**
     * Bơm khung nén vào MỘT MediaCodec mới (khởi động nguội) và gom PCM16 LE; `onPcm(mẫu đầu, bộ đệm)` mỗi khối ra (bộ đệm chỉ hợp lệ trong lệnh gọi).
     * Dừng khi đã đủ `stopAt` mẫu. `maxSkewSamples` = độ lệch lớn nhất giữa nhãn thời gian của codec và số mẫu đã đếm (0 khi trục khớp).
     */
    private fun pump(format: MediaFormat, source: FrameSource, stopAt: Long, onPcm: (Long, ByteBuffer) -> Unit): Decoded {
        var codec: MediaCodec? = null
        try {
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
                        val size = source.read(codec.getInputBuffer(slot)!!)
                        if (size < 0) {
                            codec.queueInputBuffer(slot, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM)
                            inputDone = true
                        } else {
                            codec.queueInputBuffer(slot, 0, size, source.timeUs(), 0)
                            source.advance()
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
        }
    }

    /**
     * Giải mã LIỀN MỘT MẠCH từ đầu file (không tua, không cắt encoderDelay / encoderPadding) ra PCM16 LE; `onPcm(mẫu đầu, bộ đệm)` mỗi khối ra (bộ đệm chỉ hợp lệ trong lệnh gọi).
     * Dừng khi đã đủ `stopAt` mẫu. Đây là trục tham chiếu "R" của bộ đo; [build] không dùng nó nữa (xem [decodeRegion]) trừ khi quét khung hỏng.
     */
    fun decode(file: File, stopAt: Long = Long.MAX_VALUE, onPcm: (Long, ByteBuffer) -> Unit): Decoded {
        val extractor = MediaExtractor()
        try {
            extractor.setDataSource(file.absolutePath)
            val index = (0 until extractor.trackCount).first { extractor.getTrackFormat(it).getString(MediaFormat.KEY_MIME)?.startsWith("audio/") == true }
            extractor.selectTrack(index)
            val format = extractor.getTrackFormat(index)
            // ExoPlayer không cắt gì ở Clip có mốc đầu/cuối (xem đầu lớp); codec nhận hai khoá này thì tự cắt (SkipCutBuffer) -> đặt 0.
            format.setInteger("encoder-delay", 0)
            format.setInteger("encoder-padding", 0)
            return pump(format, object : FrameSource {
                override fun read(into: ByteBuffer) = extractor.readSampleData(into, 0)
                override fun timeUs() = extractor.sampleTime
                override fun advance() {
                    extractor.advance()
                }
            }, stopAt, onPcm)
        } finally {
            extractor.release()
        }
    }

    /** Các khung mp3 của một file đã đọc hết vào bộ nhớ: vị trí byte + cỡ từng khung ÂM THANH (khung Xing / Info / VBRI không tính), cùng trục khung với Mp3Extractor và MediaExtractor. */
    internal class Mp3Frames(val data: ByteArray, val offsets: IntArray, val sizes: IntArray, val count: Int, val samplesPerFrame: Int, val sampleRate: Int, val channels: Int)

    private fun word(d: ByteArray, p: Int): Int =
        ((d[p].toInt() and 0xff) shl 24) or ((d[p + 1].toInt() and 0xff) shl 16) or ((d[p + 2].toInt() and 0xff) shl 8) or (d[p + 3].toInt() and 0xff)

    /** Quét tiêu đề khung từ đầu tới tối đa `maxFrames` khung; null nếu file không đều (mất đồng bộ, đổi tần số) để người gọi lùi về giải mã liền. Chỉ đọc tiêu đề: vài ms cho cả bài. */
    internal fun scanMp3(data: ByteArray, maxFrames: Int): Mp3Frames? {
        var pos = 0
        while (pos + 10 <= data.size && data[pos] == 'I'.code.toByte() && data[pos + 1] == 'D'.code.toByte() && data[pos + 2] == '3'.code.toByte()) {
            val size = ((data[pos + 6].toInt() and 0x7f) shl 21) or ((data[pos + 7].toInt() and 0x7f) shl 14) or ((data[pos + 8].toInt() and 0x7f) shl 7) or (data[pos + 9].toInt() and 0x7f)
            pos += 10 + size + if (data[pos + 5].toInt() and 0x10 != 0) 10 else 0
        }
        val h = MpegAudioUtil.Header()
        val next = MpegAudioUtil.Header()
        fun valid(p: Int, into: MpegAudioUtil.Header) = p >= 0 && p + 4 <= data.size && (word(data, p) and 0xFFE00000.toInt()) == 0xFFE00000.toInt() && into.setForHeaderData(word(data, p))
        var first = -1
        var p = pos
        while (p + 4 <= data.size && p < pos + 65536) {
            // khung thật khi khung kế nối ngay sau và cùng phiên bản / tầng / tần số (như ExactSeekMp3Extractor)
            if (valid(p, h) && valid(p + h.frameSize, next) && (word(data, p) and 0xFFFE0C00.toInt()) == (word(data, p + h.frameSize) and 0xFFFE0C00.toInt())) {
                first = p
                break
            }
            p++
        }
        if (first < 0) return null
        valid(first, h)
        val rate = h.sampleRate
        val channels = h.channels
        val spf = h.samplesPerFrame
        val side = if (h.version == 3) (if (channels == 1) 17 else 32) else (if (channels == 1) 9 else 17)
        val tag = word(data, first + 4 + side)
        val vbri = first + 36 + 4 <= data.size && word(data, first + 36) == 0x56425249
        p = if (tag == 0x58696e67 || tag == 0x496e666f || vbri) first + h.frameSize else first
        val offsets = IntArray(maxFrames)
        val sizes = IntArray(maxFrames)
        var count = 0
        while (count < maxFrames && p + 4 <= data.size) {
            if (!valid(p, h) || h.sampleRate != rate || h.channels != channels || h.samplesPerFrame != spf) return null
            if (p + h.frameSize > data.size) break // khung cuối cụt
            offsets[count] = p
            sizes[count] = h.frameSize
            count++
            p += h.frameSize
        }
        return Mp3Frames(data, offsets, sizes, count, spf, rate, channels)
    }

    /** Số khung đọc trước mỗi vùng Nối: bộ giải mã chạy nguội sai tối đa 2107 mẫu (1,83 khung, Music đo) rồi chính xác từng mẫu, 3 khung là dư. */
    const val SEAM_PREREAD_FRAMES = 3

    /**
     * PCM16 xen kênh của `count` khung bắt đầu ở khung `first` trên trục giải mã liền (R), chỉ giải mã đoạn quanh vùng: bơm `pre` khung đọc trước (bỏ đầu ra), vùng, rồi MỘT khung
     * thừa phía sau (bộ giải mã chậm 529 mẫu so với đầu vào). Mẫu k của đầu ra codec ứng với mẫu f0*spf + k của R: codec bỏ 529 mẫu đầu ở MỖI lần khởi động (cả bài liền lẫn đoạn này),
     * nên hai trục lệch nhau đúng cùng một lượng - kiểm bằng so byte với bản giải mã liền (SEAMCHK trong bài thử).
     */
    internal fun decodeRegion(frames: Mp3Frames, first: Int, count: Int, pre: Int): ShortArray {
        val f0 = first - pre
        val last = first + count // khung thừa
        require(f0 >= 0 && last < frames.count) { "vùng ngoài file: khung $f0..$last / ${frames.count}" }
        val spf = frames.samplesPerFrame
        val channels = frames.channels
        val format = MediaFormat.createAudioFormat(MediaFormat.MIMETYPE_AUDIO_MPEG, frames.sampleRate, channels)
        var at = f0
        val source = object : FrameSource {
            override fun read(into: ByteBuffer): Int {
                if (at > last) return -1
                into.clear()
                into.put(frames.data, frames.offsets[at], frames.sizes[at])
                return frames.sizes[at]
            }

            override fun timeUs() = (at - f0).toLong() * spf * 1_000_000L / frames.sampleRate
            override fun advance() {
                at++
            }
        }
        val out = ShortArray(count * spf * channels)
        val start = pre.toLong() * spf
        var filled = 0L
        val decoded = pump(format, source, (pre + count).toLong() * spf) { firstSample, pcm -> filled += copyInto(firstSample, pcm, channels, start, out) }
        check(decoded.sampleRate == frames.sampleRate && decoded.channels == channels) { "đầu ra bộ giải mã ${decoded.sampleRate}/${decoded.channels} khác định dạng đầu vào ${frames.sampleRate}/$channels" }
        check(filled == count.toLong() * spf) { "giải mã vùng thiếu: được $filled / ${count.toLong() * spf} mẫu" }
        return out
    }

    /** Khoá bộ nhớ đệm của Nối: file (đường dẫn, cỡ, ngày sửa) + mốc khung + phiên bản thuật toán (đổi cách dựng thì tăng). */
    private fun cacheKey(file: File, ka: Long, ks: Long, ke: Long, kx: Long, rate: Int, channels: Int): String {
        val text = "v3|${file.absolutePath}|${file.length()}|${file.lastModified()}|$ka|$ks|$ke|$kx|$rate|$channels"
        return java.security.MessageDigest.getInstance("SHA-1").digest(text.toByteArray()).joinToString("") { "%02x".format(it) }.take(16)
    }

    /**
     * Dựng Nối của `file`: biên căn khung mp3 ([ExactSeekMp3Extractor.frameBoundarySeconds]), X' = X làm tròn về bội số khung gần nhất, hai vùng
     * [loopEnd' - X', loopEnd'] và [loopStart', loopStart' + X'] giải mã RIÊNG từng vùng với [SEAM_PREREAD_FRAMES] khung đọc trước ([decodeRegion]), trộn tuyến tính theo mẫu ([mix]), ghi WAV PCM16
     * cùng tần số / kênh vào `cacheDir/loopseam/<khoá>.wav` (khoá theo file + mốc; có sẵn thì dùng lại, không giải mã). File mp3 không quét đều được thì lùi về giải mã liền từ đầu ([decode]).
     */
    fun build(context: Context, file: File, bounds: Bounds, xSeconds: Double, prerollFrames: Int = PREROLL_FRAMES): Seam {
        val planned = plan(context, file, bounds, xSeconds, prerollFrames)
        return if (planned.cached) planned else render(planned)
    }

    /**
     * Phần HÌNH HỌC của [build] (không giải mã, cỡ mili giây: chỉ đọc định dạng file): biên khung, X', đường dẫn WAV trong bộ nhớ đệm, `cached` = WAV đã có đủ. Đủ để phát Clip đầu
     * ([mediaItems] mục 0) ngay; Nối thì [render] dựng sau, ở luồng nền ([MusicBed] bật `musicSeamP3`).
     */
    fun plan(context: Context, file: File, bounds: Bounds, xSeconds: Double, prerollFrames: Int = PREROLL_FRAMES): Seam {
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
        val dir = File(context.cacheDir, "loopseam").apply { mkdirs() }
        val wav = File(dir, cacheKey(file, ka, ks, ke, kx, rate, channels) + ".wav")
        fun seam(cached: Boolean) = Seam(file, wav, ka * spf, ks * spf, ke * spf, n, rate, channels, spf, SystemClock.elapsedRealtime() - began, prerollFrames, cached)
        return seam(wav.length() == 44L + n.toLong() * channels * 2)
    }

    /** Phần GIẢI MÃ của [build]: dựng WAV của Nối theo hình học của `seam` ([plan]); có sẵn đủ thì không làm gì. Chạy ở luồng nền (vài trăm ms tới vài giây). */
    fun render(seam: Seam): Seam {
        val began = SystemClock.elapsedRealtime()
        val file = seam.file
        val wav = seam.wav
        val rate = seam.sampleRate
        val channels = seam.channels
        val spf = seam.frameSamples
        val n = seam.xFrames
        val ks = seam.loopStartSamples / spf
        val ke = seam.loopEndSamples / spf
        val kx = (n / spf).toLong()
        if (wav.length() == 44L + n.toLong() * channels * 2) return seam
        val dir = wav.parentFile!!
        val scanned = scanMp3(file.readBytes(), (ke + 2).toInt())?.takeIf { it.sampleRate == rate && it.channels == channels && it.samplesPerFrame == spf && it.count > ke }
        val old: ShortArray
        val new: ShortArray
        if (scanned != null) {
            old = decodeRegion(scanned, (ke - kx).toInt(), kx.toInt(), SEAM_PREREAD_FRAMES.coerceAtMost((ke - kx).toInt()))
            new = decodeRegion(scanned, ks.toInt(), kx.toInt(), SEAM_PREREAD_FRAMES.coerceAtMost(ks.toInt()))
        } else {
            old = ShortArray(n * channels)
            new = ShortArray(n * channels)
            var filled = 0L
            val decoded = decode(file, stopAt = ke * spf) { first, pcm ->
                filled += copyInto(first, pcm, channels, (ke - kx) * spf, old) + copyInto(first, pcm, channels, ks * spf, new)
            }
            check(decoded.sampleRate == rate && decoded.channels == channels) { "đầu ra bộ giải mã ${decoded.sampleRate}/${decoded.channels} khác định dạng đầu vào $rate/$channels" }
            check(filled == 2L * n) { "giải mã thiếu: được $filled / ${2L * n} mẫu (file ngắn hơn loopEnd'?)" }
        }
        val tmp = File(dir, wav.name + ".tmp")
        writeWav(tmp, mix(old, new, channels), rate, channels)
        check(tmp.renameTo(wav) || wav.length() == tmp.length()) { "không đổi tên được ${tmp.name}" }
        return Seam(file, wav, seam.audibleStartSamples, seam.loopStartSamples, seam.loopEndSamples, n, rate, channels, spf, seam.buildMs + SystemClock.elapsedRealtime() - began, seam.prerollFrames, false)
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

    /**
     * Sink bọc (đặt quanh DefaultAudioSink) lo MỌI việc cắt mẫu đầu mục - thay TrimmingAudioProcessor, thứ chỉ cắt khi có "cấu hình mới" nên gặp lúc tua thì cắt nhầm
     * (mục Clip lặp có encoderDelay = preroll bị cắt cả khi tua thẳng vào, tiếng đi trước ~78 ms; còn đọc trước mục kế làm TrimmingAudioProcessor mang số cắt của mục KHÁC).
     * Format chuyển xuống sink trong có `encoderDelay` = 0 (encoderPadding giữ cho TrimmingAudioProcessor cắt cuối mục). Số cắt đầu:
     * - chuyển mục liền / mở mục: `encoderDelay` do [mediaSourceFactory] ghi (preroll của Clip lặp), áp ở lần `configure` kế;
     * - tua: [seekToSample] gọi [armSeek]; MỖI lần `flush` khi còn lệnh đặt lại số cắt = số mẫu từ khung đáp tới mốc tua, và lần `configure` theo sau (nếu mục đổi) KHÔNG ghi đè nó.
     *   Số lần xả của sink KHÔNG ứng 1-1 với số lệnh `seekTo` (máy thật OPPO, PLAN_loop §46.3 / §47.1: buffer của lệnh tua trước tới sau lần xả của lệnh tua sau). Hai đường:
     *   (a) lệnh CÓ vị trí đích và đã biết offset dòng ra ([setOutputStreamOffsetUs]; Nối WAV): lệnh gắn với NHÃN THỜI GIAN của buffer đích: chỉ buffer ĐẦU TIÊN sau một lần xả, có nhãn
     *   đúng vị trí đích, mới tiêu lệnh (cắt + chụp); buffer đầu có nhãn khác là của dòng CŨ, đi qua nguyên vẹn, lệnh chờ lần xả kế;
     *   (b) lệnh KHÔNG kiểm được nhãn (Clip mp3: lần tua đệm chỉ lệch 1 ms và chưa có số máy về offset; hay chưa biết offset): đếm lần xả (`flushes`: 2 khi có lệnh tua đệm), mỗi lần xả
     *   đặt lại số cắt, chỉ lần xả CUỐI bắt đầu chụp và bỏ lệnh;
     * mẫu bị cắt khỏi các buffer đầu dòng ngay trước khi đưa xuống sink trong, nên không phụ thuộc trạng thái nào của media3 ngoài thứ tự gọi flush -> configure -> handleBuffer.
     * Lần tua vào Nối có lưới an toàn ([Capture]) thì sau khi cắt còn chép K khung đầu ra mảng riêng cho [seekToSample]; không có thì không chép gì.
     * Dịch pha TRONG DÒNG ([shift], không tua, không AudioTrack mới): chèn khung lặng / bỏ khung nội dung ngay trước buffer kế; vị trí báo lên ExoPlayer được bù ([getCurrentPositionUs]).
     * Phải đặt vào ExoPlayer qua `DefaultRenderersFactory.buildAudioSink`; app thật bọc sink MusicBed bằng cái này.
     */
    class LoopSink(inner: AudioSink) : ForwardingAudioSink(inner) {
        /**
         * Lệnh tua đang chờ: số cắt, lúc nạp, lệnh chép (lưới an toàn), vị trí đích trên trục dòng ra (µs, chưa cộng offset; [C.TIME_UNSET] = không kiểm nhãn) và độ lệch nhãn cho phép.
         * Giữ vị trí chứ không giữ nhãn đã cộng offset vì offset có thể đổi giữa lúc nạp và lúc buffer tới (tua sang mục khác đặt offset mới).
         */
        private class Arm(val frames: Long, val ns: Long, val capture: Capture?, val positionUs: Long, val toleranceUs: Long, var flushesLeft: Int)

        /** Lệnh [shift] chờ áp; `onApplied` gọi ở luồng phát khi đã chèn / bỏ xong. */
        private class ShiftOrder(val frames: Long, val onApplied: ((Shift) -> Unit)?)

        /**
         * Lưới an toàn của một lần tua vào Nối WAV ([seekToSample] với `onLand`): sau khi cắt, chép `frames` khung PCM16 ĐẦU TIÊN đưa xuống sink trong vào một mảng riêng (không giữ buffer)
         * rồi gọi `onCaptured` MỘT lần, ở luồng phát (người nhận tự đẩy việc nặng sang luồng khác). Sink không ở PCM16 thì bỏ, không gọi.
         */
        internal class Capture(val frames: Int, val onCaptured: (ShortArray) -> Unit)

        /** MÓC ĐO chỉ cho bài thử (MusicLoopSeamTest, ca RS): chỉ đọc trạng thái, không đổi gì. Gọi ở luồng phát. */
        internal interface Probe {
            /** Sau quyết định số cắt của mỗi lần flush: có số cắt của lệnh tua nạp không (`armed`), số cắt đầu dòng, cờ seekPending, nhãn thời gian lệnh tua ấy mong đợi (µs, -1 khi không có lệnh / không kiểm nhãn / chưa biết offset). */
            fun onFlush(armed: Boolean, toDrop: Long, seekPending: Boolean, expectedUs: Long)

            /**
             * Buffer ĐẦU TIÊN sau flush, TRƯỚC khi cắt: nhãn thời gian (µs), số khung (-1 khi chưa biết cỡ khung), số cắt còn lại, cờ seekPending,
             * khớp: 1 = nhãn khớp lệnh tua nên lệnh bị tiêu, 0 = nhãn khác (buffer dòng cũ, lệnh chờ tiếp), -1 = không có lệnh hay lệnh không kiểm nhãn (đường đếm lần xả, đã xử lý ở [flush]).
             */
            fun onFirstBuffer(presentationTimeUs: Long, frames: Long, toDrop: Long, seekPending: Boolean, match: Int)

            /** Buffer đầu sau flush bị bỏ qua lệnh vì nhãn khác lệnh có kiểm nhãn mong đợi (nhãn, nhãn mong đợi µs): buffer của dòng cũ. */
            fun onSkip(presentationTimeUs: Long, expectedUs: Long)
        }

        /** null (mặc định, app thật) = không gọi gì: đường cắt mẫu y nguyên. */
        @Volatile internal var probe: Probe? = null

        private val armed = AtomicReference<Arm?>(null)
        private var toDrop = 0L
        private var seekPending = false
        private var streamOffsetUs = 0L
        private var offsetKnown = false
        /** Buffer đầu sau lần xả gần nhất là của dòng cũ (nhãn không khớp lệnh tua): chưa bắt đầu dịch pha ([shift]) cho tới lần xả kế. */
        private var staleLine = false
        private var frameBytes = 0
        private var pcm16 = false
        /** PCM tuyến tính có dấu (mọi PCM trừ 8 bit không dấu): buffer số 0 là lặng, [shift] chèn được. */
        private var zeroIsSilence = false
        private var rate = 0
        /** Chưa có buffer nào từ lần flush gần nhất (chỉ [probe] đọc). */
        private var freshAfterFlush = false
        // Lưới an toàn ([Capture]) của lần tua đang chờ: mảng đang chép + số khung đã có. Buffer sink trong chưa nhận hết (handleBuffer trả false) được gọi lại nguyên con:
        // `retryBuffer` / `retryEnd` nhớ đã chép tới byte nào của nó để không chép hai lần.
        private var capture: Capture? = null
        private var captured: ShortArray? = null
        private var capturedFrames = 0
        private var retryBuffer: ByteBuffer? = null
        private var retryEnd = 0
        // Dịch pha ([shift]), mọi thứ tính từ lần xả gần nhất: byte sink trong đã NHẬN (chỉ số khung trong AudioTrack mới), sink trong còn giữ dở một buffer (trả false: lần sau phải đưa lại
        // đúng buffer ấy nên chưa được chèn / bỏ gì), pts của buffer đầu đưa xuống, số khung lệch giữa trục đã ghi và trục nội dung (+chèn -bỏ), lần chèn / bỏ đang dở, các dịch đã bắt đầu.
        private val shiftOrder = AtomicReference<ShiftOrder?>(null)
        private var writtenBytes = 0L
        private var innerBusy = false
        private var firstPtsUs = C.TIME_UNSET
        private var offsetFrames = 0L
        private var silence: ByteBuffer? = null
        private var dropLeft = 0L
        private var shifting: ShiftOrder? = null
        private var shifts: ArrayList<Shift>? = null

        /**
         * Gọi trước `player.seekTo` (trong 2 s). CÓ kiểm nhãn (`positionUs` != [C.TIME_UNSET] và đã biết offset): lần flush kế đặt số cắt `frames` khung đầu dòng, và buffer ĐẦU TIÊN sau
         * một lần xả có nhãn đúng `positionUs` (vị trí đích trên trục dòng ra, tức `plan.positionMs * 1000`; sink cộng offset dòng ra lúc buffer tới, xem [setOutputStreamOffsetUs]) tiêu
         * lệnh: cắt `frames`, bắt đầu chép [Capture]. Buffer đầu sau xả có nhãn khác (lệnh tua trước / lệnh tua đệm còn trong ống: máy thật §46.3, §47.1) đi qua nguyên vẹn và lệnh chờ lần xả
         * sau; buffer không phải đầu tiên sau xả không bao giờ tiêu lệnh; `flushes` bị bỏ qua. `toleranceUs` là độ lệch nhãn chấp nhận.
         * KHÔNG kiểm nhãn (không có `positionUs`, hay chưa biết offset): `flushes` lần flush kế (= số lệnh `seekTo` sắp gọi: 2 khi có lệnh tua đệm) mỗi lần đặt lại số cắt; lệnh chép [Capture]
         * chỉ bắt đầu ở lần xả CUỐI, rồi lệnh bị bỏ (buffer của lệnh tua đệm tới giữa hai lần xả thì vẫn bị cắt, lần xả sau đặt lại hết). Lệnh cũ chưa dùng bị thay;
         * không có `capture` thì đường cắt mẫu không chép gì thêm.
         */
        internal fun armSeek(frames: Long, capture: Capture? = null, positionUs: Long = C.TIME_UNSET, toleranceUs: Long = PTS_TOLERANCE_US, flushes: Int = 1) =
            armed.set(Arm(frames, clock(), capture, positionUs, toleranceUs, maxOf(1, flushes)))

        /** Lệnh kiểm được nhãn buffer đích: có vị trí đích và đã biết offset dòng ra. */
        private fun checks(arm: Arm) = arm.positionUs != C.TIME_UNSET && offsetKnown

        /**
         * Offset dòng ra mới nhất mà renderer báo (nhãn buffer = vị trí trong dòng + offset; mục WAV Nối của MusicBed là 1e12 + vị trí, nhưng chuyển mục tự nhiên đổi nó). MediaCodecAudioRenderer
         * gọi hàm này (qua onOutputStreamOffsetUsChanged) mỗi khi dòng ra đổi, KHÔNG gọi lại khi tua trong mục đang phát; media3 1.11.1: MediaCodecRenderer.setOutputStreamInfo.
         */
        override fun setOutputStreamOffsetUs(outputStreamOffsetUs: Long) {
            streamOffsetUs = outputStreamOffsetUs
            offsetKnown = true
            super.setOutputStreamOffsetUs(outputStreamOffsetUs)
        }

        /** Đồng hồ của hạn 2 s của [armSeek] (test JVM thay). */
        internal var clock: () -> Long = System::nanoTime

        /**
         * Dịch pha TRONG DÒNG, áp một lần ở buffer kế (sau số cắt của lần tua nếu còn), không xả, không AudioTrack mới. Gọi từ luồng nào cũng được (như [armSeek]); lệnh cũ chưa áp bị thay,
         * [flush] bỏ lệnh chưa áp lẫn lần chèn / bỏ đang dở.
         * - `frames` < 0: BỎ |frames| khung đầu dòng (tiếng đi sau: đẩy tới), cắt như số cắt của lần tua, có thể qua nhiều buffer.
         * - `frames` > 0: CHÈN `frames` khung lặng (tiếng đi trước: lùi lại) - một buffer số 0 cùng định dạng PCM đưa xuống sink trong TRƯỚC buffer thật; sink trong chưa nhận hết thì
         *   trả false như hợp đồng `handleBuffer` (ExoPlayer gọi lại cùng buffer thật) và lần sau đưa tiếp phần lặng còn lại.
         * Nhãn thời gian: sink trong nhận pts LIÊN TỤC với số khung đã ghi (pts nội dung + [offsetFrames]: +chèn, -bỏ), nên DefaultAudioSink không thấy gián đoạn (nó chỉnh lại
         * startMediaTimeUs khi lệch > 200 ms) và vị trí nó tính (pts đầu sau lần xả + khung đã phát) đi theo trục ĐÃ GHI; [getCurrentPositionUs] đổi về trục nội dung.
         * `onApplied` (luồng phát) nhận [Shift] khi đã chèn / bỏ xong: writtenAt = số khung sink trong đã nhận kể từ lần xả tới chỗ dịch, frames = K đã áp. Sink không ở PCM tuyến tính
         * (chưa biết cỡ khung) thì lệnh nằm chờ, không áp. Không có lệnh thì đường cũ y nguyên: không cấp phát, pts không đổi.
         */
        internal fun shift(frames: Long, onApplied: ((Shift) -> Unit)? = null) = shiftOrder.set(ShiftOrder(frames, onApplied))

        /** Các dịch đã bắt đầu kể từ lần xả gần nhất, cũ trước (chỉ test JVM đọc). */
        internal val appliedShifts: List<Shift> get() = shifts.orEmpty()

        /** Đang chờ / đang chép cho một lệnh [Capture] (chỉ test JVM đọc). */
        internal val capturing: Boolean get() = capture != null

        override fun configure(config: AudioSink.AudioSinkConfig) {
            val f = config.format
            frameBytes = if (f.pcmEncoding != Format.NO_VALUE && f.channelCount > 0) Util.getPcmFrameSize(f.pcmEncoding, f.channelCount) else 0
            pcm16 = f.pcmEncoding == C.ENCODING_PCM_16BIT
            zeroIsSilence = frameBytes > 0 && f.pcmEncoding != C.ENCODING_PCM_8BIT
            rate = f.sampleRate
            if (!seekPending) toDrop = maxOf(0, f.encoderDelay).toLong()
            val stripped = AudioSink.AudioSinkConfig.Builder(f.buildUpon().setEncoderDelay(0).build())
                .setPreferredBufferSizeOverride(config.preferredBufferSizeOverride)
                .setOutputChannelMapping(config.outputChannelMapping)
                .setTimeline(config.timeline)
                .setMediaPeriodId(config.mediaPeriodId)
                .build()
            super.configure(stripped)
        }

        override fun flush() {
            val waiting = armed.get()
            val arm = waiting?.takeIf { clock() - it.ns < 2_000_000_000L }
            if (waiting != null && arm == null) armed.compareAndSet(waiting, null) // quá hạn: lệnh tua ấy không sinh đủ lần xả, đừng áp cho lần xả lạ
            if (arm != null) {
                // Còn lệnh tua: mỗi lần xả đặt lại số cắt (buffer giữa hai lần xả có thể đã tiêu nó), lượt chép của lần xả trước (dở hay xong) bị bỏ.
                toDrop = arm.frames
                seekPending = true
                if (checks(arm)) {
                    startCapture(null) // có kiểm nhãn: lệnh KHÔNG bị bỏ và chưa chụp, chỉ buffer đầu sau xả có nhãn đúng đích mới tiêu nó ([handleBuffer])
                } else {
                    // không kiểm nhãn: đếm lần xả, chỉ lần CUỐI bắt đầu chép và bỏ lệnh
                    arm.flushesLeft--
                    val last = arm.flushesLeft <= 0
                    if (last) armed.compareAndSet(arm, null)
                    startCapture(if (last) arm.capture else null)
                }
            } else if (!seekPending) {
                toDrop = 0
                startCapture(null) // lần xả không phải của lệnh tua đang chờ: bỏ lệnh chép dở
            }
            freshAfterFlush = true
            staleLine = false
            // Dịch pha nói về dòng của AudioTrack cũ: bỏ hết, kể cả lệnh chưa áp.
            shiftOrder.set(null)
            writtenBytes = 0
            innerBusy = false
            firstPtsUs = C.TIME_UNSET
            offsetFrames = 0
            silence = null
            dropLeft = 0
            shifting = null
            shifts = null
            probe?.onFlush(arm != null, toDrop, seekPending, if (arm != null && checks(arm)) streamOffsetUs + arm.positionUs else -1L)
            super.flush()
        }

        /**
         * Vị trí của sink trong đổi từ trục ĐÃ GHI sang trục NỘI DUNG khi đã có dịch ([shift]): khung lặng chèn không phải nội dung, khung bỏ thì đã qua ([contentFrames]); ExoPlayer
         * (currentPosition, chuyển mục) và mọi chỗ đọc vị trí trình phát thấy đúng nội dung đang ra loa. Không giảm theo vị trí sink trong (renderer chỉ cho vị trí đi tới).
         */
        override fun getCurrentPositionUs(sourceEnded: Boolean): Long {
            val position = super.getCurrentPositionUs(sourceEnded)
            val list = shifts ?: return position
            if (position == AudioSink.CURRENT_POSITION_NOT_SET || rate <= 0 || firstPtsUs == C.TIME_UNSET) return position
            val played = maxOf(0L, ((position - firstPtsUs) * rate + 500_000L) / 1_000_000L) // làm tròn: sai < nửa khung
            return position + (contentFrames(played, list) - played) * 1_000_000L / rate
        }

        /** Đưa `buffer` xuống sink trong, đếm byte nó nhận và nhớ nó có giữ dở không (đường cũ: chỉ thêm phép đếm). */
        private fun down(buffer: ByteBuffer, pts: Long, encodedAccessUnitCount: Int): Boolean {
            if (firstPtsUs == C.TIME_UNSET) firstPtsUs = maxOf(0L, pts) // như DefaultAudioSink đặt startMediaTimeUs
            val before = buffer.position()
            val done = super.handleBuffer(buffer, pts, encodedAccessUnitCount)
            writtenBytes += buffer.position() - before
            innerBusy = !done
            return done
        }

        /** Bắt đầu lệnh dịch `order` ở chỗ đã ghi hiện tại. */
        private fun beginShift(order: ShiftOrder) {
            val at = Shift(writtenBytes / frameBytes, order.frames)
            (shifts ?: ArrayList<Shift>(4).also { shifts = it }).add(at)
            shifting = order
            if (order.frames < 0) dropLeft = -order.frames
            else silence = ByteBuffer.allocateDirect((order.frames * frameBytes).toInt()).order(ByteOrder.nativeOrder()) // số 0 = lặng với mọi PCM có dấu
        }

        private fun shiftDone() {
            val order = shifting ?: return
            shifting = null
            order.onApplied?.invoke(shifts!!.last())
        }

        private fun startCapture(c: Capture?) {
            capture = c
            captured = null
            capturedFrames = 0
            retryBuffer = null
        }

        /** Chép phần còn thiếu của [capture] từ `buffer` (đã cắt xong, chưa đưa xuống sink trong); trả byte cuối đã chép. Đủ thì gọi `onCaptured` và thôi chép. */
        private fun take(c: Capture, buffer: ByteBuffer): Int {
            if (!pcm16 || frameBytes == 0) {
                startCapture(null)
                return buffer.position()
            }
            val channels = frameBytes / 2
            val into = captured ?: ShortArray(c.frames * channels).also { captured = it }
            val from = if (buffer === retryBuffer) maxOf(buffer.position(), retryEnd) else buffer.position()
            val n = minOf(c.frames - capturedFrames, maxOf(0, buffer.limit() - from) / frameBytes)
            if (n > 0) {
                val view = buffer.duplicate().order(ByteOrder.LITTLE_ENDIAN)
                view.position(from)
                view.asShortBuffer().get(into, capturedFrames * channels, n * channels)
                capturedFrames += n
            }
            if (capturedFrames == c.frames) {
                startCapture(null)
                c.onCaptured(into)
            }
            return from + n * frameBytes
        }

        override fun handleBuffer(buffer: ByteBuffer, presentationTimeUs: Long, encodedAccessUnitCount: Int): Boolean {
            if (freshAfterFlush) {
                freshAfterFlush = false
                val arm = armed.get()
                // Chỉ lệnh CÓ kiểm nhãn xét ở đây; lệnh không kiểm nhãn đã được [flush] đếm lần xả (match -1).
                val checked = arm != null && checks(arm)
                val expected = if (checked) streamOffsetUs + arm!!.positionUs else -1L
                val match = when {
                    !checked -> -1
                    Math.abs(presentationTimeUs - expected) <= arm!!.toleranceUs -> 1
                    else -> 0
                }
                probe?.onFirstBuffer(presentationTimeUs, if (frameBytes > 0) (buffer.remaining() / frameBytes).toLong() else -1L, toDrop, seekPending, match)
                if (match == 1) {
                    // Buffer đích của lệnh tua: tiêu lệnh.
                    armed.compareAndSet(arm, null)
                    toDrop = arm!!.frames
                    startCapture(arm.capture)
                } else if (match == 0) {
                    // Buffer của dòng CŨ (lệnh tua trước / tua đệm còn trong ống): không cắt, không chụp, đi xuống nguyên vẹn; lệnh chờ lần xả kế.
                    toDrop = 0
                    staleLine = true
                    probe?.onSkip(presentationTimeUs, expected)
                }
            }
            seekPending = false
            var pts = presentationTimeUs
            if (toDrop > 0 && frameBytes > 0) {
                val k = minOf(toDrop, (buffer.remaining() / frameBytes).toLong())
                buffer.position(buffer.position() + (k * frameBytes).toInt())
                toDrop -= k
                if (rate > 0) pts += k * 1_000_000L / rate
                if (!buffer.hasRemaining()) return true
            }
            // Dịch pha ([shift]): chỉ bắt đầu khi sink trong không giữ dở buffer nào (không thì phải đưa lại đúng buffer ấy) và số cắt của lần tua đã xong.
            if (shifting == null && !innerBusy && toDrop == 0L && !staleLine && zeroIsSilence && rate > 0) shiftOrder.getAndSet(null)?.let(::beginShift)
            var dropped = 0L
            if (dropLeft > 0) {
                dropped = minOf(dropLeft, (buffer.remaining() / frameBytes).toLong())
                buffer.position(buffer.position() + (dropped * frameBytes).toInt())
                dropLeft -= dropped
                offsetFrames -= dropped
                if (dropLeft == 0L) shiftDone()
                if (!buffer.hasRemaining()) return true
            }
            // pts xuống sink trong theo trục ĐÃ GHI: pts nội dung (đã tính khung cắt) + khung vừa bỏ ở đầu buffer này + offsetFrames; khung bỏ không đẩy pts tới, khung lặng đẩy pts các buffer sau.
            val zeros = silence
            if (zeros != null) {
                if (zeros.hasRemaining() && !down(zeros, pts + (dropped + offsetFrames) * 1_000_000L / rate, 1)) return false // lặng chưa nhận hết: ExoPlayer gọi lại cùng buffer thật
                silence = null
                offsetFrames += shifting!!.frames
                shiftDone()
            }
            if (offsetFrames != 0L || dropped != 0L) pts += (dropped + offsetFrames) * 1_000_000L / rate
            val c = capture ?: return down(buffer, pts, encodedAccessUnitCount)
            val end = take(c, buffer)
            val done = down(buffer, pts, encodedAccessUnitCount)
            if (capture === c) {
                retryBuffer = if (done) null else buffer
                retryEnd = end
            }
            return done
        }
    }

    /**
     * Một lần dịch pha trong dòng của [LoopSink] ([LoopSink.shift]): `writtenAt` = số khung sink trong đã nhận kể từ lần xả tới chỗ dịch (= chỉ số khung trong AudioTrack sinh ra sau
     * lần xả ấy, cùng thang với framePosition), `frames` > 0 = chèn chừng ấy khung lặng ở đó, < 0 = bỏ chừng ấy khung nội dung.
     */
    class Shift(val writtenAt: Long, val frames: Long)

    /**
     * Vị trí NỘI DUNG (khung, kể từ khung đầu sau lần xả) khi AudioTrack đã phát `played` khung qua các dịch `shifts`: khung lặng chèn không phải nội dung (đang phát lặng thì nội dung
     * đứng yên), khung bỏ thì nội dung nhảy qua ngay khi tới chỗ dịch. Dịch chưa ra loa (writtenAt > played) không tính. Không giảm khi `played` tăng.
     * Dùng chung cho vị trí sink báo ExoPlayer ([LoopSink.getCurrentPositionUs]) và pha của lần chuyển a87 -> P3 ([SeamHandover.reading]).
     */
    fun contentFrames(played: Long, shifts: List<Shift>): Long {
        var content = played
        for (s in shifts) {
            if (s.frames > 0) content -= (played - s.writtenAt).coerceIn(0L, s.frames)
            else if (played >= s.writtenAt) content -= s.frames
        }
        return content
    }

    /** Kế hoạch một cú tua: vị trí cửa sổ ExoPlayer (ms) tới khung đáp, và số khung PCM [LoopSink] phải cắt từ khung đáp tới mốc. */
    internal class SeekPlan(val positionMs: Long, val trimFrames: Long)

    /**
     * Mốc tua `sample` là mẫu trên TRỤC DANH NGHĨA của mục `index` (0 = Clip đầu: mẫu 0 là audibleStart'; chẵn >= 2 = Clip lặp: mẫu 0 là loopStart' + X', không tính phần mở sớm; lẻ = Nối WAV).
     * Clip mp3: ExoPlayer bỏ nguyên các khung có nhãn trước vị trí tua nên khung chứa mốc không bao giờ phát; vì thế đáp ở khung `b0` = ranh khung dưới mốc lùi [Seam.prerollFrames] khung
     * (khung ấy được giữ vì ms làm tròn xuống, như mở Clip lặp), chạy nguội 3 khung, rồi cắt `mốc - b0` mẫu. Nối WAV: tua tới ranh khối 100 ms dưới mốc rồi cắt phần lẻ.
     */
    internal fun seekPlan(seam: Seam, index: Int, sample: Long): SeekPlan {
        val sr = seam.sampleRate
        if (index % 2 == 1) {
            // WavExtractor đưa mẫu theo khối sr/10 khung (100 ms). Nối đã được đọc trước (bộ đệm) thì ExoPlayer tua TRONG bộ đệm: khối chứa mốc có nhãn trước mốc nên bị bỏ nguyên khối và tiếng
            // bắt đầu ở khối sau (mốc 1005 ms -> 1100 ms, đo được +95 ms, lúc có lúc không tuỳ đã đọc trước chưa). Vì thế tua tới ĐÚNG ranh khối rồi cắt phần lẻ ở sink.
            // b0 * 1000 / sr là ms nguyên đúng của ranh khối (floor(ms * sr / 1000) == b0) khi [seamGridExact]; lần tua đệm cũng đứng trên lưới ([stepAside] theo mục).
            val chunk = (sr / 10).toLong().coerceAtLeast(1)
            val b0 = sample / chunk * chunk
            return SeekPlan(b0 * 1000 / sr, sample - b0)
        }
        val start = if (index == 0) seam.audibleStartSamples else seam.loopStartSamples + seam.xFrames
        val open = if (index == 0) start else start - seam.prerollSamples // khung đầu cửa sổ của mục (ranh khung)
        val t = start + sample
        val spf = seam.frameSamples.toLong()
        val b0 = maxOf(open, t / spf * spf - seam.prerollSamples)
        // ExoPlayer cho vào khung đầu tiên có nhãn >= vị trí tua. Nhãn khung b0 là k*spf*1e6/sr làm tròn xuống µs nên khi ranh b0 đúng bằng một số ms nguyên (đo: mốc 139520 ms ở 44,1 kHz) nhãn
        // có thể rớt dưới vị trí 1 µs và b0 bị bỏ, tiếng vào trễ đúng 1 khung. Lùi 1 ms (khung trước còn cách 24-72 ms nên vẫn không vào).
        return SeekPlan((seam.ms(b0) - seam.ms(open) - 1).coerceAtLeast(0), t - b0)
    }

    /**
     * API tua của Clip / Nối: tua tới mẫu `sample` (trục danh nghĩa của mục, xem [seekPlan]) chính xác từng mẫu; `sink` là [LoopSink] của chính player này. Gọi từ luồng của player.
     * `onLand` (chỉ Nối WAV, mục lẻ): LƯỚI AN TOÀN theo nội dung - [LoopSink] chép [LAND_FRAMES] khung đầu sau khi cắt, luồng nền tìm chúng trong WAV Nối ([landOf]) rồi gọi `onLand`
     * (ở luồng nền ấy) với mẫu đáp thật trên trục Nối, null = không tìm thấy (lần tua hỏng). Đọc WAV lỗi thì không gọi. Clip mp3 thì `onLand` không bao giờ được gọi.
     */
    fun seekToSample(player: Player, sink: LoopSink, seam: Seam, index: Int, sample: Long, onLand: ((Long?) -> Unit)? = null) {
        val plan = seekPlan(seam, index, sample)
        val capture = if (onLand != null && index % 2 == 1) LoopSink.Capture(LAND_FRAMES) { pcm -> land(seam, sample, pcm, onLand) } else null
        // ExoPlayer BỎ QUA lệnh tua tới đúng mục + vị trí nó đang đứng (đo: P3 đứng chờ ở đầu Nối, tua tới mẫu 170 cũng là mili giây 0 -> không xả bộ đệm, số cắt không áp, P3 phát tiếp từ mẫu 0).
        // Nên lệch sang bên một bước trước: tua đó thật, rồi tua tới mốc cũng thật. Số lần xả của sink không ứng 1-1 với số lệnh tua (máy thật OPPO: đáp lệch -4063, PLAN_loop §46.3 / §47.1:
        // buffer của lệnh tua trước tới sau lần xả của lệnh tua sau). Nối WAV: số cắt + lệnh chép gắn với NHÃN THỜI GIAN của buffer đích ([LoopSink.armSeek] `positionUs`: offset dòng ra + vị trí
        // tua tới từng ms, lưới khối [seamGridExact]); buffer của lần tua đệm có nhãn khác nên tự bị bỏ qua, `flushes` không dùng. Clip mp3 không kiểm nhãn (lần tua đệm chỉ lệch 1 ms, mp3 đáp ở
        // khung dưới mốc, chưa có số máy về offset của mục Clip): đếm lần xả (`flushes` = 2 khi có lần tua đệm), chỉ lần xả cuối cắt + chụp. Nối WAV chưa biết offset cũng rơi về đường đếm.
        val noop = seekIsNoop(player.currentMediaItemIndex, player.currentPosition, index, plan.positionMs)
        sink.armSeek(plan.trimFrames, capture, if (index % 2 == 1) plan.positionMs * 1000 else C.TIME_UNSET, flushes = if (noop) 2 else 1)
        if (noop) player.seekTo(index, stepAside(index, plan.positionMs))
        player.seekTo(index, plan.positionMs)
    }

    /** Lệnh tua tới (`index`, `positionMs`) khi trình phát đang ở (`currentIndex`, `currentMs`) có bị ExoPlayer bỏ qua không (cùng mục, cách nhau <= 2 ms). */
    internal fun seekIsNoop(currentIndex: Int, currentMs: Long, index: Int, positionMs: Long): Boolean = currentIndex == index && Math.abs(currentMs - positionMs) <= 2

    /** Vị trí khác vị trí tua thật 1 ms (trong cùng mục) để lần tua đệm không bị bỏ qua. Clip mp3. */
    internal fun stepAside(positionMs: Long): Long = if (positionMs > 0) positionMs - 1 else 1

    /**
     * Vị trí của lần tua đệm cho mục `index`. Nối WAV: ranh khối 100 ms TRƯỚC (sau, nếu < 100 ms) chứ không lệch 1 ms. Lệnh tua đệm thường nằm ngoài bộ đệm nên ExoPlayer tải lại WAV
     * từ floor(vị trí × sr / 1000) (WavSeekMap) và chia khối sr/10 từ đó; lệch 1 ms (399 ms ở 44,1 kHz = khung 17595) làm lưới khối lệch -45 khung, rồi lệnh tua thật (400 ms) rơi vào
     * bộ đệm ấy, chọn khối đầu có nhãn >= 400 ms = khung 22005 và bỏ nguyên khối chứa mốc: tiếng vào muộn 4365 khung (+99 ms, PLAN_loop §44.7, result10). Ranh khối kề thì lưới
     * vẫn đúng ([seamGridExact]). Clip mp3 giữ [stepAside].
     */
    internal fun stepAside(index: Int, positionMs: Long): Long =
        if (index % 2 == 1) (if (positionMs >= SEAM_CHUNK_MS) positionMs - SEAM_CHUNK_MS else positionMs + SEAM_CHUNK_MS) else stepAside(positionMs)

    /** Một khối của WavExtractor (sr/10 khung) tính bằng ms khi sr chia hết cho 10. */
    const val SEAM_CHUNK_MS = 100L

    /**
     * Ở tần số `sampleRate`, mọi ranh khối b0 = k × (sr/10) của Nối ([seekPlan]) có đúng một mili giây nguyên `b0 × 1000 / sr` với floor(ms × sr / 1000) == b0, và khối dài đúng
     * [SEAM_CHUNK_MS]: tải lại ở vị trí tua (hay vị trí tua đệm) nào cũng giữ lưới khối, tua trong bộ đệm cũng đáp đúng khối. Đúng khi sr chia hết cho 10 (8 / 12 / 16 / 22,05 / 24 /
     * 32 / 44,1 / 48 kHz). 11,025 kHz thì không (khối 1102 khung = 99,95 ms): không ms nào vừa đúng khi tải lại vừa đúng khi tua trong bộ đệm - giới hạn đã biết, lưới an toàn
     * ([seekToSample] `onLand`) bắt lệch còn lại (vài khung).
     */
    internal fun seamGridExact(sampleRate: Int): Boolean = sampleRate % 10 == 0

    /** Số khung đầu sau một lần tua vào Nối mà lưới an toàn đem đi tìm trong WAV ([seekToSample] `onLand`): 5,8 ms ở 44,1 kHz, PCM16 khớp từng bit. */
    const val LAND_FRAMES = 256

    /** Độ lệch nhãn (µs) giữa nhãn buffer đầu và vị trí đích của lệnh tua mà [LoopSink] còn coi là buffer đích. Buffer dòng cũ cách ít nhất một khối (100 ms). */
    const val PTS_TOLERANCE_US = 1000L

    /** Lưới an toàn tìm mẫu đáp trong ±chừng này giây quanh đích (kẹp trong WAV). */
    const val LAND_RADIUS_SECONDS = 1

    /** Luồng nền của lưới an toàn: đọc WAV + so, không bao giờ ở luồng phát hay luồng chính. */
    private val landWorker by lazy {
        java.util.concurrent.Executors.newSingleThreadExecutor { Thread(it, "abook-seam-land").apply { isDaemon = true } }
    }

    private fun land(seam: Seam, expected: Long, pcm: ShortArray, onLand: (Long?) -> Unit) {
        landWorker.execute {
            val landed = try {
                landOf(seam, expected, pcm)
            } catch (e: java.io.IOException) {
                android.util.Log.w("ABookMusic", "lưới an toàn Nối: không đọc được WAV (${e.message})")
                return@execute
            }
            onLand(landed)
        }
    }

    /**
     * Mẫu đáp thật của một lần tua vào Nối: vị trí (khung trong WAV Nối) gần `expected` nhất mà `pcm` (K khung đầu sau khi cắt, PCM16 xen kênh) trùng WAV từng bit, trong ±[LAND_RADIUS_SECONDS]
     * quanh đích (kẹp trong file); null = không thấy. Đọc đĩa: chạy ở luồng nền.
     */
    internal fun landOf(seam: Seam, expected: Long, pcm: ShortArray): Long? {
        val k = pcm.size / seam.channels
        val radius = LAND_RADIUS_SECONDS.toLong() * seam.sampleRate
        val from = (expected - radius).coerceIn(0L, seam.xFrames.toLong())
        val to = (expected + radius + k).coerceIn(from, seam.xFrames.toLong())
        val ref = readWavFrames(seam.wav, seam.channels, from, (to - from).toInt())
        return SeamMatch.nearest(ref, from, seam.channels, pcm, expected, radius)
    }

    /** `count` khung PCM16 xen kênh từ khung `first` của WAV do [writeWav] ghi (đầu 44 byte). */
    internal fun readWavFrames(wav: File, channels: Int, first: Long, count: Int): ShortArray {
        val bytes = ByteArray(count * channels * 2)
        java.io.RandomAccessFile(wav, "r").use {
            it.seek(44L + first * channels * 2)
            it.readFully(bytes)
        }
        val out = ShortArray(count * channels)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(out)
        return out
    }

    /** Như [seekToSample] với mốc là `ms` mili giây trên trục danh nghĩa (mẫu = round(ms * sr / 1000)). */
    fun seekTo(player: Player, sink: LoopSink, seam: Seam, index: Int, ms: Long) =
        seekToSample(player, sink, seam, index, Math.round(ms * seam.sampleRate / 1000.0))

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
     * cuối khác mặc định). encoderDelay ở đây chỉ là LỜI NHẮN cho [LoopSink] (preroll cần cắt khi vào mục bằng chuyển mục liền); nó cắt đầu và đưa sink trong encoderDelay = 0.
     * encoderPadding đi thẳng xuống TrimmingAudioProcessor, cắt cuối mục. Tua đi qua [seekToSample], không qua `player.seekTo`.
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
