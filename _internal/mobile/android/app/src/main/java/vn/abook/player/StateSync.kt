package vn.abook.player

import android.content.Context
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors

/**
 * Đẩy hồ sơ nghe đang dùng của một cuốn lên máy tính đã ghép (POST /sync/v1/books/<id>/state - webui/listening.py
 * merge_record) và nhận bản đã gộp của ĐÚNG hồ sơ ấy (Store.applySync). Dùng chung cho giao diện (LibraryPlugin) và
 * trình phát gốc (Playback): trước đây trình phát chỉ lưu chỗ nghe trên điện thoại, máy tính không bao giờ biết.
 *
 * Trình phát đẩy ngay khi dừng, còn đang phát thì tối đa mỗi phút một lần. Không có mạng thì im lặng - cuốn ấy vào [pending] và được đẩy
 * ngay khi nối lại được máy giữ sách ([flushPending]: mở Thư viện / Tải sách, vòng điều khiển từ xa) chứ không chờ lần dừng sau (soát a68 lỗi 9:
 * chỗ nghe lúc mất mạng không về máy tính, máy tính mở lại chỗ cũ rồi kéo điện thoại về đó). Mỗi phần của hồ sơ mang mốc thời gian, gộp lúc nào
 * cũng đúng: bên nghe sau thắng.
 */
object StateSync {
    private const val WHILE_PLAYING_MS = 60_000L
    private val io = Executors.newSingleThreadExecutor()
    @Volatile private var lastPushMs = 0L
    private val pending by lazy { PendingPushes(File(Store.root, "state-pending.json")) }

    /** Đẩy ngay trên luồng hiện tại (đã ở luồng nền). `only`: đúng hồ sơ ấy thay vì hồ sơ đang dùng (xem Store.syncBody). */
    fun pushNow(context: Context, bookId: String, only: String? = null) {
        if (bookId.isBlank()) return
        // Sách của thiết bị ghép (Peers) đẩy về đúng thiết bị ấy; sách của máy tính chính cần máy tính đã ghép.
        val fromPeer = !Store.playableManifest(bookId)?.optString("source").isNullOrEmpty()
        if (!fromPeer && !SyncLink.paired(context)) return
        val (link, remote) = runCatching { SyncLink.linkFor(context, bookId) }.getOrNull() ?: return
        pending.add(bookId) // gỡ khi máy kia đã nhận
        val reply = runCatching {
            JSONObject(SyncLink.request(context, "POST", "/sync/v1/books/$remote/state", Store.syncBody(bookId, only),
                readTimeoutMs = 10_000, connectTimeoutMs = 3000, root = link.base, token = link.token))
        }.getOrNull() ?: return
        lastPushMs = SystemClock.elapsedRealtime()
        Store.applySync(bookId, reply)
        pending.remove(bookId)
    }

    /** Vừa nói chuyện được với máy giữ sách: đẩy các cuốn có chỗ nghe chưa tới được nó (ở luồng nền của StateSync). */
    fun flushPending(context: Context) {
        if (pending.ids().isEmpty()) return
        io.execute { pending.ids().forEach { runCatching { pushNow(context, it) } } }
    }

    /** Trình phát: `force` khi vừa dừng; đang phát thì bỏ qua nếu vừa đẩy chưa tới một phút. */
    fun pushSoon(context: Context, bookId: String, force: Boolean) {
        if (!force && SystemClock.elapsedRealtime() - lastPushMs < WHILE_PLAYING_MS) return
        lastPushMs = SystemClock.elapsedRealtime()
        io.execute { runCatching { pushNow(context, bookId) } }
    }
}

/** Các cuốn có chỗ nghe chưa đẩy được lên máy giữ sách (mất mạng, máy tắt) - lưu ra file để cả khi app đóng rồi mở lại vẫn nhớ. */
class PendingPushes(private val file: File) {
    @Synchronized
    fun ids(): Set<String> = runCatching {
        val array = JSONArray(file.readText())
        (0 until array.length()).map { array.getString(it) }.toSet()
    }.getOrDefault(emptySet())

    @Synchronized
    fun add(id: String) {
        val now = ids()
        if (id !in now) write(now + id)
    }

    @Synchronized
    fun remove(id: String) {
        val now = ids()
        if (id in now) write(now - id)
    }

    private fun write(ids: Set<String>) {
        file.parentFile?.mkdirs()
        Store.writeAtomic(file, JSONArray(ids.sorted()).toString())
    }
}

/** Chỗ nghe đáng tin để lưu và đồng bộ (soát a68 lỗi 2): không vượt độ dài chương quá [TOLERANCE_SECONDS] - độ dài trong gói lệch vài phần giây với file thật. Máy tính
 *  kiểm cùng luật khi nhận (webui/sync.py `trusted_state`). */
object PlacePolicy {
    const val TOLERANCE_SECONDS = 2.0

    /** `duration` <= 0: chưa biết độ dài, không xét. */
    fun fits(seconds: Double, duration: Double): Boolean = duration <= 0 || seconds <= duration + TOLERANCE_SECONDS
}
