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
    sheets: SheetHost? = null,
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
                Caption("Tạo sách nói từ xa")
                val computers = pair?.studio?.values.orEmpty().toList()
                val openable = computers.filterNot { it.listenOnly }
                if (openable.isEmpty()) {
                    Caption(DeviceText.studioBlocked(computers.map { it.name }))
                    Caption("Bật Điều khiển từ xa trên máy tính.")
                } else {
                    TextAction("Mở Studio", {
                        fun open(computer: StudioComputer) { scope.launch { problem = devices?.openStudio(computer.key).orEmpty() } }
                        if (openable.size == 1) open(openable[0])
                        else sheets?.show { dismiss ->
                            Column(Modifier.fillMaxWidth()) {
                                BasicText("Mở Studio của máy nào?", style = Abook.type.sectionTitle)
                                for (computer in openable) DisclosureRow(computer.name, { dismiss(); open(computer) }, "studio_${computer.key}")
                            }
                        }
                    }, "studio_open")
                }
            }
        }
        Reveal(pair?.studio.isNullOrEmpty()) {
            Column {
                BasicText("Studio trên máy tính", style = Abook.type.sectionTitle)
                RowHint("Nối máy tính để làm sách nói và xem tiến độ.")
                Caption("Chưa ghép với máy tính nào")
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
