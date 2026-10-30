package vn.abook.player.ui.devices

import vn.abook.player.ui.studio.StudioRoute
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.Stable
import kotlinx.coroutines.flow.Flow

/** Lỗi đã dịch cho người nghe: câu nói được, chữ gốc cho phần chi tiết, và hai loại cần xử lý riêng (máy kia đã bỏ ghép / chứng chỉ đã đổi). */
class DeviceFailure(message: String, val technical: String? = null, val unpaired: Boolean = false, val changed: Boolean = false) : Exception(message)

/** Thư viện của máy tính chính: tên máy và các cuốn. */
@Immutable
data class RemoteLibrary(val name: String, val books: List<RemoteBook>)

/** Một thiết bị ghép thêm cùng thư viện của nó (rỗng khi nó không trả lời). */
@Immutable
data class PeerLibrary(val device: Paired, val books: List<RemoteBook>)

/** Tin của việc tải nền: tiến độ 0..1, hay xong / huỷ / lỗi. */
@Immutable
data class DownloadEvent(
    val id: String,
    val fraction: Float = 0f,
    val finished: Boolean = false,
    val cancelled: Boolean = false,
    val error: String? = null,
    val technical: String? = null,
) {
    val running: Boolean get() = !finished && !cancelled && error == null
}

/**
 * Việc của ba màn Thiết bị với các lõi (Devices, RemoteBooks, Peers, BookDownloads, ShareService, Store) - tách khỏi màn để thử bằng nguồn giả. Nguồn thật:
 * [DevicesRepo]. Hàm suspend tự chạy ở luồng nền; lỗi ném [DeviceFailure] (hay [IllegalStateException] với câu đã sẵn cho người nghe).
 */
interface DevicesSource {
    suspend fun link(): Link

    /** Máy đang bật đồng bộ trong cùng Wi-Fi (UDP broadcast, vài giây). */
    suspend fun discover(): List<Found>

    /** Đã có quyền "Thiết bị ở gần" (Android 12+) chưa. */
    suspend fun nearbyAllowed(): Boolean
    suspend fun bluetoothDevices(): List<Found>

    /** Ghép: `address` = host:cổng hay bt:địa chỉ; `extra` = ghép thêm một thiết bị (máy tính chính đã có). Trả tên máy kia. */
    suspend fun pair(address: String, code: String, extra: Boolean): String

    /** Bỏ ghép máy tính chính. */
    suspend fun unpair()
    suspend fun remote(): RemoteLibrary
    suspend fun peers(): List<PeerLibrary>

    /** Địa chỉ host:cổng đã ghép của thiết bị `key` (để ghép lại), null khi không có hay đi qua Bluetooth. */
    suspend fun peerAddress(key: String): String?
    suspend fun unsent(key: String): Unsent
    suspend fun forget(key: String, choice: ForgetChoice)

    /** Gom sách nghe thẳng của các máy đã ghép vào Thư viện (gói sách, bìa). */
    suspend fun streamable()
    suspend fun download(book: RemoteBook)
    suspend fun cancelDownload(id: String)
    fun downloadEvents(): Flow<DownloadEvent>
    suspend fun studio(): List<StudioComputer>

    /** Máy và màn native để mở Studio của máy tính `key`. */
    suspend fun studioTarget(key: String): Pair<String, StudioRoute>
    suspend fun share(): Share
    suspend fun setShare(on: Boolean): Share
    suspend fun startCode(): Share
    suspend fun cancelCode(): Share
    suspend fun revoke(id: String): Share

    /** Công tắc chia sẻ đổi từ ngoài màn (nút "Tắt chia sẻ" trên thông báo). */
    fun shareChanges(): Flow<Unit>
    suspend fun setDeviceName(name: String): String
    suspend fun storage(): Storage

    /** Xoá khỏi máy, cùng lõi và cùng lời xác nhận với menu "Xoá khỏi máy" của trang sách: null = đã nhận (nằm chờ Hoàn tác), khác null = câu lỗi. `title` / `partial` cho dòng "Đã xoá…" của thanh Hoàn tác. */
    suspend fun delete(id: String, title: String = "", partial: Boolean = false): String?

    /** Lúc mở app: lượt tải còn giữ từ lần trước tính là đang tải; đã bật chia sẻ từ lần trước thì mở lại. */
    suspend fun restore()
}

/** Việc cần hệ điều hành: Activity cung cấp, test đưa bản giả. */
@Stable
class DeviceLinks(
    /** Mở Studio của máy tính `computer` ở màn `route`. */
    val openStudio: (computer: String, route: StudioRoute) -> Unit = { _, _ -> },
    val openAppSettings: () -> Unit = {},
    /** Xin quyền "Thiết bị ở gần": hộp của Android hiện ra, `result(true)` khi được cho. */
    val askNearby: (result: (Boolean) -> Unit) -> Unit = { it(true) },
    /** Xin quyền thông báo trước khi bật chia sẻ (Android 13+); từ chối thì vẫn chạy tiếp. */
    val askNotifications: (then: () -> Unit) -> Unit = { it() },
    /** Chép chữ vào bộ nhớ tạm của máy; false khi máy không chép được. */
    val copyText: (text: String) -> Boolean = { false },
    /** Mở một trang của ABook trên GitHub bằng trình duyệt của máy (chỉ đường của ABook). */
    val openRelease: (url: String) -> Unit = {},
)
