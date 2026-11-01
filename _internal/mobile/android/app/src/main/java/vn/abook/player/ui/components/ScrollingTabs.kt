package vn.abook.player.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.layout.positionInParent
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.ceil
import kotlin.math.floor

/**
 * Thanh mục của mọi trang có mục (trang sách, dự án Studio): MỘT hàng, không bao giờ xuống dòng - xuống dòng làm hai thanh tab chồng nhau, gạch chân chỉ nằm một hàng
 * (soát điện thoại thật 02-11, Studio ở 360 dp). Hết chỗ (màn hẹp, chữ hệ thống to) thì hàng cuộn ngang có mép mờ, mục đang chọn tự cuộn vào khung. Gạch chân hổ phách
 * TRƯỢT sang mục mới, trôi cùng chữ khi hàng cuộn; đường kẻ chân trải cả bề rộng. `suffix` = phần phụ ngay sau nhãn (số chương; tự mang khoảng cách của nó).
 */
@Composable
fun <T> ScrollingTabs(
    tabs: List<T>,
    selected: T,
    onPick: (T) -> Unit,
    label: (T) -> String,
    tag: (T) -> String,
    rowTag: String,
    modifier: Modifier = Modifier,
    suffix: (@Composable (T) -> Unit)? = null,
) {
    val colors = Abook.colors
    val index = tabs.indexOf(selected).coerceAtLeast(0)
    val position = remember { Animatable(index.toFloat()) }
    LaunchedEffect(index) { position.animateTo(index.toFloat(), Motion.TabSlide) }
    val lefts = remember(tabs.size) { FloatArray(tabs.size) }
    val widths = remember(tabs.size) { FloatArray(tabs.size) }
    // Số lần dàn trang đổi vị trí: gạch chân đọc nó nên vẽ lại khi các mục dịch chỗ.
    var layouts by remember { mutableIntStateOf(0) }
    val viewport = remember { intArrayOf(0) }
    val scroll = rememberScrollState()
    // Mục đang chọn tự cuộn vào khung.
    LaunchedEffect(index) {
        val left = lefts[index].toInt()
        val right = left + widths[index].toInt()
        val view = viewport[0]
        val target = when {
            view <= 0 -> scroll.value
            left < scroll.value -> left
            right > scroll.value + view -> right - view
            else -> scroll.value
        }
        if (target != scroll.value) scroll.animateScrollTo(target.coerceIn(0, scroll.maxValue), Motion.TabSlide)
    }
    Box(
        modifier.fillMaxWidth().testTag(rowTag).onSizeChanged { viewport[0] = it.width }.drawBehind {
            drawRect(colors.line, Offset(0f, size.height - 1.dp.toPx()), Size(size.width, 1.dp.toPx()))
        },
    ) {
        Row(
            Modifier.fadeEdgesHorizontal(scroll).horizontalScroll(scroll).drawBehind {
                if (layouts < 0) return@drawBehind // chỉ để vẽ lại khi các mục dịch chỗ
                val thick = 3.dp.toPx()
                if (tabs.isEmpty()) return@drawBehind
                val p = position.value
                val low = floor(p).toInt().coerceIn(0, tabs.size - 1)
                val high = ceil(p).toInt().coerceIn(0, tabs.size - 1)
                val t = p - low
                val left = lefts[low] + (lefts[high] - lefts[low]) * t
                val width = widths[low] + (widths[high] - widths[low]) * t
                drawRect(colors.accent, Offset(left, size.height - thick), Size(width, thick))
            },
            horizontalArrangement = Arrangement.spacedBy(Dim.s24),
        ) {
            for ((i, tab) in tabs.withIndex()) {
                Row(
                    Modifier.heightIn(min = Dim.s48).pressable(Role.Tab) { onPick(tab) }.semantics { this.selected = tab == selected }
                        .onGloballyPositioned {
                            val x = it.positionInParent().x
                            val w = it.size.width.toFloat()
                            if (lefts[i] != x || widths[i] != w) {
                                lefts[i] = x
                                widths[i] = w
                                layouts += 1
                            }
                        }
                        .testTag(tag(tab)),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    BasicText(
                        label(tab),
                        style = Abook.type.tab,
                        color = { lerp(colors.text2, colors.text, (1f - kotlin.math.abs(position.value - i)).coerceIn(0f, 1f)) },
                    )
                    suffix?.invoke(tab)
                }
            }
        }
    }
}
