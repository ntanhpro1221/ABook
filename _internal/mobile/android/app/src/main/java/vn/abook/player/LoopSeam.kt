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
     * - tua: [seekToSample] gọi [armSeek]; lần `flush` đầu sau đó đặt số cắt = số mẫu từ khung đáp tới mốc tua, và lần `configure` theo sau (nếu mục đổi) KHÔNG ghi đè nó;
     * mẫu bị cắt khỏi các buffer đầu dòng ngay trước khi đưa xuống sink trong, nên không phụ thuộc trạng thái nào của media3 ngoài thứ tự gọi flush -> configure -> handleBuffer.
     * Phải đặt vào ExoPlayer qua `DefaultRenderersFactory.buildAudioSink`; app thật bọc sink MusicBed bằng cái này.
     */
    class LoopSink(inner: AudioSink) : ForwardingAudioSink(inner) {
        private class Arm(val frames: Long, val ns: Long)

        private val armed = AtomicReference<Arm?>(null)
        private var toDrop = 0L
        private var seekPending = false
        private var frameBytes = 0
        private var rate = 0

        /** Gọi trước `player.seekTo`: lần flush kế (trong 2 s) mang số cắt `frames` khung đầu dòng. Số cắt cũ chưa dùng bị thay. */
        internal fun armSeek(frames: Long) = armed.set(Arm(frames, System.nanoTime()))

        override fun configure(config: AudioSink.AudioSinkConfig) {
            val f = config.format
            frameBytes = if (f.pcmEncoding != Format.NO_VALUE && f.channelCount > 0) Util.getPcmFrameSize(f.pcmEncoding, f.channelCount) else 0
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
            val arm = armed.getAndSet(null)?.takeIf { System.nanoTime() - it.ns < 2_000_000_000L }
            if (arm != null) {
                toDrop = arm.frames
                seekPending = true
            } else if (!seekPending) {
                toDrop = 0
            }
            super.flush()
        }

        override fun handleBuffer(buffer: ByteBuffer, presentationTimeUs: Long, encodedAccessUnitCount: Int): Boolean {
            seekPending = false
            var pts = presentationTimeUs
            if (toDrop > 0 && frameBytes > 0) {
                val k = minOf(toDrop, (buffer.remaining() / frameBytes).toLong())
                buffer.position(buffer.position() + (k * frameBytes).toInt())
                toDrop -= k
                if (rate > 0) pts += k * 1_000_000L / rate
                if (!buffer.hasRemaining()) return true
            }
            return super.handleBuffer(buffer, pts, encodedAccessUnitCount)
        }
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
     */
    fun seekToSample(player: Player, sink: LoopSink, seam: Seam, index: Int, sample: Long) {
        val plan = seekPlan(seam, index, sample)
        sink.armSeek(plan.trimFrames)
        player.seekTo(index, plan.positionMs)
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
