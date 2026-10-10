package vn.abook.player

import java.io.File
import java.io.IOException
import java.math.BigInteger
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.Charset
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest
import java.text.Normalizer
import java.util.regex.Pattern
import java.util.zip.ZipException
import java.util.zip.ZipFile

/**
 * Nhập sách từ file người dùng có sẵn: thư mục TXT, EPUB, DOCX, và PDF có lớp chữ (docs/LISTEN_ANYTHING.md, mục 2). Bản Kotlin của
 * `abook/importers.py`: CÙNG luật, cùng câu chữ của ghi chú, và PHẢI ra đúng cùng một kết quả trên bộ ví dụ dùng chung
 * `tests/fixtures/import/` (BookImportTest). Sửa luật ở một bên thì sửa bên kia và sinh lại bộ ví dụ.
 *
 * Luật của chủ sách: không bao giờ tự sửa chữ của truyện - chỉ ĐỔI ĐỊNH DẠNG (bỏ thẻ, gộp khoảng trắng, nối dòng PDF thành đoạn,
 * Unicode NFC). Dòng ghi công của người dịch KHÔNG bị bỏ: nó nằm trong `notes` như một gợi ý.
 *
 * Không thư viện ngoài: java.util.zip + một bộ tách thẻ nhỏ (`Markup`) chịu được XHTML của EPUB (&nbsp; và các thực thể HTML,
 * không phải XML chặt nên XmlPullParser sẽ từ chối), và chạy được trong test JVM (android.jar chỉ có vỏ rỗng của XmlPullParser).
 * PDF: đọc chữ ra từng dòng bằng pdf.js ở lớp giao diện (ui/src/shared/pdfPages.ts) rồi đưa vào `fromPdfPages` - lớp LUẬT ở đây.
 */
object BookImport {
    /** Không nhập được; câu chữ cho người dùng đọc. */
    class Failed(message: String) : Exception(message)

    /** `short`: mục EPUB rất ngắn (bìa, trang bản quyền) - bị bỏ, trừ khi bước xem trước giữ nó làm chương CHƯA CHỌN (`keepShort`).
     *  `name`: tên người dùng đặt ở bước xem trước ([selectChapters]); rỗng = `title`. Chỉ là tên - `text` không đổi (`importers.Chapter`).
     *  `matter`: có vẻ không phải truyện (bìa, bản quyền, mục lục…) - lý do cho người nghe; KHÔNG bị bỏ, chỉ chưa tích sẵn ở bước xem trước. */
    class Chapter(val title: String, val text: String, val short: Boolean = false, val name: String = "", val matter: String = "")

    class Book(
        var title: String,
        var author: String? = null,
        var language: String? = null,
        var cover: ByteArray? = null,
        var coverType: String? = null,
        val chapters: MutableList<Chapter> = mutableListOf(),
        val notes: MutableList<String> = mutableListOf(),
        /** File TXT: tên chương nằm sẵn trong chữ (EPUB / DOCX / PDF: tên chương là trường riêng). */
        val textHasTitle: Boolean = false,
        /** (số chương, dòng ghi công) - gợi ý, như trong `notes` (`ImportedBook.credits`). */
        val credits: MutableList<Pair<Int, String>> = mutableListOf(),
        /** File TXT cả truyện: số chương nếu tách theo các dòng "Chương N" (0 = không có gì để tách); người dùng tích mới tách (`ImportedBook.split_offer`). */
        var splitOffer: Int = 0,
        /** Số dòng "Chương N" ấy; ít hơn [splitOffer] một khi chữ trước tiêu đề đầu thành chương "Mở đầu" (`ImportedBook.split_headings`). */
        var splitHeadings: Int = 0,
        /** EPUB / DOCX có cấu trúc: số lời chú tìm thấy (đề xuất ở bước xem trước, [FootnoteChoice]); 0 = không có (`ImportedBook.footnote_found`). */
        var footnoteFound: Int = 0,
        /** ... trong đó số dấu gọi (số chú thích) nằm trong chữ của sách (`ImportedBook.footnote_marks`). */
        var footnoteMarks: Int = 0,
        /** (dấu gọi kèm chữ đứng trước: "…trees²", lời chú) vài ví dụ (`ImportedBook.footnote_examples`). */
        val footnoteExamples: MutableList<Pair<String, String>> = mutableListOf(),
    )

    /**
     * Chú thích trong sách nhập (`importers.FootnoteChoice`): ĐỀ XUẤT người nghe tích ở bước xem trước, mặc định KHÔNG áp - ABook không tự bỏ hay sửa chữ
     * của truyện. Mặc định (cả hai trống): chữ như trong sách, chỉ lời chú nằm GIỮA chương được đặt xuống cuối chương đó. `hideMarks`: không đọc số
     * chú thích; `notes`: "" như trong sách, "end" đọc lời chú ở cuối chương chứa dấu gọi, "drop" bỏ lời chú.
     */
    data class FootnoteChoice(val hideMarks: Boolean = false, val notes: String = "")

    /** `importers.footnote_choice_from_json`: `{"hideMarks": bool, "notes": ""|"end"|"drop"}`; null = không tích gì. Dạng sai: [Failed]. */
    fun footnoteChoiceFromJson(raw: Any?): FootnoteChoice {
        if (raw == null || raw === org.json.JSONObject.NULL) return FootnoteChoice()
        if (raw !is org.json.JSONObject) throw Failed("Lựa chọn về chú thích không hợp lệ")
        val hide = if (raw.has("hideMarks")) raw.get("hideMarks") else false
        val notes = if (raw.has("notes")) raw.get("notes") else ""
        if (hide !is Boolean || notes !is String || notes !in listOf("", "end", "drop")) throw Failed("Lựa chọn về chú thích không hợp lệ")
        return FootnoteChoice(hide, notes)
    }

    /** `ImportedBook.footnote_offer`: số lời chú tìm thấy, số dấu gọi nằm trong chữ, vài ví dụ {mark, note} - cho bước xem trước và bộ ví dụ. */
    fun footnoteOffer(book: Book): Map<String, Any?> = linkedMapOf(
        "found" to book.footnoteFound,
        "marks" to book.footnoteMarks,
        "examples" to book.footnoteExamples.map { (mark, note) -> linkedMapOf<String, Any?>("mark" to mark, "note" to note) },
    )

    val IMPORT_SUFFIXES = listOf("epub", "docx", "pdf")

    private const val MAX_MEMBER = 20L * 1024 * 1024
    private const val MAX_TOTAL = 300L * 1024 * 1024
    private const val MAX_COVER = 20L * 1024 * 1024
    private const val MIN_CHARS = 80
    private const val PREAMBLE = "Mở đầu"
    private const val MAX_HEADING = 120
    private const val TITLE_FROM_LINE = 80
    private const val CREDIT_HEAD_LINES = 64
    private const val BROKEN = "không phải file %s thật hoặc bị hỏng - thử tải lại, hoặc dùng bản TXT"

    private fun broken(kind: String) = Failed(BROKEN.format(kind))

    // ---- vào ----------------------------------------------------------------------------------------------------------

    /** Một thư mục TXT, hay file .epub / .docx / .txt. (PDF đi qua `fromPdfPages`: lấy chữ ra là việc của pdf.js.) `splitChapters`: file .txt cả
     *  truyện thì tách thành các chương theo dòng "Chương N" (người dùng tích gợi ý `splitOffer`). `keepShort`: bước xem trước - mục rất ngắn vẫn nằm
     *  trong danh sách, đúng chỗ của nó trong file ([defaultPicks] bỏ chúng); không có thì chúng bị bỏ như trước. `footnotes`: EPUB / DOCX có chú thích -
     *  lựa chọn người nghe đã tích ở bước xem trước ([FootnoteChoice]); không có thì như trong sách. */
    fun importFile(path: File, splitChapters: Boolean = false, keepShort: Boolean = false, footnotes: FootnoteChoice? = null): Book {
        val choice = footnotes ?: FootnoteChoice()
        val book = when {
            path.isDirectory -> txtFolder(path)
            path.isFile -> when (val suffix = path.extension.lowercase()) {
                "epub" -> epub(path, choice)
                "docx" -> docx(path, choice)
                "txt" -> txtFile(path, splitChapters)
                "pdf" -> throw Failed("PDF cần lấy chữ bằng pdf.js trước (fromPdfPages)")
                else -> throw Failed("Chưa đọc được file ${if (suffix.isEmpty()) "không có đuôi" else ".$suffix"} - dùng .epub, .docx, .pdf, .txt hay một thư mục TXT")
            }
            else -> throw Failed("Không thấy ${path.path}.")
        }
        return finish(book, keepShort, path.name)
    }

    /** Lựa chọn chương mặc định của bước xem trước: mọi chương trừ mục rất ngắn và mục có vẻ không phải truyện. (số chương 1-based, tên mới ""). `importers.default_picks`. */
    fun defaultPicks(book: Book): List<Pair<Int, String>> =
        book.chapters.mapIndexedNotNull { index, chapter -> if (chapter.short || chapter.matter.isNotEmpty()) null else (index + 1) to "" }

    /**
     * Cuốn chỉ gồm các chương người dùng tích ở bước xem trước, theo THỨ TỰ TRONG FILE (không theo thứ tự `picks`) - `importers.select_chapters`.
     * `picks`: (số chương 1-based trong `book.chapters`, tên mới - rỗng hay trùng tên cũ là giữ tên cũ). Chỉ đổi TÊN, chữ không đổi; `credits`
     * đánh số lại. Không chọn gì, hay số chương không có / lặp: [Failed]. Trả cuốn MỚI; `book` không đổi.
     */
    fun selectChapters(book: Book, picks: List<Pair<Int, String>>): Book {
        if (picks.isEmpty()) throw Failed("Chọn ít nhất một chương để thêm vào thư viện")
        val numbers = picks.map { it.first }
        if (numbers.toSet().size != numbers.size || numbers.any { it < 1 || it > book.chapters.size }) {
            throw Failed("Danh sách chương đã chọn không khớp với file - mở lại file rồi chọn lại")
        }
        val renumbered = HashMap<Int, Int>()
        val chapters = mutableListOf<Chapter>()
        for ((position, pick) in picks.sortedBy { it.first }.withIndex()) {
            val chapter = book.chapters[pick.first - 1]
            val name = words(pick.second)
            chapters.add(Chapter(chapter.title, chapter.text, chapter.short, if (name != chapter.title) name else "", chapter.matter))
            renumbered[pick.first] = position + 1
        }
        val credits = book.credits.mapNotNull { (number, line) -> renumbered[number]?.let { it to line } }.toMutableList()
        return Book(book.title, book.author, book.language, book.cover, book.coverType, chapters, book.notes.toMutableList(), book.textHasTitle, credits, book.splitOffer, book.splitHeadings,
            book.footnoteFound, book.footnoteMarks, book.footnoteExamples.toMutableList())
    }

    /** PDF có lớp chữ: `pages` là các dòng CÓ CHỮ của từng trang (pdf.js, như file pages trong bộ ví dụ). */
    fun fromPdfPages(stem: String, pages: List<List<String>>, title: String = "", author: String = ""): Book {
        if (pages.isEmpty()) throw broken("PDF")
        val chars = pages.sumOf { page -> page.sumOf { cpLen(it) } }
        if (chars < SCAN_CHARS_PER_PAGE * pages.size) {
            throw Failed("PDF này là ảnh chụp, chưa có chữ để đọc.")
        }
        val result = Book(title.ifEmpty { titleFromFilename(stem) }, author = author.ifEmpty { null })
        val empty = pages.count { it.isEmpty() }
        if (empty > 0) result.notes.add("$empty trang không có chữ (ảnh hay trang trống) - bỏ qua.")
        val (stripped, removed) = stripRunning(pages)
        for (line in removed) result.notes.add("Bỏ dòng lặp đầu / cuối trang: “$line”")
        val (chapters, notes) = splitOnHeadings(joinParagraphs(stripped), result.title)
        result.chapters.addAll(chapters)
        result.notes.addAll(notes)
        return finish(result)
    }

    /** Dạng JSON của bộ ví dụ (cùng `ImportedBook.to_dict`): bìa chỉ ghi cỡ + sha256. */
    fun toMap(book: Book): Map<String, Any?> {
        val cover = book.cover?.let {
            linkedMapOf<String, Any?>("type" to book.coverType, "bytes" to it.size, "sha256" to sha256(it))
        }
        return linkedMapOf(
            "title" to book.title,
            "author" to book.author,
            "language" to book.language,
            "cover" to cover,
            "chapters" to book.chapters.map { chapter ->
                linkedMapOf<String, Any?>("title" to chapter.title, "text" to chapter.text).also { if (chapter.matter.isNotEmpty()) it["matter"] = chapter.matter }
            },
            "notes" to book.notes.toList(),
        ).also {
            if (book.splitOffer > 0) {
                it["splitOffer"] = book.splitOffer
                it["splitHeadings"] = book.splitHeadings
            }
            if (book.footnoteFound > 0) it["footnotes"] = footnoteOffer(book)
        }
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun finish(book: Book, keepShort: Boolean = false, source: String = ""): Book {
        book.title = nfc(book.title).let { title -> TOC_SUFFIX.matcher(title).replaceAll("").ifEmpty { title } } // "Lều chõng — Mục lục" -> "Lều chõng"
        book.author = book.author?.takeIf { it.isNotEmpty() }?.let(::nfc)
        var all = book.chapters.map { Chapter(nfc(it.title).replace(BOM, ""), nfc(it.text).replace(BOM, ""), it.short, it.name, it.matter) }
            .map { Chapter(it.title, it.text, it.short, it.name, it.matter.ifEmpty { textMatter(it.title, it.text) }) }
        if (all.all { it.matter.isNotEmpty() || it.short }) {
            // Cả cuốn "không phải truyện" là nhận nhầm (TXT cả truyện mở bằng lời Project Gutenberg): không cờ nào (`importers._finish`).
            all = all.map { Chapter(it.title, it.text, it.short, it.name) }
        }
        val notes = book.notes.map(::nfc)
        book.notes.clear()
        book.notes.addAll(notes)
        val short = all.count { it.short }
        if (short > 0) {
            book.notes.add(if (keepShort) "$short mục rất ngắn chưa chọn - tích nếu muốn giữ." else "Bỏ qua $short mục rất ngắn (bìa, trang bản quyền?).")
        }
        val matter = all.count { it.matter.isNotEmpty() && !it.short }
        if (matter > 0 && keepShort) book.notes.add("$matter mục có vẻ không phải truyện (bìa, bản quyền, mục lục…) chưa chọn - tích nếu muốn nghe.")
        val chapters = if (keepShort) all else all.filter { !it.short }
        if (chapters.none { pyStrip(it.text).isNotEmpty() || it.short }) throw Failed("Không có chương nào có chữ trong “${source.ifEmpty { book.title }}” - file rỗng hay mã hoá lạ? " +
            "Với file .txt: thử mở bằng Notepad rồi lưu lại ở dạng UTF-8.")
        book.chapters.clear()
        if (chapters.size > 1) {
            // File TXT rỗng (hay chỉ có khoảng trắng) không thành chương - nói ra, để số chương ít hơn số file có lý do. Mục rất ngắn mà chỉ có
            // tên (trang đề tựa) thì ở lại: người dùng quyết có tích nó không.
            for (chapter in chapters) if (pyStrip(chapter.text).isEmpty() && !chapter.short) book.notes.add("Bỏ qua mục trống: ${chapter.title}")
            book.chapters.addAll(chapters.filter { pyStrip(it.text).isNotEmpty() || it.short })
        } else {
            book.chapters.addAll(chapters)
        }
        for ((index, chapter) in book.chapters.withIndex()) {
            // Tên chương tính là một dòng của chương (cửa sổ 6 dòng đầu), như file chương mà Studio đọc.
            for (line in creditSuggestions(chapterSource(book, chapter))) {
                book.credits.add(index + 1 to line)
                book.notes.add("Gợi ý: chương ${index + 1} có dòng ghi công ở đầu - “$line”. Có thể bỏ khỏi phần đọc, nhưng ABook không tự bỏ.")
            }
        }
        return book
    }

    // ---- chữ ----------------------------------------------------------------------------------------------------------

    private fun nfc(text: String) = Normalizer.normalize(text, Normalizer.Form.NFC)

    /** `importers.BOM`: dấu BOM lọt giữa chữ (nối nhiều file) - vô hình, nhưng làm "Chương 1" ở đầu dòng không còn là tiêu đề. */
    private const val BOM = "\uFEFF"

    /** Khoảng trắng của Python `str.split()` / `str.strip()`. */
    private fun isPySpace(c: Char): Boolean = when (c) {
        '\t', '\n', '\u000b', '\u000c', '\r', ' ', '\u0085', ' ', ' ', ' ', ' ', ' ', ' ', '　' -> true
        in '\u001c'..'\u001f', in ' '..' ' -> true
        else -> false
    }

    /** Gộp mọi khoảng trắng thành một dấu cách, NFC (PDF hay mang chữ tiếng Việt dạng rời; luật nhận tiêu đề cần dạng gộp). */
    internal fun words(text: String): String {
        val out = StringBuilder()
        var pending = false
        for (c in text) {
            if (isPySpace(c)) {
                pending = out.isNotEmpty()
            } else {
                if (pending) out.append(' ')
                pending = false
                out.append(c)
            }
        }
        return nfc(out.toString())
    }

    /** `" ".join(text.split())` - như [words] nhưng không NFC (chữ đã NFC từ lúc tách). */
    private fun squeeze(text: String): String {
        val out = StringBuilder()
        var pending = false
        for (c in text) {
            if (isPySpace(c)) {
                pending = out.isNotEmpty()
            } else {
                if (pending) out.append(' ')
                pending = false
                out.append(c)
            }
        }
        return out.toString()
    }

    /** Số "từ" tách bằng khoảng trắng (`len(text.split())`). */
    internal fun wordCount(text: String): Int {
        var count = 0
        var inside = false
        for (c in text) {
            if (isPySpace(c)) inside = false else if (!inside) { inside = true; count++ }
        }
        return count
    }

    /** Số ký tự có chữ, không tính khoảng trắng (`sum(not ch.isspace() for ch in text)`), theo điểm mã. */
    internal fun charCount(text: String): Int = text.codePoints().filter { it >= 0x10000 || !isPySpace(it.toChar()) }.count().toInt()

    /**
     * Chữ của chương như FILE NGUỒN mà Studio đọc (`ImportedBook.chapter_source` bên Python): TXT nguyên văn (tên chương nằm sẵn trong
     * chữ); EPUB / DOCX / PDF: tên chương, một dòng trống, rồi chữ. Kết thúc bằng một dòng mới.
     */
    fun chapterSource(book: Book, chapter: Chapter): String = (if (book.textHasTitle) chapter.text else "${chapter.title}\n\n${chapter.text}") + "\n"

    private fun pyStrip(text: String): String = text.trim { isPySpace(it) }

    private fun pyRstrip(text: String): String = text.trimEnd { isPySpace(it) }

    private fun cpLen(text: String) = text.codePointCount(0, text.length)

    /** `importers.title_from_filename`: tên sách đặt từ tên file/thư mục - "_" và chuỗi "--" trở lên thành dấu cách, "-" đơn và hoa thường giữ nguyên. */
    internal fun titleFromFilename(stem: String): String =
        words(stem.replace(Regex("_+|-{2,}"), " ")).let { if (it.isEmpty()) stem else it }

    /** `importers.clip_title`: tên hiển thị dài quá `limit` ký tự thì cắt ở ranh giới từ rồi thêm "…" (cùng luật: nhát cắt giữa từ thì
     *  lùi về dấu cách gần nhất nếu từ cuối không chiếm quá nửa, còn không thì cắt cứng). CHỈ cho tên chương đặt từ dòng đầu. */
    internal fun clipTitle(text: String, limit: Int): String {
        if (cpLen(text) <= limit) return text
        var cut = text.substring(0, text.offsetByCodePoints(0, limit))
        val next = text.codePointAt(cut.length)
        if (!(next <= 0xFFFF && isPySpace(next.toChar()))) {
            val space = cut.lastIndexOf(' ')
            if (space >= 0 && cpLen(cut.substring(0, space)) >= limit / 2) cut = cut.substring(0, space)
        }
        return cut.trimEnd { it in " .,;:!?-–—" } + "…"
    }

    private fun casefold(text: String) = text.lowercase()

    // ---- thư mục TXT --------------------------------------------------------------------------------------------------

    /** Đổi định dạng thôi: xuống dòng \n, bỏ khoảng trắng cuối dòng, tối đa một dòng trống liền nhau, bỏ dòng trống hai đầu. */
    internal fun cleanText(text: String): String {
        val lines = text.replace("\r\n", "\n").replace("\r", "\n").replace(BOM, "").split("\n").map { pyRstrip(it) }
        return lines.joinToString("\n").replace(Regex("\n{3,}"), "\n\n").trim('\n')
    }

    /** `\d`, `\s`, `\w` theo Unicode như `re` của Python ("١٥.txt" cũng là số). Android (ICU) đã theo Unicode sẵn và KHÔNG nhận cờ
     *  UNICODE_CHARACTER_CLASS / `(?U)` - dùng là văng (03-10 trên OPPO: mọi lần thêm sách từ file); JVM của kiểm thử thì cần cờ. */
    private val UNICODE_CLASSES = if (System.getProperty("java.vm.name") == "Dalvik") 0 else Pattern.UNICODE_CHARACTER_CLASS
    private val NUMERIC_TITLE = Pattern.compile("^\\s*0*(\\d+)\\s*$", UNICODE_CLASSES).toRegex()

    /** Số thứ tự đệm số 0 đầu tên file ("0000 Mở đầu", "001 - Chương 1"): chỉ khi bắt đầu bằng 0 (humanize._FILE_ORDER_PREFIX). */
    private val FILE_ORDER_PREFIX = Pattern.compile("^\\s*0\\d*(?:\\s*[-_.:]+\\s*|\\s+)(\\S.*)$", UNICODE_CLASSES).toRegex()

    /** Tên file chương là số ("645") thì đọc thành "Chương 645"; số thứ tự đánh đầu file ("0000 Mở đầu") bỏ đi; còn lại giữ nguyên
     *  (webui/humanize.chapter_title). */
    internal fun chapterTitle(stem: String): String =
        NUMERIC_TITLE.find(stem)?.let { "Chương ${it.groupValues[1]}" } ?: FILE_ORDER_PREFIX.find(stem)?.let { pyStrip(it.groupValues[1]) } ?: pyStrip(stem)

    /** `Path.suffix` / `Path.stem` của Python: ".txt" là tên không đuôi, "a.b.txt" có đuôi ".txt", "ten." không có đuôi. */
    private fun suffixAt(name: String): Int = name.lastIndexOf('.').takeIf { it > 0 && it < name.length - 1 } ?: -1

    internal fun suffixOf(name: String) = suffixAt(name).let { if (it < 0) "" else name.substring(it) }

    internal fun stemOf(name: String) = suffixAt(name).let { if (it < 0) name else name.substring(0, it) }

    /** `io_utils.natural_key`: số trong tên so theo giá trị ("2" trước "10"), chữ so không phân biệt hoa thường. */
    internal val naturalOrder = Comparator<String> { first, second ->
        val a = naturalKey(first)
        val b = naturalKey(second)
        for (index in 0 until minOf(a.size, b.size)) {
            val x = a[index]
            val y = b[index]
            val compared = if (x is BigInteger && y is BigInteger) x.compareTo(y) else (x as String).compareTo(y as String)
            if (compared != 0) return@Comparator compared
        }
        // Bằng nhau theo thứ tự tự nhiên ("1.txt", "01.txt"): theo tên gốc, không theo thứ tự hệ thống tệp liệt kê (io_utils).
        a.size.compareTo(b.size).takeIf { it != 0 } ?: first.compareTo(second)
    }

    private fun naturalKey(value: String): List<Any> {
        val parts = mutableListOf<Any>()
        val digits = DIGITS.toRegex()
        var last = 0
        for (match in digits.findAll(value)) {
            parts.add(casefold(value.substring(last, match.range.first)))
            parts.add(BigInteger(match.value))
            last = match.range.last + 1
        }
        parts.add(casefold(value.substring(last)))
        return parts
    }

    private fun txtFolder(folder: File): Book {
        val files = (folder.listFiles() ?: emptyArray())
            .filter { it.isFile && suffixOf(it.name).lowercase() == ".txt" }
            .sortedWith { x, y -> naturalOrder.compare(x.name, y.name) }
        if (files.isEmpty()) throw Failed("Thư mục này không có file .txt nào nằm ngay bên trong")
        val read = files.map(::txtChapter)
        return Book(
            titleFromFilename(folder.canonicalFile.name), chapters = read.map { it.first }.toMutableList(), notes = encodingNotes(read.map { it.second }),
            textHasTitle = true,
        )
    }

    /** Một file TXT là một chương - trừ khi nó là CẢ truyện (>= 2 dòng "Chương N") và người dùng tích tách (`importers._txt_file`). */
    private fun txtFile(file: File, split: Boolean): Book {
        val (chapter, encoding) = txtChapter(file)
        val book = Book(titleFromFilename(stemOf(file.name)), chapters = mutableListOf(chapter), notes = encodingNotes(listOf(encoding)), textHasTitle = true)
        val parts = splitTxtChapters(chapter.text)
        book.splitOffer = parts.size
        // Chương tách ra từ một dòng tiêu đề mang tên dòng ấy - không bao giờ trùng tên chương "Mở đầu".
        book.splitHeadings = parts.count { it.title != PREAMBLE }
        if (parts.isNotEmpty()) {
            // Cả truyện: tên sách gợi ý là dòng tiêu đề đầu file, không phải tên file (importers._txt_file).
            titleFromLine(firstTextLine(chapter.text)).takeIf { it.isNotEmpty() }?.let { book.title = it }
            val lines = chapter.text.split("\n")
            val alone = titleOnlyPreamble(lines, txtCuts(lines).firstOrNull() ?: 0)
            if (split && alone.isNotEmpty()) book.notes.add("Dòng đầu “$alone” là tên truyện - dùng làm tên sách, không đọc thành một chương.")
        }
        val (title, author) = gutenbergHeader(chapter.text)
        if (title.isNotEmpty()) book.title = title
        book.author = author.ifEmpty { null }
        if (split && parts.isNotEmpty()) {
            book.chapters.clear()
            book.chapters.addAll(parts)
        }
        return book
    }

    private val PG_FIELD = Regex("(title|author)\\s*:\\s*(.+)", RegexOption.IGNORE_CASE)
    private const val PG_HEAD_LINES = 60

    /** `importers.gutenberg_header`: file TXT của Project Gutenberg ("The Project Gutenberg eBook of …" rồi "Title: …", "Author: …") -> (tên, tác giả);
     *  không thì ("", ""). */
    internal fun gutenbergHeader(text: String): Pair<String, String> {
        val lines = text.split("\n", limit = PG_HEAD_LINES + 1).take(PG_HEAD_LINES)
        if ("project gutenberg" !in casefold(firstTextLine(lines.joinToString("\n")))) return "" to ""
        val found = HashMap<String, String>()
        for (line in lines) {
            if (line.trimStart { isPySpace(it) }.startsWith("***")) break
            PG_FIELD.matchEntire(pyStrip(line))?.let { found.putIfAbsent(casefold(it.groupValues[1]), words(it.groupValues[2])) }
        }
        return (found["title"] ?: "") to (found["author"] ?: "")
    }

    /** `importers._txt_cuts`: các dòng "Chương N" của file TXT cả truyện, TRỪ mục lục - chuỗi tiêu đề liền nhau không có chữ giữa chúng (>= 2
     *  tiêu đề trống) không phải chương, chúng ở lại trong chữ dẫn. */
    internal fun txtCuts(lines: List<String>): List<Int> {
        val cuts = lines.indices.filter { isHeadingLine(lines[it], TXT_HEADING) }
        val kept = mutableListOf<Int>()
        val run = mutableListOf<Int>()
        for ((position, start) in cuts.withIndex()) {
            val end = if (position + 1 < cuts.size) cuts[position + 1] else lines.size
            run.add(start)
            if ((start + 1 until end).any { pyStrip(lines[it]).isNotEmpty() }) {
                if (run.size <= 2) kept.addAll(run) else kept.add(start)
                run.clear()
            }
        }
        if (run.size == 1) kept.addAll(run)
        return kept
    }

    /** `importers.first_text_line`: dòng đầu có chữ, bỏ khoảng trắng hai đầu; "" nếu không có. */
    internal fun firstTextLine(text: String): String = text.split("\n").map(::pyStrip).firstOrNull { it.isNotEmpty() }.orEmpty()

    /** `importers.title_from_line`: [line] nếu nó trông là TIÊU ĐỀ truyện (ngắn, có chữ, không bắt đầu bằng gạch lời thoại / ngoặc, không
     *  kết bằng dấu câu, không phải dòng "Chương N"; `#` Markdown đầu dòng bỏ đi), không thì "". */
    internal fun titleFromLine(line: String): String {
        val first = pyStrip(pyStrip(line).trimStart('#'))
        if (first.isEmpty() || cpLen(first) > 80 || wordCount(first) > 12 || casefold(first) in TOC_TITLES) return ""
        if (isHeadingLine(first) || first[0] in "-–—“\"‘'«(" || first.last() in ".!?…,;:\"”’»)") return ""
        return if (first.codePoints().anyMatch { Character.isLetter(it) }) first else ""
    }

    /** `importers.title_only_preamble`: chữ trước tiêu đề chương đầu ([cut] = chỉ số dòng ấy) chỉ là MỘT dòng và dòng ấy trông là tiêu đề truyện
     *  -> tên truyện đó; không thì "". Nó là tên sách chứ không phải một chương "Mở đầu". */
    internal fun titleOnlyPreamble(lines: List<String>, cut: Int): String {
        val kept = lines.subList(0, maxOf(cut, 0)).filter { pyStrip(it).isNotEmpty() }
        return if (kept.size == 1) titleFromLine(kept[0]) else ""
    }

    /** `importers.split_txt_chapters`: chữ (đã `cleanText`) của file TXT cả truyện -> các chương cắt ở đầu mỗi dòng "Chương N" (không tính "Quyển N"),
     *  tiêu đề nằm trong chữ của chương, chữ trước tiêu đề đầu tiên thành "Mở đầu". Dưới hai tiêu đề: rỗng. */
    internal fun splitTxtChapters(text: String): List<Chapter> {
        val lines = text.split("\n")
        val cuts = txtCuts(lines)
        if (cuts.size < 2) return emptyList()
        val chapters = mutableListOf<Chapter>()
        // Chữ dẫn chỉ là một dòng tên truyện thì không thành chương "Mở đầu" - nó là tên sách (titleOnlyPreamble).
        if (lines.subList(0, cuts[0]).any { pyStrip(it).isNotEmpty() } && titleOnlyPreamble(lines, cuts[0]).isEmpty()) chapters.add(Chapter(PREAMBLE, lines.subList(0, cuts[0]).joinToString("\n").trim('\n')))
        for ((position, start) in cuts.withIndex()) {
            val end = if (position + 1 < cuts.size) cuts[position + 1] else lines.size
            chapters.add(Chapter(pyStrip(lines[start]), lines.subList(start, end).joinToString("\n").trim('\n')))
        }
        return chapters
    }

    /** Một file TXT là một chương (`importers._txt_chapter`), cùng bảng mã đã đọc. Tên chương: dòng đầu nếu nó là dòng tiêu đề ("Chương 1:
     *  Buổi sáng" - đúng thứ người nghe thấy ở đầu chương), không thì tên file ("01.txt" -> "Chương 1"). */
    private fun txtChapter(file: File): Pair<Chapter, String> {
        val (decoded, encoding) = decodeText(file.readBytes())
        val text = cleanText(decoded)
        val first = text.split("\n").map(::pyStrip).firstOrNull { it.isNotEmpty() }.orEmpty()
        if (isHeadingLine(first)) return Chapter(first, text) to encoding
        // Tên file vô nghĩa ("index_split_003", "Untitled") mà dòng đầu trông là tiêu đề ("Sương sớm"): tên chương là dòng ấy.
        val named = if (MEANINGLESS_NAME.matcher(stemOf(file.name)).matches()) titleFromLine(first) else ""
        return Chapter(named.ifEmpty { chapterTitle(stemOf(file.name)) }, text) to encoding
    }

    /** `importers.MEANINGLESS_NAME`: tên file do công cụ đặt. */
    private val MEANINGLESS_NAME = Pattern.compile("index_split_\\d+|untitled(?:[\\s_-]*\\d+)?|part\\d+|text\\d+|split_\\d+", Pattern.CASE_INSENSITIVE or UNICODE_CLASSES)

    /** `importers.ENCODING_NAMES`: bảng mã đoán được không phải UTF - báo người dùng, đoán sai thì chữ lạ và họ biết cách sửa. */
    private val ENCODING_NAMES = linkedMapOf("cp1258" to "tiếng Việt Windows (cp1258)", "windows-1252" to "Tây Âu (cp1252)", "gb18030" to "tiếng Trung (GB18030)")

    private fun encodingNotes(encodings: Collection<String>): MutableList<String> {
        val names = ENCODING_NAMES.filterKeys { it in encodings }.values
        if (names.isEmpty()) return mutableListOf()
        return mutableListOf("File chữ không phải UTF-8 - đã đọc theo bảng mã ${names.joinToString(", ")}. Nếu chữ lạ, lưu lại file dạng UTF-8 rồi nhập lại.")
    }

    internal fun decodeTextBytes(raw: ByteArray): String = decodeText(raw).first

    /** `io_utils.decode_text`: (chữ NFC, bảng mã). UTF-16 (BOM, hay nhiều byte 0), UTF-8 (có / không BOM); không thì cp1258 khi chữ ra
     *  trông như tiếng Việt (`looksVietnamese`), còn lại cp1252 hay gb18030 theo `encodingScore` - cp1258 nhận mọi byte. */
    internal fun decodeText(raw: ByteArray): Pair<String, String> {
        if (raw.size >= 2 && ((raw[0] == 0xFF.toByte() && raw[1] == 0xFE.toByte()) || (raw[0] == 0xFE.toByte() && raw[1] == 0xFF.toByte()))) {
            return nfc(String(raw, Charsets.UTF_16)) to "utf-16"
        }
        val encodings = mutableListOf("utf-8-sig" to "utf-8-sig", "UTF-8" to "utf-8") // (tên Java, tên Python)
        if (raw.isNotEmpty()) {
            var even = 0
            var odd = 0
            for (index in raw.indices) if (raw[index].toInt() == 0) if (index % 2 == 0) even++ else odd++
            if ((even + odd).toDouble() / raw.size >= 0.2) encodings.add(0, if (even > odd) "UTF-16BE" to "utf-16-be" else "UTF-16LE" to "utf-16-le")
        }
        for ((charset, name) in encodings) {
            val decoded = strictDecode(raw, charset) ?: continue
            if ('�' !in decoded) return nfc(decoded) to name
        }
        val guesses = LinkedHashMap<String, String>()
        for ((charset, name) in listOf("windows-1258" to "cp1258", "windows-1252" to "windows-1252", "GB18030" to "gb18030")) {
            strictDecode(raw, charset)?.takeIf { '�' !in it }?.let { guesses[name] = nfc(it) }
        }
        guesses["cp1258"]?.takeIf(::looksVietnamese)?.let { return it to "cp1258" }
        // Hoà điểm: cp1252 (đứng trước), như `max` của Python.
        val best = listOf("windows-1252", "gb18030").filter { it in guesses }.maxByOrNull { encodingScore(guesses.getValue(it), it) }
        if (best != null) return guesses.getValue(best) to best
        guesses["cp1258"]?.let { return it to "cp1258" }
        return nfc(String(raw, Charsets.UTF_8)) to "utf-8"
    }

    // `io_utils.VIET_LETTERS` / `VIET_ONLY` ...: chữ Việt có dấu, chữ CHỈ tiếng Việt có (Bồ Đào Nha đọc nhầm qua cp1258 chỉ ra ă / ơ).
    private val VIET_LETTERS: Set<Int> = buildSet {
        for (vowel in "aăâeêioôơuưy") for (base in listOf(vowel.toString(), vowel.uppercase())) {
            for (tone in listOf("", "\u0300", "\u0301", "\u0309", "\u0303", "\u0323")) add(Normalizer.normalize(base + tone, Normalizer.Form.NFC).codePointAt(0))
        }
        add('đ'.code)
        add('Đ'.code)
    }
    private val VIET_ONLY: Set<Int> = VIET_LETTERS.filter { it >= 0x1EA0 }.toSet() + "đĐưƯĩĨũŨ".map { it.code }
    private const val VIET_WORD_MAX = 7
    private const val VIET_PLAUSIBLE = 0.9
    private const val VIET_ONLY_SHARE = 0.2
    private const val LATIN_RUN_MAX = 3
    private val LATIN_MARKS: Set<Int> = "“”‘’–—…«»°·€©®™§¡¿".map { it.code }.toSet()
    private val CJK = listOf(0x3400..0x4DBF, 0x4E00..0x9FFF, 0xF900..0xFAFF)
    private val CJK_MARKS = listOf(0x3000..0x303F, 0xFF00..0xFFEF)

    private fun letterRuns(text: String): List<IntArray> {
        val runs = ArrayList<IntArray>()
        val word = ArrayList<Int>()
        for (code in text.codePoints().toArray()) {
            if (Character.isLetter(code) || Character.getType(code) == Character.NON_SPACING_MARK.toInt()) {
                word.add(code)
            } else if (word.isNotEmpty()) {
                runs.add(word.toIntArray())
                word.clear()
            }
        }
        if (word.isNotEmpty()) runs.add(word.toIntArray())
        return runs
    }

    /** `io_utils.looks_vietnamese`. */
    internal fun looksVietnamese(text: String): Boolean {
        var accented = 0
        var plausible = 0
        var only = 0
        for (word in letterRuns(text)) {
            if (word.all { it < 0x80 }) continue
            accented++
            if (word.size <= VIET_WORD_MAX && word.all { it < 0x80 || it in VIET_LETTERS }) plausible++
            if (word.any { it in VIET_ONLY }) only++
        }
        return accented == 0 || (plausible >= VIET_PLAUSIBLE * accented && only >= VIET_ONLY_SHARE * accented)
    }

    /** `io_utils.encoding_score`: chữ đúng trừ hai lần chữ lạ. */
    internal fun encodingScore(text: String, encoding: String): Int {
        val points = text.codePoints().toArray()
        var good = 0
        var bad = 0
        if (encoding == "gb18030") {
            for ((index, code) in points.withIndex()) {
                if (code < 0x80) continue
                val near = listOfNotNull(points.getOrNull(index - 1), points.getOrNull(index + 1))
                if ((CJK.any { code in it } && near.none { it < 0x80 && Character.isLetter(it) }) || CJK_MARKS.any { code in it }) good++ else bad++
            }
            return good - 2 * bad
        }
        var run = 0
        var clean = true
        for (code in points + '\n'.code) {
            if (code >= 0x80) {
                run++
                if (!Character.isLetter(code) && code !in LATIN_MARKS) clean = false
                continue
            }
            if (run > 0) {
                if (run <= LATIN_RUN_MAX && clean) good += run else bad += run
                run = 0
                clean = true
            }
        }
        return good - 2 * bad
    }

    private val DECLARED_ENCODING = Pattern.compile("<\\?xml[^>]*?encoding\\s*=\\s*[\"']([\\w.:-]+)|<meta[^>]*?charset\\s*=\\s*[\"']?([\\w.:-]+)", Pattern.CASE_INSENSITIVE)
    private val ENCODING_ALIASES = mapOf(
        "gb2312" to "gb18030", "gbk" to "gb18030", "x-gbk" to "gb18030",
        "iso-8859-1" to "windows-1252", "latin1" to "windows-1252", "us-ascii" to "windows-1252", "ascii" to "windows-1252",
    )

    /** `importers.markup_text`: chữ một trang XHTML - UTF-8 (hay UTF-16 có BOM) nếu đọc trọn được, không thì theo khai báo
     *  `<?xml encoding>` / `<meta charset>` trong 2 KB đầu, không có thì UTF-8. */
    internal fun markupText(raw: ByteArray): String {
        if (raw.size >= 2 && ((raw[0] == 0xFF.toByte() && raw[1] == 0xFE.toByte()) || (raw[0] == 0xFE.toByte() && raw[1] == 0xFF.toByte()))) {
            return String(raw, Charsets.UTF_16)
        }
        strictDecode(raw, "utf-8-sig")?.let { return it }
        val match = DECLARED_ENCODING.matcher(String(raw, 0, minOf(raw.size, 2048), Charsets.ISO_8859_1))
        val name = if (match.find()) (match.group(1) ?: match.group(2)).lowercase() else "utf-8"
        val charset = try {
            Charset.forName(ENCODING_ALIASES[name] ?: name)
        } catch (_: Exception) {
            Charsets.UTF_8
        }
        return String(raw, charset)
    }

    private fun strictDecode(raw: ByteArray, encoding: String): String? {
        val signed = encoding == "utf-8-sig"
        val charset = try {
            Charset.forName(if (signed) "UTF-8" else encoding)
        } catch (_: Exception) {
            return null
        }
        return try {
            val text = charset.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT)
                .decode(ByteBuffer.wrap(raw)).toString()
            if (signed) text.removePrefix("﻿") else text
        } catch (_: CharacterCodingException) {
            null
        }
    }

    // ---- thẻ (XHTML / XML) --------------------------------------------------------------------------------------------

    internal object Markup {
        sealed class Tok
        class Start(val name: String, val attrs: Map<String, String>, val selfClosing: Boolean, val declared: Map<String, String> = emptyMap()) : Tok()
        class End(val name: String) : Tok()
        class Text(val text: String) : Tok()

        /** `_charref` của `html.unescape` (Python): số thập phân / thập lục, hay tên tới 32 ký tự; dấu chấm phẩy không bắt buộc. */
        private val ENTITY = Regex("&(#[0-9]+;?|#[xX][0-9a-fA-F]+;?|[^\\t\\n\\u000C <&#;]{1,32};?)")

        /** `_invalid_charrefs` của Python: &#0; và &#13;, và 0x80-0x9F đọc như bảng mã Windows-1252 (trang web cũ viết &#147;…&#148;). */
        private val INVALID_CHARREFS: Map<Int, String> = mapOf(0x00 to "�", 0x0D to "\r") +
            "€\u0081‚ƒ„…†‡ˆ‰Š‹Œ\u008DŽ\u008F\u0090‘’“”•–—˜™š›œ\u009DžŸ"
                .mapIndexed { index, char -> (0x80 + index) to char.toString() }

        /** `_invalid_codepoints` của Python: ký tự điều khiển và phi ký tự - bỏ đi. */
        private fun invalidCodePoint(value: Int) = value in 0x1..0x8 || value == 0xB || value in 0xE..0x1F || value in 0x7F..0x9F ||
            value in 0xFDD0..0xFDEF || (value and 0xFFFE) == 0xFFFE

        /** Bản chép của `html.unescape` (Python), cùng bảng tên [HtmlEntities]: bộ nhập máy tính đọc EPUB bằng `html.parser`. */
        fun decode(text: String): String {
            if (text.indexOf('&') < 0) return text
            return ENTITY.replace(text) { match ->
                val body = match.groupValues[1]
                if (body[0] == '#') charRef(body) else HtmlEntities.byName[body] ?: legacyName(body)
            }
        }

        private fun charRef(body: String): String {
            val hex = body.length > 1 && (body[1] == 'x' || body[1] == 'X')
            val number = java.math.BigInteger(body.substring(if (hex) 2 else 1).trimEnd(';'), if (hex) 16 else 10)
            val value = if (number.bitLength() > 31) Int.MAX_VALUE else number.toInt()
            return when {
                value in INVALID_CHARREFS -> INVALID_CHARREFS.getValue(value)
                value in 0xD800..0xDFFF || value > 0x10FFFF -> "�"
                invalidCodePoint(value) -> ""
                else -> String(Character.toChars(value))
            }
        }

        /** Tên cũ không cần dấu chấm phẩy ("&copy 2020"): tên dài nhất khớp ở đầu, phần còn lại giữ nguyên; không khớp thì để nguyên. */
        private fun legacyName(body: String): String {
            for (cut in body.length - 1 downTo 2) {
                HtmlEntities.byName[body.substring(0, cut)]?.let { return it + body.substring(cut) }
            }
            return "&$body"
        }

        fun tokenize(src: String): List<Tok> {
            val out = mutableListOf<Tok>()
            var i = 0
            val n = src.length
            while (i < n) {
                if (src[i] != '<') {
                    val end = src.indexOf('<', i).let { if (it < 0) n else it }
                    out.add(Text(decode(src.substring(i, end))))
                    i = end
                    continue
                }
                when {
                    src.startsWith("<!--", i) -> i = src.indexOf("-->", i + 4).let { if (it < 0) n else it + 3 }
                    src.startsWith("<![CDATA[", i) -> {
                        val end = src.indexOf("]]>", i + 9).let { if (it < 0) n else it }
                        out.add(Text(src.substring(i + 9, end)))
                        i = minOf(n, end + 3)
                    }
                    src.startsWith("<?", i) -> i = src.indexOf("?>", i + 2).let { if (it < 0) n else it + 2 }
                    src.startsWith("<!", i) -> i = skipDeclaration(src, i)
                    src.startsWith("</", i) -> {
                        val end = src.indexOf('>', i + 2).let { if (it < 0) n else it }
                        out.add(End(src.substring(i + 2, end).trim()))
                        i = minOf(n, end + 1)
                    }
                    i + 1 < n && (src[i + 1].isLetter() || src[i + 1] == '_' || src[i + 1] == ':') -> i = startTag(src, i, out)
                    else -> {
                        out.add(Text("<"))
                        i++
                    }
                }
            }
            return out
        }

        private fun skipDeclaration(src: String, from: Int): Int {
            var depth = 0
            var i = from + 2
            while (i < src.length) {
                when (src[i]) {
                    '[' -> depth++
                    ']' -> depth--
                    '>' -> if (depth <= 0) return i + 1
                }
                i++
            }
            return src.length
        }

        private fun startTag(src: String, from: Int, out: MutableList<Tok>): Int {
            val n = src.length
            var i = from + 1
            val nameStart = i
            while (i < n && !src[i].isWhitespace() && src[i] != '/' && src[i] != '>') i++
            val name = src.substring(nameStart, i)
            val attrs = linkedMapOf<String, String>()
            val declared = HashMap<String, String>() // xmlns / xmlns:tiền-tố khai báo ở thẻ này
            var selfClosing = false
            while (i < n) {
                while (i < n && src[i].isWhitespace()) i++
                if (i >= n) break
                if (src[i] == '>') {
                    i++
                    break
                }
                if (src[i] == '/') {
                    if (i + 1 < n && src[i + 1] == '>') {
                        selfClosing = true
                        i += 2
                        break
                    }
                    i++
                    continue
                }
                val keyStart = i
                while (i < n && !src[i].isWhitespace() && src[i] != '=' && src[i] != '>' && src[i] != '/') i++
                val key = src.substring(keyStart, i)
                while (i < n && src[i].isWhitespace()) i++
                var value = ""
                if (i < n && src[i] == '=') {
                    i++
                    while (i < n && src[i].isWhitespace()) i++
                    if (i < n && (src[i] == '"' || src[i] == '\'')) {
                        val quote = src[i]
                        val end = src.indexOf(quote, i + 1).let { if (it < 0) n else it }
                        value = src.substring(i + 1, end)
                        i = minOf(n, end + 1)
                    } else {
                        val valueStart = i
                        while (i < n && !src[i].isWhitespace() && src[i] != '>') i++
                        value = src.substring(valueStart, i)
                    }
                }
                if (key == "xmlns") declared[""] = decode(value) else if (key.startsWith("xmlns:")) declared[key.substring(6)] = decode(value)
                if (key.isNotEmpty()) attrs.putIfAbsent(key.substringAfter(':'), decode(value))
                // Tên có tiền tố cũng giữ nguyên ("epub:type"): `types` cần biết `type` có tiền tố hay không (`<ol type="a">` không phải vai).
                if (':' in key && !key.startsWith("xmlns")) attrs.putIfAbsent(key, decode(value))
            }
            out.add(Start(name, attrs, selfClosing, declared))
            val lower = name.lowercase()
            if (!selfClosing && (lower == "script" || lower == "style")) {
                // Chữ trong script / style là mã, không phải chữ của truyện: bỏ tới thẻ đóng.
                val close = Regex("</$lower\\s*>", RegexOption.IGNORE_CASE).find(src, i)
                if (close != null) {
                    out.add(End(name))
                    return close.range.last + 1
                }
                out.add(End(name))
                return n
            }
            return i
        }

        /** Không gian tên quen thuộc -> tiền tố chuẩn: `name` của [Node] dùng tiền tố này bất kể file viết tiền tố gì (hay không
         *  viết, xmlns mặc định) - như ElementTree so theo không gian tên chứ không theo chữ trước dấu hai chấm. */
        private val PREFIXES = mapOf(
            "http://schemas.openxmlformats.org/wordprocessingml/2006/main" to "w",
            "http://schemas.openxmlformats.org/markup-compatibility/2006" to "mc",
            "http://purl.org/dc/elements/1.1/" to "dc",
        )

        /**
         * Một phần tử XML: `parts` là chữ và phần tử con theo thứ tự (như text / tail của ElementTree). `name` có tiền tố chuẩn
         * ([PREFIXES]) khi không gian tên của nó quen thuộc; `raw` là tên như viết trong file (để khớp thẻ đóng).
         */
        class Node(val name: String, val attrs: Map<String, String>, val raw: String = name, val scope: Map<String, String> = emptyMap()) {
            val parts = mutableListOf<Any>()
            val local: String get() = name.substringAfter(':')
            val children: List<Node> get() = parts.filterIsInstance<Node>()

            /** Chữ trước phần tử con đầu tiên (`Element.text`). */
            val text: String get() = (parts.firstOrNull() as? String) ?: ""

            fun child(local: String): Node? = children.firstOrNull { it.local == local }

            fun descendants(): Sequence<Node> = sequence {
                for (child in children) {
                    yield(child)
                    yieldAll(child.descendants())
                }
            }

            /** Mọi chữ bên trong, theo thứ tự (`Element.itertext`). */
            fun allText(): String = parts.joinToString("") { if (it is String) it else (it as Node).allText() }

            fun attr(local: String): String? = attrs[local]
        }

        /** Đọc một file XML: từ chối khai báo entity (bom XML), không thấy phần tử gốc là file hỏng. `strict`: thẻ đóng sai chỗ hay thiếu
         *  cũng là file hỏng, như ElementTree của máy tính (tệp mục lục: hỏng thì cả hai bên cùng bỏ nó, đọc theo spine). */
        fun parse(raw: ByteArray, kind: String, strict: Boolean = false): Node {
            val head = String(raw, 0, minOf(raw.size, 4096), Charsets.UTF_8)
            if (head.uppercase().contains("<!ENTITY")) throw Failed("có nội dung XML lạ (khai báo entity) - không mở để giữ an toàn máy")
            val stack = ArrayList<Node>()
            var root: Node? = null
            for (token in tokenize(String(raw, Charsets.UTF_8))) {
                when (token) {
                    is Start -> {
                        val scope = (stack.lastOrNull()?.scope ?: emptyMap()).let { if (token.declared.isEmpty()) it else it + token.declared }
                        val prefix = if (':' in token.name) token.name.substringBefore(':') else ""
                        val canonical = scope[prefix]?.let(PREFIXES::get)?.let { "$it:${token.name.substringAfter(':')}" } ?: token.name
                        val node = Node(canonical, token.attrs, token.name, scope)
                        if (stack.isEmpty()) {
                            if (root == null) root = node
                        } else {
                            stack.last().parts.add(node)
                        }
                        if (!token.selfClosing) stack.add(node)
                    }
                    is End -> {
                        val index = stack.indexOfLast { it.raw == token.name }
                        if (strict && index != stack.size - 1) throw broken(kind)
                        if (index >= 0) while (stack.size > index) stack.removeAt(stack.size - 1)
                    }
                    is Text -> stack.lastOrNull()?.parts?.add(token.text)
                }
            }
            if (strict && stack.isNotEmpty()) throw broken(kind)
            return root ?: throw broken(kind)
        }
    }

    // ---- zip ----------------------------------------------------------------------------------------------------------

    private fun openZip(file: File, kind: String): ZipFile {
        val zip = try {
            ZipFile(file)
        } catch (_: ZipException) {
            throw broken(kind)
        } catch (_: IOException) {
            throw broken(kind)
        }
        if (zip.entries().asSequence().sumOf { maxOf(0L, it.size) } > MAX_TOTAL) {
            zip.close()
            throw Failed("quá lớn khi giải nén (trên 300 MB) - không giống $kind truyện")
        }
        return zip
    }

    /** Mục tên NFC -> mục, cho các gói có tên dạng rời: một lần mỗi gói (cuốn nghìn chương NFD không quét lại nghìn lần). */
    private val nfcNames = java.util.WeakHashMap<ZipFile, Map<String, java.util.zip.ZipEntry>>()

    /** Mục [name] của gói (`importers._Zip.member`): tên trong zip viết Unicode dạng rời (NFD - zip làm trên macOS) mà manifest viết dạng gộp
     *  (hay ngược lại) vẫn khớp. Không có: null. */
    private fun member(zip: ZipFile, name: String): java.util.zip.ZipEntry? {
        zip.getEntry(name)?.let { return it }
        val index = synchronized(nfcNames) { nfcNames.getOrPut(zip) { zip.entries().asSequence().associateBy { nfc(it.name) } } }
        return index[nfc(name)]
    }

    private fun read(zip: ZipFile, name: String, kind: String): ByteArray {
        val entry = member(zip, name) ?: throw broken(kind)
        if (entry.size > MAX_MEMBER) throw Failed("có một phần quá lớn (trên 20 MB) - không giống $kind truyện")
        return zip.getInputStream(entry).use { it.readBytes() }
    }

    private fun xml(zip: ZipFile, name: String, kind: String, strict: Boolean = false) = Markup.parse(read(zip, name, kind), kind, strict)

    private fun metaText(root: Markup.Node, local: String): String? {
        val node = root.descendants().firstOrNull { it.local == local && it.name.startsWith("dc:") } ?: return null
        return words(node.text).ifEmpty { null }
    }

    // ---- posix ---------------------------------------------------------------------------------------------------------

    private fun dirname(path: String) = if (path.contains('/')) path.substringBeforeLast('/') else ""

    private fun join(base: String, relative: String): String =
        if (relative.startsWith("/")) relative else if (base.isEmpty()) relative else "$base/$relative"

    private fun normpath(path: String): String {
        if (path.isEmpty()) return "."
        val absolute = path.startsWith("/")
        val out = mutableListOf<String>()
        for (part in path.split("/")) {
            if (part.isEmpty() || part == ".") continue
            if (part == ".." && out.isNotEmpty() && out.last() != "..") out.removeAt(out.size - 1)
            else if (part == ".." && absolute) continue
            else out.add(part)
        }
        val joined = out.joinToString("/")
        return if (absolute) "/$joined" else joined.ifEmpty { "." }
    }

    /** `urllib.parse.unquote`: %XX là byte UTF-8. */
    private fun unquote(text: String): String {
        if (text.indexOf('%') < 0) return text
        val bytes = java.io.ByteArrayOutputStream()
        var i = 0
        while (i < text.length) {
            val c = text[i]
            if (c == '%' && i + 2 < text.length && isHex(text[i + 1]) && isHex(text[i + 2])) {
                bytes.write(text.substring(i + 1, i + 3).toInt(16))
                i += 3
            } else {
                bytes.write(c.toString().toByteArray(Charsets.UTF_8))
                i++
            }
        }
        return String(bytes.toByteArray(), Charsets.UTF_8)
    }

    private fun isHex(c: Char) = c in '0'..'9' || c in 'a'..'f' || c in 'A'..'F'

    // ---- EPUB ----------------------------------------------------------------------------------------------------------

    private val TEXT_BLOCKS = setOf(
        "p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "section", "article", "tr", "dd", "dt", "pre", "figure", "figcaption", "aside",
    )
    private val CELLS = setOf("td", "th") // ô bảng: cách nhau một dấu cách
    private val NOTE_MARK = Pattern.compile("\\[?\\d{1,3}\\]?|\\*{1,3}|†", UNICODE_CLASSES) // chữ trong <sup> là số chú thích (`importers.NOTE_MARK`)
    private val UNIT_POWER = Pattern.compile("(?<!\\p{L})[kcdm]?m$", UNICODE_CLASSES) // trừ lũy thừa đơn vị: "m<sup>2</sup>" vẫn là "m2"
    private val TEXT_HEADINGS = setOf("h1", "h2", "h3")
    private val WRAPPERS = setOf("body", "section", "div", "article", "main") // khối bọc cả trang: vai của chúng (trước chữ đầu tiên) là vai của trang
    private val SKIPPED_TAGS = setOf("script", "style", "head", "title")
    private val LISTS = setOf("ol", "ul") // danh sách: không ngắt dòng, nhưng có thể là vùng lời chú (<ol epub:type="endnotes">)

    // Chú thích (`importers.NOTE_*`): dấu gọi nằm trong dòng giữa NOTE_OPEN…NOTE_CLOSE (ký tự vùng riêng, không bao giờ có trong chữ truyện) cho tới
    // khi `resolveNotes` gỡ chúng; DOCX dùng chúng để giữ chỗ dấu tham chiếu.
    private const val NOTE_OPEN = ""
    private const val NOTE_SEP = ""
    private const val NOTE_CLOSE = ""
    private val NOTE_SPAN = Regex("$NOTE_OPEN(\\d+)$NOTE_SEP([^\\n]*?)$NOTE_CLOSE")
    private val DOCX_REF = Regex("$NOTE_OPEN([fe])(-?\\d+)$NOTE_CLOSE")
    private val NOTE_LABEL = Pattern.compile("[\\[(]?\\d{1,3}[\\])]?|\\*{1,3}|†|‡|[⁰¹²³⁴-⁹]+", UNICODE_CLASSES) // nhãn của dấu gọi là liên kết: "1", "[2]", "*", "²"
    private const val NOTE_MARK_MAX = 12 // dấu gọi có epub:type="noteref" mang nhãn bất kỳ, nhưng không dài hơn chừng này ký tự
    private val NOTE_TYPES = setOf("footnote", "endnote", "rearnote") // epub:type / role (bỏ "doc-") của MỘT lời chú
    private val NOTE_AREA_TYPES = setOf("footnotes", "endnotes", "rearnotes") // ... của vùng chứa các lời chú (chương Endnotes)
    private const val MAX_NOTE_LINES = 40 // đích của dấu gọi dài hơn thế (không phải lời chú, vd cả một chương) thì thôi
    private const val NOTE_CONTEXT = 24 // số ký tự chữ đứng trước dấu gọi, cho ví dụ ở bước xem trước
    private const val NOTE_EXAMPLES = 3
    private const val NOTE_EXAMPLE_WIDTH = 80
    private val EXTERNAL = Pattern.compile("[a-z][a-z0-9+.-]*:", Pattern.CASE_INSENSITIVE) // liên kết ra ngoài (http:, mailto:) không phải dấu gọi
    private const val SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹" // chữ số 0-9 viết nhỏ trên dòng

    private fun superscript(digits: String): String = digits.map { if (it in '0'..'9') SUPERSCRIPT[it - '0'] else it }.joinToString("")

    /** Một dấu gọi chú thích trong chữ (`importers._Mark`): đích, nhãn ("2", "[1]"), chữ đứng ngay trước, id của chính dấu, dòng chứa nó. */
    private class Mark(val href: String, val label: String, val before: String, val id: String, val line: Int)

    /** Một `<a>` đang mở (`_Text._links`): đích, chỗ bắt đầu trong dòng đang viết, có noteref không, id, đang trong `<sup>` / chứa `<sup>`. */
    private class Link(val href: String, var start: Int, val noteref: Boolean, val id: String, val inSup: Boolean, var sup: Boolean = false)

    /** Một khối đang mở (`_Text._stack`): thẻ, dòng bắt đầu, các id nằm trong nó, kiểu: 0 thường / 1 lời chú / 2 vùng lời chú. */
    private class Block(val tag: String, val start: Int, val ids: MutableList<String>, val kind: Int)

    /** `importers._note_context`: chữ đứng ngay trước một dấu gọi (tối đa [NOTE_CONTEXT] ký tự, không cắt giữa từ) - ngữ cảnh cho ví dụ ở bước xem trước. */
    internal fun noteContext(before: String): String {
        val flat = squeeze(NOTE_SPAN.replace(before, "")) // số của dấu gọi đứng trước không phải chữ truyện
        if (cpLen(flat) <= NOTE_CONTEXT) return flat
        val cut = flat.offsetByCodePoints(flat.length, -NOTE_CONTEXT)
        var tail = flat.substring(cut)
        if (flat[flat.offsetByCodePoints(cut, -1)] != ' ' && ' ' in tail) tail = tail.substring(tail.indexOf(' ') + 1)
        return tail
    }

    /** Chữ của một trang XHTML: mỗi khối (đoạn, tiêu đề, dòng danh sách, <br>) một dòng; bỏ script/style/head. */
    /** Chữ ẩn (`importers._hides`): thẻ rỗng (void) không bao giờ mở vùng ẩn - `<img aria-hidden>` không có thẻ đóng. */
    private val VOID = setOf("area", "base", "br", "col", "embed", "hr", "img", "image", "input", "link", "meta", "source", "track", "wbr")
    private val HIDDEN_TAGS = setOf("noscript", "rt", "rp") // rt / rp của ruby: cách đọc in nhỏ trên chữ gốc - đọc chữ gốc một lần
    private val HIDDEN_STYLE = Pattern.compile("display\\s*:\\s*none|visibility\\s*:\\s*hidden", Pattern.CASE_INSENSITIVE or UNICODE_CLASSES)
    private val SIMPLE_SELECTOR = Pattern.compile("([a-z][\\w-]*)?((?:[.#][\\w-]+)*)", Pattern.CASE_INSENSITIVE or UNICODE_CLASSES)
    private val SELECTOR_PART = Pattern.compile("[.#][\\w-]+", UNICODE_CLASSES)

    /** Một bộ chọn CSS đơn giản mà stylesheet trong gói ẩn đi (`importers._Hidden`): thẻ, id, các lớp - rỗng = mọi. */
    internal class Hidden(val tag: String, val id: String, val classes: Set<String>)

    /** `importers.css_hidden`: các bộ chọn đơn giản (`.lop`, `#id`, `the`, `the.lop`) mà [css] ẩn đi (`display:none` / `visibility:hidden`);
     *  bộ chọn phức tạp và mọi khối @ (@media print…) bỏ qua. */
    internal fun cssHidden(source: String): List<Hidden> {
        val css = Regex("/\\*.*?\\*/", RegexOption.DOT_MATCHES_ALL).replace(source, "")
        val found = mutableListOf<Hidden>()
        var depth = 0
        var start = 0
        var selector = ""
        for ((index, char) in css.withIndex()) {
            if (char == '{') {
                if (depth == 0) {
                    selector = pyStrip(css.substring(start, index))
                    start = index + 1
                }
                depth++
            } else if (char == '}' && depth > 0) {
                depth--
                if (depth == 0) {
                    if (!selector.startsWith("@") && HIDDEN_STYLE.matcher(css.substring(start, index)).find()) {
                        for (raw in selector.split(",")) {
                            val one = pyStrip(raw)
                            val match = SIMPLE_SELECTOR.matcher(one)
                            if (one.isEmpty() || !match.matches()) continue
                            val parts = mutableListOf<String>()
                            val partMatcher = SELECTOR_PART.matcher(match.group(2) ?: "")
                            while (partMatcher.find()) parts.add(partMatcher.group())
                            found.add(Hidden(casefold(match.group(1) ?: ""), parts.firstOrNull { it[0] == '#' }?.substring(1) ?: "",
                                parts.filter { it[0] == '.' }.map { it.substring(1) }.toSet()))
                        }
                    }
                    start = index + 1
                }
            }
        }
        return found
    }

    /** `importers._hides`: phần tử ẩn với người đọc - `hidden`, `aria-hidden="true"`, style nội tuyến display:none / visibility:hidden, <noscript>,
     *  rt / rp của ruby, số trang (epub:type="pagebreak" / role="doc-pagebreak"), hay một luật CSS đơn giản của gói. */
    private fun hides(tag: String, attrs: Map<String, String>, rules: List<Hidden>): Boolean {
        if (tag in VOID) return false
        val named = attrs.mapKeys { it.key.lowercase() }
        if (tag in HIDDEN_TAGS || "hidden" in named || pyStrip(named["aria-hidden"] ?: "").lowercase() == "true") return true
        if (HIDDEN_STYLE.matcher(named["style"] ?: "").find() || "pagebreak" in types(attrs)) return true
        val classes = (named["class"] ?: "").split(Regex("\\s+")).filter { it.isNotEmpty() }.toSet()
        return rules.any { (it.tag.isEmpty() || it.tag == tag) && (it.id.isEmpty() || it.id == named["id"]) && classes.containsAll(it.classes) }
    }

    private class PageText(private val rules: List<Hidden> = emptyList(), private val backlinksHidden: Boolean = false) {
        val lines = mutableListOf<String>()
        val spans = hashMapOf<String, Pair<Int, Int>>() // id -> [dòng đầu, dòng cuối) của khối chứa phần tử có id ấy (đích của dấu gọi chú thích)
        val notes = mutableListOf<Pair<Int, Int>>() // khoảng dòng của từng lời chú có kiểu (epub:type footnote / endnote / rearnote)
        val areas = mutableListOf<Pair<Int, Int>>() // ... của vùng toàn lời chú (epub:type endnotes…)
        val marks = mutableListOf<Mark>()
        var noteLines: Set<Int> = emptySet() // các dòng thuộc lời chú (`resolveNotes`)
        private val stack = mutableListOf<Block>()
        private val links = mutableListOf<Link>()
        var heading = ""
        val headings = mutableListOf<Pair<Int, String>>() // (dòng của tiêu đề, chữ): mọi tiêu đề h1-h3 có chữ, theo thứ tự
        val anchors = hashMapOf<String, Int>() // id / <a name> -> chỉ số dòng bắt đầu từ chỗ ấy (mục lục trỏ #mảnh vào đây)
        var images = 0
        val types = HashSet<String>() // vai (epub:type / role) của <body> và các khối bọc ngoài trước chữ đầu tiên ("frontmatter", "cover"…)
        private val current = StringBuilder()
        private var skip = 0
        private var inHeading = 0
        private var hiddenTag = "" // thẻ mở vùng ẩn đang bỏ qua, và số thẻ cùng tên đang mở bên trong nó
        private var hiddenDepth = 0
        private var cap = "" // chữ cái đầu chương vẽ bằng ảnh (<img alt="M">): chờ xem chữ ngay sau có dính liền không
        private var pre = 0 // trong <pre>: xuống dòng của nguồn là xuống dòng thật
        private val sup = mutableListOf<Int>() // chỗ (độ dài `current`) bắt đầu mỗi <sup> đang mở

        private fun flush() {
            cap = ""
            for (index in sup.indices) sup[index] = 0 // dòng mới: <sup> đang mở bắt đầu từ đầu dòng
            for (link in links) link.start = 0
            val line = words(current.toString())
            if (line.isNotEmpty()) lines.add(line)
            current.setLength(0)
        }

        private fun start(tag: String, attrs: Map<String, String>) {
            when {
                tag in SKIPPED_TAGS -> skip++
                tag == "img" || tag == "image" -> images++
                tag == "br" || tag == "hr" -> flush() // hr: ngắt cảnh - ít nhất là ranh giới đoạn
                tag in CELLS -> current.append(' ')
                tag == "sup" -> {
                    sup.add(current.length)
                    links.lastOrNull()?.sup = true
                }
                tag == "a" -> {
                    val named = attrs.mapKeys { it.key.lowercase() }
                    links.add(Link(pyStrip(named["href"] ?: ""), current.length, "noteref" in types(attrs), named["id"] ?: "", sup.isNotEmpty()))
                }
                tag in TEXT_BLOCKS -> {
                    flush()
                    if (tag in TEXT_HEADINGS) inHeading++
                    if (tag == "pre") pre++
                }
            }
        }

        private fun close(tag: String) {
            if (hiddenDepth == 0) return end(tag)
            if (tag == hiddenTag) {
                hiddenDepth--
                if (hiddenDepth == 0 && tag in TEXT_BLOCKS) flush()
            }
        }

        private fun end(tag: String) {
            when {
                tag in SKIPPED_TAGS -> skip = maxOf(0, skip - 1)
                tag in CELLS -> current.append(' ')
                tag == "sup" && sup.isNotEmpty() -> {
                    val at = sup.removeAt(sup.size - 1)
                    // Số chú thích dính vào chữ đứng trước ("thích1"): tách bằng một dấu cách (`importers._Text.handle_endtag`).
                    val mark = pyStrip(current.substring(at))
                    val unit = (mark == "2" || mark == "3") && UNIT_POWER.matcher(current.substring(0, at)).find()
                    if (NOTE_MARK.matcher(mark).matches() && at > 0 && Character.isLetter(current.codePointBefore(at)) && !unit) current.insert(at, ' ')
                }
                tag == "a" && links.isNotEmpty() -> endLink(links.removeAt(links.size - 1))
                tag in LISTS -> closeBlock(tag)
                tag in TEXT_BLOCKS -> {
                    if (tag == "pre" && pre > 0) pre--
                    if (tag in TEXT_HEADINGS && inHeading > 0) {
                        inHeading--
                        val text = words(current.toString())
                        if (text.isNotEmpty()) headings.add(lines.size to text)
                        if (heading.isEmpty()) heading = text
                    }
                    flush()
                    closeBlock(tag)
                }
            }
        }

        /** `</a>` (`importers._Text._end_link`): nếu liên kết là dấu gọi chú thích - epub:type="noteref" / role="doc-noteref", hay nhãn như số trong `<sup>`
         *  (`<sup><a href="#fn1">1</a></sup>`, `<a href="#fn1"><sup>1</sup></a>`) trỏ vào một mảnh (#id) - bọc chữ của nó trong NOTE_OPEN…NOTE_CLOSE (kèm
         *  dấu cách tách khỏi chữ đứng trước) và ghi [Mark]; có phải dấu gọi thật hay không (đích có là lời chú) còn do [resolveNotes] quyết. */
        private fun endLink(link: Link) {
            val href = link.href
            if ('#' !in href || EXTERNAL.matcher(href).lookingAt()) return
            val text = current.substring(link.start)
            val label = words(text)
            if (label.isEmpty() || cpLen(label) > NOTE_MARK_MAX) return
            if (!(link.noteref || (NOTE_LABEL.matcher(label).matches() && (link.inSup || link.sup)))) return
            val before = current.substring(0, link.start)
            val lead = if ((text.isNotEmpty() && isPySpace(text[0])) || before.isEmpty() || !Character.isLetter(before.codePointBefore(before.length)) ||
                ((label == "2" || label == "3") && UNIT_POWER.matcher(before).find())
            ) "" else " "
            current.insert(link.start, "$NOTE_OPEN${marks.size}$NOTE_SEP$lead")
            current.append(NOTE_CLOSE)
            marks.add(Mark(href, label, noteContext(before), link.id, lines.size))
        }

        /** Khối [tag] đóng: các khối mở bên trong nó (thẻ không đóng) đóng cùng; mỗi khối ghi khoảng dòng của nó cho id / kiểu lời chú. */
        private fun closeBlock(tag: String) {
            for (at in stack.indices.reversed()) {
                if (stack[at].tag == tag) {
                    while (stack.size > at) finishBlock(stack.removeAt(stack.size - 1))
                    return
                }
            }
        }

        private fun finishBlock(block: Block) {
            val end = lines.size
            if (end > block.start) {
                for (value in block.ids) spans.putIfAbsent(value, block.start to end)
                if (block.kind == 1) notes.add(block.start to end) else if (block.kind == 2) areas.add(block.start to end)
            }
        }

        /** Mảnh của thẻ: `id` của mọi phần tử, `name` của `<a>`; mảnh trùng thì lấy cái đầu. Kể cả trong vùng ẩn: mục lục trỏ vào đó vẫn là một chỗ.
         *  [own]: phần tử không nằm trong vùng ẩn - id của nó thuộc khối đang mở (đích của dấu gọi chú thích: [spans]). */
        private fun anchor(tag: String, attrs: Map<String, String>, own: Boolean = true) {
            if (skip > 0) return
            for ((key, value) in attrs) {
                val name = key.lowercase()
                if (value.isNotEmpty() && (name == "id" || (tag == "a" && name == "name"))) {
                    anchors.putIfAbsent(value, lines.size)
                    if (own && stack.isNotEmpty()) stack.last().ids.add(value)
                }
            }
        }

        fun feed(source: String) {
            for (token in Markup.tokenize(source)) {
                when (token) {
                    is Markup.Start -> {
                        val tag = token.name.lowercase()
                        if (hiddenDepth > 0) {
                            if (tag == hiddenTag) hiddenDepth++
                            anchor(tag, token.attrs, own = false)
                        } else if (skip == 0 && (hides(tag, token.attrs, rules) || (backlinksHidden && tag == "a" && "backlink" in types(token.attrs)))) {
                            // nút quay lại "↩︎" của lời chú (epub:type="backlink") ẩn khi lời chú được đặt về cuối chương
                            if (tag in TEXT_BLOCKS) flush()
                            hiddenTag = tag
                            hiddenDepth = 1
                            anchor(tag, token.attrs, own = false)
                        } else {
                            start(tag, token.attrs)
                            if (tag in TEXT_BLOCKS || tag in LISTS) {
                                val kinds = types(token.attrs)
                                stack.add(Block(tag, lines.size, mutableListOf(), if (kinds.any { it in NOTE_TYPES }) 1 else if (kinds.any { it in NOTE_AREA_TYPES }) 2 else 0))
                            }
                            if (tag == "img" || tag == "image") {
                                val alt = token.attrs["alt"] ?: ""
                                cap = if (alt.codePointCount(0, alt.length) == 1 && Character.isLetter(alt.codePointAt(0))) alt else ""
                            }
                            if (tag in WRAPPERS && lines.isEmpty() && pyStrip(current.toString()).isEmpty()) types.addAll(BookImport.types(token.attrs))
                            anchor(tag, token.attrs)
                        }
                        if (token.selfClosing) close(tag)
                    }
                    is Markup.End -> close(token.name.lowercase())
                    is Markup.Text -> if (skip == 0 && hiddenDepth == 0) {
                        // Chữ cái đầu là ảnh ("M" + "ọi chuyện…"): chỉ ghép khi chữ ngay sau dính liền (`importers._Text.handle_data`).
                        if (cap.isNotEmpty() && token.text.isNotEmpty()) {
                            if (Character.isLetter(token.text.codePointAt(0))) current.append(cap)
                            cap = ""
                        }
                        if (pre > 0) {
                            val parts = token.text.split("\n")
                            current.append(parts[0])
                            for (line in parts.drop(1)) {
                                flush()
                                current.append(line)
                            }
                        } else {
                            current.append(token.text)
                        }
                    }
                }
            }
            flush()
            while (stack.isNotEmpty()) finishBlock(stack.removeAt(stack.size - 1))
        }
    }

    /** `importers._types`: vai của một phần tử - các từ của `epub:type` (`type` có tiền tố; `<ol type="a">` không tính) và của `role` bỏ
     *  tiền tố "doc-". [attrs] của [Markup]: tên có tiền tố có mặt cả dạng đầy đủ ("epub:type") lẫn dạng bỏ tiền tố. */
    internal fun types(attrs: Map<String, String>): Set<String> {
        val found = HashSet<String>()
        for ((key, value) in attrs) {
            val local = key.substringAfterLast(':').lowercase()
            if (value.isNotEmpty() && ((local == "type" && ':' in key) || local == "role")) {
                for (token in value.split(Regex("\\s+"))) if (token.isNotEmpty()) found.add(token.lowercase().removePrefix("doc-"))
            }
        }
        return found
    }

    /** Phần không phải truyện (`importers.MATTER_TYPES`): epub:type / role của trang -> lý do; cụ thể trước, chung sau. */
    private val MATTER_TYPES = listOf(
        "cover" to "Trang bìa", "titlepage" to "Trang tên sách", "halftitlepage" to "Trang tên sách", "copyright-page" to "Trang bản quyền",
        "imprint" to "Trang bản quyền", "colophon" to "Trang bản quyền", "toc" to "Mục lục", "landmarks" to "Mục lục",
        "endnotes" to "Chú thích", "footnotes" to "Chú thích", "rearnotes" to "Chú thích",
        "frontmatter" to "Phần đầu sách", "backmatter" to "Phần cuối sách",
    )
    private val MATTER_NAMES = linkedMapOf(
        "cover" to "Trang bìa", "title" to "Trang tên sách", "titlepage" to "Trang tên sách", "toc" to "Mục lục", "nav" to "Mục lục",
        "copyright" to "Trang bản quyền", "license" to "Trang bản quyền", "colophon" to "Trang bản quyền", "imprint" to "Trang bản quyền",
        "about" to "Trang giới thiệu", "endnotes" to "Chú thích", "footnotes" to "Chú thích",
    )
    private val MATTER_NAME = Pattern.compile("[\\W_\\d]*(" + MATTER_NAMES.keys.joinToString("|") + ")(?:[\\W_]*page)?[\\W_\\d]*", UNICODE_CLASSES)
    private val TOC_TITLES = setOf("mục lục", "muc luc", "contents", "table of contents")
    private val NOTE_TITLES = setOf("chú thích", "endnotes", "end notes", "footnotes", "notes") // tên chương toàn lời chú
    private val TOC_SUFFIX = Pattern.compile("\\s+[—–-]\\s*(?:mục lục|muc luc)\\s*$", Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or UNICODE_CLASSES)
    private const val MATTER_HEAD = 400

    /** `importers.name_matter`: lý do "không phải truyện" theo tên file trong gói EPUB; "" nếu không. */
    internal fun nameMatter(href: String): String {
        val matcher = MATTER_NAME.matcher(casefold(stemOf(href.substringAfterLast('/'))))
        return if (matcher.matches()) MATTER_NAMES.getValue(matcher.group(1)) else ""
    }

    /** `importers.text_matter`: lý do "không phải truyện" theo chữ - tên / dòng đầu là "Mục lục", "Contents"; lời của Project Gutenberg hay
     *  Wikisource ở đầu chương. "" nếu không. */
    internal fun textMatter(title: String, text: String): String {
        val head = casefold(title + "\n" + text.substring(0, text.offsetByCodePoints(0, minOf(MATTER_HEAD, cpLen(text)))))
        val first = casefold(firstTextLine(text)).trimEnd(' ', ':', '.')
        val clean = pyStrip(casefold(title))
        return when {
            clean in TOC_TITLES || first in TOC_TITLES || clean.endsWith("— mục lục") || clean.endsWith("- mục lục") -> "Mục lục"
            clean in NOTE_TITLES || first in NOTE_TITLES -> "Chú thích"
            "project gutenberg" in head -> "Trang của Project Gutenberg"
            "wikisource" in head -> "Trang của Wikisource"
            else -> ""
        }
    }

    private class ManifestItem(val href: String, val media: String, val props: String)

    private fun tokens(props: String) = props.split(Regex("\\s+")).filter { it.isNotEmpty() }

    /** Một dòng của mục lục: file (không #), mảnh sau # (rỗng nếu không có), tên. */
    private class TocEntry(val href: String, val fragment: String, val label: String)

    /** Mục lục theo thứ tự (`importers._toc`): EPUB3 nav trước, EPUB2 NCX sau. Kèm: gói CÓ khai báo mục lục hay không. Tệp mục lục hỏng
     *  hay thiếu không làm hỏng cả cuốn - chữ vẫn đọc theo spine, chỉ mất tên chương của mục lục. */
    private fun toc(zip: ZipFile, manifest: Map<String, ManifestItem>, spineToc: String): Pair<List<TocEntry>, Boolean> {
        val entries = mutableListOf<TocEntry>()
        fun add(base: String, target: String, label: String) {
            entries.add(TocEntry(normpath(join(base, unquote(target.substringBefore('#')))), unquote(target.substringAfter('#', "")), label))
        }
        val nav = manifest.values.firstOrNull { "nav" in tokens(it.props) }?.href ?: ""
        tocRoot(zip, nav)?.let { root ->
            val navDir = dirname(nav)
            // Tệp nav có nhiều <nav>: mục lục (epub:type="toc"), mốc (landmarks), số trang (page-list) - chỉ mục lục là chương (`importers._toc`).
            val navs = root.descendants().filter { it.local == "nav" }.toList()
            val listing = navs.firstOrNull { "toc" in types(it.attrs) } ?: navs.firstOrNull() ?: root
            for (anchor in listing.descendants().filter { it.local == "a" }) {
                val href = anchor.attr("href") ?: ""
                val label = words(anchor.allText())
                if (href.isNotEmpty() && label.isNotEmpty()) add(navDir, href, label)
            }
        }
        val ncx = manifest[spineToc]?.href?.takeIf { it.isNotEmpty() }
            ?: manifest.values.firstOrNull { it.media == "application/x-dtbncx+xml" }?.href ?: ""
        (if (entries.isEmpty()) tocRoot(zip, ncx) else null)?.let { root ->
            val ncxDir = dirname(ncx)
            for (point in root.descendants().filter { it.local == "navPoint" }) {
                val label = point.child("navLabel")?.child("text")
                val content = point.child("content")
                if (label != null && content != null && pyStrip(label.text).isNotEmpty()) add(ncxDir, content.attr("src") ?: "", words(label.text))
            }
        }
        // Nút cha trỏ cùng chỗ với nút con đầu ("Quyển một" và "Chương 12" cùng trỏ c1.xhtml): tên chương là tên nút con (`importers._toc`).
        val kept = entries.filterIndexed { index, entry ->
            val next = entries.getOrNull(index + 1)
            next == null || next.href != entry.href || next.fragment != entry.fragment
        }
        return kept to (nav.isNotEmpty() || ncx.isNotEmpty())
    }

    /** Tệp mục lục [href] đã đọc; không khai báo, thiếu trong gói hay hỏng: null (`importers._toc_root`). */
    private fun tocRoot(zip: ZipFile, href: String): Markup.Node? =
        if (href.isEmpty()) null else try {
            xml(zip, href, "EPUB", strict = true)
        } catch (_: Failed) {
            null
        }

    /**
     * Một file chứa nhiều chương (`importers._split_points`): các mục lục (mảnh, tên) trỏ vào file này -> (dòng bắt đầu, tên) theo thứ tự đọc.
     * Chỉ tính mục không mảnh (đầu file) và mục có mảnh mà trang thật sự có; dưới hai điểm thì không tách (danh sách rỗng).
     */
    private fun splitPoints(page: PageText, entries: List<TocEntry>): List<Pair<Int, String>> {
        val points = mutableListOf<Pair<Int, String>>()
        val seen = hashSetOf<String>()
        for (entry in entries) {
            if (!seen.add(entry.fragment)) continue
            if (entry.fragment.isEmpty()) points.add(0 to entry.label) else page.anchors[entry.fragment]?.let { points.add(it to entry.label) }
        }
        return if (points.size >= 2 && page.lines.isNotEmpty()) points.sortedBy { it.first } else emptyList()
    }

    /** Một chương cắt từ trang: dòng [start, end) của trang, tiêu đề trong chữ, tên mục lục. */
    private class Part(val start: Int, val end: Int, val heading: String, val listed: String)

    /** Một lời chú trong sách (`importers._Unit`): các dòng của trang [page], và các dấu gọi trỏ tới nó theo thứ tự đọc. */
    private data class Key(val page: Int, val start: Int, val end: Int) : Comparable<Key> {
        override fun compareTo(other: Key) = compareValuesBy(this, other, Key::page, Key::start, Key::end)
    }

    private class Ref(val page: Int, val line: Int, val number: Int)

    private class NoteUnit(val key: Key) {
        val refs = mutableListOf<Ref>()
    }

    private class Notes(val found: Int, val marks: Int) {
        val examples = mutableListOf<Pair<String, String>>()
        val byPage = hashMapOf<Int, MutableList<NoteUnit>>() // trang -> lời chú nằm ở trang ấy
        val byDest = hashMapOf<Int, MutableList<NoteUnit>>() // trang -> lời chú có dấu gọi đầu tiên ở trang ấy (theo thứ tự đọc)
    }

    private val REF_ORDER = compareBy<Ref>({ it.page }, { it.line }, { it.number })

    /**
     * Chú thích của cả cuốn EPUB (`importers._resolve_notes`; mọi trang đã đọc, theo thứ tự đọc): dấu gọi nào trỏ tới lời chú nào (cùng trang hay trang khác),
     * lời chú là các dòng nào ([PageText.noteLines]), vài ví dụ cho bước xem trước. Gỡ NOTE_OPEN…NOTE_CLOSE khỏi chữ: dấu gọi đã nhận ra được bỏ chữ khi
     * [hideMarks], còn lại giữ nguyên. Không bỏ dòng nào - chỉ số dòng của mọi trang vẫn như cũ (mục lục còn trỏ vào đó).
     */
    private fun resolveNotes(entries: List<Pair<String, PageText>>, hideMarks: Boolean): Notes {
        val spans = hashMapOf<Pair<String, String>, Key>()
        val markIds = hashSetOf<Pair<String, String>>()
        val typed = hashSetOf<Key>()
        for ((at, entry) in entries.withIndex()) {
            val (path, page) = entry
            for ((name, span) in page.spans) spans.putIfAbsent(path to name, Key(at, span.first, span.second))
            for (mark in page.marks) if (mark.id.isNotEmpty()) markIds.add(path to mark.id)
            for ((start, end) in page.notes) typed.add(Key(at, start, end))
        }
        val headingLines = entries.map { (_, page) -> page.headings.map { it.first }.toSet() }
        val refs = linkedMapOf<Key, MutableList<Ref>>()
        val resolved = entries.map { linkedMapOf<Int, Key>() } // trang -> {số thứ tự dấu gọi: lời chú}
        for ((at, entry) in entries.withIndex()) {
            val (path, page) = entry
            val inside = page.notes + page.areas // dấu trong một lời chú (nhãn "1" quay lại chỗ gọi) không phải dấu gọi
            for ((number, mark) in page.marks.withIndex()) {
                if (inside.any { (start, end) -> mark.line in start until end }) continue
                val target = mark.href.substringBefore('#')
                val fragment = unquote(mark.href.substringAfter('#', ""))
                val where = if (target.isNotEmpty()) normpath(join(dirname(path), unquote(target))) else path
                val found = (if (fragment.isNotEmpty() && (where to fragment) !in markIds) spans[where to fragment] else null) ?: continue
                if (found !in typed && (found.end - found.start > MAX_NOTE_LINES || headingLines[found.page].any { it in found.start until found.end })) continue
                if (found.page == at && mark.line in found.start until found.end) continue
                refs.getOrPut(found) { mutableListOf() }.add(Ref(at, mark.line, number))
                resolved[at][number] = found
            }
        }
        // Lời chú nằm gọn trong lời chú khác (<aside epub:type="footnote"><p id="fn1">…) thì là một: lấy khối ngoài; dấu gọi trỏ vào khối trong về khối ngoài.
        val outer = hashMapOf<Key, Key>()
        val keysByPage = hashMapOf<Int, MutableList<Key>>()
        for (key in typed + refs.keys) keysByPage.getOrPut(key.page) { mutableListOf() }.add(key)
        for (keys in keysByPage.values) {
            var top: Key? = null
            for (key in keys.sortedWith(compareBy<Key>({ it.start }, { -it.end }))) {
                val above = top
                if (above != null && key.end <= above.end) {
                    outer[key] = above
                } else {
                    top = key
                    outer[key] = key
                }
            }
        }
        val units = linkedMapOf<Key, NoteUnit>()
        for (key in outer.values.toSortedSet()) units[key] = NoteUnit(key)
        for ((key, marks) in refs) units.getValue(outer.getValue(key)).refs.addAll(marks)
        val notes = Notes(units.size, resolved.sumOf { it.size })
        for (unit in units.values) {
            unit.refs.sortWith(REF_ORDER)
            notes.byPage.getOrPut(unit.key.page) { mutableListOf() }.add(unit)
            if (unit.refs.isNotEmpty()) notes.byDest.getOrPut(unit.refs[0].page) { mutableListOf() }.add(unit)
        }
        for (listed in notes.byDest.values) listed.sortWith { a, b -> REF_ORDER.compare(a.refs[0], b.refs[0]) }
        for ((at, entry) in entries.withIndex()) {
            val page = entry.second
            for (number in page.lines.indices) {
                val line = page.lines[number]
                if (NOTE_OPEN in line) {
                    page.lines[number] = squeeze(NOTE_SPAN.replace(line) { match ->
                        if (hideMarks && match.groupValues[1].toInt() in resolved[at]) "" else match.groupValues[2]
                    })
                }
            }
            val flagged = hashSetOf<Int>()
            for (unit in notes.byPage[at].orEmpty()) for (line in unit.key.start until unit.key.end) flagged.add(line)
            for ((start, end) in page.areas) for (line in start until end) if (line !in headingLines[at]) flagged.add(line)
            page.noteLines = flagged
        }
        val seen = hashSetOf<Key>()
        for ((at, entry) in entries.withIndex()) {
            for ((number, mark) in entry.second.marks.withIndex()) {
                val key = resolved[at][number]?.let { outer.getValue(it) }
                if (key == null || key in seen || notes.examples.size >= NOTE_EXAMPLES) continue
                seen.add(key)
                val core = mark.label.trim { it in "[]()" }
                val joined = pyStrip(entries[key.page].second.lines.subList(key.start, key.end).joinToString(" "))
                val text = Pattern.compile("^[\\[(]?" + Pattern.quote(core) + "[\\])]?[.:)]?\\s+", UNICODE_CLASSES).matcher(joined).replaceFirst("")
                    .trim { it in " \u00a0\u21a9\ufe0e\ufe0f" }
                if (text.isNotEmpty()) {
                    val sup = if (core.isNotEmpty() && core.all { Character.isDigit(it) || it in SUPERSCRIPT }) superscript(core) else mark.label
                    notes.examples.add(((if (mark.before.isNotEmpty()) "…" + mark.before else "") + sup) to clipTitle(text, NOTE_EXAMPLE_WIDTH))
                }
            }
        }
        return notes
    }

    /** `importers._notes_only`: trang chỉ có lời chú (và tiêu đề của nó) - chương "Endnotes": có cờ "Chú thích", không bỏ. */
    private fun notesOnly(page: PageText): Boolean {
        val headings = page.headings.map { it.first }.toSet()
        return page.noteLines.any { page.lines[it].isNotEmpty() } &&
            page.lines.withIndex().all { (line, text) -> line in page.noteLines || line in headings || text.isEmpty() }
    }

    private class PartLines(val body: List<String>, val tail: List<String>, val removed: Boolean)

    /**
     * Các dòng [start, end) của trang [at] (một chương hay cả trang) thành thân + lời chú ở cuối + có lời chú bị bỏ / dời đi (`importers._part_lines`).
     * Lời chú nằm giữa chương đứng ở CUỐI chương, theo thứ tự trong trang - chữ không đổi, chỉ đổi chỗ. [mode]: "" như trên; "end" - lời chú của mọi dấu
     * gọi trong chương này, cả lời chú ở trang khác (chương Endnotes), theo thứ tự dấu gọi; "drop" - bỏ lời chú.
     */
    private fun partLines(entries: List<Pair<String, PageText>>, notes: Notes, at: Int, start: Int, end: Int, mode: String): PartLines {
        val page = entries[at].second
        val lines = page.lines
        val flagged = page.noteLines
        val body = (start until end).filter { it !in flagged }.map { lines[it] }
        val tail = mutableListOf<String>()
        val touched = (start until end).any { it in flagged }
        if (mode == "end") {
            val covered = hashSetOf<Int>()
            for (unit in notes.byPage[at].orEmpty()) {
                if (unit.refs.isNotEmpty() && unit.key.start in start until end) for (line in unit.key.start until unit.key.end) covered.add(line)
            }
            for (unit in notes.byDest[at].orEmpty()) {
                if (unit.refs[0].line in start until end) tail.addAll(entries[unit.key.page].second.lines.subList(unit.key.start, unit.key.end))
            }
            for (line in start until end) if (line in flagged && line !in covered) tail.add(lines[line])
        } else if (mode != "drop") {
            for (line in start until end) if (line in flagged) tail.add(lines[line])
        }
        return PartLines(body.filter { it.isNotEmpty() }, tail.filter { it.isNotEmpty() }, touched && (mode == "end" || mode == "drop"))
    }

    private fun epubCover(zip: ZipFile, opf: Markup.Node, manifest: Map<String, ManifestItem>): Pair<ByteArray, String>? {
        var href = manifest.values.firstOrNull { "cover-image" in tokens(it.props) }?.href ?: ""
        if (href.isEmpty()) {
            val meta = opf.child("metadata")?.children?.firstOrNull { it.local == "meta" && it.attr("name") == "cover" }
            href = if (meta != null) manifest[meta.attr("content") ?: ""]?.href ?: "" else ""
        }
        val media = manifest.values.firstOrNull { it.href == href }?.media ?: ""
        if (href.isEmpty() || !media.startsWith("image/")) return null
        val entry = member(zip, href) ?: return null
        if (entry.size > MAX_COVER) return null
        return zip.getInputStream(entry).use { it.readBytes() } to media
    }

    private fun epub(file: File, choice: FootnoteChoice): Book = openZip(file, "EPUB").use { zip ->
        val container = xml(zip, "META-INF/container.xml", "EPUB")
        val opfPath = container.descendants().firstOrNull { it.local == "rootfile" }?.attr("full-path")
        if (opfPath.isNullOrEmpty()) throw broken("EPUB")
        val opf = xml(zip, opfPath, "EPUB")
        val opfDir = dirname(opfPath)
        val manifest = linkedMapOf<String, ManifestItem>()
        for (item in opf.child("manifest")?.children.orEmpty().filter { it.local == "item" }) {
            manifest[item.attr("id") ?: ""] = ManifestItem(
                normpath(join(opfDir, unquote(item.attr("href") ?: ""))), item.attr("media-type") ?: "", item.attr("properties") ?: "",
            )
        }
        val spine = opf.child("spine") ?: throw broken("EPUB")
        val (tocEntries, declared) = toc(zip, manifest, spine.attr("toc") ?: "")
        val titles = linkedMapOf<String, String>() // file -> tên đầu tiên trỏ tới nó
        for (entry in tocEntries) titles.putIfAbsent(entry.href, entry.label)
        val listedIn = tocEntries.groupBy { it.href }
        val result = Book(metaText(opf, "title") ?: titleFromFilename(stemOf(file.name)), author = metaText(opf, "creator"), language = metaText(opf, "language"))
        if (declared && tocEntries.isEmpty()) result.notes.add("Mục lục trong file không đọc được - tên chương lấy từ chữ của từng chương.")
        epubCover(zip, opf, manifest)?.let { (bytes, media) ->
            result.cover = bytes
            result.coverType = media
        }
        // Có mục lục thì file của thứ tự đọc không có mục nào, không phải phần đầu / cuối sách và không mở bằng tiêu đề riêng là PHẦN SAU của
        // chương trước (Calibre cắt chương dài thành index_split_001, _002…) - nối vào (`importers._epub`).
        val hasToc = spine.children.any { it.local == "itemref" && manifest[it.attr("idref") ?: ""]?.href in titles }
        val hidden = manifest.values.filter { it.media == "text/css" && member(zip, it.href) != null }
            .flatMap { cssHidden(String(read(zip, it.href, "EPUB"), Charsets.UTF_8)) }
        var images = 0 // trang chỉ có ảnh: một ghi chú đếm, không kể tên file trong gói (mục rất ngắn: `finish` đếm)
        var missing = 0 // mục của thứ tự đọc mà gói không có (tải chưa trọn): bỏ qua + đếm, phần còn lại vẫn đọc được
        val entries = mutableListOf<Pair<String, PageText>>() // (đường trong gói, trang) theo thứ tự đọc: chú thích cần nhìn cả cuốn trước khi dựng chương
        for (itemref in spine.children.filter { it.local == "itemref" }) {
            if ((itemref.attr("linear") ?: "yes") == "no") continue
            val item = manifest[itemref.attr("idref") ?: ""] ?: ManifestItem("", "", "")
            if (item.href.isEmpty() || "nav" in tokens(item.props) || !item.media.contains("html")) continue
            if (member(zip, item.href) == null) {
                missing++
                continue
            }
            entries.add(item.href to PageText(hidden, choice.notes == "end").also { it.feed(markupText(read(zip, item.href, "EPUB"))) })
        }
        val notes = resolveNotes(entries, choice.hideMarks)
        result.footnoteFound = notes.found
        result.footnoteMarks = notes.marks
        result.footnoteExamples.addAll(notes.examples)
        val stored = mutableListOf<Pair<List<String>, List<String>>>() // thân + lời chú ở cuối của từng chương trong `result.chapters` (nối file sau vào chương trước)
        for ((at, entry) in entries.withIndex()) {
            val (href, page) = entry
            // Nhiều chương trong MỘT file: mục lục trỏ vào các mảnh (#id) của file này thì cắt chữ tại các mảnh ấy, theo thứ tự đọc,
            // mỗi phần mang tên của mục lục. Chữ trước mảnh đầu là phần riêng (không tên) nếu không mục nào trỏ về đầu file.
            val points = splitPoints(page, listedIn[href].orEmpty()).toMutableList()
            val parts = if (points.isNotEmpty()) {
                if (points[0].first > 0) points.add(0, 0 to "")
                points.mapIndexed { index, (start, label) ->
                    val end = if (index + 1 < points.size) points[index + 1].first else page.lines.size
                    Part(start, end, page.headings.firstOrNull { it.first in start until end }?.second ?: "", label)
                }
            } else {
                listOf(Part(0, page.lines.size, page.heading, titles[href] ?: ""))
            }
            val pageMatter = MATTER_TYPES.firstOrNull { it.first in page.types }?.second
                ?: nameMatter(href).ifEmpty { if (points.isEmpty() && notesOnly(page)) "Chú thích" else "" }
            for (part in parts) {
                val taken = partLines(entries, notes, at, part.start, part.end, choice.notes)
                var body = taken.body
                var tail = taken.tail
                var lines = body + tail
                val heading = part.heading
                val listed = part.listed
                if (hasToc && points.isEmpty() && listed.isEmpty() && pageMatter.isEmpty() && page.heading.isEmpty() && lines.isNotEmpty() &&
                    !isHeadingLine(lines[0]) && textMatter("", lines.joinToString("\n\n")).isEmpty() &&
                    result.chapters.isNotEmpty() && result.chapters.last().matter.isEmpty()
                ) {
                    val merged = Pair(stored.last().first + body, stored.last().second + tail)
                    stored[stored.size - 1] = merged
                    val last = result.chapters.removeAt(result.chapters.size - 1)
                    result.chapters.add(Chapter(last.title, (merged.first + merged.second).filter { it.isNotEmpty() }.joinToString("\n\n"), last.short, last.name, last.matter))
                    continue
                }
                if (lines.isEmpty() && page.images > 0 && points.isEmpty() && !taken.removed) {
                    images++
                    continue
                }
                if (lines.isEmpty()) continue
                val isShort = lines.sumOf { cpLen(it) } < MIN_CHARS && listed.isEmpty() // bìa, trang bản quyền: `finish` bỏ, hay để người dùng tích
                var title = listed.ifEmpty { heading.ifEmpty { clipTitle(lines[0], TITLE_FROM_LINE) } }
                val first = casefold(lines[0])
                // Dòng đầu là tiêu đề của chính chương: bỏ khi nó đã nằm trong tên chương ("Gặp gỡ" trong "Chương 2: Gặp gỡ"),
                // hay lấy nó làm tên khi nó đầy đủ hơn tên mục lục - không để người nghe nghe tên chương hai lần.
                if (first == casefold(title) || (heading.isNotEmpty() && first == casefold(heading) && casefold(title).contains(first))) {
                    lines = lines.drop(1)
                    if (body.isNotEmpty()) body = body.drop(1) else tail = tail.drop(1)
                } else if (heading.isNotEmpty() && first == casefold(heading) && first.contains(casefold(title))) {
                    title = lines[0]
                    lines = lines.drop(1)
                    if (body.isNotEmpty()) body = body.drop(1) else tail = tail.drop(1)
                }
                if (taken.removed && lines.isEmpty()) continue // trang chỉ có lời chú (chương Endnotes) mà lời chú đã đặt về chương của chúng / bị bỏ: không còn gì
                result.chapters.add(Chapter(title, lines.joinToString("\n\n"), short = isShort, matter = pageMatter))
                stored.add(body to tail)
            }
        }
        if (images > 0) result.notes.add("Bỏ qua $images trang chỉ có ảnh.")
        if (missing > 0) result.notes.add("Bỏ qua $missing phần bị thiếu trong file (file có thể tải chưa trọn).")
        result
    }

    // ---- DOCX ----------------------------------------------------------------------------------------------------------

    /** Tên kiểu (viết thường) của mục lục Word tự sinh (`importers.TOC_STYLE`). */
    private val TOC_STYLE = Regex("toc ?\\d|toc ?heading")

    private fun docxStyles(zip: ZipFile): Map<String, String> {
        val root = try {
            xml(zip, "word/styles.xml", "DOCX")
        } catch (_: Failed) {
            return emptyMap()
        }
        val styles = HashMap<String, String>()
        for (style in root.descendants().filter { it.name == "w:style" }) {
            val name = style.children.firstOrNull { it.name == "w:name" } ?: continue
            styles[style.attr("styleId") ?: ""] = casefold(name.attr("val") ?: "")
        }
        return styles
    }

    /** Mọi đoạn theo thứ tự trong file, kể cả trong bảng và khung chữ; bỏ bản dự phòng (mc:Fallback lặp lại khung chữ). */
    private fun docxParagraphs(element: Markup.Node): Sequence<Markup.Node> = sequence {
        for (child in element.children) {
            if (child.name == "mc:Fallback") continue
            if (child.name == "w:p") yield(child)
            yieldAll(docxParagraphs(child))
        }
    }

    /** Các dòng của một đoạn: xuống dòng cứng (Shift+Enter) tách dòng; tab = khoảng trắng; chữ đã xoá (w:delText) không có mặt. */
    private fun docxText(element: Markup.Node): List<String> {
        val lines = mutableListOf("")
        for (child in element.children) {
            when (child.name) {
                "w:pPr", "w:p", "w:txbxContent", "mc:Fallback" -> continue
                "w:t" -> lines[lines.size - 1] += child.text
                "w:tab" -> lines[lines.size - 1] += " "
                "w:noBreakHyphen" -> lines[lines.size - 1] += "-"
                // chữ của lời chú ở footnotes.xml / endnotes.xml: giữ chỗ để biết dấu gọi ở đâu
                "w:footnoteReference", "w:endnoteReference" ->
                    lines[lines.size - 1] += NOTE_OPEN + (if (child.name == "w:footnoteReference") "f" else "e") + (child.attr("id") ?: "") + NOTE_CLOSE
                "w:br" -> if ((child.attr("type") ?: "textWrapping") == "textWrapping") lines.add("") else {
                    val nested = docxText(child)
                    lines[lines.size - 1] += nested[0]
                    lines.addAll(nested.drop(1))
                }
                else -> {
                    val nested = docxText(child)
                    lines[lines.size - 1] += nested[0]
                    lines.addAll(nested.drop(1))
                }
            }
        }
        return lines
    }

    /** Xuống dòng cứng giữa câu (chữ dán từ web/PDF) -> nối lại, kẻo câu bị đọc thành hai đoạn. Chỉ nối khi dòng trước chưa hết
     *  câu và dòng sau mở đầu bằng chữ thường; thơ, thoại từng dòng giữ nguyên. Giống `_join_wrapped` của máy tính. */
    private fun joinWrapped(lines: List<String>): List<String> {
        val joined = mutableListOf<String>()
        for (line in lines) {
            val previous = joined.lastOrNull() ?: ""
            if (previous.isNotEmpty() && line.isNotEmpty() && line[0].isLowerCase() && previous.last() !in SENTENCE_END && previous.last() !in ":;") {
                joined[joined.size - 1] = if (previous.last() == SOFT_HYPHEN) previous.dropLast(1) + line else "$previous $line"
            } else {
                joined.add(line)
            }
        }
        return joined
    }

    // `importers.HEADING_LEVELS` / `BOLD_ROMAN` / `TITLE_PAGE_LINES` / `TITLE_PAGE_WIDTH`.
    private val HEADING_LEVELS = mapOf("heading 1" to 1, "heading1" to 1, "heading 2" to 2, "heading2" to 2)
    private val BOLD_ROMAN = Pattern.compile("\\s*[IVXLC]+\\.\\s+\\S", UNICODE_CLASSES)
    private const val TITLE_PAGE_LINES = 3
    private const val TITLE_PAGE_WIDTH = 80

    /** Mọi đoạn chạy có chữ trong đoạn đều in đậm (w:b, không phải w:val="0") - `importers._docx_bold`. */
    private fun docxBold(paragraph: Markup.Node): Boolean {
        val runs = paragraph.descendants().filter { it.name == "w:r" }
            .filter { run -> pyStrip(run.descendants().filter { it.name == "w:t" }.joinToString("") { it.text }).isNotEmpty() }.toList()
        return runs.isNotEmpty() && runs.all { run ->
            val node = run.children.firstOrNull { it.name == "w:rPr" }?.children?.firstOrNull { it.name == "w:b" }
            node != null && casefold(node.attr("val") ?: "true") !in setOf("0", "false", "off")
        }
    }

    /** `importers.title_page`: chữ trước chương đầu chỉ là trang tên sách / tác giả - vài dòng ngắn, không dòng nào kết thúc câu. */
    internal fun titlePage(text: String): Boolean {
        val lines = text.split("\n\n").filter { pyStrip(it).isNotEmpty() }
        return lines.size in 1..TITLE_PAGE_LINES && lines.all { line ->
            val end = pyRstrip(line)
            cpLen(line) <= TITLE_PAGE_WIDTH && listOf(".", "!", "?", "…", "。").none { end.endsWith(it) }
        }
    }

    /** Một dòng của tài liệu Word: cấp tiêu đề (0 là chữ thường), dòng, cả đoạn in đậm, là lời chú đặt về cuối chương. */
    private class Item(val level: Int, val line: String, val bold: Boolean, val note: Boolean)

    /** `importers._docx_notes`: lời chú Word {("f" | "e", id): các dòng} từ word/footnotes.xml và word/endnotes.xml (bỏ separator / continuationSeparator).
     *  Phần hỏng hay thiếu: bỏ qua. */
    private fun docxNotes(zip: ZipFile): Map<Pair<String, String>, List<String>> {
        val notes = hashMapOf<Pair<String, String>, List<String>>()
        for ((key, kind, part) in listOf(Triple("f", "w:footnote", "word/footnotes.xml"), Triple("e", "w:endnote", "word/endnotes.xml"))) {
            if (member(zip, part) == null) continue
            val root = try {
                xml(zip, part, "DOCX")
            } catch (_: Failed) {
                continue
            }
            for (note in root.descendants().filter { it.name == kind }) {
                if ((note.attr("type") ?: "normal") != "normal") continue
                val lines = docxParagraphs(note).flatMap { paragraph -> docxText(paragraph).map { words(it) } }.filter { it.isNotEmpty() }.toList()
                if (lines.isNotEmpty()) notes[key to (note.attr("id") ?: "")] = lines
            }
        }
        return notes
    }

    private fun docx(file: File, choice: FootnoteChoice): Book = openZip(file, "DOCX").use { zip ->
        val document = xml(zip, "word/document.xml", "DOCX")
        val styles = docxStyles(zip)
        val wordNotes = docxNotes(zip)
        var metaTitle: String? = null
        var metaAuthor: String? = null
        var metaLanguage: String? = null
        if (zip.getEntry("docProps/core.xml") != null) {
            val core = xml(zip, "docProps/core.xml", "DOCX")
            metaTitle = metaText(core, "title")
            metaAuthor = metaText(core, "creator")
            metaLanguage = metaText(core, "language")
        }
        val body = document.children.firstOrNull { it.name == "w:body" } ?: throw broken("DOCX")
        val items = mutableListOf<Item>()
        var bookTitle: String? = null
        var tocLines = 0
        val cited = hashSetOf<Pair<String, String>>() // lời chú đã có dấu gọi (mỗi lời chú một lần)
        val examples = mutableListOf<Pair<String, String>>()
        var references = 0 // số dấu gọi đã gặp: số thứ tự Word đánh cho chú thích
        for (paragraph in docxParagraphs(body)) {
            val styleNode = paragraph.children.firstOrNull { it.name == "w:pPr" }?.children?.firstOrNull { it.name == "w:pStyle" }
            val styleId = styleNode?.attr("val") ?: ""
            val style = styles[styleId] ?: casefold(styleId)
            if (TOC_STYLE.matches(style)) {
                // Mục lục Word tự sinh (kiểu "toc 1".."toc 9"): không phải chữ của truyện, và dòng "Chương N … 3" của nó sẽ bị nhận
                // nhầm là tiêu đề chương.
                tocLines++
                continue
            }
            val level = HEADING_LEVELS[style] ?: 0
            val bold = docxBold(paragraph)
            for (raw in joinWrapped(docxText(paragraph).map { words(it) })) {
                val line = DOCX_REF.replace(raw, "")
                val cites = mutableListOf<Pair<String, String>>()
                for (match in DOCX_REF.findAll(raw)) {
                    val key = match.groupValues[1] to match.groupValues[2]
                    references++
                    val noteLines = wordNotes[key]
                    if (noteLines != null && key !in cited) {
                        cited.add(key)
                        cites.add(key)
                        if (examples.size < NOTE_EXAMPLES) {
                            val before = noteContext(DOCX_REF.replace(raw.substring(0, match.range.first), ""))
                            examples.add(((if (before.isNotEmpty()) "…$before" else "") + superscript(references.toString())) to clipTitle(noteLines.joinToString(" "), NOTE_EXAMPLE_WIDTH))
                        }
                    }
                }
                if (line.isNotEmpty()) {
                    if (level == 0 && style == "title" && bookTitle == null) bookTitle = line
                    items.add(Item(level, line, bold, false))
                }
                // lời chú Word (chưa từng vào sách): đề xuất, tích mới đưa về cuối chương chứa dấu gọi
                if (choice.notes == "end") for (key in cites) for (text in wordNotes.getValue(key)) items.add(Item(0, text, false, true))
            }
        }
        val levels = items.map { it.level }.filter { it != 0 }
        var lines: List<Item> = items.toList()
        val chapterLevels = when {
            // Heading 1 duy nhất, ở đầu, không phải "Chương N": tên sách. Chương theo cấp kế (Heading 2), không có thì dòng "Chương N" / đậm.
            levels.count { it == 1 } == 1 && items.size > 1 && items[0].level == 1 && !isHeadingLine(items[0].line) -> {
                bookTitle = bookTitle ?: items[0].line
                lines = items.drop(1)
                setOf(2)
            }
            1 in levels && 2 in levels -> setOf(1) // Heading 1 là chương, Heading 2 là cảnh trong chương: một dòng của chương
            else -> setOf(1, 2)
        }
        val result = Book(metaTitle ?: bookTitle ?: titleFromFilename(stemOf(file.name)), author = metaAuthor, language = metaLanguage)
        result.footnoteFound = cited.size
        result.footnoteExamples.addAll(examples)
        if (tocLines > 0) result.notes.add("Bỏ qua mục lục của tài liệu ($tocLines dòng).")
        if (lines.none { it.level in chapterLevels }) {
            // Không có kiểu Heading: tách theo dòng "Chương N" (như PDF), và dòng in đậm "I. KHỞI ĐẦU" khi có từ hai dòng như thế.
            val roman = lines.indices.filter { lines[it].bold && isHeadingLine(lines[it].line, BOLD_ROMAN) }
            val (chapters, notes) = splitOnHeadings(
                lines.map { it.line }, result.title, if (roman.size >= 2) roman.toSet() else emptySet(), lines.indices.filter { lines[it].note }.toSet(),
            )
            result.chapters.addAll(chapters)
            result.notes.addAll(notes)
        } else {
            class Section(val title: String?, val paragraphs: MutableList<String> = mutableListOf(), val tail: MutableList<String> = mutableListOf())
            val sections = mutableListOf(Section(null))
            for (item in lines) {
                if (item.level in chapterLevels) sections.add(Section(item.line)) else (if (item.note) sections.last().tail else sections.last().paragraphs).add(item.line)
            }
            for (section in sections) {
                val title = section.title
                val text = (section.paragraphs + section.tail).joinToString("\n\n")
                when {
                    title == null -> if (section.paragraphs.isNotEmpty()) result.chapters.add(Chapter(PREAMBLE, text))
                    section.paragraphs.isNotEmpty() -> result.chapters.add(Chapter(title, text))
                    else -> result.notes.add("Bỏ qua mục trống: $title")
                }
            }
        }
        val first = result.chapters.firstOrNull()?.takeIf { result.chapters.size > 1 }
        if (first != null && first.title == PREAMBLE && titlePage(first.text)) {
            result.chapters[0] = Chapter(first.title, first.text, first.short, first.name, "Trang tên sách") // không bỏ: chưa tích, kèm lý do
        }
        result
    }

    // ---- chia chương theo dòng tiêu đề (DOCX không có Heading, PDF) ---------------------------------------------------

    private const val NUMBER_WORDS = "một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|mốt|trăm|nghìn|ngàn|linh|lẻ|" +
        "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"

    /** Số thứ tự chỉ đứng sau "thứ" ("Hồi thứ nhất", "Hồi thứ nhứt"): "Hồi nhất định…" là câu văn (importers._ORDINAL_WORDS). */
    private const val ORDINAL_WORDS = "nhất|nhứt|nhì"

    /** Dòng tiêu đề chương: "Chương 12", "Hồi thứ hai", "Quyển 2", "第三章" (importers.HEADING). */
    private val HEADING: Pattern = Pattern.compile(
        "^\\s*(?:(?:chương|chuong|hồi|hoi|chapter|tiết|quyển|quyen)\\s+(?:thứ\\s+(?:$ORDINAL_WORDS)|(?:thứ\\s+)?(?:\\d+|[ivxlcdm]+|(?:(?:$NUMBER_WORDS)\\s*)+))(?![\\w])" +
            "|第\\s*[\\d一二三四五六七八九十百千零〇两]+\\s*[章回])",
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or UNICODE_CLASSES,
    )

    /** Tiêu đề chương của file TXT cả truyện: "Chương N" thôi, như trình tạo sách (importers.TXT_HEADING) - "Quyển N" là tên tập. */
    private val TXT_HEADING: Pattern = Pattern.compile(
        "^\\s*(?:(?:chương|chuong|hồi|hoi|chapter|tiết)\\s+(?:thứ\\s+(?:$ORDINAL_WORDS)|(?:thứ\\s+)?(?:\\d+|[ivxlcdm]+|(?:(?:$NUMBER_WORDS)\\s*)+))(?![\\w])" +
            "|第\\s*[\\d一二三四五六七八九十百千零〇两]+\\s*[章回])",
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or UNICODE_CLASSES,
    )

    internal fun isHeadingLine(line: String, pattern: Pattern = HEADING): Boolean = cpLen(pyStrip(line)) <= MAX_HEADING && pattern.matcher(line).lookingAt()

    /** `importers._split_on_headings`; `extra`: số thứ tự các dòng cũng là tiêu đề (DOCX: dòng in đậm "I. KHỞI ĐẦU"). `noteLines`: số thứ tự các dòng là
     *  lời chú (DOCX, người nghe tích đọc lời chú): không bao giờ là tiêu đề, và đứng ở cuối chương. */
    private fun splitOnHeadings(
        paragraphs: List<String>, bookTitle: String, extra: Set<Int> = emptySet(), noteLines: Set<Int> = emptySet(),
    ): Pair<List<Chapter>, List<String>> {
        val chapters = mutableListOf<Chapter>()
        val notes = mutableListOf<String>()
        var title: String? = null
        var body = mutableListOf<String>()
        var tail = mutableListOf<String>()
        val headings = paragraphs.mapIndexed { index, paragraph -> index !in noteLines && (isHeadingLine(paragraph) || index in extra) }
        val anyHeading = headings.any { it }

        fun close() {
            val current = title
            when {
                current == null -> if (body.isNotEmpty()) chapters.add(Chapter(if (anyHeading) PREAMBLE else bookTitle, (body + tail).joinToString("\n\n")))
                body.isNotEmpty() -> chapters.add(Chapter(current, (body + tail).joinToString("\n\n")))
                else -> notes.add("Bỏ qua mục trống: $current")
            }
        }

        for ((index, paragraph) in paragraphs.withIndex()) {
            if (headings[index]) {
                close()
                title = pyStrip(paragraph)
                body = mutableListOf()
                tail = mutableListOf()
            } else {
                (if (index in noteLines) tail else body).add(paragraph)
            }
        }
        close()
        if (!anyHeading) notes.add("Không thấy tiêu đề chương (Chương N, Chapter N…) - cả file là một chương.")
        return chapters to notes
    }

    // ---- PDF có lớp chữ: lớp luật -------------------------------------------------------------------------------------

    private val PAGE_NUMBER: Pattern = Pattern.compile(
        "^[\\s\\-–—·|]*(?:trang|page|tr\\.?|p\\.?)?\\s*\\d{1,5}(?:\\s*(?:/|of|trên)\\s*\\d{1,5})?[\\s\\-–—·|]*$",
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or UNICODE_CLASSES,
    )
    private const val SENTENCE_END = ".!?…”\"»’)。"
    private const val DIALOGUE_START = "-–—“\"«‘"
    private const val SOFT_HYPHEN = '­'
    private const val RUNNING_ZONE = 2
    private const val RUNNING_MIN_PAGES = 3
    private const val SCAN_CHARS_PER_PAGE = 30
    private val DIGITS = Pattern.compile("\\d+", UNICODE_CLASSES)

    private fun isPageNumber(line: String) = PAGE_NUMBER.matcher(line).matches()

    private fun runningKey(line: String) = DIGITS.matcher(casefold(line)).replaceAll("#")

    /** Bỏ số trang và tiêu đề chạy đầu / cuối trang (dòng lặp lại ở >= 40% số trang, chữ số coi như nhau). Dòng tiêu đề chương
     *  không bao giờ bị coi là dòng lặp. Trả (các trang, các dòng đã bỏ - cho `notes`). */
    internal fun stripRunning(pages: List<List<String>>): Pair<List<List<String>>, List<String>> {
        val zones = pages.map { lines ->
            val filled = lines.indices.filter { lines[it].isNotEmpty() }
            if (filled.size > RUNNING_ZONE) filled.take(RUNNING_ZONE) + filled.takeLast(RUNNING_ZONE) else filled
        }
        val counts = HashMap<String, Int>()
        for ((lines, zone) in pages.zip(zones)) {
            val keys = zone.filter { !isHeadingLine(lines[it]) }.map { runningKey(lines[it]) }.toSet()
            for (key in keys) counts[key] = (counts[key] ?: 0) + 1
        }
        val repeated = counts.filter { (_, seen) -> pages.size >= RUNNING_MIN_PAGES && seen >= 3 && seen * 5 >= pages.size * 2 }.keys
        val removed = mutableListOf<String>()
        val noted = HashSet<String>() // một ghi chú cho mỗi dòng lặp, dù số trang trong nó đổi theo trang
        val result = mutableListOf<List<String>>()
        for ((lines, zone) in pages.zip(zones)) {
            val drop = HashSet<Int>()
            for (index in zone) {
                val line = lines[index]
                if (isHeadingLine(line)) continue
                val edge = index == zone[0] || index == zone[zone.size - 1]
                val key = runningKey(line)
                if (key in repeated || (edge && isPageNumber(line))) {
                    drop.add(index)
                    if (key !in noted && !isPageNumber(line) && removed.size < 5) {
                        noted.add(key)
                        removed.add(line)
                    }
                }
            }
            result.add(lines.filterIndexed { index, _ -> index !in drop })
        }
        return result to removed
    }

    /** Các dòng của PDF -> đoạn văn. Một dòng cuối câu mà ngắn hơn hẳn dòng đầy (hay dòng kế mở đầu bằng gạch / ngoặc thoại) ngắt
     *  đoạn; "chữ-" cuối dòng nối liền (không dấu cách, giữ gạch nối) với chữ thường dòng sau, dấu nối mềm U+00AD thì bỏ; còn lại
     *  nối bằng một dấu cách. Hết trang KHÔNG ngắt đoạn (đoạn văn vắt qua trang). */
    internal fun joinParagraphs(pages: List<List<String>>): List<String> {
        val sizes = pages.flatten().map { cpLen(it) }.sorted()
        val full = if (sizes.isEmpty()) 0 else sizes[(sizes.size * 0.9).toInt()]
        val paragraphs = mutableListOf<String>()
        var current = ""
        var last = 0
        for (page in pages) {
            for (line in page) {
                if (isHeadingLine(line)) {
                    if (current.isNotEmpty()) paragraphs.add(current)
                    paragraphs.add(line)
                    current = ""
                    continue
                }
                if (current.isEmpty()) {
                    current = line
                } else if (current.last() == SOFT_HYPHEN) {
                    current = current.dropLast(1) + line
                } else if (current.last() == '-' && current.length > 1 && current[current.length - 2].isLetter() &&
                    Character.isLowerCase(line.codePointAt(0))
                ) {
                    current += line
                } else if (current.last() in SENTENCE_END && (last < full * 0.75 || line[0] in DIALOGUE_START)) {
                    paragraphs.add(current)
                    current = line
                } else {
                    current = "$current $line"
                }
                last = cpLen(line)
            }
        }
        if (current.isNotEmpty()) paragraphs.add(current)
        return paragraphs
    }

    // ---- dòng ghi công (text_processing.credit_lines) ----------------------------------------------------------------

    private val CREDIT_LINE: Pattern = Pattern.compile(
        "^[*_~#>\\-–—\\s]*(?:edit(?:or|ed by)?|tl|t/l|trans(?:lator|lated by)?|dịch(?: giả)?|người dịch|biên tập(?: viên)?|" +
            "beta(?:[- ]?reader)?|converter|cvt|proof ?read(?:er)?|typesetter)\\s*[:：]\\s*[^\\s.!?…\"“”][^.!?…\"“”]{0,39}$",
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or UNICODE_CLASSES,
    )
    private const val CREDIT_WINDOW_LINES = 6
    private val NOTE_MARKER = Regex("\\[\\s*note\\d+\\s*\\]", RegexOption.IGNORE_CASE)

    /** `text_processing.normalize_text` (phần ảnh hưởng tới việc nhận ra dòng ghi công). */
    private fun normalizeText(input: String): String {
        var text = input.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
        for (zero in listOf("​", "‌", "‍", "⁠", "﻿")) text = text.replace(zero, "")
        text = text.replace("「", "“").replace("」", "”")
        text = NOTE_MARKER.replace(text, "")
        text = text.replace(Regex("[ \t]+"), " ").replace(Regex("\n[ \t]+"), "\n").replace(Regex("\n{3,}"), "\n\n")
        return pyStrip(text)
    }

    /**
     * Dòng ghi công ở đầu một chương, `source` như file chương ([chapterSource]): GỢI Ý để người nghe chọn bỏ khỏi phần đọc (lớp sửa
     * `skip`), không bao giờ tự bỏ (`importers.credit_suggestions`). Chỉ đưa phần đầu chương (`CREDIT_HEAD_LINES`): chuẩn hoá cả chương
     * chỉ để xem 6 dòng là phần chậm nhất của cuốn hơn nghìn chương.
     */
    fun creditSuggestions(source: String): List<String> =
        creditLines(source.split("\n", limit = CREDIT_HEAD_LINES + 1).take(CREDIT_HEAD_LINES).joinToString("\n"))

    /** Đúng những dòng `drop_credit_lines` của Studio sẽ bỏ: dòng ghi công trong 6 dòng có chữ đầu tiên của chương. */
    internal fun creditLines(text: String): List<String> {
        val lines = normalizeText(text).split("\n")
        val found = mutableListOf<String>()
        var seen = 0
        for (line in lines) {
            val stripped = pyStrip(line)
            if (stripped.isEmpty()) continue
            if (seen >= CREDIT_WINDOW_LINES) break
            seen++
            if (CREDIT_LINE.matcher(stripped).lookingAt()) found.add(stripped)
        }
        return found
    }
}
