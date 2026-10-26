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

    /** Mã các lượt đã báo xong / dừng / lỗi (giữ vài chục lượt gần nhất): snapshot WorkManager chụp trước đó không được hồi sinh chúng (soát a111 R3). */
    private val ended: MutableSet<String> = java.util.Collections.synchronizedSet(object : LinkedHashSet<String>() {
        override fun add(element: String): Boolean = super.add(element).also { if (size > 64) remove(first()) }
    })

    fun isEnded(run: String): Boolean = run in ended

    /**
     * Việc nền vừa bắt đầu: ghi chỗ lưu, ô "Kèm nhạc nền"... của lượt (`fields`) để giao diện mới mở dựng lại thông báo; lượt cũ của cuốn ấy (bị
     * thay) không còn được tính.
     */
    fun note(bookId: String, run: String, fields: JSONObject) {
        if (last[bookId]?.optString("run").let { it != null && it != run }) last.remove(bookId)
        notes[bookId] = JSONObject(fields.toString()).put("run", run)
    }

    /** Người nghe thêm (giao diện native không có plugin): cùng tin với `events` của từng kiểu xuất, mỗi người nghe tự gỡ bằng hàm trả về. */
    private val listeners = java.util.concurrent.CopyOnWriteArrayList<(JSONObject) -> Unit>()

    fun listen(listener: (JSONObject) -> Unit): () -> Unit {
        listeners.add(listener)
        return { listeners.remove(listener) }
    }

    fun emit(event: JSONObject) {
        val book = event.optString("bookId")
        val run = event.optString("run")
        if (event.optBoolean("finished") || event.optBoolean("stopped") || event.has("error")) {
            if (run.isNotEmpty()) ended.add(run)
            // Lượt cũ bị thay bằng lượt mới báo "dừng" muộn: không được xoá trạng thái của lượt mới.
            if (last[book]?.optString("run").let { it == null || it == run }) last.remove(book)
            if (notes[book]?.optString("run") == run) notes.remove(book)
        } else if (notes[book]?.optString("run").let { it == null || it == run }) {
            last[book] = event
        }
        // Người nghe thấy tin SAU khi bảng trạng thái đã đổi: hỏi lại [ExportJobs.running] trong lúc xử lý tin thì thấy đúng.
        for (listener in listeners) runCatching { listener(event) }
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
    internal fun merge(live: List<JSONObject>, works: List<Work>, ended: (Work) -> Boolean = { false }): List<JSONObject> {
        val known = live.map { it.optString("kind") to it.optString("bookId") }.toSet()
        val extra = works.filter { (it.kind to it.bookId) !in known && !ended(it) }.distinctBy { it.kind to it.bookId }
            .map { JSONObject().put("kind", it.kind).put("bookId", it.bookId).put("run", it.run) }
        return live + extra
    }

    fun running(context: Context): List<JSONObject> {
        val query = WorkQuery.Builder.fromTags(listOf(TAG))
            .addStates(listOf(WorkInfo.State.ENQUEUED, WorkInfo.State.RUNNING, WorkInfo.State.BLOCKED)).build()
        // Gọi từ luồng I/O (get() chờ cơ sở dữ liệu của WorkManager).
        val works = runCatching { WorkManager.getInstance(context).getWorkInfos(query).get() }.getOrDefault(emptyList())
            .mapNotNull { work(it.tags, it.id) }
        // Tin của tiến trình này chụp SAU truy vấn WorkManager: lượt xong trong lúc chờ truy vấn đã biến khỏi `live` và nằm trong `ended`, nên bản chụp
        // WorkManager cũ không hồi sinh nó thành "đang chạy" (soát a111 R3).
        val lives = listOf(Mp3Exports.live, M4bExports.live, ListenExports.live)
        val live = lives.flatMap { it.running() }
        return merge(live, works) { work -> lives.any { it.isEnded(work.run) } }
    }
}
