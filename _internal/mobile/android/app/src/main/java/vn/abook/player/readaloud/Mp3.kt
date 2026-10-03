package vn.abook.player.readaloud

/**
 * Độ dài thật của một file MP3 lớp III bằng cách đi qua từng khung (không giải mã) - bản Kotlin của `abook/readaloud/mp3.py`, cùng cách tính tới từng ms. Giọng
 * dùng khoá (Google, FPT.AI, Viettel AI) trả MP3 mà không nói độ dài; nhiều lượt gọi của một đoạn nối liền nhau nên phải cộng đúng từng khung.
 * Định dạng khung: ISO/IEC 11172-3 và 13818-3.
 */
object Mp3 {
    private val BITRATES_V1 = intArrayOf(0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
    private val BITRATES_V2 = intArrayOf(0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
    private val RATES = mapOf(3 to intArrayOf(44100, 48000, 32000), 2 to intArrayOf(22050, 24000, 16000), 0 to intArrayOf(11025, 12000, 8000))

    private fun u(data: ByteArray, at: Int) = data[at].toInt() and 0xFF

    private fun skipId3(data: ByteArray, at: Int): Int {
        if (at + 10 <= data.size && data[at] == 'I'.code.toByte() && data[at + 1] == 'D'.code.toByte() && data[at + 2] == '3'.code.toByte()) {
            val size = (u(data, at + 6) shl 21) or (u(data, at + 7) shl 14) or (u(data, at + 8) shl 7) or u(data, at + 9)
            val footer = if (u(data, at + 5) and 0x10 != 0) 10 else 0
            return at + 10 + size + footer
        }
        return at
    }

    /** Khung bắt đầu ở `at`: (độ dài byte, số mẫu, tần số) hay null. */
    fun frameAt(data: ByteArray, at: Int): Triple<Int, Int, Int>? {
        if (at + 4 > data.size || u(data, at) != 0xFF || u(data, at + 1) and 0xE0 != 0xE0) return null
        val version = (u(data, at + 1) shr 3) and 0x03
        val layer = (u(data, at + 1) shr 1) and 0x03
        val bitrateIndex = u(data, at + 2) shr 4
        val rateIndex = (u(data, at + 2) shr 2) and 0x03
        if (version == 1 || layer != 1 || bitrateIndex == 0 || bitrateIndex == 15 || rateIndex == 3) return null
        val rate = RATES.getValue(version)[rateIndex]
        val padding = (u(data, at + 2) shr 1) and 0x01
        return if (version == 3) Triple(144_000 * BITRATES_V1[bitrateIndex] / rate + padding, 1152, rate)
        else Triple(72_000 * BITRATES_V2[bitrateIndex] / rate + padding, 576, rate)
    }

    /** Tổng độ dài (ms, làm tròn xuống) của mọi khung; thẻ ID3 và rác bị bỏ qua. Không khung nào -> 0. */
    fun durationMs(data: ByteArray): Long {
        var at = 0
        var micros = 0L
        while (at < data.size) {
            val skipped = skipId3(data, at)
            if (skipped != at) {
                at = skipped
                continue
            }
            val frame = frameAt(data, at)
            if (frame == null) {
                at += 1
                continue
            }
            micros += frame.second * 1_000_000L / frame.third
            at += frame.first
        }
        return micros / 1000
    }
}
