package vn.abook.player

import android.content.Context
import android.os.SystemClock
import org.json.JSONArray
import org.json.JSONObject
import org.json.JSONException
import java.io.File
import java.util.concurrent.Executors
import java.util.UUID

/**
 * Đẩy hồ sơ nghe đang dùng của một cuốn lên máy tính đã ghép (POST /sync/v1/books/<id>/state - webui/listening.py
 * merge_record) và nhận bản đã gộp của ĐÚNG hồ sơ ấy (Store.applySync). Dùng chung cho giao diện và
 * trình phát gốc (Playback): trước đây trình phát chỉ lưu chỗ nghe trên điện thoại, máy tính không bao giờ biết.
 *
 * Trình phát đẩy ngay khi dừng, còn đang phát thì tối đa mỗi phút một lần. Không có mạng thì im lặng - cuốn ấy vào [pending] và được đẩy
 * ngay khi nối lại được máy giữ sách ([flushPending]: mở Thư viện / Thiết bị, vòng điều khiển từ xa) chứ không chờ lần dừng sau (soát a68 lỗi 9:
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
        val saved = pending.add(bookId, Store.syncBody(bookId, only))
        send(context, saved)
    }

    private fun send(context: Context, saved: JSONObject) {
        val bookId = saved.getString("bookId")
        val record = saved.getString("recordId")
        // Sách của thiết bị ghép (Peers) đẩy về đúng thiết bị ấy; sách của máy tính chính cần máy tính đã ghép.
        val fromPeer = !Store.playableManifest(bookId)?.optString("source").isNullOrEmpty()
        if (!fromPeer && !SyncLink.paired(context)) return
        val (link, remote) = runCatching { SyncLink.linkFor(context, bookId) }.getOrNull() ?: return
        val reply = runCatching {
            JSONObject(SyncLink.request(context, "POST", "/sync/v1/books/$remote/state", saved.getJSONObject("body"),
                readTimeoutMs = 10_000, connectTimeoutMs = 3000, root = link.base, token = link.token))
        }.getOrNull() ?: return
        if (reply.has("record") && reply.optString("record") != record) return
        lastPushMs = SystemClock.elapsedRealtime()
        // Máy giữ sách đời cũ không trả mã hồ sơ: câu trả lời vẫn thuộc đúng hồ sơ vừa gửi.
        reply.put("record", record)
        localizeReply(bookId, remote, Store.playableManifest(bookId)?.optString("source").orEmpty(), reply)
        Store.applySync(bookId, reply)
        pending.ack(bookId, record, saved.getString("revision"))
    }

    /**
     * Lời đáp nói sách bằng mã của MÁY GIỮ SÁCH (`remote`: máy tính chính dùng đúng mã cục bộ, thiết bị ghép có mã cục bộ riêng
     * `p<thiết bị>_<mã bên ấy>`, Peers.localId). `Store.applySync` coi `book` là mã cục bộ - không dịch thì hồ sơ bị gỡ khỏi cuốn
     * `p<thiết bị>_sach` rồi gắn sang `sach` (cuốn khác, hay của thiết bị ghép khác cùng mã). Dịch về namespace của đúng máy giữ sách,
     * kể cả cuốn đích khi hồ sơ được chuyển sách; mã không dịch được thì coi như chưa chuyển (hồ sơ ở nguyên cuốn đang gửi).
     */
    internal fun localizeReply(bookId: String, remote: String, source: String, reply: JSONObject) {
        val replied = reply.optString("book")
        if (replied.isEmpty()) return
        val local = when {
            replied == remote -> bookId
            source.isEmpty() -> replied
            else -> runCatching { Peers.localId(source, replied) }.getOrDefault(bookId)
        }
        reply.put("book", local)
    }

    /** Vừa nói chuyện được với máy giữ sách: đẩy các cuốn có chỗ nghe chưa tới được nó (ở luồng nền của StateSync). */
    fun flushPending(context: Context) {
        if (pending.ids().isEmpty()) return
        io.execute {
            pending.entries().forEach { runCatching { send(context, it) } }
        }
    }

    /** Trình phát: `force` khi vừa dừng; đang phát thì bỏ qua nếu vừa đẩy chưa tới một phút. */
    fun pushSoon(context: Context, bookId: String, force: Boolean, only: String? = null) {
        if (!force && SystemClock.elapsedRealtime() - lastPushMs < WHILE_PLAYING_MS) return
        lastPushMs = SystemClock.elapsedRealtime()
        io.execute { runCatching { pushNow(context, bookId, only) } }
    }
}

/** Mỗi hồ sơ giữ một snapshot bền. ACK của lượt cũ không được gỡ revision vừa được ghi trong lúc gửi. */
class PendingPushes(private val file: File) {
    private fun read(): JSONArray {
        if (!file.isFile) return JSONArray()
        return try {
            JSONArray(file.readText())
        } catch (error: JSONException) {
            Store.preserveCorrupt(file)
            JSONArray()
        }
    }

    @Synchronized
    fun ids(): Set<String> {
        val array = read()
        return (0 until array.length()).map { array.getJSONObject(it).getString("bookId") }.toSet()
    }

    @Synchronized
    fun entries(): List<JSONObject> = read().let { array -> (0 until array.length()).mapNotNull { array.optJSONObject(it) } }

    @Synchronized
    fun add(bookId: String, body: JSONObject): JSONObject {
        val record = body.getString("record")
        val saved = JSONObject().put("bookId", bookId).put("recordId", record).put("revision", UUID.randomUUID().toString())
            .put("body", JSONObject(body.toString()))
        val kept = entries().filterNot { it.optString("bookId") == bookId && it.optString("recordId") == record }
        write(JSONArray(kept + saved))
        return saved
    }

    @Synchronized
    fun ack(bookId: String, recordId: String, revision: String) {
        val kept = entries().filterNot {
            it.optString("bookId") == bookId && it.optString("recordId") == recordId && it.optString("revision") == revision
        }
        write(JSONArray(kept))
    }

    private fun write(ids: JSONArray) {
        file.parentFile?.mkdirs()
        Store.writeAtomic(file, ids.toString())
    }
}

/** Chỗ nghe đáng tin để lưu và đồng bộ (soát a68 lỗi 2): không vượt độ dài chương quá [TOLERANCE_SECONDS] - độ dài trong gói lệch vài phần giây với file thật. Máy tính
 *  kiểm cùng luật khi nhận (webui/sync.py `trusted_state`). */
object PlacePolicy {
    const val TOLERANCE_SECONDS = 2.0

    /** `duration` <= 0: chưa biết độ dài, không xét. */
    fun fits(seconds: Double, duration: Double): Boolean = duration <= 0 || seconds <= duration + TOLERANCE_SECONDS
}
