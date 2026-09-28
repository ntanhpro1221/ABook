package vn.ebookreader.player

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.util.concurrent.Callable
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Trình phát trên máy khác - mạng trạm bước 4 (chủ sách 27-09: điều khiển hai chiều, mọi cặp máy). Máy tính chính
 * (SyncLink) và mọi thiết bị ghép (Peers: điện thoại khác, máy tính khác) trả trình phát của chúng ở GET /sync/v1/player -
 * cùng hình dạng thân báo điện thoại gửi máy tính (Remote.kt): `state`, `books`, `stream`, `acks`, `age`. Điện thoại xem
 * được "đang phát gì" ở đâu, gửi lệnh (POST), và nghe tiếp ngay tại điện thoại đúng chỗ ấy.
 *
 * Mã sách đi hai chiều qua đúng quy ước sẵn có: sách của máy tính chính mang nguyên mã máy tính (tải về hay nghe thẳng);
 * sách của thiết bị ghép mang mã cục bộ `p<key>_<mã bên ấy>` (Peers.localId) và `remoteId` trong gói.
 */
object RemotePlayers {
    const val MAIN = "main"
    private val pool = Executors.newCachedThreadPool()

    /** Trình phát của mọi máy đã ghép, hỏi song song; máy không trả lời trong ~2,5 giây thì bỏ qua lượt này. */
    fun all(context: Context): JSONArray {
        val targets = mutableListOf<String>()
        if (SyncLink.paired(context)) targets += MAIN
        targets += Peers.all(context).keys().asSequence().toList()
        val futures = targets.map { key -> key to pool.submit(Callable { fetch(context, key) }) }
        val out = JSONArray()
        for ((key, future) in futures) {
            val reply = runCatching { future.get(4, TimeUnit.SECONDS) }.getOrNull() ?: continue
            val state = reply.optJSONObject("state")
            val remoteBook = state?.optString("bookId").orEmpty()
            val local = if (remoteBook.isEmpty()) "" else if (key == MAIN) remoteBook else Peers.localId(key, remoteBook)
            out.put(reply.put("device", key)
                .put("localBookId", local)
                // Máy tính chính: mọi cuốn của nó nghe thẳng được; thiết bị ghép: cuốn có trong thư viện nó chia sẻ.
                .put("known", local.isNotEmpty()))
        }
        return out
    }

    private fun fetch(context: Context, key: String): JSONObject {
        val text = if (key == MAIN) {
            SyncLink.request(context, "GET", "/sync/v1/player", readTimeoutMs = 2500, connectTimeoutMs = 1500)
        } else {
            Peers.request(context, key, "GET", "/sync/v1/player", readTimeoutMs = 2500, connectTimeoutMs = 1500)
        }
        return JSONObject(text)
    }

    /** Gửi một lệnh; "load" mang mã cuốn CỦA ĐIỆN THOẠI NÀY, đổi sang mã của máy kia - máy kia chỉ phát được sách của nó. */
    fun command(context: Context, device: String, command: JSONObject): JSONObject {
        if (command.optString("action") == "load") {
            val local = command.optString("bookId")
            val manifest = Store.playableManifest(local)
            val source = manifest?.optString("source").orEmpty()
            val remote = when {
                device == MAIN && source.isEmpty() && manifest?.has("package") != true -> local
                device != MAIN && source == device -> manifest?.optString("remoteId").orEmpty()
                else -> ""
            }
            if (remote.isEmpty()) throw IllegalStateException("Máy kia không có cuốn này")
            command.put("bookId", remote)
        }
        val text = if (device == MAIN) {
            SyncLink.request(context, "POST", "/sync/v1/player", command, readTimeoutMs = 6000)
        } else {
            Peers.request(context, device, "POST", "/sync/v1/player", command, readTimeoutMs = 6000)
        }
        val reply = JSONObject(text)
        if (reply.has("ok") && !reply.optBoolean("ok")) {
            throw IllegalStateException(reply.optString("message").ifBlank { "Máy kia không làm được lệnh này" })
        }
        return reply
    }
}
