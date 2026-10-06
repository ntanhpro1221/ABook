package vn.abook.player

import java.io.ByteArrayOutputStream

/** Đọc byte của file MP3 trong bộ ví dụ "Xuất MP3" (tests/fixtures/mp3_export) - dùng chung cho test JVM và bài thử trên máy Android. */
object Id3Bytes {
    fun syncsafe(bytes: ByteArray, at: Int): Int =
        (bytes[at].toInt() and 0x7F shl 21) or (bytes[at + 1].toInt() and 0x7F shl 14) or
            (bytes[at + 2].toInt() and 0x7F shl 7) or (bytes[at + 3].toInt() and 0x7F)

    /** Thẻ ID3v2.3 đầu file `data` với khung `drop` bị bỏ (cỡ thẻ tính lại) - khung TSSE là tên phiên bản ffmpeg. */
    fun v2Without(data: ByteArray, drop: String): ByteArray {
        val size = syncsafe(data, 6)
        val body = data.copyOfRange(10, 10 + size)
        val kept = ByteArrayOutputStream()
        var at = 0
        while (at + 10 <= body.size && body[at] != 0.toByte()) {
            val length = ((body[at + 4].toInt() and 0xFF) shl 24) or ((body[at + 5].toInt() and 0xFF) shl 16) or
                ((body[at + 6].toInt() and 0xFF) shl 8) or (body[at + 7].toInt() and 0xFF)
            if (String(body, at, 4, Charsets.ISO_8859_1) != drop) kept.write(body, at, 10 + length)
            at += 10 + length
        }
        kept.write(body, at, body.size - at) // phần đệm
        val frames = kept.toByteArray()
        val n = frames.size
        return data.copyOfRange(0, 6) + byteArrayOf((n shr 21 and 0x7F).toByte(), (n shr 14 and 0x7F).toByte(),
            (n shr 7 and 0x7F).toByte(), (n and 0x7F).toByte()) + frames
    }

    /** Thẻ ID3v1 (128 byte cuối). */
    fun v1(data: ByteArray): ByteArray = data.copyOfRange(data.size - 128, data.size)

    /** Cỡ khung MP3 bắt đầu ở `at` (MPEG-1/2/2.5 lớp III). */
    fun frameLength(data: ByteArray, at: Int): Int {
        val b1 = data[at + 1].toInt() and 0xFF
        val b2 = data[at + 2].toInt() and 0xFF
        val version = (b1 shr 3) and 3 // 3 = MPEG-1, 2 = MPEG-2, 0 = MPEG-2.5
        val bitrates = if (version == 3) intArrayOf(0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
        else intArrayOf(0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
        val rates = when (version) {
            3 -> intArrayOf(44100, 48000, 32000)
            2 -> intArrayOf(22050, 24000, 16000)
            else -> intArrayOf(11025, 12000, 8000)
        }
        val bitrate = bitrates[b2 shr 4] * 1000
        val rate = rates[(b2 shr 2) and 3]
        val padding = (b2 shr 1) and 1
        return (if (version == 3) 144 else 72) * bitrate / rate + padding
    }
}
