package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONException
import java.io.File
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID
import kotlin.concurrent.thread

/**
 * Kho trên điện thoại: sách đã tải (books/<id>/book.json + file) và HỒ SƠ NGHE (state/<mã hồ sơ>.json).
 *
 * Hồ sơ nghe độc lập với sách (chủ sách 27-09): hồ sơ không biết mình thuộc sách nào, sách không biết gì về việc nghe;
 * app giữ bảng liên kết `records.json` - một sách nhiều hồ sơ, một hồ sơ đang dùng - giống hệt máy tính
 * (abook/webui/listening.py). Mọi hàm nhận MÃ SÁCH làm việc trên hồ sơ đang dùng của sách ấy.
 *
 * Trạng thái của hồ sơ CÙNG hình dạng với máy tính để hai bên gộp được với nhau: mỗi phần mang mốc thời gian riêng,
 * dấu trang đã xoá để lại dấu vết trong "deleted".
 */
object Store {
    private const val DONE_TAIL_SECONDS = 20.0
    lateinit var root: File
        private set

    fun init(context: Context) {
        if (!::root.isInitialized) {
            root = File(context.filesDir, "library").apply { mkdirs() }
            // Mở file sách bị cắt giữa chừng (app bị giết, máy tắt): bản đang giải / bản cũ chờ xoá nằm lại trong books/.
            // Đổi tên trả lại ngay (rẻ); xoá thì ở nền - danh sách sách không bao giờ thấy chúng (bookFolders).
            val stale = recoverStaging()
            recoverRekeys()
            if (stale.isNotEmpty()) thread(name = "abook-staging-sweep", isDaemon = true) { stale.forEach { it.deleteRecursively() } }
        }
    }

    internal fun requireBookId(id: String): String {
        require(id.isNotEmpty() && id.length <= 200 && id.all { it.code < 128 && it.isLetterOrDigit() || it == '_' || it == '-' } &&
            !Regex("(?i)CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]").matches(id)) {
            "Mã sách không hợp lệ; bạn hãy kiểm tra lại máy gửi sách."
        }
        return id
    }

    fun bookDir(id: String): File {
        requireBookId(id)
        val books = File(root, "books").canonicalFile
        val dir = File(books, id).canonicalFile
        require(dir.parentFile == books) { "Thư mục sách nằm ngoài thư viện của bạn." }
        return dir
    }

    /** Thư mục của từng cuốn trong books/ - trừ thư mục tạm tên bắt đầu bằng "." (bản đang giải `.<mã>.<số>.part`, bản cũ
     *  chờ xoá `.<mã>.<số>.old` của BookFileImport): bị cắt giữa chừng thì chúng có book.json mà không phải một cuốn. */
    fun bookFolders(): List<File> =
        File(root, "books").listFiles()?.filter { it.isDirectory && !it.name.startsWith(".") } ?: emptyList()

    private val STAGING = Regex("""\.(.+)\.\d+\.(part|old)""")
    const val STAGING_MAX_AGE_MS = 60 * 60 * 1000L

    /**
     * Thư mục tạm của BookFileImport còn lại sau một lần bị cắt: bản cũ (`.old`) mà bản chính vắng - cắt giữa hai lần đổi tên
     * của `replace` - thì đổi tên trả lại; còn lại, cũ hơn [STAGING_MAX_AGE_MS], là thứ phải xoá (trả về để xoá ở nền).
     */
    @Synchronized
    fun recoverStaging(now: Long = System.currentTimeMillis()): List<File> {
        val stale = ArrayList<File>()
        for (dir in File(root, "books").listFiles()?.filter { it.isDirectory && it.name.startsWith(".") } ?: emptyList()) {
            val match = STAGING.matchEntire(dir.name) ?: continue
            if (match.groupValues[2] == "old") {
                val home = runCatching { deletableBookDir(match.groupValues[1]) }.getOrNull()
                if (home != null && !home.exists() && dir.renameTo(home)) continue
            }
            if (now - dir.lastModified() > STAGING_MAX_AGE_MS) stale.add(dir)
        }
        return stale
    }

    fun file(id: String, relative: String): File = contained(bookDir(id), relative)

    /** `relative` trong thư mục `dir`; ra ngoài thì từ chối (đường dẫn lấy từ book.json hay từ người lạ). */
    fun contained(dir: File, relative: String): File {
        require(PeerPaths.safeRelative(relative)) { "Đường dẫn trong sách không hợp lệ; bạn hãy kiểm tra lại máy gửi sách." }
        val target = File(dir, relative).canonicalFile
        val base = dir.canonicalFile
        // Ranh giới thành phần qua separator, dùng được cả Android 24/25 (java.nio.file cần API 26).
        require(target != base && target.path.startsWith(base.path.trimEnd(File.separatorChar) + File.separator)) {
            "Đường dẫn nằm ngoài thư mục sách của bạn."
        }
        return target
    }

    /**
     * `book.json` NGUYÊN VĂN của người làm sách (hay của máy tính), không có lớp sửa của người nghe. Chỗ nào GHI book.json lại
     * (nhận mã, đổi mã) hay so sách với file dùng hàm này - `manifest` đã phủ lớp sửa lên, ghi ngược nó là biến thay đổi của
     * người nghe thành nội dung của sách.
     */
    @Synchronized
    fun rawManifest(id: String): JSONObject? {
        val file = File(bookDir(id), "book.json")
        return readJson(file)
    }

    /**
     * Sửa `book.json` của cuốn đã tải tại chỗ (đọc, đổi, ghi nguyên tử dưới cùng khoá với mọi nơi khác ghi nó). Giữ mốc sửa của file: "Mới thêm" và
     * `updatedAt` của thư viện chia sẻ đọc mốc ấy, nên chỉ đổi mô tả thì cuốn không nhảy lên đầu "Mới thêm". Cuốn không còn thì không làm gì.
     */
    @Synchronized
    fun rewriteManifest(id: String, change: (JSONObject) -> JSONObject): Boolean {
        val file = File(bookDir(id), "book.json")
        val current = readJson(file) ?: return false
        val stamp = file.lastModified()
        writeAtomic(file, change(current).toString())
        if (stamp > 0) file.setLastModified(stamp)
        return true
    }

    /**
     * `book.json` như NGƯỜI NGHE thấy: lớp sửa (BookEdits: tên sách, bìa, tên chương, nhạc) phủ lên sách, kèm `edits` (số
     * thay đổi) và `capabilities` (docs/EDITING.md) - trình phát, thông báo, widget, thư viện đều đọc qua đây.
     */
    @Synchronized
    fun manifest(id: String): JSONObject? = rawManifest(id)?.let { shown(id, it, printsBook()) }

    private fun shown(id: String, raw: JSONObject, prints: JSONObject): JSONObject {
        val edits = BookEdits.load(bookDir(id))
        // `edits`: mọi thay đổi (áp ngay + ý muốn); `wishes`: trong số ấy bao nhiêu là ý muốn chờ Studio (chưa áp vào audio).
        // Lines the holder skipped are skipped here too (EditsSync.experienced); the change count stays this device's own.
        val out = BookEdits.applyManifest(raw, EditsSync.experienced(bookDir(id), edits)).put("edits", BookEdits.count(edits))
            .put("unsaved", BookEdits.unsaved(bookDir(id), edits)).put("wishes", BookEdits.countWishes(edits))
        val home = homeOf(raw, prints.optJSONObject(id))
        // Mọi cuốn sửa được ở đây, kể cả nghe thẳng chưa tải và của thiết bị ghép khác (docs/EDITING.md, P2d): phần sửa về máy giữ
        // sách (`sync`) nếu nó nhận được, không thì nằm lại trên máy này (`local`).
        out.put("capabilities", capabilities(link = false, sync = home == Home.COMPUTER, local = home == Home.LOCAL))
        // Cuốn nhập từ file dự án `.abookproj` (ProjectDocument): giữ xưởng của nó / chờ dựng xưởng, kèm các bản chụp chỉ đọc.
        out.put("projectFile", ProjectDocument.info(bookDir(id)) ?: JSONObject.NULL)
        if (home == Home.COMPUTER) out.put("editsSync", EditsSync.view(bookDir(id), EditsSync.pending(bookDir(id), edits)))
        return out
    }

    /** Phần sửa của một cuốn đi về đâu: `COMPUTER` - máy tính (chính, hay máy tính khác đã ghép) nhận được gói sửa; `LOCAL` - cuốn của một
     *  thiết bị ghép không nhận gói sửa (điện thoại khác): sửa chỉ nằm trên máy này; `FILE` - cuốn mở từ file, lưu thành file. */
    enum class Home { COMPUTER, LOCAL, FILE }

    private fun homeOf(manifest: JSONObject, print: JSONObject?): Home = when {
        manifest.optString("source").isNotEmpty() -> if (manifest.optString("sourceKind") == "computer") Home.COMPUTER else Home.LOCAL
        isComputer(manifest, print) -> Home.COMPUTER
        else -> Home.FILE
    }

    /**
     * Điện thoại không có Studio ({toolchain, workshop} luôn false). `sync`: sửa được, và phần sửa gửi về máy tính giữ sách (đã tải hay
     * nghe thẳng). `local`: sửa được nhưng phần sửa chỉ nằm trên máy này (sách của điện thoại khác). `link`: không sửa được ở đây - điện
     * thoại không còn trường hợp nào, giữ trường cho máy tính (sách của điện thoại chia sẻ).
     */
    fun capabilities(link: Boolean, sync: Boolean = false, local: Boolean = false): JSONObject =
        JSONObject().put("toolchain", false).put("workshop", false).put("link", link).put("sync", sync).put("local", local)

    /** Gói sách của cuốn chưa tải (nghe thẳng), như người nghe thấy: lớp sửa phủ lên, kèm khả năng và tình trạng gửi sửa. */
    fun streamed(id: String, manifest: JSONObject): JSONObject = shown(id, manifest, printsBook())

    /** Máy làm được gì với cuốn `id` (EbookLibrary.capabilities): sửa được mọi cuốn; `sync` nếu máy giữ sách là máy tính, `local` nếu là điện thoại khác. */
    fun capabilitiesOf(id: String): JSONObject {
        val raw = rawManifest(id) ?: streamManifest(id) ?: return capabilities(link = false)
        val home = homeOf(raw, printsBook().optJSONObject(id))
        return capabilities(link = false, sync = home == Home.COMPUTER, local = home == Home.LOCAL)
    }

    /**
     * Nơi gửi phần sửa của cuốn `id`: (thiết bị ghép hay null = máy tính chính, mã sách bên ấy); null khi sửa chỉ nằm trên máy này
     * (cuốn mở từ file, hay của điện thoại khác). Đã tải hay nghe thẳng đều tính.
     */
    @Synchronized
    fun editDestination(id: String): Pair<String?, String>? {
        val raw = rawManifest(id) ?: streamManifest(id) ?: return null
        if (homeOf(raw, printsBook().optJSONObject(id)) != Home.COMPUTER) return null
        val source = raw.optString("source")
        return if (source.isEmpty()) null to id else source to raw.optString("remoteId").ifEmpty { id.removePrefix("p${source}_") }
    }

    /** Mã mọi cuốn có gói sách trên máy (đã tải hay nghe thẳng). */
    @Synchronized
    fun bookIds(): List<String> =
        bookFolders().filter { File(it, "book.json").isFile || File(it, "stream.json").isFile }.map { it.name }

    /**
     * Gói sách của mọi cuốn đã tải. KHÔNG giữ khoá của Store suốt cả lượt: thư viện hàng trăm cuốn đọc + phủ lớp sửa từng gói mất hàng trăm mili giây, và
     * trong lúc ấy mọi lần ghi (chỗ nghe, dấu trang) đứng chờ - mỗi cuốn một lần giữ khoá, ghi chen vào giữa được (soát a101 F6).
     */
    fun books(): List<JSONObject> {
        val prints = synchronized(this) { printsBook() }
        return bookFolders().mapNotNull { dir -> synchronized(this) { rawManifest(dir.name)?.let { shown(dir.name, it, prints) } } }
    }

    /**
     * Sách nghe thẳng từ máy tính, chưa tải (Streaming): gói sách cất ở `stream.json` - KHÔNG phải `book.json` - nên
     * không bao giờ bị tính là đã tải; các file nhỏ (bìa, văn bản đọc theo, dàn nhân vật, câu mẫu) nằm cạnh đúng chỗ của
     * sách đã tải, nên giao diện đọc chúng như nhau và tải hẳn về sau chỉ việc ghi thêm audio + `book.json`.
     */
    @Synchronized
    fun streamManifest(id: String): JSONObject? {
        val file = File(bookDir(id), "stream.json")
        return readJson(file)
    }

    /** Gói sách phát được: đã tải thì bản đã tải, không thì bản nghe thẳng đã cất. */
    fun playableManifest(id: String): JSONObject? = manifest(id) ?: streamManifest(id)?.let { shown(id, it, printsBook()) }

    fun playableBooks(): List<JSONObject> {
        val prints = synchronized(this) { printsBook() }
        return bookFolders().mapNotNull { dir ->
            synchronized(this) { (rawManifest(dir.name) ?: streamManifest(dir.name))?.let { shown(dir.name, it, prints) } }
        }
    }

    /** Ảnh bìa người nghe thấy: bìa họ đặt (edits/cover.jpg), hay bìa của sách; null khi họ đã bỏ bìa hay sách không có. */
    fun coverFile(id: String): File? = BookEdits.coverFile(bookDir(id))

    /**
     * Văn bản trong gói như người nghe thấy khi lớp sửa làm nó khác đi: `cast.json` (tên nhân vật đã đổi) và
     * `scripts/<n>.json` (tên người nói, tên chương). null = không có gì phủ lên - dùng đúng file. `shared`: bản gửi máy khác
     * (không dấu ý muốn chưa áp của máy này - [BookEdits.sharedCast]).
     */
    fun overlaidText(id: String, relative: String, shared: Boolean = false): String? {
        val dir = bookDir(id)
        val edits = BookEdits.load(dir)
        if (BookEdits.isEmpty(edits)) return null
        val book = rawManifest(id) ?: return null
        return BookEdits.overlaidText(dir, book, edits, relative, shared)
    }

    /** Nội dung một file văn bản của gói (đã qua lớp sửa); null khi file không có. */
    fun readText(id: String, relative: String): String? {
        val file = file(id, relative)
        if (!file.isFile) return null
        return overlaidText(id, relative) ?: file.readText()
    }

    fun writeAtomic(target: File, text: String) = writeAtomic(target, text.toByteArray(Charsets.UTF_8))

    @Synchronized
    fun writeAtomic(target: File, bytes: ByteArray) {
        check(!target.isDirectory) { "Không ghi được dữ liệu của bạn lên thư mục: ${target.name}" }
        target.parentFile?.mkdirs()
        val temporary = File(target.path + ".part")
        FileOutputStream(temporary).use { stream ->
            stream.write(bytes)
            stream.fd.sync()
        }
        check(temporary.renameTo(target)) { "Không lưu được dữ liệu của bạn: ${target.name}" }
    }

    /** Giữ nguyên byte hỏng để có thể cứu lại, trước khi reader tạo dữ liệu mới. Lỗi I/O vẫn phải báo cho nơi gọi. */
    @Synchronized
    fun readJson(file: File): JSONObject? {
        if (!file.isFile) return null
        return try {
            JSONObject(file.readText(Charsets.UTF_8))
        } catch (error: JSONException) {
            preserveCorrupt(file)
            null
        }
    }

    fun preserveCorrupt(file: File) {
        val copy = File(file.path + ".corrupt-${System.currentTimeMillis()}-${UUID.randomUUID()}")
        check(file.renameTo(copy)) { "Không giữ được bản dữ liệu hỏng của bạn: ${file.name}" }
    }

    // ---- hồ sơ nghe + liên kết với sách ----------------------------------------------------------------------

    private const val DEFAULT_RECORD_NAME = "Mặc định"
    private val RECORD_ID = Regex("r-[0-9a-f]{16}")
    private val SYNC_KEYS = listOf("record", "recordName", "nameAt", "activeAt", "movedAt", "book", "records", "active", "activeState",
        "deleted", "deletedRecords")
    private val recordsFile get() = File(root, "records.json")
    private var recordsCache: JSONObject? = null

    fun isRecordId(value: String) = RECORD_ID.matches(value)

    private fun newRecordId() = "r-" + UUID.randomUUID().toString().replace("-", "").take(16)

    /**
     * Mã hồ sơ "Mặc định" của một cuốn (tạo khi nghe lần đầu hay khi chuyển bản lưu cũ): suy từ mã sách theo đúng công
     * thức của máy tính (webui/listening.py default_record_id) - hai máy cùng nghe một cuốn là cùng MỘT hồ sơ, gộp được,
     * không tách đôi chỗ nghe. Hồ sơ người dùng tự tạo thêm thì mã ngẫu nhiên.
     */
    fun defaultRecordId(bookId: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest("default:$bookId".toByteArray(Charsets.UTF_8))
        return "r-" + digest.joinToString("") { "%02x".format(it) }.take(16)
    }

    /**
     * {"version": 2, "records": {mã: {name, nameAt, createdAt, movedAt}}, "links": {mã sách: {records, active, activeAt}},
     *  "deleted": {mã: lúc xoá}} - bia mộ để hồ sơ đã xoá ở máy nào cũng không sống lại khi đồng bộ.
     */
    private fun recordsBook(): JSONObject {
        recordsCache?.let { return it }
        val loaded = readJson(recordsFile)
        val book = loaded ?: upgradeStates()
        if (!book.has("deleted")) book.put("deleted", JSONObject())
        recordsCache = book
        return book
    }

    /** Bản cũ state/<mã sách>.json: giữ nguồn tới khi bảng liên kết đã commit để restart làm tiếp được. */
    private fun upgradeStates(): JSONObject {
        val book = JSONObject().put("version", 2).put("records", JSONObject()).put("links", JSONObject())
        val sources = File(root, "state").listFiles()?.filter {
            it.isFile && it.name.endsWith(".json") && !RECORD_ID.matches(it.name.removeSuffix(".json"))
        } ?: emptyList()
        for (file in sources) {
            val bookId = file.name.removeSuffix(".json")
            val record = defaultRecordId(bookId)
            val target = File(root, "state/$record.json")
            writeAtomic(target, file.readBytes())
            check(target.isFile) { "Không lưu được hồ sơ nghe của bạn" }
            book.getJSONObject("records").put(record, JSONObject().put("name", DEFAULT_RECORD_NAME).put("createdAt", now()).put("nameAt", 0.0))
            book.getJSONObject("links").put(bookId,
                JSONObject().put("records", JSONArray().put(record)).put("active", record).put("activeAt", 0.0))
        }
        writeAtomic(recordsFile, book.toString())
        check(recordsFile.isFile) { "Không lưu được liên kết hồ sơ nghe của bạn" }
        sources.forEach { it.delete() }
        return book
    }

    private fun saveRecords(book: JSONObject) {
        writeAtomic(recordsFile, book.toString())
        recordsCache = book
    }

    /** Hồ sơ đang dùng của sách - chưa có thì tạo hồ sơ "Mặc định" và gắn vào. */
    @Synchronized
    fun activeRecord(bookId: String): String {
        val book = recordsBook()
        val records = book.getJSONObject("records")
        val links = book.getJSONObject("links")
        val link = links.optJSONObject(bookId) ?: JSONObject().put("records", JSONArray()).put("activeAt", 0.0)
        val active = link.optString("active")
        if (active.isNotBlank() && records.has(active)) return active
        val tombstones = book.getJSONObject("deleted")
        val record = defaultRecordId(bookId).takeUnless { records.has(it) || tombstones.has(it) } ?: newRecordId()
        records.put(record, JSONObject().put("name", DEFAULT_RECORD_NAME).put("createdAt", now()).put("nameAt", 0.0))
        links.put(bookId, link.put("records", (link.optJSONArray("records") ?: JSONArray()).put(record)).put("active", record))
        saveRecords(book)
        return record
    }

    private fun recordFile(record: String) = File(root, "state/$record.json")

    private fun stateFile(bookId: String) = recordFile(activeRecord(bookId))

    private fun withoutSyncKeys(value: JSONObject) = JSONObject(value.toString()).also { copy ->
        // `deleted` còn là bảng bia mộ dấu trang; chỉ cờ boolean mới là metadata xoá hồ sơ.
        SYNC_KEYS.filterNot { it == "deleted" && copy.opt(it) is JSONObject }.forEach(copy::remove)
    }

    /**
     * Gói gửi máy tính (webui/listening.py merge_record): trạng thái hồ sơ đang dùng + mã, tên và lúc đặt tên, lúc chọn
     * nó, lúc chuyển nó sang cuốn này (lần chuyển sau thắng), cùng bia mộ những hồ sơ đã xoá trên điện thoại. Hoặc đúng hồ sơ `only` (hồ sơ vừa rời: chỗ nghe cuối của nó
     * phải tới máy tính) - khi ấy không nhận là "đang chọn" (activeAt 0), nếu không máy tính sẽ chọn lại nó.
     */
    @Synchronized
    fun syncBody(bookId: String, only: String? = null): JSONObject {
        val active = activeRecord(bookId)
        val record = only ?: active
        val book = recordsBook()
        val meta = book.getJSONObject("records").optJSONObject(record)
        val chosenAt = if (record == active) book.getJSONObject("links").optJSONObject(bookId)?.optDouble("activeAt", 0.0) ?: 0.0 else 0.0
        return recordState(record).put("record", record).put("recordName", meta?.optString("name") ?: DEFAULT_RECORD_NAME)
            .put("nameAt", meta?.optDouble("nameAt", 0.0) ?: 0.0).put("activeAt", chosenAt)
            .put("movedAt", meta?.optDouble("movedAt", 0.0) ?: 0.0)
            .put("deletedRecords", book.getJSONObject("deleted"))
    }

    /**
     * Trả lời của máy tính: trạng thái đã gộp của hồ sơ vừa gửi, tên các hồ sơ, sách hồ sơ gắn ở máy tính (có thể đã được
     * chuyển), hồ sơ đang dùng bên ấy - bên chọn sau thắng, kèm trạng thái của nó nếu điện thoại chưa có.
     * Máy tính đời trước không trả `record`: trạng thái ấy là của hồ sơ đang dùng. `player`: cuốn đang nạp trong trình phát
     * và có đang phát không (test JVM đưa giá trị giả - Playback cần Android).
     */
    @Synchronized
    fun applySync(bookId: String, reply: JSONObject, player: () -> Pair<String, Boolean> = { Playback.bookId to Playback.isPlaying },
                  onGone: (Set<String>) -> Unit = { Playback.recordsGone(it) }) {
        val record = reply.optString("record")
        if (!RECORD_ID.matches(record)) {
            save(bookId, mergeStates(state(bookId), withoutSyncKeys(reply)))
            return
        }
        val book = recordsBook()
        val records = book.getJSONObject("records")
        val links = book.getJSONObject("links")
        // bia mộ của máy tính: xoá theo, kể cả hồ sơ vừa gửi (máy tính trả deleted=true)
        val tombstones = reply.optJSONObject("deletedRecords") ?: JSONObject()
        if (reply.optBoolean("deleted")) tombstones.put(record, now())
        val removed = mutableSetOf<String>()
        for (gone in tombstones.keys()) {
            if (!RECORD_ID.matches(gone)) continue
            if (records.has(gone)) removed.add(gone)
            forget(book, gone)
            book.getJSONObject("deleted").put(gone, tombstones.optDouble(gone, now()))
        }
        // Trình phát đang giữ hồ sơ vừa bị xoá từ máy khác thì phải dừng / đóng phiên và chọn hồ sơ thay thế (sau khi sổ đã lưu): lần lưu
        // kế không được rơi sang hồ sơ còn lại (hay đẻ hồ sơ mới).
        if (reply.optBoolean("deleted") || book.getJSONObject("deleted").has(record)) {
            saveRecords(book)
            if (removed.isNotEmpty()) onGone(removed)
            return
        }
        // Trong lúc chờ mạng người nghe vẫn sửa hồ sơ: gộp với bản đang có của ĐÚNG mã vừa gửi.
        writeAtomic(recordFile(record), mergeStates(recordState(record), withoutSyncKeys(reply)).toString())
        val known = reply.optJSONArray("records") ?: JSONArray()
        for (index in 0 until known.length()) {
            val item = known.optJSONObject(index) ?: continue
            val id = item.optString("id")
            if (!RECORD_ID.matches(id) || book.getJSONObject("deleted").has(id)) continue
            val meta = records.optJSONObject(id) ?: JSONObject().put("createdAt", now()).put("nameAt", 0.0)
            // tên: bên đổi sau thắng
            if (!meta.has("name") || item.optDouble("nameAt", 0.0) > meta.optDouble("nameAt", 0.0)) {
                meta.put("name", item.optString("name", DEFAULT_RECORD_NAME)).put("nameAt", item.optDouble("nameAt", 0.0))
            }
            records.put(id, meta)
        }
        // Hồ sơ gắn ở cuốn nào: lần chuyển sau thắng (webui/listening.py merge_record trả `book` + `movedAt` đã phân xử).
        // Máy tính nói cuốn khác mà hồ sơ được chuyển ở đây sau đó (máy tính đời trước, không biết movedAt): giữ chỗ gắn ở đây.
        val remoteMoved = reply.optDouble("movedAt", 0.0)
        val pushed = records.optJSONObject(record)
        val replied = reply.optString("book").ifBlank { bookId }
        val owner = if (replied != bookId && (pushed?.optDouble("movedAt", 0.0) ?: 0.0) > remoteMoved) bookId else replied
        if (pushed != null && remoteMoved > pushed.optDouble("movedAt", 0.0)) pushed.put("movedAt", remoteMoved)
        if (owner != bookId) unlink(links, bookId, record)
        val link = links.optJSONObject(owner) ?: JSONObject().put("records", JSONArray()).put("activeAt", 0.0)
        addRecord(link, record)
        // Mọi hồ sơ máy giữ sách biết của cuốn này (không chỉ hồ sơ vừa gửi và hồ sơ đang chọn) hiện trong bộ chọn hồ sơ: hồ sơ chưa
        // thuộc cuốn nào ở đây thì gắn vào; đang ở cuốn khác thì theo lần chuyển sau thắng (`movedAt`, như hồ sơ vừa gửi).
        for (index in 0 until known.length()) {
            val item = known.optJSONObject(index) ?: continue
            val id = item.optString("id")
            val meta = records.optJSONObject(id) ?: continue
            if (!RECORD_ID.matches(id) || id == record || book.getJSONObject("deleted").has(id)) continue
            val there = ownerOf(links, id)
            val theirMoved = item.optDouble("movedAt", 0.0)
            if (there != null && there != owner) {
                if (theirMoved <= meta.optDouble("movedAt", 0.0)) continue
                unlink(links, there, id)
            }
            if (there == owner || there == null || theirMoved > meta.optDouble("movedAt", 0.0)) {
                addRecord(link, id)
                if (theirMoved > meta.optDouble("movedAt", 0.0)) meta.put("movedAt", theirMoved)
            }
        }
        val active = reply.optJSONObject("active")
        val chosen = active?.optString("record").orEmpty()
        val chosenAt = active?.optDouble("at", 0.0) ?: 0.0
        // Cuốn đang PHÁT thì chưa đổi hồ sơ (trình phát ghi vào hồ sơ đang dùng: chỗ nghe của hồ sơ cũ sẽ rơi sang hồ sơ
        // mới) - lần đồng bộ sau, lúc đã dừng (dừng là đẩy ngay), đổi. Đang dừng thì đổi, rồi trình phát theo sang.
        val (loaded, playing) = player()
        val holding = loaded == owner
        var follow = false
        // Hồ sơ máy tính đang chọn cho cuốn này mà điện thoại đã chuyển sang cuốn khác sau lần chuyển máy tính biết: không
        // kéo nó về (máy tính theo lần chuyển ấy khi điện thoại đẩy hồ sơ đó dưới cuốn mới của nó).
        val movedAway = chosen != record && ownerOf(links, chosen).let { it != null && it != owner } &&
            (records.optJSONObject(chosen)?.optDouble("movedAt", 0.0) ?: 0.0) > remoteMovedAt(known, chosen)
        if (RECORD_ID.matches(chosen) && !book.getJSONObject("deleted").has(chosen) &&
            chosenAt > link.optDouble("activeAt", 0.0) && !(holding && playing) && !movedAway) {
            follow = holding && link.optString("active") != chosen
            // máy tính đã chuyển hồ sơ ấy sang cuốn này: gỡ khỏi cuốn cũ ở đây, nhớ lúc chuyển
            ownerOf(links, chosen)?.takeIf { it != owner }?.let { unlink(links, it, chosen) }
            records.optJSONObject(chosen)?.let { meta ->
                remoteMovedAt(known, chosen).takeIf { it > meta.optDouble("movedAt", 0.0) }?.let { meta.put("movedAt", it) }
            }
            addRecord(link, chosen)
            link.put("active", chosen).put("activeAt", chosenAt)
            reply.optJSONObject("activeState")?.let {
                writeAtomic(recordFile(chosen), mergeStates(recordState(chosen), withoutSyncKeys(it)).toString())
            }
        }
        if (link.optString("active").isBlank()) link.put("active", record)
        links.put(owner, link)
        saveRecords(book)
        if (removed.isNotEmpty()) onGone(removed)
        if (follow) Playback.onMain { Playback.follow(owner) }
    }

    /**
     * Điện thoại làm MÁY GIỮ SÁCH: máy kia (máy tính hay điện thoại khác) gửi hồ sơ của nó, gộp vào đúng hồ sơ ấy chứ không phải
     * hồ sơ đang dùng ở đây (webui/listening.py merge_record; bộ ví dụ dùng chung tests/fixtures/sync/records_host.json): hồ sơ lạ
     * được nhận cùng mã, tên đổi sau thắng (`nameAt`), hồ sơ đang chọn bên chọn sau thắng (`activeAt`), hồ sơ gắn ở cuốn nào
     * lần chuyển sau thắng (`movedAt`), bia mộ gửi tới xoá theo, hồ sơ đã xoá ở đây thì không sống lại (`deleted: true`).
     * Lời đáp mang `record`, `book`, `movedAt`, danh sách hồ sơ của cuốn, hồ sơ đang chọn (kèm `activeState` nếu khác hồ sơ
     * vừa gộp) và mọi bia mộ.
     */
    @Synchronized
    fun mergeRecord(bookId: String, body: JSONObject, onGone: (Set<String>) -> Unit = { Playback.recordsGone(it) }): JSONObject {
        val record = body.optString("record")
        require(RECORD_ID.matches(record)) { "Thiếu mã hồ sơ nghe" }
        val book = recordsBook()
        val records = book.getJSONObject("records")
        val links = book.getJSONObject("links")
        val tombstones = book.getJSONObject("deleted")
        val removed = mutableSetOf<String>()
        body.optJSONObject("deletedRecords")?.let { sent ->
            for (id in sent.keys()) {
                if (!RECORD_ID.matches(id)) continue
                if (records.has(id)) removed.add(id)
                forget(book, id)
                tombstones.put(id, maxOf(tombstones.optDouble(id, 0.0).takeIf { !it.isNaN() } ?: 0.0, sent.optDouble(id, 0.0)))
            }
        }
        if (tombstones.has(record)) {
            saveRecords(book)
            if (removed.isNotEmpty()) onGone(removed)
            return JSONObject().put("record", record).put("deleted", true).put("deletedRecords", JSONObject(tombstones.toString()))
        }
        val nameAt = body.optDouble("nameAt", 0.0).takeIf { !it.isNaN() } ?: 0.0
        val sentName = body.optString("recordName").trim().take(60)
        val meta = records.optJSONObject(record) ?: JSONObject().put("name", sentName.ifBlank { DEFAULT_RECORD_NAME })
            .put("createdAt", now()).put("nameAt", nameAt).also { records.put(record, it) }
        if (sentName.isNotBlank() && nameAt > meta.optDouble("nameAt", 0.0)) meta.put("name", sentName).put("nameAt", nameAt)
        val movedAt = body.optDouble("movedAt", 0.0).takeIf { !it.isNaN() } ?: 0.0
        var owner = ownerOf(links, record)
        if (owner != null && owner != bookId && movedAt > meta.optDouble("movedAt", 0.0)) {
            unlink(links, owner, record)  // máy kia chuyển hồ sơ sang cuốn này sau lần chuyển ở đây: theo nó
            owner = null
        }
        if (owner == null) {
            owner = bookId
            val fresh = links.optJSONObject(bookId) ?: JSONObject().put("records", JSONArray()).put("activeAt", 0.0)
            addRecord(fresh, record)
            if (fresh.optString("active").isBlank() || !records.has(fresh.optString("active"))) fresh.put("active", record)
            links.put(bookId, fresh)
        }
        if (owner == bookId) meta.put("movedAt", maxOf(meta.optDouble("movedAt", 0.0), movedAt))
        val link = links.getJSONObject(owner)
        val activeAt = body.optDouble("activeAt", 0.0).takeIf { !it.isNaN() } ?: 0.0
        if (activeAt > 0.0 && activeAt > link.optDouble("activeAt", 0.0)) {
            link.put("active", record).put("activeAt", activeAt)
        }
        val merged = mergeStates(recordState(record), withoutSyncKeys(body))
        writeAtomic(recordFile(record), merged.toString())
        saveRecords(book)
        if (removed.isNotEmpty()) onGone(removed)
        val listed = JSONArray()
        val list = link.optJSONArray("records") ?: JSONArray()
        for (index in 0 until list.length()) {
            val id = list.optString(index)
            val item = records.optJSONObject(id) ?: continue
            listed.put(JSONObject().put("id", id).put("name", item.optString("name", DEFAULT_RECORD_NAME))
                .put("nameAt", item.optDouble("nameAt", 0.0)).put("movedAt", item.optDouble("movedAt", 0.0)))
        }
        val chosen = link.optString("active")
        val reply = JSONObject(merged.toString()).put("record", record)
            .put("recordName", meta.optString("name", DEFAULT_RECORD_NAME)).put("book", owner)
            .put("movedAt", meta.optDouble("movedAt", 0.0)).put("records", listed)
            .put("active", JSONObject().put("record", chosen).put("at", link.optDouble("activeAt", 0.0)))
            .put("deletedRecords", JSONObject(tombstones.toString()))
        if (chosen.isNotBlank() && chosen != record && records.has(chosen)) reply.put("activeState", recordState(chosen))
        return reply
    }

    private fun ownerOf(links: JSONObject, record: String): String? = links.keys().asSequence().firstOrNull { bookId ->
        val list = links.optJSONObject(bookId)?.optJSONArray("records") ?: return@firstOrNull false
        (0 until list.length()).any { list.optString(it) == record }
    }

    /** Lúc chuyển của một hồ sơ theo máy tính (danh sách `records` trong lời đáp); không có thì 0. */
    private fun remoteMovedAt(known: JSONArray, record: String): Double =
        (0 until known.length()).mapNotNull { known.optJSONObject(it) }.firstOrNull { it.optString("id") == record }
            ?.optDouble("movedAt", 0.0) ?: 0.0

    private fun addRecord(link: JSONObject, record: String) {
        val list = link.optJSONArray("records") ?: JSONArray()
        if ((0 until list.length()).none { list.optString(it) == record }) list.put(record)
        link.put("records", list)
    }

    private fun unlink(links: JSONObject, bookId: String, record: String) {
        val link = links.optJSONObject(bookId) ?: return
        val list = link.optJSONArray("records") ?: JSONArray()
        val kept = JSONArray()
        for (index in 0 until list.length()) if (list.optString(index) != record) kept.put(list.optString(index))
        link.put("records", kept)
        if (link.optString("active") == record) link.put("active", if (kept.length() > 0) kept.optString(kept.length() - 1) else "")
    }

    /** Bỏ hẳn một hồ sơ: gỡ khỏi mọi liên kết, xoá trạng thái. (Bia mộ do nơi gọi ghi.) */
    private fun forget(book: JSONObject, record: String) {
        val links = book.getJSONObject("links")
        for (bookId in links.keys().asSequence().toList()) unlink(links, bookId, record)
        book.getJSONObject("records").remove(record)
        recordFile(record).delete()
    }

    // ---- hồ sơ nghe: lệnh cho giao diện (cùng hình dạng API máy tính: webui/server.py records) --------------------

    /** Các hồ sơ gắn với cuốn: mã, tên, lúc tạo, lúc nghe gần nhất, có đang dùng không. */
    @Synchronized
    fun records(bookId: String): JSONArray {
        val book = recordsBook()
        val records = book.getJSONObject("records")
        val link = book.getJSONObject("links").optJSONObject(bookId) ?: return JSONArray()
        val list = link.optJSONArray("records") ?: JSONArray()
        val out = JSONArray()
        for (index in 0 until list.length()) {
            val id = list.optString(index)
            val meta = records.optJSONObject(id) ?: continue
            val state = readJson(recordFile(id))
            out.put(JSONObject().put("id", id).put("name", meta.optString("name", DEFAULT_RECORD_NAME))
                .put("createdAt", meta.optDouble("createdAt", 0.0))
                .put("updatedAt", state?.optDouble("updatedAt", 0.0) ?: JSONObject.NULL)
                .put("active", id == link.optString("active")))
        }
        return out
    }

    /** Hồ sơ mới cho cuốn (nghe từ đầu), thành hồ sơ đang dùng; hồ sơ cũ giữ nguyên. */
    @Synchronized
    fun createRecord(bookId: String, name: String): JSONArray {
        val book = recordsBook()
        val links = book.getJSONObject("links")
        val link = links.optJSONObject(bookId) ?: JSONObject().put("records", JSONArray())
        val record = newRecordId()
        val label = name.trim().take(60).ifBlank { "Hồ sơ ${(link.optJSONArray("records")?.length() ?: 0) + 1}" }
        book.getJSONObject("records").put(record, JSONObject().put("name", label).put("createdAt", now()).put("nameAt", now()))
        addRecord(link, record)
        links.put(bookId, link.put("active", record).put("activeAt", now()))
        saveRecords(book)
        return records(bookId)
    }

    @Synchronized
    fun activateRecord(bookId: String, record: String): JSONArray {
        val book = recordsBook()
        val link = book.getJSONObject("links").optJSONObject(bookId)
        val list = link?.optJSONArray("records") ?: JSONArray()
        require((0 until list.length()).any { list.optString(it) == record }) { "Không có hồ sơ nghe này" }
        link!!.put("active", record).put("activeAt", now())
        saveRecords(book)
        return records(bookId)
    }

    @Synchronized
    fun renameRecord(bookId: String, record: String, name: String): JSONArray {
        val book = recordsBook()
        val meta = book.getJSONObject("records").optJSONObject(record) ?: throw IllegalArgumentException("Không có hồ sơ nghe này")
        require(name.isNotBlank()) { "Tên hồ sơ không được để trống" }
        meta.put("name", name.trim().take(60)).put("nameAt", now())
        saveRecords(book)
        return records(bookId)
    }

    /** Xoá hồ sơ (và trạng thái của nó); bia mộ đồng bộ sang máy tính để hồ sơ không sống lại. */
    @Synchronized
    fun deleteRecord(bookId: String, record: String): JSONArray {
        val book = recordsBook()
        require(book.getJSONObject("records").has(record)) { "Không có hồ sơ nghe này" }
        forget(book, record)
        book.getJSONObject("deleted").put(record, now())
        saveRecords(book)
        return records(bookId)
    }

    /** Gắn hồ sơ của cuốn `bookId` sang cuốn `toBook` (vd. bản làm lại của cùng truyện), thành hồ sơ đang dùng ở đó - chỗ
     *  nghe, dấu trang đi theo (như webui/listening.py move_record). Trả các hồ sơ còn lại của `bookId`. */
    @Synchronized
    fun moveRecord(bookId: String, record: String, toBook: String): JSONArray {
        val book = recordsBook()
        val links = book.getJSONObject("links")
        val list = links.optJSONObject(bookId)?.optJSONArray("records") ?: JSONArray()
        require(book.getJSONObject("records").has(record) && (0 until list.length()).any { list.optString(it) == record }) {
            "Không có hồ sơ nghe này"
        }
        require(toBook.isNotEmpty() && toBook != bookId) { "Chọn một cuốn khác" }
        unlink(links, bookId, record)
        val link = links.optJSONObject(toBook) ?: JSONObject().put("records", JSONArray()).put("activeAt", 0.0)
        addRecord(link, record)
        // Lúc chuyển: đồng bộ với máy tính theo "lần chuyển sau thắng" (applySync, merge_record).
        val at = now()
        book.getJSONObject("records").getJSONObject(record).put("movedAt", at)
        links.put(toBook, link.put("active", record).put("activeAt", at))
        saveRecords(book)
        return records(bookId)
    }

    /** Liên kết hồ sơ của cuốn mở từ file sang mã máy tính khi hai bên nhận ra là một cuốn (adopt). */
    private fun moveLinks(from: String, to: String) {
        val book = JSONObject(recordsBook().toString())
        val links = book.getJSONObject("links")
        val moved = links.optJSONObject(from) ?: return
        links.remove(from)
        val existing = links.optJSONObject(to)
        if (existing == null) {
            links.put(to, moved)
        } else {
            val list = moved.optJSONArray("records") ?: JSONArray()
            for (index in 0 until list.length()) addRecord(existing, list.optString(index))
        }
        saveRecords(book)
    }

    // ---- trạng thái nghe của hồ sơ đang dùng -----------------------------------------------------------------

    /** Hồ sơ đang dùng của sách nếu đã có - chỉ ĐỌC thì không tạo hồ sơ (xem thư viện không đẻ ra hồ sơ rỗng). */
    @Synchronized
    fun knownActiveRecord(bookId: String): String? {
        val book = recordsBook()
        val active = book.getJSONObject("links").optJSONObject(bookId)?.optString("active").orEmpty()
        return active.takeIf { it.isNotBlank() && book.getJSONObject("records").has(it) }
    }

    @Synchronized
    fun hasRecord(record: String): Boolean = recordsBook().getJSONObject("records").has(record)

    /** Hồ sơ này đã có trạng thái nghe ở máy chưa (hồ sơ máy giữ sách báo trong danh sách mà chưa được tải về thì chưa). */
    @Synchronized
    fun hasState(record: String): Boolean = recordFile(record).isFile

    /** Hồ sơ [record] còn gắn với cuốn [bookId] (không đọc file trạng thái nào). */
    private fun ownsRecord(bookId: String, record: String): Boolean {
        val book = recordsBook()
        val list = book.getJSONObject("links").optJSONObject(bookId)?.optJSONArray("records") ?: return false
        return book.getJSONObject("records").has(record) && (0 until list.length()).any { list.optString(it) == record }
    }

    @Synchronized
    fun state(id: String): JSONObject = knownActiveRecord(id)?.let(::recordState) ?: recordState(null)

    private fun recordState(record: String?): JSONObject {
        val file = record?.let(::recordFile)
        val state = file?.let(::readJson) ?: JSONObject()
        if (!state.has("chapters")) state.put("chapters", JSONObject())
        if (!state.has("bookmarks")) state.put("bookmarks", JSONArray())
        return state
    }

    @Synchronized
    private fun save(id: String, state: JSONObject) = writeAtomic(stateFile(id), state.toString())

    /**
     * Máy khác đang nghe một cuốn CỦA điện thoại (LibraryServer, POST .../state) gửi chỗ nghe của nó: gộp vào hồ sơ đang
     * dùng của cuốn ấy đúng như máy tính gộp khi điện thoại gửi lên (webui/listening.py `merge` + `merge_states`) và trả
     * bản đã gộp - bên gửi (remote_books.exchange_state) không cần biết đầu kia là điện thoại.
     */
    @Synchronized
    fun mergeRemote(id: String, incoming: JSONObject): JSONObject {
        val merged = mergeStates(state(id), withoutSyncKeys(incoming))
        save(id, merged)
        return JSONObject(merged.toString())
    }

    private const val MAX_SESSIONS = 200
    /** Cùng chương, cách nhau tối đa 5 giây là cùng chỗ (listening.py). */
    private const val BOOKMARK_SAME_SECONDS = 5.0

    private fun stamp(value: JSONObject?, key: String = "at") = value?.optDouble(key, 0.0)?.takeIf { !it.isNaN() } ?: 0.0

    /** `merge_states` của máy tính: mỗi phần mang mốc thời gian riêng, bên mới hơn thắng; dấu trang hợp theo id, dấu trang
     *  đã xoá ở một bên (bia mộ "deleted") thì xoá ở cả hai; phiên nghe hợp theo id, giữ 200 phiên cuối; đêm nghe theo
     *  `merge_nights`. */
    fun mergeStates(ours: JSONObject, theirs: JSONObject): JSONObject {
        val result = JSONObject(ours.toString())
        if (result.optJSONObject("chapters") == null) result.put("chapters", JSONObject())
        if (result.optJSONArray("bookmarks") == null) result.put("bookmarks", JSONArray())
        for (key in listOf("last", "reading")) {
            if (stamp(theirs.optJSONObject(key)) > stamp(result.optJSONObject(key))) result.put(key, theirs.get(key))
        }
        val chapters = result.getJSONObject("chapters")
        theirs.optJSONObject("chapters")?.let { incoming ->
            for (key in incoming.keys()) {
                val record = incoming.optJSONObject(key) ?: continue
                if (stamp(record) > stamp(chapters.optJSONObject(key)) || chapters.optJSONObject(key) == null) chapters.put(key, record)
            }
        }
        for ((field, at) in listOf("rate" to "rateAt", "finished" to "finishedAt", "voice" to "voiceAt")) {
            if (theirs.has(field) && stamp(theirs, at) > stamp(result, at)) {
                result.put(field, theirs.get(field)).put(at, theirs.get(at))
            }
        }
        // Bookmarks: newer edit wins (a tie keeps ours); a tombstone only removes a mark not changed after it - an undone delete
        // (newer `at`) comes back on both devices. Both sides deleted: keep the later stamp.
        val deleted = JSONObject((result.optJSONObject("deleted") ?: JSONObject()).toString())
        theirs.optJSONObject("deleted")?.let { gone ->
            for (key in gone.keys()) deleted.put(key, maxOf(gone.optDouble(key, 0.0).takeIf { !it.isNaN() } ?: 0.0, stamp(deleted, key)))
        }
        val marks = LinkedHashMap<String, JSONObject>()
        result.getJSONArray("bookmarks").let { list -> for (i in 0 until list.length()) list.optJSONObject(i)?.let { marks[it.optString("id")] = it } }
        (theirs.optJSONArray("bookmarks") ?: JSONArray()).let { list ->
            for (i in 0 until list.length()) {
                val mark = list.optJSONObject(i) ?: continue
                if (marks[mark.optString("id")] == null || stamp(mark) > stamp(marks[mark.optString("id")])) marks[mark.optString("id")] = mark
            }
        }
        result.put("bookmarks", JSONArray(marks.values.filter { stamp(it) > stamp(deleted, it.optString("id")) }
            .sortedBy { if (it.has("createdAt")) stamp(it, "createdAt") else stamp(it) }))
        result.put("deleted", deleted)
        val sessions = LinkedHashMap<String, JSONObject>()
        for (source in listOf(result, theirs)) {
            val list = source.optJSONArray("sessions") ?: continue
            for (i in 0 until list.length()) list.optJSONObject(i)?.takeIf { it.optString("id").isNotEmpty() }?.let { sessions[it.optString("id")] = it }
        }
        if (sessions.isNotEmpty()) result.put("sessions", JSONArray(sessions.values.sortedBy { stamp(it, "startedAt") }.takeLast(MAX_SESSIONS)))
        mergeNights(result.optJSONObject("night"), theirs.optJSONObject("night"))?.let { result.put("night", it) }
        result.put("updatedAt", maxOf(stamp(result, "updatedAt"), stamp(theirs, "updatedAt")))
        return result
    }

    /** `merge_nights`: đêm mới hơn thắng; cùng một đêm thì bản ghi dài hơn thắng, "đã gạt đi" ở đâu cũng giữ. */
    private fun mergeNights(ours: JSONObject?, theirs: JSONObject?): JSONObject? {
        if (ours == null || theirs == null) return ours ?: theirs
        if (ours.optString("id") != theirs.optString("id")) {
            return if (stamp(ours, "startedAt") >= stamp(theirs, "startedAt")) ours else theirs
        }
        val longer = if ((ours.optJSONArray("events")?.length() ?: 0) >= (theirs.optJSONArray("events")?.length() ?: 0)) ours else theirs
        val result = JSONObject(longer.toString())
        result.put("dismissed", ours.optBoolean("dismissed") || theirs.optBoolean("dismissed"))
        result.put("endedAt", ours.opt("endedAt")?.takeIf { it != JSONObject.NULL } ?: theirs.opt("endedAt") ?: JSONObject.NULL)
        return result
    }

    private fun now() = System.currentTimeMillis() / 1000.0

    /** Chỗ đọc cùng hợp đồng anchor với chỗ nghe; flush của hồ sơ cũ vẫn về đúng hồ sơ ấy. */
    @Synchronized
    fun saveReading(id: String, chapterId: Int, index: Int, at: Double = now(), anchor: JSONObject? = null, record: String? = null): JSONObject {
        require(at.isFinite() && at >= 0) { "Thời điểm chỗ đọc không hợp lệ" }
        val target = record ?: activeRecord(id)
        require(records(id).let { rows -> (0 until rows.length()).any { rows.getJSONObject(it).optString("id") == target } }) { "Hồ sơ đọc không còn thuộc cuốn này" }
        val state = recordState(target)
        if ((state.optJSONObject("reading")?.optDouble("at", 0.0) ?: 0.0) >= at) return state
        val place = JSONObject().put("chapterId", chapterId).put("index", index.coerceAtLeast(0)).put("at", at)
        vn.abook.player.readaloud.ReadingAnchor.validated(anchor)?.let { place.put("anchor", it) }
        state.put("reading", place).put("updatedAt", maxOf(state.optDouble("updatedAt", 0.0), at))
        writeAtomic(recordFile(target), state.toString())
        return state
    }

    /**
     * Ghi chỗ nghe. [recordId]: hồ sơ phiên phát đã chốt lúc bắt đầu (loa / TV - [DlnaPlayers]) - lần lưu vẫn vào hồ sơ ấy dù người nghe
     * vừa đổi hồ sơ đang dùng; hồ sơ không còn thuộc cuốn này (xoá, chuyển sách) thì bỏ lần lưu. null: hồ sơ đang dùng.
     */
    @Synchronized
    fun progress(id: String, chapterId: Int, seconds: Double, duration: Double, anchor: JSONObject? = null, recordId: String? = null): JSONObject {
        val target = if (recordId == null) activeRecord(id) else recordId.takeIf { ownsRecord(id, it) } ?: return state(id)
        val state = recordState(target)
        val at = now()
        state.put("last", JSONObject().put("chapterId", chapterId).put("seconds", seconds).put("at", at))
        vn.abook.player.readaloud.ReadingAnchor.validated(anchor)?.let { state.getJSONObject("last").put("anchor", it) }
        val chapters = state.getJSONObject("chapters")
        val record = chapters.optJSONObject(chapterId.toString()) ?: JSONObject().put("heard", 0.0).put("done", false)
        record.put("heard", maxOf(record.optDouble("heard", 0.0), seconds))
        if (duration > 0 && duration - seconds <= DONE_TAIL_SECONDS) record.put("done", true)
        if (duration > 0) record.put("duration", duration)
        record.put("at", at)
        chapters.put(chapterId.toString(), record)
        state.put("updatedAt", at)
        writeAtomic(recordFile(target), state.toString())
        return state
    }

    /** Lời báo khi một việc ghi mang hồ sơ đã xoá / chuyển sang sách khác (cùng câu với 409 của máy tính, webui/listening.py `RecordGone`). */
    const val RECORD_GONE = "Hồ sơ nghe này đã bị xoá hoặc chuyển sang cuốn khác. Bạn hãy nạp lại sách."

    /** Hồ sơ cho một việc ghi của người nghe: [recordId] là hồ sơ màn đang hiện đã chốt lúc bắt đầu (không nói: hồ sơ đang dùng);
     *  đã xoá / chuyển sách thì ném [IllegalStateException] - không ghi sang hồ sơ khác (đúng `Listening._named`). */
    private fun named(id: String, recordId: String?): String =
        target(id, recordId) ?: throw IllegalStateException(RECORD_GONE)

    @Synchronized
    fun setChapterDone(id: String, chapterId: Int, done: Boolean, recordId: String? = null): JSONObject {
        val target = named(id, recordId)
        val state = recordState(target)
        val chapters = state.getJSONObject("chapters")
        val record = chapters.optJSONObject(chapterId.toString()) ?: JSONObject().put("heard", 0.0)
        record.put("done", done)
        if (!done) record.put("heard", 0.0)
        record.put("at", now())
        chapters.put(chapterId.toString(), record)
        state.put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
        return state
    }

    @Synchronized
    fun setFinished(id: String, finished: Boolean, recordId: String? = null): JSONObject {
        val target = named(id, recordId)
        val state = recordState(target)
        state.put("finished", finished).put("finishedAt", now()).put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
        return state
    }

    /** Hồ sơ để ghi: [recordId] là hồ sơ nơi gọi đã chốt lúc bắt đầu việc (phiên phát, yêu cầu gửi đi) - còn thuộc cuốn thì ghi vào đúng
     *  nó, đã xoá hay sang cuốn khác thì null (bỏ lần ghi, không rơi sang hồ sơ khác); không nói thì hồ sơ đang dùng. */
    private fun target(id: String, recordId: String?): String? =
        if (recordId == null) activeRecord(id) else recordId.takeIf { ownsRecord(id, it) }

    /** Hồ sơ [record] còn thuộc cuốn [id] (phiên phát đang giữ nó có còn ghi được không). */
    @Synchronized
    fun holds(id: String, record: String): Boolean = ownsRecord(id, record)

    @Synchronized
    fun setRate(id: String, rate: Double, recordId: String? = null) {
        val target = target(id, recordId) ?: return
        val state = recordState(target)
        state.put("rate", rate).put("rateAt", now()).put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
    }

    /** Giọng Nghe ngay riêng của cuốn (rỗng = giọng mặc định) - mang mốc giờ như tốc độ, đi theo hồ sơ nghe sang máy kia (webui/listening.py set_voice). */
    @Synchronized
    fun setVoice(id: String, voice: String, recordId: String? = null) {
        val target = target(id, recordId) ?: return
        val state = recordState(target)
        state.put("voice", voice.take(200)).put("voiceAt", now()).put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
    }

    /** Một phiên nghe (cùng hình dạng với máy tính: webui/listening.py add_session), giữ 200 phiên gần nhất. */
    @Synchronized
    fun addSession(id: String, session: JSONObject, recordId: String? = null) {
        val target = target(id, recordId) ?: return
        val state = recordState(target)
        val sessions = state.optJSONArray("sessions") ?: JSONArray()
        val kept = JSONArray()
        val start = maxOf(0, sessions.length() - 199)
        for (index in start until sessions.length()) kept.put(sessions.getJSONObject(index))
        kept.put(session)
        state.put("sessions", kept).put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
    }

    /** `listening.bookmark_quote`: đầu câu cho dòng dấu trang - gộp khoảng trắng, cắt ở ranh giới từ quanh 60 ký tự, thêm "…" khi có cắt. */
    fun bookmarkQuote(text: String): String {
        val clean = text.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        if (clean.length <= 60) return clean
        val cut = clean.take(60)
        val space = cut.lastIndexOf(' ')
        return (if (space > 30) cut.substring(0, space) else cut).trimEnd(' ', ',', '.', ';', ':', '!', '?', '…', '-', '—') + "…"
    }

    /** `index` + `quote`: dấu đặt ở màn đọc trỏ tới CÂU (thứ tự câu trong chương, như `?at=`) và giữ ~60 chữ đầu câu - cùng trường với
     *  máy tính (listening.py `add_bookmark`); dấu đặt từ trình phát chỉ có hai trường này khi đang đọc to chương chữ. */
    @Synchronized
    fun addBookmark(id: String, chapterId: Int, seconds: Double, note: String, index: Int? = null, quote: String = "", createdAt: Double? = null,
                    recordId: String? = null, anchor: JSONObject? = null): JSONObject {
        val target = named(id, recordId)
        val state = recordState(target)
        val marks = state.getJSONArray("bookmarks")
        val cleanNote = note.trim().take(500)
        // Same place twice (a double tap, or the same sentence): one bookmark, flagged `existing` like the computer's add_bookmark.
        for (i in 0 until marks.length()) {
            val current = marks.optJSONObject(i) ?: continue
            if (current.optInt("chapterId", -1) != chapterId) continue
            val same = if (index != null && index >= 0) current.has("index") && current.optInt("index") == index
                else Math.abs(current.optDouble("seconds", 0.0) - seconds) <= BOOKMARK_SAME_SECONDS
            if (same) {
                if (cleanNote.isNotEmpty() && current.optString("note").isEmpty()) {
                    val at = now()
                    if (!current.has("createdAt")) current.put("createdAt", current.optDouble("at", at))
                    current.put("note", cleanNote).put("at", at)
                    state.put("updatedAt", at)
                    writeAtomic(recordFile(target), state.toString())
                }
                return JSONObject(current.toString()).put("existing", true)
            }
        }
        val at = now()
        // `at` = last change (what a merge compares); `createdAt` = when it was set (what the list shows) - an undo keeps the original.
        val mark = JSONObject()
            .put("id", UUID.randomUUID().toString().replace("-", "").substring(0, 12))
            .put("chapterId", chapterId).put("seconds", seconds).put("note", cleanNote).put("at", at)
            .put("createdAt", createdAt?.takeIf { it > 0 && it <= at } ?: at)
        if (index != null && index >= 0) mark.put("index", index).put("quote", bookmarkQuote(quote))
        vn.abook.player.readaloud.ReadingAnchor.validated(anchor)?.let { mark.put("anchor", it) }
        marks.put(mark)
        state.put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
        return mark
    }

    @Synchronized
    fun updateBookmark(id: String, markId: String, note: String, recordId: String? = null) {
        val target = named(id, recordId)
        val state = recordState(target)
        val marks = state.getJSONArray("bookmarks")
        for (index in 0 until marks.length()) {
            val mark = marks.getJSONObject(index)
            if (mark.optString("id") != markId) continue
            if (!mark.has("createdAt")) mark.put("createdAt", mark.optDouble("at", now()))
            mark.put("note", note.take(500)).put("at", now())
        }
        state.put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
    }

    @Synchronized
    fun deleteBookmark(id: String, markId: String, recordId: String? = null) {
        val target = named(id, recordId)
        val state = recordState(target)
        val marks = state.getJSONArray("bookmarks")
        val kept = JSONArray()
        for (index in 0 until marks.length()) {
            val mark = marks.getJSONObject(index)
            if (mark.optString("id") != markId) kept.put(mark)
        }
        state.put("bookmarks", kept)
        val deleted = state.optJSONObject("deleted") ?: JSONObject()
        deleted.put(markId, now())
        state.put("deleted", deleted).put("updatedAt", now())
        writeAtomic(recordFile(target), state.toString())
    }

    /** Hoàn tác đúng dấu cũ như listening.restore_bookmark: giữ ID/lúc đặt, đổi mốc sửa và gỡ bia mộ ở đây. */
    @Synchronized
    fun restoreBookmark(id: String, mark: JSONObject): JSONObject {
        val state = state(id)
        val at = now()
        val created = stamp(mark, "createdAt").takeIf { it > 0 } ?: stamp(mark)
        val restored = JSONObject().put("id", mark.getString("id").take(40))
            .put("chapterId", mark.getInt("chapterId")).put("seconds", mark.getDouble("seconds"))
            .put("note", mark.optString("note").take(500)).put("at", at)
            .put("createdAt", created.takeIf { it > 0 && it <= at } ?: at)
        val index = mark.opt("index")
        if (index is Int && index >= 0) restored.put("index", index).put("quote", bookmarkQuote(mark.optString("quote")))
        vn.abook.player.readaloud.ReadingAnchor.validated(mark.optJSONObject("anchor"))?.let { restored.put("anchor", it) }
        val marks = state.getJSONArray("bookmarks")
        val kept = JSONArray()
        for (i in 0 until marks.length()) {
            val current = marks.getJSONObject(i)
            if (current.optString("id") != restored.getString("id")) kept.put(current)
        }
        state.put("bookmarks", kept.put(restored)).put("updatedAt", at)
        state.optJSONObject("deleted")?.remove(restored.getString("id"))
        save(id, state)
        return restored
    }

    /** Mã sách hợp lệ để XOÁ: không rỗng, chỉ [A-Za-z0-9_-], và thư mục của nó nằm ngay trong books/. Mã rỗng là CẢ thư
     *  mục books/ (bookDir("") = root/books) - xoá theo mã ấy là mất mọi sách đã tải; "../x" ra ngoài thư viện. */
    fun deletableBookDir(id: String): File {
        require(id.isNotEmpty() && id.all { it.isLetterOrDigit() && it.code < 128 || it == '_' || it == '-' }) {
            "mã sách không hợp lệ"
        }
        val dir = bookDir(id).canonicalFile
        require(dir.parentFile == File(root, "books").canonicalFile) { "thư mục sách nằm ngoài thư viện" }
        return dir
    }

    /** Xoá HẲN ngay (không hoàn tác): thư mục sách + dòng của nó trong sổ `prints.json`. Giao diện đi qua [holdBook]. */
    @Synchronized
    fun deleteBook(id: String) {
        deletableBookDir(id).deleteRecursively()
        forgetPrints(id)
    }

    private fun forgetPrints(id: String) {
        val all = printsBook()
        if (all.has(id)) {
            all.remove(id)
            writeAtomic(printsFile, all.toString())
        }
    }

    /**
     * "Xoá khỏi điện thoại" có "Hoàn tác" ([TrashPending]): đưa thư mục sách vào chỗ chờ, trả mã hoàn tác. Thư mục không đổi tên
     * được (hiếm: cùng filesDir) thì xoá hẳn như trước và trả null - giao diện khi ấy không hứa "Hoàn tác". Dữ liệu đi theo sách
     * (`prints.json`) giữ nguyên tới lúc xoá hẳn để Hoàn tác trả đủ.
     */
    @Synchronized
    fun holdBook(id: String): String? {
        val dir = deletableBookDir(id)
        if (dir.isDirectory) trash().hold(dir, id)?.let { return it }
        deleteBook(id)
        return null
    }

    /** Hoàn tác một lần xoá: cuốn về đúng chỗ cũ. [TrashPending.NotPending] khi mã lạ / quá hạn, [TrashPending.Occupied] khi chỗ cũ bị chiếm. */
    @Synchronized
    fun undoBook(token: String): JSONObject = trash().restore(token)

    /** Xoá hẳn những cuốn đã hết hạn Hoàn tác (`everything`: mọi cuốn đang chờ - lúc app mở). Trả số cuốn còn chờ. */
    @Synchronized
    fun sweepTrash(everything: Boolean = false): Int = trash().sweep(everything) { meta ->
        val id = meta.optString("id")
        // Cuốn cùng mã vừa được tải lại thì sổ ấy là của cuốn mới.
        if (id.isNotEmpty() && !bookDir(id).exists()) forgetPrints(id)
    }

    private fun trash() = TrashPending(root)

    // ---- một cuốn, hai đường đến -----------------------------------------------------------------------------
    //
    // Sách không mang mã nào (chủ sách 27-09: sách và dữ liệu nghe không biết đến mã; mã chỉ là thứ app dùng để liên
    // kết). App nhận ra cùng một lần sản xuất bằng audio từng chương: chung một chương giống hệt từng byte (tên, cỡ, mã
    // băm) là cùng một cuốn. Sổ của app `prints.json` - nằm NGOÀI thư mục sách - ghi cỡ + mã băm các chương đã biết của
    // từng cuốn, và cuốn nào mở từ file mà chưa gắn với cuốn nào của máy tính.

    private val printsFile get() = File(root, "prints.json")

    private fun printsBook(): JSONObject =
        readJson(printsFile) ?: JSONObject()

    @Synchronized
    fun rememberChapters(id: String, chapters: JSONObject, imported: Boolean) {
        val all = printsBook()
        val entry = all.optJSONObject(id) ?: JSONObject()
        val known = entry.optJSONObject("chapters") ?: JSONObject()
        for (name in chapters.keys()) {
            // Mã băm của lượt nhập đã được kiểm với byte vừa giải ra: kèm dấu mtime để lần kiểm sau (AudioRevision.matches) khỏi băm lại.
            val print = JSONObject(chapters.getJSONObject(name).toString())
            val file = runCatching { file(id, name) }.getOrNull()
            if (file != null && file.isFile && file.length() == print.optLong("size", -1) && print.optString("sha256").isNotEmpty()) print.put("modified", file.lastModified())
            known.put(name, print)
        }
        all.put(id, entry.put("chapters", known).put("imported", imported))
        writeAtomic(printsFile, all.toString())
    }

    // ---- băm audio có nhớ ------------------------------------------------------------------------------------
    //
    // Mỗi chương trong sổ `prints.json` mang {size, modified, sha256}: cỡ + mtime khớp file thì mã băm còn đúng, không đọc lại cả file
    // (sách 100 chương x vài chục MB mà băm lại mỗi lần máy tính hỏi thư viện hay mở trang thiết bị là hàng GB). Thiếu bản ghi, hay
    // cỡ/mtime đổi thì băm lại rồi ghi. File mới ghi trong vài giây vừa qua chưa được tin (hai lần ghi cùng cỡ có thể trùng mtime thô);
    // lượt tải thì khác: đã băm chính byte vừa tải, ghi thẳng bằng [rememberDigest].

    private const val SETTLE_MS = 2000L

    /** (mã sách, đường dẫn trong sách) nếu `file` là file của một cuốn trong thư viện (không kể `.part` đang tải); ngoài ra null. */
    private fun located(file: File): Pair<String, String>? {
        if (!::root.isInitialized || file.name.endsWith(".part")) return null
        val books = File(root, "books").canonicalFile
        val path = file.canonicalFile
        if (!path.path.startsWith(books.path.trimEnd(File.separatorChar) + File.separator)) return null
        val parts = path.relativeTo(books).invariantSeparatorsPath.split('/')
        val id = parts.first()
        if (parts.size < 2 || id.startsWith(".") || runCatching { requireBookId(id) }.isFailure) return null
        return id to parts.drop(1).joinToString("/")
    }

    fun audioSha256(file: File): String = audioSha256s(listOf(file)).single()

    /** Mã băm của từng file, theo thứ tự `files`; file đã nhớ (cỡ + mtime khớp) không bị đọc lại. Ghi bản ghi mới MỘT lần cho mỗi cuốn. */
    fun audioSha256s(files: List<File>): List<String> {
        val result = arrayOfNulls<String>(files.size)
        val fresh = HashMap<String, MutableMap<String, JSONObject>>()
        val prints = HashMap<String, JSONObject>()
        for ((index, file) in files.withIndex()) {
            val place = located(file)
            val recorded = place?.let { (id, relative) -> prints.getOrPut(id) { chapterPrints(id) }.optJSONObject(relative) }
            if (recorded != null && recorded.optString("sha256").isNotEmpty() && recorded.optLong("size", -1) == file.length() &&
                recorded.optLong("modified", -1) == file.lastModified()) {
                result[index] = recorded.getString("sha256")
                continue
            }
            val size = file.length()
            val modified = file.lastModified()
            val sha256 = AudioRevision.sha256(file)
            result[index] = sha256
            if (place != null && file.length() == size && file.lastModified() == modified && System.currentTimeMillis() - modified > SETTLE_MS) {
                fresh.getOrPut(place.first) { LinkedHashMap() }[place.second] = JSONObject().put("size", size).put("modified", modified).put("sha256", sha256)
            }
        }
        for ((id, records) in fresh) recordDigests(id, records)
        return result.map { it!! }
    }

    /** Ghi mã băm của `relative` (file `target` vừa đổi tên vào chỗ) - gọi sau khi đã băm đúng byte của file ấy. */
    fun rememberDigest(id: String, relative: String, target: File, sha256: String) =
        recordDigests(id, mapOf(relative to JSONObject().put("size", target.length()).put("modified", target.lastModified()).put("sha256", sha256)))

    @Synchronized
    private fun recordDigests(id: String, records: Map<String, JSONObject>) {
        if (records.isEmpty() || !runCatching { bookDir(id).isDirectory }.getOrDefault(false)) return // cuốn vừa xoá: không dựng lại dòng sổ
        val all = printsBook()
        val entry = all.optJSONObject(id) ?: JSONObject()
        val known = entry.optJSONObject("chapters") ?: JSONObject()
        for ((name, print) in records) known.put(name, print)
        all.put(id, entry.put("chapters", known))
        writeAtomic(printsFile, all.toString())
    }

    /** Cuốn `id` do file nguồn có mã băm `sha256` thêm vào (`TextImports`): lần xem trước sau nhận ra cùng một file, chọn chương nào cũng vậy. */
    @Synchronized
    fun rememberSource(id: String, sha256: String) {
        val all = printsBook()
        all.put(id, (all.optJSONObject(id) ?: JSONObject()).put("source", sha256))
        writeAtomic(printsFile, all.toString())
    }

    /** Cuốn còn trên máy được thêm từ file có mã băm `sha256`, không có thì null. */
    @Synchronized
    fun findBySource(sha256: String): String? {
        val all = printsBook()
        return all.keys().asSequence().firstOrNull { all.optJSONObject(it)?.optString("source") == sha256 && rawManifest(it) != null }
    }

    @Synchronized
    fun isImported(id: String) = printsBook().optJSONObject(id)?.optBoolean("imported") == true

    /** Cuốn mở từ file còn trên máy mà chưa gắn với cuốn nào của máy tính. */
    @Synchronized
    fun importedBooks(): List<String> {
        val all = printsBook()
        return all.keys().asSequence().filter { all.getJSONObject(it).optBoolean("imported") && rawManifest(it) != null }.toList()
    }

    /** Cỡ + mã băm các chương của một cuốn, như đã ghi trong sổ. */
    @Synchronized
    fun chapterPrints(id: String): JSONObject = printsBook().optJSONObject(id)?.optJSONObject("chapters") ?: JSONObject()

    /**
     * Cuốn đã có trên máy (tải qua Wi-Fi hay mở từ file) có chung ít nhất một chương audio với `chapters`
     * ({"chapters/x.mp3": {size, sha256}}). So theo TÊN FILE, không kể thư mục: file cả bộ đặt audio ở
     * `chapters/<phần>/x.mp3` còn cuốn tải qua Wi-Fi giữ `chapters/x.mp3`. Chỉ băm file trùng tên và cỡ (audioSha256: ghi vào sổ để
     * lần sau khỏi băm).
     *
     * Cuốn chưa có audio nào thì `chapters` là mã băm CHỮ từng chương ({"texts/1.txt": ...}): hai cuốn khác nhau có thể chung một
     * chương ngắn ("Lời nói đầu"), nên phải trùng cả bộ chữ - mọi chương của file có mặt, và cuốn trên máy không có chương chữ nào
     * thừa (`packages.import_opened` bên Python đòi tập chữ bằng nhau).
     */
    @Synchronized
    fun findByChapters(chapters: JSONObject): String? {
        val names = chapters.keys().asSequence().toList()
        val wholeBook = names.isNotEmpty() && names.all { it.startsWith("texts/") }
        for (book in books()) {
            val id = book.optString("id")
            if (id.isBlank()) continue
            val own = chapterFiles(book)
            val shares = { name: String -> sharesChapter(id, own, name, chapters.getJSONObject(name)) }
            if (wholeBook) {
                if (textChapterCount(book) == names.size && names.all(shares)) return id
            } else if (names.any(shares)) {
                return id
            }
        }
        return null
    }

    /** Cuốn `id` có đúng file của chương `name` (cỡ + mã băm như `wanted`) ở một trong các đường dẫn nó dùng? */
    private fun sharesChapter(id: String, own: List<String>, name: String, wanted: JSONObject): Boolean {
        val base = name.substringAfterLast('/')
        for (candidate in (own.filter { it.substringAfterLast('/') == base } + name).distinct()) {
            val local = runCatching { file(id, candidate) }.getOrNull() ?: continue
            if (!local.isFile || local.length() != wanted.optLong("size", -1)) continue
            if (audioSha256(local) == wanted.optString("sha256")) return true
        }
        return false
    }

    /** Số chương của cuốn mang chữ riêng (`texts/<n>.txt`). */
    private fun textChapterCount(book: JSONObject): Int {
        val array = book.optJSONArray("chapters") ?: return 0
        return (0 until array.length()).count { array.optJSONObject(it)?.optString("text").orEmpty().startsWith("texts/") }
    }

    /** Đường dẫn audio các chương như `book.json` của cuốn ghi (`chapters/x.mp3`, hay `chapters/<phần>/x.mp3` ở file cả bộ). */
    private fun chapterFiles(book: JSONObject): List<String> {
        val array = book.optJSONArray("chapters") ?: return emptyList()
        return (0 until array.length()).mapNotNull { array.optJSONObject(it)?.optString("file")?.takeIf { file -> file.startsWith("chapters/") } }
    }

    /**
     * Cuốn mở từ file mà máy tính cho biết là cuốn `syncId` của nó (cùng audio): MỘT cuốn - thư mục đổi sang mã máy tính
     * để chỗ nghe, dấu trang tiếp tục đồng bộ, audio đã có không phải tải lại. Hồ sơ nghe của cuốn đi theo liên kết (hồ sơ
     * không biết gì về sách, chỉ bảng liên kết đổi); hai bản đã cùng tải về thì để nguyên - không xoá gì của người nghe.
     */
    @Synchronized
    fun adopt(localId: String, syncId: String) {
        recoverRekeys()
        if (localId == syncId || !isImported(localId) || rawManifest(localId) == null || rawManifest(syncId) != null) return
        beginRekey(localId, syncId, adopt = true)
    }

    /** Cuốn của máy tính đã ghép chính - tải hẳn hay nghe thẳng; không kể cuốn mở từ file, cuốn của thiết bị ghép khác
     *  (gói mang `source`). */
    @Synchronized
    fun computerBooks(): List<String> {
        val prints = printsBook()
        return bookFolders().mapNotNull { dir ->
            val manifest = rawManifest(dir.name) ?: streamManifest(dir.name) ?: return@mapNotNull null
            dir.name.takeIf { isComputer(manifest, prints.optJSONObject(dir.name)) }
        }
    }

    /** Cuốn này lấy từ máy tính chính (không phải mở từ file, không phải của thiết bị ghép khác)? */
    @Synchronized
    fun isComputerBook(id: String): Boolean {
        val manifest = rawManifest(id) ?: streamManifest(id) ?: return false
        return isComputer(manifest, printsBook().optJSONObject(id))
    }

    /**
     * Cuốn nhập từ file (`.abook` / `.abookproj`) và chưa gắn với cuốn nào của máy tính - thứ duy nhất điện thoại chia sẻ cho máy đã ghép
     * (LibraryServer; máy tính làm y vậy với `Sách đã nhập/`, package_share.py). Cuốn tải từ máy tính hay từ thiết bị khác là bản soi của
     * sách bên kia: chia sẻ lại thì hai máy cứ soi nhau mãi.
     */
    @Synchronized
    fun isFileBook(id: String): Boolean {
        val raw = rawManifest(id) ?: return false
        return homeOf(raw, printsBook().optJSONObject(id)) == Home.FILE
    }

    private fun isComputer(manifest: JSONObject, print: JSONObject?) =
        manifest.optString("source").isEmpty() && print?.optBoolean("imported") != true

    /**
     * Máy tính đổi mã một cuốn (mã kiểu cũ - đường dẫn thư mục mã hoá - sang mã mới, docs/BOOK_IDS.md): thư
     * mục, gói sách, liên kết hồ sơ nghe và sổ dấu vân tay sang mã mới. Hồ sơ giữ nguyên mã (máy tính cũng giữ) nên vẫn
     * gộp được với nhau. Máy đã có bản tải hẳn mang mã mới: để nguyên cả hai - không xoá gì của người nghe.
     */
    @Synchronized
    fun rekey(oldId: String, newId: String) {
        recoverRekeys()
        if (oldId == newId) return
        val target = runCatching { deletableBookDir(newId) }.getOrNull() ?: return
        val source = runCatching { deletableBookDir(oldId) }.getOrNull() ?: return
        if (!source.isDirectory || rawManifest(newId) != null) return
        beginRekey(oldId, newId, adopt = false)
    }

    private val rekeyJournal get() = File(root, "rekey_journal.json")

    private fun beginRekey(oldId: String, newId: String, adopt: Boolean) {
        deletableBookDir(oldId)
        deletableBookDir(newId)
        val journal = readJson(rekeyJournal) ?: JSONObject()
        val action = JSONObject().put("to", newId).put("adopt", adopt)
        journal.put(oldId, action)
        writeAtomic(rekeyJournal, journal.toString())
        check(rekeyJournal.isFile) { "Không lưu được việc đổi mã sách của bạn" }
        // Lần đổi này báo lỗi cho nơi gọi (journal còn, lần mở sau làm tiếp); chỉ phần khôi phục lúc mở app mới nuốt lỗi.
        if (finishRekey(oldId, action)) {
            journal.remove(oldId)
            writeAtomic(rekeyJournal, journal.toString())
        }
    }

    /** Journal đi trước rename; mỗi bước ghi lại được, kể cả thư mục đã chuyển nhưng liên kết còn ở mã cũ.
     *  Gọi cả lúc mở app: mục không làm tiếp được thì bỏ (không đổi gì thêm), lỗi tạm thì giữ để lần sau - không bao giờ làm app văng mỗi lần mở. */
    @Synchronized
    fun recoverRekeys() {
        val journal = readJson(rekeyJournal) ?: return
        for (oldId in journal.keys().asSequence().toList()) {
            try {
                if (finishRekey(oldId, journal.getJSONObject(oldId))) {
                    journal.remove(oldId)
                    writeAtomic(rekeyJournal, journal.toString())
                }
            } catch (error: Exception) {
                runCatching { AppLog.w("Store", "đổi mã sách $oldId chưa xong, thử lại lần sau", error) } // Log không chạy trong test JVM
            }
        }
    }

    /** Làm tiếp một mục journal; true = mục đã xong (hay bỏ hẳn vì không còn gì để làm), bỏ khỏi journal. */
    private fun finishRekey(oldId: String, action: JSONObject): Boolean {
        val newId = action.optString("to")
        val source = runCatching { deletableBookDir(oldId) }.getOrNull() ?: return true
        val target = runCatching { deletableBookDir(newId) }.getOrNull() ?: return true
        if (source.isDirectory) {
            if (rawManifest(newId) != null) return true // mã mới đã thành một cuốn khác: bỏ việc đổi, cuốn cũ giữ nguyên
            target.deleteRecursively() // chỉ là cache nghe thẳng, như trước khi có journal
            check(source.renameTo(target)) { "Không chuyển được thư mục sách của bạn" }
        }
        if (!target.isDirectory) return true // cả hai thư mục đã mất (sách bị xoá): không còn gì để làm
        rawManifest(newId)?.let { writeAtomic(File(target, "book.json"), it.put("id", newId).toString()) }
        streamManifest(newId)?.let { writeAtomic(File(target, "stream.json"), it.put("id", newId).toString()) }
        moveLinks(oldId, newId)
        val all = printsBook()
        val entry = all.optJSONObject(oldId)
        if (entry != null) {
            all.remove(oldId)
            if (action.optBoolean("adopt")) entry.put("imported", false)
            all.put(newId, entry)
            writeAtomic(printsFile, all.toString())
        }
        return true
    }

    fun sizeOf(dir: File): Long = dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }

    // Cỡ từng cuốn, nhớ theo dấu thư mục (sizes.json NGOÀI thư mục sách): đi cả cây mỗi lần mở Thư viện là hàng chục nghìn lần liệt kê file khi có 100+ cuốn
    // (soát a101 F6). Dấu = mốc sửa của thư mục sách, các thư mục con có file lớn / hay đổi và book.json: thêm, xoá, thay file nào trong đó cũng đổi dấu.
    private val STAMPED = listOf("", "chapters", "edits", "music", "book.json")
    private val sizes = HashMap<String, Pair<String, Long>>()
    private var sizesFrom: File? = null
    private var sizesDirty = false

    private fun sizeStamp(dir: File): String = STAMPED.joinToString("/") { File(dir, it).lastModified().toString() }

    /** Cỡ (byte) của cuốn trong `dir`: dùng số đã nhớ khi dấu thư mục chưa đổi, không thì đo lại. Nhớ xuống đĩa ở [saveSizes]. */
    fun bookBytes(dir: File): Long {
        val stamp = sizeStamp(dir)
        synchronized(sizes) {
            loadSizes()
            sizes[dir.name]?.takeIf { it.first == stamp }?.let { return it.second }
        }
        val bytes = sizeOf(dir)
        synchronized(sizes) {
            sizes[dir.name] = stamp to bytes
            sizesDirty = true
        }
        return bytes
    }

    private fun loadSizes() {
        if (sizesFrom == root) return
        sizes.clear()
        sizesDirty = false
        sizesFrom = root
        val saved = runCatching { JSONObject(File(root, "sizes.json").readText(Charsets.UTF_8)) }.getOrNull() ?: return
        for (id in saved.keys()) {
            val entry = saved.optJSONObject(id) ?: continue
            sizes[id] = entry.optString("stamp") to entry.optLong("bytes")
        }
    }

    /** Ghi các cỡ vừa đo xuống đĩa (cuốn đã xoá thì bỏ khỏi sổ). Lỗi ghi thì thôi: lần mở sau đo lại. */
    fun saveSizes() {
        val text = synchronized(sizes) {
            if (sizes.keys.retainAll(bookFolders().map { it.name }.toSet())) sizesDirty = true
            if (!sizesDirty) return
            sizesDirty = false
            JSONObject().also { all -> sizes.forEach { (id, entry) -> all.put(id, JSONObject().put("stamp", entry.first).put("bytes", entry.second)) } }.toString()
        }
        runCatching { writeAtomic(File(root, "sizes.json"), text) }
    }

    /** Cỡ từng cuốn trên máy (mã cuốn -> byte) để màn "Tải sách" xếp cuốn nào chiếm nhiều nhất; tổng của chúng là cỡ cả thư viện. */
    fun bookSizes(): Map<String, Long> =
        bookFolders().associate { it.name to bookBytes(it) }.also { saveSizes() }
}
