package vn.abook.player.ui.devices

import vn.abook.player.S

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
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
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/*
 * Chia sẻ thư viện. Công tắc bật / tắt; khi bật: địa chỉ để gõ vào máy kia, mã ghép 6 số (hay "Tạo mã ghép"), Bluetooth nếu có tin, rồi danh sách máy đã ghép
 * để nghe thư viện này - chạm một máy để bỏ ghép. Mã hiện giờ hết hạn (không đếm từng giây): màn không dựng lại mỗi nhịp đồng hồ.
 */

@Composable
fun ShareScreen(devices: DevicesState, sheets: SheetHost, embedded: Boolean = false, onBack: () -> Unit) {
    val ui by devices.share.collectAsState()
    LaunchedEffect(devices) { devices.openShare() }
    // Quay lại từ Cài đặt Android (quyền "Thiết bị ở gần", chạy nền): đọc lại trạng thái.
    LifecycleResumeEffect(devices) {
        devices.openShare()
        onPauseOrDispose { devices.closeShare() }
    }
    val share = ui.share
    // Mã vừa huỷ vẫn vẽ trong lúc khối khép lại (không trống trơn giữa chừng).
    val lastCode = remember { arrayOf<Code?>(null) }
    share.code?.let { lastCode[0] = it }
    val problem = ui.problem.ifEmpty { share.error }.ifEmpty { if (share.blocked && share.code == null) S.s_sai_5_lan_chi_tao_ma_moi_khi_ban_dang_ghep_6f3c0e90 else "" }
    DeviceSettingsContent(S.s_chia_se_thu_vien_940de671, onBack, "share_screen", embedded) {
        if (ui.loaded) Column(Modifier.fillMaxWidth().testTag("share_list").padding(bottom = Dim.s16)) {
            key("switch", "switch") {
                Column(Modifier.padding(top = Dim.s8)) {
                    SwitchRow(S.s_ket_noi_wi_fi_7680d1aa, share.running, { on ->
                        if (!on) devices.setSharing(false) else sheets.show { dismiss ->
                            Column(Modifier.fillMaxWidth()) {
                                Caption(S.s_khi_chia_se_abook_giu_mot_thong_bao_nho_de_31e37d13)
                                PrimaryButton(S.s_tiep_tuc_87a7ae88, { devices.setSharing(true); dismiss() }, Modifier.fillMaxWidth().testTag("share_continue"))
                                QuietButton(S.s_de_sau_9be0a7ab, dismiss, "share_later")
                            }
                        }
                    }, "share_switch", hint = S.s_may_da_ghep_nghe_duoc_sach_ban_them_tu_fil_42f7a70f)
                    Reveal(share.running) {
                        Column(Modifier.fillMaxWidth()) {
                            RowLine()
                            ListItem(S.s_ten_c8b17259, hint = share.name)
                            Fold(S.s_chi_tiet_e762d926, "share_details") {
                                ListItem(S.s_dia_chi_249de6f5, Modifier.testTag("share_address"), hint = share.addressLine)
                                if (share.fingerprint.isNotBlank()) ListItem(S.s_van_tay_74d5ff65, hint = share.fingerprint.uppercase().replace(Regex("(.{4})(?=.)"), "$1 "))
                            }
                            Caption(S.s_may_kia_chua_tu_thay_dien_thoai_dia_chi_na_34b7f3e8, Modifier.padding(top = Dim.s4, bottom = Dim.s12))
                            RowLine()
                            Reveal(share.code != null) {
                                lastCode[0]?.let { code -> CodeRow(code, devices::cancelCode) }
                            }
                            Reveal(share.code == null) {
                                TextAction(S.s_ghep_thiet_bi_moi_e22fb590, devices::newCode, "share_new_code", Modifier.fillMaxWidth(), align = Alignment.CenterStart)
                            }
                        }
                    }
                    InlineProblem(problem, if (!share.running && problem.isNotEmpty() && ui.problem.isEmpty()) ({ devices.setSharing(true) }) else null, "share_problem")
                }
            }
            if (share.running) {
                share.bluetoothLine?.takeIf { !share.needsNearby }?.let { line -> key("bluetooth", "note") { Caption(line, Modifier.padding(top = Dim.s8).testTag("share_bluetooth")) } }
                if (share.needsNearby) key("nearby", "status") {
                    ListItem(
                        S.s_can_quyen_thiet_bi_o_gan_ea24d4e0, Modifier.testTag("share_nearby"), titleColor = Abook.colors.danger,
                        trailing = { TextAction(S.s_mo_cai_dat_60ab929f, devices::openAppSettings, "share_open_settings") },
                    )
                }
                if (!share.backgroundAllowed) key("background", "background") {
                    DisclosureRow(
                        S.s_cho_abook_chay_nen_a56d0e4e, devices::openAppSettings, "share_background",
                        summary = S.s_khi_tat_man_hinh_may_co_the_tam_dung_chia_9a8ee70e,
                    )
                }
            }
            if (share.devices.isNotEmpty()) {
                key("devices_title", "title") { SectionTitle(S.s_may_da_ghep_c2103758) }
                for (sharer in share.devices) key("sharer_${sharer.id}") {
                    Column(Modifier.fillMaxWidth()) {
                        SharerRow(sharer, onOpen = { sheets.show { dismiss -> RevokeSheet(sharer, devices, dismiss) } })
                        RowLine(start = 36.dp)
                    }
                }
            }
        }
    }
}
