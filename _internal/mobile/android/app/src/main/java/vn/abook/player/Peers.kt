package vn.abook.player

import android.content.Context
import android.net.Uri
import android.os.Build
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.UUID

/**
 * Thiết bị đã ghép NGOÀI máy tính chính (SyncLink): điện thoại khác bật "Cho máy khác nghe thư viện này" (LibraryServer)
 * hay một máy tính nữa - mạng trạm bước 2, điện thoại <-> điện thoại (chủ sách 27-09). Cùng giao thức cổng đồng bộ.
 *
 * Sách của một thiết bị ghép mang mã CỤC BỘ riêng (`localId`: không đụng mã sách của máy tính chính hay của thiết bị
 * khác) và ghi nguồn ngay trong gói (`source` = mã thiết bị ở đây, `remoteId` = mã sách bên ấy) - nên nghe thẳng, tải về,
 * văn bản đọc theo và chỗ nghe đều đi đúng máy (SyncLink.linkFor). Máy tính chính giữ nguyên như trước (Studio từ xa,
 * điều khiển từ xa, báo sách xong chỉ có ở máy tính).
 */
object Peers {
    data class Link(val base: String, val token: String)

    private fun prefs(context: Context) = context.getSharedPreferences("peers", Context.MODE_PRIVATE)

    /** key -> {name, host, port, token, fingerprint, kind, pairedAt}. */
    @Synchronized
    fun all(context: Context): JSONObject =
        runCatching { JSONObject(prefs(context).getString("peers", "{}") ?: "{}") }.getOrDefault(JSONObject())

    @Synchronized
    private fun save(context: Context, peers: JSONObject) {
        prefs(context).edit().putString("peers", peers.toString()).commit()
    }

    fun link(context: Context, key: String): Link? {
        Pin.install(context)
        val peer = all(context).optJSONObject(key) ?: return null
        val host = peer.optString("host")
        if (host.startsWith("bt:")) return Link(BluetoothLink.base(context, host.removePrefix("bt:")), peer.optString("token"))
        return Link("https://$host:${peer.optInt("port", 47630)}", peer.optString("token"))
    }

    /** Ghép thiết bị đã ghép Bluetooth với điện thoại này (không chung Wi-Fi): cùng mã 6 số, đi qua đường hầm. */
    fun pairBluetooth(context: Context, address: String, code: String): JSONObject {
        val device = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
        val body = JSONObject().put("code", code.filter { it.isDigit() }).put("device", device)
        val root = BluetoothLink.base(context, address)
        val (reply, fingerprint) = try {
            SyncLink.pair(context, root, body)
        } catch (error: Exception) {
            throw IllegalStateException(BluetoothLink.lastError(address).ifBlank { error.message ?: "không kết nối được qua Bluetooth" })
        }
        val host = "bt:$address"
        val peers = all(context)
        val key = peers.keys().asSequence().firstOrNull { peers.getJSONObject(it).optString("host") == host }
            ?: UUID.randomUUID().toString().replace("-", "").take(8)
        peers.put(key, JSONObject().put("name", reply.optString("name", address)).put("host", host).put("port", 0)
            .put("token", reply.getString("token")).put("fingerprint", fingerprint)
            .put("pairedAt", System.currentTimeMillis() / 1000.0))
        save(context, peers)
        return JSONObject().put("key", key).put("name", reply.optString("name", address))
    }

    /** Mã sách cục bộ cho một cuốn của thiết bị ghép: chữ cái đầu "p" + mã thiết bị + mã sách bên ấy (mọi ký tự đều nằm
     *  trong [A-Za-z0-9_-] - thư viện của chính điện thoại này phục vụ lại được). */
    fun localId(key: String, remoteId: String) = "p${key}_$remoteId"

    /** Ngược của `localId` cho một thiết bị đang ghép: (key, mã bên ấy), hay null nếu không phải sách của thiết bị ghép. */
    fun sourceOf(context: Context, localId: String): Pair<String, String>? =
        all(context).keys().asSequence().firstOrNull { localId.startsWith("p${it}_") }
            ?.let { it to localId.removePrefix("p${it}_") }

    /** Ghép bằng mã 6 số đang hiện trên thiết bị kia (điện thoại: màn Tải sách; máy tính: Cài đặt). Ghép lại cùng địa chỉ
     *  thì thay chỗ cũ - sách đã tải và chỗ nghe giữ nguyên. */
    fun pair(context: Context, host: String, port: Int, code: String): JSONObject {
        val device = "${Build.MANUFACTURER} ${Build.MODEL}".trim()
        val body = JSONObject().put("code", code.filter { it.isDigit() }).put("device", device)
        val (reply, fingerprint) = SyncLink.pair(context, "https://$host:$port", body)
        val peers = all(context)
        val key = peers.keys().asSequence().firstOrNull { existing ->
            peers.getJSONObject(existing).let { it.optString("host") == host && it.optInt("port") == port }
        } ?: UUID.randomUUID().toString().replace("-", "").take(8)
        peers.put(key, JSONObject().put("name", reply.optString("name", host)).put("host", host).put("port", port)
            .put("token", reply.getString("token")).put("fingerprint", fingerprint)
            .put("pairedAt", System.currentTimeMillis() / 1000.0))
        save(context, peers)
        return JSONObject().put("key", key).put("name", reply.optString("name", host))
    }

    /** Sách nghe thẳng (chưa tải: không có `book.json`) của thiết bị `key` - đúng những thư mục `forget` xoá. */
    private fun streamedDirs(key: String): List<File> =
        File(Store.root, "books").listFiles()?.filter { it.isDirectory && it.name.startsWith("p${key}_") && !File(it, "book.json").isFile } ?: emptyList()

    /** Sửa chưa gửi của các cuốn nghe thẳng của một thiết bị: mỗi cuốn còn bao nhiêu thay đổi (gồm cả ý muốn chờ Studio, trừ phần đã gửi rồi - [EditsSync.pending]). */
    class Unsent(val books: List<Book>) {
        class Book(val id: String, val title: String, val changes: Int)

        val changes get() = books.sumOf { it.changes }
    }

    /**
     * Phần sửa của người nghe đang nằm trong thư mục các cuốn nghe thẳng của `key` - thứ mà thôi ghép sẽ xoá cùng thư mục. Cuốn đã
     * tải giữ nguyên khi thôi ghép (cả lớp sửa của nó) nên không tính ở đây.
     */
    fun unsent(key: String): Unsent = Unsent(
        streamedDirs(key).mapNotNull { dir ->
            val changes = EditsSync.pending(dir, BookEdits.load(dir)) // cách đọc / nhạc đã gửi rồi mà còn nằm ở lớp sửa thì không tính là chưa gửi
            if (changes == 0) null else Unsent.Book(dir.name, Store.playableManifest(dir.name)?.optString("title").orEmpty().ifEmpty { dir.name }, changes)
        }.sortedBy { it.id },
    )

    /**
     * Gửi hết phần sửa chưa gửi của `key` về máy ấy trước khi thôi ghép: `send(mã sách)` gửi một cuốn và ném lỗi nếu máy kia không
     * nhận (cuốn ấy cùng các cuốn sau giữ nguyên). Gửi xong mà vẫn còn sửa (vd người dùng sửa thêm giữa chừng) cũng là lỗi - không
     * bao giờ coi như xong khi còn thứ sẽ mất.
     */
    fun sendUnsent(key: String, send: (String) -> Unit) {
        for (book in unsent(key).books) send(book.id)
        val left = unsent(key)
        if (left.books.isNotEmpty()) throw IllegalStateException("Còn ${left.changes} thay đổi chưa gửi về máy kia - chưa thôi ghép")
    }

    /** Từ chối thôi ghép khi còn sửa chưa gửi mà người dùng chưa chọn bỏ (`discard`): lỗi nói số cuốn và số thay đổi sẽ mất. */
    internal fun refuseIfUnsent(key: String, discard: Boolean) {
        if (discard) return
        val left = unsent(key)
        if (left.books.isNotEmpty()) {
            throw IllegalStateException("${left.books.size} cuốn còn ${left.changes} thay đổi chưa gửi - gửi trước hay chọn bỏ rồi thôi ghép")
        }
    }

    /** Thôi ghép: bỏ mã thiết bị và mọi sách CHƯA TẢI (chỉ nghe thẳng) của thiết bị ấy; sách đã tải giữ lại. Còn sửa chưa gửi mà
     *  `discard` = false thì từ chối, không đổi gì (gọi [unsent] để hỏi người dùng trước). */
    fun forget(context: Context, key: String, discard: Boolean = false) {
        refuseIfUnsent(key, discard)
        val peers = all(context)
        peers.optJSONObject(key)?.optString("host")?.takeIf { it.startsWith("bt:") }?.let { BluetoothLink.forget(it) }
        peers.remove(key)
        save(context, peers)
        streamedDirs(key).forEach { it.deleteRecursively() }
    }

    fun request(context: Context, key: String, method: String, path: String, body: JSONObject? = null,
                readTimeoutMs: Int = 20_000, connectTimeoutMs: Int = 5000, upload: File? = null): String {
        val link = link(context, key) ?: throw IllegalStateException("Thiết bị này chưa ghép")
        return SyncLink.request(context, method, path, body, auth = false, root = link.base, readTimeoutMs = readTimeoutMs,
            connectTimeoutMs = connectTimeoutMs, token = link.token, upload = upload)
    }

    /** Loại thiết bị ghép đã biết ("computer": máy tính khác - nhận gói sửa như máy tính chính; "phone": điện thoại - không nhận), hay "" khi chưa thấy. */
    fun kindOf(context: Context, key: String): String = all(context).optJSONObject(key)?.optString("kind").orEmpty()

    /** Ghi loại thiết bị mà thiết bị tự báo trong lời đáp thư viện (`kind`); chỉ ghi khi đổi. */
    @Synchronized
    private fun rememberKind(context: Context, key: String, kind: String) {
        if (kind.isEmpty()) return
        val peers = all(context)
        val peer = peers.optJSONObject(key) ?: return
        if (peer.optString("kind") == kind) return
        save(context, peers.put(key, peer.put("kind", kind)))
    }

    /** Thư viện của từng thiết bị ghép, mỗi cuốn kèm mã cục bộ và trạng thái đã tải; thiết bị không trả lời thì `error`. */
    fun libraries(context: Context): JSONArray {
        val out = JSONArray()
        val peers = all(context)
        for (key in peers.keys()) {
            val peer = peers.getJSONObject(key)
            val entry = JSONObject().put("key", key).put("name", peer.optString("name")).put("host", peer.optString("host"))
                .put("fingerprint", peer.optString("fingerprint"))
            try {
                val reply = JSONObject(request(context, key, "GET", "/sync/v1/library", readTimeoutMs = 8000, connectTimeoutMs = 1500))
                val books = reply.optJSONArray("books") ?: JSONArray()
                rememberKind(context, key, reply.optString("kind"))
                for (index in 0 until books.length()) {
                    val book = books.getJSONObject(index)
                    val local = localId(key, book.getString("id"))
                    val downloaded = Store.manifest(local)
                    book.put("remoteId", book.getString("id")).put("id", local).put("source", key)
                        .put("downloaded", downloaded != null)
                        .put("localChapters", downloaded?.optInt("chaptersAvailable") ?: 0)
                        .put("localCoverVersion", downloaded?.optJSONObject("cover")?.optLong("version") ?: 0L)
                        .put("localWordsVersion", downloaded?.optString("wordsVersion") ?: "")
                }
                entry.put("name", reply.optString("name", peer.optString("name"))).put("books", books)
            } catch (error: Exception) {
                entry.put("books", JSONArray()).put("error", error.message ?: "không kết nối được")
                if (error is Pin.ChangedException) entry.put("pinChanged", true)
            }
            out.put(entry)
        }
        return out
    }

    /** Thiết bị ghép nào giữ địa chỉ này (để trình phát gắn đúng mã thiết bị vào từng yêu cầu audio). */
    fun tokenFor(context: Context, uri: Uri): String? {
        val peers = all(context)
        for (key in peers.keys()) {
            val peer = peers.getJSONObject(key)
            val host = peer.optString("host")
            if (host.startsWith("bt:")) {
                if (uri.toString().startsWith(BluetoothLink.base(context, host.removePrefix("bt:")))) return peer.optString("token")
                continue
            }
            if (peer.optString("host") == uri.host && peer.optInt("port", 47630) == uri.port) return peer.optString("token")
        }
        return null
    }
}
