package vn.abook.player.ui.screens

import vn.abook.player.S
import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** The Studio tab owns its project list; only notification links use Destination.Studio. */
@Composable
fun StudioScreen(
    modifier: Modifier = Modifier,
    companion: CompanionRepo? = null,
    devices: DevicesState? = null,
    askNotifications: (() -> Unit) -> Unit = { it() },
    openNotificationSettings: () -> Unit = {},
    connect: () -> Unit = {},
    hub: StudioHub? = null,
    active: Boolean = true,
    computerKey: String? = null,
    pickComputer: ((String) -> Unit)? = null,
    onOpen: (String, String) -> Unit = { _, _ -> },
    onNew: (String) -> Unit = {},
) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val pair = devices?.pair?.collectAsState()?.value
    LaunchedEffect(devices, active) { if (active) devices?.loadStudio() }
    val computers = pair?.studio?.values.orEmpty().toList()
    var selected by rememberSaveable { mutableStateOf<String?>(null) }
    val computer = computers.firstOrNull { it.key == (computerKey ?: selected) }
        ?: computers.firstOrNull { !it.listenOnly } ?: computers.firstOrNull()
    val header: @Composable () -> Unit = {
        ScreenHeader(S.s_studio_0aa91af2)
        Reveal(computers.size >= 2) {
            val choices = computers.map { Option(it.key, it.name) }
            if (choices.isNotEmpty()) ChoiceRow(choices, choices.firstOrNull { it.value == computer?.key } ?: choices.first(),
                { choice, _ -> if (pickComputer != null) pickComputer(choice.value) else selected = choice.value }, tag = "studio_computer")
        }
        if (computer != null && companion != null) StudioNotices(companion, askNotifications, openNotificationSettings)
    }
    Column(modifier.fillMaxSize().padding(top = top, start = Dim.margin, end = Dim.margin).testTag("studio_screen")) {
        if (computer != null && hub != null && !computer.listenOnly) {
            key(computer.key) {
                val state = remember(hub, computer.key) { StudioHomeState(hub.session(computer.key)) }
                StudioHomeScreen(state, {}, { onOpen(computer.key, it.id) }, active, embeddedHeader = header, onNew = { onNew(computer.key) })
            }
        } else {
            val scroll = rememberScrollState()
            Column(Modifier.fillMaxSize().fadeEdges(scroll, startInset = 0.dp).verticalScroll(scroll).padding(bottom = Dim.s24)) {
                header()
                if (computer == null) {
                    RowHint(S.s_noi_may_tinh_de_lam_sach_noi_va_xem_tien_d_4b697ccc)
                    TextAction(S.s_noi_may_tinh_2950692d, connect, "studio_connect")
                } else {
                    BasicText(DeviceText.studioBlocked(listOf(computer.name)), style = Abook.type.body.copy(color = Abook.colors.text2))
                    TextAction(StudioText.RETRY, { devices?.loadStudio() }, "studio_retry")
                }
            }
        }
    }
}
