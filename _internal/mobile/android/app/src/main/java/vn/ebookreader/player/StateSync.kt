package vn.ebookreader.player

import android.content.Context
import android.os.SystemClock
import org.json.JSONObject
import java.util.concurrent.Executors

/**
 * Đẩy hồ sơ nghe đang dùng của một cuốn lên máy tính đã ghép (POST /sync/v1/books/<id>/state - webui/listening.py
 * merge_record) và nhận bản đã gộp của ĐÚNG hồ sơ ấy (Store.applySync). Dùng chung cho giao diện (LibraryPlugin) và
 * trình phát gốc (Playback): trước đây trình phát chỉ lưu chỗ nghe trên điện thoại, máy tính không bao giờ biết.
 *
 * Trình phát đẩy ngay khi dừng, còn đang phát thì tối đa mỗi phút một lần. Không có mạng thì im lặng - lần sau đẩy lại
 * (mỗi phần của hồ sơ mang mốc thời gian, gộp lúc nào cũng đúng).
 */
object StateSync {
    private const val WHILE_PLAYING_MS = 60_000L
    private val io = Executors.newSingleThreadExecutor()
    @Volatile private var lastPushMs = 0L

    /** Đẩy ngay trên luồng hiện tại (đã ở luồng nền). `only`: đúng hồ sơ ấy thay vì hồ sơ đang dùng (xem Store.syncBody). */
    fun pushNow(context: Context, bookId: String, only: String? = null) {
        if (bookId.isBlank() || !SyncLink.paired(context)) return
        val reply = runCatching {
            JSONObject(SyncLink.request(context, "POST", "/sync/v1/books/$bookId/state", Store.syncBody(bookId, only),
                readTimeoutMs = 10_000, connectTimeoutMs = 3000))
        }.getOrNull() ?: return
        lastPushMs = SystemClock.elapsedRealtime()
        Store.applySync(bookId, reply)
    }

    /** Trình phát: `force` khi vừa dừng; đang phát thì bỏ qua nếu vừa đẩy chưa tới một phút. */
    fun pushSoon(context: Context, bookId: String, force: Boolean) {
        if (!force && SystemClock.elapsedRealtime() - lastPushMs < WHILE_PLAYING_MS) return
        lastPushMs = SystemClock.elapsedRealtime()
        io.execute { runCatching { pushNow(context, bookId) } }
    }
}
