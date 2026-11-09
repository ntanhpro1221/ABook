package vn.abook.player.ui.screens

import vn.abook.player.S

import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

@Composable
fun StudioScreen(
    modifier: Modifier = Modifier,
    companion: CompanionRepo? = null,
    devices: DevicesState? = null,
    askNotifications: (() -> Unit) -> Unit = { it() },
    openNotificationSettings: () -> Unit = {},
    connect: () -> Unit = {},
    sheets: SheetHost? = null,
) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val scope = rememberCoroutineScope()
    var problem by remember { mutableStateOf("") }
    val pair = devices?.pair?.collectAsState()?.value
    LaunchedEffect(devices) { devices?.loadStudio() }
    val scroll = rememberScrollState()
    Column(modifier.fillMaxSize().fadeEdges(scroll, startInset = top).verticalScroll(scroll).padding(top = top, start = Dim.margin, end = Dim.margin).testTag("studio_screen")) {
        ScreenHeader(S.s_studio_0aa91af2)
        Reveal(pair?.studio?.isNotEmpty() == true) {
            Column {
                Caption(S.s_tao_sach_noi_tu_xa_def2fcf7)
                val computers = pair?.studio?.values.orEmpty().toList()
                val openable = computers.filterNot { it.listenOnly }
                if (openable.isEmpty()) {
                    // Đoạn giải thích (có thể nhiều dòng): chữ 16 mực phụ cách nhau 8, như trang xác nhận - không xếp Caption chồng nhau.
                    val line = Abook.type.body.copy(color = Abook.colors.text2)
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(DeviceText.studioBlocked(computers.map { it.name }), style = line)
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(S.s_bat_dieu_khien_tu_xa_tren_may_tinh_4263d8db, style = line)
                } else {
                    TextAction(S.s_mo_studio_84ec0a81, {
                        fun open(computer: StudioComputer) { scope.launch { problem = devices?.openStudio(computer.key).orEmpty() } }
                        if (openable.size == 1) open(openable[0])
                        else sheets?.show { dismiss ->
                            Column(Modifier.fillMaxWidth()) {
                                BasicText(S.s_mo_studio_cua_may_nao_1e9d7740, style = Abook.type.sectionTitle)
                                for (computer in openable) DisclosureRow(computer.name, { dismiss(); open(computer) }, "studio_${computer.key}")
                            }
                        }
                    }, "studio_open")
                }
            }
        }
        Reveal(pair?.studio.isNullOrEmpty()) {
            Column {
                BasicText(S.s_studio_tren_may_tinh_6c00d830, style = Abook.type.sectionTitle)
                RowHint(S.s_noi_may_tinh_de_lam_sach_noi_va_xem_tien_d_4b697ccc)
                Caption(S.s_chua_ghep_voi_may_tinh_nao_97f851e1)
                TextAction(S.s_noi_may_tinh_2950692d, connect, "studio_connect")
            }
        }
        if (companion != null) {
            Spacer(Modifier.height(Dim.s24))
            StudioNotices(companion, askNotifications, openNotificationSettings)
        }
        Reveal(problem.isNotEmpty()) { Caption(problem) }
    }
}
