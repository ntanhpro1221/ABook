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
    /** Loa / TV ĐIỆN THOẠI tự thấy (PhoneCast, 01-10): điện thoại phục vụ audio sách của nó, không cần máy tính. */
    const val DLNA = "dlna:"
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
        val direct = runCatching { PhoneCast.players.view() }.getOrDefault(JSONArray())
        // Cùng một thiết bị cả máy tính lẫn điện thoại đều thấy (mã theo UDN trùng nhau): một mục thôi - mục đang có sách,
        // không thì mục của điện thoại (phát được cả khi máy tính tắt). Đường phát thật chọn lúc bấm (`command`).
        val busy = { entry: JSONObject -> entry.optJSONObject("state")?.optString("bookId").orEmpty().isNotEmpty() }
        val chosen = LinkedHashMap<String, Pair<String, JSONObject>>()
        for (index in 0 until direct.length()) direct.optJSONObject(index)?.let { chosen[it.optString("id")] = DLNA to it }
        for (index in 0 until cast.length()) {
            val renderer = cast.optJSONObject(index) ?: continue
            val mine = chosen[renderer.optString("id")]
            if (mine == null || busy(renderer) && !busy(mine.second)) chosen[renderer.optString("id")] = CAST to renderer
        }
        for ((id, pick) in chosen) {
            val (prefix, renderer) = pick
            val book = renderer.optJSONObject("state")?.optString("bookId").orEmpty()
            out.put(renderer.put("device", prefix + id).put("via", "cast").put("localBookId", book).put("known", book.isNotEmpty()))
        }
        return out
    }

    /** Loa / TV điện thoại tự thấy: phát sách đã có trên điện thoại; sách nghe thẳng thì nhờ máy tính (nếu nó thấy thiết bị). */
    private fun direct(context: Context, id: String, command: JSONObject): JSONObject {
        if (command.optString("action") == "load" && PhoneCast.book(command.optString("bookId")) == null) {
            if (!SyncLink.paired(context)) throw IllegalStateException("Sách này chưa tải về điện thoại - tải về rồi phát lên loa, TV")
            return command(context, CAST + id, command)
        }
        return try {
            PhoneCast.players.send(id, command)
        } catch (error: Dlna.Failure) {
            throw IllegalStateException(error.message)
        }
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
        if (device.startsWith(DLNA)) return direct(context, device.removePrefix(DLNA), command)
        val cast = device.startsWith(CAST)
        // Sách chỉ có trên điện thoại (mở file .abook, sách của thiết bị ghép) mà điện thoại cũng thấy thiết bị: phát thẳng.
        if (cast && command.optString("action") == "load" && PhoneCast.players.owns(device.removePrefix(CAST))) {
            val manifest = Store.playableManifest(command.optString("bookId"))
            val computers = manifest != null && manifest.optString("source").isEmpty() && !manifest.has("package")
            if (!computers && PhoneCast.book(command.optString("bookId")) != null) return direct(context, device.removePrefix(CAST), command)
        }
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
