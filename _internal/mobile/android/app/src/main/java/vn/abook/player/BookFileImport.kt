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
 * File dự án .abookproj (abook/webui/projectfile.py) mang luôn phần NGHE của sách: `book.json` như của file .abook, audio
 * chương nằm ở project/output/chapters/<tên>.mp3. Điện thoại chỉ nhập phần nghe - book.json, các chương, cast/scripts/
 * samples/music/bìa; sổ dự án (project/project.sqlite3), bản thu từng câu và nguồn chương KHÔNG bao giờ được giải nén. Vào
 * thư viện nó là một cuốn như mọi cuốn nhập từ file: audio chương được đặt về chapters/<tên>.mp3 (book.json và `package`
 * sửa theo), nên mã nhận cuốn, nhập lại, so với cuốn đã có trên máy dùng đúng như file .abook - chỗ trống cũng tính theo
 * phần nghe, không theo cả gói.
 */
object BookFileImport {
    const val MIMETYPE = "application/vnd.ngdtuanh.abook+zip"
    const val PROJECT_MIMETYPE = "application/vnd.ngdtuanh.abookproj+zip"
    private const val FORMAT = "abook"
    private const val PROJECT_FORMAT = "abookproj"
    private const val PROJECT_FORMAT_VERSION = 2  // 1 = dự án thuần (không có phần nghe); 2 = thêm book.json + cast/scripts/samples/music
    private const val PROJECT_MAX_ENTRIES = 1_000_000
    private const val FORMAT_VERSION = 4  // 2 = có thêm rãnh nhạc nền (music/<sha1>.<mp3|m4a|ogg|opus|flac|wav>; bài người dùng nhập giữ định dạng của file); 3 = cả bộ nhiều phần (chapters/<phần>/...); 4 = lớp sửa của người nghe (edits.json, edits/cover.jpg)
    /** Chỗ trống dư ngoài cỡ giải nén (book.json, thư mục tạm): đủ để không đầy bộ nhớ giữa chừng. */
    private const val ROOM_MARGIN = 64L shl 20
    private const val MAX_ENTRIES = 20_000
    private const val MAX_TOTAL_BYTES = 64L shl 30
    private const val MAX_JSON_BYTES = 32L shl 20
    private const val COMMON = """cast\.json|cover\.jpg|scripts/\d+\.json|samples/\d+\.wav|music/[0-9a-f]{40}\.(?:mp3|m4a|ogg|opus|flac|wav)"""
    private val CONTENT = Regex("""$COMMON|chapters/[0-9A-Za-z_.\-]+\.mp3""")
    /** Phiên bản 3 thêm thư mục phần: chapters/<phần>/<tên>.mp3 (phiên bản 1-2 không có - gặp thì là mục lạ). */
    private val CONTENT_V3 = Regex("""$COMMON|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3""")
    /** Phiên bản 4 thêm lớp sửa của người nghe (BookEdits): edits.json và edits/cover.jpg - chỉ file .abook, không phải .abookproj. */
    private val CONTENT_V4 = Regex("""$COMMON|chapters/(?:\d{1,4}/)?[0-9A-Za-z_.\-]+\.mp3|edits\.json|edits/cover\.jpg""")
    private val DESCRIPTIONS = setOf("mimetype", "book.json", "manifest.json")
    /** Audio chương trong file dự án: chỗ nó nằm trong thư mục dự án (webui/store.py chapter_mp3). */
    private val PROJECT_AUDIO = Regex("""project/output/chapters/([^\x00-\x1f<>:"|?*\\/]+\.mp3)""")

    /** Lý do không nhận file - câu chữ để người dùng đọc. */
    class Refused(message: String) : Exception(message)

    /** `keptEdits`: số thay đổi của người nghe đã có sẵn trên cuốn này và được giữ nguyên (0 = cuốn mới hay chưa sửa gì) - giao
     *  diện nói "giữ nguyên N chỉnh sửa của bạn". */
    data class Imported(val id: String, val title: String, val keptEdits: Int = 0)

    /** Chép từ content:// (trình quản lý file, Zalo, Drive...) vào bộ nhớ đệm rồi nhập. */
    fun import(context: Context, uri: Uri): Imported {
        Store.init(context)
        // File dự án có thể vài chục GB (sổ dự án, từng câu đã thu): đọc thẳng từ chỗ nó nằm, chỉ phần nghe mới được chép.
        openInPlace(context, uri)?.let { descriptor ->
            descriptor.use { return importFile(File("/proc/self/fd/${it.fd}")) }
        }
        val copy = File(context.cacheDir, "import-${System.nanoTime()}.abook")
        try {
            sizeOf(context, uri)?.let { requireRoom(context.cacheDir, it + ROOM_MARGIN) }
            val input = context.contentResolver.openInputStream(uri) ?: throw Refused("Không đọc được file.")
            input.use { source -> copy.outputStream().use { source.copyTo(it) } }
            return importFile(copy)
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
            throw Refused("Bộ nhớ máy không đủ chỗ để mở sách này: cần khoảng ${gigabytes(need)}, còn ${gigabytes(free)}. " +
                "Hãy xoá bớt rồi mở lại file.")
        }
    }

    private fun gigabytes(bytes: Long) = "%.1f GB".format(java.util.Locale.ROOT, bytes / (1L shl 30).toDouble()).replace('.', ',')

    fun importFile(file: File, freeSpace: (File) -> Long = { it.usableSpace }): Imported {
        val zip = try {
            ZipFile(file)
        } catch (error: Exception) {
            throw Refused("Đây không phải file sách của app.")
        }
        zip.use {
            val entries = zip.entries().toList()
            val first = entries.firstOrNull()
            val kind = if (first == null || first.name != "mimetype" || first.method != ZipEntry.STORED) null
            else zip.getInputStream(first).use { it.readBytes() }.toString(Charsets.US_ASCII).trim()
            if (kind != MIMETYPE && kind != PROJECT_MIMETYPE) throw Refused("Đây không phải file sách của app.")
            val project = kind == PROJECT_MIMETYPE
            if (entries.size > if (project) PROJECT_MAX_ENTRIES else MAX_ENTRIES) throw Refused("File sách có quá nhiều mục.")
            val names = HashSet<String>()
            var total = 0L
            for (entry in entries) {
                val name = entry.name
                if (entry.isDirectory || !names.add(name)) throw Refused("Gói có mục trùng hay thư mục lạ: $name")
                total += maxOf(0L, entry.size)
            }
            if (!project && total > MAX_TOTAL_BYTES) throw Refused("File sách quá lớn.")
            if (project) requireSupportedProject(zip)
            val bookEntry = zip.getEntry("book.json") ?: throw Refused(
                if (project) "Dự án này chưa có chương nào nghe được - hãy mở nó bằng ABook trên máy tính."
                else "File sách thiếu phần mô tả (book.json).")
            if (bookEntry.size > MAX_JSON_BYTES) throw Refused("book.json quá lớn.")
            val book = try {
                JSONObject(zip.getInputStream(bookEntry).use { it.readBytes() }.toString(Charsets.UTF_8))
            } catch (error: Exception) {
                throw Refused("book.json hỏng.")
            }
            val pack = book.optJSONObject("package")
            if (pack == null || pack.optString("format") != FORMAT) throw Refused("Đây không phải file sách của app.")
            val version = pack.optInt("version", -1)
            if (version < 1) throw Refused("File sách có phiên bản định dạng không hợp lệ.")
            if (version > FORMAT_VERSION) throw Refused("Sách này được làm bằng bản app mới hơn. Hãy cập nhật app để mở.")
            // Thư mục phần chỉ có từ phiên bản 3, lớp sửa của người nghe từ phiên bản 4 (và chỉ file .abook - file dự án thì không).
            val allowed = if (project) (if (version >= 3) CONTENT_V3 else CONTENT) else contentPattern(version)
            // File dự án: chỉ phần nghe (những gì `package.files` kể) được nhận; mọi mục khác của gói (sổ dự án, bản thu từng
            // câu, nguồn chương) không bao giờ được giải nén nên không cần xét.
            val listening = if (project) names.filter { allowed.matches(it) || PROJECT_AUDIO.matches(it) }.toSet() else null
            if (!project) for (name in names - DESCRIPTIONS) if (!allowed.matches(name)) throw Refused("Gói có mục lạ: $name")
            val files = pack.optJSONObject("files") ?: throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            val content = listening ?: (names - DESCRIPTIONS)
            if (files.keys().asSequence().toSet() != content) {
                throw Refused("Danh sách file trong sách không khớp nội dung gói.")
            }
            // Lớp sửa của người nghe mà file mang theo (phiên bản 4): sai thì từ chối cả file, TRƯỚC khi chép gì.
            val incoming = if (project) Edits(BookEdits.empty(), null) else readEdits(zip)
            // File dự án: audio chương về chapters/<tên>.mp3 như mọi cuốn nhập từ file; book.json và `package` sửa theo.
            val local ={ name: String -> PROJECT_AUDIO.matchEntire(name)?.let { "chapters/${it.groupValues[1]}" } ?: name }
            if (project) relocateChapters(book, pack, files, content, local)
            // Sách không mang mã nào (chủ sách 27-09): app nhận ra cùng một lần sản xuất bằng audio từng chương.
            val chapters = JSONObject()
            for (name in content.filter { local(it).startsWith("chapters/") }) {
                val meta = files.getJSONObject(name)
                chapters.put(local(name), JSONObject().put("size", meta.optLong("size")).put("sha256", meta.optString("sha256")))
            }
            // Cùng cuốn đã có trên máy (tải qua Wi-Fi, hay mở từ file trước đó): nhập VÀO đúng cuốn ấy, giữ mã của nó để
            // chỗ nghe vẫn nối - không thành hai cuốn. Bản trên máy nhiều chương hơn file thì giữ nguyên bản trên máy.
            val existing = Store.findByChapters(chapters)
            val target = existing ?: contentKey(chapters)
            val current = existing?.let { Store.rawManifest(it) }
            // Chỉ cuốn mở từ file mới nhận phần sửa của người nghe; cuốn của máy tính thì sửa ở máy ấy.
            val editable = existing == null || Store.isImported(existing)
            val keptEdits = if (existing != null && editable) BookEdits.count(BookEdits.load(Store.bookDir(target))) else 0
            if (current != null && current.optInt("chaptersAvailable") > book.optInt("chaptersAvailable")) {
                // Giữ bản trên máy, nhưng phần sửa trong file vẫn được hợp vào (bên máy này thắng) - không mất công của ai.
                if (editable && BookEdits.count(incoming.edits) > 0) BookEdits.adopt(Store.bookDir(target), incoming.edits, incoming.cover)
                return Imported(target, Store.manifest(target)?.optString("title") ?: current.optString("title"), keptEdits)
            }
            val books = File(Store.root, "books").apply { mkdirs() }
            // File dự án: chỗ cần là cỡ phần nghe sẽ giải nén, không phải cả gói.
            val needed = if (project) content.sumOf { maxOf(0L, zip.getEntry(it).size) } else total
            requireRoom(books, needed + ROOM_MARGIN, freeSpace)
            val staging = File(books, ".$target.${System.nanoTime()}.part")
            try {
                for (name in DESCRIPTIONS.filter { it != "mimetype" && it in names && (!project || it == "book.json") } + content.sorted()) {
                    val (size, sha256) = extract(zip, name, File(staging, local(name)))
                    val expected = files.optJSONObject(name) ?: continue
                    if (size != expected.optLong("size", -1) || sha256 != expected.optString("sha256")) {
                        throw Refused("File sách bị hỏng hoặc bị sửa ($name). Hãy chép lại file từ nguồn.")
                    }
                }
                if (editable) keepLocalEdits(Store.bookDir(target), staging, incoming.edits)
                else File(staging, BookEdits.EDITS_FILE).delete().also { File(staging, BookEdits.EDITS_COVER).delete() }
                // Bản sách của app trên máy mang mã thư mục của app (book.json không nằm trong danh sách mã băm).
                Store.writeAtomic(File(staging, "book.json"), book.put("id", target).toString())
                replace(books, staging, Store.bookDir(target), target)
            } finally {
                staging.deleteRecursively()
            }
            Store.rememberChapters(target, chapters, imported = existing == null || Store.isImported(existing))
            return Imported(target, Store.manifest(target)?.optString("title") ?: book.optString("title"), keptEdits)
        }
    }

    /** Phần sửa của người nghe trong file (đã kiểm) và byte ảnh bìa sửa của nó. */
    private class Edits(val edits: JSONObject, val cover: ByteArray?)

    /**
     * `edits.json` đúng giao ước (BookEdits.validate - sai thì từ chối cả file) và bìa sửa đi đôi với nó: có `cover` là đối tượng
     * thì phải có edits/cover.jpg, và ngược lại; là JPEG, không quá cỡ (bookfile.py `_check_edits`).
     */
    private fun readEdits(zip: ZipFile): Edits {
        var edits = BookEdits.empty()
        zip.getEntry(BookEdits.EDITS_FILE)?.let { entry ->
            val data = readLimited(zip, entry, BookEdits.MAX_EDITS_BYTES) ?: throw Refused("Phần sửa của sách quá lớn.")
            edits = try {
                BookEdits.parse(data)
            } catch (error: BookEdits.EditsError) {
                throw Refused(error.message.orEmpty())
            }
        }
        val entry = zip.getEntry(BookEdits.EDITS_COVER)
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
    }

    /** Tên mục hợp lệ của một file .abook phiên bản `version` (BookDocumentWriter dùng cùng bộ luật với bộ nhập). */
    internal fun contentPattern(version: Int): Regex = if (version >= 4) CONTENT_V4 else if (version >= 3) CONTENT_V3 else CONTENT

    /** File dự án: `project.json` đúng loại và không mới hơn app (không thì nhắc cập nhật, như file sách). */
    private fun requireSupportedProject(zip: ZipFile) {
        val entry = zip.getEntry("project.json") ?: throw Refused("File dự án thiếu phần mô tả (project.json).")
        if (entry.size > MAX_JSON_BYTES) throw Refused("project.json quá lớn.")
        val manifest = try {
            JSONObject(zip.getInputStream(entry).use { it.readBytes() }.toString(Charsets.UTF_8))
        } catch (error: Exception) {
            throw Refused("project.json hỏng.")
        }
        if (manifest.optString("format") != PROJECT_FORMAT) throw Refused("Đây không phải file sách của app.")
        val version = manifest.optInt("version", -1)
        if (version < 1) throw Refused("File dự án có phiên bản định dạng không hợp lệ.")
        if (version > PROJECT_FORMAT_VERSION) throw Refused("Dự án này được gói bằng bản app mới hơn. Hãy cập nhật app để mở.")
    }

    /**
     * Sửa `book.json` của file dự án cho đúng chỗ audio sẽ nằm sau khi nhập: chương trỏ `project/output/chapters/x.mp3` thành
     * `chapters/x.mp3`, và `package.files` đổi khoá theo. Chương nào trỏ tới audio không có trong phần nghe thì từ chối.
     */
    private fun relocateChapters(book: JSONObject, pack: JSONObject, files: JSONObject, content: Set<String>, local: (String) -> String) {
        val chapters = book.optJSONArray("chapters")
        for (index in 0 until (chapters?.length() ?: 0)) {
            val chapter = chapters?.optJSONObject(index) ?: continue
            val file = chapter.optString("file")
            if (file.isEmpty()) continue
            if (file !in content || !PROJECT_AUDIO.matches(file)) throw Refused("File sách thiếu audio của một chương.")
            chapter.put("file", local(file))
        }
        val renamed = JSONObject()
        for (name in files.keys()) renamed.put(local(name), files.getJSONObject(name))
        pack.put("files", renamed)
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

    private fun extract(zip: ZipFile, name: String, target: File): Pair<Long, String> {
        target.parentFile?.mkdirs()
        val digest = MessageDigest.getInstance("SHA-256")
        var size = 0L
        zip.getInputStream(zip.getEntry(name)).use { source ->
            target.outputStream().use { sink ->
                val buffer = ByteArray(1 shl 16)
                while (true) {
                    val read = source.read(buffer)
                    if (read < 0) break
                    digest.update(buffer, 0, read)
                    sink.write(buffer, 0, read)
                    size += read
                }
            }
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
