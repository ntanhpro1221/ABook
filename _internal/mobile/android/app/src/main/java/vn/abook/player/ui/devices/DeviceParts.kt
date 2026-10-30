package vn.abook.player.ui.devices

import vn.abook.player.formatSize

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
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
import vn.abook.player.ui.motion.Motion
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
        trailing = if (failed && device.reach !is Reach.Unpaired) ({ TextAction("Thử lại", onRetry, "retry_${device.key.ifEmpty { "main" }}") }) else null,
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
            downloading -> "Đang tải"
            else -> book.detail
        },
        hintColor = if (failure != null) colors.danger else colors.text2,
        trailing = {
            when {
                downloading -> TextAction("Huỷ tải", onCancel, "cancel_${book.id}")
                failure != null -> TextAction("Thử lại", onDownload, "download_${book.id}")
                book.upToDate -> BasicText("Đã tải về máy", style = Abook.type.caption.copy(color = colors.success))
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

/** Thanh "đang làm" khi chưa biết còn bao lâu (đang ghép, đang tìm): chạy chậm dần tới gần hết rồi dừng, không lặp vô hạn. */
@Composable
fun CreepProgress() {
    val creep = remember { Animatable(0.06f) }
    LaunchedEffect(Unit) { creep.animateTo(0.92f, tween(12_000, easing = Motion.Decelerate)) }
    StageProgress { creep.value }
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
        Caption("Nhập mã này trên máy kia", Modifier.padding(top = Dim.s8))
        ListItem(
            code.digits.chunked(3).joinToString(" "), Modifier, null, "share_code",
            hint = "Dùng được đến ${DeviceText.clock(code.expiresAt)}",
            titleStyle = Abook.type.sectionTitle.copy(lineHeight = 24.sp, letterSpacing = 2.sp),
            trailing = { TextAction("Huỷ mã", onCancel, "share_cancel_code") },
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
            busy -> "Đang tải"
            item.partial -> "Phần đã tải, chưa thành sách"
            else -> null
        },
        trailing = { BasicText(formatSize(item.bytes), style = Abook.type.bodySmall.copy(color = colors.text2)) },
    )
}
