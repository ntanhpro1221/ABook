package vn.abook.player.ui.screens

import androidx.compose.ui.Modifier
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.text.BasicText
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
) {
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val scope = rememberCoroutineScope()
    var problem by remember { mutableStateOf("") }
    val pair = devices?.pair?.collectAsState()?.value
    LaunchedEffect(devices) { devices?.loadStudio() }
    val scroll = rememberScrollState()
    Column(modifier.fillMaxSize().fadeEdges(scroll).verticalScroll(scroll).padding(top = top, start = Dim.margin, end = Dim.margin).testTag("studio_screen")) {
        ScreenHeader("Studio")
        Reveal(pair?.studio?.isNotEmpty() == true) {
            Column {
                for (computer in pair?.studio?.values.orEmpty()) {
                    DisclosureRow(computer.name, { scope.launch { problem = devices?.openStudio(computer.key).orEmpty() } }, "studio_${computer.key}", summary = "Tạo sách nói từ xa")
                }
            }
        }
        Reveal(pair?.studio.isNullOrEmpty()) {
            Column {
                BasicText("Studio trên máy tính", style = Abook.type.sectionTitle)
                BasicText("Nối máy tính để làm sách nói và xem tiến độ.", style = Abook.type.bodySmall)
                TextAction("Nối máy tính", connect, "studio_connect")
            }
        }
        if (companion != null) {
            Spacer(Modifier.height(Dim.s24))
            StudioNotices(companion, askNotifications, openNotificationSettings)
        }
        Reveal(problem.isNotEmpty()) { Caption(problem) }
    }
}
