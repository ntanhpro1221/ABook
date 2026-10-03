package vn.abook.player.readaloud

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.io.RandomAccessFile

/**
 * WAV PCM tối thiểu cho giọng của máy: đọc đầu file `synthesizeToFile` ghi ra (độ dài thật lấy từ cỡ file - bộ đọc nào cũng có thể ghi cỡ `data` sai khi
 * ghi theo dòng) và nối nhiều mảnh (đoạn dài hơn `getMaxSpeechInputLength`) thành một file.
 */
object Wav {
    class Format(val sampleRate: Int, val channels: Int, val bitsPerSample: Int, val dataOffset: Int) {
        val bytesPerSecond: Long get() = sampleRate.toLong() * channels * (bitsPerSample / 8)
        fun durationMs(fileLength: Long): Long = ((fileLength - dataOffset).coerceAtLeast(0)) * 1000 / bytesPerSecond.coerceAtLeast(1)
    }

    private fun le32(b: ByteArray, at: Int) = (b[at].toInt() and 0xFF) or ((b[at + 1].toInt() and 0xFF) shl 8) or ((b[at + 2].toInt() and 0xFF) shl 16) or ((b[at + 3].toInt() and 0xFF) shl 24)
    private fun le16(b: ByteArray, at: Int) = (b[at].toInt() and 0xFF) or ((b[at + 1].toInt() and 0xFF) shl 8)

    /** Đọc `fmt ` và vị trí bắt đầu `data` từ `head` (vài trăm byte đầu là đủ); null nếu không phải WAV PCM. */
    fun parse(head: ByteArray): Format? {
        if (head.size < 12 || String(head, 0, 4, Charsets.US_ASCII) != "RIFF" || String(head, 8, 4, Charsets.US_ASCII) != "WAVE") return null
        var at = 12
        var rate = 0
        var channels = 0
        var bits = 0
        while (at + 8 <= head.size) {
            val name = String(head, at, 4, Charsets.US_ASCII)
            val size = le32(head, at + 4)
            if (name == "fmt " && at + 8 + 16 <= head.size) {
                channels = le16(head, at + 10)
                rate = le32(head, at + 12)
                bits = le16(head, at + 22)
            } else if (name == "data") {
                return if (rate > 0 && channels > 0 && bits > 0) Format(rate, channels, bits, at + 8) else null
            }
            if (size < 0) return null
            at += 8 + size + (size and 1)
        }
        return null
    }

    fun format(file: File): Format? {
        val head = ByteArray(minOf(file.length(), 1024L).toInt())
        RandomAccessFile(file, "r").use { it.readFully(head) }
        return parse(head)
    }

    /** Nối các file WAV cùng định dạng thành `out` (một đầu 44 byte + dữ liệu của từng mảnh). */
    fun concat(parts: List<File>, out: File): Format {
        val formats = parts.map { format(it) ?: throw IOException("không đọc được WAV: ${it.name}") }
        val first = formats.first()
        if (formats.any { it.sampleRate != first.sampleRate || it.channels != first.channels || it.bitsPerSample != first.bitsPerSample }) {
            throw IOException("các mảnh WAV khác định dạng")
        }
        val dataSize = parts.indices.sumOf { parts[it].length() - formats[it].dataOffset }
        out.outputStream().buffered().use { sink ->
            val head = ByteArrayOutputStream(44)
            fun put32(v: Long) { for (i in 0 until 4) head.write(((v shr (8 * i)) and 0xFF).toInt()) }
            fun put16(v: Int) { head.write(v and 0xFF); head.write((v shr 8) and 0xFF) }
            head.write("RIFF".toByteArray()); put32(36 + dataSize); head.write("WAVEfmt ".toByteArray()); put32(16)
            put16(1); put16(first.channels); put32(first.sampleRate.toLong()); put32(first.bytesPerSecond)
            put16(first.channels * first.bitsPerSample / 8); put16(first.bitsPerSample)
            head.write("data".toByteArray()); put32(dataSize)
            sink.write(head.toByteArray())
            for ((index, part) in parts.withIndex()) {
                part.inputStream().use { input ->
                    var left = formats[index].dataOffset.toLong()
                    while (left > 0) {
                        val skipped = input.skip(left)
                        if (skipped <= 0) throw IOException("WAV cụt: ${part.name}")
                        left -= skipped
                    }
                    input.copyTo(sink)
                }
            }
        }
        return Format(first.sampleRate, first.channels, first.bitsPerSample, 44)
    }
}
