package vn.abook.player

import android.content.Context
import org.json.JSONObject

/**
 * Máy tính nào mở Studio cho StudioActivity, trang nào trong Studio ấy, và chờ máy ấy trả lời lại - như "Mở Studio" của máy
 * tính (webui/peer_studio.py, ui/src/shared/peerStudio.ts) nhưng không cần cầu nối: cả trang là của máy tính kia.
 *
 * Mã thiết bị không bao giờ nằm trong đường trang hay Intent: StudioActivity đặt nó vào cookie HttpOnly của đúng máy ấy.
 */
object StudioLink {
    /** Mã của máy tính chính (SyncLink); máy tính ghép thêm mang mã của nó trong [Peers]. */
    const val MAIN = ""

    /** Hai máy khác bản (cùng câu với máy tính: peer_studio.MISMATCH). */
    const val MISMATCH = "Cập nhật ABook ở hai máy cùng phiên bản"

    private val BOOK = Regex("[A-Za-z0-9_-]+")

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

    /** Đường trang Studio của một cuốn (`book` = mã cuốn ở máy ấy) hay danh sách dự án khi không có cuốn / mã lạ. */
    fun bookPath(book: String?): String = if (book != null && BOOK.matches(book)) "/#/studio/$book" else "/#/studio"

    /** Đường trang mà Intent xin (thông báo Studio: "/#/studio/<mã>?tab=work"): chỉ nhận trang của Studio, còn lại về danh sách dự án. */
    fun safePath(requested: String?): String = requested?.takeIf { it.startsWith("/#/studio") } ?: "/#/studio"

    /**
     * Trang đang xem khi máy ấy trả lời lại, ở gốc mới (máy tính chính nối lại qua đường khác: Wi-Fi <-> Bluetooth). `url` không thuộc
     * gốc cũ (chưa nạp được gì) thì về `fallback` - trang đã xin lúc mở.
     */
    fun rebase(url: String?, oldBase: String, newBase: String, fallback: String): String {
        val rest = url?.takeIf { it.startsWith("$oldBase/") }?.removePrefix(oldBase) ?: fallback
        return newBase + rest
    }

    /** Máy ấy trả lời `/api/app` với bản `theirs`: lệch bản của điện thoại thì không mở. Bản chạy từ mã nguồn ("" / "dev") không so được. */
    fun mismatched(theirs: String, ours: String): Boolean = theirs.isNotBlank() && theirs != "dev" && theirs != ours

    /** "Máy <tên>" - tên đã mở đầu bằng "Máy" thì không thêm (như remote_books._called). */
    fun called(name: String): String =
        if (name.lowercase().startsWith("máy ")) name.replaceFirstChar { it.uppercase() } else "Máy $name"

    /** Dòng của màn chờ khi máy ấy không trả lời (tắt, đổi mạng). */
    fun silentLine(name: String): String = "${called(name)} không trả lời - đang chờ nối lại"

    /**
     * Hỏi `reachable` mỗi `everyMs` tới khi nó trả true thì gọi `onBack` một lần rồi thôi; quá `giveUpMs` thì thôi hỏi (còn nút Thử
     * lại) - cùng nhịp với ui/src/listen/peerBack.ts `watchUntilBack`. Lỗi khi hỏi = chưa trả lời. `schedule(ms, việc)` chạy việc ở
     * luồng nền (hỏi mạng); `onBack` cũng gọi ở đó.
     */
    class Watch(
        private val reachable: () -> Boolean,
        private val onBack: () -> Unit,
        private val schedule: (Long, () -> Unit) -> Unit,
        private val now: () -> Long = System::currentTimeMillis,
        private val everyMs: Long = 5000,
        private val giveUpMs: Long = 30 * 60_000L,
    ) {
        @Volatile var stopped = false
            private set
        private var started = 0L

        fun start(): Watch {
            started = now()
            schedule(everyMs, ::tick)
            return this
        }

        fun stop() {
            stopped = true
        }

        private fun tick() {
            if (stopped) return
            if (now() - started > giveUpMs) return stop()
            val back = runCatching(reachable).getOrDefault(false)
            if (stopped) return
            if (back) {
                stop()
                onBack()
            } else {
                schedule(everyMs, ::tick)
            }
        }
    }

    /** Gốc https và mã thiết bị của máy tính `key` lúc này (máy tính chính: theo đường đang thông), hay null khi đã thôi ghép. */
    fun link(context: Context, key: String): Peers.Link? =
        if (key == MAIN) Peers.Link(SyncLink.base(context), SyncLink.token(context)).takeIf { SyncLink.paired(context) }
        else Peers.link(context, key)?.takeIf { known(key, SyncLink.paired(context), Peers.all(context)) }

    /** Tên máy tính `key` như người dùng thấy ở màn Tải sách. */
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
