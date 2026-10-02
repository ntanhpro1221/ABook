package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import java.util.UUID

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
        }
    }

    fun bookDir(id: String) = File(root, "books/$id")

    fun file(id: String, relative: String): File {
        val target = File(bookDir(id), relative).canonicalFile
        require(target.path.startsWith(bookDir(id).canonicalPath)) { "đường dẫn ra ngoài thư mục sách" }
        return target
    }

    @Synchronized
    fun manifest(id: String): JSONObject? {
        val file = File(bookDir(id), "book.json")
        return if (file.isFile) JSONObject(file.readText()) else null
    }

    @Synchronized
    fun books(): List<JSONObject> =
        File(root, "books").listFiles()?.mapNotNull { dir -> manifest(dir.name) } ?: emptyList()

    /**
     * Sách nghe thẳng từ máy tính, chưa tải (Streaming): gói sách cất ở `stream.json` - KHÔNG phải `book.json` - nên
     * không bao giờ bị tính là đã tải; các file nhỏ (bìa, văn bản đọc theo, dàn nhân vật, câu mẫu) nằm cạnh đúng chỗ của
     * sách đã tải, nên giao diện đọc chúng như nhau và tải hẳn về sau chỉ việc ghi thêm audio + `book.json`.
     */
    @Synchronized
    fun streamManifest(id: String): JSONObject? {
        val file = File(bookDir(id), "stream.json")
        return if (file.isFile) runCatching { JSONObject(file.readText()) }.getOrNull() else null
    }

    /** Gói sách phát được: đã tải thì bản đã tải, không thì bản nghe thẳng đã cất. */
    fun playableManifest(id: String): JSONObject? = manifest(id) ?: streamManifest(id)

    @Synchronized
    fun playableBooks(): List<JSONObject> =
        File(root, "books").listFiles()?.mapNotNull { dir -> playableManifest(dir.name) } ?: emptyList()

    fun writeAtomic(target: File, text: String) {
        target.parentFile?.mkdirs()
        val temporary = File(target.path + ".part")
        temporary.writeText(text)
        if (!temporary.renameTo(target)) {
            target.delete()
            temporary.renameTo(target)
        }
    }

    // ---- hồ sơ nghe + liên kết với sách ----------------------------------------------------------------------

    private const val DEFAULT_RECORD_NAME = "Mặc định"
    private val RECORD_ID = Regex("r-[0-9a-f]{16}")
    private val SYNC_KEYS = listOf("record", "recordName", "nameAt", "activeAt", "book", "records", "active", "activeState",
        "deleted", "deletedRecords")
    private val recordsFile get() = File(root, "records.json")
    private var recordsCache: JSONObject? = null

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
     * {"version": 2, "records": {mã: {name, nameAt, createdAt}}, "links": {mã sách: {records, active, activeAt}},
     *  "deleted": {mã: lúc xoá}} - bia mộ để hồ sơ đã xoá ở máy nào cũng không sống lại khi đồng bộ.
     */
    private fun recordsBook(): JSONObject {
        recordsCache?.let { return it }
        val loaded = if (recordsFile.isFile) runCatching { JSONObject(recordsFile.readText()) }.getOrNull() else null
        val book = loaded ?: upgradeStates()
        if (!book.has("deleted")) book.put("deleted", JSONObject())
        recordsCache = book
        return book
    }

    /** Bản cũ state/<mã sách>.json: mỗi sách thành một hồ sơ "Mặc định" (file đổi tên theo mã hồ sơ). */
    private fun upgradeStates(): JSONObject {
        val book = JSONObject().put("version", 2).put("records", JSONObject()).put("links", JSONObject())
        File(root, "state").listFiles()?.filter { it.isFile && it.name.endsWith(".json") && !RECORD_ID.matches(it.name.removeSuffix(".json")) }
            ?.forEach { file ->
                val record = defaultRecordId(file.name.removeSuffix(".json"))
                if (file.renameTo(File(root, "state/$record.json"))) {
                    book.getJSONObject("records").put(record, JSONObject().put("name", DEFAULT_RECORD_NAME).put("createdAt", now()).put("nameAt", 0.0))
                    book.getJSONObject("links").put(file.name.removeSuffix(".json"),
                        JSONObject().put("records", JSONArray().put(record)).put("active", record).put("activeAt", 0.0))
                }
            }
        writeAtomic(recordsFile, book.toString())
        return book
    }

    private fun saveRecords(book: JSONObject) {
        recordsCache = book
        writeAtomic(recordsFile, book.toString())
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

    private fun withoutSyncKeys(value: JSONObject) = JSONObject(value.toString()).also { copy -> SYNC_KEYS.forEach(copy::remove) }

    /**
     * Gói gửi máy tính (webui/listening.py merge_record): trạng thái hồ sơ đang dùng + mã, tên và lúc đặt tên, lúc chọn
     * nó, cùng bia mộ những hồ sơ đã xoá trên điện thoại. Hoặc đúng hồ sơ `only` (hồ sơ vừa rời: chỗ nghe cuối của nó
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
            .put("deletedRecords", book.getJSONObject("deleted"))
    }

    /**
     * Trả lời của máy tính: trạng thái đã gộp của hồ sơ vừa gửi, tên các hồ sơ, sách hồ sơ gắn ở máy tính (có thể đã được
     * chuyển), hồ sơ đang dùng bên ấy - bên chọn sau thắng, kèm trạng thái của nó nếu điện thoại chưa có.
     * Máy tính đời trước không trả `record`: trạng thái ấy là của hồ sơ đang dùng.
     */
    @Synchronized
    fun applySync(bookId: String, reply: JSONObject) {
        val record = reply.optString("record")
        if (!RECORD_ID.matches(record)) {
            save(bookId, withoutSyncKeys(reply))
            return
        }
        val book = recordsBook()
        val records = book.getJSONObject("records")
        val links = book.getJSONObject("links")
        // bia mộ của máy tính: xoá theo, kể cả hồ sơ vừa gửi (máy tính trả deleted=true)
        val tombstones = reply.optJSONObject("deletedRecords") ?: JSONObject()
        if (reply.optBoolean("deleted")) tombstones.put(record, now())
        for (gone in tombstones.keys()) {
            if (!RECORD_ID.matches(gone)) continue
            forget(book, gone)
            book.getJSONObject("deleted").put(gone, tombstones.optDouble(gone, now()))
        }
        if (reply.optBoolean("deleted")) {
            saveRecords(book)
            return
        }
        writeAtomic(recordFile(record), withoutSyncKeys(reply).toString())
        val known = reply.optJSONArray("records") ?: JSONArray()
        for (index in 0 until known.length()) {
            val item = known.optJSONObject(index) ?: continue
            val id = item.optString("id")
            if (!RECORD_ID.matches(id)) continue
            val meta = records.optJSONObject(id) ?: JSONObject().put("createdAt", now()).put("nameAt", 0.0)
            // tên: bên đổi sau thắng
            if (!meta.has("name") || item.optDouble("nameAt", 0.0) > meta.optDouble("nameAt", 0.0)) {
                meta.put("name", item.optString("name", DEFAULT_RECORD_NAME)).put("nameAt", item.optDouble("nameAt", 0.0))
            }
            records.put(id, meta)
        }
        val owner = reply.optString("book").ifBlank { bookId }
        if (owner != bookId) unlink(links, bookId, record)
        val link = links.optJSONObject(owner) ?: JSONObject().put("records", JSONArray()).put("activeAt", 0.0)
        addRecord(link, record)
        val active = reply.optJSONObject("active")
        val chosen = active?.optString("record").orEmpty()
        val chosenAt = active?.optDouble("at", 0.0) ?: 0.0
        // Cuốn đang PHÁT thì chưa đổi hồ sơ (trình phát ghi vào hồ sơ đang dùng: chỗ nghe của hồ sơ cũ sẽ rơi sang hồ sơ
        // mới) - lần đồng bộ sau, lúc đã dừng (dừng là đẩy ngay), đổi. Đang dừng thì đổi, rồi trình phát theo sang.
        val holding = Playback.bookId == owner
        var follow = false
        if (RECORD_ID.matches(chosen) && chosenAt > link.optDouble("activeAt", 0.0) && !(holding && Playback.isPlaying)) {
            follow = holding && link.optString("active") != chosen
            addRecord(link, chosen)
            link.put("active", chosen).put("activeAt", chosenAt)
            reply.optJSONObject("activeState")?.let { writeAtomic(recordFile(chosen), withoutSyncKeys(it).toString()) }
        }
        if (link.optString("active").isBlank()) link.put("active", record)
        links.put(owner, link)
        saveRecords(book)
        if (follow) Playback.onMain { Playback.follow(owner) }
    }

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
            val state = recordFile(id).takeIf { it.isFile }?.let { runCatching { JSONObject(it.readText()) }.getOrNull() }
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

    /** Liên kết hồ sơ của cuốn mở từ file sang mã máy tính khi hai bên nhận ra là một cuốn (adopt). */
    private fun moveLinks(from: String, to: String) {
        val book = recordsBook()
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

    @Synchronized
    fun state(id: String): JSONObject = knownActiveRecord(id)?.let(::recordState) ?: recordState(null)

    private fun recordState(record: String?): JSONObject {
        val file = record?.let(::recordFile)
        val state = if (file != null && file.isFile) runCatching { JSONObject(file.readText()) }.getOrElse { JSONObject() } else JSONObject()
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
        for ((field, at) in listOf("rate" to "rateAt", "finished" to "finishedAt")) {
            if (theirs.has(field) && stamp(theirs, at) > stamp(result, at)) {
                result.put(field, theirs.get(field)).put(at, theirs.get(at))
            }
        }
        val deleted = JSONObject((result.optJSONObject("deleted") ?: JSONObject()).toString())
        theirs.optJSONObject("deleted")?.let { gone -> for (key in gone.keys()) deleted.put(key, gone.get(key)) }
        val marks = LinkedHashMap<String, JSONObject>()
        result.getJSONArray("bookmarks").let { list -> for (i in 0 until list.length()) list.optJSONObject(i)?.let { marks[it.optString("id")] = it } }
        (theirs.optJSONArray("bookmarks") ?: JSONArray()).let { list ->
            for (i in 0 until list.length()) {
                val mark = list.optJSONObject(i) ?: continue
                if (stamp(mark) >= stamp(marks[mark.optString("id")]) || marks[mark.optString("id")] == null) marks[mark.optString("id")] = mark
            }
        }
        result.put("bookmarks", JSONArray(marks.values.filter { !deleted.has(it.optString("id")) }.sortedBy { stamp(it) }))
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

    @Synchronized
    fun progress(id: String, chapterId: Int, seconds: Double, duration: Double): JSONObject {
        val state = state(id)
        val at = now()
        state.put("last", JSONObject().put("chapterId", chapterId).put("seconds", seconds).put("at", at))
        val chapters = state.getJSONObject("chapters")
        val record = chapters.optJSONObject(chapterId.toString()) ?: JSONObject().put("heard", 0.0).put("done", false)
        record.put("heard", maxOf(record.optDouble("heard", 0.0), seconds))
        if (duration > 0 && duration - seconds <= DONE_TAIL_SECONDS) record.put("done", true)
        if (duration > 0) record.put("duration", duration)
        record.put("at", at)
        chapters.put(chapterId.toString(), record)
        state.put("updatedAt", at)
        save(id, state)
        return state
    }

    @Synchronized
    fun setChapterDone(id: String, chapterId: Int, done: Boolean): JSONObject {
        val state = state(id)
        val chapters = state.getJSONObject("chapters")
        val record = chapters.optJSONObject(chapterId.toString()) ?: JSONObject().put("heard", 0.0)
        record.put("done", done)
        if (!done) record.put("heard", 0.0)
        record.put("at", now())
        chapters.put(chapterId.toString(), record)
        state.put("updatedAt", now())
        save(id, state)
        return state
    }

    @Synchronized
    fun setFinished(id: String, finished: Boolean): JSONObject {
        val state = state(id)
        state.put("finished", finished).put("finishedAt", now()).put("updatedAt", now())
        save(id, state)
        return state
    }

    @Synchronized
    fun setRate(id: String, rate: Double) {
        val state = state(id)
        state.put("rate", rate).put("rateAt", now()).put("updatedAt", now())
        save(id, state)
    }

    /** Một phiên nghe (cùng hình dạng với máy tính: webui/listening.py add_session), giữ 200 phiên gần nhất. */
    @Synchronized
    fun addSession(id: String, session: JSONObject) {
        val state = state(id)
        val sessions = state.optJSONArray("sessions") ?: JSONArray()
        val kept = JSONArray()
        val start = maxOf(0, sessions.length() - 199)
        for (index in start until sessions.length()) kept.put(sessions.getJSONObject(index))
        kept.put(session)
        state.put("sessions", kept).put("updatedAt", now())
        save(id, state)
    }

    @Synchronized
    fun addBookmark(id: String, chapterId: Int, seconds: Double, note: String): JSONObject {
        val state = state(id)
        val mark = JSONObject()
            .put("id", UUID.randomUUID().toString().replace("-", "").substring(0, 12))
            .put("chapterId", chapterId).put("seconds", seconds).put("note", note.take(500)).put("at", now())
        state.getJSONArray("bookmarks").put(mark)
        state.put("updatedAt", now())
        save(id, state)
        return mark
    }

    @Synchronized
    fun updateBookmark(id: String, markId: String, note: String) {
        val state = state(id)
        val marks = state.getJSONArray("bookmarks")
        for (index in 0 until marks.length()) {
            val mark = marks.getJSONObject(index)
            if (mark.optString("id") == markId) mark.put("note", note.take(500)).put("at", now())
        }
        state.put("updatedAt", now())
        save(id, state)
    }

    @Synchronized
    fun deleteBookmark(id: String, markId: String) {
        val state = state(id)
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
        save(id, state)
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

    @Synchronized
    fun deleteBook(id: String) {
        deletableBookDir(id).deleteRecursively()
        val all = printsBook()
        if (all.has(id)) {
            all.remove(id)
            writeAtomic(printsFile, all.toString())
        }
    }

    // ---- một cuốn, hai đường đến -----------------------------------------------------------------------------
    //
    // Sách không mang mã nào (chủ sách 27-09: sách và dữ liệu nghe không biết đến mã; mã chỉ là thứ app dùng để liên
    // kết). App nhận ra cùng một lần sản xuất bằng audio từng chương: chung một chương giống hệt từng byte (tên, cỡ, mã
    // băm) là cùng một cuốn. Sổ của app `prints.json` - nằm NGOÀI thư mục sách - ghi cỡ + mã băm các chương đã biết của
    // từng cuốn, và cuốn nào mở từ file mà chưa gắn với cuốn nào của máy tính.

    private val printsFile get() = File(root, "prints.json")

    private fun printsBook(): JSONObject =
        if (printsFile.isFile) runCatching { JSONObject(printsFile.readText()) }.getOrElse { JSONObject() } else JSONObject()

    @Synchronized
    fun rememberChapters(id: String, chapters: JSONObject, imported: Boolean) {
        val all = printsBook()
        val entry = all.optJSONObject(id) ?: JSONObject()
        val known = entry.optJSONObject("chapters") ?: JSONObject()
        for (name in chapters.keys()) known.put(name, chapters.getJSONObject(name))
        all.put(id, entry.put("chapters", known).put("imported", imported))
        writeAtomic(printsFile, all.toString())
    }

    @Synchronized
    fun isImported(id: String) = printsBook().optJSONObject(id)?.optBoolean("imported") == true

    /** Cuốn mở từ file còn trên máy mà chưa gắn với cuốn nào của máy tính. */
    @Synchronized
    fun importedBooks(): List<String> {
        val all = printsBook()
        return all.keys().asSequence().filter { all.getJSONObject(it).optBoolean("imported") && manifest(it) != null }.toList()
    }

    /** Cỡ + mã băm các chương của một cuốn, như đã ghi trong sổ. */
    @Synchronized
    fun chapterPrints(id: String): JSONObject = printsBook().optJSONObject(id)?.optJSONObject("chapters") ?: JSONObject()

    /**
     * Cuốn đã có trên máy (tải qua Wi-Fi hay mở từ file) có chung ít nhất một chương audio với `chapters`
     * ({"chapters/x.mp3": {size, sha256}}). Chỉ băm file trùng tên và cỡ, rồi ghi vào sổ để lần sau khỏi băm.
     */
    @Synchronized
    fun findByChapters(chapters: JSONObject): String? {
        for (book in books()) {
            val id = book.optString("id")
            if (id.isBlank()) continue
            val known = chapterPrints(id)
            for (name in chapters.keys()) {
                val wanted = chapters.getJSONObject(name)
                val local = runCatching { file(id, name) }.getOrNull() ?: continue
                if (!local.isFile || local.length() != wanted.optLong("size", -1)) continue
                val recorded = known.optJSONObject(name)
                val sha256 = if (recorded != null && recorded.optLong("size") == local.length()) {
                    recorded.optString("sha256")
                } else {
                    sha256(local).also {
                        rememberChapters(id, JSONObject().put(name, JSONObject().put("size", local.length()).put("sha256", it)),
                            isImported(id))
                    }
                }
                if (sha256 == wanted.optString("sha256")) return id
            }
        }
        return null
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(1 shl 16)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }

    /**
     * Cuốn mở từ file mà máy tính cho biết là cuốn `syncId` của nó (cùng audio): MỘT cuốn - thư mục đổi sang mã máy tính
     * để chỗ nghe, dấu trang tiếp tục đồng bộ, audio đã có không phải tải lại. Hồ sơ nghe của cuốn đi theo liên kết (hồ sơ
     * không biết gì về sách, chỉ bảng liên kết đổi); hai bản đã cùng tải về thì để nguyên - không xoá gì của người nghe.
     */
    @Synchronized
    fun adopt(localId: String, syncId: String) {
        if (localId == syncId || !isImported(localId) || manifest(localId) == null || manifest(syncId) != null) return
        val target = bookDir(syncId)
        target.deleteRecursively() // chỉ là bộ nhớ đệm nghe thẳng (stream.json + file nhỏ): lấy lại được
        if (!bookDir(localId).renameTo(target)) return
        val book = manifest(syncId) ?: return
        writeAtomic(File(target, "book.json"), book.put("id", syncId).toString())
        moveLinks(localId, syncId)
        val all = printsBook()
        val entry = all.optJSONObject(localId)
        all.remove(localId)
        if (entry != null) all.put(syncId, entry.put("imported", false))
        writeAtomic(printsFile, all.toString())
    }

    /** Cuốn của máy tính đã ghép chính - tải hẳn hay nghe thẳng; không kể cuốn mở từ file, cuốn của thiết bị ghép khác
     *  (gói mang `source`). */
    @Synchronized
    fun computerBooks(): List<String> {
        val prints = printsBook()
        return File(root, "books").listFiles()?.filter { it.isDirectory }?.mapNotNull { dir ->
            val manifest = playableManifest(dir.name) ?: return@mapNotNull null
            val imported = prints.optJSONObject(dir.name)?.optBoolean("imported") == true
            dir.name.takeIf { manifest.optString("source").isEmpty() && !imported }
        } ?: emptyList()
    }

    /**
     * Máy tính đổi mã một cuốn (mã kiểu cũ - đường dẫn thư mục mã hoá - sang mã mới, docs/BOOK_IDS.md): thư
     * mục, gói sách, liên kết hồ sơ nghe và sổ dấu vân tay sang mã mới. Hồ sơ giữ nguyên mã (máy tính cũng giữ) nên vẫn
     * gộp được với nhau. Máy đã có bản tải hẳn mang mã mới: để nguyên cả hai - không xoá gì của người nghe.
     */
    @Synchronized
    fun rekey(oldId: String, newId: String) {
        if (oldId == newId) return
        val target = runCatching { deletableBookDir(newId) }.getOrNull() ?: return
        val source = runCatching { deletableBookDir(oldId) }.getOrNull() ?: return
        if (!source.isDirectory || manifest(newId) != null) return
        target.deleteRecursively() // chỉ có thể là bộ nhớ đệm nghe thẳng của mã mới: lấy lại được
        if (!source.renameTo(target)) return
        manifest(newId)?.let { writeAtomic(File(target, "book.json"), it.put("id", newId).toString()) }
        streamManifest(newId)?.let { writeAtomic(File(target, "stream.json"), it.put("id", newId).toString()) }
        moveLinks(oldId, newId)
        val all = printsBook()
        val entry = all.optJSONObject(oldId) ?: return
        all.remove(oldId)
        all.put(newId, entry)
        writeAtomic(printsFile, all.toString())
    }

    fun sizeOf(dir: File): Long = dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }
}
