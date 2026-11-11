package vn.abook.player.ui.devices

import vn.abook.player.S

import vn.abook.player.formatSize

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.flow.StateFlow
import vn.abook.player.ui.components.BluetoothIcon
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.DevicesIcon
import vn.abook.player.ui.components.LaptopIcon
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PhoneIcon
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Các loại hàng của ba màn Thiết bị. Mọi hàng là một [ListItem]: biểu tượng đầu hàng và phần cuối hàng cùng thẳng dòng đầu của tên (luật của cả danh sách).
 */

@Composable
fun DeviceIcon(kind: DeviceKind, color: Color) = when (kind) {
    DeviceKind.Computer -> LaptopIcon(color)
    DeviceKind.Phone -> PhoneIcon(color)
}

/** Một máy tìm thấy để ghép: chạm để chọn (dấu tích cuối hàng + chữ hổ phách), chạm lần nữa để bỏ chọn. */
@Composable
fun FoundRow(found: Found, selected: Boolean, onPick: () -> Unit) {
    val colors = Abook.colors
    val ink = if (selected) colors.accentText else colors.text2
    ListItem(
        found.shown, Modifier.semantics { this.selected = selected }, onPick, "found_${found.address}", hint = found.detail,
        titleColor = if (selected) colors.accentText else colors.text,
        leading = { if (found.bluetooth) BluetoothIcon(ink) else DeviceIcon(found.kind, ink) },
        trailing = if (selected) ({ CheckIcon(colors.accentText) }) else null,
    )
}

/** Một thiết bị đã ghép: tên, dòng trạng thái (lỗi màu nguy hiểm kèm "Thử lại" ở dòng đầu), chạm mở bảng việc của nó. */
@Composable
fun DeviceRow(device: Paired, onOpen: () -> Unit, onRetry: () -> Unit) {
    val colors = Abook.colors
    val failed = device.failed
    ListItem(
        device.name, Modifier, onOpen, "device_${device.key.ifEmpty { "main" }}", hint = device.state,
        tickingHint = true,
        hintColor = if (failed) colors.danger else colors.text2,
        leading = { DeviceIcon(device.kind, colors.text2) },
        trailing = if (failed && device.reach !is Reach.Unpaired) ({ TextAction(S.s_thu_lai_c58d068c, onRetry, "retry_${device.key.ifEmpty { "main" }}") }) else null,
        chevron = !failed || device.reach is Reach.Unpaired,
    )
}

/** Một cuốn trên máy kia: nút ở cuối hàng (Tải / cập nhật / Huỷ / Thử lại), tiến độ ngay dưới tên khi đang tải. */
@Composable
fun RemoteBookRow(
    book: RemoteBook, downloading: Boolean, failure: String?, progress: () -> StateFlow<Float>,
    onDownload: () -> Unit, onCancel: () -> Unit,
) {
    val colors = Abook.colors
    val tag = "book_${book.id}"
    ListItem(
        book.title, Modifier, null, tag,
        tickingHint = true,
        hint = when {
            failure != null -> failure
            downloading -> S.s_dang_tai_465b1987
            else -> book.detail
        },
        hintColor = if (failure != null) colors.danger else colors.text2,
        trailing = {
            when {
                downloading -> TextAction(S.s_huy_tai_1a9ff73d, onCancel, "cancel_${book.id}")
                failure != null -> TextAction(S.s_thu_lai_c58d068c, onDownload, "download_${book.id}")
                book.upToDate -> BasicText(S.s_da_tai_ve_may_a3ac321b, style = Abook.type.caption.copy(color = colors.success))
                else -> TextAction(book.action, onDownload, "download_${book.id}")
            }
        },
        below = if (downloading) ({ DownloadBar(progress()) }) else null,
    )
}

/** Thanh tiến độ tải: giá trị chỉ đọc trong pha vẽ, nên mỗi nhịp tải không dựng lại hàng. */
@Composable
fun DownloadBar(flow: StateFlow<Float>) {
    val value = flow.collectAsState()
    StageProgress { value.value }
}

/** Một thiết bị đang nghe thư viện này: lần cuối thấy nó; chạm mở bảng bỏ ghép. */
@Composable
fun SharerRow(sharer: Sharer, onOpen: () -> Unit) {
    val colors = Abook.colors
    ListItem(
        sharer.name, Modifier, onOpen, "sharer_${sharer.id}", hint = DeviceText.seen(sharer.lastSeen), tickingHint = true,
        leading = { DevicesIcon(colors.text2) }, chevron = true,
    )
}

/** Mã ghép đang hiện cho máy kia nhập: lời dặn, mã lớn, hạn dùng, "Huỷ mã" ở cuối dòng mã. */
@Composable
fun CodeRow(code: Code, onCancel: () -> Unit) {
    Column {
        Caption(S.s_nhap_ma_nay_tren_may_kia_113245f6, Modifier.padding(top = Dim.s8))
        ListItem(
            code.digits.chunked(3).joinToString(" "), Modifier, null, "share_code",
            hint = S.s_dung_duoc_den_0_90292ae2(DeviceText.clock(code.expiresAt)),
            titleStyle = Abook.type.sectionTitle.copy(lineHeight = 24.sp, letterSpacing = 2.sp),
            trailing = { TextAction(S.s_huy_ma_1b0a6559, onCancel, "share_cancel_code") },
        )
    }
}

/** Một thứ đang chiếm chỗ: cỡ ở cuối dòng đầu; chạm cả hàng mở bảng có "Xoá khỏi máy" (có bước xác nhận). Đang tải thì không xoá được. */
@Composable
fun StoredRow(item: Stored, busy: Boolean, onDelete: () -> Unit) {
    val colors = Abook.colors
    ListItem(
        item.title, Modifier, if (busy) null else onDelete, "stored_${item.id}",
        hint = when {
            busy -> S.s_dang_tai_465b1987
            item.partial -> S.s_phan_da_tai_chua_thanh_sach_992f1af6
            else -> null
        },
        trailing = { BasicText(formatSize(item.bytes), style = Abook.type.bodySmall.copy(color = colors.text2)) },
    )
}
