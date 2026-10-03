package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStream
import java.security.MessageDigest

/**
 * Sách CHỈ CÓ CHỮ (giai đoạn 0 của sách nhiều lớp, docs/LISTEN_ANYTHING.md mục 1) - bản Kotlin của `abook/webui/textbook.py`: một cuốn vừa
 * đọc từ EPUB / DOCX / PDF / thư mục TXT ([BookImport]) thành file `.abook` phiên bản 5 - `book.json` với `chapters[i].state` "text" và
 * `chapters[i].text` = `texts/<n>.txt`, chữ từng chương (như FILE NGUỒN mà Studio đọc - [BookImport.chapterSource]), `cover.jpg` nếu
 * file sách có bìa. Ghi bằng [BookDocumentWriter.seal] (cùng bộ ghi với "Lưu thành .abook"), rồi nhập bằng [BookFileImport] như mọi
 * file sách: kiểm cỡ + mã băm, không nhân đôi khi nhập lại, cùng lớp sửa. `book.json` PHẢI ra đúng cùng JSON với bản Python trên bộ ví dụ
 * dùng chung `tests/fixtures/text_books/` (TextBookTest).
 *
 * Chữ KHÔNG bao giờ bị sửa: bộ nhập chỉ đổi định dạng; dòng ghi công chỉ là gợi ý trong [preview].
 */
object TextBook {
    const val TEXT_STATE = "text"
    private const val FORMAT = "abook-book/1"
    private const val COVER_VERSION = 1L

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    /** Tên đã làm sạch như `store.clean_title` (không NFC lại: bộ nhập đã NFC), không có thì `fallback`. */
    private fun cleanTitle(raw: String?, fallback: String): String =
        BookEdits.cleanText(raw.orEmpty(), 160, normalize = false).ifEmpty { fallback }

    /** `book.json` (chưa có mục `package`) của sách chỉ-chữ; `texts` = {tên mục: byte chữ} theo thứ tự chương (`textbook.book_json`). */
    fun bookJson(book: BookImport.Book, texts: Map<String, ByteArray>, cover: CoverCodec.Normalized?): JSONObject {
        val chapters = JSONArray()
        for ((index, name) in texts.keys.withIndex()) {
            val number = index + 1
            val title = cleanTitle(book.chapters[index].title, "Chương $number")
            chapters.put(
                JSONObject().put("id", number).put("index", number).put("title", title).put("subtitle", "").put("fullTitle", title)
                    .put("duration", 0).put("available", false).put("size", 0).put("state", TEXT_STATE).put("text", name),
            )
        }
        val result = JSONObject().put("format", FORMAT).put("title", cleanTitle(book.title, "Sách"))
        book.author?.takeIf { it.isNotEmpty() }?.let { result.put("author", it) }
        book.language?.takeIf { it.isNotEmpty() }?.let { result.put("language", it) }
        val digest = sha256(texts.values.joinToString("") { sha256(it) }.toByteArray(Charsets.UTF_8))
        result.put("narrator", "").put("duration", 0).put("chaptersTotal", chapters.length()).put("chaptersAvailable", 0).put("complete", false)
            .put("version", digest.take(16)).put("chapters", chapters).put("samples", JSONArray())
            .put("cover", cover?.let { JSONObject().put("color", it.color).put("width", it.width.toLong()).put("height", it.height.toLong())
                .put("version", COVER_VERSION).put("file", "cover.jpg") } ?: JSONObject.NULL)
        return result
    }

    /** {tên mục: byte chữ} của các chương, đúng như [build] ghi vào gói (`textbook.texts_of`). */
    fun texts(book: BookImport.Book): LinkedHashMap<String, ByteArray> {
        val texts = LinkedHashMap<String, ByteArray>()
        for ((index, chapter) in book.chapters.withIndex()) texts["texts/${index + 1}.txt"] = BookImport.chapterSource(book, chapter).toByteArray(Charsets.UTF_8)
        return texts
    }

    /** Cỡ + mã băm chữ từng chương - cách thư viện nhận ra cuốn chỉ-chữ ([Store.findByChapters]), để hỏi ngay ở bước xem trước. */
    fun prints(book: BookImport.Book): JSONObject {
        val out = JSONObject()
        for ((name, data) in texts(book)) out.put(name, JSONObject().put("size", data.size.toLong()).put("sha256", sha256(data)))
        return out
    }

    /**
     * Ghi cuốn thành file `.abook` chỉ-chữ vào `out` (`textbook.build`). `codec` chuẩn hoá ảnh bìa; ảnh hỏng hay quá nhỏ thì bỏ bìa, sách vẫn
     * nhập được. Trả [BookDocumentWriter.Written].
     */
    fun build(book: BookImport.Book, out: OutputStream, codec: CoverCodec? = null): BookDocumentWriter.Written {
        val texts = texts(book)
        val files = LinkedHashMap<String, Any>(texts)
        var cover: CoverCodec.Normalized? = null
        val raw = book.cover
        if (raw != null && codec != null) {
            cover = try {
                codec.normalize(raw)
            } catch (error: CoverCodec.CoverError) {
                null // bìa hỏng hay quá nhỏ: sách vẫn nhập được, giao diện tự vẽ bìa từ tên
            }
            cover?.let { files["cover.jpg"] = it.jpeg }
        }
        return BookDocumentWriter.seal(bookJson(book, texts, cover), files, emptyMap(), BookEdits.empty(), 5, out)
    }

    /**
     * Danh sách chương cho bước xem trước (`textbook.preview`): tên, dòng đầu, số chữ, số ký tự. `notes` là gợi ý - hiện ra, không tự áp.
     */
    fun preview(book: BookImport.Book): JSONObject {
        val rows = JSONArray()
        var words = 0
        for ((index, chapter) in book.chapters.withIndex()) {
            val source = BookImport.chapterSource(book, chapter)
            val count = BookImport.wordCount(source)
            words += count
            val first = source.lines().map { it.trim { c -> c.isWhitespace() || Character.isSpaceChar(c) } }.firstOrNull { it.isNotEmpty() }.orEmpty()
            rows.put(
                JSONObject().put("index", index + 1).put("title", cleanTitle(chapter.title, "Chương ${index + 1}"))
                    .put("firstLine", BookEdits.cut(first, 200)).put("words", count).put("chars", BookImport.charCount(source)),
            )
        }
        return JSONObject().put("title", cleanTitle(book.title, "Sách")).put("author", book.author ?: JSONObject.NULL)
            .put("language", book.language ?: JSONObject.NULL).put("hasCover", book.cover != null).put("chapters", rows)
            .put("notes", JSONArray(book.notes))
            // Gợi ý chọn được: dòng ghi công người nghe có thể bỏ khỏi phần đọc (mặc định KHÔNG bỏ). `chapter` = mã chương trong sách.
            .put("suggestions", JSONArray(book.credits.map { (chapter, line) -> JSONObject().put("chapter", chapter).put("line", line) }))
            .put("totals", JSONObject().put("chapters", rows.length()).put("words", words))
            // File TXT cả truyện: số chương nếu tách theo "Chương N" - giao diện đề xuất (ô KHÔNG tích sẵn). Không có gì để tách thì không có khoá.
            .also { if (book.splitOffer > 0) it.put("splitOffer", book.splitOffer) }
    }
}
