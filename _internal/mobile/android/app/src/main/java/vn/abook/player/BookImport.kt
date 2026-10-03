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

    class Chapter(val title: String, val text: String)

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
    )

    val IMPORT_SUFFIXES = listOf("epub", "docx", "pdf")

    private const val MAX_MEMBER = 20L * 1024 * 1024
    private const val MAX_TOTAL = 300L * 1024 * 1024
    private const val MAX_COVER = 20L * 1024 * 1024
    private const val MIN_CHARS = 80
    private const val PREAMBLE = "Mở đầu"
    private const val MAX_HEADING = 120
    private const val BROKEN = "không phải file %s thật hoặc bị hỏng - thử tải lại, hoặc dùng bản TXT"

    private fun broken(kind: String) = Failed(BROKEN.format(kind))

    // ---- vào ----------------------------------------------------------------------------------------------------------

    /** Một thư mục TXT, hay file .epub / .docx / .txt. (PDF đi qua `fromPdfPages`: lấy chữ ra là việc của pdf.js.) */
    fun importFile(path: File): Book {
        val book = when {
            path.isDirectory -> txtFolder(path)
            path.isFile -> when (val suffix = path.extension.lowercase()) {
                "epub" -> epub(path)
                "docx" -> docx(path)
                "txt" -> txtFile(path)
                "pdf" -> throw Failed("PDF cần lấy chữ bằng pdf.js trước (fromPdfPages)")
                else -> throw Failed("Chưa đọc được file ${if (suffix.isEmpty()) "không có đuôi" else ".$suffix"} - dùng .epub, .docx, .pdf, .txt hay một thư mục TXT")
            }
            else -> throw Failed("Không thấy ${path.path}")
        }
        return finish(book)
    }

    /** PDF có lớp chữ: `pages` là các dòng CÓ CHỮ của từng trang (pdf.js, như file pages trong bộ ví dụ). */
    fun fromPdfPages(stem: String, pages: List<List<String>>, title: String = "", author: String = ""): Book {
        if (pages.isEmpty()) throw broken("PDF")
        val chars = pages.sumOf { page -> page.sumOf { cpLen(it) } }
        if (chars < SCAN_CHARS_PER_PAGE * pages.size) {
            throw Failed("PDF scan, cần OCR: file chỉ có ảnh của trang, không có lớp chữ - ABook chưa đọc được loại này")
        }
        val result = Book(title.ifEmpty { stem }, author = author.ifEmpty { null })
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
            "chapters" to book.chapters.map { linkedMapOf<String, Any?>("title" to it.title, "text" to it.text) },
            "notes" to book.notes.toList(),
        )
    }

    private fun sha256(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private fun finish(book: Book): Book {
        book.title = nfc(book.title)
        book.author = book.author?.takeIf { it.isNotEmpty() }?.let(::nfc)
        val chapters = book.chapters.map { Chapter(nfc(it.title), nfc(it.text)) }
        book.chapters.clear()
        book.chapters.addAll(if (chapters.size > 1) chapters.filter { pyStrip(it.text).isNotEmpty() } else chapters)
        val notes = book.notes.map(::nfc)
        book.notes.clear()
        book.notes.addAll(notes)
        if (book.chapters.isEmpty() || book.chapters.none { pyStrip(it.text).isNotEmpty() }) throw Failed("Không có chương nào có chữ")
        for ((index, chapter) in book.chapters.withIndex()) {
            // Tên chương tính là một dòng của chương (cửa sổ 6 dòng đầu), như file chương mà Studio đọc.
            val head = if (book.textHasTitle) chapter.text else "${chapter.title}\n\n${chapter.text}"
            for (line in creditLines(head)) {
                book.notes.add("Gợi ý: chương ${index + 1} có dòng ghi công ở đầu - “$line”. Có thể bỏ khỏi phần đọc, nhưng ABook không tự bỏ.")
            }
        }
        return book
    }

    // ---- chữ ----------------------------------------------------------------------------------------------------------

    private fun nfc(text: String) = Normalizer.normalize(text, Normalizer.Form.NFC)

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

    private fun cpTake(text: String, count: Int): String =
        if (cpLen(text) <= count) text else text.substring(0, text.offsetByCodePoints(0, count))

    private fun casefold(text: String) = text.lowercase()

    // ---- thư mục TXT --------------------------------------------------------------------------------------------------

    /** Đổi định dạng thôi: xuống dòng \n, bỏ khoảng trắng cuối dòng, tối đa một dòng trống liền nhau, bỏ dòng trống hai đầu. */
    internal fun cleanText(text: String): String {
        val lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n").map { pyRstrip(it) }
        return lines.joinToString("\n").replace(Regex("\n{3,}"), "\n\n").trim('\n')
    }

    private val NUMERIC_TITLE = Regex("^\\s*0*(\\d+)\\s*$")

    /** Tên file chương là số ("645") thì đọc thành "Chương 645"; còn lại giữ nguyên (webui/humanize.chapter_title). */
    internal fun chapterTitle(stem: String): String =
        NUMERIC_TITLE.find(stem)?.let { "Chương ${it.groupValues[1]}" } ?: pyStrip(stem)

    private fun stemOf(name: String) = if (name.contains('.') && !name.startsWith(".")) name.substringBeforeLast('.') else name

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
        a.size.compareTo(b.size)
    }

    private fun naturalKey(value: String): List<Any> {
        val parts = mutableListOf<Any>()
        val digits = Regex("\\d+")
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
            .filter { it.isFile && it.extension.lowercase() == "txt" }
            .sortedWith { x, y -> naturalOrder.compare(x.name, y.name) }
        if (files.isEmpty()) throw Failed("Thư mục này không có file .txt nào nằm ngay bên trong")
        val chapters = files.map { Chapter(chapterTitle(stemOf(it.name)), cleanText(decodeTextBytes(it.readBytes()))) }
        return Book(folder.canonicalFile.name, chapters = chapters.toMutableList(), textHasTitle = true)
    }

    private fun txtFile(file: File): Book {
        val chapter = Chapter(chapterTitle(stemOf(file.name)), cleanText(decodeTextBytes(file.readBytes())))
        return Book(stemOf(file.name), chapters = mutableListOf(chapter), textHasTitle = true)
    }

    /** `io_utils.decode_text_bytes`: UTF-16 (có BOM, hay nhiều byte 0), UTF-8 (có / không BOM), rồi cp1258, cp1252; NFC. */
    internal fun decodeTextBytes(raw: ByteArray): String {
        if (raw.size >= 2 && ((raw[0] == 0xFF.toByte() && raw[1] == 0xFE.toByte()) || (raw[0] == 0xFE.toByte() && raw[1] == 0xFF.toByte()))) {
            return nfc(String(raw, Charsets.UTF_16))
        }
        val encodings = mutableListOf("utf-8-sig", "UTF-8", "windows-1258", "windows-1252")
        if (raw.isNotEmpty()) {
            var even = 0
            var odd = 0
            for (index in raw.indices) if (raw[index].toInt() == 0) if (index % 2 == 0) even++ else odd++
            if ((even + odd).toDouble() / raw.size >= 0.2) encodings.add(0, if (even > odd) "UTF-16BE" else "UTF-16LE")
        }
        for (encoding in encodings) {
            val decoded = strictDecode(raw, encoding) ?: continue
            if ('�' !in decoded) return nfc(decoded)
        }
        return nfc(String(raw, Charsets.UTF_8))
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
        class Start(val name: String, val attrs: Map<String, String>, val selfClosing: Boolean) : Tok()
        class End(val name: String) : Tok()
        class Text(val text: String) : Tok()

        private val NAMED = mapOf(
            "amp" to "&", "lt" to "<", "gt" to ">", "quot" to "\"", "apos" to "'", "nbsp" to " ", "ndash" to "–",
            "mdash" to "—", "hellip" to "…", "laquo" to "«", "raquo" to "»", "ldquo" to "“", "rdquo" to "”", "lsquo" to "‘",
            "rsquo" to "’", "copy" to "©", "shy" to "­", "middot" to "·", "bull" to "•", "times" to "×", "deg" to "°",
        )
        private val ENTITY = Regex("&(#[xX][0-9a-fA-F]+|#[0-9]+|[A-Za-z][A-Za-z0-9]*);")

        fun decode(text: String): String {
            if (text.indexOf('&') < 0) return text
            return ENTITY.replace(text) { match ->
                val body = match.groupValues[1]
                when {
                    body.startsWith("#x") || body.startsWith("#X") -> codePoint(body.substring(2).toLongOrNull(16), match.value)
                    body.startsWith("#") -> codePoint(body.substring(1).toLongOrNull(), match.value)
                    else -> NAMED[body] ?: match.value
                }
            }
        }

        private fun codePoint(value: Long?, original: String): String =
            if (value == null || value <= 0 || value > 0x10FFFF || value in 0xD800..0xDFFF) original else String(Character.toChars(value.toInt()))

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
                if (key.isNotEmpty()) attrs.putIfAbsent(key.substringAfter(':'), decode(value))
            }
            out.add(Start(name, attrs, selfClosing))
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

        /** Một phần tử XML: `parts` là chữ và phần tử con theo thứ tự (như text / tail của ElementTree). */
        class Node(val name: String, val attrs: Map<String, String>) {
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

        /** Đọc một file XML: từ chối khai báo entity (bom XML), không thấy phần tử gốc là file hỏng. */
        fun parse(raw: ByteArray, kind: String): Node {
            val head = String(raw, 0, minOf(raw.size, 4096), Charsets.UTF_8)
            if (head.uppercase().contains("<!ENTITY")) throw Failed("có nội dung XML lạ (khai báo entity) - không mở để giữ an toàn máy")
            val stack = ArrayList<Node>()
            var root: Node? = null
            for (token in tokenize(String(raw, Charsets.UTF_8))) {
                when (token) {
                    is Start -> {
                        val node = Node(token.name, token.attrs)
                        if (stack.isEmpty()) {
                            if (root == null) root = node
                        } else {
                            stack.last().parts.add(node)
                        }
                        if (!token.selfClosing) stack.add(node)
                    }
                    is End -> {
                        val index = stack.indexOfLast { it.name == token.name }
                        if (index >= 0) while (stack.size > index) stack.removeAt(stack.size - 1)
                    }
                    is Text -> stack.lastOrNull()?.parts?.add(token.text)
                }
            }
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

    private fun read(zip: ZipFile, name: String, kind: String): ByteArray {
        val entry = zip.getEntry(name) ?: throw broken(kind)
        if (entry.size > MAX_MEMBER) throw Failed("có một phần quá lớn (trên 20 MB) - không giống $kind truyện")
        return zip.getInputStream(entry).use { it.readBytes() }
    }

    private fun xml(zip: ZipFile, name: String, kind: String) = Markup.parse(read(zip, name, kind), kind)

    private fun metaText(root: Markup.Node, local: String): String? {
        val node = root.descendants().firstOrNull { it.local == local && it.name.startsWith("dc:") } ?: return null
        return words(node.text).ifEmpty { null }
    }

    // ---- posix ---------------------------------------------------------------------------------------------------------

    private fun dirname(path: String) = if (path.contains('/')) path.substringBeforeLast('/') else ""

    private fun basename(path: String) = path.substringAfterLast('/')

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

    private val TEXT_BLOCKS = setOf("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "blockquote", "section", "article", "tr", "dd", "dt", "pre")
    private val TEXT_HEADINGS = setOf("h1", "h2", "h3")
    private val SKIPPED_TAGS = setOf("script", "style", "head", "title")

    /** Chữ của một trang XHTML: mỗi khối (đoạn, tiêu đề, dòng danh sách, <br>) một dòng; bỏ script/style/head. */
    private class PageText {
        val lines = mutableListOf<String>()
        var heading = ""
        var images = 0
        private val current = StringBuilder()
        private var skip = 0
        private var inHeading = 0

        private fun flush() {
            val line = words(current.toString())
            if (line.isNotEmpty()) lines.add(line)
            current.setLength(0)
        }

        private fun start(tag: String) {
            when {
                tag in SKIPPED_TAGS -> skip++
                tag == "img" || tag == "image" -> images++
                tag == "br" -> flush()
                tag in TEXT_BLOCKS -> {
                    flush()
                    if (tag in TEXT_HEADINGS) inHeading++
                }
            }
        }

        private fun end(tag: String) {
            when {
                tag in SKIPPED_TAGS -> skip = maxOf(0, skip - 1)
                tag in TEXT_BLOCKS -> {
                    if (tag in TEXT_HEADINGS && inHeading > 0) {
                        inHeading--
                        if (heading.isEmpty()) heading = words(current.toString())
                    }
                    flush()
                }
            }
        }

        fun feed(source: String) {
            for (token in Markup.tokenize(source)) {
                when (token) {
                    is Markup.Start -> {
                        start(token.name.lowercase())
                        if (token.selfClosing) end(token.name.lowercase())
                    }
                    is Markup.End -> end(token.name.lowercase())
                    is Markup.Text -> if (skip == 0) current.append(token.text)
                }
            }
            flush()
        }
    }

    private class ManifestItem(val href: String, val media: String, val props: String)

    private fun tokens(props: String) = props.split(Regex("\\s+")).filter { it.isNotEmpty() }

    private fun toc(zip: ZipFile, manifest: Map<String, ManifestItem>, spineToc: String): Map<String, String> {
        val titles = linkedMapOf<String, String>()
        val nav = manifest.values.firstOrNull { "nav" in tokens(it.props) }?.href ?: ""
        if (nav.isNotEmpty()) {
            val root = xml(zip, nav, "EPUB")
            val navDir = dirname(nav)
            for (anchor in root.descendants().filter { it.local == "a" }) {
                val href = anchor.attr("href") ?: ""
                val label = words(anchor.allText())
                if (href.isNotEmpty() && label.isNotEmpty()) {
                    titles.putIfAbsent(normpath(join(navDir, unquote(href.substringBefore('#')))), label)
                }
            }
        }
        val ncx = manifest[spineToc]?.href?.takeIf { it.isNotEmpty() }
            ?: manifest.values.firstOrNull { it.media == "application/x-dtbncx+xml" }?.href ?: ""
        if (ncx.isNotEmpty() && titles.isEmpty()) {
            val root = xml(zip, ncx, "EPUB")
            val ncxDir = dirname(ncx)
            for (point in root.descendants().filter { it.local == "navPoint" }) {
                val label = point.child("navLabel")?.child("text")
                val content = point.child("content")
                if (label != null && content != null && pyStrip(label.text).isNotEmpty()) {
                    val src = normpath(join(ncxDir, unquote((content.attr("src") ?: "").substringBefore('#'))))
                    titles.putIfAbsent(src, words(label.text))
                }
            }
        }
        return titles
    }

    private fun epubCover(zip: ZipFile, opf: Markup.Node, manifest: Map<String, ManifestItem>): Pair<ByteArray, String>? {
        var href = manifest.values.firstOrNull { "cover-image" in tokens(it.props) }?.href ?: ""
        if (href.isEmpty()) {
            val meta = opf.child("metadata")?.children?.firstOrNull { it.local == "meta" && it.attr("name") == "cover" }
            href = if (meta != null) manifest[meta.attr("content") ?: ""]?.href ?: "" else ""
        }
        val media = manifest.values.firstOrNull { it.href == href }?.media ?: ""
        if (href.isEmpty() || !media.startsWith("image/")) return null
        val entry = zip.getEntry(href) ?: return null
        if (entry.size > MAX_COVER) return null
        return zip.getInputStream(entry).use { it.readBytes() } to media
    }

    private fun epub(file: File): Book = openZip(file, "EPUB").use { zip ->
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
        val titles = toc(zip, manifest, spine.attr("toc") ?: "")
        val result = Book(metaText(opf, "title") ?: stemOf(file.name), author = metaText(opf, "creator"), language = metaText(opf, "language"))
        epubCover(zip, opf, manifest)?.let { (bytes, media) ->
            result.cover = bytes
            result.coverType = media
        }
        for (itemref in spine.children.filter { it.local == "itemref" }) {
            if ((itemref.attr("linear") ?: "yes") == "no") continue
            val item = manifest[itemref.attr("idref") ?: ""] ?: ManifestItem("", "", "")
            if (item.href.isEmpty() || "nav" in tokens(item.props) || !item.media.contains("html")) continue
            val page = PageText().also { it.feed(String(read(zip, item.href, "EPUB"), Charsets.UTF_8)) }
            var lines: List<String> = page.lines
            val heading = page.heading
            val listed = titles[item.href] ?: ""
            if (lines.isEmpty() && page.images > 0) {
                result.notes.add("Bỏ qua trang chỉ có ảnh: ${basename(item.href)}")
                continue
            }
            if (lines.isEmpty()) continue
            if (lines.sumOf { cpLen(it) } < MIN_CHARS && listed.isEmpty()) {
                result.notes.add("Bỏ qua mục rất ngắn (bìa, trang bản quyền?): ${basename(item.href)}")
                continue
            }
            var title = listed.ifEmpty { heading.ifEmpty { cpTake(lines[0], 80) } }
            val first = casefold(lines[0])
            // Dòng đầu là tiêu đề của chính chương: bỏ khi nó đã nằm trong tên chương ("Gặp gỡ" trong "Chương 2: Gặp gỡ"),
            // hay lấy nó làm tên khi nó đầy đủ hơn tên mục lục - không để người nghe nghe tên chương hai lần.
            if (first == casefold(title) || (heading.isNotEmpty() && first == casefold(heading) && casefold(title).contains(first))) {
                lines = lines.drop(1)
            } else if (heading.isNotEmpty() && first == casefold(heading) && first.contains(casefold(title))) {
                title = lines[0]
                lines = lines.drop(1)
            }
            result.chapters.add(Chapter(title, lines.joinToString("\n\n")))
        }
        result
    }

    // ---- DOCX ----------------------------------------------------------------------------------------------------------

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

    private fun docx(file: File): Book = openZip(file, "DOCX").use { zip ->
        val document = xml(zip, "word/document.xml", "DOCX")
        val styles = docxStyles(zip)
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
        val sections = mutableListOf<Pair<String?, MutableList<String>>>(null to mutableListOf())
        var bookTitle: String? = null
        for (paragraph in docxParagraphs(body)) {
            val styleNode = paragraph.children.firstOrNull { it.name == "w:pPr" }?.children?.firstOrNull { it.name == "w:pStyle" }
            val styleId = styleNode?.attr("val") ?: ""
            val style = styles[styleId] ?: casefold(styleId)
            for (raw in docxText(paragraph)) {
                val line = words(raw)
                if (line.isEmpty()) continue
                if (style in setOf("heading 1", "heading 2", "heading1", "heading2")) {
                    sections.add(line to mutableListOf())
                } else {
                    if (style == "title" && bookTitle == null) bookTitle = line
                    sections.last().second.add(line)
                }
            }
        }
        val result = Book(metaTitle ?: bookTitle ?: stemOf(file.name), author = metaAuthor, language = metaLanguage)
        if (sections.size == 1) {
            // Không có kiểu Heading: tách theo dòng "Chương N" (như PDF).
            val (chapters, notes) = splitOnHeadings(sections[0].second, result.title)
            result.chapters.addAll(chapters)
            result.notes.addAll(notes)
            return@use result
        }
        for ((title, paragraphs) in sections) {
            when {
                title == null -> if (paragraphs.isNotEmpty()) result.chapters.add(Chapter(PREAMBLE, paragraphs.joinToString("\n\n")))
                paragraphs.isNotEmpty() -> result.chapters.add(Chapter(title, paragraphs.joinToString("\n\n")))
                else -> result.notes.add("Bỏ qua mục không có chữ: $title")
            }
        }
        result
    }

    // ---- chia chương theo dòng tiêu đề (DOCX không có Heading, PDF) ---------------------------------------------------

    private const val NUMBER_WORDS = "một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|mốt|trăm|nghìn|ngàn|linh|lẻ|" +
        "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"

    /** Dòng tiêu đề chương: "Chương 12", "Hồi thứ hai", "Quyển 2", "第三章" (importers.HEADING). */
    private val HEADING: Pattern = Pattern.compile(
        "^\\s*(?:(?:chương|chuong|hồi|hoi|chapter|tiết|quyển|quyen)\\s+(?:thứ\\s+)?(?:\\d+|[ivxlcdm]+|(?:(?:$NUMBER_WORDS)\\s*)+)(?![\\w])" +
            "|第\\s*[\\d一二三四五六七八九十百千零〇两]+\\s*[章回])",
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or Pattern.UNICODE_CHARACTER_CLASS,
    )

    internal fun isHeadingLine(line: String): Boolean = cpLen(pyStrip(line)) <= MAX_HEADING && HEADING.matcher(line).lookingAt()

    private fun splitOnHeadings(paragraphs: List<String>, bookTitle: String): Pair<List<Chapter>, List<String>> {
        val chapters = mutableListOf<Chapter>()
        val notes = mutableListOf<String>()
        var title: String? = null
        var body = mutableListOf<String>()
        val anyHeading = paragraphs.any { isHeadingLine(it) }

        fun close() {
            val current = title
            when {
                current == null -> if (body.isNotEmpty()) chapters.add(Chapter(if (anyHeading) PREAMBLE else bookTitle, body.joinToString("\n\n")))
                body.isNotEmpty() -> chapters.add(Chapter(current, body.joinToString("\n\n")))
                else -> notes.add("Bỏ qua mục không có chữ: $current")
            }
        }

        for (paragraph in paragraphs) {
            if (isHeadingLine(paragraph)) {
                close()
                title = pyStrip(paragraph)
                body = mutableListOf()
            } else {
                body.add(paragraph)
            }
        }
        close()
        if (!anyHeading) notes.add("Không thấy tiêu đề chương (Chương N, Chapter N…) - cả file là một chương.")
        return chapters to notes
    }

    // ---- PDF có lớp chữ: lớp luật -------------------------------------------------------------------------------------

    private val PAGE_NUMBER: Pattern = Pattern.compile(
        "^[\\s\\-–—·|]*(?:trang|page|tr\\.?|p\\.?)?\\s*\\d{1,5}(?:\\s*(?:/|of|trên)\\s*\\d{1,5})?[\\s\\-–—·|]*$",
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or Pattern.UNICODE_CHARACTER_CLASS,
    )
    private const val SENTENCE_END = ".!?…”\"»’)。"
    private const val DIALOGUE_START = "-–—“\"«‘"
    private const val SOFT_HYPHEN = '­'
    private const val RUNNING_ZONE = 2
    private const val RUNNING_MIN_PAGES = 3
    private const val SCAN_CHARS_PER_PAGE = 30
    private val DIGITS = Pattern.compile("\\d+", Pattern.UNICODE_CHARACTER_CLASS)

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
        val result = mutableListOf<List<String>>()
        for ((lines, zone) in pages.zip(zones)) {
            val drop = HashSet<Int>()
            for (index in zone) {
                val line = lines[index]
                if (isHeadingLine(line)) continue
                val edge = index == zone[0] || index == zone[zone.size - 1]
                if (runningKey(line) in repeated || (edge && isPageNumber(line))) {
                    drop.add(index)
                    if (line !in removed && !isPageNumber(line) && removed.size < 5) removed.add(line)
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
        Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE or Pattern.UNICODE_CHARACTER_CLASS,
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
