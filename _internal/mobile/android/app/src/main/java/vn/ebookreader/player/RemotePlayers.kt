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
    /** Loa / TV máy tính chính thấy trong mạng nhà (webui/cast.py, 01-10): điều khiển QUA máy tính - máy tính phục vụ
     *  audio và giữ chỗ nghe, nên chỉ phát được sách của máy tính. Mã: "cast:<12 hex>". */
    const val CAST = "cast:"
    private val pool = Executors.newCachedThreadPool()

    /** Trình phát của mọi máy đã ghép, hỏi song song; máy không trả lời trong ~2,5 giây thì bỏ qua lượt này. */
    fun all(context: Context): JSONArray {
        val targets = mutableListOf<String>()
        if (SyncLink.paired(context)) targets += MAIN
        targets += Peers.all(context).keys().asSequence().toList()
        val futures = targets.map { key -> key to pool.submit(Callable { fetch(context, key) }) }
        val renderers = if (SyncLink.paired(context)) pool.submit(Callable { castRenderers(context) }) else null
        val out = JSONArray()
        for ((key, future) in futures) {
            val reply = runCatching { future.get(4, TimeUnit.SECONDS) }.getOrNull() ?: continue
            val state = reply.optJSONObject("state")
            val remoteBook = state?.optString("bookId").orEmpty()
            val local = if (remoteBook.isEmpty()) "" else if (key == MAIN) remoteBook else Peers.localId(key, remoteBook)
            // Máy tính (chính hay ghép): mọi cuốn của nó nghe thẳng được. Điện thoại ghép: chỉ cuốn nó đã tải (`books` -
            // thứ LibraryServer của nó phục vụ); cuốn nó đang nghe thẳng từ máy khác thì ở đây không nghe tiếp được.
            val served = reply.optJSONArray("books")
            val known = local.isNotEmpty() && (key == MAIN || reply.optString("kind") != "phone" ||
                (served != null && (0 until served.length()).any { served.optString(it) == remoteBook }))
            out.put(reply.put("device", key).put("localBookId", local).put("known", known))
        }
        // Máy tính chính bản cũ (trước khi có loa / TV) không có /sync/v1/cast: bỏ qua lặng lẽ.
        val cast = renderers?.let { runCatching { it.get(4, TimeUnit.SECONDS) }.getOrNull() } ?: JSONArray()
        for (index in 0 until cast.length()) {
            val renderer = cast.optJSONObject(index) ?: continue
            val book = renderer.optJSONObject("state")?.optString("bookId").orEmpty()
            out.put(renderer.put("device", CAST + renderer.optString("id")).put("via", "cast")
                .put("localBookId", book).put("known", book.isNotEmpty()))
        }
        return out
    }

    private fun castRenderers(context: Context): JSONArray =
        JSONObject(SyncLink.request(context, "GET", "/sync/v1/cast", readTimeoutMs = 2500, connectTimeoutMs = 1500))
            .optJSONArray("renderers") ?: JSONArray()

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
        val cast = device.startsWith(CAST)
        if (command.optString("action") == "load") {
            val local = command.optString("bookId")
            val manifest = Store.playableManifest(local)
            val source = manifest?.optString("source").orEmpty()
            val remote = when {
                (device == MAIN || cast) && source.isEmpty() && manifest?.has("package") != true -> local
                device != MAIN && !cast && source == device -> manifest?.optString("remoteId").orEmpty()
                else -> ""
            }
            if (remote.isEmpty()) {
                throw IllegalStateException(if (cast) "Loa, TV chỉ phát được sách của máy tính" else "Máy kia không có cuốn này")
            }
            command.put("bookId", remote)
        }
        val text = when {
            device == MAIN -> SyncLink.request(context, "POST", "/sync/v1/player", command, readTimeoutMs = 6000)
            // Đưa chương cho TV có thể mất vài giây (TV tải chương, đợi chạy rồi mới tua tới đúng chỗ).
            cast -> SyncLink.request(context, "POST", "/sync/v1/cast/" + device.removePrefix(CAST), command,
                readTimeoutMs = 20_000)
            else -> Peers.request(context, device, "POST", "/sync/v1/player", command, readTimeoutMs = 6000)
        }
        val reply = JSONObject(text)
        if (reply.has("ok") && !reply.optBoolean("ok")) {
            throw IllegalStateException(reply.optString("message").ifBlank { "Máy kia không làm được lệnh này" })
        }
        return reply
    }
}
