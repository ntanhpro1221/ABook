package vn.abook.player

import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Đọc thẻ giả cho test JVM (máy thật dùng MediaMetadataRetriever; javax.sound không có trong bộ thử Android): đọc độ dài của file WAV từ
 * phần đầu RIFF; file khác (hay không phải WAV) thì từ chối với đúng lý do của máy tính. Không có thẻ nào - tên bài là tên file.
 */
object FakeTags : MusicStore.TagReader {
    override fun read(file: File): MusicStore.Tags {
        val bytes = file.readBytes()
        if (bytes.size < 44 || String(bytes, 0, 4, Charsets.US_ASCII) != "RIFF" || String(bytes, 8, 4, Charsets.US_ASCII) != "WAVE") {
            throw MusicStore.ImportError("không đọc được như một bản nhạc")
        }
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        var byteRate = 0
        var data = -1
        var at = 12
        while (at + 8 <= bytes.size) {
            val name = String(bytes, at, 4, Charsets.US_ASCII)
            val size = buffer.getInt(at + 4)
            if (name == "fmt ") byteRate = buffer.getInt(at + 16)
            if (name == "data") {
                data = minOf(size, bytes.size - at - 8)
                break
            }
            at += 8 + size
        }
        if (byteRate <= 0 || data <= 0) throw MusicStore.ImportError("không biết bài dài bao lâu")
        return MusicStore.Tags(data / byteRate.toDouble())
    }
}
