package vn.abook.player.ui.nowplaying

import vn.abook.player.S

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.animateScrollBy
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.scrollBy
import androidx.compose.foundation.interaction.collectIsDraggedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.runtime.snapshots.Snapshot
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.layout
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlin.math.abs
import kotlin.math.roundToInt
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/** Geometry computed once per paragraph layout, never allocated in draw. */
private class ParagraphInk(layout: TextLayoutResult, paragraph: ReadParagraph, pad: Float, radius: Float, wordPad: Float, wordInset: Float) {
    val sentence: Path = ReadInk.path(ReadInk.paragraphLines(layout, pad), radius)
    val words: List<List<Rect>> = paragraph.words.map { ReadInk.rangeRects(layout, it.from, it.until, wordPad, wordInset) }
}

/** Nền tô thở ra chừng này ngoài cột chữ (0,2em của web với cỡ chữ tới 40 sp) mà chữ không dời; danh sách rộng thêm đúng chừng này để nền không bị cắt, và khung chữ của trình phát (PlayerTextArea) cũng chừa ngang chừng này. */
internal val InkBleed = 4.dp

@Composable
fun ReadAlongPane(
    state: ReadAlongState, position: PlayerPosition, modifier: Modifier = Modifier,
    onManualScroll: () -> Unit = {}, onTap: () -> Unit = {}, onRetry: () -> Unit = {},
    /** Dáng chữ (cỡ, giãn dòng). */
    look: ReadLook = ReadLook(),
    /** Lời nhắc ở đầu chữ ([ReadHint]); null = không có. */
    hint: String? = null,
    /** Chạm chữ: nghe từ mốc này. */
    onListen: (Long) -> Unit = {},
    /** Tên chương kế (thẻ "Chương tiếp theo" ở cuối chữ); null = chương cuối. */
    nextTitle: String? = null,
    onNext: () -> Unit = {},
) {
    // Lời nhắc là mục đầu của danh sách (cuộn đi cùng chữ): các chỉ số đoạn lệch đi một khi nó có mặt.
    val lead = if (hint != null) 1 else 0
    // Cây chữ chỉ sống khi đang ở chế độ đọc: mỗi lần vào, danh sách dựng lại ngay ở câu đang đọc chứ không từ đầu chương.
    // Không đăng ký đọc đồng hồ ở đây: mỗi nhịp đồng hồ không được dựng lại màn.
    val list = rememberLazyListState(initialFirstVisibleItemIndex = remember {
        Snapshot.withoutReadObservation { ReadAlongLookup.sentence(state.paragraphs, position.milliseconds.value).coerceAtLeast(0) + lead }
    })
    val userDragging by list.interactionSource.collectIsDraggedAsState()
    var following by remember(state.bookId, state.chapterId) { mutableStateOf(true) }
    // Chữ chưa đứng đúng chỗ thì chưa hiện: khung đầu tiên người nghe thấy đã là dòng đang đọc, không có cú cuộn nào để thấy.
    var placed by remember(state.bookId, state.chapterId, look.size, look.lineHeight) { mutableStateOf(false) }
    val layouts = remember { HashMap<Int, TextLayoutResult>() }
    LaunchedEffect(userDragging) {
        if (userDragging) { following = false; onManualScroll() }
    }
    BoxWithConstraints(modifier.testTag("read_along_text").layout { measurable, constraints ->
        val bleed = InkBleed.roundToPx()
        val placeable = measurable.measure(constraints.copy(
            minWidth = constraints.minWidth + 2 * bleed,
            maxWidth = if (constraints.hasBoundedWidth) constraints.maxWidth + 2 * bleed else constraints.maxWidth))
        layout(placeable.width - 2 * bleed, placeable.height) { placeable.place(-bleed, 0) }
    }.clipToBounds()) {
        // The list ends above the jump dock, so placement measures the list's own viewport.
        val listHeight = maxHeight - Dim.s48
        val third = listHeight / 3
        val density = LocalDensity.current
        val viewportPx = with(density) { listHeight.roundToPx() }
        val placeAt = (viewportPx * ReadFollow.PLACE_AT).roundToInt()
        val tracker = remember(list) { LineTracker(list, layouts, position) }
        tracker.paragraphs = state.paragraphs
        tracker.lead = lead
        LaunchedEffect(state.bookId, state.chapterId, state.paragraphs, following, lead, placeAt, viewportPx, look.size, look.lineHeight) {
            if (state.paragraphs.isEmpty()) return@LaunchedEffect
            if (!following) { placed = true; return@LaunchedEffect }
            if (!placed) {
                tracker.settle(placeAt, viewportPx, animate = false)
                tracker.settled = tracker.target()
                placed = true
            }
            // Chỉ cuộn mượt khi người đọc tiến lên (sang từ ở dòng khác, sang câu). Khung đổi cỡ (chữ mở ra khi vào tab, đổi cỡ chữ) là dàn lại: canh tức thì,
            // nếu không thì mỗi khung của hoạt cảnh lại khởi động một cú cuộn mượt và danh sách trôi thêm sau khi tab đã mở xong.
            snapshotFlow { tracker.target() }.distinctUntilChanged().collectLatest { target ->
                val progressed = target != null && tracker.settled != null && target != tracker.settled
                tracker.settled = target
                tracker.settle(placeAt, viewportPx, animate = progressed)
            }
        }
        // Tự cuộn rồi ngừng SETTLE_MS mà dòng đang đọc vẫn trong khung thì theo lại (follow.ts của web); đứng yên ở chỗ khác thì không kéo người đọc đi.
        LaunchedEffect(following) {
            if (!following) snapshotFlow { list.isScrollInProgress }.collectLatest { moving ->
                if (!moving) {
                    delay(ReadFollow.SETTLE_MS)
                    if (tracker.lineInView() == true) { following = true; onTap() }
                }
            }
        }
        val showJump by remember(state.bookId, state.chapterId) { derivedStateOf { !following && tracker.lineInView() == false } }
        when {
            state.loading -> BasicText(S.s_dang_tai_chu_d97dd379, Modifier.align(Alignment.Center), style = Abook.type.bodySmall)
            state.error.isNotEmpty() -> Column(Modifier.align(Alignment.Center)) {
                BasicText(state.error, style = Abook.type.bodySmall)
                Box(Modifier.height(48.dp).pressable(onClick = onRetry), contentAlignment = Alignment.Center) {
                    BasicText(S.s_thu_lai_c58d068c, style = Abook.type.label)
                }
            }
            else -> LazyColumn(
                state = list, modifier = Modifier.fillMaxSize().padding(bottom = Dim.s48).testTag("reading_scroll")
                    .drawWithContent { if (placed || state.paragraphs.isEmpty()) drawContent() }
                    .fadeEdges(list).pointerInput(onTap) { detectTapGestures { onTap() } },
                // Đáy chừa đủ để cả dòng cuối vẫn lên được tới vùng đọc, không kẹt ở nửa dưới màn.
                contentPadding = PaddingValues(start = InkBleed, end = InkBleed, top = 12.dp, bottom = third * 2), verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                if (hint != null) item(key = "hint", contentType = "hint") {
                    RowHint(hint, Modifier.widthIn(max = 680.dp).fillMaxWidth().testTag("read_hint"))
                }
                itemsIndexed(state.paragraphs, key = { _, paragraph -> paragraph.id }, contentType = { _, _ -> "paragraph" }) { index, paragraph ->
                    // Dàn chữ theo đoạn; hình tô dựng từ dàn chữ + mốc, nên mốc về thêm (giọng máy đọc xong clip) cũng dựng lại hình tô.
                    var layout by remember(paragraph.id) { mutableStateOf<TextLayoutResult?>(null) }
                    DisposableEffect(index) { onDispose { layouts.remove(index) } }
                    val colors = Abook.colors
                    // Cùng độ đậm với --read-along / --read-along-word của web và along / word của Qt.
                    val sentenceColor = colors.accent.copy(alpha = if (colors.dark) 0.18f else 0.26f)
                    val wordColor = colors.accent.copy(alpha = if (colors.dark) 0.30f else 0.62f)
                    val radius = with(density) { Dim.radiusControl.toPx() }
                    val geometry = remember(layout, paragraph, radius) {
                        layout?.let { with(density) { ParagraphInk(it, paragraph, 4.dp.toPx(), radius, 2.dp.toPx(), 1.dp.toPx()) } }
                    }
                    BasicText(
                        paragraph.text,
                        Modifier.widthIn(max = 680.dp).fillMaxWidth().testTag("paragraph_${paragraph.id}")
                            .semantics { onClick(S.s_nghe_tu_day_6a7ff4ab) { onListen(paragraph.startMs); following = true; true } }
                            .pointerInput(paragraph) {
                                detectTapGestures { at ->
                                    onTap()
                                    if (paragraph.timed) {
                                        onListen(ReadTap.startAt(paragraph, layout?.getOffsetForPosition(at) ?: 0))
                                        following = true
                                    }
                                }
                            }.drawBehind {
                            val ms = position.milliseconds.value
                            if (ReadAlongLookup.sentence(state.paragraphs, ms) == index) {
                                val ink = geometry
                                if (ink != null) {
                                    drawPath(ink.sentence, sentenceColor)
                                    val word = ReadAlongLookup.word(paragraph.words, ms)
                                    if (word >= 0 && word < ink.words.size) drawInkRects(ink.words[word], wordColor, radius)
                                }
                            }
                        },
                        style = Abook.type.body.copy(fontSize = look.size.sp, lineHeight = look.lineHeight.sp, lineBreak = androidx.compose.ui.text.style.LineBreak.Paragraph),
                        onTextLayout = { layout = it; layouts[index] = it },
                    )
                }
                if (nextTitle != null) item(key = "next-chapter", contentType = "next") {
                    Column(Modifier.widthIn(max = 680.dp).fillMaxWidth().heightIn(min = 56.dp).pressable(onClick = onNext).testTag("read_next_chapter"),
                        verticalArrangement = Arrangement.Center) {
                        BasicText(S.s_chuong_tiep_theo_f07a08a4, style = Abook.type.caption.copy(color = Abook.colors.text2))
                        BasicText(nextTitle, style = Abook.type.body.copy(color = Abook.colors.accentText))
                    }
                }
            }
        }
        // The fixed dock owns its space; the text viewport ends above it.
        Box(Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(Dim.s48).background(Abook.colors.bg)
            .testTag("reading_dock").clipToBounds(), contentAlignment = Alignment.Center) {
            AnimatedVisibility(showJump,
                enter = slideInVertically(tween(MotionMs.MEDIUM)) { it },
                exit = slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { it }) {
                Box(Modifier.heightIn(min = 48.dp).pressable { following = true; onTap() }.testTag("follow_sentence"),
                    contentAlignment = Alignment.Center) {
                    BasicText(S.s_toi_cau_dang_nghe_4526cf38, Modifier
                        .background(Abook.colors.accentSoft, RoundedCornerShape(Dim.radiusCover))
                        .padding(horizontal = 14.dp, vertical = 6.dp),
                        style = Abook.type.caption.copy(color = Abook.colors.accentText, fontWeight = FontWeight.Medium))
                }
            }
        }
    }
}

/** Biết dòng đang đọc ở đâu trên màn và đưa nó vào vùng đọc (luật ở [ReadFollow]). */
@Stable
private class LineTracker(private val list: LazyListState, private val layouts: Map<Int, TextLayoutResult>, private val position: PlayerPosition) {
    var paragraphs: List<ReadParagraph> by mutableStateOf(emptyList())
    var lead: Int by mutableIntStateOf(0)
    /** Chỗ đã canh tới lần trước: khác nó mới là người đọc tiến lên. */
    var settled: ReadFollow.Target? = null

    private fun sentence(): Int = ReadAlongLookup.sentence(paragraphs, position.milliseconds.value)

    /** Câu + dòng đang đọc: chỉ đổi khi từ xuống dòng mới hay sang câu khác, không phải mỗi từ. */
    fun target(): ReadFollow.Target? {
        val sentence = sentence()
        if (sentence < 0) return null
        val line = layouts[sentence]?.let { ReadFollow.lineAt(paragraphs[sentence].words, position.milliseconds.value, it::getLineForOffset) } ?: 0
        return ReadFollow.Target(sentence, line)
    }

    /** Chỗ của dòng đang đọc tính từ mép trên danh sách; null: đoạn của nó chưa dựng. */
    private fun lineY(sentence: Int): Float? {
        val item = list.layoutInfo.visibleItemsInfo.firstOrNull { it.index == sentence + lead } ?: return null
        val layout = layouts[sentence] ?: return null
        return item.offset + layout.getLineTop(ReadFollow.lineAt(paragraphs[sentence].words, position.milliseconds.value, layout::getLineForOffset))
    }

    /** true / false: câu đang đọc trong / ngoài khung; null: lúc này không có câu nào đang đọc. */
    fun lineInView(): Boolean? {
        val sentence = sentence()
        if (sentence < 0) return null
        return list.layoutInfo.visibleItemsInfo.any { it.index == sentence + lead }
    }

    suspend fun settle(placeAt: Int, viewportPx: Int, animate: Boolean) {
        val sentence = sentence()
        if (sentence < 0) return
        try {
            var far = false
            var y = lineY(sentence)
            if (y == null) {
                // Đoạn đang đọc ở xa (mới mở, tua): nhảy thẳng tới rồi mới canh dòng; cuộn dài qua cả trăm đoạn chỉ làm người đọc chóng mặt.
                far = true
                list.scrollToItem(sentence + lead, -placeAt)
                y = lineY(sentence)
            }
            val delta = (y ?: return) - placeAt
            if (abs(delta) < 1f) return
            if (animate && !far && abs(delta) <= viewportPx) list.animateScrollBy(delta, tween(MotionMs.SLOW))
            else list.scrollBy(delta)
        } catch (interrupted: CancellationException) {
            // Ngón tay người đọc giành danh sách giữa chừng: hủy riêng cú cuộn này, không dừng cả việc theo.
            currentCoroutineContext().ensureActive()
        }
    }
}
