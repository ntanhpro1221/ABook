package vn.abook.player

import android.content.Context
import org.json.JSONObject

/**
 * Máy tính nào mở Studio, so bản và báo máy chỉ cho nghe - như "Mở Studio" của máy tính (webui/peer_studio.py, ui/src/shared/peerStudio.ts).
 * Studio của điện thoại là màn native (ui/studio): mã máy và mã sách đi qua Intent, không bao giờ mã thiết bị.
 */
object StudioLink {
    /** Mã của máy tính chính (SyncLink); máy tính ghép thêm mang mã của nó trong [Peers]. */
    const val MAIN = ""

    data class Computer(val key: String, val name: String)

    /**
     * Máy tính mở Studio được, theo thứ tự hiện: máy tính chính (khi đã ghép) rồi các máy tính ghép thêm. Thiết bị ghép là điện thoại
     * (hay chưa biết loại - chưa từng trả lời) thì không có Studio. `peers`: [Peers.all].
     */
    fun computers(mainPaired: Boolean, mainName: String, peers: JSONObject): List<Computer> {
        val out = mutableListOf<Computer>()
        if (mainPaired) out += Computer(MAIN, mainName.ifBlank { "Máy tính" })
        for (key in peers.keys().asSequence().sorted()) {
            val peer = peers.optJSONObject(key) ?: continue
            if (peer.optString("kind") == "computer") out += Computer(key, peer.optString("name").ifBlank { "Máy tính" })
        }
        return out
    }

    /** Máy tính `key` còn ghép không (máy tính chính: đã ghép; máy ghép thêm: còn trong [Peers] và là máy tính). */
    fun known(key: String, mainPaired: Boolean, peers: JSONObject): Boolean =
        computers(mainPaired, "", peers).any { it.key == key }

    /**
     * `/api/app` của máy tính nói thiết bị này chỉ được nghe (remote_studio.forward: `listenOnly`, khi công tắc "Điều khiển từ xa" hay quyền riêng
     * của điện thoại tắt). Không đọc được = không biết = false: nút vẫn mở, trang Studio của máy ấy tự nói.
     */
    fun listenOnly(appJson: String): Boolean = runCatching { JSONObject(appJson).optBoolean("listenOnly", false) }.getOrDefault(false)

    /** Máy ấy trả lời `/api/app` với bản `theirs`: lệch bản của điện thoại thì không mở. Bản chạy từ mã nguồn ("" / "dev") không so được. */
    fun mismatched(theirs: String, ours: String): Boolean = theirs.isNotBlank() && theirs != "dev" && theirs != ours

    /** "Máy <tên>" - tên đã mở đầu bằng "Máy" thì không thêm (như remote_books._called). */
    fun called(name: String): String =
        if (name.lowercase().startsWith("máy ")) name.replaceFirstChar { it.uppercase() } else "Máy $name"

    /** Dòng của màn chờ khi máy ấy không trả lời (tắt, đổi mạng). */
    fun silentLine(name: String): String = "${called(name)} không trả lời - đang chờ nối lại"

    /** Gốc https và mã thiết bị của máy tính `key` lúc này (máy tính chính: theo đường đang thông), hay null khi đã bỏ ghép. */
    fun link(context: Context, key: String): Peers.Link? =
        if (key == MAIN) Peers.Link(SyncLink.base(context), SyncLink.token(context)).takeIf { SyncLink.paired(context) }
        else Peers.link(context, key)?.takeIf { known(key, SyncLink.paired(context), Peers.all(context)) }

    /** Tên máy tính `key` như người dùng thấy ở Cài đặt › Thiết bị. */
    fun name(context: Context, key: String): String =
        computers(SyncLink.paired(context), SyncLink.prefs(context).getString("name", "").orEmpty(), Peers.all(context))
            .firstOrNull { it.key == key }?.name ?: "Máy tính"

    /** Máy tính mở Studio được lúc này. */
    fun computers(context: Context): List<Computer> =
        computers(SyncLink.paired(context), SyncLink.prefs(context).getString("name", "").orEmpty(), Peers.all(context))

    /**
     * Cuốn `id` trên điện thoại này là dự án Studio đang làm ở máy tính nào: (mã máy, mã cuốn ở máy ấy), hay null - cuốn của điện thoại
     * khác, mở từ file, hay máy tính không đánh dấu `studio` (sync.py book_manifest). Nơi gửi phần sửa của cuốn cũng là máy giữ nó.
     */
    fun bookTarget(id: String): Pair<String, String>? {
        val manifest = Store.rawManifest(id) ?: Store.streamManifest(id) ?: return null
        if (!manifest.optBoolean("studio")) return null
        val (source, remote) = Store.editDestination(id) ?: return null
        return (source ?: MAIN) to remote
    }
}
