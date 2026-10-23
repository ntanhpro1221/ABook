package vn.abook.player

import android.content.Context
import android.net.Uri
import android.os.ParcelFileDescriptor
import android.provider.OpenableColumns
import android.system.Os
import android.system.OsConstants
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipEntry
import java.util.zip.ZipFile

/**
 * Mở một file sách của app (.abook - abook/webui/bookfile.py): kiểm y như máy tính rồi giải nén vào
 * books/<thư mục>/, đúng chỗ sách tải qua Wi-Fi nằm - thư viện, trình phát, đọc theo dùng lại nguyên vẹn. Sách không mang
 * mã nào: tên thư mục do app đặt (suy từ nội dung, hoặc đúng cuốn cùng lần sản xuất đã có trên máy).
 *
 * File đến từ bất kỳ đâu (Zalo, Drive, email, thẻ nhớ), nên coi là dữ liệu của người lạ: chỉ nhận đúng các tên mục của
 * định dạng (không đường dẫn tuyệt đối, không ".."), số mục và cỡ có trần, định dạng mới hơn app thì nhắc cập nhật, và
 * mọi file phải đúng cỡ + mã băm ghi trong book.json TRƯỚC khi sách vào thư viện. Giải nén vào thư mục tạm rồi mới đổi
 * tên: hỏng giữa chừng không bao giờ để lại nửa cuốn. Nhập lại cùng cuốn thì thay bản cũ.
 *
 * Phiên bản 3 (cả bộ nhiều phần trong một file, bookfile.pack_series): audio ở chapters/<phần>/<tên>.mp3 và có thể vài GB,
 * nên trước khi chép từ trình quản lý file và trước khi giải nén phải còn đủ chỗ - không thì từ chối rõ ràng thay vì để
 * bộ nhớ đầy giữa chừng.
 *
 * File dự án .abookproj (abook/webui/projectfile.py, phiên bản 3; docs/EDITING.md phase P3) mang luôn phần NGHE của sách với
 * đúng tên mục của file .abook (chapters/<tên>.mp3, book.json, cast, scripts, samples, music, edits...), nên mã nhận cuốn, nhập
 * lại, so với cuốn đã có trên máy dùng đúng như file .abook. Mục media trùng byte với mục khác chỉ là BÍ DANH (`project.json`
 * ghi `aliases`, bí danh không nằm trong gói): bộ nhập đọc byte của mục thật. Khác với file sách, điện thoại GIỮ cả xưởng trong
 * thư mục cuốn - `project.json` nguyên văn, `project/` và `sources/` (chép nguyên byte, KHÔNG BAO GIỜ mở `project/project.sqlite3`),
 * `views/` (bản chụp chỉ đọc) - để "Lưu" ghi lại được file dự án (BookDocumentWriter). File `workshop: "pending"` không có xưởng:
 * chỉ phần nghe, chờ "Dựng xưởng" ở máy có Studio. Chỗ trống cần tính theo những gì thật sự được giải ra.
 */
object BookFileImport {
    const val MIMETYPE = "application/vnd.ngdtuanh.abook+zip"
    const val PROJECT_MIMETYPE = "application/vnd.ngdtuanh.abookproj+zip"
    private const val FORMAT = "abook"
    private const val PROJECT_MAX_ENTRIES = 1_000_000
    private const val FORMAT_VERSION = 5  // 2 = có thêm rãnh nhạc nền (music/<sha1>.<mp3|m4a|ogg|opus|flac|wav>; bài người dùng nhập giữ định dạng của file); 3 = cả bộ nhiều phần (chapters/<phần>/...); 4 = lớp sửa của người nghe (edits.json, edits/cover.jpg); 5 = chương chỉ có chữ (texts/<n>.txt, không audio)
    /** Chỗ trống dư ngoài cỡ giải nén (book.json, thư mục tạm): đủ để không đầy bộ nhớ giữa chừng. */
    private const val ROOM_MARGIN = 64L shl 20
    private const val MAX_ENTRIES = 20_000
    private const val MAX_TOTAL_BYTES = 64L shl 30
    private const val MAX_JSON_BYTES = 32L shl 20
    /** Một bài nhạc nền trong gói (music_plan.TRACK_FILE bên Python) - mục duy nhất được bỏ khi hỏng (soát a26 L4). */
    private const val MUSIC_TRACK = """music/[0-9a-f]{40}\.(?:mp3|m4a|ogg|opus|flac|wav)"""
    private val MUSIC = Regex(MUSIC_TRACK)
    private const val COMMON = """cast\.json|cover\.jpg|scripts/\d+\.json|samples/\d+\.wav|$MUSIC_TRACK"""
    private val CONTENT = Regex("""$COMMON|chapters/[0-9A-Za-z_.\-]+\.mp3""")
    /** Phiên bản 3 thêm thư mục phần: chapters/<phần>/<tên>.mp3 (phiên bản 1-2 không có - gặp thì là mục lạ). */
    private val CONTENT_V3 = Regex("""$COMMON|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3""")
    /** Phiên bản 4 thêm lớp sửa của người nghe (BookEdits): edits.json và edits/cover.jpg (file .abookproj phiên bản 3 cũng mang chúng). */
    private val CONTENT_V4 = Regex("""$COMMON|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3|edits\.json|edits/cover\.jpg""")
    /** Phiên bản 5 thêm chữ của chương: texts/<mã chương>.txt (sách chỉ có chữ - docs/LISTEN_ANYTHING.md mục 1). */
    private val CONTENT_V5 = Regex("""$COMMON|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3|edits\.json|edits/cover\.jpg|texts/\d{1,9}\.txt""")
    private val DESCRIPTIONS = setOf("mimetype", "book.json", "manifest.json")
    /** Bom nén (bookfile.check_expansion, cùng các con số): âm thanh / ảnh thật gần như không nén được, chữ nén vài chục lần là cùng. */
    private const val MEDIA_RATIO = 20L
    private const val TEXT_RATIO = 100L
    private const val MEDIA_FLOOR = 1L shl 20
    private const val TEXT_FLOOR = 16L shl 20
    private val MEDIA_SUFFIXES = listOf(".mp3", ".jpg", ".wav", ".m4a", ".ogg", ".opus", ".flac")

    /** Mục `name` (`size` byte khi giải, `packed` byte trong gói) nén quá mức một file thật có thể thì từ chối cả file TRƯỚC khi giải ra.
     *  `text` = false (file dự án): chỉ kiểm media, vì sổ SQLite của dự án có thể thưa. */
    internal fun checkExpansion(name: String, size: Long, packed: Long, text: Boolean = true) {
        val media = MEDIA_SUFFIXES.any { name.lowercase().endsWith(it) }
        val room = maxOf(packed, 1L)
        if ((media && size >= MEDIA_FLOOR && size > room * MEDIA_RATIO) || (text && !media && size >= TEXT_FLOOR && size > room * TEXT_RATIO)) {
            throw Refused("Gói nén có thể gây hại hoặc bị hỏng — bạn xin người gửi gửi lại.")
        }
    }

    /** Đầu file (vài trăm byte) có đúng dáng một gói của app không: mục đầu là `mimetype`, LƯU không nén, nội dung là kiểu `.abook` hay `.abookproj`
     *  (cùng điều kiện `importFile` đòi). Cho file được chia sẻ qua kiểu chung (octet-stream, zip) khi tên mất đuôi - soát a99 V6. */
    fun looksLikeBookFile(head: ByteArray): Boolean {
        fun u16(at: Int) = (head[at].toInt() and 0xff) or ((head[at + 1].toInt() and 0xff) shl 8)
        if (head.size < 30 || head[0] != 'P'.code.toByte() || head[1] != 'K'.code.toByte() || head[2].toInt() != 3 || head[3].toInt() != 4) return false
        if (u16(8) != 0) return false // ZipEntry.STORED
        val nameEnd = 30 + u16(26)
        val dataStart = nameEnd + u16(28)
        if (String(head, 30, minOf(u16(26), head.size - 30), Charsets.US_ASCII) != "mimetype") return false
        return listOf(MIMETYPE, PROJECT_MIMETYPE).map { it.toByteArray(Charsets.US_ASCII) }.any { mime ->
            dataStart + mime.size <= head.size && head.copyOfRange(dataStart, dataStart + mime.size).contentEquals(mime)
        }
    }

    /** Gói zip bị cắt (còn chữ ký "PK" ở đầu) hay file rỗng - khác một file lạ đổi đuôi (bookfile.looks_cut). */
    private fun looksCut(file: File): Boolean = runCatching {
        file.inputStream().use { input ->
            val head = ByteArray(2)
            val read = input.read(head)
            read <= 0 || (read == 2 && head[0] == 'P'.code.toByte() && head[1] == 'K'.code.toByte())
        }
    }.getOrDefault(false)

    const val DAMAGED = "File sách bị hỏng hoặc chép chưa xong - chép lại từ nguồn."

    /** Trần độ lồng của JSON lấy từ file lạ: org.json đệ quy nên `[[[[…` hàng chục nghìn tầng làm tràn ngăn xếp (Error, không phải Exception). */
    private const val MAX_JSON_DEPTH = 256

    /** JSON của file lạ -> đối tượng; quá lồng thì ném (người gọi nói "hỏng"). */
    private fun parseObject(bytes: ByteArray): JSONObject {
        var depth = 0
        var quoted = false
        var escaped = false
        for (byte in bytes) {
            val c = byte.toInt().toChar()
            when {
                escaped -> escaped = false
                quoted -> if (c == '\\') escaped = true else if (c == '"') quoted = false
                c == '"' -> quoted = true
                c == '[' || c == '{' -> if (++depth > MAX_JSON_DEPTH) throw IllegalArgumentException("JSON lồng quá sâu")
                c == ']' || c == '}' -> depth--
            }
        }
        return try {
            JSONObject(bytes.toString(Charsets.UTF_8))
        } catch (error: StackOverflowError) {
            throw IllegalArgumentException("JSON lồng quá sâu")
        }
    }

    /** Dọn bản chép tạm `import-*.abook` (nhập từ trình quản lý file) mà lần nhập trước bị giết nên không kịp xoá: có thể hàng GB. */
    fun sweepCache(dir: File, now: Long = System.currentTimeMillis(), maxAgeMs: Long = Store.STAGING_MAX_AGE_MS) {
        dir.listFiles { file -> file.isFile && file.name.startsWith("import-") && file.name.endsWith(".abook") && now - file.lastModified() > maxAgeMs }
            ?.forEach { it.delete() }
    }

    /** Hai mục khác tên mà cùng một file trên đĩa (khác hoa-thường, hay chỉ khác dấu chấm / khoảng trắng cuối từng phần) -> từ chối
     *  (bookfile.check_distinct): giải nén để mục sau đè mục trước thì chương này phát âm thanh của chương kia. */
    private fun checkDistinct(names: Collection<String>) {
        val seen = HashMap<String, String>()
        for (name in names.sorted()) {
            val key = name.split("/").joinToString("/") { it.trimEnd('.', ' ').lowercase(java.util.Locale.ROOT) }
            val first = seen.getOrPut(key) { name }
            if (first != name) throw Refused("Gói có mục trùng tên — bạn xin người gửi gửi lại.")
        }
    }

    private enum class Kind { STR, INT, NUMBER, BOOL, LIST }

    // Kiểu trường book.json như máy tính (bookfile._BOOK_FIELDS...): sai kiểu thì thư viện của máy tính sập, nên cả hai nền cùng từ chối.
    private val BOOK_FIELDS = mapOf("title" to Kind.STR, "author" to Kind.STR, "narrator" to Kind.STR, "cast" to Kind.STR,
        "chaptersTotal" to Kind.INT, "chaptersAvailable" to Kind.INT, "duration" to Kind.NUMBER, "complete" to Kind.BOOL,
        "chapters" to Kind.LIST, "parts" to Kind.LIST, "samples" to Kind.LIST)
    private val CHAPTER_FIELDS = mapOf("id" to Kind.INT, "index" to Kind.INT, "part" to Kind.INT, "title" to Kind.STR, "subtitle" to Kind.STR,
        "fullTitle" to Kind.STR, "file" to Kind.STR, "text" to Kind.STR, "script" to Kind.STR, "state" to Kind.STR,
        "duration" to Kind.NUMBER, "available" to Kind.BOOL, "skip" to Kind.LIST)
    private val PART_FIELDS = mapOf("part" to Kind.INT, "title" to Kind.STR, "narrator" to Kind.STR, "duration" to Kind.NUMBER, "chapters" to Kind.LIST)

    private fun fits(value: Any?, kind: Kind): Boolean = when {
        value == null || value == JSONObject.NULL -> true
        kind == Kind.STR -> value is String
        kind == Kind.INT -> value is Int || value is Long || value is java.math.BigInteger
        kind == Kind.NUMBER -> value is Number && value.toDouble().isFinite()
        kind == Kind.BOOL -> value is Boolean
        else -> value is org.json.JSONArray
    }

    internal fun checkShape(book: JSONObject) {
        fun check(item: Any?, fields: Map<String, Kind>) {
            if (item !is JSONObject) throw Refused("File sách hỏng hoặc không đọc được — bạn xin người gửi gửi lại.")
            for ((key, kind) in fields) {
                if (!fits(item.opt(key), kind)) throw Refused("File sách hỏng hoặc không đọc được — bạn xin người gửi gửi lại.")
            }
        }
        check(book, BOOK_FIELDS)
        book.optJSONArray("chapters")?.let { for (index in 0 until it.length()) check(it.opt(index), CHAPTER_FIELDS) }
        book.optJSONArray("parts")?.let { for (index in 0 until it.length()) check(it.opt(index), PART_FIELDS) }
    }

    /** Lý do không nhận file - câu chữ để người dùng đọc. */
    class Refused(message: String) : Exception(message)

    /** `keptEdits`: số thay đổi của người nghe đã có sẵn trên cuốn này và được giữ nguyên (0 = cuốn mới hay chưa sửa gì) - giao
     *  diện nói "giữ nguyên N chỉnh sửa của bạn". */
    data class Imported(val id: String, val title: String, val keptEdits: Int = 0, val brokenMusic: Int = 0, val how: String = "new")

    /** Chép từ content:// (trình quản lý file, Zalo, Drive...) vào bộ nhớ đệm rồi nhập. */
    fun import(context: Context, uri: Uri, allowOlder: Boolean = false): Imported {
        Store.init(context)
        // File dự án có thể vài chục GB (sổ dự án, từng câu đã thu): đọc thẳng từ chỗ nó nằm, chỉ phần nghe mới được chép.
        openInPlace(context, uri)?.let { descriptor ->
            descriptor.use { return importFile(File("/proc/self/fd/${it.fd}"), allowOlder = allowOlder) }
        }
        val copy = File(context.cacheDir, "import-${System.nanoTime()}.abook")
        try {
            sizeOf(context, uri)?.let { requireRoom(context.cacheDir, it + ROOM_MARGIN) }
            val input = context.contentResolver.openInputStream(uri) ?: throw Refused("Không đọc được file.")
            input.use { source -> copy.outputStream().use { source.copyTo(it) } }
            return importFile(copy, allowOlder = allowOlder)
        } finally {
            copy.delete()
        }
    }

    /**
     * Mở một file dự án (.abookproj) tại chỗ qua bộ mô tả file - không chép cả gói vào bộ nhớ đệm. Chỉ khi trình quản lý
     * file nói đó là file dự án, bộ mô tả tua được và mở lại qua /proc được; không thì null và `import` chép như file sách.
     */
    private fun openInPlace(context: Context, uri: Uri): ParcelFileDescriptor? {
        val isProject = runCatching {
            context.contentResolver.getType(uri) == PROJECT_MIMETYPE ||
                context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { cursor ->
                    cursor.moveToFirst() && cursor.getString(0)?.lowercase()?.endsWith(".abookproj") == true
                } == true
        }.getOrDefault(false)
        if (!isProject) return null
        val descriptor = runCatching { context.contentResolver.openFileDescriptor(uri, "r") }.getOrNull() ?: return null
        val usable = runCatching {
            Os.lseek(descriptor.fileDescriptor, 0L, OsConstants.SEEK_SET)
            File("/proc/self/fd/${descriptor.fd}").canRead()
        }.getOrDefault(false)
        if (!usable) {
            descriptor.close()
            return null
        }
        return descriptor
    }

    /** Cỡ file theo trình quản lý file (content://), nếu nó cho biết. */
    private fun sizeOf(context: Context, uri: Uri): Long? = runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst() && !cursor.isNull(0)) cursor.getLong(0) else null
        }
    }.getOrNull()

    /** Ổ chứa `dir` còn đủ `need` byte không? Không thì từ chối, nói cần bao nhiêu và còn bao nhiêu (`File.usableSpace` là
     *  số StatFs báo cho ứng dụng). `freeSpace` cho test JVM đặt số khác. */
    private fun requireRoom(dir: File, need: Long, freeSpace: (File) -> Long = { it.usableSpace }) {
        val free = freeSpace(dir)
        if (free < need) {
            throw Refused("Thiếu chỗ mở sách (cần ${gigabytes(need)}, còn ${gigabytes(free)}) — bạn dọn ổ rồi thử lại.")
        }
    }

    private fun gigabytes(bytes: Long) = "%.1f GB".format(java.util.Locale.ROOT, bytes / (1L shl 30).toDouble()).replace('.', ',')

    /** `separate`: người dùng chọn "Thêm bản riêng" dù cuốn đã có - không tìm cuốn trùng, luôn là cuốn mới với mã riêng. */
    fun importFile(file: File, separate: Boolean = false, allowOlder: Boolean = false, freeSpace: (File) -> Long = { it.usableSpace }): Imported {
        val zip = try {
            ZipFile(file)
        } catch (error: Exception) {
            throw Refused(if (looksCut(file)) DAMAGED else "Đây không phải file sách của app.")
        }
        zip.use {
            val entries = zip.entries().toList()
            val first = entries.firstOrNull()
            val kind = if (first == null || first.name != "mimetype" || first.method != ZipEntry.STORED) null
            else readMime(first.size) { zip.getInputStream(first) }
            if (kind != MIMETYPE && kind != PROJECT_MIMETYPE) throw Refused("Đây không phải file sách của app.")
            val project = kind == PROJECT_MIMETYPE
            if (entries.size > if (project) PROJECT_MAX_ENTRIES else MAX_ENTRIES) throw Refused("File sách có quá nhiều mục.")
            val names = HashSet<String>()
            var total = 0L
            for (entry in entries) {
                val name = entry.name
                if (entry.isDirectory || !names.add(name)) throw Refused("Gói có mục trùng hay thư mục lạ: $name")
                total += maxOf(0L, entry.size)
                checkExpansion(name, entry.size, entry.compressedSize, text = !project)
            }
            if (!project && total > MAX_TOTAL_BYTES) throw Refused("File sách quá lớn.")
            checkDistinct(names)
            val layout = if (project) projectLayout(zip, names) else null
            val bookEntry = zip.getEntry("book.json") ?: throw Refused(
                if (project) "Dự án chưa có chương nghe được — bạn mở bằng ABook Studio."
                else "File sách thiếu phần mô tả (book.json).")
            if (bookEntry.size > MAX_JSON_BYTES) throw Refused("book.json quá lớn.")
            val book = try {
                parseObject(zip.getInputStream(bookEntry).use { it.readBytes() })
            } catch (error: Exception) {
                throw Refused("book.json hỏng.")
            }
            val pack = book.optJSONObject("package")
            if (pack == null || pack.optString("format") != FORMAT) throw Refused("Đây không phải file sách của app.")
            // Phiên bản phải là số nguyên thật ("3", 3.5, true không phải) - như máy tính; org.json ép kiểu mềm nên kiểm trước.
            val declared = pack.opt("version")
            val version = if (declared is Int || declared is Long) (declared as Number).toInt() else -1
            if (version < 1) throw Refused("File sách có phiên bản định dạng không hợp lệ.")
            if (version > FORMAT_VERSION) throw Refused("Sách này được làm bằng bản app mới hơn. Hãy cập nhật app để mở.")
            checkShape(book)
            BookEdits.scrubCoverColor(book) // màu bìa chỉ #rrggbb: `url(...)` trong file của người khác sẽ thành CSS gọi máy lạ
            // Thư mục phần chỉ có từ phiên bản 3, lớp sửa của người nghe từ phiên bản 4.
            if (!project) for (name in names - DESCRIPTIONS) if (!contentPattern(version).matches(name)) throw Refused("Gói có mục lạ: $name")
            val files = pack.optJSONObject("files") ?: throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            // File dự án: phần nghe là những mục logic mang tên của file .abook (bí danh cũng tính); phần còn lại của gói (sổ dự án,
            // bản thu từng câu, nguồn chương) chỉ được chép nguyên byte, không bao giờ mở.
            val content = layout?.listening ?: (names - DESCRIPTIONS)
            if (files.keys().asSequence().toSet() != content) {
                throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            }
            if (layout != null) layout.checkListening(book, files)
            val resolve = layout?.let { it::resolve } ?: { name: String -> name }
            // Lớp sửa của người nghe mà file mang theo (phiên bản 4): sai thì từ chối cả file, TRƯỚC khi chép gì.
            val incoming = readEdits(zip, resolve)
            // Chương nào trỏ tới chữ cũng phải có chữ ấy trong gói (file dự án: `checkListening` lo).
            val listed = if (layout == null) book.optJSONArray("chapters") else null
            for (index in 0 until (listed?.length() ?: 0)) {
                val reference = listed?.optJSONObject(index)?.opt("file")
                if (reference is String && reference.isNotEmpty() && reference !in content) throw Refused("File sách thiếu audio của một chương.")
                val written = listed?.optJSONObject(index)?.opt("text")
                if (written != null && written != JSONObject.NULL && (written !is String || written.isNotEmpty() && written !in content)) {
                    throw Refused("File sách thiếu chữ của một chương.")
                }
            }
            // Sách không mang mã nào (chủ sách 27-09): app nhận ra cùng một lần sản xuất bằng audio từng chương (cuốn chưa có audio
            // nào: bằng chữ từng chương).
            val chapters = identityPrints(content, files)
            // Cùng cuốn đã có trên máy (tải qua Wi-Fi, hay mở từ file trước đó): nhập VÀO đúng cuốn ấy, giữ mã của nó để
            // chỗ nghe vẫn nối - không thành hai cuốn. Bản trên máy nhiều chương hơn file thì giữ nguyên bản trên máy.
            val source = book.optString("sourceFingerprint")
            val existing = if (separate) null else (if (source.isEmpty()) null else Store.books().firstOrNull {
                it.optString("sourceFingerprint") == source
            }?.getString("id")) ?: Store.findByChapters(chapters)
            val key = contentKey(chapters)
            // Bản riêng của cuốn đã có: mã "<khoá>-2", "<khoá>-3"… (cùng chữ thì cùng khoá nội dung).
            val target = existing ?: if (separate && Store.bookDir(key).exists()) {
                generateSequence(2) { it + 1 }.map { "$key-$it" }.first { !Store.bookDir(it).exists() }
            } else {
                key
            }
            val current = existing?.let { Store.rawManifest(it) }
            val disposition = if (current == null) "new" else AudioRevision.importState(AudioRevision.chapterPrints(Store.bookDir(target), current), chapters,
                current.optString("audioUpdatedAt").ifEmpty { current.optJSONObject("package")?.optString("createdAt") ?: "" },
                book.optString("audioUpdatedAt").ifEmpty { pack.optString("createdAt") })
            if (disposition in setOf("older", "conflict") && !allowOlder) {
                return Imported(target, Store.manifest(target)?.optString("title") ?: current!!.optString("title"), how = disposition)
            }
            // Chỉ cuốn mở từ file mới nhận phần sửa của người nghe; cuốn của máy tính thì sửa ở máy ấy.
            val editable = existing == null || Store.isImported(existing)
            val keptEdits = if (existing != null) BookEdits.count(BookEdits.load(Store.bookDir(target))) else 0
            // Cuốn chỉ có chữ: tìm thấy nghĩa là CÙNG bộ chữ (Store.findByChapters) - không có bản "nhiều chương hơn" để thay, giữ bản trên máy.
            val gainsWorkshop = layout != null && !File(Store.bookDir(target), ProjectDocument.MANIFEST).isFile
            if (current != null && disposition == "existing" && !gainsWorkshop) {
                // Giữ bản trên máy, nhưng phần sửa trong file vẫn được hợp vào (bên máy này thắng) - không mất công của ai.
                if (editable && BookEdits.count(incoming.edits) > 0) {
                    BookEdits.adopt(Store.bookDir(target), incoming.edits, incoming.cover) { name, destination -> extract(zip, resolve(name), destination) }
                }
                // Xưởng của file (máy kia sửa thêm cách đọc, người nói, phán quyết...): gộp vào xưởng trên máy, không bỏ im lặng.
                if (layout != null && layout.files.has("project/project.sqlite3")) {
                    mergeWorkshop(Store.bookDir(target), Store.bookDir(target)) { name ->
                        if (layout.files.has("project/$name")) zip.getEntry(resolve("project/$name"))?.let { readLimited(zip, it, MAX_JSON_BYTES.toInt()) } else null
                    }
                }
                return Imported(target, Store.manifest(target)?.optString("title") ?: current.optString("title"), keptEdits, how = "existing")
            }
            val books = File(Store.root, "books").apply { mkdirs() }
            // File dự án: chỗ cần là cỡ những gì sẽ giải ra (phần nghe, bản chụp, xưởng), không phải cả gói.
            val needed = if (layout != null) layout.neededBytes() else total
            requireRoom(books, needed + ROOM_MARGIN, freeSpace)
            val staging = File(books, ".$target.${System.nanoTime()}.part")
            // Bài nhạc nền hỏng (chép dở, đổi byte): bỏ bài ấy, sách vẫn mở - đoạn ấy im lặng (bookfile.py, soát a26 L4).
            val brokenMusic = HashSet<String>()
            try {
                val expectedFiles = layout?.files ?: files
                val wanted = if (layout != null) listOf("book.json") + layout.materialize
                else DESCRIPTIONS.filter { it != "mimetype" && it in names } + content.sorted()
                for (name in wanted) {
                    val expected = expectedFiles.optJSONObject(name)
                    val previous = if (name.startsWith("chapters/")) Store.file(target, name) else null
                    val reuse = previous?.takeIf { expected != null && AudioRevision.matches(it, expected.optLong("size", -1), expected.optString("sha256")) }
                    val (size, sha256) = extract(zip, resolve(name), File(staging, name), reuse)
                    if (expected == null) continue
                    if (size != expected.optLong("size", -1) || sha256 != expected.optString("sha256")) {
                        if (layout != null || !MUSIC.matches(name)) throw Refused("File sách bị hỏng hoặc bị sửa ($name). Hãy chép lại file từ nguồn.")
                        File(staging, name).delete()
                        brokenMusic.add(name)
                    }
                }
                if (brokenMusic.isNotEmpty()) dropTracks(book, brokenMusic)
                if (layout != null) File(staging, ProjectDocument.MANIFEST).writeBytes(layout.manifestBytes)
                // Bản trên máy bị thay: sửa trong xưởng của nó gộp vào bản mới, không mất theo thư mục cũ.
                if (layout != null && existing != null && ProjectDocument.kept(staging)?.workshop == ProjectDocument.PRESENT) {
                    mergeWorkshop(staging, Store.bookDir(target)) { name -> File(staging, "project/$name").takeIf { it.isFile }?.readBytes() }
                }
                if (!editable) File(staging, BookEdits.EDITS_FILE).delete().also { File(staging, BookEdits.EDITS_COVER).delete() }
                keepLocalEdits(Store.bookDir(target), staging, if (editable) incoming.edits else BookEdits.empty())
                File(Store.bookDir(target), ExportHistory.FILE).takeIf { it.isFile }?.copyTo(File(staging, ExportHistory.FILE), overwrite = true)
                val bookChapters = book.optJSONArray("chapters") ?: org.json.JSONArray()
                for (index in 0 until bookChapters.length()) {
                    val chapter = bookChapters.getJSONObject(index)
                    val meta = files.optJSONObject(chapter.optString("file"))
                    chapter.put("sha256", meta?.optString("sha256") ?: "").put("size", meta?.optLong("size") ?: 0L)
                }
                book.put("audioVersion", AudioRevision.version(bookChapters))
                // Bản sách của app trên máy mang mã thư mục của app (book.json không nằm trong danh sách mã băm).
                Store.writeAtomic(File(staging, "book.json"), book.put("id", target).toString())
                replace(books, staging, Store.bookDir(target), target)
            } finally {
                staging.deleteRecursively()
            }
            Store.rememberChapters(target, chapters, imported = existing == null || Store.isImported(existing))
            if (existing == null) BookEdits.markSaved(Store.bookDir(target)) // edits that came inside the file are not "unsaved" (a70)
            return Imported(target, Store.manifest(target)?.optString("title") ?: book.optString("title"), keptEdits, brokenMusic.size, if (existing == null) "new" else "updated")
        }
    }

    /** Bỏ các bài `names` khỏi mô tả sách: danh sách file, danh sách bài, và mốc nhạc trỏ tới chúng (bookfile._drop_tracks). */
    private fun dropTracks(book: JSONObject, names: Set<String>) {
        val files = book.optJSONObject("package")?.optJSONObject("files")
        for (name in names) files?.remove(name)
        val music = book.optJSONObject("music") ?: return
        for (name in names) music.optJSONObject("tracks")?.remove(name)
        val chapters = music.optJSONObject("chapters") ?: return
        for (chapter in chapters.keys().asSequence().toList()) {
            val cues = chapters.optJSONArray(chapter) ?: continue
            val kept = org.json.JSONArray()
            for (index in 0 until cues.length()) {
                val cue = cues.opt(index)
                if (!(cue is JSONObject && cue.optString("track") in names)) kept.put(cue)
            }
            chapters.put(chapter, kept)
        }
    }

    /**
     * Cùng cuốn, cả bản trên máy (`local`) lẫn bản của file đều có xưởng: gộp sửa trong xưởng (WorkshopMerge, luật của máy tính) vào
     * thư mục `into` - bản nào được giữ cũng không bỏ sửa của bản kia. `theirs(tên)`: byte của `project/<tên>` trong bản của file.
     */
    private fun mergeWorkshop(into: File, local: File, theirs: (String) -> ByteArray?) {
        if (ProjectDocument.kept(local)?.workshop != ProjectDocument.PRESENT) return
        WorkshopMerge.mergeInto(into, { name -> File(local, "project/$name").takeIf { it.isFile }?.readBytes() }, theirs,
            System.currentTimeMillis() / 1000.0)
    }

    /** Phần sửa của người nghe trong file (đã kiểm) và byte ảnh bìa sửa của nó. */
    private class Edits(val edits: JSONObject, val cover: ByteArray?)

    /**
     * `edits.json` đúng giao ước (BookEdits.validate - sai thì từ chối cả file) và bìa sửa đi đôi với nó: có `cover` là đối tượng
     * thì phải có edits/cover.jpg, và ngược lại; là JPEG, không quá cỡ (bookfile.py `_check_edits`).
     */
    internal fun readMime(size: Long, open: () -> java.io.InputStream): String {
        val allowed = listOf(MIMETYPE, PROJECT_MIMETYPE).map { it.toByteArray(Charsets.US_ASCII) }
        val cap = allowed.maxOf { it.size }
        if (size >= 0 && allowed.none { it.size.toLong() == size }) throw Refused("File sách có mimetype không hợp lệ; bạn hãy xin người gửi gửi lại.")
        val bytes = open().use { input ->
            val out = java.io.ByteArrayOutputStream()
            val buffer = ByteArray(cap + 1)
            while (out.size() <= cap) {
                val count = input.read(buffer, 0, cap + 1 - out.size())
                if (count < 0) break
                out.write(buffer, 0, count)
            }
            out.toByteArray()
        }
        val match = allowed.firstOrNull { it.contentEquals(bytes) }
            ?: throw Refused("File sách có mimetype không hợp lệ; bạn hãy xin người gửi gửi lại.")
        return match.toString(Charsets.US_ASCII)
    }

    private fun readEdits(zip: ZipFile, resolve: (String) -> String = { it }): Edits {
        var edits = BookEdits.empty()
        zip.getEntry(resolve(BookEdits.EDITS_FILE))?.let { entry ->
            val data = readLimited(zip, entry, BookEdits.MAX_EDITS_BYTES) ?: throw Refused("Phần sửa của sách quá lớn.")
            edits = try {
                BookEdits.parse(data)
            } catch (error: BookEdits.EditsError) {
                throw Refused(error.message.orEmpty())
            }
        }
        if (BookEdits.pinnedFiles(edits).any { zip.getEntry(resolve(it)) == null }) throw Refused("File sách thiếu bài nhạc mà người nghe đã chọn.")
        val entry = zip.getEntry(resolve(BookEdits.EDITS_COVER))
        if ((entry != null) != (edits.opt("cover") is JSONObject)) throw Refused("Ảnh bìa trong phần sửa của sách không khớp.")
        if (entry == null) return Edits(edits, null)
        val cover = readLimited(zip, entry, BookEdits.MAX_COVER_BYTES)
        if (cover == null || cover.size < 3 || cover[0] != 0xFF.toByte() || cover[1] != 0xD8.toByte() || cover[2] != 0xFF.toByte()) {
            throw Refused("Ảnh bìa trong phần sửa của sách không dùng được.")
        }
        return Edits(edits, cover)
    }

    /** Đọc một mục của gói, không quá `limit` byte (nhiều hơn thì null) - không tin cỡ khai trong gói. */
    private fun readLimited(zip: ZipFile, entry: ZipEntry, limit: Int): ByteArray? {
        if (entry.size > limit) return null
        val out = java.io.ByteArrayOutputStream()
        zip.getInputStream(entry).use { input ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                out.write(buffer, 0, read)
                if (out.size() > limit) return null
            }
        }
        return out.toByteArray()
    }

    /**
     * Thư mục cũ của cuốn này đã có phần sửa của người nghe: hợp nó với phần sửa của file (BookEdits.merge: bên máy này thắng)
     * vào bản vừa giải nén, TRƯỚC khi bản cũ bị thay - nhập lại một cuốn không bao giờ xoá việc người nghe đã làm.
     */
    private fun keepLocalEdits(old: File, staging: File, incoming: JSONObject) {
        val local = BookEdits.load(old)
        if (BookEdits.isEmpty(local)) return
        val (merged, report) = BookEdits.merge(local, incoming)
        BookEdits.save(staging, merged)
        if (report.opt("cover") == "local") {
            File(staging, BookEdits.EDITS_COVER).parentFile?.mkdirs()
            File(old, BookEdits.EDITS_COVER).copyTo(File(staging, BookEdits.EDITS_COVER), overwrite = true)
        }
        for (name in BookEdits.pinnedFiles(merged)) { // bài người nghe đã ghim ở máy này: file của nó không mất khi nhập lại
            val kept = File(old, name)
            val fresh = File(staging, name)
            if (kept.isFile && !fresh.exists()) {
                fresh.parentFile?.mkdirs()
                kept.copyTo(fresh)
            }
        }
    }

    /** Tên mục hợp lệ của một file .abook phiên bản `version` (BookDocumentWriter dùng cùng bộ luật với bộ nhập). */
    internal fun contentPattern(version: Int): Regex =
        if (version >= 5) CONTENT_V5 else if (version >= 4) CONTENT_V4 else if (version >= 3) CONTENT_V3 else CONTENT

    /**
     * Cỡ + mã băm các mục DÙNG ĐỂ nhận ra một cuốn (`fingerprints.identity_prints` bên Python): audio từng chương (`chapters/...`);
     * cuốn chưa có audio nào thì chữ từng chương (`texts/<n>.txt`) - không thì mọi cuốn chỉ có chữ cùng một khoá.
     */
    internal fun identityPrints(content: Collection<String>, files: JSONObject): JSONObject {
        fun pick(prefix: String): JSONObject {
            val out = JSONObject()
            for (name in content.filter { it.startsWith(prefix) }.sorted()) {
                val meta = files.getJSONObject(name)
                out.put(name, JSONObject().put("size", meta.optLong("size")).put("sha256", meta.optString("sha256")))
            }
            return out
        }
        return pick("chapters/").takeIf { it.length() > 0 } ?: pick("texts/")
    }

    /**
     * Bố cục của một file dự án đã kiểm hình dạng (`ProjectFile._validate` bên Python): `files` - cỡ + mã băm MỌI mục logic (kể cả
     * bí danh); `aliases` - {bí danh: mục thật}; `listening` - các mục logic mang tên của file .abook; `materialize` - những mục
     * sẽ giải ra thư mục sách (phần nghe, `views/`, và - khi file có xưởng - `project/` + `sources/` thật sự nằm trong gói).
     */
    private class ProjectLayout(
        val files: JSONObject, val aliases: Map<String, String>, val listening: Set<String>, val materialize: List<String>,
        val manifestBytes: ByteArray,
    ) {
        /** Tên mục thật trong gói chứa byte của `name` (chính nó nếu không phải bí danh). */
        fun resolve(name: String) = aliases[name] ?: name

        fun neededBytes(): Long = materialize.sumOf { files.getJSONObject(it).optLong("size") } + manifestBytes.size

        /** `book.json` khớp phần còn lại của gói: `package.files` mang đúng cỡ + mã băm ghi ở `project.json`, mọi chương trỏ tới audio hay chữ có thật. */
        fun checkListening(book: JSONObject, listed: JSONObject) {
            for (name in listed.keys()) {
                val ours = files.optJSONObject(name)
                val theirs = listed.getJSONObject(name)
                if (ours == null || ours.optLong("size", -1) != theirs.optLong("size", -2) || ours.optString("sha256") != theirs.optString("sha256")) {
                    throw Refused("Phần nghe của dự án không khớp nội dung gói.")
                }
            }
            val chapters = book.optJSONArray("chapters")
            for (index in 0 until (chapters?.length() ?: 0)) {
                val file = chapters?.optJSONObject(index)?.optString("file").orEmpty()
                if (file.isNotEmpty() && file !in listening) throw Refused("Phần nghe của dự án thiếu audio của một chương.")
                val written = chapters?.optJSONObject(index)?.opt("text")
                if (written != null && written != JSONObject.NULL && (written !is String || written.isNotEmpty() && written !in listening)) {
                    throw Refused("Phần nghe của dự án thiếu chữ của một chương.")
                }
            }
        }
    }

    /**
     * `project.json` đúng loại, đúng phiên bản (cũ hơn hay mới hơn đều nhắc), tên mục đúng định dạng, bí danh hợp lệ (đích có thật
     * trong gói, cùng cỡ + mã băm), `workshop` khớp nội dung (có xưởng thì có sổ dự án; chờ xưởng thì không có `project/`), các
     * bản chụp là JSON. Sai thì từ chối cả file TRƯỚC khi chép gì.
     */
    private fun projectLayout(zip: ZipFile, names: Set<String>): ProjectLayout {
        val entry = zip.getEntry(ProjectDocument.MANIFEST) ?: throw Refused("File dự án thiếu phần mô tả (project.json).")
        if (entry.size > MAX_JSON_BYTES) throw Refused("project.json quá lớn.")
        val bytes = zip.getInputStream(entry).use { it.readBytes() }
        val manifest = try {
            parseObject(bytes)
        } catch (error: Exception) {
            throw Refused("project.json hỏng.")
        }
        if (manifest.optString("format") != ProjectDocument.FORMAT) throw Refused("Đây không phải file sách của app.")
        val version = manifest.optInt("version", -1)
        if (version < 1) throw Refused("File dự án có phiên bản định dạng không hợp lệ.")
        if (version > ProjectDocument.VERSION) throw Refused("Dự án này được gói bằng bản app mới hơn. Hãy cập nhật app để mở.")
        if (version < ProjectDocument.VERSION) {
            throw Refused("Dự án dùng định dạng cũ — bạn mở bằng bản app đã gói rồi gói lại.")
        }
        val workshop = manifest.optString("workshop")
        if (workshop != ProjectDocument.PRESENT && workshop != ProjectDocument.PENDING) throw Refused("File dự án không nói rõ có xưởng hay chưa.")
        val files = manifest.optJSONObject("files")
        val aliasJson = manifest.optJSONObject("aliases")
        if (files == null || aliasJson == null) throw Refused("Danh sách file trong dự án không khớp nội dung gói.")
        val content = names - setOf("mimetype", ProjectDocument.MANIFEST)
        for (name in content) {
            if (name != "book.json" && !ProjectDocument.listeningName(name) && !ProjectDocument.VIEW.matches(name) && !ProjectDocument.safeEntry(name)) {
                throw Refused("Gói có mục lạ: $name")
            }
        }
        val aliases = HashMap<String, String>()
        for (alias in aliasJson.keys().asSequence().toList()) {
            val target = aliasJson.opt(alias) as? String
            val sameBytes = target != null && files.optJSONObject(alias) != null && files.optJSONObject(target) != null &&
                files.getJSONObject(alias).toString() == files.getJSONObject(target).toString()
            if (target == null || alias in content || target !in content || !ProjectDocument.aliasable(alias) || !ProjectDocument.aliasable(target) ||
                !(ProjectDocument.safeEntry(alias) || ProjectDocument.listeningName(alias))) {
                throw Refused("Bí danh $alias trong dự án không hợp lệ.")
            }
            if (!sameBytes) throw Refused("Bí danh $alias không khớp mục thật của nó.")
            aliases[alias] = target
        }
        if (files.keys().asSequence().toSet() != content + aliases.keys) throw Refused("Danh sách file trong dự án không khớp nội dung gói.")
        for (name in files.keys()) {
            val meta = files.optJSONObject(name)
            val size = meta?.opt("size")
            if (meta == null || meta.opt("sha256") !is String || (size !is Int && size !is Long) ||
                (name in content && zip.getEntry(name).size != meta.getLong("size"))) {
                throw Refused("Mô tả file $name không khớp gói.")
            }
        }
        when (workshop) {
            ProjectDocument.PRESENT -> if ("project/project.sqlite3" !in content || "project/book_settings.json" !in content) {
                throw Refused("File dự án thiếu sổ dự án hay cài đặt sách.")
            }
            else -> if (files.keys().asSequence().any { it.startsWith("project/") }) throw Refused("File dự án chưa có xưởng mà lại mang sổ dự án.")
        }
        val views = files.keys().asSequence().filter { ProjectDocument.VIEW.matches(it) }.sorted().toList()
        for (name in views) {
            val meta = files.getJSONObject(name)
            val text = if (meta.getLong("size") > ProjectDocument.MAX_VIEW_BYTES) null else readLimited(zip, zip.getEntry(name), ProjectDocument.MAX_VIEW_BYTES.toInt())
            val valid = text != null && runCatching { StrictJson.parse(text.toString(Charsets.UTF_8)) }.isSuccess
            if (!valid) throw Refused("Bản chụp $name hỏng.")
        }
        val listening = files.keys().asSequence().filter { ProjectDocument.listeningName(it) }.toSet()
        val workshopFiles = if (workshop == ProjectDocument.PRESENT) {
            content.filter { (it.startsWith("project/") || it.startsWith("sources/")) && it !in aliases }.sorted()
        } else {
            content.filter { it.startsWith("sources/") }.sorted()
        }
        return ProjectLayout(files, aliases, listening, listening.sorted() + views + workshopFiles, bytes)
    }

    /**
     * Tên thư mục cho cuốn mở từ file, suy từ nội dung - mở lại đúng file ấy thì trùng tên. Đúng công thức của máy tính
     * (abook/webui/fingerprints.py: content_key): "f-" + 24 hex đầu của sha256("tên:sha256" các chương, xếp tên).
     */
    fun contentKey(chapters: JSONObject): String {
        val text = chapters.keys().asSequence().sorted()
            .joinToString("\n") { "$it:${chapters.getJSONObject(it).optString("sha256")}" }
        val digest = MessageDigest.getInstance("SHA-256").digest(text.toByteArray(Charsets.UTF_8))
        return "f-" + digest.joinToString("") { "%02x".format(it) }.take(24)
    }

    private fun extract(zip: ZipFile, name: String, target: File, reuse: File? = null): Pair<Long, String> {
        target.parentFile?.mkdirs()
        val digest = MessageDigest.getInstance("SHA-256")
        var size = 0L
        zip.getInputStream(zip.getEntry(name)).use { source ->
            (if (reuse == null) target.outputStream() else null).use { sink ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = source.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                    sink?.write(buffer, 0, read)
                    size += read
                }
            }
        }
        if (reuse != null) {
            try { Os.link(reuse.absolutePath, target.absolutePath) }
            catch (_: Exception) { reuse.copyTo(target); target.setLastModified(reuse.lastModified()) }
        }
        return size to digest.digest().joinToString("") { "%02x".format(it) }
    }

    private fun replace(books: File, staging: File, target: File, id: String) = synchronized(Store) {
        if (!target.exists()) {
            if (!staging.renameTo(target)) throw Refused("Không ghi được sách vào thư viện.")
            return@synchronized
        }
        val retired = File(books, ".$id.${System.nanoTime()}.old")
        if (!target.renameTo(retired)) throw Refused("Không thay được bản cũ của sách.")
        if (!staging.renameTo(target)) {
            retired.renameTo(target)
            throw Refused("Không ghi được sách vào thư viện.")
        }
        retired.deleteRecursively()
    }
}
