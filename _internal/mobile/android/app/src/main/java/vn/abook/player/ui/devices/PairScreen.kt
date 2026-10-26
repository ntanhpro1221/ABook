package vn.abook.player.ui.devices

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.RefreshIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Nối máy tính. Đã nối: danh sách thiết bị (mỗi hàng một dòng trạng thái, chạm mở bảng việc), rồi sách của từng máy với nút Tải / cập nhật / Huỷ ngay hàng.
 * Chưa nối (hay đang thêm): chọn cách nối (Wi-Fi tự tìm / Bluetooth / gõ địa chỉ), máy tìm thấy, mã 6 số, "Kết nối" ở đáy. Việc dài hiện tiến độ ngay hàng của nó.
 */

@Composable
fun PairScreen(devices: DevicesState, sheets: SheetHost, onBack: () -> Unit) {
    val ui by devices.pair.collectAsState()
    LaunchedEffect(devices) { devices.openPair() }
    LaunchedEffect(ui.paired) { if (ui.paired) devices.loadStudio() }
    // Quay lại từ Cài đặt Android mà đã cho quyền "Thiết bị ở gần": tìm máy Bluetooth luôn.
    LifecycleResumeEffect(devices) {
        devices.recheckBluetooth()
        onPauseOrDispose { }
    }
    val form = ui.form
    BookForm(
        "Nối máy tính", onBack, "pair_screen",
        footer = if (ui.showForm) ({
            PrimaryButton(
                "Kết nối", devices::connect,
                Modifier.fillMaxWidth().testTag("pair_connect"), enabled = form.ready && ui.attempt !is Attempt.Working,
            )
        }) else null,
        trailing = if (ui.paired) ({ RefreshButton(ui.refreshing, devices::refresh) }) else null,
    ) {
        if (ui.loaded) LazyColumn(Modifier.fillMaxSize().testTag("pair_list"), contentPadding = PaddingValues(bottom = Dim.s16)) {
            devicesList(ui, devices, sheets)
            booksLists(ui, devices)
            if (ui.showForm) pairForm(ui, devices) else item("add_device", "action") {
                TextAction("Thêm thiết bị", { devices.setAdding(true) }, "pair_add", Modifier.padding(top = Dim.s8).fillMaxWidth(), align = Alignment.CenterStart)
            }
        }
    }
}

/** Làm mới ở đầu màn: biểu tượng trong ô chạm 48; đang hỏi máy thì nhạt đi. */
@Composable
private fun RefreshButton(refreshing: Boolean, onClick: () -> Unit) {
    val colors = Abook.colors
    Box(
        Modifier.size(Dim.s48).pressable(Role.Button, onClick = { if (!refreshing) onClick() }).testTag("pair_refresh"),
        contentAlignment = Alignment.Center,
    ) { RefreshIcon(if (refreshing) colors.text3 else colors.text2) }
}

private fun LazyListScope.devicesList(ui: PairUi, devices: DevicesState, sheets: SheetHost) {
    if (ui.devices.isEmpty()) return
    item("devices_title", "title") { SectionTitle("Máy đã nối", first = true) }
    items(ui.devices, key = { "device_${it.key}" }, contentType = { "device" }) { device ->
        Column(Modifier.fillMaxWidth()) {
            DeviceRow(
                device,
                onOpen = { sheets.show { dismiss -> DeviceSheet(device, devices, dismiss) } },
                onRetry = devices::refresh,
            )
            RowLine(start = 36.dp)
        }
    }
}

private fun LazyListScope.booksLists(ui: PairUi, devices: DevicesState) {
    for (section in ui.sections) {
        val name = section.source ?: "main"
        item("books_$name", "title") { SectionTitle("Sách trên ${section.deviceName}") }
        items(section.books, key = { "book_${it.id}" }, contentType = { "book" }) { book ->
            Column(Modifier.fillMaxWidth()) {
                RemoteBookRow(
                    book, downloading = book.id in ui.downloading, failure = ui.failed[book.id], progress = { devices.progress(book.id) },
                    onDownload = { devices.download(book) }, onCancel = { devices.cancelDownload(book.id) },
                )
                RowLine()
            }
        }
    }
}

private fun LazyListScope.pairForm(ui: PairUi, devices: DevicesState) {
    val form = ui.form
    if (ui.paired) item("form_title", "title") {
        Row(Modifier.fillMaxWidth().padding(top = Dim.sectionGap).heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically) {
            BasicText("Thêm thiết bị", style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
            TextAction("Thôi", { devices.setAdding(false) }, "pair_cancel")
        }
    }
    item("method", "method") {
        ChoiceSetting("Cách nối", PairMethod.entries, ui.method, { method, _ -> devices.setMethod(method) }, "pair_method")
    }
    when (ui.method) {
        PairMethod.Wifi -> wifiRows(ui, devices)
        PairMethod.Bluetooth -> bluetoothRows(ui, devices)
        PairMethod.Address -> item("address", "address") {
            Column(Modifier.padding(top = Dim.s12)) {
                BookField(null, form.address, devices::setAddress, "pair_address", description = "Địa chỉ máy tính", placeholder = "Địa chỉ, ví dụ 192.168.1.20", keyboard = KeyboardType.Uri)
            }
        }
    }
    item("code", "code") {
        Reveal(form.target != null) {
            Column(Modifier.padding(top = Dim.s16)) {
                BookField("Mã ghép", form.code, devices::setCode, "pair_code", description = "Mã ghép", placeholder = "6 số trên máy tính", keyboard = KeyboardType.Number)
            }
        }
    }
    item("attempt", "attempt") {
        // Tên máy giữ lại trong lúc dòng khép (ghép xong hay lỗi).
        val last = remember { arrayOf("") }
        (ui.attempt as? Attempt.Working)?.let { last[0] = it.name }
        Column(Modifier.fillMaxWidth()) {
            Reveal(ui.attempt is Attempt.Working) {
                ListItem("Đang nối ${last[0]}", Modifier.testTag("pair_working"), below = { CreepProgress() })
            }
            InlineProblem((ui.attempt as? Attempt.Failed)?.message.orEmpty(), devices::connect, "pair_problem")
        }
    }
}

private fun LazyListScope.wifiRows(ui: PairUi, devices: DevicesState) {
    val list = ui.wifiChoices
    when {
        list.isNotEmpty() -> foundRows(list, ui, devices)
        ui.scanning -> item("scanning", "status") { ListItem("Đang tìm máy", Modifier.testTag("pair_scanning"), below = { CreepProgress() }) }
        else -> item("none", "status") { NoneRow("Chưa thấy máy nào", devices::scan) }
    }
}

private fun LazyListScope.bluetoothRows(ui: PairUi, devices: DevicesState) {
    when (val bluetooth = ui.bluetooth) {
        Bluetooth.Off, Bluetooth.Listing -> item("scanning", "status") { ListItem("Đang tìm máy", Modifier.testTag("pair_scanning"), below = { CreepProgress() }) }
        Bluetooth.Denied -> item("denied", "status") {
            ListItem(
                "Cần quyền Thiết bị ở gần", Modifier.testTag("pair_denied"), titleColor = Abook.colors.danger,
                trailing = { TextAction("Mở cài đặt", devices::openAppSettings, "pair_open_settings") },
            )
        }
        is Bluetooth.Failed -> item("failed", "status") {
            ListItem(
                bluetooth.message, Modifier.testTag("pair_bluetooth_failed"), titleColor = Abook.colors.danger,
                trailing = { TextAction("Thử lại", devices::findBluetooth, "pair_bluetooth_retry") },
            )
        }
        is Bluetooth.Devices -> {
            val list = ui.bluetoothChoices
            if (list.isNotEmpty()) foundRows(list, ui, devices) else item("none", "status") { NoneRow("Chưa thấy máy nào", devices::findBluetooth) }
        }
    }
}

private fun LazyListScope.foundRows(list: List<Found>, ui: PairUi, devices: DevicesState) {
    items(list, key = { "found_${it.address}" }, contentType = { "found" }) { found ->
        Column(Modifier.fillMaxWidth()) {
            FoundRow(found, selected = ui.form.picked == found.address, onPick = { devices.pick(found) })
            RowLine(start = 36.dp)
        }
    }
}

/** Không thấy máy nào: một dòng nói thẳng và "Tìm lại" ở cuối dòng đầu. */
@Composable
private fun NoneRow(title: String, onRetry: () -> Unit) {
    ListItem(title, Modifier.testTag("pair_none"), trailing = { TextAction("Tìm lại", onRetry, "pair_rescan") })
}
