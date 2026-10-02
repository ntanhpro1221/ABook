package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Proxy
import java.net.SocketTimeoutException
import java.net.URL
import java.security.KeyStore
import java.util.Base64
import java.util.UUID
import javax.net.ssl.KeyManagerFactory
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLServerSocket
import javax.net.ssl.SSLSocket

/**
 * Chromecast / Google TV / loa Nest giả cho bài thử (JVM: GCastTest) - cư xử như scripts/fake_cast_receiver.py của máy
 * tính: trả lời mDNS `_googlecast._tcp.local` (cổng UDP riêng, gửi thẳng), nghe CASTV2 qua TLS thật trên 127.0.0.1 và nói đủ
 * bốn kênh (connection, heartbeat, receiver, media) như Default Media Receiver. "Phát" là TẢI file từ đúng URL được đưa
 * (kiểm điện thoại phục vụ đúng, có CORS) - KHÔNG bao giờ giải mã hay phát audio - rồi cho vị trí chạy theo đồng hồ (nhanh
 * gấp `speed` lần), hết thì IDLE / FINISHED.
 *
 * Chiêu trò cho bài thử: [takeover] (máy khác phát thứ khác), [stopApp] (bấm dừng trên TV), [interrupt], [sleep] / [wake]
 * (thiết bị tắt nguồn: nối không được, đang nối thì đứt), [refuseLoad] (LOAD_FAILED), [failFetch]. Ghi lại mọi lệnh
 * ([actions] - "kênh.LOẠI") và mọi lần tải ([fetches]). Khung tin viết lại ĐỘC LẬP với GCast.kt (để bài thử so hai bên).
 */
class FakeCastReceiver(
    val name: String = "Loa Nest thử",
    private val speed: Double = 1.0,
    private val duration: Double = 10.0,
    private val video: Boolean = false,
    private val model: String = "Chromecast",
) {
    class Fetch(val url: String, var status: Int = 0, var bytes: Int = 0, var type: String = "", var cors: String = "", var error: String = "")

    var deviceId: String = UUID.randomUUID().toString().replace("-", "")
    var advertisedHost = "127.0.0.1" // địa chỉ A trong trả lời mDNS (bài thử đặt chỗ khác để xem điện thoại có bị lừa không)

    @Volatile var refuseLoad = false

    @Volatile var failFetch = false // không tải được URL (tường lửa chặn): LOAD vẫn nhận, rồi IDLE / ERROR
    val actions = mutableListOf<Pair<String, JSONObject>>()
    val fetches = mutableListOf<Fetch>()

    @Volatile var pings = 0

    @Volatile var connections = 0
    private val lock = Any()
    private val clients = mutableListOf<Client>()

    @Volatile private var asleep = false
    private var app: JSONObject? = null
    private var apps = 0
    private var msid = 0
    private var content = ""
    private var type = ""
    private var metadata = JSONObject()
    private var state = "IDLE"
    private var idle = ""
    private var offset = 0.0
    private var since = 0.0
    private var loaded = 0.0
    private var autoplay = true
    private var listener: SSLServerSocket? = null
    private var udp: DatagramSocket? = null

    @Volatile private var stopping = false

    private class Client(val sock: SSLSocket) {
        var sender = ""
        val connected = mutableSetOf<String>() // kết nối ảo: "receiver-0", transportId
        var buffer = ByteArray(0)

        @Synchronized
        fun send(source: String, namespace: String, payload: JSONObject) {
            runCatching {
                sock.outputStream.write(pack(source, sender, namespace, payload.toString()))
                sock.outputStream.flush()
            }
        }
    }

    // -- máy chủ ----------------------------------------------------------------------------------------------------------

    fun start(): FakeCastReceiver {
        val keys = KeyStore.getInstance("PKCS12").apply { load(ByteArrayInputStream(Base64.getDecoder().decode(KEYSTORE)), PASSWORD) }
        val factory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm()).apply { init(keys, PASSWORD) }
        val context = SSLContext.getInstance("TLS").apply { init(factory.keyManagers, null, null) }
        listener = (context.serverSocketFactory.createServerSocket(0, 8, InetAddress.getByName("127.0.0.1")) as SSLServerSocket)
        udp = DatagramSocket(InetSocketAddress("127.0.0.1", 0))
        daemon("fake-cast-accept") {
            while (!stopping) {
                val raw = runCatching { listener!!.accept() as SSLSocket }.getOrNull() ?: break
                daemon("fake-cast-client") { serve(raw) }
            }
        }
        daemon("fake-cast-mdns") { answer() }
        daemon("fake-cast-tick") { tick() }
        return this
    }

    val port: Int get() = listener!!.localPort
    val mdns: InetSocketAddress get() = InetSocketAddress("127.0.0.1", udp!!.localPort)

    fun stop() {
        stopping = true
        dropAll()
        runCatching { listener?.close() }
        runCatching { udp?.close() }
    }

    private fun daemon(name: String, body: () -> Unit) = Thread(body, name).apply { isDaemon = true }.start()

    private fun serve(sock: SSLSocket) {
        if (asleep) {
            runCatching { sock.close() } // tắt nguồn: nối được TCP rồi cụt - bắt tay TLS hỏng
            return
        }
        var client: Client? = null
        try {
            sock.soTimeout = 10_000
            sock.startHandshake()
            sock.soTimeout = 200
            client = Client(sock)
            synchronized(lock) {
                clients += client
                connections++
            }
            val buffer = ByteArray(65536)
            while (!stopping) {
                val count = try {
                    sock.inputStream.read(buffer)
                } catch (_: SocketTimeoutException) {
                    continue
                }
                if (count < 0) break
                client.buffer += buffer.copyOf(count)
                while (client.buffer.size >= 4) {
                    val size = ((client.buffer[0].toInt() and 0xFF) shl 24) or ((client.buffer[1].toInt() and 0xFF) shl 16) or
                        ((client.buffer[2].toInt() and 0xFF) shl 8) or (client.buffer[3].toInt() and 0xFF)
                    if (client.buffer.size < 4 + size) break
                    val body = client.buffer.copyOfRange(4, 4 + size)
                    client.buffer = client.buffer.copyOfRange(4 + size, client.buffer.size)
                    val (source, destination, namespace, payload) = unpack(body)
                    handle(client, source, destination, namespace, if (payload.isEmpty()) JSONObject() else JSONObject(payload))
                }
            }
        } catch (_: Exception) {
        } finally {
            runCatching { sock.close() }
            client?.let { synchronized(lock) { clients.remove(it) } }
        }
    }

    private fun dropAll() {
        val gone = synchronized(lock) { clients.toList().also { clients.clear() } }
        gone.forEach { runCatching { it.sock.close() } }
    }

    // -- điều khiển cho bài thử ---------------------------------------------------------------------------------------------

    /** Tắt nguồn: đang nối thì đứt, nối mới thì không được, mDNS im. */
    fun sleep() {
        asleep = true
        dropAll()
    }

    fun wake() {
        asleep = false
    }

    /** Một người điều khiển khác phát thứ khác trên thiết bị (phiên phát mới). */
    fun takeover(url: String) {
        synchronized(lock) {
            msid++
            content = url
            state = "PLAYING"
            idle = ""
            offset = 0.0
            since = mono()
            pushMedia(includeMedia = true)
        }
    }

    /** Một người điều khiển khác đã mở Default Media Receiver trước khi điện thoại tới. */
    fun launch() = synchronized(lock) { launchApp() }

    private fun launchApp() {
        if (app != null) return
        apps++
        app = JSONObject().put("appId", APP_ID).put("displayName", "Default Media Receiver").put("isIdleScreen", false)
            .put("namespaces", JSONArray().put(JSONObject().put("name", NS_MEDIA)).put(JSONObject().put("name", NS_CONNECTION)))
            .put("sessionId", UUID.randomUUID().toString()).put("statusText", "Ready To Cast").put("transportId", "web-$apps")
            .put("universalAppId", APP_ID)
        msid = 0
        state = "IDLE"
        idle = ""
        content = ""
    }

    /** Bấm dừng trên TV / mở app khác: ứng dụng của người gửi biến mất. */
    fun stopApp() {
        synchronized(lock) {
            val gone = app
            app = null
            state = "IDLE"
            idle = "CANCELLED"
            offset = 0.0
            if (gone != null) {
                val transport = gone.getString("transportId")
                for (client in clients.toList()) {
                    if (transport in client.connected) {
                        client.send(transport, NS_CONNECTION, JSONObject().put("type", "CLOSE"))
                        client.connected.remove(transport)
                    }
                }
            }
            pushReceiver()
        }
    }

    /** Phiên phát hiện tại bị cắt (IDLE / INTERRUPTED) - như khi máy khác LOAD đè. */
    fun interrupt() {
        synchronized(lock) {
            state = "IDLE"
            idle = "INTERRUPTED"
            pushMedia()
        }
    }

    fun state(): String = synchronized(lock) { state }
    fun content(): String = synchronized(lock) { content }
    fun appRunning(): Boolean = synchronized(lock) { app != null }
    fun position(): Double = synchronized(lock) { position0() }
    fun calls(name: String): List<JSONObject> = synchronized(lock) { actions.filter { it.first == name }.map { it.second } }
    fun names(): List<String> = synchronized(lock) { actions.map { it.first } }
    fun metadata(): JSONObject = synchronized(lock) { metadata }

    // -- trạng thái phát ----------------------------------------------------------------------------------------------------

    private fun mono() = System.nanoTime() / 1e9

    private fun position0(): Double {
        if (state != "PLAYING") return offset
        val at = offset + (mono() - since) * speed
        return if (duration > 0) minOf(at, duration) else at
    }

    private fun entry(includeMedia: Boolean = false): JSONObject {
        val out = JSONObject().put("mediaSessionId", msid).put("playbackRate", speed).put("playerState", state)
            .put("currentTime", Math.round(position0() * 1000) / 1000.0).put("supportedMediaCommands", 274447)
            .put("volume", JSONObject().put("level", 1.0).put("muted", false)).put("currentItemId", 1).put("repeatMode", "REPEAT_OFF")
        if (state == "IDLE" && idle.isNotEmpty()) out.put("idleReason", idle)
        if (includeMedia) {
            out.put("media", JSONObject().put("contentId", content).put("streamType", "BUFFERED").put("contentType", type)
                .put("metadata", metadata).put("duration", duration))
        }
        return out
    }

    /** Tin MEDIA_STATUS tới người nối vào ứng dụng ([only]: chỉ người ấy, kèm requestId trả lời). */
    private fun pushMedia(includeMedia: Boolean = false, only: Client? = null, request: Int = 0) {
        val current = app ?: return
        if (msid == 0) return
        val transport = current.getString("transportId")
        val payload = JSONObject().put("type", "MEDIA_STATUS").put("requestId", request).put("status", JSONArray().put(entry(includeMedia)))
        for (client in clients.toList()) if (transport in client.connected && (only == null || client === only)) client.send(transport, NS_MEDIA, payload)
    }

    private fun pushReceiver(only: Client? = null, request: Int = 0) {
        val status = JSONObject().put("isActiveInput", true).put("volume", JSONObject().put("level", 1.0).put("muted", false))
        app?.let { status.put("applications", JSONArray().put(it)) }
        val payload = JSONObject().put("type", "RECEIVER_STATUS").put("requestId", request).put("status", status)
        for (client in clients.toList()) if ("receiver-0" in client.connected && (only == null || client === only)) client.send("receiver-0", NS_RECEIVER, payload)
    }

    private fun tick() {
        while (!stopping) {
            Thread.sleep(50)
            synchronized(lock) {
                if (state == "BUFFERING" && mono() - loaded >= 0.05) {
                    state = if (autoplay) "PLAYING" else "PAUSED"
                    since = mono()
                    pushMedia()
                } else if (state == "PLAYING" && duration > 0 && position0() >= duration) {
                    state = "IDLE"
                    idle = "FINISHED"
                    offset = duration
                    pushMedia()
                }
            }
        }
    }

    private fun fetch(url: String, id: Int) {
        val record = Fetch(url)
        try {
            if (failFetch) throw java.io.IOException("bị chặn")
            val connection = URL(url).openConnection(Proxy.NO_PROXY) as HttpURLConnection
            connection.setRequestProperty("Range", "bytes=0-")
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            record.status = connection.responseCode
            record.type = connection.getHeaderField("Content-Type").orEmpty()
            record.cors = connection.getHeaderField("Access-Control-Allow-Origin").orEmpty()
            connection.inputStream.use { stream ->
                val buffer = ByteArray(65536)
                while (true) {
                    val count = stream.read(buffer)
                    if (count < 0) break
                    record.bytes += count
                }
            }
        } catch (error: Exception) { // thiết bị thật cũng chỉ báo "không tải được"
            record.error = error.message ?: error.javaClass.simpleName
        }
        synchronized(lock) {
            fetches += record
            if (record.error.isNotEmpty() && msid == id && state != "IDLE") {
                state = "IDLE"
                idle = "ERROR" // không tải được (tường lửa...): lỗi sau khi đã nhận LOAD
                pushMedia()
            }
        }
    }

    // -- tin nhận được -------------------------------------------------------------------------------------------------------

    private fun handle(client: Client, source: String, destination: String, namespace: String, payload: JSONObject) {
        val kind = payload.optString("type")
        val request = (payload.opt("requestId") as? Int) ?: 0
        synchronized(lock) {
            if (kind == "PING") pings++ else actions += "${SHORT[namespace] ?: namespace}.$kind" to payload
            client.sender = source
            when (namespace) {
                NS_HEARTBEAT -> if (kind == "PING") client.send(destination, namespace, JSONObject().put("type", "PONG"))
                NS_CONNECTION -> if (kind == "CONNECT") client.connected += destination else if (kind == "CLOSE") client.connected -= destination
                NS_RECEIVER -> receiver(client, kind, request, payload)
                NS_MEDIA -> media(client, destination, kind, request, payload)
            }
            Unit
        }
    }

    private fun receiver(client: Client, kind: String, request: Int, payload: JSONObject) {
        when (kind) {
            "GET_STATUS" -> pushReceiver(client, request)
            "LAUNCH" -> {
                if (payload.optString("appId") != APP_ID) {
                    client.send("receiver-0", NS_RECEIVER, JSONObject().put("type", "LAUNCH_ERROR").put("requestId", request).put("reason", "NOT_FOUND"))
                    return
                }
                launchApp()
                pushReceiver(client, request)
                pushReceiver()
            }
            "STOP" -> {
                val current = app
                if (current != null && payload.optString("sessionId") == current.getString("sessionId")) {
                    val transport = current.getString("transportId")
                    app = null
                    state = "IDLE"
                    idle = "CANCELLED"
                    offset = 0.0
                    clients.forEach { it.connected.remove(transport) }
                }
                pushReceiver(client, request)
                pushReceiver()
            }
            else -> client.send("receiver-0", NS_RECEIVER, JSONObject().put("type", "INVALID_REQUEST").put("requestId", request).put("reason", "INVALID_COMMAND"))
        }
    }

    private fun media(client: Client, destination: String, kind: String, request: Int, payload: JSONObject) {
        val current = app
        if (current == null || destination != current.getString("transportId")) {
            client.send(destination, NS_MEDIA, JSONObject().put("type", "INVALID_REQUEST").put("requestId", request).put("reason", "INVALID_APP_SESSION"))
            return
        }
        val transport = current.getString("transportId")
        if (kind == "LOAD") {
            if (refuseLoad) {
                client.send(transport, NS_MEDIA, JSONObject().put("type", "LOAD_FAILED").put("requestId", request).put("detail", JSONObject().put("itemId", 1)))
                return
            }
            val item = payload.optJSONObject("media") ?: JSONObject()
            if (msid != 0 && state != "IDLE") { // LOAD đè lên bài đang phát: bài cũ nhận INTERRUPTED trước
                state = "IDLE"
                idle = "INTERRUPTED"
                pushMedia()
            }
            msid++
            content = item.optString("contentId")
            type = item.optString("contentType")
            metadata = item.optJSONObject("metadata") ?: JSONObject()
            autoplay = payload.optBoolean("autoplay", true)
            state = "BUFFERING"
            idle = ""
            offset = payload.optDouble("currentTime", 0.0)
            since = mono()
            loaded = since
            pushMedia(includeMedia = true, only = client, request = request)
            pushMedia(includeMedia = true) // người khác nối vào ứng dụng cũng thấy
            val id = msid
            val url = content
            daemon("fake-cast-fetch") { fetch(url, id) }
            return
        }
        if (kind == "GET_STATUS") {
            val status = JSONArray().also { if (msid != 0) it.put(entry()) }
            client.send(transport, NS_MEDIA, JSONObject().put("type", "MEDIA_STATUS").put("requestId", request).put("status", status))
            return
        }
        if (msid == 0 || payload.optInt("mediaSessionId", -1) != msid) {
            client.send(transport, NS_MEDIA, JSONObject().put("type", "INVALID_REQUEST").put("requestId", request).put("reason", "INVALID_MEDIA_SESSION_ID"))
            return
        }
        when (kind) {
            "PLAY" -> if (state == "PAUSED") {
                state = "PLAYING"
                since = mono()
            }
            "PAUSE" -> if (state == "PLAYING" || state == "BUFFERING") {
                offset = position0()
                state = "PAUSED"
                autoplay = false
            }
            "SEEK" -> {
                val target = payload.optDouble("currentTime", 0.0)
                offset = if (duration > 0) minOf(target, duration) else target
                since = mono()
            }
            "STOP" -> {
                offset = 0.0
                state = "IDLE"
                idle = "CANCELLED"
            }
            else -> {
                client.send(transport, NS_MEDIA, JSONObject().put("type", "INVALID_REQUEST").put("requestId", request).put("reason", "INVALID_COMMAND"))
                return
            }
        }
        pushMedia(only = client, request = request)
        pushMedia()
    }

    // -- mDNS ---------------------------------------------------------------------------------------------------------------

    private fun answer() {
        val buffer = ByteArray(4096)
        while (!stopping) {
            val packet = DatagramPacket(buffer, buffer.size)
            try {
                udp!!.receive(packet)
            } catch (_: Exception) {
                return
            }
            val data = packet.data.copyOf(packet.length)
            if (asleep || data.size < 12 || data[2].toInt() and 0x80 != 0 || String(data, Charsets.ISO_8859_1).indexOf("\u000b_googlecast") < 0) continue
            val reply = mdnsResponse(data.copyOf(2))
            runCatching { udp!!.send(DatagramPacket(reply, reply.size, packet.socketAddress)) }
        }
    }

    /**
     * Trả lời kiểu "kế thừa" (RFC 6762 §6.7): lặp lại câu hỏi, TTL ngắn, tên nén. PTR ở phần trả lời; SRV, TXT, A ở phần
     * thêm. Cùng cách dựng với `FakeCastReceiver.mdns_response` của máy tính.
     */
    fun mdnsResponse(ident: ByteArray = byteArrayOf(0, 0), servicePort: Int = port): ByteArray {
        val label = (name.replace(Regex("[^A-Za-z0-9]+"), "-").trim('-') + "-" + deviceId.take(12)).toByteArray(Charsets.US_ASCII)
        val host = deviceId.take(12).toByteArray(Charsets.US_ASCII)
        val data = ByteArrayOutputStream()
        fun u16(value: Int) = data.write(byteArrayOf((value shr 8).toByte(), value.toByte()))
        fun u32(value: Int) = data.write(byteArrayOf((value shr 24).toByte(), (value shr 16).toByte(), (value shr 8).toByte(), value.toByte()))
        fun pointer(at: Int) = u16(0xC000 or at)
        data.write(ident)
        u16(0x8400); u16(1); u16(1); u16(0); u16(3)
        val question = data.size() // = 12
        for (part in "_googlecast._tcp.local".split('.')) {
            data.write(part.length)
            data.write(part.toByteArray())
        }
        data.write(0)
        u16(12); u16(1)
        val local = question + 1 + "_googlecast".length + 1 + "_tcp".length // vị trí nhãn "local"
        pointer(question); u16(12); u16(1); u32(10)
        // PTR: dữ liệu là tên thể hiện (nhãn + con trỏ tới tên dịch vụ)
        u16(1 + label.size + 2)
        val instance = data.size()
        data.write(label.size)
        data.write(label)
        pointer(question)
        // SRV: tên nén trỏ tới tên thể hiện; mục tiêu "<host>.local" nén vào nhãn "local"
        pointer(instance); u16(33); u16(1); u32(10)
        u16(6 + 1 + host.size + 2)
        u16(0); u16(0); u16(servicePort)
        val target = data.size()
        data.write(host.size)
        data.write(host)
        pointer(local)
        // TXT
        val pairs = listOf("id" to deviceId, "cd" to deviceId.uppercase(), "rm" to "", "ve" to "05", "md" to model,
            "ic" to "/setup/icon.png", "fn" to name, "ca" to if (video) "5" else "4", "st" to "0", "bs" to "FA8FCA000000", "nf" to "1", "rs" to "")
        val text = ByteArrayOutputStream()
        for ((key, value) in pairs) {
            val item = "$key=$value".toByteArray()
            text.write(item.size)
            text.write(item)
        }
        pointer(instance); u16(16); u16(1); u32(4500); u16(text.size())
        data.write(text.toByteArray())
        // A
        pointer(target); u16(1); u16(1); u32(10); u16(4)
        data.write(InetAddress.getByName(advertisedHost).address)
        return data.toByteArray()
    }

    companion object {
        const val APP_ID = "CC1AD845"
        const val NS_CONNECTION = "urn:x-cast:com.google.cast.tp.connection"
        const val NS_HEARTBEAT = "urn:x-cast:com.google.cast.tp.heartbeat"
        const val NS_RECEIVER = "urn:x-cast:com.google.cast.receiver"
        const val NS_MEDIA = "urn:x-cast:com.google.cast.media"
        private val SHORT = mapOf(NS_CONNECTION to "connection", NS_HEARTBEAT to "heartbeat", NS_RECEIVER to "receiver", NS_MEDIA to "media")
        private val PASSWORD = "changeit".toCharArray()

        private fun varint(number: Int): ByteArray {
            var value = number
            val out = ByteArrayOutputStream()
            do {
                val low = value and 0x7F
                value = value ushr 7
                out.write(if (value != 0) low or 0x80 else low)
            } while (value != 0)
            return out.toByteArray()
        }

        private fun field(number: Int, value: String): ByteArray {
            val data = value.toByteArray(Charsets.UTF_8)
            return varint(number shl 3 or 2) + varint(data.size) + data
        }

        /** Khung tin: 4 byte độ dài + CastMessage viết tay, trường theo thứ tự 1 (=0), 2, 3, 4, 5 (=0), 6. */
        fun pack(source: String, destination: String, namespace: String, payload: String): ByteArray {
            val body = byteArrayOf(0x08, 0x00) + field(2, source) + field(3, destination) + field(4, namespace) + byteArrayOf(0x28, 0x00) + field(6, payload)
            val size = body.size
            return byteArrayOf((size shr 24).toByte(), (size shr 16).toByte(), (size shr 8).toByte(), size.toByte()) + body
        }

        fun unpack(body: ByteArray): List<String> {
            val fields = HashMap<Int, ByteArray>()
            var at = 0
            fun varint(): Int {
                var value = 0
                var shift = 0
                while (true) {
                    val byte = body[at++].toInt() and 0xFF
                    value = value or ((byte and 0x7F) shl shift)
                    if (byte and 0x80 == 0) return value
                    shift += 7
                }
            }
            while (at < body.size) {
                val key = varint()
                when (key and 7) {
                    0 -> varint()
                    2 -> {
                        val size = varint()
                        fields[key shr 3] = body.copyOfRange(at, at + size)
                        at += size
                    }
                    else -> throw IllegalArgumentException("kiểu trường lạ")
                }
            }
            return listOf(2, 3, 4, 6).map { String(fields[it] ?: ByteArray(0), Charsets.UTF_8) }
        }

        // Khoá + chứng chỉ TỰ KÝ chỉ để bài thử có TLS thật (như thiết bị Cast thật: chứng chỉ không kiểm được); sinh bằng
        // keytool (RSA 2048, PKCS12 kiểu cũ để Android cũng đọc được), không phải khoá của ai và không bảo vệ gì.
        private val KEYSTORE =
            "MIIJdwIBAzCCCTAGCSqGSIb3DQEHAaCCCSEEggkdMIIJGTCCBWUGCSqGSIb3DQEHAaCCBVYEggVSMIIFTjCCBUoGCyqGSIb3DQEM" +
            "CgECoIIE+zCCBPcwKQYKKoZIhvcNAQwBAzAbBBT4GYYBab8TiI7ylpPjE4V3ShIdFQIDAMNQBIIEyIqfOgE/u/pUJFV5CUKVUkuG" +
            "lADx5jEFqu4Ip+eEANW77YMERvPE5MOg7M9sZKMkZqo3Wgv4mJkICUoLWyPUgVbfhUArpcCGD4hxMeuyCYb1N8E6NiTgW0S42iG/" +
            "sUc2uSaJtYwKWjAfAHnQjBdnzif9sqKES8C/i/6Xc3rjN4DR7t1VWOsQ9YwIr8lmwIR9VXS/MYmOtKpV+5jfoo7Eu23bxKG7riQz" +
            "NT4S7atcBpGNc0d4JyEE50an6Zjx4XJRvqkUUOC4vIq5+eY8t/vDvWUGIFUseyVRje6G+c6o0/7IRnNgC/mhIR9LyQt+M55+7N9i" +
            "scAHyWx9l8SayqNn2OVVY5CNANoaiNtlo8p9kVXlyubr9nLvkbG3VQfLZMcX3aKs7/xI2OyM63ncffkCzlyVe8TwjzK0VMb2pWCP" +
            "sceDZna2o7AvKxGP63wp0msHoUWvPmJ8on7ma1vC7cbDJ+OF+gJlQQx63jYVF1xT+T4gExJuccVc94G2Tf4Tz/7QxLQ6t1b5IhOt" +
            "vCiVqI1czeWGe3XljWi/QCjiohSoPt3mZeVRKZv2OMwAi4pq8H4w4Y+OAeGWCPOo+tEN6yBPkgG8JEsCxkl+24G3ibKn4CQnncGo" +
            "ZdFmyXJ4Ur9zw8+nE7QW17+FTd62SKSf3jTcGjiS9nuNEXTfkBEJhc2St3caZIDDcB0DwQB+IcSOG64p1+s1/1POwydu66aS6niF" +
            "IgRBhTRzkGzbhAQCYBJsBmiCEAcTSdWG4InHayRU367v05wk6rxfSZv8WeKqb5SvKq/0IvIFnhlvV0a6K+Qwg7g5yFhH7sJcDwVJ" +
            "9Is9xBSTMFDNnY13d1S4GRJoBPlLpJnf6ekWIr2K9ATOVtmYBbUZHNgGNX26q1zrhSGTD6KULJJ0P4j927aXzAvdVxVZfisMo3qn" +
            "nP0BQBjqLDqcFgcOXCjP/mwXeAmzYK3MN5Be/MRu41hcbKbon6R49M+aXbgJMgsjPJizWIp95myxKSom8W0x03TVzT1T1al4Aqo6" +
            "ymbhOQGaZ7Fbutk5WG92nq7oyQ8WLNjY89ybkx1g1tZo0B/M4t/JmsXye6FeIGJuMZgk+2+aj9sBblgG1qXsnkQx8e2lwByPJJQI" +
            "mQl/f3VPo6fWJJ8D8BIDnl0XKzm+ClYYSnRrwti7LszVqEdOYCUGtyD2tAebDVzCtSDKmbO8UDXxWMT4JchKxq9+Ecx86ZTeUzut" +
            "Bemt9Lztp9dckJ/N+Wq4FLDrWh8HQFRjJJYwf9BRae/Q98r/2wZdWaN9aB/z1pUe2+T9YlMDSzPt5ndMgNPn8xAO1F0MJ2rMulMQ" +
            "zUxRIWjGWl2QzFt49++Shsa3LCv/s7LQ/VOIXabQ+h9KvKbPC3HeeF4xlhBmp7ssO+eZTjRfhXX+/yFgDKdGsSruo+BdnD309zVu" +
            "fH7SdvhnH6AsFF8t8uOPuGNaxBf3To6BNgvuI8PmFqxfFAYWnLHHj194+QR2idLYstm4YD5KP7Co3RwH+w5vKPWEux2fH1dQEojz" +
            "nWz7jLm7Lgt42nfEC7zUV+h3zR4cubOZy+mMpXYqCwrEMc/y+3tx4OEQ26CI3USdZzz21A5sDL6hc1lND+OdYw3X1ZnJkW92AmzT" +
            "ha8kBnBUmDE8MBcGCSqGSIb3DQEJFDEKHggAZgBhAGsAZTAhBgkqhkiG9w0BCRUxFAQSVGltZSAxNzkwOTM1MjkyMjAzMIIDrAYJ" +
            "KoZIhvcNAQcGoIIDnTCCA5kCAQAwggOSBgkqhkiG9w0BBwEwKQYKKoZIhvcNAQwBBjAbBBRGC+2TUI6TQaxMzx+6S8uojKqR/wID" +
            "AMNQgIIDWMNND338iieKNQPFcKAlCyTGA4tL3IA+pfkAsWgTL1bUjc7CXq5WhGdt3sF/UtUxuHBitogxZVmodvt0Ki9+Wa712aAq" +
            "ZiqV8egLeT+qUGQ8Pjga2zgqPvsutb9q9UQnYwTrRsXagpHYSyAqb0oDZrh4BvFGGzRb2H/bl9BR4abORJrTlzV5i8tuinWKESIe" +
            "fe4qNBwoYB7yp5lohjcI7XuZGQ1i8xsG8gcXV7BPgrYksUJGHEHmX2cAE8AJhiMVwAxfmwkO3CoIkRwamJ/UpYnj9ALBmbD72AQv" +
            "/aNUGGOTzOQCAkEAbDTc9tXyuOAGe5/sRvjUHcnKtbmarZylFKNRrbFi3S8uR0xYQgMcfP8dcdFCOKOG6SayBf7mkwBGWd1BPg6r" +
            "zQGe/jPglUen45WEjs3dVSw8dza9WyPmFKAL8W48PIA3D18Sn7zmWkg6zfQ6244bSOx866uZQlt8Ihh86QYZURRLrgE6bEVYNvOU" +
            "kYvp/lBTpoXKN53FCNMSX/xaFl/GPHtJEewg7OeYVp04umr25XamSs0p5KLNn5zimjTSxRBC6l83sdW9HNhGSDKYlKyqodRkgzgK" +
            "qRWf7RrJ8erQPbPlDZYn9Iifd/CfEihCP56gWnPZPApsZvkSSTsWjGyYF6SYDSRBtD2kfchtcHwLirX9wLLFzJMs8DLy90jJz2Ww" +
            "5KYQi9mu6yD2FJf78ZH1rXDURV6OzwWLO74/XFcubzKUVLa9WBZNXrgqz6TU+OwD8hsgH//78pCICN51BwMEg9e87ZD/hXDF+22C" +
            "fcWYOCCWsU/kmfufeubX9UGiYDQm2hc9q5A8rU39Evh88sjysr9DUkN29RTcOg2AaU04UrYtjLuZFa/uaEYTFHfQGZDlweoxYNEX" +
            "+Tu/35YlGIlA45EH/L4cvInUzP0ROLYUWrO7bVhs+HCsZhsX6/XoGJObsDUWvEEunQpGLK93jXvfS6krq1ZXFhrH3a7qmlutgZTf" +
            "I041adgPkJAoVE8f5MZM7jCOnOP58D5Xz37smmrdf7NSrJPJNR5aBILmv5XZVyu8Akfln92Zf0qxx06IDzSNaHq4WgNxallMl4n5" +
            "JV5CSJ48DWw+3M3Wc6CVQSyOpb0HmsolSF+sShZs3hpz9sZQiBEwPjAhMAkGBSsOAwIaBQAEFC/vQPYmq9UJxDWa6ozjbN+Y31X8" +
            "BBSrJRtytG+XmkVGZl7elbjoHYEdgAIDAYag" 
    }
}
