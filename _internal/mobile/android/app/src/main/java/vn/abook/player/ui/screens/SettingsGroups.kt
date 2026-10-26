package vn.abook.player.ui.screens

import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.Reveal
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.AppSettings
import vn.abook.player.ui.data.Quarters
import vn.abook.player.ui.data.ReadingSurface
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.ShakeAction
import vn.abook.player.ui.data.ShakeSensitivity
import vn.abook.player.ui.data.SleepSchedule
import vn.abook.player.ui.data.ThemeMode
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

private val SafetyOptions = AppSettings.SAFETY_HOURS.map { Option(it, if (it == 0) "Không" else "$it giờ") }
private val ScheduleOptions = SleepSchedule.MINUTES.map { Option(it, "$it phút") }
private val ExtendOptions = AppSettings.EXTEND_MINUTES.map { Option(it, "$it′") }
private val FadeOptions = AppSettings.FADE_SECONDS.map { Option(it, "${it}s") }

/** Lời của các hàng: cùng chữ với bản WebView (android/SettingsScreen.tsx, listen/playlistBed.ts, shared/feedback.ts, android/notifications.ts). */
private object GroupCopy {
    const val NOTIFY = "Đang tắt"
    const val REWIND = "Nghỉ quá 30 giây thì lùi 5 giây (quá 10 phút: 10 giây)."
    const val HEADSET = "Bật: nút Trước/Sau lùi/tới 15 giây. Tắt: chuyển chương."
    const val AUTO_MUSIC = "Sách chỉ có chữ: nhạc nhẹ đổi theo cảnh."
    const val SAFETY = "Không chạm máy chừng này thì nhỏ dần rồi dừng."
    const val FLIP = "Lật lên trong 10 phút là nghe tiếp."
    const val SOUNDS = "Im khi đang nghe."
}

/** Nghe: thông báo (chỉ khi đang tắt), tự lùi, nút tai nghe; khối Nhạc nền. */
@Composable
fun ListenSettings(env: SettingsEnv, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val settings by repo.state.collectAsState()
    val allowed by repo.notificationsAllowed.collectAsState()
    // Mở màn và mỗi lần quay lại từ Cài đặt Android: hỏi lại quyền - cho phép xong thì dòng khép lại tại chỗ.
    LifecycleResumeEffect(repo) {
        repo.checkNotifications()
        onPauseOrDispose { }
    }
    SettingsPage(SettingsGroup.Listen.label, onBack, SettingsGroup.Listen.screenTag, modifier) {
        ListSection(first = true) {
            Reveal(!allowed) {
                Column {
                    ActionRow("Thông báo", "Cho phép", env.links.openNotificationSettings, "notify_allow", hint = GroupCopy.NOTIFY)
                    RowLine()
                }
            }
            SwitchRow("Tự lùi", settings.autoRewind, { on -> repo.change { it.copy(autoRewind = on) } }, "auto_rewind", GroupCopy.REWIND)
            RowLine()
            SwitchRow("Nút tai nghe", settings.headsetSkips, { on -> repo.change { it.copy(headsetSkips = on) } }, "headset_skips", GroupCopy.HEADSET)
        }
        ListSection("Nhạc nền") {
            SwitchRow("Tự chọn nhạc nền", settings.autoMusic, { on -> repo.change { it.copy(autoMusic = on) } }, "auto_music", GroupCopy.AUTO_MUSIC)
            RowLine()
            SoonRow("Nhạc của tôi", "Nhạc riêng của bạn cho mọi cuốn.", tag = "my_music")
        }
    }
}

/** Hẹn giờ ngủ: tự tắt, lịch đêm (giờ chọn trong bảng trượt), cử chỉ, khi sắp tắt. */
@Composable
fun SleepSettings(repo: SettingsRepo, sheets: SheetHost, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val settings by repo.state.collectAsState()
    // Lịch vừa tắt vẫn vẽ trong lúc khối khép lại (không trống trơn giữa chừng).
    val lastSchedule = remember { arrayOf(SleepSchedule.Default) }
    settings.schedule?.let { lastSchedule[0] = it }
    val schedule = lastSchedule[0]
    fun pickTime(title: String, value: String, set: (SleepSchedule, String) -> SleepSchedule) {
        sheets.show { dismiss ->
            TimeSheet(title, value) { time ->
                dismiss()
                repo.change { now -> now.schedule?.let { now.copy(schedule = set(it, time)) } ?: now }
            }
        }
    }
    SettingsPage(SettingsGroup.Sleep.label, onBack, SettingsGroup.Sleep.screenTag, modifier) {
        ListSection(first = true) {
            ChoiceSetting(
                "Tự tắt", SafetyOptions, SafetyOptions.first { it.value == settings.safetyStopHours },
                { option, _ -> repo.change { it.copy(safetyStopHours = option.value) } }, "safety_stop", GroupCopy.SAFETY,
            )
            RowLine()
            SwitchRow(
                "Lịch đêm", settings.schedule != null,
                { on -> repo.change { it.copy(schedule = if (on) SleepSchedule.Default else null) } }, "sleep_schedule",
            )
            Reveal(settings.schedule != null) {
                Column(Modifier.fillMaxWidth().testTag("schedule_editor")) {
                    Row(Modifier.fillMaxWidth()) {
                        TimeField("Từ", schedule.from, "schedule_from", Modifier.weight(1f)) {
                            pickTime("Từ", schedule.from) { plan, time -> plan.copy(from = time) }
                        }
                        Spacer(Modifier.width(Dim.s16))
                        TimeField("Đến", schedule.to, "schedule_to", Modifier.weight(1f)) {
                            pickTime("Đến", schedule.to) { plan, time -> plan.copy(to = time) }
                        }
                    }
                    ChoiceSetting(
                        "Hẹn", ScheduleOptions, ScheduleOptions.firstOrNull { it.value == schedule.minutes } ?: ScheduleOptions[1],
                        { option, _ -> repo.change { now -> now.schedule?.let { now.copy(schedule = it.copy(minutes = option.value)) } ?: now } },
                        "schedule_minutes",
                    )
                }
            }
        }
        ListSection("Cử chỉ") {
            SwitchRow("Lắc để nghe thêm", settings.shakeToExtend, { on -> repo.change { it.copy(shakeToExtend = on) } }, "shake")
            Reveal(settings.shakeToExtend) {
                Column {
                    RowLine()
                    ChoiceSetting(
                        "Khi lắc", ShakeAction.entries, settings.shakeAction,
                        { action, _ -> repo.change { it.copy(shakeAction = action) } }, "shake_action",
                    )
                    RowLine()
                    ChoiceSetting(
                        "Độ nhạy", ShakeSensitivity.entries, settings.shakeSensitivity,
                        { level, _ -> repo.change { it.copy(shakeSensitivity = level) } }, "shake_sensitivity",
                    )
                }
            }
            RowLine()
            SwitchRow("Úp máy để dừng", settings.flipToPause, { on -> repo.change { it.copy(flipToPause = on) } }, "flip_pause", GroupCopy.FLIP)
        }
        ListSection("Khi sắp tắt") {
            ChoiceSetting(
                "Mỗi lần thêm", ExtendOptions, ExtendOptions.first { it.value == settings.sleepExtendMinutes },
                { option, _ -> repo.change { it.copy(sleepExtendMinutes = option.value) } }, "sleep_extend",
            )
            RowLine()
            ChoiceSetting(
                "Nhỏ dần", FadeOptions, FadeOptions.first { it.value == settings.sleepFadeSeconds },
                { option, _ -> repo.change { it.copy(sleepFadeSeconds = option.value) } }, "sleep_fade",
            )
        }
    }
}

/** Một mốc giờ của lịch đêm: nhãn nhỏ trên, giờ lớn dưới; chạm mở bảng chọn giờ. Cao 56 (chạm). */
@Composable
private fun TimeField(label: String, value: String, tag: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Column(modifier.heightIn(min = 56.dp).pressable(onClick = onClick).testTag(tag).padding(vertical = Dim.s8)) {
        BasicText(label, style = Abook.type.caption.copy(color = Abook.colors.text2))
        BasicText(value, style = Abook.type.sectionTitle)
    }
}

/** Bảng chọn giờ: mỗi 15 phút một dòng, cuộn sẵn tới giờ đang chọn; dòng đang chọn chữ hổ phách + dấu tích đầu dòng (giữ chỗ cho mọi dòng). */
@Composable
private fun TimeSheet(title: String, value: String, onPick: (String) -> Unit) {
    val times = remember(value) { Quarters.around(value) }
    val list = rememberLazyListState(initialFirstVisibleItemIndex = (times.indexOf(value) - 3).coerceAtLeast(0))
    Column(Modifier.fillMaxWidth().testTag("time_sheet")) {
        BasicText(title, style = Abook.type.sectionTitle)
        Spacer(Modifier.size(Dim.s8))
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 400.dp), state = list) {
            items(times, key = { it }, contentType = { "time" }) { time ->
                val chosen = time == value
                Row(
                    Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable(Role.RadioButton) { onPick(time) }
                        .semantics { selected = chosen }.testTag("time_$time"),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(Dim.s24), contentAlignment = Alignment.CenterStart) {
                        if (chosen) CheckIcon(Abook.colors.accentText)
                    }
                    BasicText(time, style = Abook.type.body.copy(color = if (chosen) Abook.colors.accentText else Abook.colors.text))
                }
            }
        }
    }
}

/**
 * Giao diện: màu (Tự động / Sáng / Tối - đổi ngay cả app, vòng lan từ chữ vừa chạm), nền đọc, tiếng chạm, rung. Chọn "Tự động" -> "Sáng" khi máy đang sáng thì không
 * có gì để lan: đổi thẳng.
 */
@Composable
fun LookSettings(env: SettingsEnv, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val settings by repo.state.collectAsState()
    val systemDark = isSystemInDarkTheme()
    SettingsPage(SettingsGroup.Look.label, onBack, SettingsGroup.Look.screenTag, modifier) {
        ListSection(first = true) {
            ChoiceSetting(
                "Màu", ThemeMode.entries, settings.theme,
                { mode, at ->
                    val flips = mode.dark(systemDark) != repo.state.value.theme.dark(systemDark)
                    env.reveal.change(at, flips) { repo.change { it.copy(theme = mode) } }
                },
                "theme",
            )
            RowLine()
            ChoiceSetting(
                "Nền đọc", ReadingSurface.entries, settings.readingSurface,
                { surface, _ -> repo.change { it.copy(readingSurface = surface) } }, "reading_surface",
            )
            RowLine()
            SwitchRow("Âm thanh chạm", settings.touchSounds, { on -> repo.change { it.copy(touchSounds = on) } }, "touch_sounds", GroupCopy.SOUNDS)
            RowLine()
            SwitchRow("Rung", settings.haptics, { on -> repo.change { it.copy(haptics = on) } }, "haptics")
        }
    }
}

/**
 * Thiết bị: ghép máy tính, chia sẻ thư viện, dung lượng - lõi có (Peers, ShareService, Store) nhưng màn native của chúng là bước "Thiết bị / ghép máy" riêng
 * (NATIVE_PHONE_UI.md §6, P2); tới lúc đó nói thẳng "Sắp có".
 */
@Composable
fun DevicesSettings(onBack: () -> Unit, modifier: Modifier = Modifier) {
    SettingsPage(SettingsGroup.Devices.label, onBack, SettingsGroup.Devices.screenTag, modifier) {
        ListSection(first = true) {
            SoonRow("Nối máy tính", "Nghe sách của máy tính, dùng Studio từ xa.", tag = "devices_pair")
            RowLine()
            SoonRow("Chia sẻ thư viện", "Máy khác trong nhà nghe sách của máy này.", tag = "devices_share")
            RowLine()
            SoonRow("Dung lượng", "Sách nào chiếm bao nhiêu chỗ trên máy.", tag = "devices_storage")
        }
    }
}
