package vn.abook.player

import android.content.Context
import android.content.SharedPreferences
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import javax.net.ssl.HttpsURLConnection

/**
 * Đường tới máy tính đã ghép (địa chỉ, cổng, mã thiết bị, vân tay chứng chỉ TLS trong SharedPreferences "sync") - dùng chung
 * cho thư viện (LibraryPlugin: tải sách, đồng bộ chỗ nghe) và điều khiển từ xa (Remote). Mọi đường là HTTPS với chứng chỉ đã
 * ghim lúc ghép ([Pin]); chứng chỉ đổi thì lỗi [Pin.CHANGED], không rơi về HTTP.
 */
object SyncLink {
    fun prefs(context: Context): SharedPreferences = context.getSharedPreferences("sync", Context.MODE_PRIVATE)

    fun paired(context: Context): Boolean = !prefs(context).getString("token", "").isNullOrBlank()

    fun token(context: Context): String = prefs(context).getString("token", "") ?: ""

    /**
     * Các đường tới máy tính chính: LAN "host:port" (địa chỉ đã ghép qua Wi-Fi, cộng địa chỉ LAN máy tính báo lúc ghép -
     * `lan`, `lanPort`) và địa chỉ Bluetooth (ghép qua Bluetooth: "bt:<địa chỉ>", hay `bt` máy tính báo lúc ghép Wi-Fi).
     */
    fun routes(prefs: SharedPreferences): Pair<List<String>, String?> {
        val host = prefs.getString("host", "") ?: ""
        val lan = mutableListOf<String>()
        if (host.isNotBlank() && !host.startsWith("bt:")) lan += "$host:${prefs.getInt("port", 47630)}"
        val lanPort = prefs.getInt("lanPort", 0).takeIf { it > 0 } ?: 47630
        runCatching { JSONArray(prefs.getString("lan", "[]") ?: "[]") }.getOrNull()?.let { array ->
            for (index in 0 until array.length()) array.optString(index).takeIf { it.isNotBlank() }?.let { lan += "$it:$lanPort" }
        }
        val bluetooth = if (host.startsWith("bt:")) host.removePrefix("bt:") else prefs.getString("bt", "")?.takeIf { it.isNotBlank() }
        return lan.distinct() to bluetooth
    }

    /** Lưu các đường máy tính báo trong lời đáp ghép (sync.py `routes`) - để dùng Wi-Fi khi được, Bluetooth khi không. */
    fun saveRoutes(editor: SharedPreferences.Editor, reply: JSONObject): SharedPreferences.Editor {
        val routes = reply.optJSONObject("routes") ?: return editor
        return editor.putString("lan", (routes.optJSONArray("lan") ?: JSONArray()).toString())
            .putInt("lanPort", routes.optInt("port", 0)).putString("bt", routes.optString("bluetooth"))
    }

    /**
     * Máy tính báo lại các đường của nó mỗi lần điện thoại liệt kê thư viện (sync.py `/sync/v1/library`): địa chỉ có sau
     * lúc ghép (cài Tailscale/ZeroTier sau khi ghép) tới được điện thoại trước khi nó ra khỏi nhà. Trước đây đường chỉ lưu
     * lúc ghép.
     */
    fun refreshRoutes(context: Context, reply: JSONObject) {
        val prefs = prefs(context)
        val (lan, port, bluetooth) = refreshed(reply, prefs.getString("bt", "") ?: "") ?: return
        prefs.edit().putString("lan", lan).putInt("lanPort", port).putString("bt", bluetooth).apply()
    }

    /**
     * Phần thuần của refreshRoutes: (địa chỉ LAN dạng JSON, cổng, Bluetooth) hay null khi lời đáp không mang đường (máy
     * tính bản cũ). Máy tính đang tắt Bluetooth thì GIỮ địa chỉ Bluetooth đã biết - lúc cần nó nhất là lúc không có Wi-Fi
     * để hỏi lại.
     */
    internal fun refreshed(reply: JSONObject, knownBluetooth: String): Triple<String, Int, String>? {
        val routes = reply.optJSONObject("routes") ?: return null
        val bluetooth = routes.optString("bluetooth").takeIf { it.isNotBlank() } ?: knownBluetooth
        return Triple((routes.optJSONArray("lan") ?: JSONArray()).toString(), routes.optInt("port", 0), bluetooth)
    }

    /** Gốc https tới máy tính chính theo đường đang thông (Route - không bao giờ chặn luồng gọi). */
    fun base(context: Context): String {
        Pin.install(context)
        val prefs = prefs(context)
        val (lan, bluetooth) = routes(prefs)
        val choice = Route.pick(lan, bluetooth)
        choice.lan?.let { return "https://$it" }
        // Bluetooth: "bt:<địa chỉ>" - đi qua đường hầm (BluetoothLink), cùng giao thức.
        choice.bluetooth?.let { return BluetoothLink.base(context, it) }
        return "https://${prefs.getString("host", "")}:${prefs.getInt("port", 47630)}"
    }

    /**
     * Máy giữ một cuốn: máy tính chính, hay thiết bị đã ghép (Peers) nếu gói của cuốn ghi `source` - kèm mã sách BÊN ẤY
     * (`remoteId`; sách của máy tính chính dùng đúng mã của nó).
     */
    fun linkFor(context: Context, bookId: String): Pair<Peers.Link, String> {
        Pin.install(context)
        val manifest = Store.playableManifest(bookId)
        val source = manifest?.optString("source").orEmpty()
        if (source.isNotEmpty()) {
            val link = Peers.link(context, source) ?: throw IllegalStateException("Thiết bị giữ cuốn này đã thôi ghép")
            return link to manifest!!.optString("remoteId", bookId)
        }
        return Peers.Link(base(context), token(context)) to bookId
    }

    /** Mã thiết bị cho một địa chỉ (trình phát nghe thẳng): thiết bị ghép có địa chỉ ấy, không thì máy tính chính. */
    fun tokenFor(context: Context, uri: android.net.Uri): String = Peers.tokenFor(context, uri) ?: token(context)

    fun request(
        context: Context,
        method: String,
        path: String,
        body: JSONObject? = null,
        auth: Boolean = true,
        root: String = base(context),
        readTimeoutMs: Int = 20_000,
        connectTimeoutMs: Int = 5000,
        token: String? = null,
        upload: File? = null,
    ): String {
        try {
            return send(context, method, path, body, auth, root, readTimeoutMs, connectTimeoutMs, token, upload = upload)
        } catch (error: IOException) {
            // Nối LAN của máy tính chính hỏng (ra khỏi Wi-Fi nhà): đánh dấu hỏng và thử lại ngay một lần qua Bluetooth.
            val (lan, bluetooth) = routes(prefs(context))
            val target = lan.firstOrNull { root == "https://$it" }
            if (target == null || bluetooth == null) throw error
            Route.markDown(target)
            return send(context, method, path, body, auth, BluetoothLink.base(context, bluetooth), readTimeoutMs,
                connectTimeoutMs, token, upload = upload)
        }
    }

    /** Phần thuần (test được) của [refuseSelf]: `host` là vòng lặp, "localhost" hay một địa chỉ của chính điện thoại, kèm đúng cổng đồng bộ của nó. */
    internal fun isOwnAddress(host: String, port: Int, ownPort: Int, own: Collection<String>): Boolean {
        val clean = host.trim().lowercase()
        return port == ownPort && (clean in own || clean.startsWith("127.") || clean == "localhost" || clean == "::1")
    }

    /** Ghép bằng địa chỉ gõ tay (không phải Bluetooth) với chính điện thoại này nhân đôi cả thư viện: từ chối trước khi gửi mã, như máy tính (remote_books.py `Computers.pair`). */
    fun refuseSelf(host: String, port: Int) {
        if (isOwnAddress(host, port, LibraryServer.PORT, LibraryServer.addresses())) {
            throw IllegalArgumentException("Đây là địa chỉ của chính máy này - nhập địa chỉ máy kia")
        }
    }

    /**
     * Ghép với một máy (`root` = "https://host:port", máy tính hay điện thoại chia sẻ): trả lời đáp và VÂN TAY chứng chỉ máy ấy.
     * Lần duy nhất nhận chứng chỉ chưa biết ([Pin.firstUse]); vân tay thấy được phải trùng vân tay máy kia tự báo trong lời đáp,
     * rồi người gọi ghi lại để từ đó chỉ nhận đúng chứng chỉ này.
     */
    fun pair(context: Context, root: String, body: JSONObject): Pair<JSONObject, String> {
        Pin.install(context)
        val seen = arrayOfNulls<String>(1)
        val text = send(context, "POST", "/sync/v1/pair", body, false, root, 20_000, 5000, null, seen)
        val reply = JSONObject(text)
        val fingerprint = seen[0].orEmpty()
        if (fingerprint.isEmpty() || !reply.optString("fingerprint").equals(fingerprint, ignoreCase = true)) {
            throw IllegalStateException("Máy kia trả lời không đáng tin (chứng chỉ không khớp vân tay nó báo) - chưa ghép, thử lại; vẫn lỗi thì kiểm tra mạng")
        }
        return reply to fingerprint
    }

    private fun send(
        context: Context,
        method: String,
        path: String,
        body: JSONObject?,
        auth: Boolean,
        root: String,
        readTimeoutMs: Int,
        connectTimeoutMs: Int,
        token: String?,
        firstUse: Array<String?>? = null,
        upload: File? = null,
    ): String {
        Pin.install(context)
        return Pin.guard {
            exchange(context, method, path, body, auth, root, readTimeoutMs, connectTimeoutMs, token, firstUse, upload)
        }
    }

    private fun exchange(
        context: Context,
        method: String,
        path: String,
        body: JSONObject?,
        auth: Boolean,
        root: String,
        readTimeoutMs: Int,
        connectTimeoutMs: Int,
        token: String?,
        firstUse: Array<String?>?,
        upload: File? = null,
    ): String {
        val connection = URL(root + path).openConnection() as HttpURLConnection
        // `firstUse` != null: yêu cầu ghép - nhận chứng chỉ lạ một lần và đọc vân tay ra mảng này.
        if (firstUse != null && connection is HttpsURLConnection) Pin.firstUse(connection)
        connection.requestMethod = method
        connection.connectTimeout = connectTimeoutMs
        connection.readTimeout = readTimeoutMs
        if (token != null) connection.setRequestProperty("Authorization", "Bearer $token")
        else if (auth) connection.setRequestProperty("Authorization", "Bearer ${prefs(context).getString("token", "")}")
        if (upload != null) {
            // Gói nhị phân lớn (phần sửa + bài nhạc ghim): đẩy thẳng từ file, không giữ cả gói trong bộ nhớ.
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/zip")
            connection.setFixedLengthStreamingMode(upload.length())
            upload.inputStream().use { input -> connection.outputStream.use { input.copyTo(it, 256 * 1024) } }
        } else if (body != null) {
            connection.doOutput = true
            connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
            connection.outputStream.use { it.write(body.toString().toByteArray()) }
        }
        val code = connection.responseCode
        val text = (if (code < 400) connection.inputStream else connection.errorStream)?.bufferedReader()?.use { it.readText() } ?: ""
        if (firstUse != null && connection is HttpsURLConnection) firstUse[0] = Pin.peerFingerprint(connection)
        connection.disconnect()
        if (code >= 400) {
            val message = runCatching { JSONObject(text).optString("error") }.getOrNull()
            throw IllegalStateException(message?.ifBlank { null } ?: "Máy tính trả lỗi $code")
        }
        return text
    }
}
