package vn.abook.player.ui.components

import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.graphics.drawscope.translate
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.max

/**
 * Công tắc (vẽ tay, 48 x 28): núm TRƯỢT sang phải khi bật, rãnh đổi từ mực mờ sang mực theo cùng tiến trình - đọc trong pha vẽ. Không hổ phách: màn Cài đặt
 * chỉ có tối đa một khối hổ phách (nút chính), công tắc là trạng thái chứ không phải lời mời. Chỉ là hình: cả hàng chứa nó mới là chỗ chạm ([SwitchRow]).
 */
@Composable
fun Switch(checked: Boolean, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val knob = remember { Animatable(if (checked) 1f else 0f) }
    LaunchedEffect(checked) { knob.animateTo(if (checked) 1f else 0f, Motion.Expand) }
    Canvas(modifier.size(48.dp, 28.dp)) {
        val k = knob.value
        val inset = 2.dp.toPx()
        val radius = size.height / 2 - inset
        drawRoundRect(lerp(colors.fg3, colors.text, k), cornerRadius = CornerRadius(size.height / 2))
        val x = inset + radius + (size.width - 2 * (inset + radius)) * k
        drawCircle(colors.bg, radius, Offset(x, size.height / 2))
    }
}

/** Gạch chân dưới lựa chọn đang chọn: dày 3 dp như hàng bộ lọc Thư viện. */
private val UnderlineThickness = 3.dp

/** Khoảng giữa hai lựa chọn (mép chữ tới mép chữ). */
private val ChoiceGap = 24.dp

/**
 * Chọn một: hàng chữ có gạch chân hổ phách TRƯỢT sang lựa chọn mới (không hộp segmented - DESIGN.md §6 "Bộ lọc"). Chữ đang chọn đậm màu mực, chữ khác mực
 * phụ; cả màu chữ lẫn gạch đọc vị trí trong pha vẽ. Lựa chọn đầu thẳng mép nội dung; hết chỗ thì xuống hàng (không bao giờ cắt chữ). Mỗi lựa chọn cao 48,
 * rộng ít nhất 44 để chạm.
 *
 * `onPick` nhận thêm tâm của lựa chọn trong toạ độ gốc (vd. vòng lan đổi giao diện bắt đầu ở đó).
 */
@Composable
fun <T : Choice> ChoiceRow(
    options: List<T>,
    value: T,
    onPick: (T, Offset) -> Unit,
    modifier: Modifier = Modifier,
    tag: String = "choice",
) {
    val colors = Abook.colors
    val index = options.indexOf(value).coerceAtLeast(0)
    val position = remember { Animatable(index.toFloat()) }
    LaunchedEffect(index) { position.animateTo(index.toFloat(), Motion.TabSlide) }
    // Mỗi lựa chọn 4 số: x, y, bề ngang chữ, chiều cao ô - ghi trong pha dàn trang, đọc khi vẽ gạch và khi chạm. Bề ngang chữ ghi lúc chữ dàn dòng.
    val spans = remember(options.size) { FloatArray(options.size * 4) }
    val inks = remember(options.size) { FloatArray(options.size) }
    val where = remember { arrayOfNulls<LayoutCoordinates>(1) }
    Layout(
        content = {
            for ((i, option) in options.withIndex()) {
                val chosen = option == value
                Box(
                    Modifier.widthIn(min = Dim.touch).heightIn(min = Dim.s48)
                        .pressable(Role.RadioButton) {
                            val center = Offset(spans[i * 4] + inks[i] / 2, spans[i * 4 + 1] + spans[i * 4 + 3] / 2)
                            onPick(option, where[0]?.takeIf { it.isAttached }?.localToRoot(center) ?: Offset.Unspecified)
                        }
                        .semantics { selected = chosen }
                        .testTag("${tag}_${option.key}"),
                    contentAlignment = Alignment.CenterStart,
                ) {
                    BasicText(
                        option.label,
                        style = Abook.type.label,
                        onTextLayout = { inks[i] = it.size.width.toFloat() },
                        color = { lerp(colors.text2, colors.text, (1f - abs(position.value - i)).coerceIn(0f, 1f)) },
                    )
                }
            }
        },
        modifier = modifier.onGloballyPositioned { where[0] = it }.drawBehind {
            if (options.isEmpty()) return@drawBehind
            val p = position.value
            val low = floor(p).toInt().coerceIn(0, options.size - 1)
            val high = ceil(p).toInt().coerceIn(0, options.size - 1)
            val t = p - low
            val left = spans[low * 4] + (spans[high * 4] - spans[low * 4]) * t
            val bottom = spans[low * 4 + 1] + spans[low * 4 + 3] + (spans[high * 4 + 1] + spans[high * 4 + 3] - spans[low * 4 + 1] - spans[low * 4 + 3]) * t
            val width = inks[low] + (inks[high] - inks[low]) * t
            val thick = UnderlineThickness.toPx()
            drawRect(colors.accent, Offset(left, bottom - thick), Size(width, thick))
        },
    ) { measurables, constraints ->
        val maxWidth = if (constraints.hasBoundedWidth) constraints.maxWidth else Int.MAX_VALUE
        val placeables = measurables.map { it.measure(Constraints(maxWidth = maxWidth)) }
        val gap = ChoiceGap.roundToPx()
        var x = 0
        var y = 0
        var line = 0
        var widest = 0
        for ((i, placeable) in placeables.withIndex()) {
            val ink = inks[i].toInt().coerceAtMost(placeable.width)
            if (x > 0 && x + ink > maxWidth) {
                x = 0
                y += line
                line = 0
            }
            spans[i * 4] = x.toFloat()
            spans[i * 4 + 1] = y.toFloat()
            spans[i * 4 + 2] = placeable.width.toFloat()
            spans[i * 4 + 3] = placeable.height.toFloat()
            widest = max(widest, x + placeable.width)
            x += ink + gap
            line = max(line, placeable.height)
        }
        val width = if (constraints.hasBoundedWidth) constraints.maxWidth else widest
        layout(width, y + line) {
            for ((i, placeable) in placeables.withIndex()) placeable.place(spans[i * 4].toInt(), spans[i * 4 + 1].toInt())
        }
    }
}

/**
 * Mũi tên ">" cuối hàng mở một màn con (lucide ChevronRight như bản web, nét lưới 20 dp); `turn` (0..1, đọc khi vẽ) xoay nó xuống khi hàng mở khối tại
 * chỗ. Ô 16 dp, mũi nhọn chạm mép phải ô: mực thẳng mép cột như nút chữ cuối hàng.
 */
@Composable
fun ChevronIcon(color: androidx.compose.ui.graphics.Color, modifier: Modifier = Modifier, turn: () -> Float = { 0f }) {
    Canvas(modifier.size(16.dp)) {
        val unit = 20.dp.toPx() / 24f
        // Mực của ChevronRight: x 8..16, y 5..19 trên lưới 24 (kể cả nửa nét).
        translate(size.width - 16f * unit, size.height / 2 - 12f * unit) {
            rotate(90f * turn(), pivot = androidx.compose.ui.geometry.Offset(12f * unit, 12f * unit)) {
                drawLucide(LucidePaths.CHEVRON_RIGHT, color, unit)
            }
        }
    }
}
