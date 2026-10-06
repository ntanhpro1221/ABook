package vn.abook.player

import org.w3c.dom.Element
import org.w3c.dom.Node
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.io.OutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.MulticastSocket
import java.net.NetworkInterface
import java.net.Proxy
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketTimeoutException
import java.net.URI
import java.net.URL
import java.security.MessageDigest
import java.security.SecureRandom
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.Executors
import javax.xml.parsers.DocumentBuilderFactory

/**
 * Phát lên loa / TV DLNA (UPnP AV MediaRenderer) thẳng từ điện thoại - 01-10. Cùng giao thức và cùng phép an toàn với máy
 * tính (abook/webui/cast.py): tìm bằng SSDP, đọc mô tả ĐÚNG ở địa chỉ đã trả lời và chỉ gửi lệnh tới địa chỉ ấy,
 * không theo chuyển hướng, không qua proxy, XML có trần cỡ và không nhận DOCTYPE / ENTITY. Thiết bị tự tải chương qua cổng
 * riêng [Media]: chỉ file đã đưa, mỗi file một mã ngẫu nhiên 128 bit, có Range.
 *
 * Dùng cho sách ĐÃ CÓ trên điện thoại (tải về, mở file .abook) - không cần máy tính; sách nghe thẳng từ máy tính thì máy
 * tính phát (RemotePlayers, mã "cast:"). Điều khiển, hỏi vị trí, tự sang chương: [DlnaPlayers].
 */
object Dlna {
    const val MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
    const val FEATURES = "DLNA.ORG_OP=01;DLNA.ORG_FLAGS=01700000000000000000000000000000"
    private const val AV_TRANSPORT = "urn:schemas-upnp-org:service:AVTransport:"
    private const val RENDERING_CONTROL = "urn:schemas-upnp-org:service:RenderingControl:"
    private const val AGENT = "ABook UPnP/1.0 DLNADOC/1.50"
    private const val MAX_XML = 256 * 1024
    private val GROUP = InetSocketAddress("239.255.255.250", 1900)
    private val TV = Regex("\\b(tv|television|bravia|webos|tizen|roku|fire ?tv|google ?tv|android ?tv|smart ?tv)\\b", RegexOption.IGNORE_CASE)
    private val MEDIA = Regex("\\b(windows (digital )?media|windows media player|microsoft)\\b", RegexOption.IGNORE_CASE)
    private val DOCTYPE = Regex("<!\\s*(DOCTYPE|ENTITY)", RegexOption.IGNORE_CASE)

    /** Lỗi UPnP AVTransport nói bằng lời người nghe hiểu - như máy tính. */
    private val ERRORS = mapOf(
        401 to "thiết bị không có lệnh này",
        402 to "thiết bị không nhận lệnh này",
        701 to "thiết bị chưa sẵn sàng cho lệnh này",
        702 to "thiết bị chưa có gì để phát",
        710 to "thiết bị không tua được",
        711 to "vị trí tua nằm ngoài chương",
        714 to "thiết bị không phát được loại audio này",
        716 to "thiết bị không tải được audio từ điện thoại",
        717 to "thiết bị không đổi được tốc độ",
    )

    data class Renderer(
        val id: String, // 12 hex theo UDN (Cast: theo `id` trong TXT) - trùng mã máy tính đặt cho cùng thiết bị
        val name: String,
        val kind: String, // "tv" | "media" | "speaker" - chỉ để chọn biểu tượng
        val host: String, // địa chỉ IP đã trả lời SSDP / mDNS; mô tả và lệnh chỉ đi tới đây
        val location: String = "",
        val avUrl: String = "",
        val avType: String = "",
        val protocol: String = "dlna", // "dlna" | "gcast" (Google Cast, GCast.kt): chọn backend
        val port: Int = 0, // Cast: cổng SRV (thường 8009); DLNA đi theo avUrl
        val rcUrl: String = "", // RenderingControl (âm lượng); "" khi thiết bị không có
        val rcType: String = "",
    )

    class Failure(message: String, val code: Int = 0) : Exception(message)

    /** Lời của một mã lỗi UPnP; GCast dùng lại cho lỗi của Cast (cùng một câu người nghe hiểu). */
    fun error(code: Int): String = ERRORS.getValue(code)

    fun clock(seconds: Double): String {
        val whole = maxOf(0L, Math.round(seconds))
        return "%d:%02d:%02d".format(whole / 3600, whole / 60 % 60, whole % 60)
    }

    /** "H+:MM:SS[.F+]" hay "H+:MM:SS.F0/F1" -> giây; "NOT_IMPLEMENTED", rỗng, lạ -> 0. */
    fun secondsOf(value: String?): Double {
        val match = Regex("\\s*(\\d+):(\\d{1,2}):(\\d{1,2})(?:\\.(\\d+)(?:/(\\d+))?)?\\s*").matchEntire(value.orEmpty()) ?: return 0.0
        val (hours, minutes, whole, fraction, divisor) = match.destructured
        var total = hours.toLong() * 3600 + minutes.toLong() * 60 + whole.toLong() + 0.0
        if (fraction.isNotEmpty()) {
            total += if (divisor.isNotEmpty() && divisor.toLong() > 0) fraction.toDouble() / divisor.toDouble() else "0.$fraction".toDouble()
        }
        return total
    }

    internal fun clean(value: String, limit: Int) = value.replace(Regex("[\\u0000-\\u001f\\u007f]+"), " ").trim().take(limit)

    private fun escape(value: String) = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")

    /** IPv4 trong nhà (mạng riêng, link-local, loopback cho bài thử): thiết bị phát không ở Internet. */
    fun lan(host: String): Boolean {
        if (!Regex("\\d{1,3}(\\.\\d{1,3}){3}").matches(host)) return false
        val address = runCatching { InetAddress.getByName(host) }.getOrNull() ?: return false
        return address.isSiteLocalAddress || address.isLinkLocalAddress || address.isLoopbackAddress
    }

    // ---- tìm --------------------------------------------------------------------------------------------------

    private fun message(wait: Int) = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\n" +
        "MX: $wait\r\nST: $MEDIA_RENDERER\r\nUSER-AGENT: $AGENT\r\n\r\n").toByteArray(Charsets.US_ASCII)

    /** LOCATION của một trả lời SSDP cho thiết bị phát; "" nếu không phải. */
    fun location(data: ByteArray, length: Int = data.size): String {
        val lines = String(data, 0, length, Charsets.UTF_8).split("\r\n")
        if (lines.isEmpty() || !Regex("HTTP/1\\.[01] 200.*").matches(lines[0])) return ""
        val headers = lines.drop(1).mapNotNull { line ->
            val colon = line.indexOf(':')
            if (colon > 0) line.substring(0, colon).trim().lowercase() to line.substring(colon + 1).trim() else null
        }.toMap()
        val st = headers["st"].orEmpty()
        if ("MediaRenderer" !in st && "AVTransport" !in st) return ""
        return headers["location"].orEmpty().take(500)
    }

    /** Card mạng IPv4 trong nhà đang bật (Wi-Fi, Ethernet; bỏ loopback và card không multicast). */
    private fun interfaces(): List<Pair<NetworkInterface, Inet4Address>> = runCatching {
        NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback && it.supportsMulticast() }
            .flatMap { nif -> nif.inetAddresses.toList().filterIsInstance<Inet4Address>().filter { lan(it.hostAddress ?: "") }.map { nif to it } }
    }.getOrDefault(emptyList())

    /**
     * Gửi [message] (UDP) tới nhóm multicast [group] ra từng card mạng (hai lần - UDP trên Wi-Fi hay rơi) và thẳng tới
     * [targets] (bài thử, thiết bị giả); gom trả lời trong [timeoutMs]. [accept] (dữ liệu, độ dài, địa chỉ đã trả lời) ->
     * các cặp (khoá, giá trị); khoá trùng thì giữ lần đầu. Trả lời tới bằng unicast nên không cần MulticastLock. Dùng chung
     * cho SSDP (DLNA) ở đây và mDNS (Google Cast, GCast.kt).
     */
    fun <K : Any, V> probe(
        message: ByteArray,
        group: InetSocketAddress,
        timeoutMs: Int,
        targets: List<InetSocketAddress> = emptyList(),
        multicast: Boolean = true,
        ttl: Int = 2,
        accept: (ByteArray, Int, String) -> List<Pair<K, V>>,
    ): List<Pair<K, V>> {
        val sockets = mutableListOf<Pair<DatagramSocket, List<InetSocketAddress>>>()
        if (multicast) {
            for ((nif, address) in interfaces()) {
                runCatching {
                    MulticastSocket(InetSocketAddress(address, 0)).apply { networkInterface = nif; timeToLive = ttl }
                }.getOrNull()?.let { sockets += it to listOf(group) }
            }
        }
        if (targets.isNotEmpty()) {
            val loopback = targets.all { it.address?.isLoopbackAddress == true }
            sockets += DatagramSocket(InetSocketAddress(if (loopback) "127.0.0.1" else "0.0.0.0", 0)) to targets
        }
        val found = LinkedHashMap<K, V>()
        val pool = Executors.newFixedThreadPool(maxOf(1, sockets.size))
        try {
            val deadline = System.currentTimeMillis() + timeoutMs
            val jobs = sockets.map { (socket, destinations) ->
                pool.submit {
                    val send = { destinations.forEach { runCatching { socket.send(DatagramPacket(message, message.size, it)) } } }
                    send()
                    var resent = false
                    val buffer = ByteArray(8192)
                    while (true) {
                        val now = System.currentTimeMillis()
                        if (now >= deadline) break
                        if (!resent && now >= deadline - timeoutMs * 2 / 3) {
                            send()
                            resent = true
                        }
                        val packet = DatagramPacket(buffer, buffer.size)
                        socket.soTimeout = maxOf(1, minOf(200, (deadline - now).toInt()))
                        try {
                            socket.receive(packet)
                        } catch (_: SocketTimeoutException) {
                            continue
                        } catch (_: IOException) {
                            break
                        }
                        val source = packet.address?.hostAddress ?: continue
                        val answers = accept(packet.data, packet.length, source)
                        synchronized(found) { answers.forEach { found.putIfAbsent(it.first, it.second) } }
                    }
                }
            }
            jobs.forEach { runCatching { it.get() } }
        } finally {
            sockets.forEach { it.first.close() }
            pool.shutdownNow()
        }
        return found.map { it.key to it.value }
    }

    /** M-SEARCH tìm thiết bị phát ra từng card mạng và thẳng tới [targets] (bài thử) -> [(LOCATION, địa chỉ đã trả lời)]. */
    fun search(timeoutMs: Int = 2000, targets: List<InetSocketAddress> = emptyList(), multicast: Boolean = true): List<Pair<String, String>> =
        probe(message(maxOf(1, timeoutMs / 1000)), GROUP, timeoutMs, targets, multicast) { data, length, source ->
            location(data, length).let { if (it.isEmpty()) emptyList() else listOf(it to source) }
        }

    // ---- mô tả, lệnh --------------------------------------------------------------------------------------------

    private fun open(url: String, timeoutMs: Int): HttpURLConnection =
        (URL(url).openConnection(Proxy.NO_PROXY) as HttpURLConnection).apply {
            instanceFollowRedirects = false // chuyển hướng = lối vòng tới máy khác: không theo
            connectTimeout = timeoutMs
            readTimeout = timeoutMs
            setRequestProperty("User-Agent", AGENT)
        }

    private fun readCapped(stream: InputStream?): ByteArray {
        if (stream == null) return ByteArray(0)
        val out = ByteArrayOutputStream()
        stream.use { source ->
            val buffer = ByteArray(16 * 1024)
            while (true) {
                val count = source.read(buffer)
                if (count < 0) break
                out.write(buffer, 0, count)
                if (out.size() > MAX_XML) throw Failure("thiết bị trả lời lạ")
            }
        }
        return out.toByteArray()
    }

    private fun parse(data: ByteArray): Element {
        if (data.size > MAX_XML || DOCTYPE.containsMatchIn(String(data, Charsets.ISO_8859_1))) throw Failure("thiết bị trả lời lạ")
        return try {
            val factory = DocumentBuilderFactory.newInstance().apply {
                isNamespaceAware = true
                isExpandEntityReferences = false
            }
            factory.newDocumentBuilder().parse(data.inputStream()).documentElement
        } catch (error: Exception) {
            throw Failure("thiết bị trả lời lạ")
        }
    }

    private fun local(node: Node): String = node.localName ?: node.nodeName.substringAfter(':')

    private fun children(element: Element, name: String): List<Element> =
        (0 until element.childNodes.length).map { element.childNodes.item(it) }.filterIsInstance<Element>().filter { local(it) == name }

    private fun text(element: Element, name: String): String = children(element, name).firstOrNull()?.textContent?.trim().orEmpty()

    internal fun sha1(value: String): String =
        MessageDigest.getInstance("SHA-1").digest(value.toByteArray()).joinToString("") { "%02x".format(it) }

    /** Mô tả thiết bị ở [location] - chỉ khi nó nằm đúng ở [host]; null: không phát được hay lệnh trỏ sang máy khác. */
    fun describe(location: String, host: String, timeoutMs: Int = 3000): Renderer? {
        val uri = runCatching { URI(location) }.getOrNull() ?: return null
        if (uri.scheme != "http" || uri.host != host || !lan(host)) return null
        val connection = open(location, timeoutMs)
        val root = try {
            if (connection.responseCode != 200) throw Failure("không đọc được mô tả thiết bị")
            parse(readCapped(connection.inputStream))
        } catch (error: IOException) {
            throw Failure("không đọc được mô tả thiết bị")
        } finally {
            connection.disconnect()
        }
        val base = text(root, "URLBase").ifEmpty { location }
        val queue = ArrayDeque(children(root, "device"))
        while (queue.isNotEmpty()) {
            val device = queue.removeFirst()
            var av: Pair<String, String>? = null
            var rc: Pair<String, String>? = null
            for (list in children(device, "serviceList")) for (service in children(list, "service")) {
                val type = text(service, "serviceType")
                val url = runCatching { URI(base).resolve(text(service, "controlURL")).toString() }.getOrNull() ?: continue
                val target = runCatching { URI(url) }.getOrNull() ?: continue
                if (target.scheme != "http" || target.host != host) continue
                if (av == null && type.startsWith(AV_TRANSPORT)) av = type to url
                if (rc == null && type.startsWith(RENDERING_CONTROL)) rc = type to url
            }
            if (av == null) {
                for (list in children(device, "deviceList")) queue.addAll(children(list, "device"))
                continue
            }
            val name = clean(text(device, "friendlyName"), 80).ifEmpty { host }
            val model = listOf("manufacturer", "modelName", "modelDescription").joinToString(" ") { text(device, it) }
            val kind = when {
                TV.containsMatchIn("$name $model") -> "tv"
                MEDIA.containsMatchIn(model) -> "media"
                else -> "speaker"
            }
            return Renderer(sha1(text(device, "UDN").ifEmpty { location }).take(12), name, kind, host, location, av.second, av.first,
                rcUrl = rc?.second.orEmpty(), rcType = rc?.first.orEmpty())
        }
        return null
    }

    private fun fault(data: ByteArray): Failure {
        val root = try {
            parse(data)
        } catch (error: Failure) {
            return error
        }
        val code = root.getElementsByTagNameNS("*", "errorCode").item(0)?.textContent?.trim().orEmpty()
        val description = root.getElementsByTagNameNS("*", "errorDescription").item(0)?.textContent?.trim().orEmpty()
        val number = code.toIntOrNull() ?: 0
        return Failure(ERRORS[number] ?: clean(description, 120).ifEmpty { "thiết bị từ chối lệnh này" }, number)
    }

    /** Một lệnh UPnP (SOAP 1.1) -> các tham số trả về; lỗi UPnP hay lỗi mạng -> [Failure] câu tiếng Việt. */
    fun soap(url: String, service: String, action: String, arguments: List<Pair<String, Any>> = emptyList(), timeoutMs: Int = 5000): Map<String, String> {
        val inner = arguments.joinToString("") { (name, value) -> "<$name>${escape(value.toString())}</$name>" }
        val body = ("<?xml version=\"1.0\" encoding=\"utf-8\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\" " +
            "s:encodingStyle=\"http://schemas.xmlsoap.org/soap/encoding/\"><s:Body><u:$action xmlns:u=\"${escape(service)}\">$inner" +
            "</u:$action></s:Body></s:Envelope>").toByteArray()
        val connection = open(url, timeoutMs).apply {
            requestMethod = "POST"
            doOutput = true
            setRequestProperty("Content-Type", "text/xml; charset=\"utf-8\"")
            setRequestProperty("SOAPACTION", "\"$service#$action\"")
        }
        val data = try {
            connection.outputStream.use { it.write(body) }
            val code = connection.responseCode
            val reply = readCapped(if (code < 400) connection.inputStream else connection.errorStream)
            if (code >= 400) throw fault(reply)
            reply
        } catch (error: IOException) {
            throw Failure("không trả lời - thiết bị đã tắt hay rời mạng?")
        } finally {
            connection.disconnect()
        }
        val response = parse(data).getElementsByTagNameNS("*", "${action}Response").item(0) as? Element
            ?: throw Failure("thiết bị trả lời lạ")
        return (0 until response.childNodes.length).map { response.childNodes.item(it) }.filterIsInstance<Element>()
            .associate { local(it) to it.textContent.orEmpty() }
    }

    /** Mô tả một chương (DIDL-Lite) cho SetAVTransportURI - TV hiện tên chương, tên sách. Không ghi DLNA.ORG_PN (như máy tính). */
    fun didl(url: String, title: String, album: String, duration: Double, size: Long, mime: String): String {
        val length = if (duration > 0) " duration=\"${clock(duration)}.000\"" else ""
        return "<DIDL-Lite xmlns=\"urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" " +
            "xmlns:upnp=\"urn:schemas-upnp-org:metadata-1-0/upnp/\" xmlns:dlna=\"urn:schemas-dlna-org:metadata-1-0/\">" +
            "<item id=\"abook-chapter\" parentID=\"abook\" restricted=\"1\"><dc:title>${escape(title)}</dc:title>" +
            "<dc:creator>ABook</dc:creator><upnp:album>${escape(album)}</upnp:album><upnp:artist>${escape(album)}</upnp:artist>" +
            "<upnp:class>object.item.audioItem.musicTrack</upnp:class>" +
            "<res protocolInfo=\"http-get:*:$mime:$FEATURES\"$length size=\"$size\">${escape(url)}</res></item></DIDL-Lite>"
    }

    /** Địa chỉ của máy này mà thiết bị ở [host] tới được (card mạng hệ điều hành chọn để đi tới nó). */
    fun routeTo(host: String): String = DatagramSocket().use { probe ->
        probe.connect(InetAddress.getByName(host), 9)
        probe.localAddress.hostAddress ?: "127.0.0.1"
    }

    // ---- cổng audio -----------------------------------------------------------------------------------------------

    /**
     * Cổng riêng để thiết bị tải chương: chỉ file đã đưa qua [share], mỗi file một mã ngẫu nhiên 128 bit, hết hạn sau 12
     * giờ; GET/HEAD có Range (thiết bị tua bằng Range). Mở lần đầu cần.
     */
    class Media(private val bind: String = "0.0.0.0") {
        private val files = ConcurrentHashMap<String, Pair<File, Long>>()
        private val random = SecureRandom()
        private val workers = Executors.newCachedThreadPool()
        private var server: ServerSocket? = null

        @Synchronized
        private fun start(): ServerSocket {
            server?.takeIf { !it.isClosed }?.let { return it }
            val socket = ServerSocket().apply {
                reuseAddress = true
                bind(InetSocketAddress(bind, 0))
            }
            server = socket
            Thread({ accept(socket) }, "dlna-media").apply { isDaemon = true }.start()
            return socket
        }

        fun share(file: File, reach: String): String {
            val socket = start()
            val now = System.currentTimeMillis()
            files.entries.removeIf { it.value.second < now }
            val token = ByteArray(16).also(random::nextBytes).joinToString("") { "%02x".format(it) }
            files[token] = file to now + TTL_MS
            val address = if (bind == "127.0.0.1") "127.0.0.1" else routeTo(reach)
            return "http://$address:${socket.localPort}/c/$token.${file.extension.lowercase()}"
        }

        @Synchronized
        fun close() {
            server?.close()
            server = null
        }

        private fun accept(socket: ServerSocket) {
            while (!socket.isClosed) {
                val client = runCatching { socket.accept() }.getOrNull() ?: break
                workers.execute { runCatching { client.use(::serve) } }
            }
        }

        private fun serve(client: Socket) {
            client.soTimeout = 15_000
            val input = client.getInputStream().buffered()
            val head = StringBuilder()
            while (!head.endsWith("\r\n\r\n")) {
                val byte = input.read()
                if (byte < 0 || head.length > 16 * 1024) return
                head.append(byte.toChar())
            }
            val lines = head.split("\r\n")
            val parts = lines.first().split(" ")
            if (parts.size < 2 || parts[0] !in setOf("GET", "HEAD")) return status(client.getOutputStream(), 405)
            val headers = lines.drop(1).mapNotNull { line ->
                val colon = line.indexOf(':')
                if (colon > 0) line.substring(0, colon).trim().lowercase() to line.substring(colon + 1).trim() else null
            }.toMap()
            val token = Regex("/c/([0-9a-f]{32})(?:\\.[a-z0-9]{1,5})?").matchEntire(parts[1].substringBefore('?'))?.groupValues?.get(1)
            val entry = token?.let { files[it] }
            val output = client.getOutputStream()
            if (entry == null || entry.second < System.currentTimeMillis() || !entry.first.isFile) return status(output, 404)
            send(output, entry.first, headers["range"], parts[0] == "HEAD")
        }

        private fun status(output: OutputStream, code: Int) {
            val reason = if (code == 404) "Not Found" else if (code == 416) "Range Not Satisfiable" else "Method Not Allowed"
            output.write("HTTP/1.1 $code $reason\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
            output.flush()
        }

        private fun send(output: OutputStream, file: File, range: String?, headOnly: Boolean) {
            val size = file.length()
            var start = 0L
            var end = size - 1
            var partial = false
            val match = Regex("bytes=(\\d*)-(\\d*)").matchEntire(range?.trim().orEmpty())
            if (match != null && size > 0) {
                val (first, last) = match.destructured
                if (first.isNotEmpty()) {
                    start = first.toLong()
                    end = if (last.isNotEmpty()) minOf(last.toLong(), size - 1) else size - 1
                } else if (last.isNotEmpty()) {
                    start = maxOf(0, size - last.toLong())
                }
                if (start > end || start >= size) {
                    output.write("HTTP/1.1 416 Range Not Satisfiable\r\nContent-Range: bytes */$size\r\nContent-Length: 0\r\nConnection: close\r\n\r\n".toByteArray())
                    output.flush()
                    return
                }
                partial = true
            }
            val type = when (file.extension.lowercase()) {
                "mp3" -> "audio/mpeg"
                "m4a" -> "audio/mp4"
                "wav" -> "audio/wav"
                else -> "application/octet-stream"
            }
            val headLines = StringBuilder(if (partial) "HTTP/1.1 206 Partial Content\r\n" else "HTTP/1.1 200 OK\r\n")
                .append("Content-Type: $type\r\nContent-Length: ${end - start + 1}\r\nAccept-Ranges: bytes\r\n")
                // Ứng dụng nhận của Google Cast là trang web: tải audio bằng CORS.
                .append("Access-Control-Allow-Origin: *\r\n")
                .append("transferMode.dlna.org: Streaming\r\ncontentFeatures.dlna.org: $FEATURES\r\nConnection: close\r\n")
            if (partial) headLines.append("Content-Range: bytes $start-$end/$size\r\n")
            output.write(headLines.append("\r\n").toString().toByteArray())
            if (!headOnly) {
                file.inputStream().use { source ->
                    var skipped = 0L
                    while (skipped < start) skipped += source.skip(start - skipped).takeIf { it > 0 } ?: break
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

        companion object {
            const val TTL_MS = 12 * 3600 * 1000L
        }
    }
}
