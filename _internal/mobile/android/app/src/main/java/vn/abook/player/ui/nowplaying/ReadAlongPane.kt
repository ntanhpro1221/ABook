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
import androidx.compose.foundation.lazy.LazyListState
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.flow.distinctUntilChanged
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
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
        LaunchedEffect(state.paragraphs, following) {
            if (following) snapshotFlow { ReadAlongLookup.sentence(state.paragraphs, position.milliseconds.value) }
                .distinctUntilChanged().collect { index ->
                    if (index >= 0) list.animateScrollToItem(index, -thirdPx)
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
                state = list, modifier = Modifier.fillMaxSize().fadeEdges(24.dp, list).pointerInput(onTap) { detectTapGestures { onTap() } },
                contentPadding = PaddingValues(top = 12.dp, bottom = third), verticalArrangement = Arrangement.spacedBy(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                itemsIndexed(state.paragraphs, key = { _, paragraph -> paragraph.id }, contentType = { _, _ -> "paragraph" }) { index, paragraph ->
                    var geometry by remember(paragraph) { mutableStateOf<ParagraphInk?>(null) }
                    val sentenceColor = Abook.colors.accentSoft
                    val wordColor = Abook.colors.accent.copy(alpha = 0.27f)
                    BasicText(
                        paragraph.text,
                        Modifier.widthIn(max = 680.dp).fillMaxWidth().testTag("paragraph_${paragraph.id}").drawBehind {
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
                        style = Abook.type.body.copy(fontSize = 20.sp, lineHeight = 34.sp),
                        onTextLayout = { geometry = ParagraphInk(it, paragraph) },
                    )
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
                    BasicText("Theo câu đang nghe", Modifier
                        .background(Abook.colors.accentSoft, RoundedCornerShape(16.dp))
                        .padding(horizontal = 14.dp, vertical = 6.dp),
                        style = Abook.type.caption.copy(color = Abook.colors.accentText, fontWeight = FontWeight.Medium))
                }
            }
        }
    }
}

/** Text scrolls out under a soft edge instead of a hard cut at the header and the seek bar - only on a side that has more to scroll. */
private fun Modifier.fadeEdges(edge: Dp, list: LazyListState): Modifier = graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
    .drawWithContent {
        drawContent()
        val fraction = (edge.toPx() / size.height).coerceIn(0f, 0.5f)
        val top = if (list.canScrollBackward) Color.Transparent else Color.Black
        val bottom = if (list.canScrollForward) Color.Transparent else Color.Black
        drawRect(Brush.verticalGradient(0f to top, fraction to Color.Black, 1f - fraction to Color.Black, 1f to bottom),
            blendMode = BlendMode.DstIn)
    }
