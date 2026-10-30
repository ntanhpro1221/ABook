package vn.abook.player.ui.nowplaying

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.updateTransition
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
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
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.music.MusicKind
import vn.abook.player.ui.music.MusicPanel
import vn.abook.player.ui.music.MusicText
import vn.abook.player.ui.components.sheetEdge
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.scrim
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

enum class PlayerSheet { Speed, Sleep, Chapters, More, Voice, Music, Look }

/** Sheets translate over a fixed player. There is no scale or translation on the underlying screen. */
@Composable
fun PlayerSheets(state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState) {
    val transition = updateTransition(window.sheetOpen, label = "player-sheet")
    val accent = Abook.colors.accent
    val music = model.music
    // Tấm mở từ "Thêm tuỳ chọn" (Giọng, Nhạc nền): Back về lại tấm ấy, như một trang sâu hơn; tấm mở thẳng thì Back đóng.
    var parent by remember { mutableStateOf<PlayerSheet?>(null) }
    LaunchedEffect(window.sheetOpen) { if (!window.sheetOpen) parent = null }
    LaunchedEffect(window.sheet, window.sheetOpen, state.bookId) {
        if (window.sheetOpen && window.sheet == PlayerSheet.Voice) model.loadVoices()
        // Hàng "Nhạc nền" cần biết cuốn này có nhạc kiểu gì trước khi hiện giá trị.
        if (window.sheetOpen && window.sheet == PlayerSheet.More) music?.open(state.bookId)
    }
    fun deeper(sheet: PlayerSheet) { parent = window.sheet; window.openSheet(sheet) }
    BackHandler(enabled = window.sheetOpen) {
        val back = parent
        if (back != null && back != window.sheet) { parent = null; window.openSheet(back) } else window.closeSheet()
    }
    // Vạch kéo là thật: tấm theo ngón tay xuống, thả quá 1/4 chiều cao hay vuốt nhanh thì đóng, không thì về chỗ.
    val drag = remember { androidx.compose.animation.core.Animatable(0f) }
    val scope = rememberCoroutineScope()
    var sheetHeight by remember { mutableIntStateOf(1) }
    LaunchedEffect(window.sheetOpen) { if (window.sheetOpen) drag.snapTo(0f) }
    val scrim = Abook.colors.scrim
    // Nền tối đậm dần cùng nhịp tấm trượt lên, nhạt dần khi tấm xuống, và nhạt theo ngón tay khi kéo tấm - không bật/tắt.
    val scrimShown by transition.animateFloat(
        transitionSpec = { if (targetState) tween(MotionMs.SLOW) else tween(MotionMs.SLOW_OUT) }, label = "player-sheet-scrim",
    ) { if (it) 1f else 0f }
    BoxWithConstraints(Modifier.fillMaxSize()) {
        if (transition.currentState || transition.targetState) {
            Box(Modifier.fillMaxSize().drawBehind { drawRect(scrim, alpha = scrimShown * (1f - drag.value / sheetHeight).coerceIn(0f, 1f)) }
                .pressable(onClick = window::closeSheet).semantics { contentDescription = "Đóng" })
        }
        transition.AnimatedVisibility(
            visible = { it }, enter = slideInVertically(tween(MotionMs.SLOW)) { it },
            exit = slideOutVertically(tween(MotionMs.SLOW_OUT)) { it },
            modifier = Modifier.align(Alignment.BottomCenter),
        ) {
            Column(Modifier.fillMaxWidth().heightIn(max = maxHeight * 0.82f)
                .onSizeChanged { sheetHeight = it.height.coerceAtLeast(1) }
                .graphicsLayer { translationY = drag.value }
                .clip(RoundedCornerShape(topStart = Dim.radiusSheet, topEnd = Dim.radiusSheet)).background(Abook.colors.panel)
                .then(if (Abook.colors.dark) Modifier.sheetEdge(Abook.colors.line) else Modifier)
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
                        .background(Abook.colors.line, CircleShape))
                    Row(Modifier.fillMaxWidth().height(64.dp), verticalAlignment = Alignment.CenterVertically) {
                        RollingLabel(sheetTitle(window.sheet), style = Abook.type.sectionTitle)
                    }
                }
                SheetPages(window.sheet, { it.ordinal }, "player_sheet_pages") { shown -> Column(Modifier.fillMaxWidth()) { when (shown) {
                    PlayerSheet.Speed -> {
                        for (row in PlayerLabels.rates.chunked(3)) Row(Modifier.fillMaxWidth()) {
                            for (rate in row) ChoiceCell(PlayerLabels.rate(rate), rate == state.rate, Modifier.weight(1f)) {
                                model.setRate(rate); window.closeSheet()
                            }
                            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
                        }
                    }
                    PlayerSheet.Sleep -> {
                        val options = model.sleepOptions
                        val active = state.sleep.kind != SleepKind.Off
                        // Đang hẹn: còn bao lâu + "+N phút" / "Tắt hẹn giờ". Chưa hẹn mà vừa tắt tiếng (chưa quá 30 phút): mời bật lại đúng mức cũ.
                        if (active) {
                            RowHint(SleepText.heading(state.sleep.kind))
                            SleepClock(state.sleep, model.position)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s16)) {
                                TextAction(SleepText.extendLabel(options.extendMinutes), { model.extendSleep(); window.closeSheet() }, "sleep_extend", align = Alignment.CenterStart)
                                TextAction("Tắt hẹn giờ", { model.setSleep(SleepKind.Off); window.closeSheet() }, "sleep_off", align = Alignment.CenterStart)
                            }
                        } else {
                            val now = remember(window.sheetOpen) { System.currentTimeMillis() }
                            if (SleepText.recentlyStopped(state.sleep, now)) {
                                BasicText(SleepText.stoppedAt(state.sleep.stoppedAtMs), style = Abook.type.body, modifier = Modifier.testTag("sleep_stopped"))
                                TextAction(SleepText.restart(window.lastSleepMinutes), {
                                    model.setSleep(SleepKind.Minutes, window.lastSleepMinutes); window.closeSheet()
                                }, "sleep_again", align = Alignment.CenterStart)
                            }
                        }
                        RowHint(SleepText.gridHeading(active), Modifier.padding(top = Dim.s8))
                        for (row in PlayerLabels.sleepMinutes.chunked(3)) Row(Modifier.fillMaxWidth()) {
                            for (minutes in row) ChoiceCell("$minutes phút", state.sleep.kind == SleepKind.Minutes && state.sleep.minutes == minutes, Modifier.weight(1f)) {
                                window.lastSleepMinutes = minutes
                                model.setSleep(SleepKind.Minutes, minutes); window.closeSheet()
                            }
                        }
                        SheetRow("Hết chương này", if (state.sleep.kind == SleepKind.Chapter) "Đang chọn" else "") {
                            model.setSleep(SleepKind.Chapter); window.closeSheet()
                        }
                        BasicText(SleepText.note(options, model.hadNight), style = Abook.type.caption.copy(color = Abook.colors.text2),
                            modifier = Modifier.padding(top = Dim.s8).testTag("sleep_note"))
                    }
                    PlayerSheet.Chapters -> {
                        val chapterList = rememberLazyListState()
                        LazyColumn(Modifier.fillMaxWidth().fadeEdges(chapterList), state = chapterList) {
                            items(state.chapters, key = { it.id }, contentType = { "chapter" }) { chapter ->
                                val current = chapter.id == state.chapterId
                                Column(Modifier.fillMaxWidth().pressable { model.jump(chapter.id); window.closeSheet() }
                                    .semantics { selected = current }.padding(vertical = 12.dp)) {
                                    BasicText(chapter.title, style = Abook.type.body.copy(color = if (current) Abook.colors.accentText else Abook.colors.text))
                                    RowHint(if (current) "Đang nghe" else PlayerLabels.time(chapter.durationMs))
                                    if (current) Box(Modifier.fillMaxWidth().height(2.dp).drawBehind {
                                        val fraction = if (state.durationMs > 0) model.position.milliseconds.value.toFloat() / state.durationMs else 0f
                                        drawRect(accent, size = androidx.compose.ui.geometry.Size(size.width * fraction.coerceIn(0f, 1f), size.height))
                                    })
                                }
                            }
                        }
                    }
                    PlayerSheet.More -> {
                        BookProgressLine(state, model)
                        if (window.otherPlayers != null) SheetRow("Thiết bị phát", "Chọn") {
                            window.closeSheet()
                            window.otherPlayers?.invoke()
                        }
                        // Nhạc nền của CUỐN NÀY (danh sách, to nhỏ, ghi công) cần cả một tấm; công tắc chung "Tự chọn nhạc nền" ở Cài đặt.
                        if (music != null) {
                            val ui by music.ui.collectAsState()
                            val book = ui.book.takeIf { ui.bookId == state.bookId }
                            Reveal((book != null && book.kind != MusicKind.None) || (ui.failed && ui.bookId == state.bookId)) {
                                SheetRow("Nhạc nền", MusicText.value(book, ui.menu)) { deeper(PlayerSheet.Music) }
                            }
                        }
                        // Dáng chữ chỉ có nghĩa khi có chữ để đọc theo.
                        if (state.readAlongAvailable) Box(Modifier.semantics { contentDescription = "Cỡ chữ và giãn dòng" }) {
                            SheetRow("Cỡ chữ", window.look.summary) { deeper(PlayerSheet.Look) }
                        }
                        SheetRow("Giọng đọc", if (state.chapters.firstOrNull { it.id == state.chapterId }?.textPath.isNullOrEmpty()) "Giọng thu sẵn" else "Chọn giọng") {
                            deeper(PlayerSheet.Voice)
                        }
                    }
                    PlayerSheet.Music -> if (music != null) MusicPanel(music, state.bookId, state.music)
                    PlayerSheet.Look -> LookPage(window)
                    PlayerSheet.Voice -> {
                        if (state.voices.isEmpty()) BasicText("Máy này chưa có giọng đọc.", style = Abook.type.bodySmall)
                        else VoiceList(state, model, window)
                    }
                } } }
            }
        }
    }
}

/**
 * Tiến độ cả cuốn (phần đã có audio) ở đầu tấm "Thêm tuỳ chọn": "Đã nghe 42% cả cuốn · còn khoảng 2 giờ 32 phút ở tốc độ 1,5×".
 * Số chạy theo đồng hồ theo bước 10 giây (một lần dựng lại mỗi 10 giây, chỉ khi tấm đang mở).
 */
@Composable
private fun BookProgressLine(state: NowPlayingState, model: NowPlayingModel) {
    val base = remember(state.chapters, state.chapterId) { PlayerText.heardBase(state.chapters, state.chapterId) }
    val tens by remember(model) { derivedStateOf { model.position.milliseconds.value / 10_000 } }
    if (base.total <= 0) return
    val heard = minOf(base.total, base.before + if (base.inside) tens * 10.0 else 0.0)
    BasicText(PlayerText.bookProgress(state.whole, heard, base.total, state.rate, state.ended && state.whole),
        Modifier.fillMaxWidth().padding(bottom = Dim.s8).testTag("book_progress"), style = Abook.type.caption.copy(color = Abook.colors.text2))
}

/**
 * Danh sách giọng của tấm "Giọng đọc" (web: VoiceMenu): chọn một giọng, "Thử" nghe mẫu từng giọng (đang nghe thì thành "Dừng"; mẫu hỏng thì một dòng lý do),
 * "Thêm giọng" tới Cài đặt > Giọng đọc, và khi danh sách dài hơn khung thì một viên nhắc "Kéo xuống còn giọng khác" ở đáy (mờ đi khi đã cuộn tới cuối).
 */
@Composable
private fun VoiceList(state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState) {
    val voiceList = rememberLazyListState()
    val sampling = model.voice
    val sample by (sampling?.sample ?: remember { kotlinx.coroutines.flow.MutableStateFlow(vn.abook.player.ui.voice.SampleUi()) }).collectAsState()
    // Đóng tấm là thôi nghe thử: mẫu không tự kêu tiếp sau khi người nghe đã chọn xong.
    DisposableEffect(sampling) { onDispose { sampling?.stopSample() } }
    val more by remember { derivedStateOf { voiceList.canScrollForward } }
    val hint by androidx.compose.animation.core.animateFloatAsState(if (more) 1f else 0f, tween(MotionMs.MEDIUM), label = "voice-more")
    Column(Modifier.fillMaxWidth()) {
        Box(Modifier.weight(1f, fill = false)) {
            LazyColumn(Modifier.fadeEdges(voiceList), state = voiceList) {
                items(state.voices, key = { it.id }, contentType = { "voice" }) { voice ->
                    val playing = sample.playing == voice.id
                    Row(Modifier.fillMaxWidth().testTag("voice_${voice.id}"), verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.weight(1f)) {
                            SheetRow(voice.name, if (voice.id == state.voiceId) "Đang chọn" else "") {
                                model.setVoice(voice.id); window.closeSheet()
                            }
                        }
                        if (sampling != null) TextAction(if (playing) "Dừng" else "Thử", {
                            if (playing) sampling.stopSample() else sampling.play(voice.id)
                        }, "voice_try_${voice.id}", Modifier.semantics { contentDescription = (if (playing) "Dừng" else "Thử") + " giọng " + voice.name })
                    }
                }
                item(key = "add-voices") {
                    if (window.voiceSettings != null) SheetRow("Thêm giọng", "", role = Role.Button) {
                        window.closeSheet(); window.voiceSettings?.invoke()
                    }
                }
            }
            BasicText("Kéo xuống còn giọng khác", Modifier.align(Alignment.BottomCenter).padding(bottom = Dim.s8).graphicsLayer { alpha = hint; translationY = (1f - hint) * 8.dp.toPx() }
                .background(Abook.colors.panel, RoundedCornerShape(Dim.radiusCover)).padding(horizontal = 10.dp, vertical = 2.dp).testTag("voice_more_hint"),
                style = Abook.type.caption)
        }
        sample.failed?.let { BasicText(it.message, style = Abook.type.caption.copy(color = Abook.colors.danger), modifier = Modifier.padding(top = Dim.s8).testTag("voice_sample_failed")) }
        // "Làm trước" chỉ có với giọng tải về đọc trên máy (chậm hơn tốc độ nghe trên máy yếu).
        val prepare = model.prepare
        if (prepare != null && PrepareText.canPrepare(state.voiceId)) PrepareBlock(state, prepare)
    }
}

private fun sheetTitle(sheet: PlayerSheet) = when (sheet) {
    PlayerSheet.Speed -> "Tốc độ đọc"; PlayerSheet.Sleep -> "Hẹn giờ ngủ"; PlayerSheet.Chapters -> "Chương"
    PlayerSheet.More -> "Thêm tuỳ chọn"; PlayerSheet.Voice -> "Giọng đọc"; PlayerSheet.Music -> "Nhạc nền"; PlayerSheet.Look -> "Cỡ chữ"
}

/** Tấm "Cỡ chữ" (web: ReaderScreen, bảng cỡ chữ và giãn dòng): năm cỡ, ba mức giãn dòng; đổi là thấy ngay ở chữ Đọc theo và được nhớ. */
@Composable
private fun LookPage(window: NowPlayingWindowState) {
    val look = window.look
    Row(Modifier.fillMaxWidth()) {
        for (size in ReadLook.SIZES) ChoiceCell("$size", size == look.size, Modifier.weight(1f), "Cỡ chữ $size") { window.changeLook(look.sized(size)) }
    }
    RowHint("Giãn dòng")
    Row(Modifier.fillMaxWidth()) {
        for (leading in ReadLook.LEADINGS) ChoiceCell(ReadLook.leadingLabel(leading), leading == look.leading, Modifier.weight(1f),
            "Giãn dòng " + ReadLook.leadingLabel(leading)) { window.changeLook(look.spaced(leading)) }
    }
}

@Composable
private fun ChoiceCell(label: String, chosen: Boolean, modifier: Modifier, description: String? = null, onClick: () -> Unit) {
    Box(modifier.heightIn(min = 56.dp).pressable(onClick = onClick).semantics { selected = chosen; if (description != null) contentDescription = description }, contentAlignment = Alignment.Center) {
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
    // Hẹn theo chương không có đồng hồ để đọc: số lớn là "hết chương này" (web: SleepPicker).
    fun readout(left: Long) = if (sleep.kind == SleepKind.Chapter) SleepText.CHAPTER_END else PlayerLabels.sleep(sleep, left, clock = true)
    var label by remember(sleep) { mutableStateOf(readout(position.sleepRemainingMs.value)) }
    LaunchedEffect(sleep, position) { snapshotFlow { position.sleepRemainingMs.value }.collect {
        label = readout(it)
    } }
    ClockLabel(label, Modifier.padding(bottom = 12.dp), Abook.type.screenTitle)
    if (sleep.kind == SleepKind.Minutes && !sleep.counting)
        BasicText("Đang tạm dừng - đồng hồ cũng dừng.", style = Abook.type.caption)
}
