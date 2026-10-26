package vn.abook.player.ui.screens

import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.IconSlot
import vn.abook.player.ui.components.IconGap
import androidx.compose.foundation.layout.Column
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
import vn.abook.player.ui.components.SlidersIcon
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
import vn.abook.player.ui.voice.VoiceState
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.ThemeReveal

/** Việc Cài đặt nhờ hệ điều hành làm (mở trang khác, bảng chia sẻ): Activity cung cấp, test đưa bản giả. */
class SettingsLinks(
    val openNotificationSettings: () -> Unit = {},
    val shareLogs: () -> Unit = {},
    val openSource: () -> Unit = {},
)

/** Mọi thứ màn Cài đặt cần, gom một chỗ để khung chỉ chuyển một tham số: kho, vòng lan đổi giao diện, cửa ra hệ điều hành. */
@Stable
class SettingsEnv(
    val repo: SettingsRepo, val reveal: ThemeReveal, val links: SettingsLinks = SettingsLinks(), val devices: DevicesState? = null,
    val voice: VoiceState? = null,
)

/**
 * Tab Cài đặt (cấp một): danh sách phẳng sáu nhóm - biểu tượng + tên + một dòng giá trị hiện tại (DESIGN.md §7 "Cài đặt"); chạm một nhóm thì màn con của nó
 * trượt vào ([onOpen] đẩy lên ngăn xếp), Back trượt ra đúng đường ấy. Không có cấp ba.
 *
 * `shown`: tab đang được thấy (đọc ngoài composition): danh sách giọng (cho dòng "Giọng đọc") chỉ hỏi lõi khi bạn mở tab lần đầu, không lúc tab được dựng
 * trước lúc rảnh.
 */
@Composable
fun SettingsScreen(env: SettingsEnv, onOpen: (SettingsGroup) -> Unit, modifier: Modifier = Modifier, shown: () -> Boolean = { true }) {
    val repo = env.repo
    val settings by repo.state.collectAsState()
    val voices by repo.voices.collectAsState()
    LaunchedEffect(repo) {
        snapshotFlow(shown).first { it }
        if (repo.voices.value is VoiceList.Loading) repo.loadVoices()
    }
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    Column(
        modifier.fillMaxSize().testTag("settings_screen").verticalScroll(rememberScrollState())
            .padding(top = top, start = Dim.margin, end = Dim.margin, bottom = Dim.s24),
    ) {
        ScreenHeader("Cài đặt")
        for ((index, group) in SettingsGroup.entries.withIndex()) {
            if (index > 0) RowLine(start = IconSlot + IconGap)
            DisclosureRow(
                group.label,
                onClick = { onOpen(group) },
                tag = group.tag,
                summary = summary(group, settings, voices, repo.version),
                icon = { GroupIcon(group, Abook.colors.text2) },
            )
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
    SettingsGroup.Advanced -> SlidersIcon(color)
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
