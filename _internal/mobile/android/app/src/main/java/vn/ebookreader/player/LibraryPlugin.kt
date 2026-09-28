package vn.ebookreader.player

import android.Manifest
import com.getcapacitor.annotation.Permission
import com.getcapacitor.annotation.PermissionCallback
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import androidx.activity.result.ActivityResult
import com.getcapacitor.JSArray
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.SocketTimeoutException
import java.net.URL
import java.util.concurrent.ExecutionException
import java.util.concurrent.Executors
import java.util.concurrent.FutureTask
import java.util.concurrent.TimeUnit

/** Công tắc "Cho máy khác nghe thư viện này" (SharedPreferences "sync"). */
private const val SHARE_KEY = "shareLibrary"

/**
 * Thư viện trên điện thoại + đồng bộ với máy tính qua Wi-Fi (ebook_reader/webui/sync.py).
 *
 * Mọi mạng đi qua đây (native) chứ không qua fetch của WebView: trang chạy ở https://localhost, gọi http://<máy
 * tính> sẽ bị chặn vì mixed content, và tải hàng trăm MB audio thì nên làm ở luồng nền, ghi thẳng ra file.
 */
@CapacitorPlugin(
    name = "EbookLibrary",
    permissions = [
        Permission(strings = [Manifest.permission.POST_NOTIFICATIONS], alias = "notifications"),
        Permission(strings = [Manifest.permission.BLUETOOTH_CONNECT], alias = "bluetooth"),
    ],
)
class LibraryPlugin : Plugin() {
    private val io = Executors.newSingleThreadExecutor()
    // Trình phát máy khác (mạng trạm bước 4): hỏi mạng tới vài giây, không được chặn hàng `io` của thư viện.
    private val remotes = Executors.newCachedThreadPool()
    private val downloads = Executors.newSingleThreadExecutor()
    private val prefs by lazy { SyncLink.prefs(context) }

    override fun load() {
        Playback.init(context)
        // Đã bật "Cho máy khác nghe thư viện này" từ lần trước: mở lại máy chủ cùng app (LibraryServer).
        if (prefs.getBoolean(SHARE_KEY, false)) io.execute { runCatching { LibraryServer.start(context) } }
    }

    private fun background(call: PluginCall, block: () -> Unit) = io.execute {
        try {
            block()
        } catch (error: Exception) {
            call.reject(error.message ?: error.javaClass.simpleName)
        }
    }

    @PluginMethod
    fun info(call: PluginCall) = call.resolve(JSObject().put("root", Store.root.absolutePath))

    // ---- mở file sách (.abook) -------------------------------------------------------------------------------

    /**
     * Nhập một file sách (BookFileImport) ở luồng nền rồi báo "import" lên giao diện: mở từ trình quản lý file, Zalo,
     * Drive (MainActivity) hay nút "Nhập sách". Sự kiện được GIỮ tới khi giao diện nghe: mở app lạnh bằng file thì
     * việc nhập có thể xong trước khi trang web kịp gắn listener.
     */
    fun importFrom(uri: Uri) = io.execute {
        val event = try {
            val imported = BookFileImport.import(context, uri)
            JSObject().put("bookId", imported.id).put("title", imported.title)
        } catch (error: BookFileImport.Refused) {
            JSObject().put("error", error.message)
        } catch (error: Exception) {
            JSObject().put("error", "Không mở được file sách: ${error.message ?: error.javaClass.simpleName}")
        }
        notifyListeners("import", event, true)
    }

    /** Nút "Nhập sách": chọn file bằng bộ chọn của hệ thống (mọi loại - trình quản lý file không biết đuôi .abook). */
    @PluginMethod
    fun pickBook(call: PluginCall) {
        val intent = Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*")
        startActivityForResult(call, intent, "pickedBook")
    }

    @ActivityCallback
    private fun pickedBook(call: PluginCall?, result: ActivityResult) {
        val uri = result.data?.data
        if (uri == null) {
            call?.resolve(JSObject().put("picked", false))
            return
        }
        importFrom(uri)
        call?.resolve(JSObject().put("picked", true))
    }

    // ---- ghép nối --------------------------------------------------------------------------------------------

    private fun base(): String = SyncLink.base(context)

    private fun request(method: String, path: String, body: JSONObject? = null, auth: Boolean = true, root: String = base()): String =
        SyncLink.request(context, method, path, body, auth, root)

    /** Tìm máy tính đang bật đồng bộ trong cùng mạng Wi-Fi (UDP broadcast). */
    @PluginMethod
    fun discover(call: PluginCall) = background(call) {
        val found = JSArray()
        val seen = mutableSetOf<String>()
        val own = LibraryServer.addresses().toSet() + "127.0.0.1"
        DatagramSocket().use { socket ->
            socket.broadcast = true
            socket.soTimeout = 400
            val probe = "EBOOKREADER_DISCOVER".toByteArray()
            val deadline = System.currentTimeMillis() + (call.getInt("timeoutMs") ?: 2500)
            var sent = 0
            while (System.currentTimeMillis() < deadline) {
                if (sent < 3) {
                    runCatching { socket.send(DatagramPacket(probe, probe.size, InetAddress.getByName("255.255.255.255"), 47631)) }
                    sent += 1
                }
                val buffer = ByteArray(512)
                val packet = DatagramPacket(buffer, buffer.size)
                try {
                    socket.receive(packet)
                    val reply = JSONObject(String(packet.data, 0, packet.length))
                    val host = packet.address.hostAddress ?: continue
                    // Chính điện thoại này (đang cho máy khác nghe thư viện - LibraryServer) cũng trả lời: bỏ.
                    if (host in own) continue
                    if (reply.optString("app") == "ebook-reader" && seen.add(host)) {
                        found.put(JSObject().put("host", host).put("port", reply.optInt("port", 47630)).put("name", reply.optString("name"))
                            .put("kind", reply.optString("kind", "computer")))
                    }
                } catch (_: SocketTimeoutException) {
                }
            }
        }
        call.resolve(JSObject().put("computers", found))
    }

    @PluginMethod
    fun pair(call: PluginCall) = background(call) {
        val host = call.getString("host") ?: throw IllegalArgumentException("thiếu địa chỉ máy tính")
        val port = call.getInt("port") ?: 47630
        val device = call.getString("device") ?: "${Build.MANUFACTURER} ${Build.MODEL}"
        val body = JSONObject().put("code", call.getString("code") ?: "").put("device", device)
        val reply = JSONObject(request("POST", "/sync/v1/pair", body, auth = false, root = "http://$host:$port"))
        prefs.edit().putString("host", host).putInt("port", port).putString("token", reply.getString("token"))
            .putString("name", reply.optString("name")).commit()
        Remote.ensure()
        call.resolve(JSObject().put("name", reply.optString("name")))
    }

    // ---- qua Bluetooth (BluetoothLink, BtMux) -------------------------------------------------------------------------

    /** Máy đã ghép Bluetooth với điện thoại. Android 12+: xin quyền "Thiết bị ở gần" lần đầu. */
    @PluginMethod
    fun bluetoothDevices(call: PluginCall) {
        if (!BluetoothLink.permitted(context)) {
            requestPermissionForAlias("bluetooth", call, "bluetoothDevicesAfterPermission")
            return
        }
        bluetoothDevicesAfterPermission(call)
    }

    @PermissionCallback
    private fun bluetoothDevicesAfterPermission(call: PluginCall) = background(call) {
        if (!BluetoothLink.permitted(context)) throw IllegalStateException("Cần cho ABook dùng \"Thiết bị ở gần\" để kết nối qua Bluetooth")
        val out = JSArray()
        val devices = BluetoothLink.devices(context)
        for (index in 0 until devices.length()) out.put(JSObject.fromJSONObject(devices.getJSONObject(index)))
        call.resolve(JSObject().put("devices", out))
    }

    /** Ghép máy tính chính QUA BLUETOOTH: cùng mã 6 số, cùng /sync/v1/pair - đi qua đường hầm. */
    @PluginMethod
    fun pairBluetooth(call: PluginCall) = background(call) {
        val address = call.getString("address") ?: throw IllegalArgumentException("thiếu máy")
        val device = call.getString("device") ?: "${Build.MANUFACTURER} ${Build.MODEL}"
        val body = JSONObject().put("code", call.getString("code") ?: "").put("device", device)
        val root = BluetoothLink.base(context, address)
        val reply = try {
            JSONObject(request("POST", "/sync/v1/pair", body, auth = false, root = root))
        } catch (error: Exception) {
            val reason = BluetoothLink.lastError(address)
            throw IllegalStateException(reason.ifBlank { error.message ?: "không kết nối được qua Bluetooth" })
        }
        prefs.edit().putString("host", "bt:$address").putInt("port", 0).putString("token", reply.getString("token"))
            .putString("name", reply.optString("name")).commit()
        Remote.ensure()
        call.resolve(JSObject().put("name", reply.optString("name")))
    }

    // ---- cho máy khác nghe thư viện này (mạng trạm bước 2 - LibraryServer) ------------------------------------------

    private fun shareView(): JSObject {
        LibraryServer.init(context)
        // Màn hình hỏi trạng thái sau khi người dùng vừa cho quyền "Thiết bị ở gần" hay vừa bật Bluetooth: thử nghe lại.
        if (LibraryServer.running()) BluetoothShare.retry()
        val devices = JSArray()
        val list = LibraryServer.devices()
        for (index in 0 until list.length()) devices.put(JSObject.fromJSONObject(list.getJSONObject(index)))
        val pairing = LibraryServer.pairingCode()
        return JSObject().put("running", LibraryServer.running()).put("name", LibraryServer.name())
            .put("port", LibraryServer.PORT).put("addresses", JSArray(LibraryServer.addresses()))
            .put("pairing", if (pairing != null) JSObject.fromJSONObject(pairing) else JSONObject.NULL)
            .put("blocked", LibraryServer.blocked).put("devices", devices).put("error", LibraryServer.lastError)
            .put("bluetooth", JSObject().put("status", BluetoothShare.status).put("connections", BluetoothShare.connections()))
    }

    @PluginMethod
    fun shareStatus(call: PluginCall) = background(call) { call.resolve(shareView()) }

    @PluginMethod
    fun setShare(call: PluginCall) = background(call) {
        val enabled = call.getBoolean("enabled") ?: false
        prefs.edit().putBoolean(SHARE_KEY, enabled).commit()
        if (enabled) LibraryServer.start(context) else LibraryServer.stop()
        call.resolve(shareView())
    }

    @PluginMethod
    fun sharePair(call: PluginCall) = background(call) {
        if (!LibraryServer.running()) LibraryServer.start(context)
        LibraryServer.startPairing()
        call.resolve(shareView())
    }

    @PluginMethod
    fun shareCancelPairing(call: PluginCall) = background(call) {
        LibraryServer.cancelPairing()
        call.resolve(shareView())
    }

    @PluginMethod
    fun shareRevoke(call: PluginCall) = background(call) {
        LibraryServer.revoke(call.getString("id") ?: "")
        call.resolve(shareView())
    }

    @PluginMethod
    fun connection(call: PluginCall) {
        val paired = !prefs.getString("token", "").isNullOrBlank()
        call.resolve(
            JSObject().put("paired", paired).put("host", prefs.getString("host", "")).put("port", prefs.getInt("port", 47630))
                .put("name", prefs.getString("name", "")),
        )
    }

    @PluginMethod
    fun unpair(call: PluginCall) {
        prefs.getString("host", null)?.takeIf { it.startsWith("bt:") }?.let { BluetoothLink.forget(it) }
        prefs.edit().clear().apply()
        call.resolve()
    }

    /** Thông báo Studio (StudioAlerts.kt): công tắc, và Android có cho app đăng thông báo không. */
    @PluginMethod
    fun studioAlerts(call: PluginCall) {
        call.resolve(JSObject().put("enabled", StudioAlerts.enabled(context)).put("permitted", StudioAlerts.permitted(context)))
    }

    @PluginMethod
    fun setStudioAlerts(call: PluginCall) {
        val on = call.getBoolean("enabled") ?: false
        // Android 13+: bật mà chưa có quyền thông báo thì xin trước; người dùng từ chối thì công tắc vẫn lưu, màn hình
        // nói rõ "chưa cho phép thông báo".
        if (on && Build.VERSION.SDK_INT >= 33 && !StudioAlerts.permitted(context)) {
            requestPermissionForAlias("notifications", call, "studioAlertsAfterPermission")
        } else {
            studioAlertsAfterPermission(call)
        }
    }

    @PermissionCallback
    private fun studioAlertsAfterPermission(call: PluginCall) {
        StudioAlerts.setEnabled(context, call.getBoolean("enabled") ?: false)
        studioAlerts(call)
    }

    /** Studio từ xa (StudioActivity.kt): trang Studio của máy tính đã ghép, mang sẵn mã thiết bị. */
    @PluginMethod
    fun openStudio(call: PluginCall) {
        if (prefs.getString("token", "").isNullOrBlank()) {
            call.reject("Chưa ghép với máy tính nào")
            return
        }
        activity.startActivity(Intent(activity, StudioActivity::class.java))
        call.resolve()
    }

    @PluginMethod
    fun remoteLibrary(call: PluginCall) = background(call) {
        val reply = JSONObject(request("GET", "/sync/v1/library"))
        matchImported()
        val books = reply.getJSONArray("books")
        for (index in 0 until books.length()) {
            val book = books.getJSONObject(index)
            val local = Store.manifest(book.getString("id"))
            book.put("downloaded", local != null)
            book.put("localChapters", local?.optInt("chaptersAvailable") ?: 0)
            book.put("localCoverVersion", local?.optJSONObject("cover")?.optLong("version") ?: 0L)
        }
        call.resolve(JSObject().put("name", reply.optString("name")).put("books", books))
    }

    /**
     * Cuốn mở từ file mà máy tính cũng có: hỏi máy tính (POST /sync/v1/match, gửi cỡ + mã băm audio từng chương - sách
     * không mang mã nào) rồi gộp làm một (Store.adopt). Cuốn đang nằm trong trình phát thì để lần sau - đổi thư mục dưới
     * tay trình phát là mất chương kế tiếp và chỗ đang nghe. Máy tính không trả lời thì thôi, lần sau hỏi lại.
     */
    private fun matchImported() {
        val waiting = Store.importedBooks().filter { it != Playback.bookId }
        if (waiting.isEmpty()) return
        val books = JSONArray()
        for (id in waiting) books.put(JSONObject().put("key", id).put("chapters", Store.chapterPrints(id)))
        val reply = runCatching { JSONObject(request("POST", "/sync/v1/match", JSONObject().put("books", books))) }
            .getOrNull() ?: return
        val matches = reply.optJSONObject("matches") ?: return
        for (key in matches.keys()) {
            if (key in waiting) Store.adopt(key, matches.getString(key))
        }
    }

    // ---- tải sách --------------------------------------------------------------------------------------------

    private fun fetchFile(id: String, relative: String, expectedSize: Long, link: Peers.Link, remote: String): Long {
        val target = Store.file(id, relative)
        if (expectedSize > 0 && target.isFile && target.length() == expectedSize) return 0
        target.parentFile?.mkdirs()
        val partial = File(target.path + ".part")
        val connection = URL("${link.base}/sync/v1/books/$remote/files/$relative").openConnection() as HttpURLConnection
        connection.connectTimeout = 5000
        connection.readTimeout = 30000
        connection.setRequestProperty("Authorization", "Bearer ${link.token}")
        val resumeFrom = if (partial.isFile) partial.length() else 0L
        if (resumeFrom > 0) connection.setRequestProperty("Range", "bytes=$resumeFrom-")
        val code = connection.responseCode
        if (code >= 400) throw IllegalStateException("Không tải được $relative (mã $code)")
        val append = code == 206
        java.io.FileOutputStream(partial, append).use { output -> connection.inputStream.use { it.copyTo(output, 256 * 1024) } }
        connection.disconnect()
        if (!partial.renameTo(target)) {
            target.delete()
            partial.renameTo(target)
        }
        return target.length()
    }

    /** Tải (hoặc cập nhật) một cuốn: chỉ tải file mới/đổi; book.json ghi CUỐI để sách chỉ hiện khi đã đủ file. */
    @PluginMethod
    fun download(call: PluginCall) {
        val id = call.getString("bookId") ?: return call.reject("thiếu bookId")
        // Sách của thiết bị ghép (Peers): `source` = mã thiết bị ở đây, `remoteId` = mã sách bên ấy.
        val source = call.getString("source")?.takeIf { it.isNotEmpty() }
        call.setKeepAlive(true)
        downloads.execute {
            try {
                val link = if (source != null) Peers.link(context, source) ?: throw IllegalStateException("Thiết bị này đã thôi ghép")
                else Peers.Link(base(), prefs.getString("token", "") ?: "")
                val remote = if (source != null) call.getString("remoteId") ?: throw IllegalArgumentException("thiếu remoteId") else id
                if (source == null) matchImported() // đã mở cuốn này từ file: audio sẵn trên máy, chỉ tải phần còn thiếu
                val manifest = JSONObject(SyncLink.request(context, "GET", "/sync/v1/books/$remote/manifest", root = link.base, token = link.token))
                if (source != null) manifest.put("id", id).put("source", source).put("remoteId", remote)
                val chapters = manifest.getJSONArray("chapters")
                val files = mutableListOf<Pair<String, Long>>()
                for (index in 0 until chapters.length()) {
                    val chapter = chapters.getJSONObject(index)
                    // Văn bản của MỌI chương (vài KB) - chế độ đọc đọc được cả chương chưa thu âm; audio chỉ chương đã có.
                    val script = chapter.optString("script")
                    if (script.isNotBlank() && script != "null") files += script to 0L
                    if (!chapter.optBoolean("available")) continue
                    files += chapter.getString("file") to chapter.optLong("size")
                }
                files += "cast.json" to 0L
                val samples = manifest.optJSONArray("samples") ?: JSONArray()
                for (index in 0 until samples.length()) files += samples.getString(index) to 0L
                // Ảnh bìa thật (webui/covers.py): tải lại mỗi lần (vài trăm KB); máy tính đã bỏ bìa thì xoá bản cũ.
                val cover = manifest.optJSONObject("cover")
                if (cover != null) files += cover.optString("file", "cover.jpg") to 0L
                else Store.file(id, "cover.jpg").delete()
                val total = files.sumOf { it.second }
                var done = 0L
                files.forEachIndexed { index, (relative, size) ->
                    fetchFile(id, relative, size, link, remote)
                    done += size
                    notifyListeners("download", JSObject().put("bookId", id).put("done", done).put("total", total)
                        .put("files", index + 1).put("filesTotal", files.size))
                }
                Store.writeAtomic(File(Store.bookDir(id), "book.json"), manifest.toString())
                File(Store.bookDir(id), "stream.json").delete() // từng nghe thẳng: nay đã tải hẳn
                pushState(id)
                notifyListeners("download", JSObject().put("bookId", id).put("finished", true))
                call.resolve(JSObject().put("bookId", id))
            } catch (error: Exception) {
                notifyListeners("download", JSObject().put("bookId", id).put("error", error.message ?: "lỗi tải"))
                call.reject(error.message ?: "lỗi tải")
            } finally {
                call.setKeepAlive(false)
            }
        }
    }

    // ---- sách trên máy ---------------------------------------------------------------------------------------

    @PluginMethod
    fun localBooks(call: PluginCall) = background(call) {
        val books = JSArray()
        Store.books().forEach { manifest ->
            val id = manifest.getString("id")
            books.put(JSObject.fromJSONObject(manifest).put("state", JSObject.fromJSONObject(Store.state(id)))
                .put("bytes", Store.sizeOf(Store.bookDir(id))))
        }
        call.resolve(JSObject().put("books", books))
    }

    /**
     * Sách trên máy tính CHƯA tải mà nghe thẳng được (Streaming). Gói sách chỉ lấy lại khi máy tính có thêm chương, đổi
     * tên hay đổi bìa, còn lại dùng bản đã cất. Máy tính không trả lời thì trả danh sách rỗng: những cuốn ấy không nằm trên
     * điện thoại, hiện ra mà bấm không nghe được thì chỉ làm người nghe bối rối.
     */
    @PluginMethod
    fun streamableBooks(call: PluginCall) = background(call) {
        val books = JSArray()
        val reply = if (SyncLink.paired(context)) {
            runCatching { JSONObject(SyncLink.request(context, "GET", "/sync/v1/library", readTimeoutMs = 10_000, connectTimeoutMs = 1500)) }.getOrNull()
        } else null
        val remote = reply?.optJSONArray("books") ?: JSONArray()
        if (reply != null) matchImported()
        for (index in 0 until remote.length()) {
            val entry = remote.getJSONObject(index)
            val id = entry.getString("id")
            if (Store.manifest(id) != null) continue
            val cached = Store.streamManifest(id)
            val stale = cached == null ||
                cached.optInt("chaptersAvailable") != entry.optInt("chaptersAvailable") ||
                cached.optString("title") != entry.optString("title") ||
                cached.optJSONObject("cover")?.optLong("version") != entry.optJSONObject("cover")?.optLong("version")
            val manifest = (if (stale) runCatching { Streaming.fetchManifest(context, id) }.getOrNull() else null) ?: cached ?: continue
            if (manifest.optJSONObject("cover") != null && (stale || !Store.file(id, "cover.jpg").isFile)) {
                Streaming.fetchSmall(context, id, "cover.jpg")
            }
            books.put(JSObject.fromJSONObject(manifest).put("state", JSObject.fromJSONObject(Store.state(id))).put("streamed", true))
        }
        // Thiết bị ghép (điện thoại khác, máy tính khác): cùng cách, gói ghi nguồn - thiết bị không trả lời thì bỏ qua.
        val peers = Peers.libraries(context)
        for (index in 0 until peers.length()) {
            val peer = peers.getJSONObject(index)
            val list = peer.optJSONArray("books") ?: continue
            for (item in 0 until list.length()) {
                val entry = list.getJSONObject(item)
                val id = entry.getString("id")
                if (Store.manifest(id) != null) continue
                val cached = Store.streamManifest(id)
                val stale = cached == null || cached.optInt("chaptersAvailable") != entry.optInt("chaptersAvailable") ||
                    cached.optString("title") != entry.optString("title")
                val manifest = (if (stale) runCatching {
                    Streaming.fetchManifest(context, id, peer.getString("key"), entry.getString("remoteId"))
                }.getOrNull() else null) ?: cached ?: continue
                if (manifest.optJSONObject("cover") != null && (stale || !Store.file(id, "cover.jpg").isFile)) {
                    Streaming.fetchSmall(context, id, "cover.jpg")
                }
                books.put(JSObject.fromJSONObject(manifest).put("state", JSObject.fromJSONObject(Store.state(id))).put("streamed", true)
                    .put("sourceName", peer.optString("name")))
            }
        }
        call.resolve(JSObject().put("books", books))
    }

    // ---- thiết bị ghép khác (Peers: điện thoại khác, máy tính khác - mạng trạm bước 2) -----------------------------

    @PluginMethod
    fun peers(call: PluginCall) = background(call) {
        val out = JSArray()
        val all = Peers.all(context)
        for (key in all.keys()) {
            val peer = all.getJSONObject(key)
            out.put(JSObject().put("key", key).put("name", peer.optString("name")).put("host", peer.optString("host"))
                .put("port", peer.optInt("port", 47630)))
        }
        call.resolve(JSObject().put("peers", out))
    }

    @PluginMethod
    fun peerPair(call: PluginCall) = background(call) {
        val host = call.getString("host") ?: throw IllegalArgumentException("thiếu địa chỉ")
        val reply = Peers.pair(context, host, call.getInt("port") ?: 47630, call.getString("code") ?: "")
        call.resolve(JSObject.fromJSONObject(reply))
    }

    @PluginMethod
    fun peerPairBluetooth(call: PluginCall) = background(call) {
        val address = call.getString("address") ?: throw IllegalArgumentException("thiếu máy")
        call.resolve(JSObject.fromJSONObject(Peers.pairBluetooth(context, address, call.getString("code") ?: "")))
    }

    @PluginMethod
    fun peerForget(call: PluginCall) = background(call) {
        Peers.forget(context, call.getString("key") ?: "")
        call.resolve()
    }

    /** Trình phát của máy tính chính và mọi thiết bị ghép lúc này (RemotePlayers). */
    @PluginMethod
    fun remotePlayers(call: PluginCall) = remotes.execute {
        try {
            val out = JSArray()
            val players = RemotePlayers.all(context)
            for (index in 0 until players.length()) out.put(JSObject.fromJSONObject(players.getJSONObject(index)))
            call.resolve(JSObject().put("players", out))
        } catch (error: Exception) {
            call.reject(error.message ?: error.javaClass.simpleName)
        }
    }

    @PluginMethod
    fun remoteCommand(call: PluginCall) = remotes.execute {
        try {
            val device = call.getString("device") ?: throw IllegalArgumentException("thiếu máy")
            val command = call.getObject("command") ?: throw IllegalArgumentException("thiếu lệnh")
            call.resolve(JSObject.fromJSONObject(RemotePlayers.command(context, device, JSONObject(command.toString()))))
        } catch (error: Exception) {
            call.reject(error.message ?: error.javaClass.simpleName)
        }
    }

    @PluginMethod
    fun peerLibraries(call: PluginCall) = background(call) {
        val out = JSArray()
        val peers = Peers.libraries(context)
        for (index in 0 until peers.length()) out.put(JSObject.fromJSONObject(peers.getJSONObject(index)))
        call.resolve(JSObject().put("peers", out))
    }

    @PluginMethod
    fun book(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: throw IllegalArgumentException("thiếu id")
        val local = Store.manifest(id)
        val manifest = local ?: openStreamed(id)
        call.resolve(JSObject.fromJSONObject(manifest).put("state", JSObject.fromJSONObject(Store.state(id))).put("streamed", local == null)
            .put("records", Store.records(id)))
    }

    // ---- hồ sơ nghe (độc lập với sách, app giữ liên kết - Store) -----------------------------------------------

    /** Trả danh sách hồ sơ mới, rồi báo máy tính: hồ sơ vừa rời trước (`left` - chỗ nghe cuối của nó, lưu lúc đổi, chưa
     *  tới máy tính: điện thoại chỉ đẩy hồ sơ đang dùng), rồi hồ sơ đang dùng (lựa chọn, tên, bia mộ). */
    private fun resolveRecords(call: PluginCall, records: JSONArray, left: String? = null) {
        call.resolve(JSObject().put("records", records))
        val id = call.getString("id") ?: return
        io.execute {
            if (left != null && left != Store.knownActiveRecord(id) && Store.hasRecord(left)) {
                runCatching { StateSync.pushNow(context, id, left) }
            }
            runCatching { pushState(id) }
        }
    }

    /** Đổi hồ sơ của một cuốn: cuốn đang nạp trong trình phát thì qua Playback trên luồng chính (trình phát theo sang
     *  hồ sơ mới), cuốn khác thì đổi thẳng. */
    private fun switching(id: String, change: () -> JSONArray): JSONArray {
        if (Playback.bookId != id) return change()
        val task = FutureTask { Playback.switchRecord(id, change) }
        Playback.onMain { task.run() }
        return try {
            task.get(10, TimeUnit.SECONDS)
        } catch (error: ExecutionException) {
            throw error.cause ?: error
        }
    }

    @PluginMethod
    fun createRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val left = Store.knownActiveRecord(id)
        resolveRecords(call, switching(id) { Store.createRecord(id, call.getString("name") ?: "") }, left)
    }

    @PluginMethod
    fun activateRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        val left = Store.knownActiveRecord(id)
        resolveRecords(call, switching(id) { Store.activateRecord(id, call.getString("record")!!) }, left)
    }

    @PluginMethod
    fun renameRecord(call: PluginCall) = background(call) {
        resolveRecords(call, Store.renameRecord(call.getString("id")!!, call.getString("record")!!, call.getString("name") ?: ""))
    }

    @PluginMethod
    fun deleteRecord(call: PluginCall) = background(call) {
        val id = call.getString("id")!!
        resolveRecords(call, switching(id) { Store.deleteRecord(id, call.getString("record")!!) })
    }

    /** Mở một cuốn chưa tải: gói sách mới nhất từ máy tính (mạng lỗi thì bản đã cất), bìa ngay; dàn nhân vật và câu mẫu
     *  lấy ở luồng nền để màn sách hiện ra không phải chờ chúng. */
    private fun openStreamed(id: String): JSONObject {
        // Sách của thiết bị ghép chưa từng mở thư viện của nó ở đây (chưa có stream.json): mã `p<key>_<mã bên ấy>` nói
        // nguồn - "Nghe ở đây" từ thanh trình phát của máy kia đi thẳng tới đó thay vì hỏi nhầm máy tính chính.
        val peer = Peers.sourceOf(context, id)
        val manifest = runCatching { Streaming.fetchManifest(context, id, peer?.first, peer?.second) }.getOrNull()
            ?: Store.streamManifest(id)
            ?: throw IllegalStateException("Cuốn này nằm trên máy tính - kết nối cùng mạng với máy tính để nghe")
        if (manifest.optJSONObject("cover") != null && !Store.file(id, "cover.jpg").isFile) Streaming.fetchSmall(context, id, "cover.jpg")
        downloads.execute {
            if (!Store.file(id, "cast.json").isFile) Streaming.fetchSmall(context, id, "cast.json")
            val samples = manifest.optJSONArray("samples") ?: JSONArray()
            for (index in 0 until samples.length()) {
                val sample = samples.getString(index)
                if (!Store.file(id, sample).isFile) Streaming.fetchSmall(context, id, sample)
            }
        }
        return manifest
    }

    /** Văn bản trong gói (chương để đọc theo, dàn nhân vật). Sách nghe thẳng thì lấy từ máy tính lần đầu rồi cất lại. */
    @PluginMethod
    fun readText(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: ""
        val path = call.getString("path") ?: ""
        var file = Store.file(id, path)
        val fromPeer = !Store.streamManifest(id)?.optString("source").isNullOrEmpty()
        if (!file.isFile && Store.manifest(id) == null && (fromPeer || SyncLink.paired(context))) {
            file = Streaming.fetchSmall(context, id, path) ?: file
        }
        call.resolve(JSObject().put("text", if (file.isFile) file.readText() else ""))
    }

    @PluginMethod
    fun path(call: PluginCall) {
        val file = Store.file(call.getString("id") ?: "", call.getString("path") ?: "")
        call.resolve(JSObject().put("path", file.absolutePath).put("exists", file.isFile))
    }

    @PluginMethod
    fun deleteBook(call: PluginCall) = background(call) {
        Store.deleteBook(call.getString("id") ?: "")
        call.resolve()
    }

    @PluginMethod
    fun storage(call: PluginCall) = background(call) {
        call.resolve(JSObject().put("bytes", Store.sizeOf(File(Store.root, "books"))).put("free", Store.root.usableSpace))
    }

    // ---- trạng thái nghe -------------------------------------------------------------------------------------

    private fun resolveState(call: PluginCall, state: JSONObject) {
        call.resolve(JSObject.fromJSONObject(state))
        val id = call.getString("id") ?: return
        io.execute { runCatching { pushState(id) } }
    }

    @PluginMethod
    fun progress(call: PluginCall) = background(call) {
        resolveState(call, Store.progress(call.getString("id")!!, call.getInt("chapterId")!!, call.getDouble("seconds")!!, call.getDouble("duration") ?: 0.0))
    }

    @PluginMethod
    fun setChapterDone(call: PluginCall) = background(call) {
        resolveState(call, Store.setChapterDone(call.getString("id")!!, call.getInt("chapterId")!!, call.getBoolean("done") ?: true))
    }

    @PluginMethod
    fun setFinished(call: PluginCall) = background(call) {
        resolveState(call, Store.setFinished(call.getString("id")!!, call.getBoolean("finished") ?: true))
    }

    @PluginMethod
    fun setRate(call: PluginCall) = background(call) {
        Store.setRate(call.getString("id")!!, call.getDouble("rate") ?: 1.0)
        call.resolve()
    }

    @PluginMethod
    fun addBookmark(call: PluginCall) = background(call) {
        val mark = Store.addBookmark(call.getString("id")!!, call.getInt("chapterId")!!, call.getDouble("seconds") ?: 0.0, call.getString("note") ?: "")
        call.resolve(JSObject.fromJSONObject(mark))
    }

    @PluginMethod
    fun updateBookmark(call: PluginCall) = background(call) {
        Store.updateBookmark(call.getString("id")!!, call.getString("markId")!!, call.getString("note") ?: "")
        call.resolve()
    }

    @PluginMethod
    fun deleteBookmark(call: PluginCall) = background(call) {
        Store.deleteBookmark(call.getString("id")!!, call.getString("markId")!!)
        call.resolve()
    }

    /**
     * Gửi hồ sơ nghe đang dùng của cuốn lên máy tính (kèm mã, tên hồ sơ, lúc chọn nó), nhận bản đã gộp của ĐÚNG hồ sơ ấy
     * cùng lựa chọn hồ sơ bên kia - bên chọn sau thắng (Store.applySync). Im lặng nếu không có mạng.
     */
    private fun pushState(id: String) = StateSync.pushNow(context, id)

    @PluginMethod
    fun syncState(call: PluginCall) = background(call) {
        val id = call.getString("id") ?: throw IllegalArgumentException("thiếu id")
        pushState(id)
        call.resolve(JSObject.fromJSONObject(Store.state(id)))
    }
}
