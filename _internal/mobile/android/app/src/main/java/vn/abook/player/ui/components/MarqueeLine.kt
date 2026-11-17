package vn.abook.player.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.wrapContentWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.SemanticsPropertyKey
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.animation.core.withInfiniteAnimationFrameMillis
import kotlinx.coroutines.delay
import vn.abook.player.ui.motion.rememberReducedMotion
import vn.abook.player.ui.theme.MotionMs
import kotlin.math.floor
import kotlin.math.max
import kotlin.math.min

/** Cách tên nằm trong ô một dòng: vừa ở cỡ gốc · thu cỡ cho vừa · ở cỡ đáy và chạy chữ. */
enum class MarqueeFit { One, Shrunk, Scroll }

/** Cỡ chữ và cách nằm của [text] trong ô rộng [room] px: cùng luật với web `MarqueeLine` và Qt `MarqueeLine.qml`. [measure] trả bề ngang một dòng ở cỡ đã cho. */
fun marqueeFit(room: Int, baseSp: Float, measure: (Float) -> Int): Pair<MarqueeFit, Float> {
    if (room <= 0 || measure(baseSp) <= room) return MarqueeFit.One to baseSp
    val min = baseSp * OneLineFit.MIN_SCALE
    var size = floor(baseSp * room / measure(baseSp) / STEP) * STEP
    while (size >= min) {
        if (measure(size) <= room) return MarqueeFit.Shrunk to size
        size -= STEP
    }
    if (measure(min) <= room) return MarqueeFit.Shrunk to min
    return MarqueeFit.Scroll to min
}

private const val STEP = 0.5f

/** Original design size, before fitting the title to its fixed line. */
val MarqueeBaseSize = SemanticsPropertyKey<Float>("marquee_base_size")

/**
 * Tên trong ô MỘT DÒNG CỐ ĐỊNH (thanh phát thu nhỏ, trình phát - DESIGN.md §5.5 "Tên một dòng"; web `MarqueeLine`, Qt `MarqueeLine.qml`): ô luôn cao đúng một
 * dòng ở cỡ gốc nên bìa và nút phát không bao giờ dời vì tên dài ngắn. Vừa ở cỡ gốc thì giữ nguyên; không vừa thì thu cỡ tới [OneLineFit.MIN_SCALE] cỡ gốc;
 * thu tới đó vẫn không vừa thì CHẠY CHỮ: đứng [MotionMs.MARQUEE_DELAY_MS] ở đầu, trượt [MotionMs.MARQUEE_SPEED] dp/giây cho tới khi bản chép thứ hai (cách
 * [MotionMs.MARQUEE_GAP] dp) về đúng chỗ bản đầu, rồi lại đứng. Giảm chuyển động: không trượt - nhảy từng đoạn, mỗi đoạn đứng một nhịp, tới cuối tên thì về đầu.
 * Không bao giờ "…", không mờ đuôi; trợ năng đọc tên một lần. Vị trí chỉ đọc ở pha vẽ (graphicsLayer): chạy chữ không dựng lại gì.
 * Test (InfiniteAnimationPolicy của compose-test): vòng chạy dừng trước nhịp đầu, chữ đứng ở đầu - ảnh chụp tất định, test không treo.
 */
@Composable
fun MarqueeLine(text: String, modifier: Modifier = Modifier, style: TextStyle, textAlign: TextAlign = TextAlign.Start) {
    val measurer = rememberTextMeasurer()
    val density = LocalDensity.current
    val reduced = rememberReducedMotion()
    BoxWithConstraints(modifier.fillMaxWidth()) {
        val room = constraints.maxWidth
        val baseSp = style.fontSize.value
        val (fit, size) = remember(text, style, room, density, measurer) {
            marqueeFit(room, baseSp) { sp -> measurer.measure(text, style.copy(fontSize = sp.sp), softWrap = false).size.width }
        }
        // Ô cao đúng một dòng ở cỡ gốc: đo chính tên ở cỡ gốc không xuống dòng (cỡ thu nhỏ không đổi chiều cao ô)
        val lineHeight = remember(text, style, density, measurer) { measurer.measure(text, style, softWrap = false).size.height }
        val shown = style.copy(fontSize = size.sp, lineHeight = style.lineHeight)
        val boxHeight = with(density) { lineHeight.toDp() }
        if (fit != MarqueeFit.Scroll) {
            Box(Modifier.fillMaxWidth().height(boxHeight), contentAlignment = Alignment.CenterStart) {
                BasicText(text, Modifier.fillMaxWidth().semantics { this[MarqueeBaseSize] = baseSp }, shown.copy(textAlign = textAlign), softWrap = false)
            }
        } else {
            MarqueeScroll(text, shown, baseSp, room, boxHeight, reduced)
        }
    }
}

/** Phần chạy chữ của [MarqueeLine]: hai bản chép trên một dải, trượt bằng graphicsLayer (chỉ pha vẽ). */
@Composable
private fun MarqueeScroll(text: String, shown: TextStyle, baseSp: Float, room: Int, boxHeight: Dp, reduced: Boolean) {
    val measurer = rememberTextMeasurer()
    val density = LocalDensity.current
    val textWidth = remember(text, shown, density, measurer) { measurer.measure(text, shown, softWrap = false).size.width }
    val gap = with(density) { MotionMs.MARQUEE_GAP.dp.roundToPx() }
    val speed = with(density) { MotionMs.MARQUEE_SPEED.dp.toPx() }
    val cycle = (textWidth + gap).toFloat()
    val offset = remember(text, room) { Animatable(0f) }
    LaunchedEffect(offset, cycle, reduced) {
        offset.snapTo(0f)
        while (true) {
            // Một khung "vô hạn" mỗi vòng: compose-test dừng vòng ở đây (chữ đứng ở đầu); app thật chỉ tốn một khung
            withInfiniteAnimationFrameMillis { }
            delay(MotionMs.MARQUEE_DELAY_MS.toLong())
            if (reduced) {
                val end = (textWidth - room).toFloat()
                offset.snapTo(if (offset.value >= end - 0.5f) 0f else min(end, offset.value + max(1, room - gap)))
            } else {
                offset.animateTo(cycle, tween((cycle / speed * 1000).toInt(), easing = LinearEasing))
                offset.snapTo(0f)
            }
        }
    }
    Box(Modifier.fillMaxWidth().height(boxHeight).clipToBounds(), contentAlignment = Alignment.CenterStart) {
        Row(Modifier.wrapContentWidth(Alignment.Start, unbounded = true).graphicsLayer { translationX = -offset.value }, verticalAlignment = Alignment.CenterVertically) {
            BasicText(text, Modifier.semantics { this[MarqueeBaseSize] = baseSp }, style = shown, softWrap = false)
            if (!reduced) {
                Spacer(Modifier.width(with(density) { gap.toDp() }))
                BasicText(text, Modifier.clearAndSetSemantics {}, style = shown, softWrap = false)
            }
        }
    }
}
