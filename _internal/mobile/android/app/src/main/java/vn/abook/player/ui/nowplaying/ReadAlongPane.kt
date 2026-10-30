package vn.abook.player.ui.nowplaying

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.interaction.collectIsDraggedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.flow.distinctUntilChanged
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/** Geometry computed once per paragraph layout, never allocated in draw. */
private class ParagraphInk(layout: TextLayoutResult, paragraph: ReadParagraph) {
    val sentence: Path = layout.getPathForRange(0, paragraph.text.length)
    val words: List<Path> = paragraph.words.map { layout.getPathForRange(it.from, it.until) }
}

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
    val list = rememberLazyListState()
    val userDragging by list.interactionSource.collectIsDraggedAsState()
    var following by remember(state.bookId, state.chapterId) { mutableStateOf(true) }
    LaunchedEffect(userDragging) {
        if (userDragging) { following = false; onManualScroll() }
    }
    BoxWithConstraints(modifier.clipToBounds().testTag("read_along_text")) {
        val third = maxHeight / 3
        val thirdPx = with(androidx.compose.ui.platform.LocalDensity.current) { third.roundToPx() }
        // Lời nhắc là mục đầu của danh sách (cuộn đi cùng chữ): các chỉ số đoạn lệch đi một khi nó có mặt.
        val lead = if (hint != null) 1 else 0
        LaunchedEffect(state.paragraphs, following, lead) {
            if (following) snapshotFlow { ReadAlongLookup.sentence(state.paragraphs, position.milliseconds.value) }
                .distinctUntilChanged().collect { index ->
                    if (index >= 0) list.animateScrollToItem(index + lead, -thirdPx)
                }
        }
        when {
            state.loading -> BasicText("Đang tải chữ", Modifier.align(Alignment.Center), style = Abook.type.bodySmall)
            state.error.isNotEmpty() -> Column(Modifier.align(Alignment.Center)) {
                BasicText(state.error, style = Abook.type.bodySmall)
                Box(Modifier.height(48.dp).pressable(onClick = onRetry), contentAlignment = Alignment.Center) {
                    BasicText("Thử lại", style = Abook.type.label)
                }
            }
            else -> LazyColumn(
                state = list, modifier = Modifier.fillMaxSize().fadeEdges(list).pointerInput(onTap) { detectTapGestures { onTap() } },
                contentPadding = PaddingValues(top = 12.dp, bottom = third), verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                if (hint != null) item(key = "hint", contentType = "hint") {
                    RowHint(hint, Modifier.widthIn(max = 680.dp).fillMaxWidth().testTag("read_hint"))
                }
                itemsIndexed(state.paragraphs, key = { _, paragraph -> paragraph.id }, contentType = { _, _ -> "paragraph" }) { index, paragraph ->
                    var geometry by remember(paragraph) { mutableStateOf<ParagraphInk?>(null) }
                    var layout by remember(paragraph) { mutableStateOf<TextLayoutResult?>(null) }
                    val sentenceColor = Abook.colors.accentSoft
                    val wordColor = Abook.colors.accent.copy(alpha = 0.27f)
                    BasicText(
                        paragraph.text,
                        Modifier.widthIn(max = 680.dp).fillMaxWidth().testTag("paragraph_${paragraph.id}")
                            .semantics { onClick("Nghe từ đây") { onListen(paragraph.startMs); true } }
                            .pointerInput(paragraph) {
                                detectTapGestures { at ->
                                    onTap()
                                    if (paragraph.timed) onListen(ReadTap.startAt(paragraph, layout?.getOffsetForPosition(at) ?: 0))
                                }
                            }.drawBehind {
                            val ms = position.milliseconds.value
                            if (ReadAlongLookup.sentence(state.paragraphs, ms) == index) {
                                val ink = geometry
                                if (ink != null) {
                                    drawPath(ink.sentence, sentenceColor)
                                    val word = ReadAlongLookup.word(paragraph.words, ms)
                                    if (word >= 0 && word < ink.words.size) drawPath(ink.words[word], wordColor)
                                }
                            }
                        },
                        style = Abook.type.body.copy(fontSize = look.size.sp, lineHeight = look.lineHeight.sp, lineBreak = androidx.compose.ui.text.style.LineBreak.Paragraph),
                        onTextLayout = { layout = it; geometry = ParagraphInk(it, paragraph) },
                    )
                }
                if (nextTitle != null) item(key = "next-chapter", contentType = "next") {
                    Column(Modifier.widthIn(max = 680.dp).fillMaxWidth().heightIn(min = 56.dp).pressable(onClick = onNext).testTag("read_next_chapter"),
                        verticalArrangement = Arrangement.Center) {
                        BasicText("Chương tiếp theo", style = Abook.type.caption.copy(color = Abook.colors.text2))
                        BasicText(nextTitle, style = Abook.type.body.copy(color = Abook.colors.accentText))
                    }
                }
            }
        }
        // A pill above the text, never bare words over it; slides through a clipped slot like "Về chỗ cũ".
        Box(Modifier.align(Alignment.BottomCenter).padding(bottom = 12.dp).clipToBounds()) {
            AnimatedVisibility(!following,
                enter = slideInVertically(tween(MotionMs.MEDIUM)) { it },
                exit = slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { it }) {
                Box(Modifier.heightIn(min = 48.dp).pressable { following = true; onTap() }.testTag("follow_sentence"),
                    contentAlignment = Alignment.Center) {
                    BasicText("Tới câu đang nghe", Modifier
                        .background(Abook.colors.accentSoft, RoundedCornerShape(Dim.radiusCover))
                        .padding(horizontal = 14.dp, vertical = 6.dp),
                        style = Abook.type.caption.copy(color = Abook.colors.accentText, fontWeight = FontWeight.Medium))
                }
            }
        }
    }
}
