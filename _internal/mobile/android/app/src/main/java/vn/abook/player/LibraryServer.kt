package vn.abook.player

import android.content.Context
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.BufferedInputStream
import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.net.URLDecoder
import javax.net.ssl.SSLServerSocket
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.Executors
import android.util.Base64

/**
 * Mạng trạm, bước 2 (chủ sách 27-09): điện thoại PHỤC VỤ thư viện của nó cho máy đã ghép - máy tính (và sau này điện
 * thoại khác) nghe thẳng những cuốn chỉ có trên điện thoại, không phải chép sang.
 *
 * Nói ĐÚNG giao thức cổng đồng bộ của máy tính (abook/webui/sync.py): POST /sync/v1/pair, GET /sync/v1/library,
 * GET /sync/v1/books/<mã>/manifest, GET /sync/v1/books/<mã>/files/<tên> (có Range cho trình phát), POST
 * /sync/v1/books/<mã>/state (chỗ nghe hai chiều), và trả lời tìm máy UDP như máy tính (cổng 47631, "abook"). Nên
 * bên kết nối (webui/remote_books.py) không cần biết đầu kia là máy tính hay điện thoại.
 *
 * Không nhận sách: chỉ phục vụ sách đã tải về máy (book.json) và đúng các file book.json kể tên; ghi duy nhất danh sách
 * thiết bị đã ghép (`share.json`, lưu băm của mã thiết bị, không lưu mã thật) và chỗ nghe gộp từ máy kia. Chỉ chạy khi
 * người dùng bật "Cho máy khác nghe thư viện này". Mã ghép 6 số dùng một lần, sống 5 phút, sai 5 lần là huỷ - như máy
 * tính.
 *
 * Nói TLS, không bao giờ HTTP thường: chứng chỉ tự ký trong AndroidKeyStore ([ShareTls]), vân tay của nó đi trong lời đáp
 * ghép nối để máy kia ghim (webui/tls.py, [Pin]). Cổng Bluetooth ([BluetoothShare]) chỉ chuyển byte tới đúng cổng này nên TLS
 * đi nguyên vẹn từ máy kia tới đây.
 */
object LibraryServer {
    const val PORT = 47630
    const val DISCOVERY_PORT = 47631
    private const val PAIRING_MILLIS = 5 * 60 * 1000L
    private const val PAIRING_ATTEMPTS = 5
    private const val MAX_HEADER_BYTES = 16 * 1024
    // Chỗ nghe của một cuốn dài (mỗi chương một mục, dấu trang) vài chục KB; ghép nối vài chục byte.
    private const val MAX_BODY_BYTES = 2 * 1024 * 1024
    private val PROBE = "ABOOK_DISCOVER".toByteArray()
    private val BOOK_ID = Regex("[A-Za-z0-9_-]+")

    private lateinit var devicesFile: File
    private var server: ServerSocket? = null
    // Vân tay chứng chỉ TLS của máy này, điền lúc start().
    @Volatile var fingerprint = ""
        private set
    private var discovery: DatagramSocket? = null
    private val workers = Executors.newFixedThreadPool(6)
    private val random = SecureRandom()
    private var pairing: Pair<String, Long>? = null
    private var failures = 0
    var blocked = false
        private set
    var lastError = ""
        private set

    fun init(context: Context) {
        Store.init(context)
        Remote.init(context.applicationContext)
        if (!::devicesFile.isInitialized) devicesFile = File(context.filesDir, "share.json")
    }

    fun name(): String = "${Build.MANUFACTURER} ${Build.MODEL}".trim().ifBlank { "Điện thoại" }

    @Synchronized
    fun running(): Boolean = server?.isClosed == false

    /** Bật máy chủ (idempotent). Cổng bận: báo lỗi đọc được, không bật nửa vời. */
    @Synchronized
    fun start(context: Context) {
        init(context)
        // Bluetooth trước, và cả khi cổng Wi-Fi đã chạy: lần gọi sau khi vừa cho quyền / bật Bluetooth phải mở được nó.
        // Không mở được thì chỉ ghi lý do (BluetoothShare.status), cổng Wi-Fi vẫn chạy.
        runCatching { BluetoothShare.start(context) }
        if (running()) return
        lastError = ""
        val identity = try {
            ShareTls.identity()
        } catch (error: Exception) {
            lastError = "Không tạo được chứng chỉ bảo mật cho kết nối - ${error.message ?: error.javaClass.simpleName}"
            throw IllegalStateException(lastError)
        }
        fingerprint = identity.fingerprint
        val socket = try {
            (identity.context.serverSocketFactory.createServerSocket() as SSLServerSocket).apply {
                reuseAddress = true
                enabledProtocols = supportedProtocols.filter { it == "TLSv1.3" || it == "TLSv1.2" }.toTypedArray()
                bind(InetSocketAddress(PORT))
            }
        } catch (error: Exception) {
            lastError = "Cổng $PORT đang bận - ${error.message ?: "không mở được"}"
            throw IllegalStateException(lastError)
        }
        server = socket
        Thread({ accept(socket) }, "library-server").apply { isDaemon = true }.start()
        discovery = runCatching {
            DatagramSocket(null).apply {
                reuseAddress = true
                bind(InetSocketAddress(DISCOVERY_PORT))
            }
        }.getOrNull()?.also { udp -> Thread({ answer(udp) }, "library-discovery").apply { isDaemon = true }.start() }
    }

    @Synchronized
    fun stop() {
        runCatching { BluetoothShare.stop() }
        runCatching { server?.close() }
        runCatching { discovery?.close() }
        server = null
        discovery = null
        pairing = null
    }

    // ---- ghép nối -------------------------------------------------------------------------------------------------

    @Synchronized
    fun startPairing(): JSONObject {
        val code = "%06d".format(random.nextInt(1_000_000))
        pairing = code to System.currentTimeMillis() + PAIRING_MILLIS
        failures = 0
        blocked = false
        return JSONObject().put("code", code).put("expiresAt", pairing!!.second / 1000.0)
    }

    @Synchronized
    fun pairingCode(): JSONObject? {
        val current = pairing ?: return null
        if (current.second <= System.currentTimeMillis()) return null
        return JSONObject().put("code", current.first).put("expiresAt", current.second / 1000.0)
    }

    @Synchronized
    fun cancelPairing() {
        pairing = null
        failures = 0
        blocked = false
    }

    @Synchronized
    private fun pair(code: String, device: String): String? {
        val digits = code.filter { it.isDigit() }.take(12)
        val current = pairing ?: return null
        if (current.second <= System.currentTimeMillis()) return null
        if (!MessageDigest.isEqual(digits.toByteArray(), current.first.toByteArray())) {
            failures += 1
            if (failures >= PAIRING_ATTEMPTS) {
                pairing = null
                blocked = true
            }
            return null
        }
        pairing = null // mã dùng một lần
        val token = ByteArray(32).also(random::nextBytes)
            .let { Base64.encodeToString(it, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP) }
        val data = readDevices()
        data.getJSONObject("devices").put(hash(token), JSONObject()
            .put("name", device.trim().take(80).ifBlank { "Thiết bị" })
            .put("pairedAt", System.currentTimeMillis() / 1000.0)
            .put("lastSeen", System.currentTimeMillis() / 1000.0))
        Store.writeAtomic(devicesFile, data.toString())
        return token
    }

    /** Thiết bị đã ghép, cho giao diện: mã ngắn (12 ký tự đầu của băm), tên, lần thấy cuối - không bao giờ kèm mã thật. */
    @Synchronized
    fun devices(): JSONArray {
        val out = JSONArray()
        val devices = readDevices().getJSONObject("devices")
        devices.keys().forEach { key ->
            val entry = devices.getJSONObject(key)
            out.put(JSONObject(entry.toString()).put("id", key.take(12)))
        }
        return out
    }

    @Synchronized
    fun revoke(shortId: String) {
        val data = readDevices()
        val devices = data.getJSONObject("devices")
        devices.keys().asSequence().toList().filter { it.take(12) == shortId }.forEach(devices::remove)
        Store.writeAtomic(devicesFile, data.toString())
    }

    @Synchronized
    private fun identify(token: String): JSONObject? {
        if (token.isBlank()) return null
        val data = readDevices()
        val entry = data.getJSONObject("devices").optJSONObject(hash(token)) ?: return null
        val now = System.currentTimeMillis() / 1000.0
        if (now - entry.optDouble("lastSeen", 0.0) > 60) {
            entry.put("lastSeen", now)
            Store.writeAtomic(devicesFile, data.toString())
        }
        return entry
    }

    private fun readDevices(): JSONObject {
        val data = runCatching { JSONObject(devicesFile.readText()) }.getOrNull() ?: JSONObject()
        if (data.optJSONObject("devices") == null) data.put("devices", JSONObject())
        return data
    }

    private fun hash(token: String): String =
        MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }

    // ---- địa chỉ để người dùng gõ khi máy kia không tự tìm thấy ---------------------------------------------------

    fun addresses(): List<String> = runCatching {
        NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback }
            .flatMap { it.inetAddresses.toList() }
            .mapNotNull { address -> address.hostAddress?.takeIf { '.' in it && ':' !in it } }
            .distinct().sorted()
    }.getOrDefault(emptyList())

    // ---- tìm máy (UDP) ---------------------------------------------------------------------------------------------

    private fun answer(socket: DatagramSocket) {
        val buffer = ByteArray(512)
        while (!socket.isClosed) {
            try {
                val packet = DatagramPacket(buffer, buffer.size)
                socket.receive(packet)
                if (String(packet.data, 0, packet.length).trim().toByteArray().contentEquals(PROBE)) {
                    val reply = JSONObject().put("app", "abook").put("name", name()).put("port", PORT)
                        .put("kind", "phone").toString().toByteArray()
                    socket.send(DatagramPacket(reply, reply.size, packet.socketAddress))
                }
            } catch (_: SocketException) {
                return // đã tắt
            } catch (_: Exception) {
            }
        }
    }

    // ---- HTTP ------------------------------------------------------------------------------------------------------

    private fun accept(socket: ServerSocket) {
        while (!socket.isClosed) {
            val client = try {
                socket.accept()
            } catch (_: Exception) {
                return
            }
            workers.execute {
                client.use { connection ->
                    connection.soTimeout = 30_000
                    runCatching { handle(connection) }
                }
            }
        }
    }

    private class Request(val method: String, val path: String, val headers: Map<String, String>, val body: ByteArray)

    private fun read(input: InputStream): Request? {
        val header = StringBuilder() // dòng đầu + header là ASCII (đường dẫn đã mã hoá %)
        while (!(header.endsWith("\r\n\r\n") || header.endsWith("\n\n"))) {
            if (header.length >= MAX_HEADER_BYTES) return null
            val byte = input.read()
            if (byte < 0) return null
            header.append(byte.toChar())
        }
        val lines = header.toString().split("\r\n", "\n").filter { it.isNotEmpty() }
        val parts = lines.firstOrNull()?.split(" ") ?: return null
        if (parts.size < 2) return null
        val headers = lines.drop(1).mapNotNull { line ->
            val colon = line.indexOf(':')
            if (colon <= 0) null else line.substring(0, colon).trim().lowercase() to line.substring(colon + 1).trim()
        }.toMap()
        val length = headers["content-length"]?.toIntOrNull() ?: 0
        if (length > MAX_BODY_BYTES) return Request(parts[0], "", headers, ByteArray(0))
        val body = ByteArray(maxOf(0, length))
        var read = 0
        while (read < body.size) {
            val count = input.read(body, read, body.size - read)
            if (count < 0) break
            read += count
        }
        return Request(parts[0].uppercase(), parts[1].substringBefore('?'), headers, body)
    }

    private fun handle(connection: Socket) {
        val input = BufferedInputStream(connection.getInputStream())
        val output = connection.getOutputStream()
        val request = read(input) ?: return
        try {
            route(request, output)
        } catch (error: Exception) {
            json(output, 500, JSONObject().put("error", "${error.javaClass.simpleName}: ${error.message}"))
        }
    }

    private fun route(request: Request, output: OutputStream) {
        val path = request.path
        if (request.method == "POST" && path == "/sync/v1/pair") {
            val body = runCatching { JSONObject(String(request.body)) }.getOrDefault(JSONObject())
            val token = pair(body.optString("code"), body.optString("device"))
            if (token == null) json(output, 403, JSONObject().put("error", "Mã ghép nối sai hoặc đã hết hạn"))
            else json(output, 200, JSONObject().put("token", token).put("name", name()).put("fingerprint", fingerprint))
            return
        }
        val token = request.headers["authorization"]?.removePrefix("Bearer ")?.trim().orEmpty()
        if (identify(token) == null) {
            json(output, 401, JSONObject().put("error", "Thiết bị chưa ghép nối"))
            return
        }
        if (request.method == "GET" && path == "/sync/v1/library") {
            json(output, 200, JSONObject().put("name", name()).put("books", libraryView()))
            return
        }
        // Mạng trạm bước 4: máy đã ghép xem và điều khiển trình phát của điện thoại này - cùng hình dạng máy tính trả
        // (sync.py player_view), nên bên điều khiển không cần biết đầu kia là gì. Điện thoại làm lệnh ngay, trả luôn kết quả.
        if (path == "/sync/v1/player") {
            when (request.method) {
                "GET" -> json(output, 200, playerView())
                "POST" -> {
                    val command = runCatching { JSONObject(String(request.body)) }.getOrNull()?.let(::remoteCommand)
                    if (command == null) {
                        json(output, 400, JSONObject().put("error", "Lệnh không hỗ trợ"))
                    } else {
                        val problem = Remote.applyNow(command)
                        json(output, 200, JSONObject().put("id", hex(6)).put("ok", problem == null).put("message", problem ?: ""))
                    }
                }
                else -> json(output, 405, JSONObject().put("error", "Không hỗ trợ"))
            }
            return
        }
        val match = Regex("/sync/v1/books/([^/]+)/(manifest|state|files/(.+))").matchEntire(path)
        val book = match?.groupValues?.get(1).orEmpty()
        val manifest = if (BOOK_ID.matches(book)) Store.manifest(book) else null
        if (match == null || manifest == null) {
            json(output, 404, JSONObject().put("error", "Không có sách này"))
            return
        }
        when {
            request.method == "GET" && match.groupValues[2] == "manifest" -> json(output, 200, served(book, manifest))
            (request.method == "GET" || request.method == "HEAD") && match.groupValues[3].isNotEmpty() -> {
                val relative = URLDecoder.decode(match.groupValues[3], "UTF-8")
                val target = if (relative in allowedFiles(manifest)) Store.file(book, relative) else null
                if (target == null || !target.isFile) json(output, 404, JSONObject().put("error", "Không có file này"))
                else sendFile(output, target, request.headers["range"], request.method == "HEAD")
            }
            // Chỗ nghe hai chiều: máy kia gửi bản của nó, điện thoại gộp vào hồ sơ đang dùng của cuốn này (Store.mergeRemote,
            // cùng phép gộp của máy tính) và trả bản đã gộp.
            request.method == "POST" && match.groupValues[2] == "state" -> {
                val body = runCatching { JSONObject(String(request.body)) }.getOrNull()
                if (body == null) json(output, 400, JSONObject().put("error", "Thân yêu cầu không phải JSON"))
                else json(output, 200, Store.mergeRemote(book, body))
            }
            else -> json(output, 405, JSONObject().put("error", "Không hỗ trợ"))
        }
    }

    private fun playerView(): JSONObject {
        val books = JSONArray()
        for (manifest in Store.books()) manifest.optString("id").takeIf { BOOK_ID.matches(it) }?.let { books.put(it) }
        return JSONObject().put("name", name()).put("kind", "phone").put("state", Remote.snapshot()).put("books", books)
            .put("stream", false).put("acks", JSONArray()).put("age", 0)
    }

    /** Lệnh từ mạng, kiểm và rút gọn như `sync.remote_command` của máy tính: chỉ lệnh biết, đúng kiểu, có trần. */
    private fun remoteCommand(body: JSONObject): JSONObject? {
        val action = body.optString("action")
        if (action !in setOf("play", "pause", "toggle", "skip", "seek", "next", "previous", "jump", "rate", "load")) return null
        val command = JSONObject().put("action", action)
        fun number(key: String, low: Double, high: Double): Double =
            body.optDouble(key, low).let { if (it.isNaN()) low else it.coerceIn(low, high) }
        if (action in setOf("skip", "seek", "jump", "load")) {
            command.put("seconds", number("seconds", if (action == "skip") -3600.0 else 0.0, 86_400.0))
        }
        if (action == "jump" || action == "load") {
            val chapter = body.opt("chapterId") as? Int ?: return null
            command.put("chapterId", chapter)
        }
        if (action == "load") {
            val book = body.optString("bookId")
            if (!BOOK_ID.matches(book) || book.length > 700) return null
            command.put("bookId", book)
        }
        if (action == "rate") command.put("rate", number("rate", 0.5, 3.0))
        return command
    }

    private fun hex(bytes: Int): String = ByteArray(bytes).also(random::nextBytes).joinToString("") { "%02x".format(it) }

    /** Sách đã tải về điện thoại, cùng hình dạng `library_view` của máy tính. */
    private fun libraryView(): JSONArray {
        val books = JSONArray()
        for (manifest in Store.books()) {
            val id = manifest.optString("id")
            if (!BOOK_ID.matches(id)) continue
            val chapters = availableChapters(id, manifest)
            if (chapters == 0) continue
            val entry = JSONObject().put("id", id).put("title", manifest.optString("title"))
                .put("narrator", manifest.opt("narrator") ?: JSONObject.NULL)
                .put("duration", manifest.optDouble("duration", 0.0))
                .put("chaptersTotal", manifest.optInt("chaptersTotal", chapters))
                .put("chaptersAvailable", chapters)
                .put("complete", manifest.optBoolean("complete"))
                .put("updatedAt", File(Store.bookDir(id), "book.json").lastModified() / 1000.0)
            val cover = manifest.optJSONObject("cover")
            entry.put("cover", if (cover == null) JSONObject.NULL
            else JSONObject().put("color", cover.opt("color") ?: JSONObject.NULL).put("version", cover.opt("version") ?: 0))
            books.put(entry)
        }
        return books
    }

    private fun availableChapters(id: String, manifest: JSONObject): Int {
        val chapters = manifest.optJSONArray("chapters") ?: return 0
        return (0 until chapters.length()).count { index ->
            val chapter = chapters.getJSONObject(index)
            chapter.optBoolean("available") && runCatching { Store.file(id, chapter.getString("file")).isFile }.getOrDefault(false)
        }
    }

    /** book.json như máy kia cần: bỏ phần "package" (của file sách/của máy khác), chương nào không có file thì chưa nghe được. */
    private fun served(id: String, manifest: JSONObject): JSONObject {
        val copy = JSONObject(manifest.toString())
        copy.remove("package")
        copy.put("id", id)
        val chapters = copy.optJSONArray("chapters") ?: JSONArray()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            val present = chapter.optBoolean("available") &&
                runCatching { Store.file(id, chapter.getString("file")).isFile }.getOrDefault(false)
            if (!present) chapter.put("available", false).put("file", JSONObject.NULL).put("size", 0)
        }
        copy.put("chaptersAvailable", availableChapters(id, manifest))
        return copy
    }

    /** Đúng các file book.json kể tên - không bao giờ một đường dẫn tuỳ ý. */
    private fun allowedFiles(manifest: JSONObject): Set<String> {
        val names = mutableSetOf<String>()
        val chapters = manifest.optJSONArray("chapters") ?: JSONArray()
        for (index in 0 until chapters.length()) {
            val chapter = chapters.getJSONObject(index)
            chapter.optString("file").takeIf { it.isNotBlank() && it != "null" }?.let(names::add)
            chapter.optString("script").takeIf { it.isNotBlank() && it != "null" }?.let(names::add)
        }
        manifest.optString("cast").takeIf { it.isNotBlank() }?.let(names::add)
        val samples = manifest.optJSONArray("samples") ?: JSONArray()
        for (index in 0 until samples.length()) names += samples.getString(index)
        manifest.optJSONObject("cover")?.optString("file", "cover.jpg")?.let(names::add)
        return names.filter { !it.contains("..") }.toSet()
    }

    private fun json(output: OutputStream, status: Int, payload: JSONObject) {
        val body = payload.toString().toByteArray()
        head(output, status, "application/json; charset=utf-8", body.size.toLong(), mapOf("Cache-Control" to "no-store"))
        output.write(body)
        output.flush()
    }

    private fun sendFile(output: OutputStream, file: File, range: String?, headOnly: Boolean) {
        val size = file.length()
        var start = 0L
        var end = size - 1
        var status = 200
        val match = Regex("bytes=(\\d*)-(\\d*)").matchEntire(range?.trim().orEmpty())
        if (match != null && size > 0) {
            val (first, last) = match.destructured
            if (first.isNotEmpty()) {
                start = first.toLong()
                end = if (last.isNotEmpty()) minOf(last.toLong(), size - 1) else size - 1
            } else if (last.isNotEmpty()) {
                start = maxOf(0, size - last.toLong())
            }
            if (start > end) {
                head(output, 416, "application/octet-stream", 0, mapOf("Content-Range" to "bytes */$size"))
                output.flush()
                return
            }
            status = 206
        }
        val type = when (file.extension.lowercase()) {
            "mp3" -> "audio/mpeg"
            "wav" -> "audio/wav"
            "json" -> "application/json; charset=utf-8"
            "jpg", "jpeg" -> "image/jpeg"
            "png" -> "image/png"
            else -> "application/octet-stream"
        }
        val extra = mutableMapOf("Accept-Ranges" to "bytes")
        if (status == 206) extra["Content-Range"] = "bytes $start-$end/$size"
        head(output, status, type, end - start + 1, extra)
        if (!headOnly) {
            file.inputStream().use { source ->
                source.skip(start)
                var remaining = end - start + 1
                val buffer = ByteArray(64 * 1024)
                while (remaining > 0) {
                    val count = source.read(buffer, 0, minOf(buffer.size.toLong(), remaining).toInt())
                    if (count < 0) break
                    output.write(buffer, 0, count)
                    remaining -= count
                }
            }
        }
        output.flush()
    }

    private fun head(output: OutputStream, status: Int, type: String, length: Long, extra: Map<String, String> = emptyMap()) {
        val reason = mapOf(200 to "OK", 206 to "Partial Content", 400 to "Bad Request", 401 to "Unauthorized", 403 to "Forbidden",
            404 to "Not Found", 405 to "Method Not Allowed", 416 to "Range Not Satisfiable", 500 to "Internal Server Error")
        val lines = StringBuilder("HTTP/1.1 $status ${reason[status] ?: "Status"}\r\n")
            .append("Content-Type: $type\r\n").append("Content-Length: $length\r\n").append("Connection: close\r\n")
        extra.forEach { (key, value) -> lines.append("$key: $value\r\n") }
        output.write(lines.append("\r\n").toString().toByteArray())
    }
}
