package vn.abook.player

import org.json.JSONObject

/**
 * "Studio" nhẹ trên điện thoại: máy chủ giao diện của máy tính (abook/webui/server.py) trả lời `/api/books/<mã>/...` còn điện
 * thoại thì không có máy chủ - giao diện gọi `EbookLibrary.studio({method, path, body})` và nhận đúng JSON máy chủ sẽ trả
 * (docs/EDITING.md, bảng "Routes"). Chỉ phần L ("áp ngay", không cần Studio) cho cuốn mở từ file `.abook`: đổi tên sách, bìa,
 * tên nhân vật, tên chương, nhạc nền, xem/bỏ thay đổi. Mọi thứ khác: 404. Cuốn lấy từ máy tính khác thì sửa ở máy ấy: 409.
 *
 * Lời đáp phải y hệt bản Python (tests/fixtures/book_edits/contract/ - LocalStudioTest phát lại từng bước), nên câu báo lỗi
 * và mã trạng thái theo đúng server.py: sửa sai (ValueError bên Python) là 400.
 */
object LocalStudio {
    private class Api(val status: Int, message: String) : Exception(message)

    private val ROUTE = Regex("/api/books/([A-Za-z0-9_-]+)(/[^?#]*)?")
    private val CHAPTER_TITLE = Regex("/chapters/([0-9]+)/title")
    private val CHAPTER_SCRIPT = Regex("/chapters/([0-9]+)/script")
    private val EDITS_ONLY_KEYS = setOf("enabled", "levelDb", "silence")
    private val lock = Any()

    /** Bộ chuẩn hoá ảnh bìa: máy thật dùng [AndroidCoverCodec]; test JVM đặt bản giả. */
    @Volatile
    var coverCodec: CoverCodec? = null

    /** Đồng hồ (giây) - làm số phiên bản cho bìa; test đặt số cố định. */
    @Volatile
    var clock: () -> Long = { System.currentTimeMillis() / 1000 }

    fun handle(method: String, path: String, body: JSONObject?): Pair<Int, Any?> = try {
        run(method.uppercase(), path, body ?: JSONObject())
    } catch (error: Api) {
        error.status to fail(error.message.orEmpty())
    } catch (error: BookEdits.EditsError) {
        400 to fail(error.message.orEmpty())
    }

    private fun fail(message: String): JSONObject = JSONObject().put("error", message)

    private fun run(method: String, path: String, body: JSONObject): Pair<Int, Any?> {
        val match = ROUTE.matchEntire(path) ?: throw Api(404, "Không có đường dẫn này")
        val id = match.groupValues[1]
        val rest = match.groupValues[2]
        val handler = route(method, rest) ?: throw Api(404, "Không có đường dẫn này")
        val dir = editable(id)
        // Mỗi cuốn một lần sửa một lúc: đọc-sửa-ghi của hai yêu cầu không được chen nhau.
        return synchronized(lock) { 200 to handler(dir, body) }
    }

    /** Thư mục cuốn nhập từ file mà người nghe sửa được; không có thì 404, cuốn lấy từ máy tính thì 409. */
    private fun editable(id: String): java.io.File {
        val raw = Store.rawManifest(id) ?: throw Api(404, "Không tìm thấy sách này trong thư viện")
        if (Store.isComputerBook(id) || raw.optString("source").isNotEmpty() || raw.optJSONObject("package") == null) {
            throw Api(409, "Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy")
        }
        return Store.bookDir(id)
    }

    private fun route(method: String, path: String): ((java.io.File, JSONObject) -> Any?)? {
        CHAPTER_TITLE.matchEntire(path)?.takeIf { method == "PUT" }?.let { match -> return { dir, body -> chapterTitle(dir, match.groupValues[1], body) } }
        CHAPTER_SCRIPT.matchEntire(path)?.takeIf { method == "GET" }?.let { match -> return { dir, _ -> script(dir, match.groupValues[1]) } }
        return when (method to path) {
            "PUT" to "/title" -> ::title
            "PUT" to "/cover" -> ::cover
            "DELETE" to "/cover" -> { dir, _ -> BookEdits.removeCover(dir); JSONObject().put("cover", JSONObject.NULL) }
            "POST" to "/characters/rename" -> ::renameCharacter
            "GET" to "/music" -> { dir, _ -> BookEdits.musicView(BookEdits.rawBook(dir), BookEdits.load(dir)) }
            "PUT" to "/music" -> ::music
            "GET" to "/edits" -> { dir, _ -> JSONObject().put("applied", BookEdits.count(BookEdits.load(dir))).put("waiting", 0) }
            "DELETE" to "/edits" -> { dir, _ -> BookEdits.clear(dir); JSONObject().put("applied", 0).put("waiting", 0) }
            "GET" to "/cast" -> { dir, _ -> BookEdits.cast(dir, BookEdits.rawBook(dir)) }
            else -> null
        }
    }

    /** PUT /title {title}: `App.rename` - làm sạch như `store.clean_title` rồi lớp sửa ghi lại (NFC) hay bỏ khi đúng tên sách. */
    private fun title(dir: java.io.File, body: JSONObject): Any? {
        val cleaned = BookEdits.cleanText(BookEdits.pyText(body.opt("title")), BookEdits.TITLE_MAX, normalize = false)
        if (cleaned.isEmpty()) throw BookEdits.EditsError("Tên sách không được để trống")
        return JSONObject().put("title", BookEdits.setTitle(dir, cleaned))
    }

    /** PUT /cover {image: data URL}: bìa người nghe đặt nằm ở edits/cover.jpg, bìa của sách giữ nguyên. */
    private fun cover(dir: java.io.File, body: JSONObject): Any? {
        if (BookEdits.truthy(body.opt("url"))) throw BookEdits.EditsError("Điện thoại chưa tải bìa từ địa chỉ mạng - hãy chọn ảnh có sẵn trong máy")
        val raw = try {
            Covers.decodeDataUrl(BookEdits.pyText(body.opt("image")))
        } catch (error: CoverCodec.CoverError) {
            throw BookEdits.EditsError(error.message.orEmpty())
        }
        val codec = coverCodec ?: AndroidCoverCodec
        return JSONObject().put("cover", BookEdits.setCover(dir, raw, clock(), codec))
    }

    /** POST /characters/rename {character, name}. */
    private fun renameCharacter(dir: java.io.File, body: JSONObject): Any? {
        val character = BookEdits.pyStrip(BookEdits.pyStr(if (body.has("character")) body.opt("character") else "")).let {
            if (it.codePointCount(0, it.length) > 200) it.substring(0, it.offsetByCodePoints(0, 200)) else it
        }
        if (character.isEmpty() || character.uppercase(java.util.Locale.ROOT) == "NARRATOR") throw BookEdits.EditsError("Thiếu nhân vật")
        return BookEdits.setCharacterName(dir, character, BookEdits.pyStr(if (body.has("name")) body.opt("name") else ""))
    }

    /** PUT /chapters/<n>/title {title?, subtitle?, revert?}. */
    private fun chapterTitle(dir: java.io.File, chapter: String, body: JSONObject): Any? {
        val revert = BookEdits.truthy(body.opt("revert"))
        val title = if (revert) null else body.opt("title")
        val subtitle = if (revert) null else body.opt("subtitle")
        fun text(value: Any?): String? = when {
            value == null || value === JSONObject.NULL -> null
            value is String -> value
            else -> throw BookEdits.EditsError("Tên chương phải là chữ")
        }
        val (newTitle, newSubtitle) = text(title) to text(subtitle)
        return BookEdits.setChapterTitle(dir, chapter.toLongOrNull() ?: throw BookEdits.EditsError("Không có chương này trong sách"), newTitle, newSubtitle)
    }

    /** PUT /music {enabled?, levelDb?, silence?}: sách đã đóng gói chỉ chỉnh được ba thứ ấy. */
    private fun music(dir: java.io.File, body: JSONObject): Any? {
        if (body.keys().asSequence().any { it !in EDITS_ONLY_KEYS }) {
            throw BookEdits.EditsError("Sách đã đóng gói chỉ chỉnh được bật/tắt nhạc, mức nhạc và im lặng từng đoạn")
        }
        return BookEdits.setMusic(dir, body)
    }

    /** GET /chapters/<n>/script: chữ đọc theo đã qua lớp sửa. */
    private fun script(dir: java.io.File, chapter: String): Any? =
        chapter.toLongOrNull()?.let { BookEdits.script(dir, BookEdits.rawBook(dir), it) } ?: throw Api(404, "Không có chương này")
}
