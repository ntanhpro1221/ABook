package vn.abook.player.ui.nowplaying

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.updateTransition
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import kotlinx.coroutines.launch
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.MotionMs

enum class PlayerSheet { Speed, Sleep, Chapters, More, Voice }

/** Sheets translate over a fixed player. There is no scale or translation on the underlying screen. */
@Composable
fun PlayerSheets(state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState) {
    val transition = updateTransition(window.sheetOpen, label = "player-sheet")
    val accent = Abook.colors.accent
    LaunchedEffect(window.sheet, window.sheetOpen) {
        if (window.sheetOpen && window.sheet == PlayerSheet.Voice) model.loadVoices()
    }
    BackHandler(enabled = window.sheetOpen) { window.closeSheet() }
    // Vạch kéo là thật: tấm theo ngón tay xuống, thả quá 1/4 chiều cao hay vuốt nhanh thì đóng, không thì về chỗ.
    val drag = remember { androidx.compose.animation.core.Animatable(0f) }
    val scope = rememberCoroutineScope()
    var sheetHeight by remember { mutableIntStateOf(1) }
    LaunchedEffect(window.sheetOpen) { if (window.sheetOpen) drag.snapTo(0f) }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (transition.currentState || transition.targetState) {
            Box(Modifier.fillMaxSize().drawBehind { drawRect(Color.Black.copy(alpha = 0.24f)) }
                .pressable(onClick = window::closeSheet).semantics { contentDescription = "Đóng bảng" })
        }
        transition.AnimatedVisibility(
            visible = { it }, enter = slideInVertically(tween(MotionMs.SLOW)) { it },
            exit = slideOutVertically(tween(MotionMs.SLOW_OUT)) { it },
            modifier = Modifier.align(Alignment.BottomCenter),
        ) {
            Column(Modifier.fillMaxWidth().heightIn(max = maxHeight * 0.82f)
                .onSizeChanged { sheetHeight = it.height.coerceAtLeast(1) }
                .graphicsLayer { translationY = drag.value }
                .clip(RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp)).background(Abook.colors.panel)
                .navigationBarsPadding().padding(horizontal = 20.dp).padding(top = 12.dp, bottom = 20.dp)
                .testTag("player_sheet_${window.sheet.name.lowercase()}").semantics { paneTitle = sheetTitle(window.sheet) }) {
                // Đầu tấm (vạch + tên) là chỗ kéo; danh sách bên dưới vẫn cuộn bình thường. Đóng bằng kéo, chạm nền tối hay Back - không nút đóng riêng.
                Column(Modifier.fillMaxWidth().testTag("player_sheet_grip").pointerInput(Unit) {
                    val tracker = androidx.compose.ui.input.pointer.util.VelocityTracker()
                    detectVerticalDragGestures(
                        onDragStart = { tracker.resetTracking() },
                        onVerticalDrag = { change, amount ->
                            tracker.addPosition(change.uptimeMillis, change.position)
                            scope.launch { drag.snapTo((drag.value + amount).coerceAtLeast(0f)) }
                        },
                        onDragEnd = {
                            val fling = tracker.calculateVelocity().y
                            scope.launch {
                                if (drag.value > sheetHeight / 4f || fling > 1200f) {
                                    drag.animateTo(sheetHeight.toFloat(), tween(MotionMs.MEDIUM_OUT))
                                    window.closeSheet()
                                } else drag.animateTo(0f, tween(MotionMs.MEDIUM))
                            }
                        },
                        onDragCancel = { scope.launch { drag.animateTo(0f, tween(MotionMs.MEDIUM)) } },
                    )
                }) {
                    Box(Modifier.align(Alignment.CenterHorizontally).width(32.dp).height(4.dp)
                        .background(Abook.colors.line, RoundedCornerShape(2.dp)))
                    Row(Modifier.fillMaxWidth().height(64.dp), verticalAlignment = Alignment.CenterVertically) {
                        RollingLabel(sheetTitle(window.sheet), style = Abook.type.sectionTitle)
                    }
                }
                when (window.sheet) {
                    PlayerSheet.Speed -> {
                        for (row in PlayerLabels.rates.chunked(3)) Row(Modifier.fillMaxWidth()) {
                            for (rate in row) ChoiceCell(PlayerLabels.rate(rate), rate == state.rate, Modifier.weight(1f)) {
                                model.setRate(rate); window.closeSheet()
                            }
                            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                        }
                    }
                    PlayerSheet.Sleep -> {
                        SleepClock(state.sleep, model.position)
                        for (row in PlayerLabels.sleepMinutes.chunked(3)) Row(Modifier.fillMaxWidth()) {
                            for (minutes in row) ChoiceCell("$minutes phút", state.sleep.kind == SleepKind.Minutes && state.sleep.minutes == minutes, Modifier.weight(1f)) {
                                model.setSleep(SleepKind.Minutes, minutes); window.closeSheet()
                            }
                        }
                        SheetRow("Hết chương", if (state.sleep.kind == SleepKind.Chapter) "Đang chọn" else "") {
                            model.setSleep(SleepKind.Chapter); window.closeSheet()
                        }
                        SheetRow("Tắt hẹn giờ", if (state.sleep.kind == SleepKind.Off) "Đang chọn" else "") {
                            model.setSleep(SleepKind.Off); window.closeSheet()
                        }
                    }
                    PlayerSheet.Chapters -> LazyColumn(Modifier.fillMaxWidth()) {
                        items(state.chapters, key = { it.id }, contentType = { "chapter" }) { chapter ->
                            val current = chapter.id == state.chapterId
                            Column(Modifier.fillMaxWidth().pressable { model.jump(chapter.id); window.closeSheet() }
                                .semantics { selected = current }.padding(vertical = 12.dp)) {
                                BasicText(chapter.title, style = Abook.type.body.copy(color = if (current) Abook.colors.accentText else Abook.colors.text))
                                BasicText(if (current) "Đang nghe" else PlayerLabels.time(chapter.durationMs), style = Abook.type.caption)
                                if (current) Box(Modifier.fillMaxWidth().height(2.dp).drawBehind {
                                    val fraction = if (state.durationMs > 0) model.position.milliseconds.value.toFloat() / state.durationMs else 0f
                                    drawRect(accent, size = androidx.compose.ui.geometry.Size(size.width * fraction.coerceIn(0f, 1f), size.height))
                                })
                            }
                        }
                    }
                    PlayerSheet.More -> {
                        if (window.otherPlayers != null) SheetRow("Thiết bị phát", "Chọn") {
                            window.closeSheet()
                            window.otherPlayers?.invoke()
                        }
                        // Nhạc nền chỉ có một lựa chọn bật/tắt: đổi ngay tại hàng, không mở thêm một tấm chỉ chứa đúng một công tắc.
                        SheetRow("Nhạc nền", if (state.musicEnabled) "Bật" else "Tắt", role = Role.Switch) { model.setMusic(!state.musicEnabled) }
                        SheetRow("Giọng", if (state.chapters.firstOrNull { it.id == state.chapterId }?.textPath.isNullOrEmpty()) "Giọng thu sẵn" else "Chọn giọng") {
                            window.openSheet(PlayerSheet.Voice)
                        }
                    }
                    PlayerSheet.Voice -> {
                        if (state.voices.isEmpty()) BasicText("Chưa có giọng cài sẵn. Bạn chọn giọng trong Cài đặt.", style = Abook.type.bodySmall)
                        else LazyColumn {
                            items(state.voices, key = { it.id }, contentType = { "voice" }) { voice ->
                                SheetRow(voice.name, if (voice.id == state.voiceId) "Đang chọn" else "") {
                                    model.setVoice(voice.id); window.closeSheet()
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

private fun sheetTitle(sheet: PlayerSheet) = when (sheet) {
    PlayerSheet.Speed -> "Tốc độ đọc"; PlayerSheet.Sleep -> "Hẹn giờ ngủ"; PlayerSheet.Chapters -> "Chương"
    PlayerSheet.More -> "Tuỳ chọn"; PlayerSheet.Voice -> "Giọng đọc"
}

@Composable
private fun ChoiceCell(label: String, chosen: Boolean, modifier: Modifier, onClick: () -> Unit) {
    Box(modifier.heightIn(min = 56.dp).pressable(onClick = onClick).semantics { selected = chosen }, contentAlignment = Alignment.Center) {
        BasicText(label, style = Abook.type.body.copy(color = if (chosen) Abook.colors.accentText else Abook.colors.text,
            fontWeight = if (chosen) FontWeight.Bold else FontWeight.Normal))
    }
}

@Composable
private fun SheetRow(label: String, value: String, enabled: Boolean = true, role: Role = Role.Button, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = 56.dp).then(if (enabled) Modifier.pressable(role = role, onClick = onClick) else Modifier)
        .semantics { if (!enabled) disabled() }.padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        BasicText(label, Modifier.weight(1f), style = Abook.type.body)
        Spacer(Modifier.width(12.dp))
        RollingLabel(value, Modifier.widthIn(max = 144.dp), Abook.type.bodySmall)
    }
}

@Composable
private fun SleepClock(sleep: PlayerSleep, position: PlayerPosition) {
    var label by remember(sleep) { mutableStateOf(PlayerLabels.sleep(sleep, position.sleepRemainingMs.value, clock = true)) }
    LaunchedEffect(sleep, position) { snapshotFlow { position.sleepRemainingMs.value }.collect {
        label = PlayerLabels.sleep(sleep, it, clock = true)
    } }
    RollingLabel(label, Modifier.padding(bottom = 12.dp), Abook.type.screenTitle)
    if (sleep.kind == SleepKind.Minutes && !sleep.counting)
        BasicText("Đồng hồ cũng tạm dừng.", style = Abook.type.caption)
}
