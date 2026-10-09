package vn.abook.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import java.util.concurrent.ScheduledFuture
import java.util.concurrent.TimeUnit
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

/**
 * Gửi phần sửa của người nghe về máy tính (docs/EDITING.md, P2b; máy tính nhận ở abook/webui/edits_inbox.py).
 *
 * Cuốn của máy tính (đã tải hay nghe thẳng chưa tải; máy tính chính hay một máy tính khác đã ghép - [Store.editDestination]) sửa được
 * ngay trên điện thoại - lớp sửa `edits.json` như cuốn mở từ file, cạnh gói sách (book.json hay stream.json) - nhưng sách là của
 * máy tính: sửa chỉ có nghĩa lâu dài khi về tới đó. Cuốn của điện thoại khác thì không có chỗ gửi: sửa ở lại máy này. Gói gửi là một file zip nhỏ (`edits.json`, `edits/cover.jpg`
 * khi đổi bìa, `music/<sha1>.<đuôi>` các bài nhạc ghim) qua đường TLS đã ghim (`POST /sync/v1/books/<mã>/edits`). Máy tính áp liền
 * sửa "áp ngay"; ý muốn chờ Studio thành yêu cầu nếu thiết bị này được điều khiển sản xuất, không thì nằm trong hộp thư chờ chủ máy
 * duyệt (không bao giờ tự áp). Máy tính nhận xong thì điện thoại gỡ khỏi lớp sửa của mình đúng những gì đã gửi
 * ([BookEdits.subtract]) rồi tải lại sách từ máy tính - bản mới của máy tính đã mang các sửa ấy.
 *
 * Gửi xong, cuốn đã tải thì tải lại từ máy ấy, cuốn nghe thẳng thì chỉ lấy lại gói sách (không tải cả cuốn).
 *
 * Trạng thái hiện cho người dùng (`editsSync` trong JSON sách): số thay đổi CHƯA gửi (`pending`) và kết quả lần gửi gần nhất
 * (`last`: đã gửi lúc nào, bao nhiêu áp, bao nhiêu chờ duyệt, xung đột, hay lỗi). Gửi tự động sau mỗi lần sửa (chờ vài giây cho
 * người dùng sửa xong) và mỗi lần mở thư viện khi tới được máy tính; không tới được thì thử lại, rồi để lần sau.
 */
object EditsSync {
    const val STATE_FILE = "sync_edits.json"
    const val MAX_PACKAGE_BYTES = 150L * 1024 * 1024
    private const val DEBOUNCE_MS = 4_000L
    private val RETRY_MS = listOf(60_000L, 300_000L)

    /** Lần gửi gần nhất đã thành công, thất bại, hay chưa gửi bao giờ. */
    const val SENT = "sent"
    const val FAILED = "error"

    private val executor = Executors.newSingleThreadScheduledExecutor { runnable -> Thread(runnable, "edits-sync").apply { isDaemon = true } }
    private val scheduled = ConcurrentHashMap<String, ScheduledFuture<*>>()
    private val attempts = ConcurrentHashMap<String, Int>()

    /** Cầu tới plugin: tải lại sách từ máy tính sau khi gửi xong, và báo giao diện làm mới (đặt trong LibraryPlugin.load). */
    @Volatile var refresh: ((String) -> Unit)? = null
    @Volatile var changed: ((String) -> Unit)? = null

    /** Đồng hồ (giây) của dấu giờ trạng thái; test đặt số cố định. */
    @Volatile var clock: () -> Long = { System.currentTimeMillis() / 1000 }

    /** Ảnh chụp lớp sửa lúc đóng gói: dùng cả để gỡ đúng những gì đã gửi. */
    class Snapshot(val edits: JSONObject, val cover: ByteArray?)

    // ---- trạng thái -------------------------------------------------------------------------------------------------

    private fun stateFile(dir: File) = File(dir, STATE_FILE)

    private fun lastState(dir: File): JSONObject? =
        stateFile(dir).takeIf { it.isFile }?.let { runCatching { JSONObject(it.readText()) }.getOrNull() }

    /**
     * `editsSync` của một cuốn: {pending: số thay đổi chưa gửi, last: kết quả lần gửi gần nhất hay null}. `pending` đếm lớp sửa
     * hiện có (`edits` = BookEdits.count): gửi xong là gỡ, nên số còn lại chính là phần chưa tới máy tính.
     */
    fun view(dir: File, pending: Int): JSONObject = JSONObject().put("pending", pending).put("last", lastState(dir) ?: JSONObject.NULL)

    private fun record(dir: File, state: JSONObject) {
        Store.writeAtomic(stateFile(dir), state.toString())
    }

    // ---- đóng gói -----------------------------------------------------------------------------------------------------

    /** Lớp sửa hiện có của cuốn, kèm byte bìa mới; null khi không còn gì để gửi. Thiếu file bìa / file nhạc đã chọn: lỗi nói rõ. */
    fun snapshot(dir: File): Snapshot? = BookEdits.locked {
        val edits = BookEdits.load(dir)
        if (BookEdits.isEmpty(edits)) return@locked null
        var cover: ByteArray? = null
        if (edits.opt("cover") is JSONObject) {
            val file = File(dir, BookEdits.EDITS_COVER)
            if (!file.isFile) throw IllegalStateException("Thiếu ảnh bìa mới trong sách - hãy đặt lại ảnh bìa rồi gửi")
            cover = file.readBytes()
        }
        for (name in BookEdits.pinnedFiles(edits)) {
            if (!File(dir, name).isFile) throw IllegalStateException("Thiếu file nhạc đã chọn trong sách - hãy chọn lại bài ấy rồi gửi")
        }
        Snapshot(BookEdits.deepCopy(edits) as JSONObject, cover)
    }

    /** Ghi gói zip của `snapshot` ra `target` (edits.json, bìa, bài nhạc ghim) - đúng tên mục mà máy tính nhận (edits_inbox.py). */
    fun writePackage(dir: File, snapshot: Snapshot, target: File) {
        target.parentFile?.mkdirs()
        ZipOutputStream(target.outputStream().buffered()).use { zip ->
            zip.putNextEntry(ZipEntry(BookEdits.EDITS_FILE))
            zip.write(BookEdits.dump(snapshot.edits))
            zip.closeEntry()
            snapshot.cover?.let {
                zip.putNextEntry(ZipEntry(BookEdits.EDITS_COVER))
                zip.write(it)
                zip.closeEntry()
            }
            for (name in BookEdits.pinnedFiles(snapshot.edits)) {
                zip.putNextEntry(ZipEntry(name))
                File(dir, name).inputStream().use { it.copyTo(zip, 256 * 1024) }
                zip.closeEntry()
            }
        }
        if (target.length() > MAX_PACKAGE_BYTES) {
            target.delete()
            throw IllegalStateException("Phần sửa quá lớn để gửi một lần - bớt bài nhạc đã chọn rồi gửi lại")
        }
    }

    // ---- gửi --------------------------------------------------------------------------------------------------------

    /**
     * Gửi phần sửa của cuốn `id` (đã tải từ máy tính chính) qua `send` (nhận file gói, trả JSON lời đáp; ném lỗi nếu máy tính
     * không nhận) - gọi trên luồng nền. Nhận xong: gỡ phần đã gửi khỏi lớp sửa, ghi trạng thái "đã gửi", rồi nhờ plugin tải lại
     * sách. Lỗi: ghi trạng thái "lỗi" (lớp sửa giữ nguyên, lần sau gửi lại) rồi ném tiếp. Trả `editsSync` mới. Không có gì để gửi:
     * trả `editsSync` hiện tại.
     */
    @Synchronized
    fun push(id: String, send: (File) -> String): JSONObject {
        if (Store.editDestination(id) == null) throw IllegalStateException("Cuốn này không lấy từ máy tính nên không có chỗ gửi về")
        val dir = Store.bookDir(id)
        val snapshot = try {
            snapshot(dir)
        } catch (error: IllegalStateException) {
            throw failure(dir, id, error.message.orEmpty(), error)
        }
        if (snapshot == null) return view(dir, 0)
        val file = File(Store.root, "edits_out_$id.zip")
        try {
            try {
                writePackage(dir, snapshot, file)
            } catch (error: IllegalStateException) {
                throw failure(dir, id, error.message.orEmpty(), error)
            }
            val reply = try {
                JSONObject(send(file))
            } catch (error: IOException) {
                throw failure(dir, id, "Chưa tới được máy tính - phần sửa vẫn nằm trên máy này, sẽ gửi lại khi có kết nối", error)
            } catch (error: IllegalStateException) {
                throw failure(dir, id, error.message ?: "Máy tính không nhận phần sửa", error)
            } catch (error: JSONException) {
                throw failure(dir, id, "Máy tính trả lời không hiểu được", error)
            }
            refresh?.let { runCatching { it(id) } } // sách mới của máy tính đã mang sửa: tải lại TRƯỚC khi gỡ lớp phủ để không chớp bản cũ
            val rest = BookEdits.subtract(dir, snapshot.edits, snapshot.cover)
            record(dir, JSONObject().put("state", SENT).put("at", clock())
                .put("applied", reply.optInt("applied")).put("skipped", reply.optInt("skipped"))
                .put("requests", reply.optInt("requests")).put("waiting", reply.optInt("waiting"))
                .put("skippedWishes", reply.optInt("skippedWishes"))
                .put("conflicts", labels(reply.optJSONArray("conflicts"))))
            attempts.remove(id)
            changed?.invoke(id)
            return view(dir, rest)
        } finally {
            file.delete()
        }
    }

    /** Ghi lỗi vào trạng thái (lớp sửa giữ nguyên, lần sau gửi lại) và trả ngoại lệ để người gọi ném: mất mạng là [IOException]. */
    private fun failure(dir: File, id: String, message: String, cause: Exception): Exception {
        record(dir, JSONObject().put("state", FAILED).put("at", clock()).put("error", message))
        changed?.invoke(id)
        return if (cause is IOException) IOException(message, cause) else IllegalStateException(message, cause)
    }

    private fun labels(array: JSONArray?): JSONArray {
        val out = JSONArray()
        if (array != null) for (index in 0 until array.length()) array.optJSONObject(index)?.optString("label")?.takeIf { it.isNotEmpty() }?.let(out::put)
        return out
    }

    /** Gửi thật qua đường TLS đã ghim tới máy giữ sách - máy tính chính, hay máy tính khác đã ghép (không bao giờ gọi trên luồng giao diện). */
    fun pushNow(context: Context, id: String): JSONObject = push(id) { file ->
        val (peer, remote) = Store.editDestination(id) ?: throw IllegalStateException("Cuốn này không lấy từ máy tính nên không có chỗ gửi về")
        if (peer == null) SyncLink.request(context, "POST", "/sync/v1/books/$remote/edits", upload = file, readTimeoutMs = 120_000)
        else Peers.request(context, peer, "POST", "/sync/v1/books/$remote/edits", readTimeoutMs = 120_000, upload = file)
    }

    /** Có đường tới máy giữ sách `id` không (chưa ghép / thôi ghép thì không gửi, không hẹn). */
    private fun reachable(context: Context, id: String): Boolean {
        val (peer, _) = Store.editDestination(id) ?: return false
        return if (peer == null) SyncLink.paired(context) else Peers.link(context, peer) != null
    }

    // ---- gửi tự động --------------------------------------------------------------------------------------------------

    /**
     * Hẹn gửi cuốn `id` sau vài giây (mỗi lần sửa lại dời hẹn - người dùng đang sửa dở thì chưa gửi). Không có gì để gửi, chưa ghép
     * với máy tính, hay cuốn không thuộc máy tính: không làm gì. Gửi hỏng thì thử lại sau 1 phút, 5 phút, rồi để lần sau.
     */
    fun schedule(context: Context, id: String, delayMs: Long = DEBOUNCE_MS) {
        if (!reachable(context, id)) return
        scheduled.remove(id)?.cancel(false)
        scheduled[id] = executor.schedule({
            scheduled.remove(id)
            if (BookEdits.isEmpty(BookEdits.load(Store.bookDir(id)))) return@schedule
            val ok = runCatching { pushNow(context, id) }.isSuccess
            if (!ok) {
                val tried = attempts.merge(id, 1, Int::plus) ?: 1
                RETRY_MS.getOrNull(tried - 1)?.let { schedule(context, id, it) }
            }
        }, delayMs, TimeUnit.MILLISECONDS)
    }

    /**
     * Khi thư viện vừa nói chuyện được với máy tính: gửi nốt phần sửa còn tồn của mọi cuốn của máy tính, và hỏi lại những cuốn đang
     * có việc chờ chủ máy duyệt xem còn bao nhiêu (chủ máy đã quyết bớt thì dòng "đang chờ duyệt" cũng bớt theo).
     */
    fun scheduleAllPending(context: Context) {
        for (id in Store.bookIds()) {
            if (!reachable(context, id)) continue
            val dir = Store.bookDir(id)
            if (!BookEdits.isEmpty(BookEdits.load(dir))) schedule(context, id, 500)
            if ((lastState(dir)?.optInt("waiting") ?: 0) <= 0) continue
            val (peer, remote) = Store.editDestination(id) ?: continue
            executor.execute {
                runCatching {
                    refreshWaiting(id) {
                        if (peer == null) SyncLink.request(context, "GET", "/sync/v1/books/$remote/edits", readTimeoutMs = 10_000, connectTimeoutMs = 2_000)
                        else Peers.request(context, peer, "GET", "/sync/v1/books/$remote/edits", readTimeoutMs = 10_000, connectTimeoutMs = 2_000)
                    }
                }
            }
        }
    }

    /**
     * Số việc của điện thoại này còn chờ chủ máy duyệt (`fetch`: lời đáp của `GET /sync/v1/books/<mã>/edits`, {waiting}); ghi lại vào
     * trạng thái lần gửi gần nhất và báo giao diện nếu khác. Không hỏi được thì thôi - giữ số cũ.
     */
    @Synchronized
    fun refreshWaiting(id: String, fetch: () -> String) {
        val dir = Store.bookDir(id)
        val last = lastState(dir) ?: return
        if (last.optString("state") != SENT) return
        val waiting = JSONObject(fetch()).optInt("waiting", -1)
        if (waiting < 0 || waiting == last.optInt("waiting")) return
        record(dir, last.put("waiting", waiting))
        changed?.invoke(id)
    }
}
