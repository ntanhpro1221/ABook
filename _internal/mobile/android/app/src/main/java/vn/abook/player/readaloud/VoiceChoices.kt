package vn.abook.player.readaloud

import org.json.JSONObject
import java.io.File

/**
 * Giọng "Nghe ngay" người nghe đã chọn, nhớ TRONG LÕI theo từng cuốn VÀ từng hồ sơ nghe (khoá `<mã cuốn>#<mã hồ sơ>`; hồ sơ chưa chọn giọng riêng thì theo giọng mặc định,
 * không kế thừa giọng của hồ sơ trước - soát a105 F4), cộng giọng mặc định (Cài đặt) cho cuốn chưa chọn - cùng luật với
 * `chosenVoice` / `chooseVoice` / `chooseDefaultVoice` của giao diện (listen/readAloudVoice.ts). Giao diện gửi giọng mỗi lần nạp / đổi, nhưng phát tiếp từ widget, xe hơi,
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
    fun voiceFor(bookId: String, recordId: String = ""): String =
        data.optJSONObject("books")?.optString(slot(bookId, recordId), "")?.takeIf { it.isNotBlank() } ?: data.optString("global", "")

    /** Khoá lưu: cuốn + hồ sơ (không biết hồ sơ thì khoá theo cuốn). */
    private fun slot(bookId: String, recordId: String) = if (recordId.isBlank()) bookId else "$bookId#$recordId"

    /** Chọn giọng cho RIÊNG cuốn này - giọng chung giữ nguyên (soát a67); không có cuốn ("") thì là giọng chung. "" (người nghe chưa chọn gì) không
     *  ghi đè lựa chọn đã có. */
    fun remember(bookId: String, voice: String, recordId: String = "") {
        if (voice.isBlank()) return
        if (bookId.isBlank()) {
            data.put("global", voice)
        } else {
            val books = data.optJSONObject("books") ?: JSONObject().also { data.put("books", it) }
            books.put(slot(bookId, recordId), voice)
            // The very first choice also becomes the default, like chooseVoice in the UI.
            if (data.optString("global", "").isBlank()) data.put("global", voice)
        }
        save()
    }

    /** Giọng mặc định đặt ở Cài đặt (giao diện gửi lúc mở app và mỗi lần đổi): "" = chưa đặt, cuốn chưa chọn đọc bằng giọng của người chưa chọn. */
    fun rememberDefault(voice: String) {
        if (voice.isBlank()) data.remove("global") else data.put("global", voice)
        save()
    }

    /** Nhà cung cấp giọng trực tuyến người nghe đã đồng ý gửi chữ tới (giao diện hỏi - listen/onlineConsent.ts - rồi gửi cả danh sách xuống). */
    fun onlineAllowed(provider: String): Boolean =
        data.optJSONArray("onlineOk")?.let { list -> (0 until list.length()).any { list.optString(it) == provider } } == true

    fun allowOnline(providers: List<String>) {
        data.put("onlineOk", org.json.JSONArray(providers.filter { it.isNotBlank() }.distinct()))
        save()
    }

    /** Các nhà cung cấp đã được đồng ý (giao diện native đọc lại để biết hỏi hay không). */
    fun allowedProviders(): List<String> = data.optJSONArray("onlineOk")?.let { list -> (0 until list.length()).map { list.optString(it) } }.orEmpty()

    /** Người nghe bấm đổi giọng (giọng VieNeu không kịp nghe): mọi cuốn đang chọn giọng có mã bắt đầu bằng `fromPrefix`, và giọng chung, chuyển sang `voice` - như `switchVoices` của giao diện. */
    fun replaceVoices(fromPrefix: String, voice: String) {
        data.optJSONObject("books")?.let { books ->
            for (key in books.keys().asSequence().toList()) if (books.optString(key).startsWith(fromPrefix)) books.put(key, voice)
        }
        data.put("global", voice)
        save()
    }

    /**
     * Gốc Nhật / Hàn của cuốn để đọc tên theo luật phiên âm ([Names]): người dùng ghi đè ("ja" / "ko" / "none") thì theo đó, không thì lần máy đoán đã lưu, chưa có thì đoán từ
     * `texts` (các chương đầu) và lưu ở `"origins": {"<mã cuốn>": {"guess", "rule", "override"}}`. Trả "" khi không có gốc.
     */
    @Synchronized
    fun originFor(bookId: String, texts: () -> Sequence<String>): String {
        val entry = origins().optJSONObject(bookId) ?: JSONObject().also { origins().put(bookId, it) }
        val override = entry.optString("override", "")
        if (override == "none") return ""
        if (override in Names.ORIGINS) return override
        var guess = if (entry.optInt("rule", 0) == Names.RULE_VERSION) entry.optString("guess", "") else ""
        if (guess.isEmpty()) {
            guess = Names.bookOrigin(texts()) ?: "none"
            entry.put("guess", guess).put("rule", Names.RULE_VERSION)
            save()
        }
        return if (guess in Names.ORIGINS) guess else ""
    }

    /** Người dùng chọn gốc của cuốn: "ja" / "ko" / "none"; null bỏ ghi đè (theo máy đoán). */
    @Synchronized
    fun setOriginOverride(bookId: String, value: String?) {
        require(value == null || value == "none" || value in Names.ORIGINS) { "gốc phải là ja, ko, none hay bỏ trống" }
        val entry = origins().optJSONObject(bookId) ?: JSONObject().also { origins().put(bookId, it) }
        if (value == null) entry.remove("override") else entry.put("override", value)
        save()
    }

    private fun origins(): JSONObject = data.optJSONObject("origins") ?: JSONObject().also { data.put("origins", it) }

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
