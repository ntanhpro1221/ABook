package vn.abook.player

import androidx.annotation.OptIn
import androidx.media3.common.C
import androidx.media3.common.util.UnstableApi
import androidx.media3.extractor.Extractor
import androidx.media3.extractor.ExtractorInput
import androidx.media3.extractor.ExtractorOutput
import androidx.media3.extractor.ForwardingExtractorInput
import androidx.media3.extractor.MpegAudioUtil
import androidx.media3.extractor.PositionHolder
import androidx.media3.extractor.mp3.Mp3Extractor
import kotlin.math.roundToLong

/**
 * Bộ tách mp3 tua ĐÚNG KHUNG cho nhạc nền (loopfix): bài lặp mờ chéo vào lại từ loopStart ([MusicBed.crossLoop]) mà file có
 * khung Xing kèm mục lục 100 điểm thì Mp3Extractor tua theo mục lục ấy - lệch 0,3-2,2 s (scratchpad loopseek/REPORT.md); bài CBR có
 * khung Info thì trôi vài ms theo vị trí. Media3 1.11.1 không có cách công khai buộc đếm khung: FLAG_ENABLE_INDEX_SEEKING chỉ dùng
 * IndexSeeker khi seeker từ header không tua được.
 *
 * Nên lớp này cho Mp3Extractor(FLAG_ENABLE_INDEX_SEEKING) thấy khung Xing/Info đã viết lại TẠI CHỖ, cùng cỡ: nhãn "Xing" (Info sẽ
 * dựng ConstantBitrateSeeker), bỏ cờ mục lục (bit 4), phần sau mục lục dời lên 100 byte, đệm 0. Vị trí byte trong file không đổi;
 * số khung, cỡ dữ liệu, gapless LAME vẫn do Mp3Extractor tự đọc như cũ (độ dài + gapless trùng DefaultExtractorsFactory); XingSeeker
 * hết tua được nên nó chuyển sang IndexSeeker (đếm khung từ đầu, nhãn sau khi tua = k*spf/sr). Khung VBRI và file không header:
 * nguyên như cũ. Chỉ nhạc nền dùng ([Streaming.mediaSourceFactory] `exactMp3Seek`): tua xa trong chương nghe thẳng sẽ phải tải
 * mọi byte từ đầu.
 */
@OptIn(UnstableApi::class)
class ExactSeekMp3Extractor : Extractor {
    private val inner = Mp3Extractor(Mp3Extractor.FLAG_ENABLE_INDEX_SEEKING)
    private var scanned = false
    private var patchAt = -1L // vị trí trong file của patch[0]
    private var patch: ByteArray? = null // byte thay thế (null = để nguyên)

    override fun sniff(input: ExtractorInput): Boolean {
        scan(input)
        return inner.sniff(view(input))
    }

    override fun init(output: ExtractorOutput) = inner.init(output)

    override fun read(input: ExtractorInput, seekPosition: PositionHolder): Int {
        if (!scanned && input.position == 0L) scan(input)
        return inner.read(view(input), seekPosition)
    }

    override fun seek(position: Long, timeUs: Long) = inner.seek(position, timeUs)

    override fun release() = inner.release()

    private fun view(input: ExtractorInput): ExtractorInput = if (patch == null) input else View(input)

    /** Tìm khung đầu (bỏ thẻ ID3v2) bằng peek từ vị trí 0, rồi trả vị trí peek về chỗ cũ. */
    private fun scan(input: ExtractorInput) {
        if (scanned || input.position != 0L) return
        scanned = true
        input.resetPeekPosition()
        try {
            val id3 = ByteArray(10)
            var pos = 0L
            while (input.peekFully(id3, 0, 10, true) && id3[0] == 'I'.code.toByte() && id3[1] == 'D'.code.toByte() && id3[2] == '3'.code.toByte()) {
                val size = ((id3[6].toInt() and 0x7f) shl 21) or ((id3[7].toInt() and 0x7f) shl 14) or
                    ((id3[8].toInt() and 0x7f) shl 7) or (id3[9].toInt() and 0x7f)
                val skip = size + if (id3[5].toInt() and 0x10 != 0) 10 else 0
                if (!input.advancePeekPosition(skip, true)) return
                pos += 10 + skip
            }
            input.resetPeekPosition()
            if (pos > 0 && !input.advancePeekPosition(pos.toInt(), true)) return
            val window = ByteArray(16384)
            var n = 0
            while (n < window.size) {
                val r = input.peek(window, n, window.size - n)
                if (r == C.RESULT_END_OF_INPUT) break
                n += r
            }
            val header = MpegAudioUtil.Header()
            var i = 0
            while (i + 4 <= n) {
                val word = u32(window, i)
                if ((word and 0xFFE00000.toInt()) == 0xFFE00000.toInt() && header.setForHeaderData(word)) {
                    val size = header.frameSize
                    // khung kế phải nối ngay sau thì mới chắc là khung thật
                    if (i + size + 4 <= n && (u32(window, i + size) and 0xFFFE0C00.toInt()) == (word and 0xFFFE0C00.toInt())) {
                        build(window, i, pos + i, header)
                        return
                    }
                }
                i++
            }
        } finally {
            input.resetPeekPosition()
        }
    }

    private fun build(window: ByteArray, at: Int, fileAt: Long, header: MpegAudioUtil.Header) {
        val mono = header.channels == 1
        val side = if (header.version == 3 /* MPEG-1 */) (if (mono) 17 else 32) else (if (mono) 9 else 17)
        val tagAt = at + 4 + side
        val tag = u32(window, tagAt)
        if (tag != XING && tag != INFO) return // VBRI (luôn tua được) hay không header: để nguyên
        val flags = u32(window, tagAt + 4)
        if (tag == XING && flags and 4 == 0) return // Xing không mục lục: đã đếm khung sẵn
        val frameSize = header.frameSize
        val frame = window.copyOfRange(at, at + frameSize)
        val t = tagAt - at
        // Info -> Xing, bỏ cờ mục lục, xoá 100 byte mục lục tại chỗ
        "Xing".forEachIndexed { k, c -> frame[t + k] = c.code.toByte() }
        val newFlags = flags and 4.inv()
        for (k in 0 until 4) frame[t + 4 + k] = (newFlags ushr (24 - 8 * k)).toByte()
        if (flags and 4 != 0) {
            val tocAt = t + 8 + (if (flags and 1 != 0) 4 else 0) + (if (flags and 2 != 0) 4 else 0)
            System.arraycopy(frame, tocAt + 100, frame, tocAt, frameSize - tocAt - 100)
            frame.fill(0, frameSize - 100, frameSize)
        }
        patchAt = fileAt
        patch = frame
    }

    /** Phủ [patch] lên mọi byte Mp3Extractor đọc hay peek ở vùng [patchAt]. */
    private inner class View(input: ExtractorInput) : ForwardingExtractorInput(input) {
        private fun fix(at: Long, buffer: ByteArray, offset: Int, length: Int) {
            val bytes = patch ?: return
            if (length <= 0) return
            val from = maxOf(at, patchAt)
            val end = minOf(at + length, patchAt + bytes.size)
            for (p in from until end) buffer[offset + (p - at).toInt()] = bytes[(p - patchAt).toInt()]
        }

        override fun read(buffer: ByteArray, offset: Int, length: Int): Int {
            val at = position
            val r = super.read(buffer, offset, length)
            if (r > 0) fix(at, buffer, offset, r)
            return r
        }

        override fun readFully(target: ByteArray, offset: Int, length: Int, allowEndOfInput: Boolean): Boolean {
            val at = position
            val ok = super.readFully(target, offset, length, allowEndOfInput)
            if (ok) fix(at, target, offset, length)
            return ok
        }

        override fun readFully(target: ByteArray, offset: Int, length: Int) {
            readFully(target, offset, length, false)
        }

        override fun peek(target: ByteArray, offset: Int, length: Int): Int {
            val at = peekPosition
            val r = super.peek(target, offset, length)
            if (r > 0) fix(at, target, offset, r)
            return r
        }

        override fun peekFully(target: ByteArray, offset: Int, length: Int, allowEndOfInput: Boolean): Boolean {
            val at = peekPosition
            val ok = super.peekFully(target, offset, length, allowEndOfInput)
            if (ok) fix(at, target, offset, length)
            return ok
        }

        override fun peekFully(target: ByteArray, offset: Int, length: Int) {
            peekFully(target, offset, length, false)
        }
    }

    companion object {
        private const val XING = 0x58696e67
        private const val INFO = 0x496e666f

        private fun u32(b: ByteArray, p: Int): Int =
            ((b[p].toInt() and 0xff) shl 24) or ((b[p + 1].toInt() and 0xff) shl 16) or ((b[p + 2].toInt() and 0xff) shl 8) or (b[p + 3].toInt() and 0xff)

        /**
         * Ranh khung mp3 gần `seconds` nhất (giây, = k*spf/sr): ExoPlayer bỏ nguyên khung có nhãn trước chỗ bắt đầu chứ không cắt
         * giữa khung, nên vào thẳng ranh khung thì tiếng đầu lệch loopStart nửa khung là cùng, không phải gần trọn khung. spf 1152 với
         * MPEG-1 (sr >= 32 kHz), 576 với MPEG-2/2.5. Gọi xong lấy mili giây làm tròn xuống (MusicBed.open) - khung ấy vẫn được giữ.
         */
        fun frameBoundarySeconds(seconds: Double, sampleRate: Int): Double {
            if (sampleRate <= 0) return seconds
            val samplesPerFrame = if (sampleRate >= 32000) 1152 else 576
            val k = (seconds * sampleRate / samplesPerFrame).roundToLong()
            return k * samplesPerFrame.toDouble() / sampleRate
        }
    }
}
