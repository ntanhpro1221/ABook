package vn.abook.player.ui.screens

import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.IconSlot
import vn.abook.player.ui.components.IconGap
import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.LocalEmbeddedPane
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.WidthClass
import vn.abook.player.ui.theme.widthClass
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.flow.first
import vn.abook.player.ui.components.DevicesIcon
import vn.abook.player.ui.components.HeadphonesIcon
import vn.abook.player.ui.components.MoonIcon
import vn.abook.player.ui.components.ScreenHeader
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.WrenchIcon
import vn.abook.player.ui.components.ThemeIcon
import vn.abook.player.ui.components.VoiceIcon
import vn.abook.player.ui.data.AppSettings
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.SettingsSummary
import vn.abook.player.ui.data.VoiceList
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.devices.DevicesState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.voice.VoicePage
import vn.abook.player.ui.music.MusicState
import vn.abook.player.ui.voice.VoiceState
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.ThemeReveal
import vn.abook.player.ui.components.fadeEdges

/** Việc Cài đặt nhờ hệ điều hành làm (mở trang khác, bảng chia sẻ): Activity cung cấp, test đưa bản giả. */
class SettingsLinks(
    val openNotificationSettings: () -> Unit = {},
    val shareLogs: () -> Unit = {},
    val openSource: () -> Unit = {},
    val openRelease: (String) -> Unit = {},
    val saveOld: (String, (String?) -> Unit) -> Unit = { _, result -> result(null) },
)

/** Mọi thứ màn Cài đặt cần, gom một chỗ để khung chỉ chuyển một tham số: kho, vòng lan đổi giao diện, cửa ra hệ điều hành. */
@Stable
class SettingsEnv(
    val repo: SettingsRepo, val reveal: ThemeReveal, val links: SettingsLinks = SettingsLinks(), val devices: DevicesState? = null,
    val voice: VoiceState? = null,
    /** Nhạc nền của từng cuốn (trang sách, trình phát); null = bản thử. */
    val music: MusicState? = null,
    /** Cửa sổ nhỏ (PiP); null hay không có PiP thì Cài đặt không có công tắc "Tự mở cửa sổ mini". */
    val pip: vn.abook.player.ui.pip.PipControl? = null,
    /** "Làm trước" các chương tới (tấm Giọng đọc của trình phát, dấu "Đã làm sẵn" ở trang sách); null = bản thử. */
    val prepare: vn.abook.player.ui.data.PrepareState? = null,
    /** Nhật ký đêm: thẻ "Tối qua" ở Thư viện, và tấm Hẹn giờ nhắc thẻ ấy; null = bản thử. */
    val night: vn.abook.player.ui.data.NightState? = null,
)

/**
 * Tab Cài đặt (cấp một): danh sách phẳng sáu nhóm - biểu tượng + tên + một dòng giá trị hiện tại (DESIGN.md §7 "Cài đặt"); chạm một nhóm thì màn con của nó
 * trượt vào ([onOpen] đẩy lên ngăn xếp), Back trượt ra đúng đường ấy. Không có cấp ba.
 *
 * Từ khổ expanded của bề ngang nội dung (DESIGN.md §5.5 "Khổ cửa sổ", như Qt): nhóm ở cột trái (260 dp), màn con của nhóm đang chọn ở cột phải, tối đa
 * 1180 dp cả hai. Chọn nhóm KHÔNG đẩy màn lên ngăn xếp (Back vẫn chỉ rời tab); việc mở tiếp từ trong nhóm ([openDevices], [openVoice]) vẫn là màn riêng.
 *
 * `shown`: tab đang được thấy (đọc ngoài composition): danh sách giọng (cho dòng "Giọng đọc") chỉ hỏi lõi khi bạn mở tab lần đầu, không lúc tab được dựng
 * trước lúc rảnh.
 */
@Composable
fun SettingsScreen(
    env: SettingsEnv, onOpen: (SettingsGroup) -> Unit, modifier: Modifier = Modifier, shown: () -> Boolean = { true },
    sheets: SheetHost = SheetHost(), openDevices: (DevicesPage) -> Unit = {}, openVoice: (VoicePage) -> Unit = {},
) {
    val repo = env.repo
    val settings by repo.state.collectAsState()
    val voices by repo.voices.collectAsState()
    LaunchedEffect(repo) {
        snapshotFlow(shown).first { it }
        if (repo.voices.value is VoiceList.Loading) repo.loadVoices()
    }
    // Nhóm đang mở ở cột phải: nhớ qua xoay máy và qua lúc cửa sổ hẹp lại rồi rộng ra.
    var selected by rememberSaveable { mutableStateOf(SettingsGroup.entries.first()) }
    BoxWithConstraints(modifier.fillMaxSize()) {
        val wide = widthClass(maxWidth.value) >= WidthClass.EXPANDED
        AnimatedContent(wide, Modifier.fillMaxSize(), transitionSpec = { Motion.layoutSwitch(targetState) }, label = "settings-layout") { twoColumns ->
            if (twoColumns) {
                Box(Modifier.fillMaxSize().testTag("settings_split"), contentAlignment = Alignment.TopCenter) {
                    Row(Modifier.widthIn(max = SettingsMaxWidth).fillMaxSize()) {
                        GroupList(settings, voices, repo.version, selected, { selected = it }, Modifier.width(GroupColumnWidth))
                        // Đổi nhóm thì màn con trượt như đổi khổ; mỗi màn con tự cuộn.
                        AnimatedContent(selected, Modifier.weight(1f).fillMaxHeight().testTag("settings_pane"), transitionSpec = { Motion.layoutSwitch(true) }, label = "settings-pane") { group ->
                            CompositionLocalProvider(LocalEmbeddedPane provides true) {
                                SettingsGroupScreen(group, env, sheets, onBack = {}, openDevices = openDevices, openVoice = openVoice)
                            }
                        }
                    }
                }
            } else {
                GroupList(settings, voices, repo.version, null, onOpen, Modifier.fillMaxSize())
            }
        }
    }
}

/** Bề ngang cột nhóm ở bố cục hai cột (như Qt SettingsScreen.qml) và trần cả hai cột (DESIGN.md §5.5). */
private val GroupColumnWidth = 260.dp
private val SettingsMaxWidth = 1180.dp

/** Danh sách nhóm. `selected` == null: danh sách một cột (chạm mở màn con); khác null: cột trái của hai cột, nhóm đang mở nền trung tính nhạt + chữ đậm. */
@Composable
private fun GroupList(
    settings: AppSettings, voices: VoiceList, version: String, selected: SettingsGroup?, onPick: (SettingsGroup) -> Unit, modifier: Modifier,
) {
    val split = selected != null
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val scroll = rememberScrollState()
    Column(
        modifier.testTag("settings_screen").fadeEdges(scroll, startInset = top).verticalScroll(scroll)
            .padding(top = top, start = if (split) Dim.margin - Dim.s8 else Dim.margin, end = if (split) Dim.s8 else Dim.margin, bottom = Dim.s24),
    ) {
        Box(Modifier.padding(horizontal = if (split) Dim.s8 else 0.dp)) { ScreenHeader("Cài đặt") }
        for ((index, group) in SettingsGroup.entries.withIndex()) {
            if (!split && index > 0) RowLine(start = IconSlot + IconGap)
            val here = group == selected
            val row: @Composable () -> Unit = {
                DisclosureRow(
                    group.label,
                    onClick = { onPick(group) },
                    tag = group.tag,
                    summary = summary(group, settings, voices, version),
                    icon = { GroupIcon(group, if (here) Abook.colors.text else Abook.colors.text2) },
                    chevron = !split,
                )
            }
            if (split) {
                Box(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(Dim.radiusControl))
                        .then(if (here) Modifier.background(Abook.colors.accentSoft) else Modifier)
                        .padding(horizontal = Dim.s8).semantics { this.selected = here },
                ) { row() }
            } else {
                row()
            }
        }
    }
}

private fun summary(group: SettingsGroup, settings: AppSettings, voices: VoiceList, version: String): String? = when (group) {
    SettingsGroup.Voice -> (voices as? VoiceList.Ready)?.chosenVoice?.name
    SettingsGroup.Listen -> SettingsSummary.listen(settings)
    SettingsGroup.Sleep -> SettingsSummary.sleep(settings)
    SettingsGroup.Look -> SettingsSummary.look(settings)
    SettingsGroup.Devices -> "Nối máy · chia sẻ · dung lượng"
    SettingsGroup.Advanced -> "Phiên bản $version"
}

@Composable
private fun GroupIcon(group: SettingsGroup, color: Color) = when (group) {
    SettingsGroup.Voice -> VoiceIcon(color)
    SettingsGroup.Listen -> HeadphonesIcon(color)
    SettingsGroup.Sleep -> MoonIcon(color)
    SettingsGroup.Look -> ThemeIcon(color)
    SettingsGroup.Devices -> DevicesIcon(color)
    SettingsGroup.Advanced -> WrenchIcon(color)
}

/** Màn con của một nhóm (cấp hai, cấp cuối). Bảng trượt (chọn giờ, nhật ký, thành phần) mở qua [sheets] - lớp nổi, không phải cấp thứ ba. */
@Composable
fun SettingsGroupScreen(
    group: SettingsGroup, env: SettingsEnv, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier,
    openDevices: (DevicesPage) -> Unit = {}, openVoice: (VoicePage) -> Unit = {},
) {
    when (group) {
        SettingsGroup.Voice -> VoiceSettings(env, sheets, openVoice, onBack, modifier)
        SettingsGroup.Listen -> ListenSettings(env, openVoice, onBack, modifier)
        SettingsGroup.Sleep -> SleepSettings(env.repo, sheets, onBack, modifier)
        SettingsGroup.Look -> LookSettings(env, onBack, modifier)
        SettingsGroup.Devices -> DevicesSettings(env.devices, sheets, openDevices, onBack, modifier)
        SettingsGroup.Advanced -> AdvancedSettings(env, sheets, onBack, modifier)
    }
}

/** testTag của màn con một nhóm ("settings_look_screen"). */
internal val SettingsGroup.screenTag: String get() = "${tag}_screen"
