package vn.abook.player

import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.ServerSocket
import java.net.Socket
import java.net.URL
import java.util.UUID

/**
 * Loa giả DLNA cho bài thử (JVM: DlnaTest; trên máy Android: DlnaOnDeviceTest) - cư xử như scripts/fake_renderer.py của máy
 * tính: trả lời SSDP (cổng UDP riêng, gửi thẳng), mô tả, SOAP AVTransport; chỉ tua khi đã chạy (701), hết bài về STOPPED vị
 * trí 0, không Pause được nếu `pause = false`; TẢI audio từ đường dẫn được đưa khi Play; vị trí chạy nhanh gấp `speed`.
 */
class FakeRenderer(val name: String, private val speed: Double = 1.0, private val pause: Boolean = true) {
    val udn = "uuid:${UUID.randomUUID()}"
    val actions = mutableListOf<Pair<String, Map<String, String>>>()
    val fetched = mutableListOf<Int>()
    private var state = "NO_MEDIA_PRESENT"
    private var uri = ""
    private var duration = 0.0
    private var offset = 0.0
    private var since = 0L
    private val http = ServerSocket().apply { bind(InetSocketAddress("127.0.0.1", 0)) }
    private val udp = DatagramSocket(InetSocketAddress("127.0.0.1", 0))
    var description: () -> String = ::describe

    val location get() = "http://127.0.0.1:${http.localPort}/description.xml"
    val ssdp get() = InetSocketAddress("127.0.0.1", udp.localPort)

    @Synchronized
    fun position(): Double {
        if (state != "PLAYING") return offset
        val at = offset + (System.currentTimeMillis() - since) / 1000.0 * speed
        if (duration > 0 && at >= duration) {
            state = "STOPPED"
            offset = 0.0
            return 0.0
        }
        return at
    }

    @Synchronized fun state(): String = position().let { state }
    @Synchronized fun uri(): String = uri
    @Synchronized fun takeover(other: String) {
        uri = other
        state = "PLAYING"
        offset = 0.0
        since = System.currentTimeMillis()
    }
    fun calls(name: String) = synchronized(this) { actions.filter { it.first == name }.map { it.second } }

    fun start(): FakeRenderer {
        Thread {
            while (!http.isClosed) {
                val client = runCatching { http.accept() }.getOrNull() ?: break
                Thread { runCatching { client.use(::serve) } }.apply { isDaemon = true }.start()
            }
        }.apply { isDaemon = true }.start()
        Thread {
            val buffer = ByteArray(8192)
            while (!udp.isClosed) {
                val packet = DatagramPacket(buffer, buffer.size)
                runCatching { udp.receive(packet) }.onFailure { return@Thread }
                val text = String(packet.data, 0, packet.length)
                if (!text.startsWith("M-SEARCH") || Dlna.MEDIA_RENDERER !in text) continue
                val answer = ("HTTP/1.1 200 OK\r\nCACHE-CONTROL: max-age=1800\r\nEXT:\r\nLOCATION: $location\r\n" +
                    "ST: ${Dlna.MEDIA_RENDERER}\r\nUSN: $udn::${Dlna.MEDIA_RENDERER}\r\n\r\n").toByteArray()
                runCatching { udp.send(DatagramPacket(answer, answer.size, packet.socketAddress)) }
            }
        }.apply { isDaemon = true }.start()
        return this
    }

    fun stop() {
        http.close()
        udp.close()
    }

    /** HTTP/1.1 tối thiểu (android.jar không có com.sun.net.httpserver): mô tả + SOAP, mỗi kết nối một yêu cầu. */
    private fun serve(client: Socket) {
        val input = client.getInputStream().buffered()
        val head = StringBuilder()
        while (!head.endsWith("\r\n\r\n")) {
            val byte = input.read()
            if (byte < 0) return
            head.append(byte.toChar())
        }
        val lines = head.split("\r\n")
        val (method, path) = lines.first().split(" ").let { it[0] to it[1] }
        val headers = lines.drop(1).mapNotNull { line ->
            val colon = line.indexOf(':')
            if (colon > 0) line.substring(0, colon).trim().lowercase() to line.substring(colon + 1).trim() else null
        }.toMap()
        val length = headers["content-length"]?.toIntOrNull() ?: 0
        val body = ByteArray(length).also { buffer ->
            var read = 0
            while (read < length) read += input.read(buffer, read, length - read).takeIf { it > 0 } ?: break
        }.toString(Charsets.UTF_8)
        val reply: Pair<Int, String> = if (method == "GET" && path == "/description.xml") {
            200 to description()
        } else {
            val action = headers["soapaction"].orEmpty().trim('"').substringAfter('#')
            val args = Regex("<([A-Za-z]+)>([^<]*)</\\1>").findAll(body).associate { it.groupValues[1] to unescape(it.groupValues[2]) }
            try {
                val out = handle(action, args)
                200 to ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\"><s:Body>" +
                    "<u:${action}Response xmlns:u=\"urn:schemas-upnp-org:service:AVTransport:1\">" +
                    out.entries.joinToString("") { "<${it.key}>${escape(it.value)}</${it.key}>" } +
                    "</u:${action}Response></s:Body></s:Envelope>")
            } catch (error: IllegalStateException) {
                500 to ("<?xml version=\"1.0\"?><s:Envelope xmlns:s=\"http://schemas.xmlsoap.org/soap/envelope/\"><s:Body><s:Fault>" +
                    "<detail><UPnPError xmlns=\"urn:schemas-upnp-org:control-1-0\"><errorCode>${error.message}</errorCode>" +
                    "<errorDescription>x</errorDescription></UPnPError></detail></s:Fault></s:Body></s:Envelope>")
            }
        }
        val bytes = reply.second.toByteArray()
        val reason = if (reply.first == 200) "OK" else "Internal Server Error"
        client.getOutputStream().apply {
            write(("HTTP/1.1 ${reply.first} $reason\r\nContent-Type: text/xml; charset=\"utf-8\"\r\n" +
                "Content-Length: ${bytes.size}\r\nConnection: close\r\n\r\n").toByteArray())
            write(bytes)
            flush()
        }
    }

    private fun describe() = "<?xml version=\"1.0\"?><root xmlns=\"urn:schemas-upnp-org:device-1-0\"><device>" +
        "<deviceType>${Dlna.MEDIA_RENDERER}</deviceType><friendlyName>${escape(name)}</friendlyName>" +
        "<manufacturer>ABook</manufacturer><modelName>Fake renderer</modelName><UDN>$udn</UDN><serviceList>" +
        "<service><serviceType>urn:schemas-upnp-org:service:AVTransport:1</serviceType>" +
        "<controlURL>/AVTransport/control</controlURL></service></serviceList></device></root>"

    @Synchronized
    private fun handle(action: String, args: Map<String, String>): Map<String, String> {
        actions += action to args
        position()
        when (action) {
            "SetAVTransportURI" -> {
                uri = args["CurrentURI"].orEmpty()
                duration = Dlna.secondsOf(Regex("duration=\"([^\"]+)\"").find(args["CurrentURIMetaData"].orEmpty())?.groupValues?.get(1))
                state = "STOPPED"
                offset = 0.0
            }
            "Play" -> {
                if (uri.isEmpty()) error("701")
                if (state != "PLAYING") {
                    val fresh = state != "PAUSED_PLAYBACK"
                    state = "PLAYING"
                    since = System.currentTimeMillis()
                    if (fresh) {
                        val target = uri
                        Thread { fetch(target) }.start()
                    }
                }
            }
            "Pause" -> {
                if (!pause) error("401")
                if (state == "PLAYING") {
                    offset = position()
                    state = "PAUSED_PLAYBACK"
                }
            }
            "Stop" -> {
                offset = 0.0
                state = if (uri.isEmpty()) "NO_MEDIA_PRESENT" else "STOPPED"
            }
            "Seek" -> {
                if (state != "PLAYING" && state != "PAUSED_PLAYBACK") error("701")
                offset = Dlna.secondsOf(args["Target"])
                since = System.currentTimeMillis()
            }
            "GetTransportInfo" -> return mapOf("CurrentTransportState" to state, "CurrentTransportStatus" to "OK")
            "GetPositionInfo" -> return mapOf("TrackDuration" to Dlna.clock(duration), "TrackURI" to uri, "RelTime" to Dlna.clock(position()))
            else -> error("401")
        }
        return emptyMap()
    }

    private fun fetch(target: String) {
        val connection = URL(target).openConnection(Proxy.NO_PROXY) as HttpURLConnection
        connection.setRequestProperty("Range", "bytes=0-")
        val count = runCatching { connection.inputStream.use { it.readBytes().size } }.getOrDefault(-1)
        synchronized(this) { fetched += count }
    }

    private fun escape(value: String) = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\"", "&quot;")
    private fun unescape(value: String) = value.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", "\"").replace("&amp;", "&")
}
