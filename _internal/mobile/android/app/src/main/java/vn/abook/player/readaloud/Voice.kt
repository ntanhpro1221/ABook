package vn.abook.player.readaloud

import java.io.File

/**
 * Một đoạn âm thanh đọc to: MỘT đoạn chữ thành một file ở tốc độ 1.0, kèm mốc từng chữ (`words`: một [bắt đầu, kết thúc] ms cho mỗi chữ `\S+`, từ đầu đoạn) và
 * độ dài. Đổi tốc độ nghe bằng tốc độ phát của trình phát, không bao giờ đọc lại. `fromWord` > 0: CLIP ĐUÔI (uxfix57) - người nghe bấm giữa đoạn chưa đọc nên chỉ đọc từ chữ thứ `fromWord` tới hết đoạn;
 * `words` vẫn đủ chữ của đoạn (chữ trước `fromWord` mốc [0, 0]) và âm thanh bắt đầu từ chữ `fromWord`: chỉ dùng khi chỗ nghe nằm trong nó ([SeekPlan]).
 */
class Clip(val file: File, val durationMs: Long, val words: List<Span>, val voice: String, val fromWord: Int = 0)

/**
 * Giọng đọc không dùng được lúc này (hết mạng, thiếu giọng tiếng Việt, quá hạn...). `message` là câu nói thẳng cho người nghe. `reason` như bên máy tính
 * (abook/readaloud/model.py): "offline", "auth" (khoá của người dùng sai / bị khoá), "quota" (hết hạn mức), "service", "timeout"... - [ClipReader] dựa vào đó để chọn giọng đỡ.
 * `final`: lời cuối của [ClipReader] (đã thử hết giọng, hay giọng đang nghỉ) - người gọi không thử lại thêm.
 */
class VoiceException(
    message: String, val offline: Boolean = false, cause: Throwable? = null, val reason: String = if (offline) "offline" else "service", val final: Boolean = false,
) : Exception(message, cause) {
    /** Lỗi thoáng qua (Edge cắt lượt / bận / chậm - "service", "timeout"): thử lại là xong. Mất mạng, bị từ chối, khoá / giọng hỏng thì không. */
    val transient: Boolean get() = !final && !offline && reason in TRANSIENT_REASONS

    companion object {
        val TRANSIENT_REASONS = setOf("service", "timeout")
    }
}

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
    /**
     * Như trên với cách đọc riêng người nghe đặt cho cuốn ([Readings]): giọng nhận chữ đem đọc đã thay ([Readings.spokenLayout]; chữ hiện cuối một cụm đọc ngắn hơn
     * mất khỏi chuỗi nên `words` được [Readings.expandWords] về đủ chữ hiện); giọng trên máy (VieNeu, Supertonic) áp trong `VieneuUnits.spokenTokens`, sau bước đọc tên;
     * giọng nhận chữ đã chuẩn hoá ([SpokenText.normalises]: Edge) nhận chữ của `VieneuUnits.spokenTokens` luôn cả cách đọc riêng ([SpokenText.layout]).
     */
    fun synthesize(text: String, out: File, origin: String?, readings: Map<String, String>?): Clip {
        if (SpokenText.normalises(id)) { // Edge: đúng chữ giọng trên máy nhận (tên, tiếng kêu, số, ký hiệu, viết tắt + cách đọc riêng), mốc về đủ chữ hiện
            val (said, spans) = SpokenText.layout(text, origin, readings)
            // Clip phát luồng ([LiveClips]): mốc chữ tạm cũng về đủ chữ hiện như mốc cuối.
            val clip = LiveClips.expanding({ SpokenText.expandWords(it, spans) }) { synthesize(said, out) }
            return Clip(clip.file, clip.durationMs, SpokenText.expandWords(clip.words, spans), clip.voice)
        }
        if (readings.isNullOrEmpty()) return synthesize(text, out, origin)
        val (said, slots) = Readings.spokenLayout(text, readings)
        val clip = synthesize(said, out, origin)
        return Clip(clip.file, clip.durationMs, Readings.expandWords(clip.words, slots), clip.voice)
    }
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
