package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.OutputStream
import java.io.RandomAccessFile

/**
 * Thẻ ID3 của "Xuất MP3" (Mp3Export): đúng những byte ffmpeg ghi ở máy tính (webui/export.py `write_chapter`: `-c:a copy
 * -map_metadata -1 -id3v2_version 3 -write_id3v1 1`) - ID3v2.3 đầu file, ID3v1 cuối file, ảnh bìa trong khung APIC. Chỉ thiếu
 * khung TSSE (tên phiên bản ffmpeg, "Lavf61.7.100"): điện thoại không có ffmpeg để mà ghi. Bộ ví dụ chung tests/fixtures/mp3_export.
 *
 * Âm thanh chép nguyên từng byte (không mã hoá lại): bỏ thẻ ID3v2 đầu và ID3v1 cuối của file chương, giữ mọi khung MP3 ở giữa.
 */
object Id3Tag {
    /** Thể loại ghi cho mọi chương xuất - khớp tên trong bảng thể loại ID3v1 (số 183). */
    const val GENRE = "Audiobook"
    private const val GENRE_V1 = 183
    /** ffmpeg luôn chừa 10 byte trống sau các khung (id3v2enc: padding mặc định). */
    private const val PADDING = 10
    private const val V1_SIZE = 128

    /** Ảnh bìa: kiểu MIME như ffmpeg đặt theo codec (`image/jpeg`, `image/png`) và nguyên byte của file. */
    class Cover(val mime: String, val bytes: ByteArray) {
        companion object {
            /** Nhận JPEG hay PNG theo mấy byte đầu; loại khác thì không làm bìa (null). */
            fun of(bytes: ByteArray): Cover? = when {
                bytes.size > 3 && bytes[0] == 0xFF.toByte() && bytes[1] == 0xD8.toByte() -> Cover("image/jpeg", bytes)
                bytes.size > 8 && bytes.copyOfRange(0, 8).contentEquals(PNG) -> Cover("image/png", bytes)
                else -> null
            }

            private val PNG = byteArrayOf(0x89.toByte(), 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A)
        }
    }

    /** Thứ ghi vào thẻ của một chương: tên chương, tên sách, giọng kể (cả TPE1 lẫn TPE2), số thứ tự "n/tổng", bìa. */
    class Fields(val title: String, val album: String, val artist: String, val number: Int, val total: Int, val cover: Cover?)

    /** Thẻ ID3v2.3: các khung chữ theo thứ tự ffmpeg ghi, rồi APIC, rồi 10 byte trống. Chữ rỗng thì không có khung (như ffmpeg). */
    fun v2(fields: Fields): ByteArray {
        val frames = ByteArrayOutputStream()
        text(frames, "TIT2", fields.title)
        text(frames, "TALB", fields.album)
        text(frames, "TPE1", fields.artist)
        text(frames, "TPE2", fields.artist)
        text(frames, "TRCK", "${fields.number}/${fields.total}")
        text(frames, "TCON", GENRE)
        fields.cover?.let { cover ->
            val body = ByteArrayOutputStream()
            body.write(0) // ISO-8859-1: mô tả "Album cover" là ASCII
            body.write(cover.mime.toByteArray(Charsets.ISO_8859_1))
            body.write(0)
            body.write(3) // bìa trước (ffmpeg: comment "Cover (front)")
            body.write("Album cover".toByteArray(Charsets.ISO_8859_1))
            body.write(0)
            body.write(cover.bytes)
            frame(frames, "APIC", body.toByteArray())
        }
        val size = frames.size() + PADDING
        val out = ByteArrayOutputStream(10 + size)
        out.write("ID3".toByteArray(Charsets.ISO_8859_1))
        out.write(byteArrayOf(3, 0, 0))
        out.write(byteArrayOf((size shr 21 and 0x7F).toByte(), (size shr 14 and 0x7F).toByte(), (size shr 7 and 0x7F).toByte(), (size and 0x7F).toByte()))
        frames.writeTo(out)
        out.write(ByteArray(PADDING))
        return out.toByteArray()
    }

    /** Thẻ ID3v1 (128 byte): UTF-8 nguyên byte như ffmpeg chép, mỗi ô cắt ở 30 byte (có thể giữa một chữ có dấu, như máy tính). */
    fun v1(fields: Fields): ByteArray {
        val tag = ByteArray(V1_SIZE)
        "TAG".toByteArray(Charsets.ISO_8859_1).copyInto(tag)
        put(tag, 3, fields.title)
        put(tag, 33, fields.artist)
        put(tag, 63, fields.album)
        tag[125] = 0
        tag[126] = fields.number.toByte() // atoi("n/tổng") vào một byte
        tag[127] = GENRE_V1.toByte()
        return tag
    }

    /** Khoảng [đầu, cuối) của phần âm thanh trong file MP3: sau (các) thẻ ID3v2 đầu file, trước thẻ ID3v1 cuối file. */
    fun audioRange(file: File): LongRange {
        RandomAccessFile(file, "r").use { input ->
            val length = input.length()
            var start = 0L
            val header = ByteArray(10)
            while (start + 10 <= length) {
                input.seek(start)
                input.readFully(header)
                if (header[0] != 'I'.code.toByte() || header[1] != 'D'.code.toByte() || header[2] != '3'.code.toByte()) break
                val size = (header[6].toLong() and 0x7FL shl 21) or (header[7].toLong() and 0x7FL shl 14) or
                    (header[8].toLong() and 0x7FL shl 7) or (header[9].toLong() and 0x7FL)
                val footer = if (header[5].toInt() and 0x10 != 0) 10 else 0
                start = minOf(length, start + 10 + size + footer)
            }
            var end = length
            if (end - V1_SIZE >= start) {
                val tail = ByteArray(3)
                input.seek(end - V1_SIZE)
                input.readFully(tail)
                if (tail.contentEquals("TAG".toByteArray(Charsets.ISO_8859_1))) end -= V1_SIZE
            }
            return start until end
        }
    }

    /**
     * Chép `source` sang `out` với thẻ mới: ID3v2.3, âm thanh nguyên byte, ID3v1. `stopped` được hỏi giữa từng khúc 64 KB - trả true
     * thì ném [Mp3Export.Stopped] (người dùng bấm "Dừng").
     */
    fun write(source: File, out: OutputStream, fields: Fields, stopped: () -> Boolean = { false }) {
        val range = audioRange(source)
        out.write(v2(fields))
        RandomAccessFile(source, "r").use { input ->
            input.seek(range.first)
            var left = range.last - range.first + 1
            val buffer = ByteArray(64 * 1024)
            while (left > 0) {
                if (stopped()) throw Mp3Export.Stopped()
                val read = input.read(buffer, 0, minOf(buffer.size.toLong(), left).toInt())
                if (read < 0) break
                out.write(buffer, 0, read)
                left -= read
            }
        }
        out.write(v1(fields))
    }

    /** Khung chữ: ASCII ghi ISO-8859-1, còn lại UTF-16 có BOM (FF FE, little-endian) - đều kết thúc bằng ký tự 0, như ffmpeg. */
    private fun text(out: ByteArrayOutputStream, id: String, value: String) {
        if (value.isEmpty()) return
        val body = ByteArrayOutputStream()
        if (value.all { it.code < 128 }) {
            body.write(0)
            body.write(value.toByteArray(Charsets.ISO_8859_1))
            body.write(0)
        } else {
            body.write(1)
            body.write(byteArrayOf(0xFF.toByte(), 0xFE.toByte()))
            body.write(value.toByteArray(Charsets.UTF_16LE))
            body.write(byteArrayOf(0, 0))
        }
        frame(out, id, body.toByteArray())
    }

    /** Khung ID3v2.3: mã 4 chữ, cỡ 4 byte big-endian (không syncsafe), 2 byte cờ 0. */
    private fun frame(out: ByteArrayOutputStream, id: String, body: ByteArray) {
        out.write(id.toByteArray(Charsets.ISO_8859_1))
        val size = body.size
        out.write(byteArrayOf((size ushr 24).toByte(), (size ushr 16).toByte(), (size ushr 8).toByte(), size.toByte()))
        out.write(byteArrayOf(0, 0))
        out.write(body)
    }

    private fun put(tag: ByteArray, at: Int, value: String) {
        val bytes = value.toByteArray(Charsets.UTF_8)
        bytes.copyInto(tag, at, 0, minOf(30, bytes.size))
    }
}
