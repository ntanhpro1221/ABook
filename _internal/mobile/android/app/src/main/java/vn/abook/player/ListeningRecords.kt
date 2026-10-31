package vn.abook.player

import android.content.Context
import org.json.JSONArray
import java.util.concurrent.ExecutionException
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit

/**
 * Hồ sơ nghe của một cuốn (độc lập với sách, app giữ liên kết - [Store]) - việc của giao diện (`ui.data.LibraryRepo`). Mỗi hàm đổi xong trả [Change]: danh sách hồ sơ mới + việc báo máy tính ([Change.push], chạy ở luồng nền sau khi đã trả lời người nghe).
 * Mọi hàm đọc / ghi đĩa: gọi ở luồng nền.
 */
object ListeningRecords {
    /**
     * `records`: danh sách hồ sơ của cuốn sau khi đổi. `push`: báo máy tính - hồ sơ vừa rời (`left` - chỗ nghe cuối của nó, lưu lúc đổi, chưa tới máy tính: điện thoại
     * chỉ đẩy hồ sơ đang dùng), rồi hồ sơ đang dùng (lựa chọn, tên, bia mộ). `first`: cuốn đẩy trước tiên (cuốn vừa nhận hồ sơ chuyển tới - máy tính gắn lại hồ sơ
     * theo lần chuyển ấy trước khi nghe cuốn cũ). Im lặng nếu không có mạng.
     */
    class Change(val records: JSONArray, val push: () -> Unit)

    private fun change(context: Context, id: String, records: JSONArray, left: String? = null, first: String? = null) = Change(records) {
        if (first != null) runCatching { StateSync.pushNow(context, first) }
        if (left != null && left != Store.knownActiveRecord(id) && Store.hasRecord(left)) {
            runCatching { StateSync.pushNow(context, id, left) }
        }
        runCatching { StateSync.pushNow(context, id) }
    }

    /** Đổi hồ sơ của một cuốn: cuốn đang nạp trong trình phát thì qua Playback trên luồng chính (trình phát theo sang hồ sơ mới), cuốn khác thì đổi thẳng. */
    private fun switching(id: String, change: () -> JSONArray): JSONArray {
        if (Playback.bookId != id) return change()
        val task = FutureTask { Playback.switchRecord(id, change) }
        Playback.onMain { task.run() }
        return try {
            task.get(10, TimeUnit.SECONDS)
        } catch (error: ExecutionException) {
            throw error.cause ?: error
        }
    }

    /** Hồ sơ mới (nghe từ đầu), thành hồ sơ đang dùng; hồ sơ cũ giữ nguyên. */
    fun create(context: Context, id: String, name: String): Change {
        val left = Store.knownActiveRecord(id)
        return change(context, id, switching(id) { Store.createRecord(id, name) }, left)
    }

    fun activate(context: Context, id: String, record: String): Change {
        val left = Store.knownActiveRecord(id)
        // Hồ sơ máy giữ sách báo trong danh sách mà điện thoại chưa có trạng thái (mới hiện ra ở bộ chọn): lấy trạng thái của đúng mã
        // ấy trước khi nạp - đẩy hồ sơ rỗng, lời đáp mang trạng thái đã gộp (Store.applySync). Không với tới máy giữ sách thì chọn như cũ.
        if (Store.hasRecord(record) && !Store.hasState(record)) runCatching { StateSync.pushNow(context, id, record) }
        return change(context, id, switching(id) { Store.activateRecord(id, record) }, left)
    }

    fun rename(context: Context, id: String, record: String, name: String): Change =
        change(context, id, Store.renameRecord(id, record, name))

    /** Chuyển hồ sơ sang cuốn `to`: cuốn nhận đang nạp trong trình phát thì cũng qua Playback - lưu chỗ của hồ sơ đang dùng ở đó trước, rồi theo sang hồ sơ vừa chuyển tới. */
    fun move(context: Context, id: String, record: String, to: String): Change {
        val move = { Store.moveRecord(id, record, to) }
        return change(context, id, if (Playback.bookId == to) switching(to, move) else switching(id, move), first = to)
    }

    fun delete(context: Context, id: String, record: String): Change =
        change(context, id, switching(id) { Store.deleteRecord(id, record) })
}
