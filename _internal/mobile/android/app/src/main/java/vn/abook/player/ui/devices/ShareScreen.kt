package vn.abook.player.ui.devices

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Chia sẻ thư viện. Công tắc bật / tắt; khi bật: địa chỉ để gõ vào máy kia, mã ghép 6 số (hay "Tạo mã ghép"), Bluetooth nếu có tin, rồi danh sách máy đã ghép
 * để nghe thư viện này - chạm một máy để bỏ ghép. Mã hiện giờ hết hạn (không đếm từng giây): màn không dựng lại mỗi nhịp đồng hồ.
 */

@Composable
fun ShareScreen(devices: DevicesState, sheets: SheetHost, onBack: () -> Unit) {
    val ui by devices.share.collectAsState()
    LaunchedEffect(devices) { devices.openShare() }
    // Quay lại từ Cài đặt Android (quyền "Thiết bị ở gần", chạy nền): đọc lại trạng thái.
    LifecycleResumeEffect(devices) {
        devices.openShare()
        onPauseOrDispose { }
    }
    val share = ui.share
    // Mã vừa huỷ vẫn vẽ trong lúc khối khép lại (không trống trơn giữa chừng).
    val lastCode = remember { arrayOf<Code?>(null) }
    share.code?.let { lastCode[0] = it }
    val problem = ui.problem.ifEmpty { share.error }.ifEmpty { if (share.blocked && share.code == null) "Mã đã huỷ vì nhập sai nhiều lần." else "" }
    BookForm("Chia sẻ thư viện", onBack, "share_screen") {
        if (ui.loaded) LazyColumn(Modifier.fillMaxSize().testTag("share_list"), contentPadding = PaddingValues(bottom = Dim.s16)) {
            item("switch", "switch") {
                Column(Modifier.padding(top = Dim.s8)) {
                    SwitchRow("Cho máy khác nghe", share.running, devices::setSharing, "share_switch")
                    Reveal(share.running) {
                        Column(Modifier.fillMaxWidth()) {
                            RowLine()
                            ListItem("Địa chỉ", Modifier.testTag("share_address"), hint = share.addressLine)
                            RowLine()
                            Reveal(share.code != null) {
                                lastCode[0]?.let { code -> CodeRow(code, devices::cancelCode) }
                            }
                            Reveal(share.code == null) {
                                TextAction("Ghép máy mới", devices::newCode, "share_new_code", Modifier.fillMaxWidth(), align = Alignment.CenterStart)
                            }
                        }
                    }
                    InlineProblem(problem, if (!share.running && problem.isNotEmpty() && ui.problem.isEmpty()) ({ devices.setSharing(true) }) else null, "share_problem")
                }
            }
            if (share.running) {
                share.bluetoothLine?.takeIf { !share.needsNearby }?.let { line -> item("bluetooth", "note") { Caption(line, Modifier.padding(top = Dim.s8).testTag("share_bluetooth")) } }
                if (share.needsNearby) item("nearby", "status") {
                    ListItem(
                        "Cần quyền Thiết bị ở gần", Modifier.testTag("share_nearby"), titleColor = Abook.colors.danger,
                        trailing = { TextAction("Mở cài đặt", devices::openAppSettings, "share_open_settings") },
                    )
                }
                if (!share.backgroundAllowed) item("background", "background") {
                    DisclosureRow(
                        "Cho ABook chạy nền", devices::openAppSettings, "share_background",
                        summary = "Khi tắt màn hình, máy có thể tạm dừng chia sẻ - máy tính sẽ phải chờ lâu hơn.",
                    )
                }
            }
            if (share.devices.isNotEmpty()) {
                item("devices_title", "title") { SectionTitle("Máy đã ghép") }
                items(share.devices, key = { "sharer_${it.id}" }, contentType = { "sharer" }) { sharer ->
                    Column(Modifier.fillMaxWidth()) {
                        SharerRow(sharer, onOpen = { sheets.show { dismiss -> RevokeSheet(sharer, devices, dismiss) } })
                        RowLine(start = 36.dp)
                    }
                }
            }
        }
    }
}
