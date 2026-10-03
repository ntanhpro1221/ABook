package vn.abook.player.readaloud

import java.io.File

/**
 * Một đoạn âm thanh đọc to: MỘT đoạn chữ thành một file ở tốc độ 1.0, kèm mốc từng chữ (`words`: một [bắt đầu, kết thúc] ms cho mỗi chữ `\S+`, từ đầu đoạn) và
 * độ dài. Đổi tốc độ nghe bằng tốc độ phát của trình phát, không bao giờ đọc lại.
 */
class Clip(val file: File, val durationMs: Long, val words: List<Span>, val voice: String)

/**
 * Giọng đọc không dùng được lúc này (hết mạng, thiếu giọng tiếng Việt, quá hạn...). `message` là câu nói thẳng cho người nghe. `reason` như bên máy tính
 * (abook/readaloud/model.py): "offline", "auth" (khoá của người dùng sai / bị khoá), "quota" (hết hạn mức), "service"... - [ClipReader] dựa vào đó để chọn giọng đỡ.
 */
class VoiceException(message: String, val offline: Boolean = false, cause: Throwable? = null, val reason: String = if (offline) "offline" else "service") :
    Exception(message, cause)

/** Một giọng: đổi MỘT đoạn chữ thành file âm thanh (chặn tới khi xong hay hỏng; chạy ở luồng nền). */
interface Voice {
    /** "edge:vi-VN-HoaiMyNeural" / "device:<tên giọng Android>". */
    val id: String
    /** Đuôi file âm thanh nó ghi ("mp3" / "wav"). */
    val extension: String
    /** Ghi âm thanh của `text` vào `out`, trả độ dài + mốc từng chữ (`words` theo `text`). */
    fun synthesize(text: String, out: File): Clip
    /** Như trên cho cuốn có gốc Nhật / Hàn ([Names]): giọng đọc trên máy (VieNeu) đọc tên theo luật phiên âm, giọng khác bỏ qua `origin`. */
    fun synthesize(text: String, out: File, origin: String?): Clip = synthesize(text, out)
}

/** Một giọng cho người dùng chọn (plugin `voices()`). `gender`: "female" / "male" / "" - gợi ý trong Cài đặt. */
data class VoiceInfo(val id: String, val name: String, val provider: String, val online: Boolean, val default: Boolean, val gender: String = "")

/** Cắt một đoạn quá dài thành các mảnh mà giọng nhận được (Edge 4096 byte một lần, Android `getMaxSpeechInputLength`). */
object TextChunks {
    /** (vị trí đầu mảnh trong chữ gốc, mảnh). Cắt ở dấu cách cuối cùng còn vừa `limit` (tính bằng `weight` mỗi ký tự); không có dấu cách thì cắt cứng. */
    fun split(text: String, limit: Int, weight: (Char) -> Int = { 1 }): List<Pair<Int, String>> {
        val parts = ArrayList<Pair<Int, String>>()
        var from = 0
        while (from < text.length) {
            var used = 0
            var cut = from
            var lastSpace = -1
            while (cut < text.length) {
                val w = weight(text[cut])
                if (used + w > limit && cut > from) break
                used += w
                if (text[cut] == ' ') lastSpace = cut
                cut += 1
            }
            if (cut < text.length && lastSpace > from) cut = lastSpace + 1
            parts.add(from to text.substring(from, cut))
            from = cut
        }
        return parts.filter { it.second.isNotBlank() }
    }
}
