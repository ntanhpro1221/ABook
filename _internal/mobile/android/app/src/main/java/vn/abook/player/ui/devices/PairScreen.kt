package vn.abook.player.ui.devices

import vn.abook.player.ui.components.WorkingProgress
import vn.abook.player.S

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.components.keepUrlTogether
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.CopyIcon
import vn.abook.player.ui.components.DownloadIcon
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.LaptopIcon
import vn.abook.player.ui.components.MoreInfo
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.RefreshIcon
import vn.abook.player.ui.components.IconAction
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
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
 * Chưa nối: một câu nói mở gì trên máy tính + "Cách lấy mã" gập, và cuối trang phần gập "Cài trên máy tính" (lấy ABook máy tính ở đâu) - như PairPanel /
 * ComputerIntro của web. Máy đã nối không trả lời: một câu "sách đã tải vẫn nghe được" + "Nghe khi ra ngoài" (mạng riêng ảo) gập.
 */

@Composable
fun PairScreen(devices: DevicesState, sheets: SheetHost, embedded: Boolean = false, onBack: () -> Unit) {
    val ui by devices.pair.collectAsState()
    val notice by devices.notice.collectAsState()
    LaunchedEffect(devices) { devices.openPair() }
    LaunchedEffect(ui.paired) { if (ui.paired) devices.loadStudio() }
    // Quay lại từ Cài đặt Android mà đã cho quyền "Thiết bị ở gần": tìm máy Bluetooth luôn.
    LifecycleResumeEffect(devices) {
        devices.recheckBluetooth()
        onPauseOrDispose { }
    }
    val form = ui.form
    DeviceSettingsContent(
        S.s_noi_may_tinh_2950692d, onBack, "pair_screen", embedded,
        footer = if (ui.showForm) ({
            PrimaryButton(
                if (ui.attempt is Attempt.Confirm) S.s_pair_fingerprint_confirm else if (ui.paired) S.s_ghep_thiet_bi_8de1f23c else S.s_ket_noi_02ca3cba,
                { if (ui.attempt is Attempt.Confirm) devices.confirmPair() else devices.connect() },
                Modifier.fillMaxWidth().testTag("pair_connect"), enabled = form.ready && ui.attempt !is Attempt.Working,
            )
        }) else null,
        trailing = if (ui.paired) ({ RefreshButton(ui.refreshing, devices::refresh) }) else null,
    ) {
        Reveal(ui.loaded) { Column(Modifier.fillMaxWidth().testTag("pair_list").padding(bottom = Dim.s16)) {
            key("notice", "notice") { Reveal(notice.isNotBlank()) { RowHint(notice) } }
            devicesList(ui, devices, sheets)
            booksLists(ui, devices)
            if (ui.showForm) pairForm(ui, devices) else key("add_device", "action") {
                TextAction(S.s_them_thiet_bi_15b663e2, { devices.setAdding(true) }, "pair_add", Modifier.padding(top = Dim.s8).fillMaxWidth(), align = Alignment.CenterStart)
            }
            if (!ui.paired) key("install", "install") { InstallFold(devices) }
        } }
    }
}

/** Làm mới ở đầu màn: biểu tượng trong ô chạm 48; đang hỏi máy thì nhạt đi. */
@Composable
private fun RefreshButton(refreshing: Boolean, onClick: () -> Unit) {
    val colors = Abook.colors
    Box(
        Modifier.size(Dim.s48).pressable(Role.Button, onClick = { if (!refreshing) onClick() }).testTag("pair_refresh").semantics { contentDescription = S.s_tim_lai_635fcbe8 },
        contentAlignment = Alignment.Center,
    ) { RefreshIcon(if (refreshing) colors.text3 else colors.text2) }
}

@Composable
private fun devicesList(ui: PairUi, devices: DevicesState, sheets: SheetHost) {
    if (ui.devices.isEmpty()) return
    key("devices_title", "title") { SectionTitle(S.s_may_da_noi_a1b94280, first = true) }
    for (device in ui.devices) key("device_${device.key}") {
        Column(Modifier.fillMaxWidth()) {
            DeviceRow(
                device,
                onOpen = { sheets.show { dismiss -> DeviceSheet(device, devices, dismiss) } },
                onRetry = devices::refresh,
            )
            RowLine(start = 36.dp)
        }
    }
    // Máy đã nối không trả lời (tắt máy hay khác mạng): sách đã tải vẫn nghe được; nghe tiếp sách trên máy kia khi ra ngoài thì cần mạng riêng ảo.
    key("away", "away") {
        Reveal(ui.devices.any { it.reach is Reach.Offline }) {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("pair_away")) {
                RowHint(S.s_sach_da_tai_van_nghe_duoc_khi_ra_ngoai_93db87dd)
                MoreInfo(S.s_nghe_khi_ra_ngoai_b5de4fd3, DeviceText.AWAY_HELP, "pair_away_help")
            }
        }
    }
}

@Composable
private fun booksLists(ui: PairUi, devices: DevicesState) {
    for (section in ui.sections) {
        val name = section.source ?: "main"
        key("books_$name", "title") { SectionTitle(S.s_sach_tren_0_7e7f4260(section.deviceName)) }
        for (book in section.books) key("book_${book.id}") {
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

@Composable
private fun pairForm(ui: PairUi, devices: DevicesState) {
    val form = ui.form
    if (ui.paired) key("form_title", "title") {
        Row(Modifier.fillMaxWidth().padding(top = Dim.sectionGap).heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically) {
            BasicText(S.s_thiet_bi_khac_e027e6f8, style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
            TextAction(S.s_huy_96732485, { devices.setAdding(false) }, "pair_cancel")
        }
    }
    if (!ui.paired) key("intro", "intro") {
        Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("pair_intro")) {
            RowHint(S.s_cung_wi_fi_mo_thiet_bi_tren_may_tinh_49c24644)
            MoreInfo(S.s_cach_lay_ma_12058487, DeviceText.PAIR_CODE_HELP, "pair_code_help")
        }
    }
    key("method", "method") {
        Reveal(ui.paired) {
            RowHint(S.s_sach_may_kia_hien_trong_thu_vien_a323b709)
            TextAction(S.s_ghep_bluetooth_0193ced5, { devices.setMethod(PairMethod.Bluetooth) }, "pair_extra_bluetooth")
        }
        ChoiceSetting(S.s_cach_noi_54df7083, PairMethod.entries, ui.method, { method, _ -> devices.setMethod(method) }, "pair_method")
    }
    when (ui.method) {
        PairMethod.Wifi -> wifiRows(ui, devices)
        PairMethod.Bluetooth -> bluetoothRows(ui, devices)
        PairMethod.Address -> key("address", "address") {
            Column(Modifier.padding(top = Dim.s12)) {
                BookField(null, form.address, devices::setAddress, "pair_address", description = S.s_dia_chi_may_tinh_3717a634, placeholder = S.s_dia_chi_vi_du_192_168_1_20_47630_23c40eb4, keyboard = KeyboardType.Uri)
            }
        }
    }
    key("code", "code") {
        Reveal(form.target != null) {
            Column(Modifier.padding(top = Dim.s16)) {
                BookField(S.s_pair_code_or_string, form.code, devices::setCode, "pair_code", description = S.s_pair_code_or_string, placeholder = "123456", keyboard = KeyboardType.Text)
                (ui.attempt as? Attempt.Confirm)?.let { confirm ->
                    RowHint(S.s_pair_fingerprint_label + vn.abook.player.Pin.short(confirm.fingerprint))
                    RowHint(S.s_pair_fingerprint_help)
                }
            }
        }
    }
    key("attempt", "attempt") {
        // Tên máy giữ lại trong lúc dòng khép (ghép xong hay lỗi).
        val last = remember { arrayOf("") }
        (ui.attempt as? Attempt.Working)?.let { last[0] = it.name }
        Column(Modifier.fillMaxWidth()) {
            Reveal(ui.attempt is Attempt.Working) {
                ListItem(S.s_dang_noi_0_12f5920e(last[0]), Modifier.testTag("pair_working"), below = { WorkingProgress() })
            }
            InlineProblem((ui.attempt as? Attempt.Failed)?.message.orEmpty(), devices::connect, "pair_problem")
        }
    }
}

@Composable
private fun wifiRows(ui: PairUi, devices: DevicesState) {
    val list = ui.wifiChoices
    when {
        list.isNotEmpty() -> { key("wifi_title", "title") { SectionTitle(S.s_may_tinh_tim_thay_fda2636c) }; foundRows(list, ui, devices) }
        ui.scanning -> key("scanning", "status") { ListItem(S.s_dang_tim_thiet_bi_b72cae79, Modifier.testTag("pair_scanning"), below = { WorkingProgress() }) }
        else -> key("none", "status") { NoneRow(S.s_chua_thay_thiet_bi_192c6e9e, devices::scan) }
    }
}

@Composable
private fun bluetoothRows(ui: PairUi, devices: DevicesState) {
    when (val bluetooth = ui.bluetooth) {
        Bluetooth.Off, Bluetooth.Explain -> key("permission", "permission") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s12)) {
                RowHint(S.s_cho_phep_thiet_bi_o_gan_de_tim_may_da_ghep_9a04ce0a)
                MoreInfo(S.s_quyen_bluetooth_b86ed969, S.s_chi_tim_may_da_ghep_bluetooth_de_nhan_sach_29918072, "bluetooth_reason")
                TextAction(S.s_cho_phep_f1a437f5, devices::requestBluetooth, "bluetooth_allow")
                TextAction(S.s_de_sau_9be0a7ab, devices::deferBluetooth, "bluetooth_later")
            }
        }
        Bluetooth.Listing -> key("scanning", "status") { ListItem(S.s_dang_tim_thiet_bi_b72cae79, Modifier.testTag("pair_scanning"), below = { WorkingProgress() }) }
        Bluetooth.Denied -> key("denied", "status") {
            ListItem(
                S.s_can_quyen_thiet_bi_o_gan_ea24d4e0, Modifier.testTag("pair_denied"), titleColor = Abook.colors.danger,
                trailing = { TextAction(S.s_mo_cai_dat_60ab929f, devices::openAppSettings, "pair_open_settings") },
            )
        }
        is Bluetooth.Failed -> key("failed", "status") {
            ListItem(
                bluetooth.message, Modifier.testTag("pair_bluetooth_failed"), titleColor = Abook.colors.danger,
                trailing = { TextAction(S.s_thu_lai_c58d068c, devices::findBluetooth, "pair_bluetooth_retry") },
            )
        }
        is Bluetooth.Devices -> {
            key("bt_title", "title") { SectionTitle(S.s_may_tinh_da_ghep_bluetooth_7f2e5d06) }
            val list = ui.bluetoothChoices
            if (list.isNotEmpty()) foundRows(list, ui, devices) else key("none", "status") {
                NoneRow(S.s_chua_co_may_nao_ghep_bluetooth_ghep_o_cai_01e82050, devices::findBluetooth)
            }
        }
    }
}

@Composable
private fun foundRows(list: List<Found>, ui: PairUi, devices: DevicesState) {
    for (found in list) key("found_${found.address}") {
        Column(Modifier.fillMaxWidth()) {
            FoundRow(found, selected = ui.form.picked == found.address, onPick = { devices.pick(found) })
            RowLine(start = 36.dp)
        }
    }
}

/** Không thấy máy nào: một dòng nói thẳng và "Tìm lại" ở cuối dòng đầu. */
@Composable
private fun NoneRow(title: String, onRetry: () -> Unit) {
    ListItem(title, Modifier.testTag("pair_none"), trailing = { IconAction(S.s_tim_lai_635fcbe8, onRetry, "pair_rescan") { RefreshIcon(Abook.colors.text2) } })
}

/**
 * "Cài trên máy tính" (web: ComputerIntro trong Fold): máy tính thêm được gì, và lấy ABook máy tính ở đâu - chạm "Tải ABook Windows" mở trang tải, nút chép ở cuối
 * hàng chép địa chỉ để mở trên máy tính. Kết quả lần chép là dòng phụ ngay dưới tên (trong dòng chảy, không hộp nổi); chép không được thì dòng ấy là chính địa chỉ.
 */
@Composable
private fun InstallFold(devices: DevicesState) {
    val colors = Abook.colors
    var copied by remember { mutableStateOf<Boolean?>(null) }
    Fold(S.s_cai_tren_may_tinh_3a208e7c, "pair_install", Modifier.padding(top = Dim.s16)) {
        ListItem(
            S.s_studio_may_tinh_1773d208, Modifier, null, "pair_studio_intro", hint = S.s_tao_sach_noi_roi_nghe_o_day_2bf381ff,
            titleStyle = Abook.type.bodyStrong, leading = { LaptopIcon(colors.text2) },
        )
        RowLine(start = 36.dp)
        ListItem(
            S.s_tai_abook_windows_9001b86d, Modifier, devices::openDesktopRelease, "pair_download",
            hint = copied?.let { if (it) S.s_da_chep_dia_chi_956bdd76 else keepUrlTogether(DeviceText.DESKTOP_RELEASES) },
            titleColor = colors.accentText, titleStyle = Abook.type.bodyStrong, leading = { DownloadIcon(colors.text2) },
            trailing = { IconAction(S.s_chep_dia_chi_06306764, { copied = devices.copyDesktopRelease() }, "pair_copy_release") { CopyIcon(colors.text2) } },
        )
    }
}
