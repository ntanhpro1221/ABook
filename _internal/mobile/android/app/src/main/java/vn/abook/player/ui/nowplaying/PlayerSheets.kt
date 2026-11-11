package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import vn.abook.player.ui.components.gestureBarPadding
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.IconAction
import vn.abook.player.ui.components.LucideIcon
import vn.abook.player.ui.components.LucidePaths
import vn.abook.player.ui.components.ValuePicker
import vn.abook.player.ui.components.ValueSpecs
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
import vn.abook.player.ui.components.BasicText
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

enum class PlayerSheet { Speed, Sleep, Chapters, More, Voice, Music, Look, Audio }

/** Sheets translate over a fixed player. There is no scale or translation on the underlying screen. */
@Composable
fun PlayerSheets(state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState) {
    val transition = updateTransition(window.sheetOpen, label = "player-sheet")
    val accent = Abook.colors.accent
    val music = model.music
    // Tấm mở từ S.s_them_tuy_chon_a0b4bb6e (Giọng, Nhạc nền): Back về lại tấm ấy, như một trang sâu hơn; tấm mở thẳng thì Back đóng.
    var parent by remember { mutableStateOf<PlayerSheet?>(null) }
    LaunchedEffect(window.sheetOpen) { if (!window.sheetOpen) parent = null }
    LaunchedEffect(window.sheet, window.sheetOpen, state.bookId) {
        if (window.sheetOpen && window.sheet == PlayerSheet.Voice) model.loadVoices()
        // Hàng S.s_nhac_nen_271fb292 cần biết cuốn này có nhạc kiểu gì trước khi hiện giá trị.
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
                .pressable(onClick = window::closeSheet).semantics { contentDescription = S.s_dong_5d54c2a1 })
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
                .gestureBarPadding().padding(horizontal = 20.dp).padding(top = 12.dp, bottom = 20.dp)
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
                    // Bộ chọn giá trị (DESIGN mục 6, chủ sách 09-11): chip tiêu biểu một chạm + kéo / -,+ / gõ số ra mọi tốc độ 0,5-3× bước 0,05.
                    // Đổi là áp ngay, tấm không tự đóng (kéo thước cần tấm đứng yên).
                    PlayerSheet.Speed -> ValuePicker(ValueSpecs.speed, state.rate, { rate -> model.setRate(rate) }, PlayerLabels::rate,
                        S.s_toc_do_doc_3657e59d, "speed_picker", Modifier.padding(bottom = Dim.s8))
                    PlayerSheet.Sleep -> {
                        val options = model.sleepOptions
                        val active = state.sleep.kind != SleepKind.Off
                        // Đang hẹn: còn bao lâu + S.s_copy_4a2a3696181b / S.s_tat_hen_gio_fc8af231. Chưa hẹn mà vừa tắt tiếng (chưa quá 30 phút): mời bật lại đúng mức cũ.
                        if (active) {
                            RowHint(SleepText.heading(state.sleep.kind))
                            SleepClock(state.sleep, model.position)
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(Dim.s16)) {
                                TextAction(SleepText.extendLabel(SleepText.extendMinutes(state.sleep, options)), { model.extendSleep(); window.closeSheet() }, "sleep_extend", align = Alignment.CenterStart)
                                TextAction(S.s_tat_hen_gio_fc8af231, { model.setSleep(SleepKind.Off); window.closeSheet() }, "sleep_off", align = Alignment.CenterStart)
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
                        // Bộ chọn giá trị (DESIGN mục 6, chủ sách 09-11): chip tiêu biểu + chọn tự do 1-240 phút; hàng riêng dưới là "Hết chương này" / "Hết N chương".
                        val minutesNow = state.sleep.kind == SleepKind.Minutes
                        ValuePicker(
                            ValueSpecs.sleepMinutes, (if (minutesNow) state.sleep.minutes else window.lastSleepMinutes).toDouble(),
                            { minutes -> window.lastSleepMinutes = minutes.toInt(); model.setSleep(SleepKind.Minutes, minutes.toInt()) },
                            { minutes -> S.s_0_phut_2596d212(minutes.toInt()) }, S.s_hen_gio_ngu_21073488, "sleep_picker",
                            chipLabel = { minutes -> minutes.toInt().toString() }, current = minutesNow,
                            special = { SleepChapterChoice(state.sleep) { count -> model.setSleep(SleepKind.Chapter, count) } },
                        )
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
                                    RowHint(if (current) S.s_dang_nghe_9310d8cf else PlayerLabels.time(chapter.durationMs))
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
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            vn.abook.player.ui.components.LucideIcon(vn.abook.player.ui.components.LucidePaths.SLIDERS_HORIZONTAL, Abook.colors.text)
                            Spacer(Modifier.width(8.dp))
                            Box(Modifier.weight(1f)) { SheetRow(S.s_copy_c1303271503d, S.s_copy_cc27613e0895) { deeper(PlayerSheet.Audio) } }
                        }
                        if (window.otherPlayers != null) SheetRow(S.s_thiet_bi_phat_c8cfc7a8, S.s_chon_1171ca97) {
                            window.closeSheet()
                            window.otherPlayers?.invoke()
                        }
                        // Nhạc nền của CUỐN NÀY (danh sách, to nhỏ, ghi công) cần cả một tấm; công tắc chung S.s_tu_chon_nhac_nen_a14c52b4 ở Cài đặt.
                        if (music != null) {
                            val ui by music.ui.collectAsState()
                            val book = ui.book.takeIf { ui.bookId == state.bookId }
                            Reveal((book != null && book.kind != MusicKind.None) || (ui.failed && ui.bookId == state.bookId)) {
                                SheetRow(S.s_nhac_nen_271fb292, MusicText.value(book, ui.menu)) { deeper(PlayerSheet.Music) }
                            }
                        }
                        // Dáng chữ chỉ có nghĩa khi có chữ để đọc theo.
                        if (state.readAlongAvailable) Box(Modifier.semantics { contentDescription = S.s_co_chu_va_gian_dong_7dfe48ac }) {
                            SheetRow(S.s_co_chu_d7b231e3, window.look.summary) { deeper(PlayerSheet.Look) }
                        }
                        SheetRow(S.s_giong_doc_11f2548d, if (state.chapters.firstOrNull { it.id == state.chapterId }?.textPath.isNullOrEmpty()) S.s_giong_thu_san_ff3861c7 else S.s_chon_giong_1bc47aed) {
                            deeper(PlayerSheet.Voice)
                        }
                    }
                    PlayerSheet.Music -> if (music != null) MusicPanel(music, state.bookId, state.music)
                    PlayerSheet.Look -> LookPage(window)
                    PlayerSheet.Audio -> AudioFxPage()
                    PlayerSheet.Voice -> {
                        if (state.voices.isEmpty()) BasicText(S.s_may_nay_chua_co_giong_doc_3449f846, style = Abook.type.bodySmall)
                        else VoiceList(state, model, window)
                    }
                } } }
            }
        }
    }
}

/**
 * Tiến độ cả cuốn (phần đã có audio) ở đầu tấm S.s_them_tuy_chon_a0b4bb6e: S.s_copy_c21ecde32b7f.
 * Số chạy theo đồng hồ theo bước 10 giây (một lần dựng lại mỗi 10 giây, chỉ khi tấm đang mở).
 */
@Composable
private fun BookProgressLine(state: NowPlayingState, model: NowPlayingModel) {
    val base = remember(state.chapters, state.chapterId) { PlayerText.heardBase(state.chapters, state.chapterId) }
    val tens by remember(model) { derivedStateOf { model.position.milliseconds.value / 10_000 } }
    if (base.total <= 0) return
    val heard = minOf(base.total, base.before + if (base.inside) tens * 10.0 else 0.0)
    ClockLabel(PlayerText.bookProgress(state.whole, heard, base.total, state.rate, state.ended && state.whole),
        Modifier.fillMaxWidth().padding(bottom = Dim.s8).testTag("book_progress"), style = Abook.type.caption.copy(color = Abook.colors.text2))
}

/**
 * Danh sách giọng của tấm S.s_giong_doc_11f2548d (web: VoiceMenu): chọn một giọng, S.s_thu_77e1c0d9 nghe mẫu từng giọng (đang nghe thì thành S.s_dung_11554138; mẫu hỏng thì một dòng lý do),
 * S.s_them_giong_15d3a618 tới Cài đặt > Giọng đọc, và khi danh sách dài hơn khung thì một viên nhắc S.s_keo_xuong_con_giong_khac_d4bb507b ở đáy (mờ đi khi đã cuộn tới cuối).
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
                            SheetRow(voice.name, if (voice.id == state.voiceId) S.s_dang_chon_ad61dc23 else "") {
                                model.setVoice(voice.id); window.closeSheet()
                            }
                        }
                        if (sampling != null) TextAction(if (playing) S.s_dung_11554138 else S.s_thu_77e1c0d9, {
                            if (playing) sampling.stopSample() else sampling.play(voice.id)
                        }, "voice_try_${voice.id}", Modifier.semantics { contentDescription = (if (playing) S.s_dung_11554138 else S.s_thu_77e1c0d9) + S.s_giong_ded5e045 + voice.name })
                    }
                }
                item(key = "add-voices") {
                    if (window.voiceSettings != null) SheetRow(S.s_them_giong_15d3a618, "", role = Role.Button) {
                        window.closeSheet(); window.voiceSettings?.invoke()
                    }
                }
            }
            BasicText(S.s_keo_xuong_con_giong_khac_d4bb507b, Modifier.align(Alignment.BottomCenter).padding(bottom = Dim.s8).graphicsLayer { alpha = hint; translationY = (1f - hint) * 8.dp.toPx() }
                .background(Abook.colors.panel, RoundedCornerShape(Dim.radiusCover)).padding(horizontal = 10.dp, vertical = 2.dp).testTag("voice_more_hint"),
                style = Abook.type.caption)
        }
        sample.failed?.let { BasicText(it.message, style = Abook.type.caption.copy(color = Abook.colors.danger), modifier = Modifier.padding(top = Dim.s8).testTag("voice_sample_failed")) }
        // S.s_copy_7d00f642cba3 chỉ có với giọng tải về đọc trên máy (chậm hơn tốc độ nghe trên máy yếu).
        val prepare = model.prepare
        if (prepare != null && PrepareText.canPrepare(state.voiceId)) PrepareBlock(state, prepare)
    }
}

private fun sheetTitle(sheet: PlayerSheet) = when (sheet) {
    PlayerSheet.Speed -> S.s_toc_do_doc_3657e59d; PlayerSheet.Sleep -> S.s_hen_gio_ngu_21073488; PlayerSheet.Chapters -> S.s_chuong_2d157977
    PlayerSheet.More -> S.s_them_tuy_chon_a0b4bb6e; PlayerSheet.Voice -> S.s_giong_doc_11f2548d; PlayerSheet.Music -> S.s_nhac_nen_271fb292; PlayerSheet.Look -> S.s_co_chu_d7b231e3; PlayerSheet.Audio -> S.s_copy_c1303271503d
}

/** Tấm S.s_co_chu_d7b231e3 (web: ReaderScreen, bảng cỡ chữ và giãn dòng): năm cỡ, ba mức giãn dòng; đổi là thấy ngay ở chữ Đọc theo và được nhớ. */
@Composable
private fun LookPage(window: NowPlayingWindowState) {
    val look = window.look
    // Bộ chọn giá trị (DESIGN mục 6): chip tiêu biểu + chọn tự do (cỡ 12-40, giãn dòng 1,2-2,4 bước 0,05); hàng gọn như web ReaderScreen.
    ValuePicker(ValueSpecs.readSize, look.size.toDouble(), { size -> window.changeLook(window.look.sized(size.toInt())) },
        { size -> size.toInt().toString() }, S.s_co_chu_d7b231e3, "read_size", dense = true)
    ValuePicker(ValueSpecs.readLeading, look.leading, { leading -> window.changeLook(window.look.spaced(leading)) },
        ReadLook::leadingLabel, S.s_gian_dong_db0409d5, "read_leading", Modifier.padding(top = Dim.s16), dense = true)
}

/** Chapter counts share the same value field, text color and label rhythm as the minutes picker. */
@Composable
private fun SleepChapterChoice(sleep: PlayerSleep, onSet: (Int) -> Unit) {
    var chapters by remember { mutableIntStateOf(if (sleep.kind == SleepKind.Chapter) sleep.minutes.coerceAtLeast(1) else 1) }
    val active = sleep.kind == SleepKind.Chapter && sleep.minutes.coerceAtLeast(1) == chapters
    ValuePicker(ValueSpecs.sleepChapters, chapters.toDouble(), { next ->
        chapters = next.toInt(); vn.abook.player.Feedback.play("toggle"); onSet(chapters)
    }, { it.toInt().toString() }, S.s_so_chuong_6e52dccd, "sleep_chapters", current = active, stepperOnly = true)
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
    // Hẹn theo chương không có đồng hồ để đọc: số lớn là S.s_het_chuong_nay_8ccc288f (web: SleepPicker).
    fun readout(left: Long) = if (sleep.kind == SleepKind.Chapter) (if (sleep.minutes > 1) S.s_het_0_chuong_79433c77(sleep.minutes) else SleepText.CHAPTER_END)
        else PlayerLabels.sleep(sleep, left, clock = true)
    var label by remember(sleep) { mutableStateOf(readout(position.sleepRemainingMs.value)) }
    LaunchedEffect(sleep, position) { snapshotFlow { position.sleepRemainingMs.value }.collect {
        label = readout(it)
    } }
    ClockLabel(label, Modifier.padding(bottom = 12.dp), Abook.type.screenTitle)
    if (sleep.kind == SleepKind.Minutes && !sleep.counting)
        BasicText(S.s_dang_tam_dung_dong_ho_cung_dung_474889f9, style = Abook.type.caption)
}
