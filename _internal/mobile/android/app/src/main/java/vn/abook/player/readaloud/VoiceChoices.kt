package vn.abook.player.readaloud

import org.json.JSONObject
import java.io.File

/**
 * Giọng "Nghe ngay" người nghe đã chọn, nhớ TRONG LÕI theo từng cuốn, cộng một lựa chọn chung cho cuốn chưa chọn - cùng luật với
 * `chosenVoice` / `chooseVoice` của giao diện (listen/readAloudVoice.ts). Giao diện gửi giọng mỗi lần nạp / đổi, nhưng phát tiếp từ widget, xe hơi,
 * tai nghe hay máy tính điều khiển sau khi app khởi động lại thì không qua giao diện - trước đây những đường ấy đọc bằng giọng mặc định.
 *
 * Một file JSON nhỏ `{"global": "...", "books": {"<mã cuốn>": "..."}, "onlineOk": ["edge", ...]}`; ghi qua file tạm rồi đổi tên. File hỏng / thiếu: như chưa chọn gì.
 */
class VoiceChoices(private val file: File) {
    private var data: JSONObject = load()

    private fun load(): JSONObject = try {
        if (file.isFile) JSONObject(file.readText(Charsets.UTF_8)) else JSONObject()
    } catch (_: Exception) {
        JSONObject()
    }

    /** Giọng của cuốn này; chưa chọn thì giọng chung; chưa có gì thì "" (= giọng mặc định). */
    fun voiceFor(bookId: String): String =
        data.optJSONObject("books")?.optString(bookId, "")?.takeIf { it.isNotBlank() } ?: data.optString("global", "")

    /** Chọn giọng cho cuốn (và làm giọng chung cho cuốn khác chưa chọn). "" (người nghe chưa chọn gì) không ghi đè lựa chọn đã có. */
    fun remember(bookId: String, voice: String) {
        if (voice.isBlank()) return
        if (bookId.isNotBlank()) {
            val books = data.optJSONObject("books") ?: JSONObject().also { data.put("books", it) }
            books.put(bookId, voice)
        }
        data.put("global", voice)
        save()
    }

    /** Nhà cung cấp giọng trực tuyến người nghe đã đồng ý gửi chữ tới (giao diện hỏi - listen/onlineConsent.ts - rồi gửi cả danh sách xuống). */
    fun onlineAllowed(provider: String): Boolean =
        data.optJSONArray("onlineOk")?.let { list -> (0 until list.length()).any { list.optString(it) == provider } } == true

    fun allowOnline(providers: List<String>) {
        data.put("onlineOk", org.json.JSONArray(providers.filter { it.isNotBlank() }.distinct()))
        save()
    }

    private fun save() {
        try {
            file.parentFile?.mkdirs()
            val tmp = File(file.parentFile, "${file.name}.tmp")
            tmp.writeText(data.toString(), Charsets.UTF_8)
            if (!tmp.renameTo(file)) {
                file.delete()
                tmp.renameTo(file)
            }
        } catch (_: Exception) {
            // không ghi được thì lần sau dùng giọng chung / mặc định - không chặn việc phát
        }
    }
}
