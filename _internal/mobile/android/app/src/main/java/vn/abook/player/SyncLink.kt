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

    /** Mã cố định của chính điện thoại này (16 chữ hex), gửi lúc ghép - như remote_books.py `Computers.own_id` của máy tính. Không nằm trong
     *  `prefs` (bỏ ghép máy tính chính xoá sạch nó). */
    @Synchronized
    fun selfId(context: Context): String {
        val store = context.getSharedPreferences("abook_self", Context.MODE_PRIVATE)
        store.getString("id", null)?.takeIf { Regex("[0-9a-f]{16}").matches(it) }?.let { return it }
        val fresh = java.util.UUID.randomUUID().toString().replace("-", "").take(16)
        store.edit().putString("id", fresh).commit()
        return fresh
    }

    /** Báo máy kia thu hồi mã của máy này ở đó (`POST /sync/v1/unpair`, sync.py) - lúc bỏ ghép; máy kia tắt thì thôi (chỉ thử một lần). */
    fun tellUnpaired(context: Context, root: String, token: String) {
        if (token.isBlank()) return
        runCatching { request(context, "POST", "/sync/v1/unpair", JSONObject(), false, root, 3000, 1500, token) }
    }

    fun paired(context: Context): Boolean = !prefs(context).getString("token", "").isNullOrBlank()

    fun token(context: Context): String = prefs(context).getString("token", "") ?: ""

    fun routes(prefs: SharedPreferences): Pair<List<String>, String?> {
        val peer = PeerRouting.mainPrefs(prefs)
        return PeerAddresses.ordered(peer) to PeerRouting.bluetooth(peer).takeIf { it.isNotBlank() }
    }

    /** Called only after pair() verified TLS and the claimed fingerprint. */
    fun saveRoutes(editor: SharedPreferences.Editor, reply: JSONObject, host: String, port: Int, fingerprint: String,
                   previous: JSONObject? = null): SharedPreferences.Editor {
        val peer = JSONObject().put("host", host).put("port", port).put("fingerprint", fingerprint)
            .put("addresses", previous?.optJSONArray("addresses") ?: JSONArray())
        PeerAddresses.learn(peer, reply.optJSONArray("addresses"), fingerprint,
            if (host.startsWith("bt:")) "" else PeerAddresses.endpoint(host, port))
        return editor.putString("addresses", peer.getJSONArray("addresses").toString())
            .putString("bt", reply.optJSONObject("routes")?.optString("bluetooth").orEmpty().ifBlank { previous?.optString("bt").orEmpty() })
    }

    fun base(context: Context): String {
        Pin.install(context)
        return PeerRouting.base(context, PeerRouting.main(context))
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
            val link = Peers.link(context, source) ?: throw IllegalStateException("Thiết bị giữ cuốn này đã bỏ ghép")
            return link to manifest!!.optString("remoteId", bookId)
        }
        return Peers.Link(base(context), token(context)) to bookId
    }

    /** Tên máy giữ cuốn `bookId` cho lời báo ("Mất kết nối với <tên>"): thiết bị ghép giữ nó, không thì máy tính chính; không biết tên thì "máy tính". */
    fun holderName(context: Context, bookId: String): String {
        val source = Store.playableManifest(bookId)?.optString("source").orEmpty()
        val name = if (source.isNotEmpty()) Peers.all(context).optJSONObject(source)?.optString("name") else prefs(context).getString("name", "")
        return name?.takeIf { it.isNotBlank() } ?: "máy tính"
    }

    /** Một file của cuốn `remote` trên máy giữ sách `link` (đã nhận header, có retry GET); `resumeFrom` > 0 = tải tiếp từ byte ấy (kèm `If-Range` = [ifRange]). */
    fun bookFile(context: Context, link: Peers.Link, remote: String, relative: String, resumeFrom: Long = 0, ifRange: String = ""): HttpURLConnection {
        Pin.install(context)
        return PeerTransfer.openGet {
            val selected = PeerRouting.resolve(context, link.base, link.token)
            val connection = URL("$selected/sync/v1/books/$remote/files/$relative").openConnection() as HttpURLConnection
            PeerRouting.expected(context, link.token)?.let { expected -> if (connection is HttpsURLConnection) Pin.pin(connection, expected) }
            connection.connectTimeout = 5000
            connection.readTimeout = 30000
            connection.setRequestProperty("Authorization", "Bearer ${link.token}")
            if (resumeFrom > 0) {
                connection.setRequestProperty("Range", "bytes=$resumeFrom-")
                // Phiên bản của file mà phần dở thuộc về (PartResume): file đã đổi thì máy kia gửi lại cả file thay vì đuôi của file mới.
                if (ifRange.isNotEmpty()) connection.setRequestProperty("If-Range", ifRange)
            }
            connection
        }
    }

    /** Nguồn một bài nhạc nền của cuốn cho [BookMusic.fetch]: null khi máy kia không có (mã khác 200). */
    fun musicSource(context: Context, link: Peers.Link, remote: String, name: String): BookMusic.Source? {
        val connection = bookFile(context, link, remote, name)
        if (Pin.guard { connection.responseCode } != 200) {
            connection.disconnect()
            return null
        }
        return BookMusic.Source(connection.inputStream, connection.contentLengthLong, connection::disconnect)
    }

    /** Mã thiết bị cho một địa chỉ (trình phát nghe thẳng): thiết bị ghép có địa chỉ ấy, không thì máy tính chính. */
    fun tokenFor(context: Context, uri: android.net.Uri): String {
        uri.fragment?.takeIf { it.startsWith("abook-book:") }?.removePrefix("abook-book:")?.let { book ->
            return linkFor(context, Store.requireBookId(book)).first.token
        }
        return Peers.tokenFor(context, uri) ?: token(context)
    }

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
        // Choose before HTTP: never replay a POST/upload after an uncertain result.
        val credential = token ?: if (auth) SyncLink.token(context) else ""
        val selected = PeerRouting.resolve(context, root, credential)
        try {
            return send(context, method, path, body, auth, selected, readTimeoutMs, connectTimeoutMs, token, upload = upload)
        } catch (error: IOException) {
            Route.markDown(selected.removePrefix("https://"))
            throw error
        }
    }

    /**
     * Phần thuần (test được) của [refuseSelf]: `host` là vòng lặp (127.x, `::1`, `::ffff:127.x`), "localhost" hay một địa chỉ của chính điện thoại
     * (IPv4 hay IPv6, viết ngắn hay đầy đủ, có ngoặc vuông / vùng `%`), kèm đúng cổng đồng bộ của nó. Chỉ so địa chỉ dạng số: tên chữ
     * ("may-khac.local") không tra DNS, và điện thoại không có tên máy đáng tin để so (tên thiết bị là tên người đặt, không phân giải được) -
     * khác máy tính (remote_books.py `is_own_host` so thêm `<tên máy>.local`).
     */
    internal fun isOwnAddress(host: String, port: Int, ownPort: Int, own: Collection<String>): Boolean {
        if (port != ownPort) return false
        val clean = cleanHost(host)
        if (clean == "localhost" || clean in own) return true
        val address = literal(clean) ?: return false
        return address.isLoopbackAddress || own.any { literal(cleanHost(it))?.hostAddress == address.hostAddress }
    }

    private fun cleanHost(host: String) = host.trim().trim('[', ']').substringBefore('%').trimEnd('.').lowercase()

    /** Địa chỉ số (IPv4 hay IPv6) thành [java.net.InetAddress]; không phải địa chỉ số thì null (không bao giờ tra DNS). `::ffff:a.b.c.d` thành IPv4. */
    private fun literal(text: String): java.net.InetAddress? {
        val numeric = ':' in text || Regex("""\d{1,3}(\.\d{1,3}){3}""").matches(text)
        return if (numeric) runCatching { java.net.InetAddress.getByName(text) }.getOrNull() else null
    }

    /** Ghép bằng địa chỉ gõ tay (không phải Bluetooth) với chính điện thoại này nhân đôi cả thư viện: từ chối trước khi gửi mã, như máy tính (remote_books.py `Computers.pair`). */
    fun refuseSelf(host: String, port: Int) {
        if (isOwnAddress(host, port, LibraryServer.PORT, LibraryServer.ownAddresses())) {
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
        // Mã của chính máy này: máy kia nhận ra cùng máy ghép lại thì thay dòng cũ, không thêm dòng trùng (sync.py `Devices.pair` `ident`).
        if (!body.has("id")) body.put("id", selfId(context))
        val seen = arrayOfNulls<String>(1)
        val text = send(context, "POST", "/sync/v1/pair", body, false, root, 20_000, 5000, null, seen)
        val reply = JSONObject(text)
        val fingerprint = seen[0].orEmpty()
        if (fingerprint.isEmpty() || !reply.optString("fingerprint").equals(fingerprint, ignoreCase = true)) {
            throw IllegalStateException("Chứng chỉ không khớp nên chưa ghép — bạn thử lại; vẫn lỗi thì kiểm tra mạng.")
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
        fun connect(): HttpURLConnection {
            val connection = URL(root + path).openConnection() as HttpURLConnection
            // `firstUse` != null: yêu cầu ghép - nhận chứng chỉ lạ một lần và đọc vân tay ra mảng này.
            if (firstUse != null && connection is HttpsURLConnection) Pin.firstUse(connection)
            else if (connection is HttpsURLConnection) {
                val credential = token ?: if (auth) SyncLink.token(context) else ""
                PeerRouting.expected(context, credential)?.let { Pin.pin(connection, it) }
            }
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
            return connection
        }
        val connection = if (method == "GET") PeerTransfer.openGet { connect() } else connect()
        try {
            val code = connection.responseCode
            val text = responseText(connection, code)
            if (firstUse != null && connection is HttpsURLConnection) firstUse[0] = Pin.peerFingerprint(connection)
            if (code >= 400) {
                val message = runCatching { JSONObject(text).optString("error") }.getOrNull()
                // Mang mã HTTP (NetErrors.Refused): 401 = máy kia đã bỏ ghép máy này, giao diện nói đúng thế thay vì "không kết nối được".
                throw NetErrors.Refused(code, message?.ifBlank { null } ?: "Máy tính trả lỗi $code")
            }
            if (firstUse == null && connection is HttpsURLConnection) {
                val credential = token ?: if (auth) SyncLink.token(context) else ""
                val seen = Pin.peerFingerprint(connection)
                PeerRouting.remember(context, credential, runCatching { JSONObject(text) }.getOrNull(), seen,
                    if (URL(root).host == "127.0.0.1" && BluetoothLink.addressOfPort(URL(root).port) != null) "bluetooth" else URL(root).authority)
            }
            if (firstUse == null && path.substringBefore('?').endsWith("/state")) {
                return JSONObject(text).apply { remove("addresses") }.toString()
            }
            return text
        } finally {
            connection.disconnect()
        }
    }

    internal fun responseText(connection: HttpURLConnection, code: Int): String {
        val cap = if (code >= 400) PeerTransfer.ERROR_BYTES else PeerTransfer.JSON_BYTES
        val declared = connection.getHeaderField("Content-Length")
        if (declared != null && (declared.toLongOrNull()?.let { it in 0..cap } != true)) throw PeerTransfer.Limit()
        val input = (if (code < 400) connection.inputStream else connection.errorStream) ?: return ""
        val bytes = java.io.ByteArrayOutputStream()
        input.use {
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val count = it.read(buffer, 0, minOf(buffer.size.toLong(), cap - bytes.size() + 1).toInt())
                if (count < 0) break
                if (count > cap - bytes.size()) throw PeerTransfer.Limit()
                bytes.write(buffer, 0, count)
            }
        }
        val text = bytes.toString("UTF-8")
        // Một đối tượng hay một mảng (GET /api/listen/library, /api/voices... trả mảng trần): số, chữ, true/null trần vẫn bị từ chối.
        if (text.isNotEmpty()) try {
            require(StrictJson.parse(text).let { it is JSONObject || it is JSONArray })
        } catch (error: Exception) {
            throw IllegalArgumentException("Dữ liệu máy gửi không hợp lệ; bạn hãy thử lại.", error)
        }
        return text
    }
}
