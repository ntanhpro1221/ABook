package vn.abook.player.ui.devices

import androidx.compose.runtime.Immutable
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.Fmt

/*
 * Mô hình dữ liệu của ba màn Thiết bị (Nối máy tính, Chia sẻ thư viện, Dung lượng) và phần logic thuần của chúng: lời trạng thái, nhãn nút tải, điều kiện "Kết nối"
 * sẵn sàng, lời hỏi trước khi bỏ ghép. Không Android, không Compose ngoài dấu @Immutable - thử được trên JVM không cần Robolectric.
 * Lời giữ nguyên chữ của bản WebView (android/DevicesScreen.tsx, shared/connectionRoute.ts, shared/unpair.ts) ở những chỗ cùng một ý.
 */

/** Ba màn con của nhóm "Thiết bị" ở Cài đặt. */
enum class DevicesPage { Pair, Share, Storage }

enum class DeviceKind { Computer, Phone }

/** Mã của máy tính chính trong danh sách thiết bị đã ghép (các thiết bị ghép thêm mang mã riêng của chúng). */
const val MAIN_KEY = ""

/** Cổng mặc định của máy tính khi người dùng gõ địa chỉ không kèm cổng. */
const val DEFAULT_PORT = 47630

/** Một máy tìm thấy để ghép: trong Wi-Fi (`address` = host:cổng) hay đã ghép Bluetooth với điện thoại (`address` = bt:địa chỉ). */
@Immutable
data class Found(val address: String, val name: String, val kind: DeviceKind, val bluetooth: Boolean = false, val abook: Boolean = true) {
    val shown: String get() = name.ifBlank { detail }

    /** Máy theo cách danh sách thiết bị đã ghép gọi nó: host trong Wi-Fi, "bt:địa chỉ" qua Bluetooth. */
    val host: String get() = if (bluetooth) address else address.substringBeforeLast(':')

    /** Dòng phụ: địa chỉ máy trong Wi-Fi, hay "Qua Bluetooth". */
    val detail: String get() = if (bluetooth) "Qua Bluetooth" else host
}

/** Máy tính chính lúc này, như `Devices.connection`. */
@Immutable
data class Link(
    val paired: Boolean = false,
    val name: String = "",
    val host: String = "",
    val via: String = "",
    val fingerprint: String = "",
    val deviceName: String = "",
    val lastAddress: String = "",
) {
    val shownName: String get() = name.ifBlank { host.removePrefix("bt:") }.ifBlank { "Máy tính" }
}

/** Máy kia có trả lời lúc này không. */
@Immutable
sealed interface Reach {
    data object Checking : Reach
    data object Ok : Reach

    /** Không nối được: `message` là câu cho người nghe (đã có tên máy), `technical` là chữ gốc của lỗi cho phần chi tiết. */
    data class Offline(val message: String, val technical: String? = null) : Reach

    /** Máy kia đã bỏ ghép điện thoại này - không phải tắt máy hay khác mạng. */
    data object Unpaired : Reach

    /** Chứng chỉ của máy kia đã đổi: `message` là câu bảo ghép lại. */
    data class Changed(val message: String) : Reach
}

/** Một thiết bị đã ghép: máy tính chính (`key` = [MAIN_KEY]) hay thiết bị ghép thêm. */
@Immutable
data class Paired(
    val key: String,
    val name: String,
    val kind: DeviceKind,
    val via: String = "",
    val fingerprint: String = "",
    val reach: Reach = Reach.Checking,
    val books: Int = 0,
    val host: String = "",
) {
    val main: Boolean get() = key == MAIN_KEY
    val failed: Boolean get() = reach !is Reach.Checking && reach !is Reach.Ok

    /** Dòng trạng thái dưới tên: đường nối đang thông, hay lý do không thông. */
    val state: String
        get() = when (reach) {
            Reach.Checking -> if (via.isEmpty()) "Đang kiểm tra" else DeviceText.route(via)
            Reach.Ok -> if (!main && books > 0) "$books cuốn nghe được · ${DeviceText.route(via)}" else DeviceText.route(via)
            is Reach.Offline -> DeviceText.OFFLINE
            Reach.Unpaired -> "$name đã bỏ ghép với điện thoại này"
            is Reach.Changed -> reach.message
        }
}

/** Một cuốn trên máy kia để tải, với việc nút của nó làm. */
@Immutable
data class RemoteBook(
    val id: String,
    /** Mã thiết bị ghép giữ cuốn này (null = máy tính chính) và mã sách bên ấy. */
    val source: String? = null,
    val remoteId: String? = null,
    val title: String,
    val chaptersAvailable: Int = 0,
    val chaptersTotal: Int = 0,
    val duration: Double = 0.0,
    val bytes: Long = 0,
    val producing: Boolean = false,
    val downloaded: Boolean = false,
    val newChapters: Int = 0,
    val newAudio: Boolean = false,
    val newCover: Boolean = false,
    val newMeta: Boolean = false,
    val newWords: Boolean = false,
) {
    /** Còn gì để tải: cuốn chưa tải, hay cuốn đã tải mà máy kia có chương / bản thu / bìa / tên / chữ mới. */
    val upToDate: Boolean get() = downloaded && newChapters <= 0 && !newAudio && !newCover && !newMeta && !newWords

    /** Nhãn nút: "Tải" cho cuốn chưa tải, còn lại nói thứ mới (chương trước, rồi bản thu, bìa, tên, chữ). */
    val action: String
        get() = when {
            !downloaded -> "Tải"
            newChapters > 0 -> "+$newChapters chương"
            newAudio -> "Cập nhật bản thu"
            newCover -> "Cập nhật bìa"
            newMeta -> "Cập nhật tên"
            else -> "Cập nhật chữ"
        }

    /** Dòng phụ: số chương, thời lượng, cỡ khi tải (cuốn chưa tải), "đang làm" khi máy kia còn đang làm cuốn này. */
    val detail: String
        get() = buildString {
            append("$chaptersAvailable/$chaptersTotal chương · ${Fmt.length(duration)}")
            if (!downloaded && bytes > 0) append(" · ${Fmt.size(bytes)}")
            if (producing) append(" · đang làm")
        }
}

/** Sách của một máy, một phần của màn (tiêu đề "Sách trên <tên>"). */
@Immutable
data class BookSection(val source: String?, val deviceName: String, val books: List<RemoteBook>)

/** "Máy tìm thấy" còn lại sau khi bỏ những máy đã ghép (so theo host). */
fun List<Found>.withoutPaired(paired: List<Paired>): List<Found> = filter { found -> paired.none { it.host == found.host } }

// ---- ghép máy ---------------------------------------------------------------------------------------------------------

/** Phần người dùng đang nhập: máy chọn trong danh sách, hay địa chỉ gõ tay, và mã 6 số. */
@Immutable
data class PairForm(val address: String = "", val code: String = "", val picked: String? = null, val manual: Boolean = false) {
    val digits: String get() = code.filter(Char::isDigit)

    /** Nơi sẽ ghép: máy đã chọn, hay địa chỉ gõ tay (có dấu chấm hay dấu hai chấm) khi đang ở chế độ nhập địa chỉ. */
    val target: String?
        get() = picked ?: address.trim().takeIf { manual && (it.contains('.') || it.contains(':')) }

    val ready: Boolean get() = target != null && digits.length == 6
}

/** Địa chỉ gõ tay "host" hay "host:cổng" -> "host:cổng" (cổng mặc định khi thiếu). Null khi không hiểu được. */
fun normalizeAddress(text: String): String? {
    val value = text.trim()
    if (value.isEmpty()) return null
    if (value.startsWith("bt:")) return value
    val colon = value.lastIndexOf(':')
    if (colon < 0) return "$value:$DEFAULT_PORT"
    val port = value.substring(colon + 1).toIntOrNull() ?: return null
    return if (value.substring(0, colon).isNotBlank() && port in 1..65535) value else null
}

@Immutable
sealed interface Attempt {
    data object Idle : Attempt

    /** Đang ghép với `name`: tiến độ ở ngay hàng, không hộp chặn. */
    data class Working(val name: String) : Attempt
    data class Failed(val message: String, val technical: String? = null) : Attempt
}

/** Cách nối: tự tìm trong Wi-Fi, chọn máy đã ghép Bluetooth, hay gõ địa chỉ. */
enum class PairMethod(override val label: String) : Choice {
    Wifi("Wi-Fi"), Bluetooth("Bluetooth"), Address("Địa chỉ");

    override val key: String get() = name.lowercase()
}

/** Tìm máy qua Bluetooth: cần quyền "Thiết bị ở gần" trước. */
@Immutable
sealed interface Bluetooth {
    data object Off : Bluetooth
    data object Listing : Bluetooth

    /** Android không hỏi quyền nữa (từ chối hẳn): chỉ Cài đặt bật lại được. */
    data object Denied : Bluetooth
    data class Devices(val list: List<Found>) : Bluetooth
    data class Failed(val message: String) : Bluetooth
}

// ---- chia sẻ ----------------------------------------------------------------------------------------------------------

@Immutable
data class Code(val digits: String, val expiresAt: Double)

/** Một thiết bị đã ghép để nghe thư viện này. */
@Immutable
data class Sharer(val id: String, val name: String, val lastSeen: Double)

/** Trạng thái chia sẻ thư viện, như `Devices.shareView`. */
@Immutable
data class Share(
    val running: Boolean = false,
    val name: String = "",
    val port: Int = 0,
    val addresses: List<String> = emptyList(),
    val code: Code? = null,
    val blocked: Boolean = false,
    val devices: List<Sharer> = emptyList(),
    val error: String = "",
    val bluetooth: String = "",
    val bluetoothConnections: Int = 0,
    val fingerprint: String = "",
    val backgroundAllowed: Boolean = true,
) {
    /** Địa chỉ để gõ vào máy kia khi nó không tự thấy điện thoại. */
    val addressLine: String
        get() = if (addresses.isEmpty()) "Chưa vào mạng Wi-Fi nào" else addresses.joinToString(", ") { if (':' in it) "[$it]:$port" else "$it:$port" }

    /** Bluetooth của chia sẻ báo thiếu quyền "Thiết bị ở gần". */
    val needsNearby: Boolean get() = bluetooth.contains("Thiết bị ở gần")

    /** Dòng Bluetooth khi nó mang tin: số máy đang nối, hay lý do không bật được. Null khi chưa bật. */
    val bluetoothLine: String?
        get() = when {
            bluetooth.isEmpty() -> null
            bluetooth == "running" -> if (bluetoothConnections > 0) "Bluetooth: $bluetoothConnections máy đang nối" else null
            else -> bluetooth
        }
}

// ---- dung lượng -------------------------------------------------------------------------------------------------------

/** Một thứ đang chiếm chỗ trên máy: cuốn đã tải xong, hay `partial` - phần tải dở / gói nghe thẳng đã nhớ (cuốn vẫn ở máy kia). */
@Immutable
data class Stored(val id: String, val title: String, val bytes: Long, val partial: Boolean, val holder: String = "")

@Immutable
data class Storage(val bytes: Long = 0, val free: Long = 0, val entries: List<Stored> = emptyList()) {
    /** Một dòng cho phần đầu danh sách: "Sách 1,2 GB · còn trống 20 GB" (cùng lời web). */
    val line: String get() = "Sách ${Fmt.size(bytes)} · còn trống ${Fmt.size(free)}"
}

// ---- bỏ ghép ----------------------------------------------------------------------------------------------------------

/** Phần sửa chưa gửi và dữ liệu đã tải của một thiết bị ghép thêm - thứ bỏ ghép sẽ quên (Peers.unsent / Peers.cached). */
@Immutable
data class Unsent(
    val books: List<UnsentBook> = emptyList(),
    val changes: Int = 0,
    val sendable: Boolean = false,
    val cacheBooks: Int = 0,
    val cacheBytes: Long = 0,
    val places: Int = 0,
)

@Immutable
data class UnsentBook(val title: String, val changes: Int)

enum class ForgetChoice { Plain, Send, Discard }

/** Lời hỏi trước khi bỏ ghép: mỗi ý một dòng (mất gì, giữ gì), nhãn nút "gửi trước" (null khi máy kia không nhận sửa), nhãn nút bỏ. */
@Immutable
data class ForgetCopy(val title: String, val lines: List<String>, val send: String?, val discard: String, val edited: Boolean = false)

object DeviceText {
    const val OFFLINE = "Không kết nối được - máy đang tắt hoặc khác Wi-Fi"

    /** Trang tải ABook cho máy tính (web: DESKTOP_RELEASES của android/DevicesScreen.tsx) - "Tải ABook Windows" mở nó, "Chép địa chỉ" chép nó. */
    const val DESKTOP_RELEASES = "https://github.com/ntanhpro1221/ABook/releases"

    /** Tên công tắc chia sẻ trên máy tính (web: SYNC_SWITCH_LABEL của shared/syncSwitch.ts) - lời "Cách lấy mã" gọi đúng tên ấy. */
    const val SYNC_SWITCH_LABEL = "Kết nối Wi-Fi"

    /** "Cách lấy mã": mã 6 số lấy ở đâu trên máy tính (cùng câu với PairPanel của web). */
    const val PAIR_CODE_HELP = "Trong Cài đặt › Thiết bị của máy tính, bật “$SYNC_SWITCH_LABEL” rồi chọn ghép thiết bị để lấy mã 6 số."

    /** "Nghe khi ra ngoài": máy đã ghép không trả lời vì khác mạng - app không cần gì riêng, mạng riêng ảo cho máy tính một địa chỉ tới được (web DevicesScreen). */
    const val AWAY_HELP = "Cho hai máy vào cùng một mạng riêng ảo (Tailscale, ZeroTier, NetBird, WireGuard), rồi mở mục này một lần khi còn ở nhà."

    /** Cùng chữ với shared/connectionRoute.ts: nói đường nối thành công, không lộ địa chỉ. */
    fun route(address: String?): String {
        if (address.isNullOrEmpty()) return "Chưa kết nối"
        if (address == "bluetooth" || address.lowercase().startsWith("bt:")) return "Đang nối qua Bluetooth"
        val host = if (address.startsWith("[")) address.substring(1, address.indexOf(']').let { if (it < 0) address.length else it }) else address.substringBefore(':')
        val parts = host.split('.').map { it.toIntOrNull() }
        if (parts.size == 4 && parts.all { it != null && it in 0..255 }) {
            val a = parts[0]!!
            val b = parts[1]!!
            if (a == 100 && b in 64..127) return "Đang nối qua Tailscale"
            if (a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168)) return "Đang nối qua Wi-Fi nhà"
        }
        return "Đang nối qua mạng"
    }

    /** Dòng mốc thời gian của máy nghe thư viện này: lần cuối thấy nó. */
    fun seen(lastSeen: Double, nowMs: Long = System.currentTimeMillis()): String =
        Fmt.whenText(lastSeen, nowMs).let { if (it.isEmpty()) "Chưa thấy" else "Thấy $it" }

    /** Giờ hết hạn của mã ghép, như "14:12" (giờ máy). */
    fun clock(epochSeconds: Double): String {
        val calendar = java.util.Calendar.getInstance().apply { timeInMillis = (epochSeconds * 1000).toLong() }
        return String.format(java.util.Locale.ROOT, "%02d:%02d", calendar.get(java.util.Calendar.HOUR_OF_DAY), calendar.get(java.util.Calendar.MINUTE))
    }

    /** Phần thuần của "Bỏ ghép" thiết bị ghép thêm (shared/unpair.ts, `self` = điện thoại): null khi không còn gì để mất - bỏ luôn không hỏi. */
    fun forgetCopy(device: String, unsent: Unsent?, reachable: Boolean): ForgetCopy? {
        val edited = unsent != null && unsent.changes > 0 && unsent.books.isNotEmpty()
        val cache = unsent != null && unsent.cacheBooks > 0
        if (unsent == null || (!edited && !cache)) return null
        val lines = ArrayList<String>()
        if (cache) {
            val downloaded = if (unsent.cacheBytes > 0) {
                ", và ${if (unsent.cacheBytes < 1024L * 1024) "dưới 1 MB" else Fmt.size(unsent.cacheBytes)} đã tải về điện thoại này sẽ bị xoá"
            } else ""
            lines += "${unsent.cacheBooks} cuốn của $device sẽ rời Thư viện$downloaded."
            if (unsent.places > 0) lines += "Chỗ nghe của ${unsent.places} cuốn vẫn giữ - ghép lại đúng $device là nghe tiếp được."
        }
        var send: String? = null
        if (edited) {
            val names = unsent.books.take(3).map { "“${it.title}”" }
            val rest = unsent.books.size - names.size
            lines += "${unsent.books.size} cuốn có ${unsent.changes} thay đổi chưa gửi về $device sẽ mất: ${names.joinToString(", ")}${if (rest > 0) " và $rest cuốn khác" else ""}."
            if (!unsent.sendable) {
                lines += "$device không nhận phần sửa - những thay đổi này chỉ có trên điện thoại này."
            } else if (reachable) {
                send = "Gửi trước rồi bỏ ghép"
            } else {
                send = "Thử gửi trước rồi bỏ ghép"
                lines += "$device đang tắt hay khác mạng lúc này nên chưa gửi được - mở máy ấy rồi gửi, hay bỏ thay đổi."
            }
        }
        return ForgetCopy("Bỏ ghép $device?", lines, send, if (edited) "Vẫn bỏ ghép, bỏ thay đổi" else "Bỏ ghép", edited)
    }

    /** Lời khi máy tính chỉ cho điện thoại nghe (không mở được Studio) - nói trước khi bấm. */
    fun listenOnly(name: String): String =
        "Máy tính $name chỉ cho nghe - trên máy tính ấy, bật Cài đặt › Thiết bị › “Điều khiển từ xa”."
}

/** Máy tính mở được Studio từ điện thoại (`Devices.studioComputers`). */
@Immutable
data class StudioComputer(val key: String, val name: String, val listenOnly: Boolean)
