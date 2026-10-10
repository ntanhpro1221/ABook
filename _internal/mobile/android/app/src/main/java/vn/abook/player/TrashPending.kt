package vn.abook.player

import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * Chỗ chờ trước khi xoá hẳn: "Xoá khỏi điện thoại" được "Hoàn tác" trong [UNDO_SECONDS] giây (cùng tính năng máy tính,
 * abook/webui/trash_pending.py - hằng số và tên thư mục khớp nhau).
 *
 * Xoá = đổi tên (`renameTo`, cùng filesDir nên tức thì, không chép byte nào) cả thư mục sách sang
 * `<gốc thư viện>/.trash-pending/<mã>/<tên>` kèm `meta.json` (đường gốc, tên, lúc xoá). Thư viện thôi thấy cuốn ngay vì nó chỉ
 * quét `books/`; "Hoàn tác" là đổi tên ngược lại. Điện thoại KHÔNG có Thùng rác nên hết hạn (và lúc app mở) là XOÁ HẲN - đúng
 * hành vi trước đây, chỉ trễ [UNDO_SECONDS] giây.
 *
 * Luật giữ cho chỗ này an toàn:
 * - Dọn không được (file khoá, hết quyền) thì để nguyên chỗ chờ, lần sau dọn tiếp; không bao giờ văng ra ngoài.
 * - Dữ liệu đi theo sách mà nằm ngoài thư mục sách (sổ `prints.json`) chỉ bị dọn lúc xoá hẳn ([purge] gọi `onPurge`), không lúc
 *   đưa vào chỗ chờ - nên Hoàn tác là nguyên vẹn. Mọi thứ trong thư mục sách (lớp sửa, bìa, audio...) đi cùng thư mục.
 * - Xoá hẳn bỏ `meta.json` TRƯỚC rồi mới xoá thư mục: dọn dở giữa chừng thì không còn "Hoàn tác" ra một cuốn thiếu file, và lần
 *   dọn sau tiếp tục.
 */
class TrashPending(private val root: File, private val clock: () -> Long = System::currentTimeMillis) {
    /** Mã này không còn trong chỗ chờ (quá hạn đã xoá hẳn, đã hoàn tác rồi, hay mã lạ). */
    class NotPending(message: String) : Exception(message)

    /** Đường gốc đã có thư mục cùng tên - không đè lên được (cuốn vẫn nằm chờ). */
    class Occupied(message: String) : Exception(message)

    private val base get() = File(root, FOLDER)

    /**
     * Đưa thư mục sách `dir` vào chỗ chờ, trả mã hoàn tác; null khi đổi tên không được (thư mục còn nguyên chỗ cũ - nơi gọi
     * quyết định xoá thẳng hay báo lỗi).
     */
    @Synchronized
    fun hold(dir: File, id: String): String? {
        val token = UUID.randomUUID().toString().replace("-", "")
        val folder = File(base, token)
        if (!folder.mkdirs()) return null
        val meta = JSONObject().put("original", dir.absolutePath).put("name", dir.name).put("id", id).put("deletedAt", clock())
        try {
            File(folder, META).writeBytes(meta.toString().toByteArray(Charsets.UTF_8))
            if (dir.renameTo(File(folder, dir.name))) return token
        } catch (_: Exception) {
        }
        folder.deleteRecursively()
        tidyBase()
        return null
    }

    /** Hoàn tác: thư mục về đúng đường gốc. Trả meta. [NotPending] khi mã lạ / hết hạn, [Occupied] khi chỗ cũ đã bị chiếm. */
    @Synchronized
    fun restore(token: String): JSONObject {
        if (!TOKEN.matches(token)) throw NotPending("Cuốn này không còn để hoàn tác (đã xoá hẳn khỏi điện thoại).")
        val folder = File(base, token)
        val meta = meta(folder) ?: throw NotPending("Cuốn này không còn để hoàn tác (đã xoá hẳn khỏi điện thoại).")
        val item = File(folder, meta.getString("name"))
        val original = File(meta.getString("original"))
        if (!item.isDirectory) throw NotPending("Cuốn này không còn để hoàn tác (đã xoá hẳn khỏi điện thoại).")
        if (original.exists()) throw Occupied("Đã có một cuốn cùng mã ở chỗ cũ (có thể vừa được tải lại), nên chưa hoàn tác được.")
        original.parentFile?.mkdirs()
        if (!item.renameTo(original)) throw java.io.IOException("Chưa đưa cuốn về chỗ cũ được.")
        folder.deleteRecursively()
        tidyBase()
        return meta
    }

    /**
     * Xoá hẳn những mã đã quá [UNDO_SECONDS] (`everything`: mọi mã - lúc app mở, khi giao diện cũ với nút "Hoàn tác" đã mất).
     * `onPurge(meta)` chạy trước khi xoá thư mục (dọn dữ liệu đi theo sách). Trả số mã còn lại - dọn không được thì còn, lần sau
     * thử tiếp; không bao giờ văng.
     */
    @Synchronized
    fun sweep(everything: Boolean = false, onPurge: (JSONObject) -> Unit = {}): Int {
        var left = 0
        val folders = base.listFiles { entry -> entry.isDirectory && TOKEN.matches(entry.name) }?.sortedBy { it.name } ?: return 0
        for (folder in folders) {
            val meta = meta(folder)
            // Không có meta = dọn dở lần trước (đã bỏ meta, chưa xoá hết thư mục): xoá nốt.
            if (meta != null && !everything && clock() - meta.optLong("deletedAt") < UNDO_SECONDS * 1000L) {
                left++
                continue
            }
            if (!purge(folder, meta, onPurge)) left++
        }
        tidyBase()
        return left
    }

    private fun purge(folder: File, meta: JSONObject?, onPurge: (JSONObject) -> Unit): Boolean = try {
        if (meta != null) {
            onPurge(meta)
            if (!File(folder, META).delete()) throw java.io.IOException("meta")
        }
        folder.deleteRecursively()
    } catch (_: Exception) {
        false
    }

    private fun meta(folder: File): JSONObject? {
        val file = File(folder, META)
        return runCatching { JSONObject(file.readText(Charsets.UTF_8)) }.getOrNull()?.takeIf { it.has("name") && it.has("original") }
    }

    private fun tidyBase() {
        base.listFiles()?.let { if (it.isEmpty()) base.delete() }
    }

    companion object {
        const val FOLDER = ".trash-pending"
        const val META = "meta.json"
        /** Khớp `trash_pending.UNDO_SECONDS` của máy tính và `UNDO_SECONDS` của trashUndo.ts. */
        const val UNDO_SECONDS = 30
        private val TOKEN = Regex("[0-9a-f]{32}")
    }
}
