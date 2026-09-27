package vn.ebookreader.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * Kho trên điện thoại: sách đã tải (books/<id>/book.json + file) và trạng thái nghe (state/<id>.json).
 *
 * Trạng thái nghe CÙNG hình dạng với máy tính (ebook_reader/webui/listening.py) để hai bên gộp được với nhau:
 * mỗi phần mang mốc thời gian riêng, dấu trang đã xoá để lại dấu vết trong "deleted".
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

    // ---- trạng thái nghe -------------------------------------------------------------------------------------

    private fun stateFile(id: String) = File(root, "state/$id.json")

    @Synchronized
    fun state(id: String): JSONObject {
        val file = stateFile(id)
        val state = if (file.isFile) runCatching { JSONObject(file.readText()) }.getOrElse { JSONObject() } else JSONObject()
        if (!state.has("chapters")) state.put("chapters", JSONObject())
        if (!state.has("bookmarks")) state.put("bookmarks", JSONArray())
        return state
    }

    @Synchronized
    private fun save(id: String, state: JSONObject) = writeAtomic(stateFile(id), state.toString())

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

    /** Thay trạng thái bằng bản đã gộp từ máy tính (máy tính gộp theo đúng luật mới-hơn-thắng). */
    @Synchronized
    fun replaceState(id: String, merged: JSONObject) = save(id, merged)

    @Synchronized
    fun deleteBook(id: String) {
        bookDir(id).deleteRecursively()
    }

    // ---- một cuốn, hai đường đến -----------------------------------------------------------------------------

    private val PACKAGE_ID = Regex("bk-[0-9a-f]{24}")

    fun isPackageId(value: String) = PACKAGE_ID.matches(value)

    /** Cuốn đã có trên máy (đã tải hay đang nghe thẳng) mang mã sách cố định `packageId` nhưng mã máy tính khác. */
    @Synchronized
    fun findByPackage(packageId: String): JSONObject? =
        playableBooks().firstOrNull { it.optString("packageId") == packageId && it.optString("id") != packageId }

    /**
     * Cùng một cuốn đến bằng hai đường - mở từ file .abook (thư mục mang mã sách cố định `bk-...`) rồi máy tính cho biết
     * cuốn của nó có đúng mã ấy - là MỘT cuốn: thư mục đổi sang mã máy tính để chỗ nghe, dấu trang tiếp tục đồng bộ, audio
     * đã có không phải tải lại. Trạng thái nghe đi theo nếu mã máy tính chưa có trạng thái riêng; hai bản đã cùng tải về
     * (từ trước bản sửa này) thì để nguyên - không xoá gì của người nghe.
     */
    @Synchronized
    fun adopt(packageId: String, syncId: String) {
        if (packageId == syncId || !isPackageId(packageId) || manifest(packageId) == null || manifest(syncId) != null) return
        val target = bookDir(syncId)
        target.deleteRecursively() // chỉ là bộ nhớ đệm nghe thẳng (stream.json + file nhỏ): lấy lại được
        if (!bookDir(packageId).renameTo(target)) return
        val book = manifest(syncId) ?: return
        writeAtomic(File(target, "book.json"), book.put("id", syncId).put("packageId", packageId).toString())
        val imported = stateFile(packageId)
        if (imported.isFile && !stateFile(syncId).exists()) imported.renameTo(stateFile(syncId))
    }

    fun sizeOf(dir: File): Long = dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }
}
