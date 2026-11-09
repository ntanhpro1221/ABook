package vn.abook.player.ui.screens

import vn.abook.player.S

import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.ActionRow
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.devices.DevicesState
import vn.abook.player.ui.devices.RenameSheet
import vn.abook.player.ui.devices.Summary
import androidx.compose.runtime.LaunchedEffect
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
import vn.abook.player.ui.components.BasicText
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
import vn.abook.player.ui.data.ShakeSensitivity
import vn.abook.player.ui.data.SleepSchedule
import vn.abook.player.ui.data.ThemeMode
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.voice.VoicePage
import vn.abook.player.ui.voice.VoiceSummary
import vn.abook.player.ui.components.fadeEdges

private val ScheduleOptions = SleepSchedule.MINUTES.map { Option(it, S.s_0_phut_2596d212(it)) }
private val ExtendOptions = AppSettings.EXTEND_MINUTES.map { Option(it, S.s_0_phut_2596d212(it)) }
private val FadeOptions = AppSettings.FADE_SECONDS.map { Option(it, if (it == 60) S.s_1_phut_eca10dbb else S.s_0_giay_daac30d3(it)) }

/** Lời của các hàng. */
private object GroupCopy {
    const val NOTIFY = S.s_dang_tat_khong_bao_khi_sach_xong_nut_tam_d_1db703e7
    const val REWIND = S.s_nghi_qua_30_giay_thi_lui_5_giay_qua_10_phu_328c3ffd
    const val HEADSET = S.s_bat_nut_truoc_sau_lui_toi_15_giay_tat_chuy_6fc6ddb5
    const val AUTO_MUSIC = S.s_sach_chi_co_chu_nhac_nhe_doi_theo_canh_aef4ce0c
    const val FLIP = S.s_lat_len_trong_10_phut_la_nghe_tiep_6a636fb0
    const val SOUNDS = S.s_copy_34fb8bbc7719
    const val SCHEDULE = S.s_may_ranh_2_phut_trong_khung_gio_nay_moi_tu_93ce72b6
    const val SHAKE = S.s_dang_hen_gio_lac_nhe_hai_lan_de_hen_lai_tu_c3c8f5c5
    const val SURFACE = S.s_nen_cua_chu_khi_doc_theo_d0cbef86
    const val HAPTICS = S.s_rung_nhe_khi_ban_chon_hay_giu_5292ace9
    const val AUTO_PIP = S.s_roi_app_khi_co_sach_mo_thi_sach_thu_vao_cu_7f4e317e
}

/** Nghe: thông báo (chỉ khi đang tắt), tự lùi, nút tai nghe; khối Nhạc nền. */
@Composable
fun ListenSettings(env: SettingsEnv, openVoice: (VoicePage) -> Unit, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val repo = env.repo
    val settings by repo.state.collectAsState()
    val voice = env.voice
    val summary by (voice?.summary ?: NoVoiceSummary).collectAsState()
    LaunchedEffect(voice) { voice?.loadMusic() }
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
                    ActionRow(S.s_thong_bao_a9b656f5, S.s_cho_phep_f1a437f5, env.links.openNotificationSettings, "notify_allow", hint = GroupCopy.NOTIFY)
                    RowLine()
                }
            }
            SwitchRow(S.s_tu_lui_6fc7685a, settings.autoRewind, { on -> repo.change { it.copy(autoRewind = on) } }, "auto_rewind", GroupCopy.REWIND)
            RowLine()
            SwitchRow(S.s_nut_tai_nghe_lui_toi_973e4a19, settings.headsetSkips, { on -> repo.change { it.copy(headsetSkips = on) } }, "headset_skips", GroupCopy.HEADSET)
            if (env.pip?.available == true) {
                RowLine()
                SwitchRow(S.s_tu_mo_cua_so_mini_a93a51d2, settings.autoPip, { on -> repo.change { it.copy(autoPip = on) } }, "auto_pip", GroupCopy.AUTO_PIP)
            }
        }
        ListSection(S.s_nhac_nen_271fb292) {
            SwitchRow(S.s_tu_chon_nhac_nen_a14c52b4, settings.autoMusic, { on -> repo.change { it.copy(autoMusic = on) } }, "auto_music", GroupCopy.AUTO_MUSIC)
            RowLine()
            DisclosureRow(S.s_nhac_cua_toi_f65b7ac6, { if (voice != null) openVoice(VoicePage.Music) }, "my_music", summary = summary.music)
        }
    }
}

/** Hẹn giờ ngủ: lịch đêm (giờ chọn trong bảng trượt), cử chỉ, khi sắp tắt. */
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
            SwitchRow(
                S.s_lich_dem_5f61612f, settings.schedule != null,
                { on -> repo.change { it.copy(schedule = if (on) SleepSchedule.Default else null) } }, "sleep_schedule", GroupCopy.SCHEDULE,
            )
            Reveal(settings.schedule != null) {
                Column(Modifier.fillMaxWidth().testTag("schedule_editor")) {
                    Row(Modifier.fillMaxWidth()) {
                        TimeField(S.s_tu_c2634aaa, schedule.from, "schedule_from", Modifier.weight(1f)) {
                            pickTime(S.s_tu_c2634aaa, schedule.from) { plan, time -> plan.copy(from = time) }
                        }
                        Spacer(Modifier.width(Dim.s16))
                        TimeField(S.s_den_4f14ac22, schedule.to, "schedule_to", Modifier.weight(1f)) {
                            pickTime(S.s_den_4f14ac22, schedule.to) { plan, time -> plan.copy(to = time) }
                        }
                    }
                    ChoiceSetting(
                        S.s_hen_244e495e, ScheduleOptions, ScheduleOptions.firstOrNull { it.value == schedule.minutes } ?: ScheduleOptions[1],
                        { option, _ -> repo.change { now -> now.schedule?.let { now.copy(schedule = it.copy(minutes = option.value)) } ?: now } },
                        "schedule_minutes",
                    )
                }
            }
        }
        ListSection(S.s_cu_chi_0ae3f7ba) {
            SwitchRow(S.s_lac_de_nghe_them_405614ff, settings.shakeToExtend, { on -> repo.change { it.copy(shakeToExtend = on) } }, "shake", GroupCopy.SHAKE)
            Reveal(settings.shakeToExtend) {
                Column {
                    RowLine()
                    ChoiceSetting(
                        S.s_do_nhay_5af83fde, ShakeSensitivity.entries, settings.shakeSensitivity,
                        { level, _ -> repo.change { it.copy(shakeSensitivity = level) } }, "shake_sensitivity",
                    )
                }
            }
            RowLine()
            SwitchRow(S.s_up_may_de_dung_f4c69dd7, settings.flipToPause, { on -> repo.change { it.copy(flipToPause = on) } }, "flip_pause", GroupCopy.FLIP)
        }
        ListSection(S.s_khi_sap_tat_ac78648f) {
            ChoiceSetting(
                S.s_moi_lan_nghe_them_9a74fcef, ExtendOptions, ExtendOptions.first { it.value == settings.sleepExtendMinutes },
                { option, _ -> repo.change { it.copy(sleepExtendMinutes = option.value) } }, "sleep_extend",
            )
            RowLine()
            ChoiceSetting(
                S.s_nho_dan_ae8f3a2d, FadeOptions, FadeOptions.first { it.value == settings.sleepFadeSeconds },
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
        LazyColumn(Modifier.fillMaxWidth().heightIn(max = 400.dp).fadeEdges(list), state = list) {
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
 * Giao diện: màu (Tự động / Sáng / Tối - đổi ngay cả app, vòng lan từ chữ vừa chạm), nền đọc, tiếng chạm, rung. Chọn S.s_tu_dong_a25c8028 -> S.s_sang_8f0c677d khi máy đang sáng thì không
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
                S.s_mau_bf45a510, ThemeMode.entries, settings.theme,
                { mode, at ->
                    val flips = mode.dark(systemDark) != repo.state.value.theme.dark(systemDark)
                    env.reveal.change(at, flips) { repo.change { it.copy(theme = mode) } }
                },
                "theme",
            )
            RowLine()
            ChoiceSetting(
                S.s_nen_doc_25ec1519, ReadingSurface.entries, settings.readingSurface,
                { surface, _ -> repo.change { it.copy(readingSurface = surface) } }, "reading_surface", GroupCopy.SURFACE,
            )
            RowLine()
            SwitchRow(S.s_am_thanh_cham_a33e2a3c, settings.touchSounds, { on -> repo.change { it.copy(touchSounds = on) } }, "touch_sounds", GroupCopy.SOUNDS)
            RowLine()
            SwitchRow(S.s_rung_24cfaa21, settings.haptics, { on -> repo.change { it.copy(haptics = on) } }, "haptics", GroupCopy.HAPTICS)
        }
    }
}

/**
 * Thiết bị: ba màn riêng (Nối máy tính, Chia sẻ thư viện, Dung lượng - [vn.abook.player.ui.devices]) mỗi cái một hàng có mũi tên và một dòng giá trị hiện tại,
 * rồi tên của máy này (máy kia thấy điện thoại bằng tên ấy; chạm mở bảng đổi tên). `devices` null (ảnh chụp không có lõi): hàng vẫn dựng, chưa có dòng giá trị.
 */
@Composable
fun DevicesSettings(devices: DevicesState?, sheets: SheetHost, open: (DevicesPage) -> Unit, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val summary by (devices?.summary ?: NoSummary).collectAsState()
    LaunchedEffect(devices) { devices?.loadSummary() }
    SettingsPage(SettingsGroup.Devices.label, onBack, SettingsGroup.Devices.screenTag, modifier) {
        ListSection(first = true) {
            DisclosureRow(S.s_noi_may_tinh_2950692d, { open(DevicesPage.Pair) }, "devices_pair", summary = summary.pair)
            RowLine()
            DisclosureRow(S.s_chia_se_thu_vien_940de671, { open(DevicesPage.Share) }, "devices_share", summary = summary.sharing)
            RowLine()
            DisclosureRow(S.s_dung_luong_32009349, { open(DevicesPage.Storage) }, "devices_storage", summary = summary.storageLine)
            RowLine()
        }
        ListSection(S.s_dien_thoai_nay_94875d9a) {
            ActionRow(
                S.s_ten_thiet_bi_525223a8, S.s_doi_ten_a2a0dc70, { if (devices != null) sheets.show { dismiss -> RenameSheet(summary.deviceName, devices, dismiss) } }, "devices_name",
                hint = summary.deviceName,
            )
        }
    }
}

private val NoSummary = kotlinx.coroutines.flow.MutableStateFlow(Summary())
private val NoVoiceSummary = kotlinx.coroutines.flow.MutableStateFlow(VoiceSummary())
