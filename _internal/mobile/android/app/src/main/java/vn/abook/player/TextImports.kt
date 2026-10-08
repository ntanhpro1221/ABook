package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.util.concurrent.ConcurrentHashMap

/**
 * "Thêm sách từ file…" trên điện thoại - phần không dính Android của [LibraryPlugin]: chép thứ người dùng chọn (một file EPUB / DOCX / PDF /
 * TXT, hay một thư mục TXT) vào thư mục tạm của app, đọc nó bằng luật nhập sách ([BookImport]) cho bước xem trước, rồi nhập thành sách
 * chỉ-có-chữ ([TextBook] → [BookFileImport], cùng đường với mọi file sách). Máy tính làm cùng việc ở `webui/textbook.py` + `server.add_text_book`.
 *
 * PDF cần pdf.js nên đi qua WebView: giao diện (ui/src/android/textImport.ts) đọc bản sao PDF đã chép, lấy các dòng của từng trang
 * (ui/src/shared/pdfPages.ts) rồi gọi [preview] với `pages`; luật bỏ tiêu đề chạy / nối đoạn / chia chương là [BookImport.fromPdfPages].
 *
 * Mỗi lần chọn có một `ref` (tên thư mục tạm). Cuốn đã đọc giữ trong bộ nhớ tới khi thêm hay bỏ; app bị giết giữa chừng thì thư mục tạm
 * bị dọn lúc mở lại ([sweep]).
 */
object TextImports {
    private const val MAX_SOURCE_BYTES = 300L shl 20
    private const val MAX_FOLDER_FILES = 5_000
    private val SUPPORTED = setOf("epub", "docx", "pdf", "txt")
    private val UNSAFE = Regex("""[<>:"/\\|?*\u0000-\u001f]""")
    private val kept = ConcurrentHashMap<String, BookImport.Book>()

    /** Bộ chuẩn hoá ảnh bìa của máy (AndroidCoverCodec); không có thì sách không có bìa. */
    @Volatile var codec: CoverCodec? = null

    /** Thứ vừa chép: `ref`, tên hiện cho người dùng, và - nếu là PDF - bản sao để WebView lấy chữ. */
    class Staged(val ref: String, val name: String, val pdf: File?)

    private fun root() = File(Store.root, "imports")

    private fun dir(ref: String): File {
        require(ref.isNotEmpty() && ref.all { it.isLetterOrDigit() && it.code < 128 }) { "mã lần chọn không hợp lệ" }
        return File(root(), ref)
    }

    /** Loại của những file app khác gửi tới ("Mở bằng", chia sẻ) theo kiểu nội dung (AndroidManifest.xml). */
    private val MIME_SUFFIX = mapOf(
        "application/epub+zip" to "epub",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document" to "docx",
        "application/pdf" to "pdf",
        "text/plain" to "txt",
    )

    /**
     * File app khác gửi tới ("Mở bằng ABook", chia sẻ tới ABook): tên để chép vào bước xem trước của "Thêm sách từ file…" nếu nó là
     * EPUB / DOCX / PDF / TXT, hay null khi nó là việc của [BookFileImport] (file sách .abook / .abookproj, hay loại không biết - để
     * đường mở file sách nói lý do). Đuôi của tên hiện đi trước kiểu nội dung (Drive hay gửi EPUB là octet-stream); tên không có
     * đuôi đọc được thì lấy đuôi theo kiểu nội dung.
     */
    fun incomingName(mime: String?, displayName: String?): String? {
        val name = displayName?.substringAfterLast('/')?.trim().orEmpty()
        val suffix = name.substringAfterLast('.', "").lowercase()
        if (suffix == "abook" || suffix == "abookproj") return null
        if (suffix in SUPPORTED) return name
        val kind = MIME_SUFFIX[mime?.substringBefore(';')?.trim()?.lowercase()] ?: return null
        return "${name.ifEmpty { "Sách" }}.$kind"
    }

    /** File sách / dự án của app (.abook, .abookproj - theo đuôi tên, hay kiểu nội dung khi tên mất đuôi): đi đường mở file sách
     *  (BookFileImport), không phải bước xem trước của "Thêm sách từ file…". Cho một nút nhận mọi loại file (soát UX a9). */
    fun isAppBookFile(mime: String?, displayName: String?): Boolean {
        val suffix = displayName?.substringAfterLast('/')?.trim().orEmpty().substringAfterLast('.', "").lowercase()
        if (suffix == "abook" || suffix == "abookproj") return true
        val type = mime?.substringBefore(';')?.trim()?.lowercase()
        return type == BookFileImport.MIMETYPE || type == BookFileImport.PROJECT_MIMETYPE
    }

    /** Dọn mọi thư mục tạm còn sót (app bị giết giữa chừng): bước xem trước đang dở mất theo, người dùng chọn lại. */
    fun sweep() {
        kept.clear()
        root().deleteRecursively()
    }

    /** Tên an toàn cho hệ thống tệp, tối đa 120 ký tự - cắt phần tên chứ không cắt đuôi (tên chương light novel hay dài: cắt mất ".txt"
     *  là file bị bỏ qua không một lời). */
    internal fun safeName(name: String, fallback: String): String {
        val cleaned = UNSAFE.replace(name.substringAfterLast('/').substringAfterLast('\\'), " ").trim(' ', '.').ifEmpty { fallback }
        if (cleaned.length <= 120) return cleaned
        val suffix = BookImport.suffixOf(cleaned).takeIf { it.length <= 10 }.orEmpty()
        return cleaned.substring(0, 120 - suffix.length).trimEnd(' ', '.') + suffix
    }

    /** Hai tên khác nhau thành cùng một tên sau [safeName] (cắt bớt, ký tự lạ): thêm " (2)"… thay vì chép đè mất một chương. */
    internal fun uniqueName(name: String, used: MutableSet<String>): String {
        var candidate = name
        var number = 2
        while (!used.add(candidate.lowercase())) {
            val suffix = BookImport.suffixOf(name)
            candidate = "${name.removeSuffix(suffix)} (${number++})$suffix"
        }
        return candidate
    }

    private fun newRef() = "i" + java.lang.Long.toHexString(System.nanoTime()) + java.lang.Long.toHexString(System.currentTimeMillis())

    private fun copy(source: InputStream, target: File, budget: Long): Long {
        var size = 0L
        target.parentFile?.mkdirs()
        target.outputStream().use { sink ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val read = source.read(buffer)
                if (read < 0) break
                size += read
                if (size > budget) throw BookImport.Failed("File này quá lớn để thêm vào thư viện (tối đa ${MAX_SOURCE_BYTES shr 20} MB).")
                sink.write(buffer, 0, read)
            }
        }
        return size
    }

    /** Chép MỘT file (EPUB / DOCX / PDF / TXT). `open` trả luồng đọc file (content:// của hệ thống). */
    fun stageFile(name: String, open: () -> InputStream?): Staged {
        val clean = safeName(name, "sach")
        val ext = clean.substringAfterLast('.', "").lowercase()
        if (ext !in SUPPORTED) throw BookImport.Failed("Chưa đọc được file ${if (ext.isEmpty()) "không có đuôi" else ".$ext"} - dùng .epub, .docx, .pdf, .txt hay một thư mục TXT")
        val ref = newRef()
        val target = File(dir(ref), clean)
        try {
            val input = open() ?: throw BookImport.Failed("Không đọc được file.")
            input.use { copy(it, target, MAX_SOURCE_BYTES) }
        } catch (error: Exception) {
            dir(ref).deleteRecursively()
            throw error
        }
        return Staged(ref, clean, if (ext == "pdf") target else null)
    }

    /** Chép một thư mục TXT (chỉ các file .txt nằm ngay trong, như Studio): `files` = (tên file, luồng đọc). */
    fun stageFolder(name: String, files: List<Pair<String, () -> InputStream?>>): Staged {
        val texts = files.filter { it.first.lowercase().endsWith(".txt") }
        if (texts.isEmpty()) throw BookImport.Failed("Thư mục này không có file .txt nào nằm ngay bên trong")
        if (texts.size > MAX_FOLDER_FILES) throw BookImport.Failed("Thư mục có quá nhiều file (${texts.size}) - tối đa $MAX_FOLDER_FILES.")
        val ref = newRef()
        val folder = File(dir(ref), safeName(name, "Sách"))
        try {
            var budget = MAX_SOURCE_BYTES
            val used = HashSet<String>()
            for ((fileName, open) in texts) {
                val input = open() ?: continue
                budget -= input.use { copy(it, File(folder, uniqueName(safeName(fileName, "chuong.txt"), used)), budget) }
            }
        } catch (error: Exception) {
            dir(ref).deleteRecursively()
            throw error
        }
        return Staged(ref, folder.name, null)
    }

    /** Thứ đã chép: file duy nhất, hay thư mục TXT. */
    private fun staged(ref: String): File {
        val children = dir(ref).listFiles()?.sortedBy { it.name } ?: throw BookImport.Failed("Lần chọn này đã hết hạn - chọn lại file.")
        return children.singleOrNull() ?: throw BookImport.Failed("Lần chọn này đã hết hạn - chọn lại file.")
    }

    /** Đọc thứ đã chọn bằng luật nhập sách và trả danh sách chương (`textbook.preview`). PDF: `pages` là các dòng từng trang do pdf.js lấy.
     *  `splitChapters`: file TXT cả truyện tách theo "Chương N" - cuốn giữ lại là cuốn của lần xem trước cuối, nên [create] thêm đúng thứ người dùng thấy.
     *  Cuốn giữ lại gồm MỌI hàng của danh sách xem trước (kể cả mục rất ngắn chưa tích); [create] nhận phần người dùng chọn. */
    fun preview(ref: String, pages: List<List<String>>? = null, title: String = "", author: String = "", splitChapters: Boolean = false): JSONObject {
        val source = staged(ref)
        val book = if (source.isFile && source.extension.lowercase() == "pdf") {
            BookImport.fromPdfPages(source.nameWithoutExtension, pages ?: throw BookImport.Failed("Chưa lấy được chữ của PDF này - thử lại."), title, author)
        } else {
            BookImport.importFile(source, splitChapters, keepShort = true)
        }
        kept[ref] = book
        // Đúng bộ chữ này đã có trong thư viện (với các chương mặc định): hỏi ngay ở bước xem trước ("Mở cuốn đó" / "Thêm bản riêng") - như máy
        // tính (`server.preview_text_book`, `textbook.find_existing`).
        val defaults = BookImport.defaultPicks(book)
        val existing = if (defaults.isEmpty()) null else Store.findByChapters(TextBook.prints(BookImport.selectChapters(book, defaults)))
        // Cũng đúng FILE này đã được thêm (chọn chương khác, tách hay không tách): nói ngay, đừng để thành cuốn trùng tên không ai báo
        // (`server.preview_text_book`, `textbook.find_same_source`).
        val same = Store.findBySource(sourceDigest(source))
        return TextBook.preview(book).put("existing", existing?.let { id ->
            JSONObject().put("id", id).put("title", Store.manifest(id)?.optString("title").orEmpty())
        } ?: JSONObject.NULL).put("sameSource", same?.let { id ->
            val shown = Store.manifest(id)
            JSONObject().put("id", id).put("title", shown?.optString("title").orEmpty()).put("chapters", shown?.optInt("chaptersTotal") ?: 0)
        } ?: JSONObject.NULL)
    }

    /** Mã băm của thứ người dùng chọn để thêm sách: nội dung file, hay (thư mục TXT) tên + nội dung từng file theo thứ tự tên (`textbook.source_digest`). */
    private fun sourceDigest(source: File): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256")
        val files = if (source.isDirectory) source.listFiles()!!.sortedBy { it.name } else listOf(source)
        for (file in files.filter { it.isFile }) {
            if (source.isDirectory) digest.update(file.name.toByteArray(Charsets.UTF_8))
            file.inputStream().use { input ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = input.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                }
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /**
     * Nhập thành sách chỉ-có-chữ trong thư viện (`textbook.add_to_library`): ghi file `.abook` tạm trong `cacheDir` rồi [BookFileImport.importFile].
     * `title` trống thì giữ tên của file sách. Trả {id, how, chapters}; `how` "existing" khi đúng cuốn này đã có (nhập lại không nhân đôi),
     * trừ khi người dùng chọn "Thêm bản riêng" (`separate`). `picks`: các chương người dùng tích ở bước xem trước kèm tên mới
     * ([picksOf]); không có thì các chương mặc định.
     */
    fun create(ref: String, title: String, cacheDir: File, separate: Boolean = false, picks: List<Pair<Int, String>>? = null): JSONObject {
        val candidates = kept[ref] ?: throw BookImport.Failed("Lần chọn này đã hết hạn - chọn lại file.")
        val book = BookImport.selectChapters(candidates, picks ?: BookImport.defaultPicks(candidates))
        if (BookEdits.cleanText(title, 160, normalize = false).isNotEmpty()) book.title = title
        val packed = File.createTempFile("text-book-", ".abook", cacheDir)
        try {
            packed.outputStream().use { TextBook.build(book, it, codec) }
            val before = Store.books().map { it.optString("id") }.toSet()
            val imported = BookFileImport.importFile(packed, separate = separate)
            if (imported.id !in before) Store.rememberSource(imported.id, sourceDigest(staged(ref)))
            discard(ref)
            return JSONObject().put("id", imported.id).put("how", if (imported.id in before) "existing" else "new").put("chapters", book.chapters.size)
        } finally {
            packed.delete()
        }
    }

    /** Bỏ thứ tạm của một lần chọn. */
    fun discard(ref: String) {
        kept.remove(ref)
        runCatching { dir(ref).deleteRecursively() }
    }

    /** `chapters` của lời gọi plugin ([{index, title?}], `textbook.picks_from_json`) thành lựa chọn cho [BookImport.selectChapters]; không có là mặc định. */
    fun picksOf(array: JSONArray?): List<Pair<Int, String>>? = array?.let { all ->
        (0 until all.length()).map { number ->
            val item = all.optJSONObject(number)
            val index = (item?.opt("index") as? Number)?.takeIf { it.toDouble() == it.toInt().toDouble() }?.toInt()
            val title = item?.opt("title") ?: ""
            if (index == null || title !is String) throw BookImport.Failed("Danh sách chương đã chọn không hợp lệ")
            index to title
        }
    }

    /** `pages` của lời gọi plugin (mảng các mảng chữ) thành danh sách. */
    fun pagesOf(array: JSONArray?): List<List<String>>? = array?.let { all ->
        (0 until all.length()).map { number ->
            val lines = all.getJSONArray(number)
            (0 until lines.length()).map { lines.getString(it) }
        }
    }
}
