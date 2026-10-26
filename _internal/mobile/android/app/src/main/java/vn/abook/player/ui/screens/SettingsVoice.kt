package vn.abook.player.ui.screens

import vn.abook.player.ui.components.PageHeader
import vn.abook.player.ui.components.ListSection
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.ListRow
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.Reveal
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.VoiceList
import vn.abook.player.ui.data.VoiceOption
import vn.abook.player.ui.data.VoiceSpeedChoice
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Máy chưa có giọng tiếng Việt của hệ điều hành (như `deviceHint` của bản WebView). */
private const val DEVICE_HINT = "Điện thoại chưa có giọng tiếng Việt. Cài ở Cài đặt điện thoại › Chuyển văn bản thành giọng nói."

/**
 * Giọng đọc: giọng mặc định của "Nghe ngay" (cuốn chưa chọn giọng riêng), xếp theo nơi đọc; tốc độ đọc của giọng trên máy. Danh sách giọng có thể dài (giọng của
 * máy) nên cả màn là MỘT danh sách lười, mỗi giọng một mục có khoá.
 */
@Composable
fun VoiceSettings(repo: SettingsRepo, onBack: () -> Unit, modifier: Modifier = Modifier) {
    val voices by repo.voices.collectAsState()
    val speed by repo.speed.collectAsState()
    LaunchedEffect(repo) {
        if (repo.voices.value !is VoiceList.Ready) repo.loadVoices()
        repo.loadSpeed()
    }
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val bottom = WindowInsets.navigationBars.asPaddingValues().calculateBottomPadding()
    LazyColumn(
        modifier.fillMaxSize().testTag(SettingsGroup.Voice.screenTag),
        contentPadding = PaddingValues(top = top, start = Dim.margin, end = Dim.margin, bottom = bottom + Dim.s48),
    ) {
        item(key = "header", contentType = "header") { PageHeader(SettingsGroup.Voice.label, onBack) }
        when (val list = voices) {
            VoiceList.Loading -> item(key = "loading", contentType = "loading") { VoiceSkeleton() }
            VoiceList.Failed -> item(key = "failed", contentType = "failed") {
                ListRow("Chưa tải được giọng", hint = "Bạn hãy kiểm tra kết nối rồi tải lại giọng đọc.") {
                    TextAction("Thử lại", repo::loadVoices, "voices_retry")
                }
            }
            is VoiceList.Ready -> {
                item(key = "current", contentType = "current") {
                    BasicText(
                        "Đang dùng: ${list.chosenVoice?.name ?: "giọng mặc định"}",
                        style = Abook.type.bodyStrong,
                        modifier = Modifier.padding(top = Dim.s16).testTag("voice_current"),
                    )
                }
                for (group in list.groups) {
                    item(key = "group:${group.provider}", contentType = "group") {
                        val detail = if (group.detail.isEmpty()) "${group.voices.size} giọng" else "${group.detail} · ${group.voices.size} giọng"
                        Column(Modifier.fillMaxWidth().padding(top = Dim.s24, bottom = Dim.s4)) {
                            BasicText(group.title, style = Abook.type.sectionTitle)
                            BasicText(detail, style = Abook.type.caption.copy(color = Abook.colors.text2))
                        }
                    }
                    items(group.voices, key = { "voice:${it.id}" }, contentType = { "voice" }) { voice ->
                        VoiceRow(voice, voice.id == list.chosen) { repo.chooseVoice(voice.id) }
                    }
                }
                if (list.groups.none { it.provider == "device" }) {
                    item(key = "device_hint", contentType = "hint") {
                        Column(Modifier.fillMaxWidth().padding(top = Dim.s24)) {
                            BasicText("Giọng của máy", style = Abook.type.sectionTitle)
                            BasicText(DEVICE_HINT, style = Abook.type.caption.copy(color = Abook.colors.text2))
                        }
                    }
                }
            }
        }
        item(key = "speed", contentType = "speed") {
            Reveal(speed != null) {
                val state = speed ?: return@Reveal
                ListSection("Hiệu năng") {
                    ChoiceSetting(
                        "Tốc độ đọc", VoiceSpeedChoice.entries, state.choice,
                        { choice, _ -> repo.chooseSpeed(choice) }, "voice_speed",
                    )
                    for (line in state.lines) {
                        BasicText(line, style = Abook.type.caption.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s4))
                    }
                }
            }
        }
        item(key = "more", contentType = "more") {
            ListSection("Thêm giọng") {
                SoonRow("Giọng VieNeu", "Tải về máy, đọc không cần mạng.", tag = "voice_vieneu")
                RowLine()
                SoonRow("Giọng Supertonic", "Tải về máy, đọc không cần mạng.", tag = "voice_supertonic")
                RowLine()
                SoonRow("Khóa giọng trực tuyến", "Azure, Google Cloud, FPT.AI, Viettel AI.", tag = "voice_keys")
                RowLine()
                SoonRow("Thử giọng", "Nghe một câu trước khi chọn.", tag = "voice_sample")
            }
        }
    }
}

/**
 * Một giọng trong danh sách chọn: dấu tích ĐẦU dòng (luôn giữ chỗ, nở / thu tại chỗ - không mờ) + tên; giọng đang chọn chữ hổ phách (DESIGN.md §6 "Hàng danh
 * sách"). Tên dài xuống dòng.
 */
@Composable
private fun VoiceRow(voice: VoiceOption, chosen: Boolean, onClick: () -> Unit) {
    val mark by animateFloatAsState(if (chosen) 1f else 0f, Motion.Expand, label = "mark")
    Row(
        Modifier.fillMaxWidth().heightIn(min = Dim.s48).pressable(Role.RadioButton, onClick = onClick)
            .semantics { selected = chosen }.testTag("voice_${voice.id}"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(Dim.s24).graphicsLayer { scaleX = mark; scaleY = mark }, contentAlignment = Alignment.CenterStart) {
            CheckIcon(Abook.colors.accentText)
        }
        BasicText(
            voice.name,
            style = Abook.type.body.copy(color = if (chosen) Abook.colors.accentText else Abook.colors.text),
            modifier = Modifier.weight(1f).padding(vertical = Dim.s8),
        )
    }
}

/** Đang hỏi giọng: khung xám đúng hình ba hàng giọng (DESIGN.md §2 "đang tải"), không vòng xoay. */
@Composable
private fun VoiceSkeleton() {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s24).testTag("voices_loading")) {
        for (width in SkeletonWidths) {
            Row(Modifier.fillMaxWidth().height(Dim.s48), verticalAlignment = Alignment.CenterVertically) {
                Spacer(Modifier.size(Dim.s24))
                Box(Modifier.fillMaxWidth(width).height(14.dp).clip(RoundedCornerShape(4.dp)).background(Abook.colors.bgSunken))
            }
        }
    }
}

private val SkeletonWidths = floatArrayOf(0.5f, 0.38f, 0.44f)
