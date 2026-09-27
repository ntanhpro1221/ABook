package vn.ebookreader.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
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
     * để chỗ nghe, dấu trang tiếp tục đồng bộ, audio đã có không phải tải lại. Trạng thái nghe đi theo nếu mã máy tính
     * chưa có trạng thái riêng; hai bản đã cùng tải về thì để nguyên - không xoá gì của người nghe.
     */
    @Synchronized
    fun adopt(localId: String, syncId: String) {
        if (localId == syncId || !isImported(localId) || manifest(localId) == null || manifest(syncId) != null) return
        val target = bookDir(syncId)
        target.deleteRecursively() // chỉ là bộ nhớ đệm nghe thẳng (stream.json + file nhỏ): lấy lại được
        if (!bookDir(localId).renameTo(target)) return
        val book = manifest(syncId) ?: return
        writeAtomic(File(target, "book.json"), book.put("id", syncId).toString())
        val imported = stateFile(localId)
        if (imported.isFile && !stateFile(syncId).exists()) imported.renameTo(stateFile(syncId))
        val all = printsBook()
        val entry = all.optJSONObject(localId)
        all.remove(localId)
        if (entry != null) all.put(syncId, entry.put("imported", false))
        writeAtomic(printsFile, all.toString())
    }

    fun sizeOf(dir: File): Long = dir.walkTopDown().filter { it.isFile }.sumOf { it.length() }
}
