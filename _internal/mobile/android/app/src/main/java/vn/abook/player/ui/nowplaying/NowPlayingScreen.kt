package vn.abook.player.ui.nowplaying

import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.launch
import vn.abook.player.Playback
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

@Composable
fun NowPlayingScreen(
    state: NowPlayingState, model: NowPlayingModel, window: NowPlayingWindowState,
    parts: SharedPlayerParts, windowProgress: State<Float>, modifier: Modifier = Modifier,
) {
    val background = rememberPlayerBackground(state.cover)
    val scope = rememberCoroutineScope()
    val mode = animateFloatAsState(if (window.reading) 1f else 0f, tween(MotionMs.SLOW), label = "reading-mode")
    var controlsDimmed by remember { mutableStateOf(false) }
    val dim = animateFloatAsState(if (controlsDimmed && window.reading) 0.42f else 1f, tween(MotionMs.FAST), label = "controls-visibility")
    LaunchedEffect(window.reading, state.bookId, state.chapterId) {
        if (window.reading) model.loadReadAlong()
    }
    // Lời nhắc ở đầu chữ cần biết máy có giọng đọc không (chương đọc to).
    LaunchedEffect(window.reading) { if (window.reading) model.loadVoices() }
    DisposableEffect(model, window.reading) {
        model.setReadAlongActive(window.reading)
        onDispose { model.setReadAlongActive(false) }
    }
    // Giọng máy đọc đoạn đầu mà chờ lâu hơn ~1,5 giây mới nói "Đang chuẩn bị giọng đọc" (đệm một nhịp giữa câu không được nháy chữ).
    val waiting = state.playing && state.buffering
    var waited by remember { mutableStateOf(false) }
    LaunchedEffect(waiting) {
        waited = false
        if (waiting) { kotlinx.coroutines.delay(PlayerText.PREPARING_AFTER_MS); waited = true }
    }
    val preparing = waiting && state.speaking && waited
    val toggleLabel = PlayerText.toggleLabel(state.playing, waiting && (!state.speaking || waited), state.speaking)
    val subtitle = when {
        preparing -> PlayerText.PREPARING_VOICE
        state.ended && !state.whole -> PlayerText.CAUGHT_UP_HEAD
        else -> state.bookTitle
    }
    val panel = Abook.colors.panel
    // The tint follows the window's progress, so it is drawn by this outer node (inside the container's moving layer); everything else lives in the inner layer,
    // whose recorded drawing stays untouched while the window moves.
    Box(modifier.drawBehind { drawRect(lerp(panel, background.value, windowProgress.value)) }) {
      Box(Modifier.fillMaxSize().graphicsLayer {}) {
        Column(Modifier.fillMaxSize().systemBarsPadding().padding(horizontal = 20.dp).padding(bottom = 12.dp)) {
            val setReading = { on: Boolean -> if (on != window.reading) { window.reading = on; controlsDimmed = false } }
            Row(Modifier.fillMaxWidth().height(56.dp).playerReveal(windowProgress)
                .dismissPlayerOnDrag(window, window.reading && !window.sheetOpen),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                GlyphButton("Thu nhỏ", "⌄", window::close, Modifier.testTag("collapse_player"))
                // Đọc theo là một chế độ của chính cửa sổ này, nên công tắc chế độ nằm ở thanh trên của cửa sổ - không phải một nút hành động ở đáy.
                if (state.readAlongAvailable) PlayerModeSwitch(mode, setReading)
                else BasicText("ĐANG NGHE", style = Abook.type.caption)
                GlyphButton("Thêm tuỳ chọn", "⋯", { window.openSheet(PlayerSheet.More) }, Modifier.testTag("player_more"))
            }
            // Both modes occupy this same fixed weight. Transport is outside it and never changes coordinates.
            // Nghe: bìa lớn ở trên, tên chương + tên sách ở dưới. Đọc theo: chính bìa ấy thu về ô 48 dp, chính hai dòng tên trượt lên
            // đứng cạnh nó (thu nhỏ, vẫn xuống dòng, không mất), chữ chương mở ra bên dưới. Không phần nào mờ đi rồi biến mất.
            // Ô chữ có mặt khi đang đọc hoặc còn đang chuyển cảnh; chỉ đổi khi qua mốc 0, không recompose theo từng khung.
            val textShown by remember { derivedStateOf { mode.value > 0f } }
            Layout(modifier = Modifier.weight(1f).fillMaxWidth(), content = {
                Box(Modifier.fillMaxSize()) {
                  if (window.reading || textShown) {
                    val reading by model.readAlong.collectAsState()
                    val hint = ReadHint.of(state.speaking, state.voices.isNotEmpty(), reading.paragraphs.any { it.timed }, window.look.tapped)
                    val nextTitle = if (state.hasNext) state.chapters.getOrNull(state.chapters.indexOfFirst { it.id == state.chapterId } + 1)?.title else null
                    ReadAlongPane(reading, model.position, Modifier.fillMaxSize(),
                        onManualScroll = { controlsDimmed = true }, onTap = { controlsDimmed = false },
                        onRetry = { controlsDimmed = false; scope.launch { model.loadReadAlong() } },
                        look = window.look, hint = hint,
                        onListen = { ms -> window.changeLook(window.look.copy(tapped = true)); model.listenFrom(ms) },
                        nextTitle = nextTitle, onNext = model::next)
                  }
                }
                // Chạm bìa cũng đổi chế độ: bìa lớn -> đọc theo, bìa nhỏ -> về nghe. Bìa là phần tử chung (bay bằng lớp vẽ, xem SharedPlayerParts);
                // ở chế độ đọc theo nó không nhận chạm (để không nuốt chạm vào chữ), ô 48 dp riêng phía dưới nhận thay.
                PlayerCover(state.cover, state.bookTitle, parts.element(NowPlayingPart.Cover, Modifier
                    .testTag("player_cover")
                    .then(if (state.readAlongAvailable && !window.reading) Modifier.pressable { setReading(true) } else Modifier)))
                Column(Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                    RollingLabel(state.chapterTitle, parts.element(NowPlayingPart.Chapter),
                        Abook.type.bodyStrong.copy(fontSize = 20.sp, lineHeight = 28.sp, fontWeight = FontWeight.Bold))
                    Spacer(Modifier.height(4.dp))
                    RollingLabel(subtitle, parts.element(NowPlayingPart.Book), Abook.type.bodySmall)
                }
                Box(Modifier.testTag("player_cover_small").then(if (window.reading) Modifier
                    .pressable { setReading(false) }.semantics { contentDescription = "Về chế độ nghe" } else Modifier))
            }) { measurables, constraints ->
                val width = constraints.maxWidth
                val height = constraints.maxHeight
                val thumb = 48.dp.roundToPx()
                val gap = 12.dp.roundToPx()
                val titles = measurables[2].measure(Constraints(maxWidth = width, maxHeight = height))
                val coverSide = minOf(width, (height - titles.height - 24.dp.roundToPx()).coerceAtLeast(1), 320.dp.roundToPx())
                val cover = measurables[1].measure(Constraints.fixed(coverSide, coverSide))
                // Tên trong đầu trang đọc theo = cùng khối chữ thu theo một tỉ lệ (20 sp -> 16 sp), vừa phần bề ngang còn lại cạnh bìa nhỏ.
                val titleScale = minOf(0.8f, (width - thumb - gap).toFloat() / width)
                val header = maxOf(thumb, (titles.height * titleScale).toInt())
                val textTop = header + gap
                val text = measurables[0].measure(Constraints.fixed(width, (height - textTop).coerceAtLeast(0)))
                val thumbTarget = measurables[3].measure(Constraints.fixed(thumb, thumb))
                val coverX = (width - coverSide) / 2
                // Bìa nằm giữa khoảng trống phía trên khối tên, không dính trần để lại một hố giữa bìa và tên.
                val coverY = ((height - titles.height - coverSide) / 2).coerceAtLeast(0)
                val titlesY = height - titles.height
                layout(width, height) {
                    // Mép trên của chữ bám mép dưới của khối bìa + tên đang thu lại: chữ trượt lên từ đáy, không bao giờ nằm dưới bìa hay tên.
                    text.placeWithLayer(0, textTop) {
                        val p = mode.value
                        val coverBottom = coverY * (1f - p) + coverSide * (1f + (thumb.toFloat() / coverSide - 1f) * p)
                        val titlesTop = titlesY * (1f - p) + (header - titles.height * titleScale).coerceAtLeast(0f) / 2f * p
                        val titlesBottom = titlesTop + titles.height * (1f + (titleScale - 1f) * p)
                        translationY = maxOf(coverBottom, titlesBottom) + gap * p - textTop
                        // The text is cut at this area's edges (not the area itself: the cover and the titles fly in from the mini bar, outside it).
                        clip = true
                        shape = PlayerTextArea(-(textTop + translationY), height - textTop - translationY)
                    }
                    cover.placeWithLayer(coverX, coverY) {
                        val p = mode.value
                        transformOrigin = TransformOrigin(0f, 0f)
                        scaleX = 1f + (thumb.toFloat() / coverSide - 1f) * p; scaleY = scaleX
                        translationX = -coverX * p
                        translationY = -coverY * p
                    }
                    thumbTarget.place(0, 0)
                    titles.placeWithLayer(0, titlesY) {
                        val p = mode.value
                        transformOrigin = TransformOrigin(0f, 0f)
                        scaleX = 1f + (titleScale - 1f) * p; scaleY = scaleX
                        translationX = (thumb + gap) * p
                        translationY = (-titlesY + (header - titles.height * titleScale).coerceAtLeast(0f) / 2f) * p
                    }
                }
            }
            Column(Modifier.fillMaxWidth().pointerInput(Unit) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    controlsDimmed = false
                    waitForUpOrCancellation()
                }
            }.graphicsLayer {
                alpha = dim.value
                scaleX = 0.98f + dim.value * 0.02f; scaleY = scaleX
            }) {
                PlayerSeekBar(state.durationMs, model.position, model::seek, Modifier.playerReveal(windowProgress)) {
                    ReturnChip(state.returnAvailable, state.returnSerial, model::returnToPreviousPlace)
                }
                Row(Modifier.fillMaxWidth().height(88.dp).testTag("transport"),
                    verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceEvenly) {
                    GlyphButton("Chương trước", "|‹", model::previous, Modifier.playerReveal(windowProgress))
                    GlyphButton("Lùi 15 giây", "↶15", { model.skip(-Playback.SKIP_SECONDS) }, Modifier.playerReveal(windowProgress))
                    PlayMorph(state.playing, model::toggle, parts.element(NowPlayingPart.Play), description = toggleLabel)
                    GlyphButton("Tới 15 giây", "15↷", { model.skip(Playback.SKIP_SECONDS) }, Modifier.playerReveal(windowProgress))
                    // Chương cuối: nút mờ và nói đó là chương cuối; chương sau chưa có audio: nói vì sao (nút vẫn bấm được, như web).
                    GlyphButton(PlayerText.nextLabel(state.hasNext, state.hasNext || state.moreChapters), "›|", model::next,
                        Modifier.playerReveal(windowProgress), dimmed = !state.hasNext && !state.moreChapters)
                }
                // Các ô bằng nhau (ba, hoặc bốn khi máy có PiP): tâm ở giữa mỗi phần bề ngang dù nhãn dài ngắn khác nhau.
                Row(Modifier.fillMaxWidth().playerReveal(windowProgress)) {
                    PlayerAction("Tốc độ", PlayerLabels.rate(state.rate), { window.openSheet(PlayerSheet.Speed) }, Modifier.weight(1f).testTag("player_speed"))
                    SleepAction(state.sleep, model.position, { window.openSheet(PlayerSheet.Sleep) }, Modifier.weight(1f))
                    PlayerAction("Chương", "☷", { window.openSheet(PlayerSheet.Chapters) }, Modifier.weight(1f).testTag("player_chapters"))
                    window.miniWindow?.let { enter -> PlayerAction("Cửa sổ mini", MINI_WINDOW_GLYPH, enter, Modifier.weight(1f).testTag("player_mini")) }
                }
            }
            SleepNotice(state, model, Modifier.playerReveal(windowProgress))
            PlayerNoteLine(model, Modifier.playerReveal(windowProgress))
            EndNotice(state, model, window, Modifier.playerReveal(windowProgress))
            // Gạt lời báo đi tới lần lỗi mới (web: "Đóng lời báo"): người đang làm việc khác không bị nó đè mãi.
            var dismissed by remember(state.error) { mutableStateOf(false) }
            if (state.error.isNotBlank() && !dismissed) PlayerAlert(state, model, window, Modifier.playerReveal(windowProgress), onDismiss = { dismissed = true })
        }
        PlayerSheets(state, model, window)
      }
    }
}

@Composable
fun GlyphButton(label: String, glyph: String, onClick: () -> Unit, modifier: Modifier = Modifier, dimmed: Boolean = false) {
    val view = LocalView.current
    Box(modifier.size(48.dp).then(if (dimmed) Modifier.alpha(0.4f) else Modifier).pressable {
        view.performHapticFeedback(android.view.HapticFeedbackConstants.CONTEXT_CLICK)
        onClick()
    }.semantics { contentDescription = label }, contentAlignment = Alignment.Center) {
        PlayerGlyph(glyph)
    }
}

@Composable
private fun SleepAction(sleep: PlayerSleep, position: PlayerPosition, onClick: () -> Unit, modifier: Modifier = Modifier) {
    var label by remember(sleep) { mutableStateOf(PlayerLabels.sleep(sleep, position.sleepRemainingMs.value)) }
    LaunchedEffect(sleep, position) {
        snapshotFlow { position.sleepRemainingMs.value }.collect { label = PlayerLabels.sleep(sleep, it) }
    }
    PlayerAction("Hẹn giờ", label.takeIf { sleep.kind != SleepKind.Off } ?: "◷", onClick, modifier.testTag("player_sleep"), clock = true)
}

@Composable
fun PlayerSeekBar(durationMs: Long, position: PlayerPosition, onSeek: (Long) -> Unit, modifier: Modifier = Modifier, center: @Composable () -> Unit = {}) {
    val colors = Abook.colors
    val dragging = remember { mutableStateOf(false) }
    val dragged = remember { mutableLongStateOf(0L) }
    val view = LocalView.current
    var lastTick by remember { mutableLongStateOf(-1) }
    var seconds by remember { mutableLongStateOf(0L) }
    LaunchedEffect(position) { snapshotFlow { position.milliseconds.value / 1000 }.distinctUntilChanged().collect { seconds = it } }
    Column(modifier.fillMaxWidth()) {
        Canvas(Modifier.fillMaxWidth().height(44.dp).testTag("player_seek")
            .semantics {
                contentDescription = "Vị trí trong chương"
                progressBarRangeInfo = ProgressBarRangeInfo((seconds * 1000).toFloat(), 0f..durationMs.coerceAtLeast(1).toFloat())
                setProgress { value -> onSeek(value.toLong().coerceIn(0, durationMs)); true }
            }
            .pointerInput(durationMs) {
                fun seekAt(x: Float): Long = ((x / size.width).coerceIn(0f, 1f) * durationMs).toLong()
                detectTapGestures { onSeek(seekAt(it.x)) }
            }
            .pointerInput(durationMs) {
                detectDragGestures(
                    onDragStart = { dragging.value = true; dragged.longValue = ((it.x / size.width).coerceIn(0f, 1f) * durationMs).toLong() },
                    onDrag = { change, _ ->
                        change.consume()
                        dragged.longValue = ((change.position.x / size.width).coerceIn(0f, 1f) * durationMs).toLong()
                        val tick = dragged.longValue / 15_000
                        if (tick != lastTick) { lastTick = tick; view.performHapticFeedback(android.view.HapticFeedbackConstants.CLOCK_TICK) }
                    },
                    onDragEnd = { onSeek(dragged.longValue); dragging.value = false },
                    onDragCancel = { dragging.value = false },
                )
            }) {
            val ms = if (dragging.value) dragged.longValue else position.milliseconds.value
            val fraction = if (durationMs > 0) (ms.toFloat() / durationMs).coerceIn(0f, 1f) else 0f
            val y = size.height / 2
            drawLine(colors.line, Offset(0f, y), Offset(size.width, y), 3.dp.toPx(), StrokeCap.Round)
            drawLine(colors.accent, Offset(0f, y), Offset(size.width * fraction, y), 3.dp.toPx(), StrokeCap.Round)
            drawCircle(colors.accent, 5.dp.toPx(), Offset(size.width * fraction, y))
        }
        // Isolated second-resolution labels. The frame clock never recomposes the transport or chapter.
        // Hàng giờ cao cố định: chip ở giữa hiện / ẩn không bao giờ đẩy hàng nút phát.
        Box(Modifier.fillMaxWidth().height(32.dp)) {
            ClockLabel(PlayerLabels.time(seconds * 1000), Modifier.align(Alignment.TopStart).testTag("time_elapsed"), style = Abook.type.caption)
            Box(Modifier.align(Alignment.TopCenter)) { center() }
            ClockLabel("−" + PlayerLabels.time(durationMs - seconds * 1000), Modifier.align(Alignment.TopEnd).testTag("time_left"), style = Abook.type.caption)
        }
    }
}

/**
 * Công tắc hai chế độ của cửa sổ: "Nghe" / "Đọc theo". Hai ô bằng nhau; viên chỉ báo trượt theo đúng tiến độ của phép đổi bố cục
 * ([mode] 0 -> 1) và màu chữ đổi theo cùng tiến độ ấy - một chuyển động, đọc ở pha vẽ, không recompose mỗi khung.
 */
@Composable
fun PlayerModeSwitch(mode: State<Float>, onSelect: (Boolean) -> Unit, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val style = Abook.type.label.copy(textAlign = androidx.compose.ui.text.style.TextAlign.Center)
    Layout(modifier = modifier.height(36.dp).testTag("player_mode")
        .drawBehind {
            val corner = size.height / 2
            val inset = 3.dp.toPx()
            val segment = size.width / 2
            drawRoundRect(colors.bgSunken, cornerRadius = androidx.compose.ui.geometry.CornerRadius(corner))
            drawRoundRect(colors.panel, Offset(inset + segment * mode.value, inset),
                androidx.compose.ui.geometry.Size(segment - inset * 2, size.height - inset * 2),
                androidx.compose.ui.geometry.CornerRadius(corner - inset))
        },
        content = {
            for ((index, label) in listOf("Nghe", "Đọc theo").withIndex()) {
                val reading = index == 1
                Box(Modifier
                    .pressable(role = Role.Tab) { onSelect(reading) }
                    .semantics { selected = (mode.value >= 0.5f) == reading }
                    .testTag(if (reading) "mode_read" else "mode_listen"),
                    contentAlignment = Alignment.Center) {
                    BasicText(label, Modifier.padding(horizontal = 16.dp), style = style,
                        color = { lerp(colors.text3, colors.text, if (reading) mode.value else 1f - mode.value) })
                }
            }
        }) { measurables, constraints ->
        val segment = measurables.maxOf { it.maxIntrinsicWidth(constraints.maxHeight) }
            .coerceAtMost(constraints.maxWidth / 2)
        val placeables = measurables.map { it.measure(Constraints.fixed(segment, constraints.maxHeight)) }
        layout(segment * 2, constraints.maxHeight) {
            placeables.forEachIndexed { i, p -> p.place(segment * i, 0) }
        }
    }
}

/**
 * "Về chỗ cũ": ngay sau khi bạn tua / nhảy, nằm đúng chỗ vừa thao tác (giữa hàng giờ dưới thanh tua) trong 10 giây - không phải một hàng tắt sẵn
 * trong menu "…". Vào / ra bằng trượt dọc qua khe cắt.
 */
@Composable
private fun ReturnChip(available: Boolean, serial: Int, onReturn: () -> Unit) {
    var shown by remember { mutableStateOf(false) }
    LaunchedEffect(available, serial) {
        shown = available
        if (available) { kotlinx.coroutines.delay(10_000); shown = false }
    }
    Box(Modifier.clipToBounds()) {
        androidx.compose.animation.AnimatedVisibility(shown,
            enter = androidx.compose.animation.slideInVertically(tween(MotionMs.MEDIUM)) { it },
            exit = androidx.compose.animation.slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { it }) {
            BasicText("Về chỗ vừa nghe", Modifier
                .background(Abook.colors.accentSoft, RoundedCornerShape(Dim.radiusCover))
                .pressable { shown = false; onReturn() }
                .testTag("return_place")
                .padding(horizontal = 14.dp, vertical = 6.dp),
                style = Abook.type.caption.copy(color = Abook.colors.accentText, fontWeight = FontWeight.Medium))
        }
    }
}

/** The read-along text's visible band, in the text's own coordinates (it slides under the header and over the transport; nothing may show outside the band). */
private data class PlayerTextArea(val top: Float, val bottom: Float) : androidx.compose.ui.graphics.Shape {
    override fun createOutline(size: androidx.compose.ui.geometry.Size, layoutDirection: androidx.compose.ui.unit.LayoutDirection, density: androidx.compose.ui.unit.Density) =
        androidx.compose.ui.graphics.Outline.Rectangle(androidx.compose.ui.geometry.Rect(0f, top, size.width, bottom))
}
