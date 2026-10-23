package vn.abook.player

import android.content.Context
import androidx.work.WorkInfo
import androidx.work.WorkManager
import androidx.work.WorkQuery
import org.json.JSONObject
import java.util.UUID
import java.util.concurrent.ConcurrentHashMap

/**
 * Tin cuối của mỗi lượt xuất đang chạy của MỘT kiểu xuất (theo cuốn): giao diện được dựng lại (vuốt app khỏi danh sách gần đây, WebView tải lại)
 * trong lúc việc nền vẫn chạy thì hỏi [ExportJobs.running] để hiện lại thông báo tiến độ và nghe tiếp tin "xong" / "lỗi". Dùng chung cho
 * xuất MP3, M4B và sách nói.
 */
class ExportLive(val kind: String) {
    private val last = ConcurrentHashMap<String, JSONObject>()
    private val notes = ConcurrentHashMap<String, JSONObject>()

    /**
     * Việc nền vừa bắt đầu: ghi chỗ lưu, ô "Kèm nhạc nền"... của lượt (`fields`) để giao diện mới mở dựng lại thông báo; lượt cũ của cuốn ấy (bị
     * thay) không còn được tính.
     */
    fun note(bookId: String, run: String, fields: JSONObject) {
        if (last[bookId]?.optString("run").let { it != null && it != run }) last.remove(bookId)
        notes[bookId] = JSONObject(fields.toString()).put("run", run)
    }

    fun emit(event: JSONObject) {
        val book = event.optString("bookId")
        val run = event.optString("run")
        if (event.optBoolean("finished") || event.optBoolean("stopped") || event.has("error")) {
            // Lượt cũ bị thay bằng lượt mới báo "dừng" muộn: không được xoá trạng thái của lượt mới.
            if (last[book]?.optString("run").let { it == null || it == run }) last.remove(book)
            if (notes[book]?.optString("run") == run) notes.remove(book)
        } else if (notes[book]?.optString("run").let { it == null || it == run }) {
            last[book] = event
        }
    }

    /** Các cuốn đang có lượt chạy. */
    fun books(): Set<String> = last.keys + notes.keys

    /** Mỗi lượt đang chạy: tin cuối kèm các trường ghi lúc bắt đầu và `kind`. Chưa có tin nào thì chỉ có mã lượt và các trường ấy. */
    fun running(): List<JSONObject> = books().mapNotNull { book ->
        val event = last[book]
        val note = notes[book]
        val out = JSONObject(event?.toString() ?: JSONObject().put("bookId", book).toString())
        note?.keys()?.forEach { key -> if (!out.has(key)) out.put(key, note.get(key)) }
        if (!out.has("run")) return@mapNotNull null
        out.put("kind", kind)
    }
}

/** Mọi việc xuất đang chạy trên máy: tin của tiến trình này, bổ sung bằng việc WorkManager còn giữ (tiến trình bị giết, việc chờ chạy lại). */
object ExportJobs {
    const val TAG = "abook-export"

    /** Dấu gắn vào mỗi việc xuất để tìm lại từ WorkManager. */
    fun tags(kind: String, bookId: String): Set<String> = setOf(TAG, "export-kind:$kind", "export-book:$bookId")

    class Work(val kind: String, val bookId: String, val run: String)

    internal fun work(tags: Set<String>, id: UUID): Work? {
        if (TAG !in tags) return null
        val kind = tags.firstOrNull { it.startsWith("export-kind:") }?.removePrefix("export-kind:") ?: return null
        val book = tags.firstOrNull { it.startsWith("export-book:") }?.removePrefix("export-book:") ?: return null
        return Work(kind, book, id.toString())
    }

    /** Việc WorkManager còn giữ mà tiến trình này chưa có tin nào của kiểu + cuốn ấy thì thêm một dòng tối thiểu (mã lượt, chưa có tiến độ). */
    internal fun merge(live: List<JSONObject>, works: List<Work>): List<JSONObject> {
        val known = live.map { it.optString("kind") to it.optString("bookId") }.toSet()
        val extra = works.filter { (it.kind to it.bookId) !in known }.distinctBy { it.kind to it.bookId }
            .map { JSONObject().put("kind", it.kind).put("bookId", it.bookId).put("run", it.run) }
        return live + extra
    }

    fun running(context: Context): List<JSONObject> {
        val live = Mp3Exports.live.running() + M4bExports.live.running() + ListenExports.live.running()
        val query = WorkQuery.Builder.fromTags(listOf(TAG))
            .addStates(listOf(WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED)).build()
        // Gọi từ luồng I/O (get() chờ cơ sở dữ liệu của WorkManager).
        val works = runCatching { WorkManager.getInstance(context).getWorkInfos(query).get() }.getOrDefault(emptyList())
            .mapNotNull { work(it.tags, it.id) }
        return merge(live, works)
    }
}
