package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.InputStream
import java.util.concurrent.ConcurrentHashMap

/**
 * "Thêm sách từ file…" trên điện thoại - phần không dính Android: chép thứ người dùng chọn (một file EPUB / DOCX / PDF /
 * TXT, hay một thư mục TXT) vào thư mục tạm của app, đọc nó bằng luật nhập sách ([BookImport]) cho bước xem trước, rồi nhập thành sách
 * chỉ-có-chữ ([TextBook] → [BookFileImport], cùng đường với mọi file sách). Máy tính làm cùng việc ở `webui/textbook.py` + `server.add_text_book`.
 *
 * PDF: giao diện (`ui.addbook.ImportRepo.readPdf`, PdfRenderer của Android 15+) đọc bản sao PDF đã chép, lấy các dòng của từng trang
 * rồi gọi [preview] với `pages`; luật bỏ tiêu đề chạy / nối đoạn / chia chương là [BookImport.fromPdfPages].
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
    private const val FOLDER_NAMES = ".abook-import-names.json"

    private fun originalNames(source: File): Map<String, String> {
        val file = File(source, FOLDER_NAMES)
        if (!source.isDirectory || !file.isFile) return emptyMap()
        val names = JSONObject(file.readText(Charsets.UTF_8))
        return names.keys().asSequence().associateWith { names.getString(it) }
    }

    /** Bộ chuẩn hoá ảnh bìa của máy (AndroidCoverCodec); không có thì sách không có bìa. */
    @Volatile var codec: CoverCodec? = null

    /** Thứ vừa chép: `ref`, tên hiện cho người dùng, và - nếu là PDF - bản sao để giao diện lấy chữ. */
    class Staged(val ref: String, val name: String, val pdf: File?)

    private fun root() = File(Store.root, "imports")

    private fun dir(ref: String): File {
        require(ref.isNotEmpty() && ref.all { it.isLetterOrDigit() && it.code < 128 }) { S.s_ma_lan_chon_khong_hop_le_9a254152 }
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
        return S.s_0_1_0adfdd23(name.ifEmpty { S.s_sach_0c2b3e9b }, kind)
    }

    /**
     * File được CHIA SẺ tới app qua kiểu nội dung "chung" (octet-stream, zip - nơi gửi đặt cho mọi file lạ; AndroidManifest nhận hai kiểu ấy cho `.abook`):
     * lời báo nếu nó không phải thứ app nhận được, null nếu cứ đi tiếp. Nhận được: tên có đuôi .abook / .abookproj, EPUB / DOCX / PDF / TXT theo đuôi, hay đầu
     * file đúng dáng gói của app ([BookFileImport.looksLikeBookFile]; `head` chỉ được gọi khi tên chưa đủ để quyết). Kiểu nội dung khác không thuộc việc này.
     */
    fun refuseShared(mime: String?, displayName: String?, head: () -> ByteArray?): String? {
        val type = mime?.substringBefore(';')?.trim()?.lowercase()
        if (type != "application/octet-stream" && type != "application/zip") return null
        if (incomingName(mime, displayName) != null || isAppBookFile(mime, displayName)) return null
        if (BookFileImport.looksLikeBookFile(head() ?: ByteArray(0))) return null
        return S.s_ban_chon_abook_abookproj_epub_word_pdf_hoa_edd3723c
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

    private fun copy(source: InputStream, target: File, budget: Long, counted: (Long) -> Unit = {}): Long {
        var size = 0L
        target.parentFile?.mkdirs()
        target.outputStream().use { sink ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val read = source.read(buffer)
                if (read < 0) break
                size += read
                if (size > budget) throw BookImport.Failed(S.s_file_nay_qua_lon_de_them_vao_thu_vien_toi_c51dc582(MAX_SOURCE_BYTES shr 20))
                sink.write(buffer, 0, read)
                counted(size)
            }
        }
        return size
    }

    /** Phần của thanh dành cho bước chép file chữ vào máy; phần còn lại là bước đọc (tách chương, lấy chữ PDF). */
    const val STAGE_SHARE = 0.7f

    /**
     * Chép MỘT file (EPUB / DOCX / PDF / TXT). `open` trả luồng đọc file (content:// của hệ thống). `progress`: byte đã chép / `total`
     * (cỡ file theo hệ thống; <= 0 = chưa biết, thanh chạy liên tục), chiếm [0, [STAGE_SHARE]] của thanh.
     */
    fun stageFile(name: String, total: Long = 0, progress: WorkSink = {}, open: () -> InputStream?): Staged {
        val clean = safeName(name, "sach")
        val ext = clean.substringAfterLast('.', "").lowercase()
        if (ext !in SUPPORTED) throw BookImport.Failed(S.s_chua_doc_duoc_file_0_dung_epub_docx_pdf_tx_1a70d200(if (ext.isEmpty()) S.s_khong_co_duoi_178f5d10 else ".$ext"))
        val ref = newRef()
        val target = File(dir(ref), clean)
        try {
            val input = open() ?: throw BookImport.Failed(S.s_chua_doc_duoc_file_6575d76b)
            progress(Work(WorkStep.Copy, 0, total, 0f, STAGE_SHARE))
            input.use { copy(it, target, MAX_SOURCE_BYTES) { done -> progress(copyWork(done, total, STAGE_SHARE)) } }
        } catch (error: Exception) {
            dir(ref).deleteRecursively()
            throw error
        }
        return Staged(ref, clean, if (ext == "pdf") target else null)
    }

    /** Chép một thư mục TXT (chỉ các file .txt nằm ngay trong, như Studio): `files` = (tên file, luồng đọc). `progress`: số file đã chép / tổng. */
    fun stageFolder(name: String, files: List<Pair<String, () -> InputStream?>>, progress: WorkSink = {}): Staged {
        val texts = files.filter { it.first.lowercase().endsWith(".txt") }
        if (texts.isEmpty()) throw BookImport.Failed(S.s_thu_muc_nay_khong_co_file_txt_nao_nam_ngay_ba76d525)
        if (texts.size > MAX_FOLDER_FILES) throw BookImport.Failed(S.s_thu_muc_co_qua_nhieu_file_0_toi_da_1_842b73bc(texts.size, MAX_FOLDER_FILES))
        val ref = newRef()
        val folder = File(dir(ref), safeName(name, S.s_sach_0c2b3e9b))
        try {
            var budget = MAX_SOURCE_BYTES
            val used = HashSet<String>()
            val names = JSONObject()
            for ((index, pair) in texts.withIndex()) {
                val (fileName, open) = pair
                progress(Work(WorkStep.Copy, index.toLong(), texts.size.toLong(), 0f, STAGE_SHARE, bytes = false))
                try {
                    val input = open() ?: throw BookImport.Failed(S.s_chua_mo_duoc_file_8895249d)
                    val diskName = uniqueName(safeName(fileName, "chuong.txt"), used)
                    budget -= input.use { copy(it, File(folder, diskName), budget) }
                    names.put(diskName, fileName)
                } catch (error: Exception) {
                    throw BookImport.Failed(S.s_chua_doc_duoc_0_ban_kiem_tra_quyen_doc_va_9145df31(fileName))
                }
            }
            progress(Work(WorkStep.Copy, texts.size.toLong(), texts.size.toLong(), 0f, STAGE_SHARE, bytes = false))
            File(folder, FOLDER_NAMES).writeText(names.toString(), Charsets.UTF_8)
        } catch (error: Exception) {
            dir(ref).deleteRecursively()
            throw error
        }
        return Staged(ref, folder.name, null)
    }

    /** Thứ đã chép: file duy nhất, hay thư mục TXT. */
    private fun staged(ref: String): File {
        val children = dir(ref).listFiles()?.sortedBy { it.name } ?: throw BookImport.Failed(S.s_lan_chon_nay_da_het_han_chon_lai_file_fece2ec0)
        return children.singleOrNull() ?: throw BookImport.Failed(S.s_lan_chon_nay_da_het_han_chon_lai_file_fece2ec0)
    }

    /** Đọc thứ đã chọn bằng luật nhập sách và trả danh sách chương (`textbook.preview`). PDF: `pages` là các dòng từng trang do lớp giao diện lấy.
     *  `splitChapters`: file TXT cả truyện tách theo "Chương N" - cuốn giữ lại là cuốn của lần xem trước cuối, nên [create] thêm đúng thứ người dùng thấy.
     *  Cuốn giữ lại gồm MỌI hàng của danh sách xem trước (kể cả mục rất ngắn chưa tích); [create] nhận phần người dùng chọn.
     *  `footnotes`: EPUB / DOCX có chú thích - đề xuất người dùng đã tích ([BookImport.footnoteChoiceFromJson]); cuốn giữ lại theo đúng lựa chọn của lần xem trước cuối. */
    fun preview(
        ref: String, pages: List<List<String>>? = null, title: String = "", author: String = "", splitChapters: Boolean = false,
        footnotes: BookImport.FootnoteChoice? = null,
    ): JSONObject {
        val book = prepare(ref, pages, title, author, splitChapters, footnotes)
        val source = staged(ref)
        // JSON is only the adapter for the existing web client. Native callers use prepare directly.
        val defaults = BookImport.defaultPicks(book)
        val existing = if (defaults.isEmpty()) null else Store.findByChapters(TextBook.prints(BookImport.selectChapters(book, defaults)))
        val same = Store.findBySource(sourceDigest(source))
        return TextBook.preview(book).put("existing", existing?.let { id ->
            JSONObject().put("id", id).put("title", Store.manifest(id)?.optString("title").orEmpty())
        } ?: JSONObject.NULL).put("sameSource", same?.let { id ->
            val shown = Store.manifest(id)
            JSONObject().put("id", id).put("title", shown?.optString("title").orEmpty()).put("chapters", shown?.optInt("chaptersTotal") ?: 0)
        } ?: JSONObject.NULL)
    }

    /** Typed entry for native UI; callers own the I/O dispatcher. No serialization of chapter text. */
    fun prepare(
        ref: String, pages: List<List<String>>? = null, title: String = "", author: String = "", splitChapters: Boolean = false,
        footnotes: BookImport.FootnoteChoice? = null,
    ): BookImport.Book {
        val source = staged(ref)
        val book = if (source.isFile && source.extension.lowercase() == "pdf") {
            BookImport.fromPdfPages(source.nameWithoutExtension, pages ?: throw BookImport.Failed(S.s_chua_lay_duoc_chu_cua_pdf_nay_thu_lai_b245b159), title, author)
        } else {
            BookImport.importFile(source, splitChapters, keepShort = true, footnotes = footnotes, originalNames = originalNames(source))
        }
        kept[ref] = book
        return book
    }

    fun sameSource(ref: String): String? = Store.findBySource(sourceDigest(staged(ref)))

    /** Mã băm của thứ người dùng chọn để thêm sách: nội dung file, hay (thư mục TXT) tên + nội dung từng file theo thứ tự tên (`textbook.source_digest`). */
    private fun sourceDigest(source: File): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256")
        val names = originalNames(source)
        val files = if (source.isDirectory) source.listFiles()!!.filter { it.name != FOLDER_NAMES }.sortedBy { names[it.name] ?: it.name } else listOf(source)
        for (file in files.filter { it.isFile }) {
            if (source.isDirectory) digest.update((names[file.name] ?: file.name).toByteArray(Charsets.UTF_8))
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
        val result = createBook(ref, title, cacheDir, separate, picks)
        return JSONObject().put("id", result.id).put("how", result.how).put("chapters", result.chapters)
    }

    data class Created(val id: String, val how: String, val chapters: Int)

    fun createBook(ref: String, title: String, cacheDir: File, separate: Boolean = false, picks: List<Pair<Int, String>>? = null): Created {
        val candidates = kept[ref] ?: throw BookImport.Failed(S.s_lan_chon_nay_da_het_han_chon_lai_file_fece2ec0)
        val book = BookImport.selectChapters(candidates, picks ?: BookImport.defaultPicks(candidates))
        if (BookEdits.cleanText(title, 160, normalize = false).isNotEmpty()) book.title = title
        val packed = File.createTempFile("text-book-", ".abook", cacheDir)
        try {
            packed.outputStream().use { TextBook.build(book, it, codec) }
            val before = Store.books().map { it.optString("id") }.toSet()
            // Repeating an EPUB/TXT pick keeps the existing book; opening an exported .abook refreshes its base layer.
            val imported = BookFileImport.importFile(packed, separate = separate, refreshBase = false)
            if (imported.id !in before) Store.rememberSource(imported.id, sourceDigest(staged(ref)))
            discard(ref)
            return Created(imported.id, if (imported.id in before) "existing" else "new", book.chapters.size)
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
            if (index == null || title !is String) throw BookImport.Failed(S.s_danh_sach_chuong_da_chon_khong_hop_le_ccef4036)
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
