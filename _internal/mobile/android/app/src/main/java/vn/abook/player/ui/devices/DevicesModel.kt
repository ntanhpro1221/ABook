package vn.abook.player.ui.devices

import vn.abook.player.S

import vn.abook.player.formatSize
import vn.abook.player.BuildConfig

import androidx.compose.runtime.Immutable
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.data.Fmt

/*
 * Mô hình dữ liệu của ba màn Thiết bị (Nối máy tính, Chia sẻ thư viện, Dung lượng) và phần logic thuần của chúng: lời trạng thái, nhãn nút tải, điều kiện "Kết nối"
 * sẵn sàng, lời hỏi trước khi bỏ ghép. Không Android, không Compose ngoài dấu @Immutable - thử được trên JVM không cần Robolectric.
 */

/** Ba màn con của nhóm "Thiết bị" ở Cài đặt. */
enum class DevicesPage { Pair, Share, Storage }

enum class DeviceKind { Computer, Phone }

/** Mã của máy tính chính trong danh sách thiết bị đã ghép (các thiết bị ghép thêm mang mã riêng của chúng). */
const val MAIN_KEY = ""

/** Cổng mặc định của máy tính khi người dùng gõ địa chỉ không kèm cổng. */
const val DEFAULT_PORT = BuildConfig.DEFAULT_PEER_PORT

/** Một máy tìm thấy để ghép: trong Wi-Fi (`address` = host:cổng) hay đã ghép Bluetooth với điện thoại (`address` = bt:địa chỉ). */
@Immutable
data class Found(val address: String, val name: String, val kind: DeviceKind, val bluetooth: Boolean = false, val abook: Boolean = true) {
    val shown: String get() = name.ifBlank { detail }

    /** Máy theo cách danh sách thiết bị đã ghép gọi nó: host trong Wi-Fi, "bt:địa chỉ" qua Bluetooth. */
    val host: String get() = if (bluetooth) address else address.substringBeforeLast(':')

    /** Dòng phụ: địa chỉ máy trong Wi-Fi, hay S.s_qua_bluetooth_983cecc1. */
    val detail: String get() = if (bluetooth) S.s_qua_bluetooth_983cecc1 else host
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
    val shownName: String get() = name.ifBlank { host.removePrefix("bt:") }.ifBlank { S.s_may_tinh_828ebb9d }
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
            Reach.Checking -> if (via.isEmpty()) S.s_dang_kiem_tra_424c43e3 else DeviceText.route(via)
            Reach.Ok -> if (!main && books > 0) S.s_0_cuon_nghe_duoc_1_a4f8332c(books, DeviceText.route(via)) else DeviceText.route(via)
            is Reach.Offline -> DeviceText.OFFLINE
            Reach.Unpaired -> S.s_0_da_bo_ghep_voi_dien_thoai_nay_1f625c42(name)
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
            !downloaded -> S.s_tai_73be7aad
            newChapters > 0 -> S.s_0_chuong_7d8fad7e(newChapters)
            newAudio -> S.s_cap_nhat_ban_thu_632992d0
            newCover -> S.s_cap_nhat_bia_ac9878fb
            newMeta -> S.s_cap_nhat_ten_15b727cc
            else -> S.s_cap_nhat_chu_1a3e07d8
        }

    /** Dòng phụ: số chương, thời lượng, cỡ khi tải (cuốn chưa tải), "đang làm" khi máy kia còn đang làm cuốn này. */
    val detail: String
        get() = buildString {
            append(S.s_0_1_chuong_2_469dd411(chaptersAvailable, chaptersTotal, Fmt.length(duration)))
            if (!downloaded && bytes > 0) append(" · ${formatSize(bytes)}")
            if (producing) append(S.s_dang_lam_0fb7a8f9)
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
    Wifi(S.s_tu_tim_3f09ad05), Bluetooth(S.s_bluetooth_8bb29098), Address(S.s_nhap_dia_chi_4a264769);

    override val key: String get() = name.lowercase()
}

/** Tìm máy qua Bluetooth: cần quyền "Thiết bị ở gần" trước. */
@Immutable
sealed interface Bluetooth {
    data object Off : Bluetooth
    data object Explain : Bluetooth
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
        get() = if (addresses.isEmpty()) S.s_chua_vao_mang_wi_fi_nao_7f74d463 else addresses.joinToString(", ") { if (':' in it) "[$it]:$port" else "$it:$port" }

    /** Bluetooth của chia sẻ báo thiếu quyền "Thiết bị ở gần". */
    val needsNearby: Boolean get() = bluetooth.contains(S.s_thiet_bi_o_gan_ae6fdbbc)

    /** Dòng Bluetooth khi nó mang tin: số máy đang nối, hay lý do không bật được. Null khi chưa bật. */
    val bluetoothLine: String?
        get() = when {
            bluetooth.isEmpty() -> null
            bluetooth == "running" -> if (bluetoothConnections > 0) S.s_bluetooth_0_may_dang_noi_72627bd6(bluetoothConnections) else null
            else -> bluetooth
        }
}

// ---- dung lượng -------------------------------------------------------------------------------------------------------

/** Một thứ đang chiếm chỗ trên máy: cuốn đã tải xong, hay `partial` - phần tải dở / gói nghe thẳng đã nhớ (cuốn vẫn ở máy kia). */
@Immutable
data class Stored(val id: String, val title: String, val bytes: Long, val partial: Boolean, val holder: String = "")

@Immutable
data class Storage(val bytes: Long = 0, val free: Long = 0, val entries: List<Stored> = emptyList()) {
    /** Một dòng cho phần đầu danh sách: "Sách 1,2 GB · còn trống 20 GB"; chưa có sách (dưới 1 KB) thì "Chưa có sách · còn trống 20 GB" (web: storageSummary, cùng từng chữ). */
    val line: String get() = S.s_0_con_trong_1_2568383f(if (bytes < 1024) S.s_chua_co_sach_30843cb2 else S.s_sach_0_529204b5(formatSize(bytes)), formatSize(free))
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
    fun failure(title: String, detail: String?): String =
        listOf(title, detail?.takeIf { it.isNotBlank() }).filterNotNull().joinToString(". ")
    fun studioBlocked(names: List<String>): String = when (names.size) {
        0 -> S.s_chua_ghep_voi_may_tinh_nao_97f851e1
        1 -> listenOnly(names[0])
        2 -> S.s_may_tinh_0_va_1_deu_chi_cho_nghe_tren_tung_54032487(names[0], names[1])
        else -> S.s_cac_may_tinh_da_ghep_deu_chi_cho_nghe_tren_7b97a8d5
    }
    const val OFFLINE = S.s_chua_ket_noi_duoc_may_dang_tat_hoac_khac_w_1aa869f3

    /** Trang tải ABook cho máy tính (web: DESKTOP_RELEASES của android/DevicesScreen.tsx) - "Tải ABook Windows" mở nó, "Chép địa chỉ" chép nó. */
    const val DESKTOP_RELEASES = "https://github.com/ntanhpro1221/ABook/releases"

    /** Tên công tắc chia sẻ trên máy tính (web: SYNC_SWITCH_LABEL của shared/syncSwitch.ts) - lời "Cách lấy mã" gọi đúng tên ấy. */
    const val SYNC_SWITCH_LABEL = S.s_ket_noi_wi_fi_7680d1aa

    /** "Cách lấy mã": mã 6 số lấy ở đâu trên máy tính (cùng câu với PairPanel của web). */
    val PAIR_CODE_HELP = S.s_trong_cai_dat_thiet_bi_cua_may_tinh_bat_0_af63d4c8(SYNC_SWITCH_LABEL)

    /** "Nghe khi ra ngoài": máy đã ghép không trả lời vì khác mạng - app không cần gì riêng, mạng riêng ảo cho máy tính một địa chỉ tới được (web DevicesScreen). */
    const val AWAY_HELP = S.s_cho_hai_may_vao_cung_mot_mang_rieng_ao_tai_0e231104

    /** Cùng chữ với shared/connectionRoute.ts: nói đường nối thành công, không lộ địa chỉ. */
    fun route(address: String?): String {
        if (address.isNullOrEmpty()) return S.s_chua_ket_noi_f3743a06
        if (address == "bluetooth" || address.lowercase().startsWith("bt:")) return S.s_dang_noi_qua_bluetooth_fb6ba9e5
        val host = if (address.startsWith("[")) address.substring(1, address.indexOf(']').let { if (it < 0) address.length else it }) else address.substringBefore(':')
        val parts = host.split('.').map { it.toIntOrNull() }
        if (parts.size == 4 && parts.all { it != null && it in 0..255 }) {
            val a = parts[0]!!
            val b = parts[1]!!
            if (a == 100 && b in 64..127) return S.s_dang_noi_qua_tailscale_7de36f5d
            if (a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168)) return S.s_dang_noi_qua_wi_fi_nha_ebf18485
        }
        return S.s_dang_noi_qua_mang_807811f3
    }

    /** Dòng mốc thời gian của máy nghe thư viện này: lần cuối thấy nó. */
    fun seen(lastSeen: Double, nowMs: Long = System.currentTimeMillis()): String =
        Fmt.whenText(lastSeen, nowMs).let { if (it.isEmpty()) S.s_chua_thay_46bcd090 else S.s_thay_0_4319765d(it) }

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
                S.s_va_0_da_tai_ve_dien_thoai_nay_se_bi_xoa_0a9ac335(if (unsent.cacheBytes < 1024L * 1024) S.s_duoi_1_mb_b59395ae else formatSize(unsent.cacheBytes))
            } else ""
            lines += S.s_0_cuon_cua_1_se_roi_thu_vien_2_da517a50(unsent.cacheBooks, device, downloaded)
            if (unsent.places > 0) lines += S.s_cho_nghe_cua_0_cuon_van_giu_ghep_lai_dung_9f62342f(unsent.places, device)
        }
        var send: String? = null
        if (edited) {
            val names = unsent.books.take(3).map { "“${it.title}”" }
            val rest = unsent.books.size - names.size
            lines += S.s_0_cuon_co_1_thay_doi_chua_gui_ve_2_se_mat_74fdd211(unsent.books.size, unsent.changes, device, names.joinToString(", "), if (rest > 0) S.s_va_0_cuon_khac_718f50c0(rest) else "")
            if (!unsent.sendable) {
                lines += S.s_0_khong_nhan_phan_sua_nhung_thay_doi_nay_c_c8a49e9f(device)
            } else if (reachable) {
                send = S.s_gui_truoc_roi_bo_ghep_99e6d1f1
            } else {
                send = S.s_thu_gui_truoc_roi_bo_ghep_f12544da
                lines += S.s_0_dang_tat_hay_khac_mang_luc_nay_nen_chua_ebd45cfe(device)
            }
        }
        return ForgetCopy(S.s_bo_ghep_0_e98b86ca(device), lines, send, if (edited) S.s_van_bo_ghep_bo_thay_doi_64cb2e74 else S.s_bo_ghep_64f921f9, edited)
    }

    /** Lời khi máy tính chỉ cho điện thoại nghe (không mở được Studio) - nói trước khi bấm. */
    fun listenOnly(name: String): String =
        S.s_may_tinh_0_chi_cho_nghe_tren_may_tinh_ay_b_ab856008(name)
}

/** Máy tính mở được Studio từ điện thoại (`Devices.studioComputers`). */
@Immutable
data class StudioComputer(val key: String, val name: String, val listenOnly: Boolean)
