package vn.abook.player

import android.content.Context
import android.os.Build
import android.os.PowerManager
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.ui.studio.StudioRoute
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.net.SocketTimeoutException

/**
 * Việc "Thiết bị" mà cả hai giao diện cùng làm (WebView qua [LibraryPlugin], native qua `ui.data.DevicesRepo`): tìm và ghép máy, tên điện thoại, chia sẻ thư viện,
 * dung lượng, máy tính mở được Studio. Trước đây nằm trong thân phương thức plugin (docs/NATIVE_PHONE_UI.md §2: logic dời vào lõi, plugin chỉ chuyển tiếp).
 * Hàm trả JSON giữ nguyên hình đã gửi cho WebView. Mọi hàm đọc đĩa / mạng: gọi ở luồng nền.
 */
object Devices {
    /** Công tắc "Cho máy khác nghe thư viện này" (SharedPreferences "sync"). */
    const val SHARE_KEY = ShareService.SHARE_KEY

    private const val DISCOVERY_PORT = 47631

    /** Máy tính chính: đã ghép chưa, địa chỉ, tên, đường nối đang thông, địa chỉ ghép lần trước và tên điện thoại này. */
    fun connection(context: Context): JSONObject {
        val prefs = SyncLink.prefs(context)
        val paired = !prefs.getString("token", "").isNullOrBlank()
        return JSONObject().put("paired", paired).put("host", prefs.getString("host", "")).put("port", prefs.getInt("port", 47630))
            .put("name", prefs.getString("name", "")).put("fingerprint", prefs.getString("fingerprint", "") ?: "")
            .put("connectedVia", prefs.getString("connectedVia", ""))
            .put("lastAddress", context.getSharedPreferences("abook_self", Context.MODE_PRIVATE).getString("lastAddress", "") ?: "")
            .put("deviceName", DeviceName.of(context))
    }

    /** Tìm máy đang bật đồng bộ trong cùng mạng Wi-Fi (UDP broadcast): mảng {host, port, name, kind}. */
    fun discover(context: Context, timeoutMs: Int = 2500): JSONArray {
        val found = JSONArray()
        val hints = DiscoveryHints { hint -> PeerRouting.discovered(context, hint.host, hint.port, hint.claimed) }
        val own = LibraryServer.addresses().toSet() + "127.0.0.1"
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.soTimeout = 400
            val probe = "ABOOK_DISCOVER".toByteArray()
            val deadline = System.currentTimeMillis() + timeoutMs
            var sent = 0
            while (System.currentTimeMillis() < deadline) {
                if (sent < 3) {
                    runCatching { socket.send(DatagramPacket(probe, probe.size, InetAddress.getByName("255.255.255.255"), DISCOVERY_PORT)) }
                    sent += 1
                }
                val buffer = ByteArray(4096)
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    socket.receive(packet)
                    val reply = JSONObject(String(packet.data, 0, packet.length))
                    val host = packet.address.hostAddress ?: continue
                    // Chính điện thoại này (đang cho máy khác nghe thư viện - LibraryServer) cũng trả lời: bỏ.
                    if (host in own && reply.optInt("port") == LibraryServer.PORT) continue
                    val address = PeerAddresses.discoveryEndpoint(host, reply.opt("port")) ?: continue
                    val port = PeerAddresses.split(address).second
                    if (reply.optString("app") == "abook" && hints.add(host, port, reply.optString("fingerprint"))) {
                        found.put(JSONObject().put("host", host).put("port", port).put("name", reply.optString("name"))
                            .put("kind", reply.optString("kind", "computer")))
                    }
                } catch (_: SocketTimeoutException) {
                } catch (_: org.json.JSONException) {
                    // A malformed UDP responder must not discard the remaining discoveries.
                }
            }
        }
        hints.finish()
        return found
    }

    /** Ghép máy tính chính bằng địa chỉ + mã 6 số; trả tên máy ấy. */
    fun pair(context: Context, host: String, port: Int, code: String, device: String? = null): String {
        SyncLink.refuseSelf(host, port)
        val prefs = SyncLink.prefs(context)
        val body = JSONObject().put("code", code).put("device", device ?: DeviceName.of(context))
        val (reply, fingerprint) = SyncLink.pair(context, "https://${PeerAddresses.endpoint(host, port)}", body)
        SyncLink.saveRoutes(prefs.edit().putString("host", host).putInt("port", port).putString("token", reply.getString("token"))
            .putString("fingerprint", fingerprint).putString("name", reply.optString("name")), reply, host, port, fingerprint,
            PeerRouting.main(context).takeIf { it.optString("fingerprint").equals(fingerprint, true) }).commit()
        // Ô địa chỉ nhớ máy đã ghép lần trước (soát a68 lỗi 20): ngoài "sync" vì bỏ ghép xoá sạch "sync" - ghép lại là lúc cần nó nhất.
        context.getSharedPreferences("abook_self", Context.MODE_PRIVATE).edit().putString("lastAddress", "$host:$port").apply()
        Remote.ensure()
        return reply.optString("name")
    }

    /** Ghép máy tính chính QUA BLUETOOTH: cùng mã 6 số, cùng /sync/v1/pair - đi qua đường hầm. */
    fun pairBluetooth(context: Context, address: String, code: String, device: String? = null): String {
        val prefs = SyncLink.prefs(context)
        val body = JSONObject().put("code", code).put("device", device ?: DeviceName.of(context))
        val root = BluetoothLink.base(context, address)
        val (reply, fingerprint) = try {
            SyncLink.pair(context, root, body)
        } catch (error: Exception) {
            val reason = BluetoothLink.lastError(address)
            throw IllegalStateException(reason.ifBlank { error.message ?: "không kết nối được qua Bluetooth" })
        }
        SyncLink.saveRoutes(prefs.edit().putString("host", "bt:$address").putInt("port", 0).putString("token", reply.getString("token"))
            .putString("fingerprint", fingerprint).putString("name", reply.optString("name")), reply, "bt:$address", 0, fingerprint,
            PeerRouting.main(context).takeIf { it.optString("fingerprint").equals(fingerprint, true) }).commit()
        Remote.ensure()
        return reply.optString("name")
    }

    /** Máy đã ghép Bluetooth với điện thoại; nơi gọi đã kiểm quyền "Thiết bị ở gần" ([BluetoothLink.permitted]). */
    fun bluetoothDevices(context: Context): JSONArray {
        if (!BluetoothLink.permitted(context)) throw IllegalStateException("Cần cho ABook dùng \"Thiết bị ở gần\" để kết nối qua Bluetooth")
        return BluetoothLink.devices(context)
    }

    /** Đổi tên điện thoại này ở máy khác (soát a68 lỗi 16); rỗng = tên mặc định. Báo ngay máy tính chính và các máy đã ghép (máy tắt thì lần ghép sau). */
    fun setDeviceName(context: Context, name: String): String {
        val clean = DeviceName.set(context, name)
        val body = JSONObject().put("name", clean)
        if (SyncLink.paired(context)) runCatching { SyncLink.request(context, "POST", "/sync/v1/name", body, readTimeoutMs = 5000, connectTimeoutMs = 2000) }
        for (key in Peers.all(context).keys()) runCatching { Peers.request(context, key, "POST", "/sync/v1/name", body, readTimeoutMs = 5000, connectTimeoutMs = 2000) }
        return clean
    }

    /** Bỏ ghép máy tính chính. Máy tính thu hồi mã của điện thoại này trước (soát a27 lỗi 5) - máy tính tắt thì chỉ chờ vài giây. Chặn luồng gọi. */
    fun unpair(context: Context) {
        val prefs = SyncLink.prefs(context)
        runCatching { SyncLink.tellUnpaired(context, SyncLink.base(context), SyncLink.token(context)) }
        prefs.getString("host", null)?.takeIf { it.startsWith("bt:") }?.let { BluetoothLink.forget(it) }
        prefs.edit().clear().apply()
    }

    // ---- cho máy khác nghe thư viện này (mạng trạm bước 2 - LibraryServer) ------------------------------------------

    /**
     * Hãng máy (chọn lời chỉ đường cho chạy nền: OPPO, Xiaomi, Samsung...) và ABook đã được miễn tối ưu pin chưa. Máy hãng cho app "ngủ"
     * khi ở nền; bật "Cho phép hoạt động dưới nền" thì ABook vào danh sách miễn và cờ này thành true. Chỉ đọc - app không tự xin miễn.
     */
    fun backgroundView(context: Context, into: JSONObject = JSONObject()): JSONObject =
        into.put("manufacturer", Build.MANUFACTURER.orEmpty())
            .put("backgroundAllowed", context.getSystemService(PowerManager::class.java)?.isIgnoringBatteryOptimizations(context.packageName) ?: false)

    fun shareView(context: Context): JSONObject {
        LibraryServer.init(context)
        // Màn hình hỏi trạng thái sau khi người dùng vừa cho quyền "Thiết bị ở gần" hay vừa bật Bluetooth: thử nghe lại.
        if (LibraryServer.running()) BluetoothShare.retry()
        val devices = JSONArray()
        val list = LibraryServer.devices()
        for (index in 0 until list.length()) devices.put(list.getJSONObject(index))
        val pairing = LibraryServer.pairingCode()
        return JSONObject().put("running", LibraryServer.running()).put("name", LibraryServer.name())
            .put("port", LibraryServer.PORT).put("addresses", JSONArray(LibraryServer.addresses()))
            .put("pairing", pairing ?: JSONObject.NULL)
            .put("blocked", LibraryServer.blocked).put("devices", devices).put("error", LibraryServer.lastError)
            .put("fingerprint", if (LibraryServer.fingerprint.isEmpty()) "" else Pin.display(LibraryServer.fingerprint))
            .put("bluetooth", JSONObject().put("status", BluetoothShare.status).put("connections", BluetoothShare.connections()))
            .also { backgroundView(context, it) }
    }

    /** Bật / tắt chia sẻ (công tắc trong app và nút "Tắt chia sẻ" trên thông báo dùng cùng đường [ShareService]); trả trạng thái mới. */
    fun setShare(context: Context, enabled: Boolean): JSONObject {
        if (enabled) ShareService.turnOn(context) else ShareService.turnOff(context)
        return shareView(context)
    }

    /** Hiện mã 6 số cho máy khác ghép; mở máy chủ nếu chưa chạy. */
    fun sharePair(context: Context): JSONObject {
        if (!LibraryServer.running()) ShareService.enable(context)
        LibraryServer.startPairing()
        return shareView(context)
    }

    fun shareCancelPairing(context: Context): JSONObject {
        LibraryServer.cancelPairing()
        return shareView(context)
    }

    fun shareRevoke(context: Context, id: String): JSONObject {
        LibraryServer.revoke(id)
        return shareView(context)
    }

    // ---- dung lượng ------------------------------------------------------------------------------------------

    /** Tổng, chỗ trống và từng thư mục sách trên máy (`title`: tên trong gói sách của thư mục - tải dở chưa có gói thì không có). */
    fun storage(): JSONObject {
        val sizes = Store.bookSizes()
        val books = JSONArray()
        for ((id, bytes) in sizes) {
            val title = (Store.rawManifest(id) ?: Store.streamManifest(id))?.optString("title").orEmpty()
            books.put(JSONObject().put("id", id).put("bytes", bytes).apply { if (title.isNotEmpty()) put("title", title) })
        }
        return JSONObject().put("bytes", sizes.values.sum()).put("free", Store.root.usableSpace).put("books", books)
    }

    // ---- Studio của máy tính đã ghép -------------------------------------------------------------------------------

    /**
     * Máy tính mở Studio được (StudioLink.computers): máy tính chính rồi các máy tính ghép thêm. `book` (mã cuốn trên điện thoại này): máy tính GIỮ cuốn ấy
     * mang `holdsBook`. Máy chỉ cho điện thoại này nghe mang `listenOnly` (không hỏi được = coi như mở được).
     */
    fun studioComputers(context: Context, book: String? = null): JSONArray {
        val out = JSONArray()
        val holder = book?.let { StudioLink.bookTarget(it)?.first }
        for (computer in StudioLink.computers(context)) {
            val listenOnly = StudioLink.link(context, computer.key)?.let { link ->
                runCatching {
                    StudioLink.listenOnly(SyncLink.request(context, "GET", "/api/app", auth = false, root = link.base, token = link.token,
                        readTimeoutMs = 3000, connectTimeoutMs = 2000))
                }.getOrDefault(false)
            } ?: false
            out.put(JSONObject().put("key", computer.key).put("name", computer.name).put("listenOnly", listenOnly).apply { if (computer.key == holder) put("holdsBook", true) })
        }
        return out
    }

    /**
     * Máy và màn native để mở Studio từ xa: `book` = mã cuốn trên điện thoại này (mở thẳng cuốn ấy ở máy giữ nó), không thì `computer`
     * (mã máy, "" = máy tính chính) ở danh sách dự án. Chỉ mã máy và mã sách đi qua Intent, không bao giờ mã thiết bị; mã sách lạ thì về danh sách dự án.
     */
    fun studioTarget(context: Context, book: String?, computer: String?): Pair<String, StudioRoute> {
        val (key, route) = if (book != null) {
            val (holder, remote) = StudioLink.bookTarget(book) ?: throw IllegalStateException("Cuốn này không làm trên máy tính nào đã ghép")
            holder to StudioRoute(remote.takeIf { StudioPaths.valid(it) })
        } else {
            (computer ?: StudioLink.MAIN) to StudioRoute()
        }
        if (!StudioLink.known(key, SyncLink.paired(context), Peers.all(context))) throw IllegalStateException("Chưa ghép với máy tính nào")
        return key to route
    }
}
