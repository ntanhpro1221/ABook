package vn.abook.player

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketTimeoutException
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.locks.ReentrantLock
import javax.net.ssl.SSLContext
import javax.net.ssl.SSLEngine
import javax.net.ssl.SSLSocket
import javax.net.ssl.X509ExtendedTrustManager
import kotlin.concurrent.withLock

/**
 * Điện thoại phát sang Chromecast, Google TV, loa Nest bằng giao thức Cast (CASTV2) - 02-10, bên cạnh DLNA ([Dlna]). Bản
 * Kotlin của abook/webui/gcast.py trên máy tính, KHÔNG dùng Google Cast SDK / Play Services (một ứng dụng phát sách không
 * cần cả bộ SDK ấy): TÌM thiết bị bằng mDNS ([discover]) và NÓI CHUYỆN với một thiết bị ([GoogleCast], một [CastBackend]).
 *
 * Tìm: truy vấn mDNS `_googlecast._tcp.local` (PTR) gửi từ cổng TẠM với bit QU - theo RFC 6762 §6.7 thiết bị trả THẲNG về
 * cổng ấy (unicast), nên không cần MulticastLock, không cần quyền mới, không giành cổng 5353. Gửi ra từng card mạng như SSDP
 * ([Dlna.probe]). Thiết bị gói đủ trong một trả lời: PTR (tên), SRV (cổng), TXT (id, fn tên, md kiểu, ca khả năng), A.
 *
 * Nói: TLS tới cổng SRV (thường 8009) rồi CASTV2 - mỗi tin là 4 byte độ dài (big-endian) + một CastMessage protobuf viết tay.
 * Kênh: connection (CONNECT / CLOSE), heartbeat (PING mỗi 5 giây), receiver (mở "Default Media Receiver" CC1AD845), media
 * (LOAD, PLAY, PAUSE, SEEK, STOP). Một luồng đọc cho mỗi thiết bị giữ bản chụp tin mới nhất để [GoogleCast.status] không bao
 * giờ đợi mạng; vẫn nhịp PING và khi đứt thì tự nối lại.
 *
 * An toàn - trả lời mDNS là dữ liệu từ mạng LAN: chỉ nối tới ĐÚNG địa chỉ IP đã trả lời (A trong gói mà trỏ chỗ khác thì bỏ
 * thiết bị ấy), chỉ địa chỉ riêng / loopback; tin có trần 64 KiB; TLS không kiểm chứng chỉ (thiết bị Cast dùng chứng chỉ của
 * Google cấp theo máy, không có tên máy để kiểm) - cũng không gửi gì ngoài lệnh phát chương, và URL audio là cổng
 * [Dlna.Media] của điện thoại dưới mã ngẫu nhiên.
 */
object GCast {
    val MDNS_GROUP = InetSocketAddress("224.0.0.251", 5353)
    const val SERVICE = "_googlecast._tcp.local"
    const val CAST_PORT = 8009
    const val APP_ID = "CC1AD845" // Default Media Receiver: phát file audio / video theo URL
    const val NS_CONNECTION = "urn:x-cast:com.google.cast.tp.connection"
    const val NS_HEARTBEAT = "urn:x-cast:com.google.cast.tp.heartbeat"
    const val NS_RECEIVER = "urn:x-cast:com.google.cast.receiver"
    const val NS_MEDIA = "urn:x-cast:com.google.cast.media"
    const val MAX_FRAME = 64 * 1024
    private const val STRANGE = "thiết bị trả lời lạ"

    /** Các mốc giờ (mili giây); bài thử rút ngắn. */
    data class Timing(
        val connect: Int = 4000, // TLS tới thiết bị
        val reply: Long = 8000, // thiết bị trả lời một lệnh thường
        val launch: Long = 15_000, // mở ứng dụng phát (TV đánh thức màn hình mất vài giây)
        val load: Long = 15_000, // đưa chương: thiết bị báo bắt đầu tải
        val heartbeat: Long = 5000, // PING mỗi chừng ấy (thiết bị cũng bỏ người gửi im quá ~10 giây)
        val status: Long = 5000, // hỏi lại trạng thái phát mỗi chừng ấy (giữa hai lần, vị trí ước theo đồng hồ)
        val dead: Long = 15_000, // im lặng chừng ấy: coi như không trả lời, nối lại
        val reconnect: Long = 4000, // nối lại sau khi đứt: thử mỗi chừng ấy
        val tick: Int = 250, // luồng đọc tỉnh dậy mỗi chừng ấy để gửi PING, xem còn nghe được không
    )

    // ---- CastMessage (protobuf viết tay) -----------------------------------------------------------------------------

    private fun varint(number: Int): ByteArray {
        var value = number
        val out = ByteArrayOutputStream()
        while (true) {
            val low = value and 0x7F
            value = value ushr 7
            out.write(low or if (value != 0) 0x80 else 0)
            if (value == 0) return out.toByteArray()
        }
    }

    private fun text(out: ByteArrayOutputStream, number: Int, value: String) {
        val data = value.toByteArray(Charsets.UTF_8)
        out.write(varint(number shl 3 or 2))
        out.write(varint(data.size))
        out.write(data)
    }

    data class Message(val source: String, val destination: String, val namespace: String, val payload: String)

    /** CastMessage: 1 protocol_version = 0 (CASTV2_1_0), 2 source_id, 3 destination_id, 4 namespace, 5 payload_type = 0 (STRING), 6 payload_utf8. */
    fun encode(source: String, destination: String, namespace: String, payload: String): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(varint(1 shl 3))
        out.write(varint(0))
        text(out, 2, source)
        text(out, 3, destination)
        text(out, 4, namespace)
        out.write(varint(5 shl 3))
        out.write(varint(0))
        text(out, 6, payload)
        return out.toByteArray()
    }

    fun frame(message: ByteArray): ByteArray {
        val size = message.size
        return byteArrayOf((size ushr 24).toByte(), (size ushr 16).toByte(), (size ushr 8).toByte(), size.toByte()) + message
    }

    private fun readVarint(data: ByteArray, start: Int): Pair<Long, Int> {
        var offset = start
        var value = 0L
        var shift = 0
        while (true) {
            if (offset >= data.size || shift > 63) throw Dlna.Failure(STRANGE)
            val byte = data[offset++].toInt() and 0xFF
            value = value or ((byte and 0x7F).toLong() shl shift)
            if (byte and 0x80 == 0) return value to offset
            shift += 7
        }
    }

    /** Đọc một CastMessage: biết varint và chuỗi (length-delimited), trường lạ thì bỏ qua; payload nhị phân thành rỗng. */
    fun decode(data: ByteArray): Message {
        val fields = HashMap<Int, Any>()
        var offset = 0
        while (offset < data.size) {
            val (key, afterKey) = readVarint(data, offset)
            offset = afterKey
            val number = (key shr 3).toInt()
            when ((key and 7).toInt()) {
                0 -> readVarint(data, offset).let { fields[number] = it.first; offset = it.second }
                2 -> {
                    val (size, afterSize) = readVarint(data, offset)
                    if (size > data.size - afterSize) throw Dlna.Failure(STRANGE)
                    fields[number] = data.copyOfRange(afterSize, afterSize + size.toInt())
                    offset = afterSize + size.toInt()
                }
                1 -> if (offset + 8 <= data.size) offset += 8 else throw Dlna.Failure(STRANGE)
                5 -> if (offset + 4 <= data.size) offset += 4 else throw Dlna.Failure(STRANGE)
                else -> throw Dlna.Failure(STRANGE)
            }
        }
        fun string(number: Int): String = (fields[number] as? ByteArray)?.toString(Charsets.UTF_8).orEmpty()
        return Message(string(2), string(3), string(4), if ((fields[5] as? Long ?: 0L) == 0L) string(6) else "")
    }

    /** Ráp các tin từ luồng byte: 4 byte độ dài rồi tin; độ dài quá [MAX_FRAME] là thiết bị lạ - [Dlna.Failure]. */
    class Framer {
        private var buffer = ByteArray(0)

        fun feed(data: ByteArray): List<ByteArray> {
            buffer += data
            val frames = mutableListOf<ByteArray>()
            while (buffer.size >= 4) {
                val size = (buffer[0].toLong() and 0xFF shl 24) or (buffer[1].toLong() and 0xFF shl 16) or
                    (buffer[2].toLong() and 0xFF shl 8) or (buffer[3].toLong() and 0xFF)
                if (size > MAX_FRAME) throw Dlna.Failure(STRANGE)
                if (buffer.size < 4 + size) break
                frames += buffer.copyOfRange(4, 4 + size.toInt())
                buffer = buffer.copyOfRange(4 + size.toInt(), buffer.size)
            }
            return frames
        }
    }

    // ---- tìm thiết bị (mDNS) -----------------------------------------------------------------------------------------

    /** Hỏi PTR `_googlecast._tcp.local` với bit QU (0x8000): trả lời về thẳng người hỏi. */
    fun query(): ByteArray {
        val out = ByteArrayOutputStream()
        out.write(byteArrayOf(0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0))
        for (label in SERVICE.split('.')) {
            out.write(label.length)
            out.write(label.toByteArray(Charsets.US_ASCII))
        }
        out.write(0)
        out.write(byteArrayOf(0, 12, 0x80.toByte(), 1))
        return out.toByteArray()
    }

    private class Malformed : Exception()

    private fun u16(data: ByteArray, offset: Int): Int {
        if (offset < 0 || offset + 2 > data.size) throw Malformed()
        return (data[offset].toInt() and 0xFF shl 8) or (data[offset + 1].toInt() and 0xFF)
    }

    /** Tên DNS (có nén) tại [start] -> (tên, vị trí sau tên ở chỗ gốc). Con trỏ chỉ được trỏ lùi: không thể vòng. */
    private fun name(data: ByteArray, start: Int): Pair<String, Int> {
        val labels = mutableListOf<String>()
        var after = -1
        var offset = start
        while (true) {
            if (offset >= data.size) throw Malformed()
            val size = data[offset].toInt() and 0xFF
            if (size == 0) return labels.joinToString(".") to if (after >= 0) after else offset + 1
            if (size and 0xC0 == 0xC0) {
                if (offset + 1 >= data.size) throw Malformed()
                val pointer = (size and 0x3F shl 8) or (data[offset + 1].toInt() and 0xFF)
                if (pointer >= offset) throw Malformed()
                if (after < 0) after = offset + 2
                offset = pointer
                continue
            }
            if (size and 0xC0 != 0 || offset + 1 + size > data.size) throw Malformed()
            labels += String(data, offset + 1, size, Charsets.UTF_8)
            offset += 1 + size
            if (labels.size > 40) throw Malformed()
        }
    }

    /** Một thiết bị Cast đã trả lời mDNS: [host] là địa chỉ đã gửi gói trả lời. */
    data class Found(val host: String, val port: Int, val instance: String, val txt: List<Pair<String, String>>) {
        fun field(key: String): String = txt.firstOrNull { it.first == key }?.second.orEmpty()
    }

    private fun txt(data: ByteArray, start: Int, size: Int): List<Pair<String, String>> {
        val out = mutableListOf<Pair<String, String>>()
        var offset = start
        val end = start + size
        while (offset < end) {
            val length = data[offset].toInt() and 0xFF
            val stop = minOf(offset + 1 + length, end)
            val item = String(data, offset + 1, stop - offset - 1, Charsets.UTF_8)
            offset += 1 + length
            val name = item.substringBefore('=')
            if (name.isNotEmpty()) out += name.lowercase() to if ('=' in item) item.substringAfter('=') else ""
        }
        return out
    }

    /**
     * Thiết bị Cast trong một gói trả lời mDNS từ [source]. Gói hỏng, không phải trả lời, hay địa chỉ A của máy trỏ chỗ khác
     * [source] thì bỏ - mDNS là dữ liệu từ mạng, không để một máy lạ chỉ máy này sang địa chỉ nó chọn.
     */
    fun parse(packet: ByteArray, source: String, length: Int = packet.size): List<Found> {
        if (length < 12) return emptyList()
        val data = if (length == packet.size) packet else packet.copyOf(length)
        val pointers = mutableListOf<String>()
        val services = HashMap<String, Pair<Int, String>>()
        val texts = HashMap<String, List<Pair<String, String>>>()
        val addresses = HashMap<String, MutableSet<String>>()
        try {
            val flags = u16(data, 2)
            val questions = u16(data, 4)
            val records = u16(data, 6) + u16(data, 8) + u16(data, 10)
            if (flags and 0x8000 == 0 || questions > 8 || records > 64) return emptyList()
            var offset = 12
            repeat(questions) { offset = name(data, offset).second + 4 }
            repeat(records) {
                val (label, afterName) = name(data, offset)
                val kind = u16(data, afterName)
                val size = u16(data, afterName + 8)
                offset = afterName + 10
                if (offset + size > data.size) return emptyList()
                val key = label.lowercase()
                when {
                    kind == 12 -> if (key == SERVICE) pointers += name(data, offset).first
                    kind == 33 && size >= 7 -> services[key] = u16(data, offset + 4) to name(data, offset + 6).first.lowercase()
                    kind == 16 -> texts[key] = txt(data, offset, size)
                    kind == 1 && size == 4 -> addresses.getOrPut(key) { mutableSetOf() }.add((0 until 4).joinToString(".") { (data[offset + it].toInt() and 0xFF).toString() })
                }
                offset += size
            }
        } catch (_: Malformed) {
            return emptyList()
        }
        val found = mutableListOf<Found>()
        for (instance in pointers) {
            val key = instance.lowercase()
            val (port, target) = services[key] ?: (CAST_PORT to "")
            if (target.isNotEmpty() && addresses[target]?.isNotEmpty() == true && source !in addresses.getValue(target)) {
                continue // A trỏ sang máy khác: thiết bị ấy không phải máy vừa trả lời
            }
            if (port in 1..65535) found += Found(source, port, instance, texts[key].orEmpty())
        }
        return found
    }

    /**
     * Hỏi mDNS ra từng card mạng (multicast 224.0.0.251, TTL 255) và thẳng tới [targets] (bài thử, thiết bị giả); gom trả lời
     * trong [timeoutMs]. Cổng nguồn tạm - không bao giờ 5353.
     */
    fun search(timeoutMs: Int = 2000, targets: List<InetSocketAddress> = emptyList(), multicast: Boolean = true): List<Found> =
        Dlna.probe(query(), MDNS_GROUP, timeoutMs, targets, multicast, ttl = 255) { data, length, source ->
            if (Dlna.lan(source)) parse(data, source, length).map { (it.host to it.instance) to it } else emptyList()
        }.map { it.second }

    /**
     * Thiết bị phát từ trả lời mDNS: mã 12 hex theo `id` trong TXT (như mã DLNA theo UDN), tên `fn`, kiểu theo `ca` (bit 1 =
     * có hình -> TV, còn lại loa). null nếu địa chỉ không ở trong nhà.
     */
    fun describe(found: Found): Dlna.Renderer? {
        if (!Dlna.lan(found.host)) return null
        val suffix = ".$SERVICE"
        val label = if (found.instance.lowercase().endsWith(suffix)) found.instance.substring(0, found.instance.length - suffix.length) else found.instance
        val capabilities = found.field("ca")
        val name = Dlna.clean(found.field("fn").ifEmpty { label }, 80).ifEmpty { found.host }
        val tv = capabilities.isNotEmpty() && capabilities.all { it in '0'..'9' } && (capabilities.toLongOrNull() ?: 0L) and 1L != 0L
        return Dlna.Renderer(Dlna.sha1(found.field("id").ifEmpty { label }).take(12), name, if (tv) "tv" else "speaker", found.host,
            protocol = "gcast", port = found.port)
    }

    /** [search] rồi [describe] - mỗi thiết bị một lần (mã trùng thì giữ cái thấy đầu). */
    fun discover(timeoutMs: Int = 2000, targets: List<InetSocketAddress> = emptyList(), multicast: Boolean = true): List<Dlna.Renderer> {
        val seen = LinkedHashMap<String, Dlna.Renderer>()
        for (found in search(timeoutMs, targets, multicast)) describe(found)?.let { seen.putIfAbsent(it.id, it) }
        return seen.values.toList()
    }

    // ---- TLS ---------------------------------------------------------------------------------------------------------

    /** Không kiểm chứng chỉ, không kiểm tên máy: xem "An toàn" ở đầu file. */
    private object TrustAll : X509ExtendedTrustManager() {
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?, socket: Socket?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?, socket: Socket?) {}
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?, engine: SSLEngine?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?, engine: SSLEngine?) {}
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) {}
        override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
    }

    internal val context: SSLContext by lazy { SSLContext.getInstance("TLS").apply { init(null, arrayOf(TrustAll), SecureRandom()) } }
}

/**
 * Một thiết bị Cast. Kết nối mở ở lần [load] đầu và giữ tới [close]; luồng đọc cache MEDIA_STATUS / RECEIVER_STATUS.
 *
 * Vòng đời: CONNECT receiver-0 -> GET_STATUS -> LAUNCH (nếu Default Media Receiver chưa chạy) -> CONNECT transportId -> LOAD
 * (có vị trí bắt đầu - không tua sau). Bị chiếm máy = ứng dụng của ta biến khỏi RECEIVER_STATUS, MEDIA_STATUS có contentId
 * không phải của ta hay mediaSessionId mới, IDLE INTERRUPTED / CANCELLED mà ta không gây ra, hay đối phương CLOSE.
 */
class GoogleCast(renderer: Dlna.Renderer, private val timing: GCast.Timing = GCast.Timing()) : CastBackend {
    private val host = renderer.host
    private val port = if (renderer.port > 0) renderer.port else GCast.CAST_PORT
    private val sender = "sender-" + ByteArray(4).also(SecureRandom()::nextBytes).joinToString("") { "%02x".format(it) }
    private val lock = ReentrantLock()
    private val cond = lock.newCondition()
    private val sendLock = Any() // một khung tin gửi xong rồi mới tới khung khác
    private val wake = CountDownLatch(1)

    @Volatile private var sock: SSLSocket? = null
    @Volatile private var thread: Thread? = null
    @Volatile private var closed = false
    @Volatile private var connected = false
    @Volatile private var heard = 0L // lần cuối nhận được tin (bất kỳ) từ thiết bị
    @Volatile private var attached = 0L // lần nối gần nhất
    private var ids = 0
    private val inbox = HashMap<Int, MutableList<JSONObject>>()

    // ứng dụng nhận
    @Volatile private var sessionId = ""
    @Volatile private var transportId = ""
    @Volatile private var transportOpen = false
    @Volatile private var launched = false // ứng dụng do máy này mở: lúc trả máy thì đóng nó
    @Volatile private var releasing = false

    // đang phát
    private var loading = false
    private var adopted = false // đã nhận trả lời cho LOAD đang chờ
    private var pendingToken = "" // mã trong URL của LOAD đang chờ
    private var pendingUrl = ""
    private var pendingPrevious: Int? = null // mediaSessionId cũ
    @Volatile private var stopping = false
    private var interrupted = false
    private var msid: Int? = null
    private var token = ""
    private var content = ""
    private var duration = 0.0
    private var entry: JSONObject? = null
    private var entryAt = 0L

    private fun now() = System.nanoTime() / 1_000_000

    // -- kết nối --------------------------------------------------------------------------------------------------------

    private fun dial(): SSLSocket {
        if (!Dlna.lan(host)) throw Dlna.Failure("địa chỉ thiết bị không ở trong nhà")
        val raw = Socket()
        try {
            raw.connect(InetSocketAddress(host, port), timing.connect)
            raw.soTimeout = timing.connect
            val ssl = GCast.context.socketFactory.createSocket(raw, host, port, true) as SSLSocket
            ssl.enabledProtocols = ssl.supportedProtocols.filter { it == "TLSv1.2" || it == "TLSv1.3" }.toTypedArray()
            ssl.startHandshake()
            ssl.soTimeout = timing.tick // từ đây đọc chỉ đợi một nhịp
            return ssl
        } catch (error: IOException) { // kể cả SSLException
            runCatching { raw.close() }
            throw Dlna.Failure(LOST_AT_CONNECT)
        }
    }

    private fun attach(socket: SSLSocket, ask: Boolean) {
        lock.withLock {
            if (closed) { // đóng giữa lúc đang nối lại
                runCatching { socket.close() }
                throw Dlna.Failure("đã đóng kết nối với thiết bị")
            }
            sock = socket
            connected = true
            attached = now()
            if (!ask) heard = attached // nối lại thì `heard` giữ nguyên: thiết bị chưa nói gì thì vẫn chưa nghe được
            transportOpen = false
            cond.signalAll()
        }
        send(GCast.NS_CONNECTION, "receiver-0", JSONObject().put("type", "CONNECT"))
        if (ask) send(GCast.NS_RECEIVER, "receiver-0", JSONObject().put("type", "GET_STATUS").put("requestId", next())) // nối lại giữa phiên: ứng dụng của ta còn không
    }

    /** Mở kết nối, mở ứng dụng phát và nối vào nó (nếu chưa). */
    private fun ready() {
        val first = lock.withLock {
            if (closed) throw Dlna.Failure("đã đóng kết nối với thiết bị")
            thread == null
        }
        if (first) {
            attach(dial(), ask = false)
            thread = Thread(::reader, "gcast-reader").apply {
                isDaemon = true
                start()
            }
        }
        if (sessionId.isNotEmpty() && transportOpen) return
        if (!connected) throw Dlna.Failure(LOST)
        var replies = ask(GCast.NS_RECEIVER, "receiver-0", JSONObject().put("type", "GET_STATUS"), timing.reply) { got ->
            got.any { it.text("type") == "RECEIVER_STATUS" }
        }
        var app = app(replies)
        if (app == null) {
            replies = ask(GCast.NS_RECEIVER, "receiver-0", JSONObject().put("type", "LAUNCH").put("appId", GCast.APP_ID), timing.launch, accept = ::launchedIn)
            app = app(replies)
            launched = true
        }
        if (app == null || app.text("transportId").isEmpty()) throw Dlna.Failure("thiết bị không mở được trình phát")
        lock.withLock {
            sessionId = app.text("sessionId")
            transportId = app.text("transportId")
            transportOpen = true
        }
        send(GCast.NS_CONNECTION, transportId, JSONObject().put("type", "CONNECT"))
    }

    private fun app(replies: List<JSONObject>): JSONObject? {
        for (reply in replies.asReversed()) {
            val apps = reply.optJSONObject("status")?.optJSONArray("applications") ?: continue
            for (index in 0 until apps.length()) {
                val app = apps.optJSONObject(index) ?: continue
                if (app.text("appId") == GCast.APP_ID && app.text("sessionId").isNotEmpty()) return app
            }
        }
        return null
    }

    private fun launchedIn(replies: List<JSONObject>): Boolean {
        for (reply in replies) {
            if (reply.text("type") == "LAUNCH_ERROR" || reply.text("type") == "INVALID_REQUEST") throw Dlna.Failure("thiết bị không mở được trình phát")
        }
        val app = app(replies)
        return app != null && app.text("transportId").isNotEmpty()
    }

    // -- luồng đọc ------------------------------------------------------------------------------------------------------

    /** Đọc tin, trả PONG, gửi PING; đứt hay im quá `dead` thì nối lại tới khi được hay bị đóng. */
    private fun reader() {
        while (!closed) {
            val current = sock
            if (current != null) serve(current)
            lock.withLock {
                connected = false
                cond.signalAll()
            }
            runCatching { current?.close() }
            while (!closed) {
                wake.await(timing.reconnect, TimeUnit.MILLISECONDS)
                try {
                    attach(dial(), ask = true)
                    break
                } catch (_: Dlna.Failure) {
                    continue
                }
            }
        }
    }

    private fun serve(socket: SSLSocket) {
        val framer = GCast.Framer()
        val buffer = ByteArray(65536)
        var ping = now()
        var status = ping
        try {
            val input = socket.inputStream
            while (!closed && sock === socket) {
                val moment = now()
                if (moment - maxOf(heard, attached) > timing.dead) return
                if (moment - ping >= timing.heartbeat) {
                    ping = moment
                    send(GCast.NS_HEARTBEAT, "receiver-0", JSONObject().put("type", "PING"))
                }
                if (moment - status >= timing.status && transportOpen && msid != null) {
                    status = moment
                    send(GCast.NS_MEDIA, transportId, JSONObject().put("type", "GET_STATUS").put("requestId", next()))
                }
                val count = try {
                    input.read(buffer)
                } catch (_: SocketTimeoutException) {
                    continue
                }
                if (count < 0) return
                for (raw in framer.feed(buffer.copyOf(count))) handle(GCast.decode(raw))
            }
        } catch (_: IOException) {
            return
        } catch (_: Dlna.Failure) {
            return
        }
    }

    private fun handle(message: GCast.Message) {
        lock.withLock { heard = now() }
        val payload = try {
            if (message.payload.isEmpty()) JSONObject() else JSONObject(message.payload)
        } catch (_: JSONException) {
            return
        }
        val kind = payload.text("type")
        if (message.namespace == GCast.NS_HEARTBEAT) {
            if (kind == "PING") runCatching { send(GCast.NS_HEARTBEAT, message.source, JSONObject().put("type", "PONG")) }
            return
        }
        if (message.namespace == GCast.NS_CONNECTION) {
            if (kind == "CLOSE" && sessionId.isNotEmpty() && !releasing && (message.source == transportId || message.source == "receiver-0")) {
                lock.withLock {
                    interrupted = true // thiết bị đóng nối với ta: máy khác chiếm, hay ứng dụng đã tắt
                    cond.signalAll()
                }
            }
            return
        }
        val request = (payload.opt("requestId") as? Number)?.toInt()
        var reattach = false
        lock.withLock {
            if (request != null) inbox[request]?.add(payload)
            if (message.namespace == GCast.NS_RECEIVER && kind == "RECEIVER_STATUS") {
                reattach = onReceiver(payload.optJSONObject("status") ?: JSONObject())
            } else if (message.namespace == GCast.NS_MEDIA && kind == "MEDIA_STATUS") {
                val list = payload.optJSONArray("status") ?: JSONArray()
                for (index in 0 until list.length()) list.optJSONObject(index)?.let(::onMedia)
            }
            cond.signalAll()
        }
        if (reattach) { // nối lại sau khi đứt và ứng dụng của ta vẫn còn: nối vào nó, hỏi lại đang phát gì
            runCatching {
                send(GCast.NS_CONNECTION, transportId, JSONObject().put("type", "CONNECT"))
                send(GCast.NS_MEDIA, transportId, JSONObject().put("type", "GET_STATUS").put("requestId", next()))
            }
        }
    }

    /** Gọi khi giữ khoá. true: phải nối lại vào ứng dụng của ta. */
    private fun onReceiver(status: JSONObject): Boolean {
        if (sessionId.isEmpty() || releasing) return false
        val apps = status.optJSONArray("applications") ?: JSONArray()
        val ours = (0 until apps.length()).mapNotNull { apps.optJSONObject(it) }.firstOrNull { it.text("sessionId") == sessionId }
        if (ours == null) {
            interrupted = true // ứng dụng của ta không còn: có người mở app khác hay tắt trên TV
            return false
        }
        if (!transportOpen) {
            transportOpen = true
            return transportId.isNotEmpty()
        }
        return false
    }

    /** Gọi khi giữ khoá. Tin về phiên phát của ta thì ghi lại; về phiên khác thì là bị chiếm máy. */
    private fun onMedia(item: JSONObject) {
        val id = (item.opt("mediaSessionId") as? Number)?.toInt()
        val state = item.text("playerState")
        val contentId = item.optJSONObject("media")?.text("contentId").orEmpty()
        if (loading) { // chờ trả lời LOAD của ta: tin về bài cũ (còn phát, hay IDLE INTERRUPTED) không đáng kể
            if (id != null && id != pendingPrevious && pendingToken in contentId.ifEmpty { pendingUrl } &&
                (state != "IDLE" || item.text("idleReason") == "ERROR")
            ) {
                msid = id
                entry = item
                entryAt = now()
                token = pendingToken
                content = pendingUrl
                adopted = true
                interrupted = false
                duration = 0.0
                note(item)
            }
            return
        }
        val mine = msid
        if (mine == null || interrupted) return
        if (contentId.isNotEmpty() && token !in contentId) {
            interrupted = true
            content = contentId
            return
        }
        if (id != mine) {
            if (id != null && id > mine) interrupted = true // có phiên phát mới mà không phải của ta
            return
        }
        entry = item
        entryAt = now()
        note(item)
        if (state == "IDLE" && item.text("idleReason").let { it == "INTERRUPTED" || it == "CANCELLED" } && !stopping) interrupted = true
    }

    private fun note(item: JSONObject) {
        val media = item.optJSONObject("media") ?: return
        (media.opt("duration") as? Number)?.let { duration = it.toDouble() }
        media.text("contentId").takeIf { it.isNotEmpty() }?.let { content = it }
    }

    // -- gửi / hỏi ------------------------------------------------------------------------------------------------------

    private fun next(): Int = lock.withLock { ++ids }

    private fun send(namespace: String, destination: String, body: JSONObject) {
        val data = GCast.frame(GCast.encode(sender, destination, namespace, body.toString()))
        synchronized(sendLock) {
            val socket = sock
            if (socket == null || closed) throw Dlna.Failure(LOST)
            try {
                socket.outputStream.write(data)
                socket.outputStream.flush()
            } catch (error: IOException) {
                throw Dlna.Failure(NO_ANSWER)
            }
        }
    }

    /** Gửi lệnh có requestId rồi đợi tới khi [accept] (các trả lời đã nhận) true. [accept] ném [Dlna.Failure] để báo lỗi. */
    private fun ask(namespace: String, destination: String, body: JSONObject, timeoutMs: Long, request: Int? = null,
                    accept: (List<JSONObject>) -> Boolean): List<JSONObject> {
        val id = request ?: next()
        lock.withLock { inbox[id] = ArrayList() }
        try {
            send(namespace, destination, body.put("requestId", id))
            val deadline = now() + timeoutMs
            lock.withLock {
                while (true) {
                    val replies = ArrayList(inbox[id].orEmpty())
                    if (accept(replies)) return replies
                    val left = deadline - now()
                    if (closed || !connected) throw Dlna.Failure(LOST)
                    if (left <= 0) throw Dlna.Failure(NO_ANSWER)
                    cond.await(minOf(left, timing.tick.toLong()), TimeUnit.MILLISECONDS)
                }
            }
        } finally {
            lock.withLock { inbox.remove(id) }
        }
        @Suppress("UNREACHABLE_CODE")
        throw IllegalStateException()
    }

    private fun media(kind: String, timeoutMs: Long = timing.reply, extra: JSONObject = JSONObject()) {
        val id = lock.withLock { msid }
        if (id == null || !transportOpen) throw Dlna.Failure(Dlna.error(702))
        val body = extra.put("type", kind).put("mediaSessionId", id)
        ask(GCast.NS_MEDIA, transportId, body, timeoutMs) { replies ->
            for (reply in replies) {
                if (reply.text("type") == "INVALID_REQUEST" || reply.text("type") == "LOAD_FAILED") throw Dlna.Failure(Dlna.error(402))
            }
            replies.any { it.text("type") == "MEDIA_STATUS" }
        }
    }

    // -- CastBackend ----------------------------------------------------------------------------------------------------

    override fun load(track: CastTrack, seconds: Double): Double {
        ready()
        val metadata = JSONObject().put("metadataType", 3).put("title", track.title).put("albumName", track.album)
        if (track.art.isNotEmpty()) metadata.put("images", JSONArray().put(JSONObject().put("url", track.art)))
        val media = JSONObject().put("contentId", track.url).put("contentType", track.mime).put("streamType", "BUFFERED")
            .put("metadata", metadata)
        val request = next()
        lock.withLock {
            loading = true
            adopted = false
            stopping = false
            pendingToken = track.url.substringAfterLast('/').substringBefore('.')
            pendingUrl = track.url
            pendingPrevious = msid
        }
        try {
            val body = JSONObject().put("type", "LOAD").put("sessionId", sessionId).put("media", media).put("autoplay", true)
                .put("currentTime", Math.round(seconds * 100) / 100.0)
            ask(GCast.NS_MEDIA, transportId, body, timing.load, request) { replies ->
                for (reply in replies) {
                    if (reply.text("type") == "LOAD_FAILED") throw Dlna.Failure(Dlna.error(716))
                    if (reply.text("type") == "INVALID_REQUEST" || reply.text("type") == "LOAD_CANCELLED") throw Dlna.Failure(Dlna.error(402))
                }
                if (adopted && entry?.text("idleReason") == "ERROR") throw Dlna.Failure(Dlna.error(716))
                adopted
            }
        } finally {
            lock.withLock { loading = false }
        }
        return seconds
    }

    override fun play() = media("PLAY")

    override fun pause(): Boolean {
        media("PAUSE")
        return false
    }

    override fun stop(timeoutMs: Int) {
        stopping = true
        media("STOP", timeoutMs.toLong())
    }

    override fun seek(seconds: Double) = media("SEEK", extra = JSONObject().put("currentTime", Math.round(seconds * 100) / 100.0))

    override fun status(): CastStatus = lock.withLock {
        val moment = now()
        if (closed || !connected || moment - heard > timing.dead) throw Dlna.Failure(NO_ANSWER)
        val item = entry
        if (msid == null || item == null) return@withLock CastStatus("NO_MEDIA_PRESENT", 0.0, 0.0, "", if (interrupted) "interrupted" else "")
        val raw = item.text("playerState")
        var state = PLAYER_STATES[raw] ?: "STOPPED"
        var position = item.optDouble("currentTime", 0.0)
        if (state == "PLAYING") {
            position += maxOf(0.0, (moment - entryAt) / 1000.0) * item.optDouble("playbackRate", 1.0).let { if (it == 0.0) 1.0 else it }
            if (duration > 0) position = minOf(position, duration)
        }
        var reason = ""
        if (interrupted) {
            state = "STOPPED"
            reason = "interrupted"
        } else if (raw == "IDLE") {
            reason = IDLE_REASONS[item.text("idleReason")].orEmpty()
            if (reason == "interrupted" && stopping) reason = ""
        }
        CastStatus(state, position, duration, content, reason)
    }

    override fun close(release: Boolean) {
        val leave = lock.withLock {
            if (closed) return
            releasing = true
            release && launched && sessionId.isNotEmpty() && connected
        }
        if (leave) { // ứng dụng do ta mở: đóng nó, màn hình TV / loa về như cũ
            runCatching {
                ask(GCast.NS_RECEIVER, "receiver-0", JSONObject().put("type", "STOP").put("sessionId", sessionId), 2000) { replies ->
                    replies.any { it.text("type") == "RECEIVER_STATUS" }
                }
            }
        }
        val socket = lock.withLock {
            closed = true
            val current = sock
            sock = null
            connected = false
            cond.signalAll()
            current
        }
        wake.countDown()
        if (socket != null) {
            runCatching {
                synchronized(sendLock) {
                    for (destination in listOf(transportId, "receiver-0")) {
                        if (destination.isNotEmpty()) {
                            socket.outputStream.write(GCast.frame(GCast.encode(sender, destination, GCast.NS_CONNECTION, "{\"type\":\"CLOSE\"}")))
                        }
                    }
                    socket.outputStream.flush()
                }
            }
            runCatching { socket.close() }
        }
    }

    private fun JSONObject.text(key: String): String = opt(key) as? String ?: ""

    companion object {
        private const val LOST = "mất kết nối - thiết bị đã tắt hay rời mạng?"
        private const val NO_ANSWER = "không trả lời - thiết bị đã tắt hay rời mạng?"
        private const val LOST_AT_CONNECT = "không nối được - thiết bị đã tắt hay rời mạng?"
        private val IDLE_REASONS = mapOf("FINISHED" to "finished", "ERROR" to "error", "INTERRUPTED" to "interrupted", "CANCELLED" to "interrupted")
        private val PLAYER_STATES = mapOf("PLAYING" to "PLAYING", "PAUSED" to "PAUSED_PLAYBACK", "BUFFERING" to "TRANSITIONING", "LOADING" to "TRANSITIONING")
    }
}
