package vn.abook.player.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.Layout
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.layout
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.IntOffset
import androidx.compose.animation.core.tween
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import vn.abook.player.ui.components.fadeEdgesHorizontal
import vn.abook.player.ui.theme.MotionMs
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.CloseIcon
import vn.abook.player.ui.components.PlusIcon
import vn.abook.player.ui.components.SearchIcon
import vn.abook.player.ui.components.SortIcon
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.LibraryFilter
import vn.abook.player.ui.data.LibrarySort
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.abs
import kotlin.math.ceil
import kotlin.math.floor
import kotlin.math.roundToInt

/** "Thêm sách": chữ hổ phách với dấu + (nút chữ, DESIGN.md §6 "Nút (c)"), vùng chạm cao 48. */
@Composable
fun AddBookButton(onClick: () -> Unit, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    Row(
        modifier.height(Dim.s48).pressable(onClick = onClick).testTag("add_book"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        PlusIcon(colors.accentText, size = 18.dp)
        Spacer(Modifier.width(Dim.s4))
        BasicText("Thêm sách", style = Abook.type.label.copy(color = colors.accentText))
    }
}

private val LabelPad = 6.dp

/** Khe tối thiểu giữa hai chữ bộ lọc (web: `RowGap w-4`) và tối đa khi còn dư chỗ. */
internal val FilterGapMin = 16.dp
private val FilterGapMax = 24.dp

/**
 * Bề rộng nội dung của hàng bộ lọc và khe giữa các chữ, theo bề rộng khung nhìn [viewport], tổng bề rộng chữ [ink] (không tính lề chạm) và số chữ [count]:
 * đủ chỗ thì giãn đều trong khoảng [FilterGapMin]..[FilterGapMax] (nội dung = khung nhìn); thiếu thì khe giữ [FilterGapMin] và nội dung dài hơn khung - hàng cuộn.
 * Hàm thuần để test kiểm ở 320 / 360 / 411 dp.
 */
internal fun filterSpread(viewport: Int, ink: Int, count: Int, minGap: Int, maxGap: Int): Pair<Int, Int> {
    if (count <= 1) return maxOf(viewport, ink) to 0
    val gap = ((viewport - ink) / (count - 1)).coerceIn(minGap, maxGap)
    return maxOf(viewport, ink + gap * (count - 1)) to gap
}

/**
 * Hàng bộ lọc: chữ có gạch chân hổ phách trượt theo [LibraryUiState.position] (không hộp segmented). Chữ giãn đều trong bề rộng có sẵn (khe 16..24 dp giữa hai chữ,
 * như web), chữ đầu thẳng mép nội dung; hẹp quá (màn 320 dp, chữ hệ thống to) thì hàng CUỘN ngang với mép mờ - chữ không bị ép sát nút Xếp theo, không xuống dòng.
 * Mục đang chọn tự cuộn vào giữa. Màu chữ và gạch chân đọc vị trí trong pha vẽ.
 */
@Composable
fun FilterRow(ui: LibraryUiState, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val filters = LibraryFilter.entries
    val spans = remember { FloatArray(filters.size * 2) }
    val scroll = rememberScrollState()
    val viewportWidth = remember { intArrayOf(0) }
    LaunchedEffect(ui.filter) {
        val width = viewportWidth[0]
        if (width <= 0) return@LaunchedEffect
        val index = ui.filter.ordinal
        val target = (spans[index * 2] + spans[index * 2 + 1] / 2f - width / 2f).roundToInt().coerceIn(0, scroll.maxValue)
        scroll.animateScrollTo(target, tween(MotionMs.MEDIUM, easing = Motion.Standard))
    }
    Layout(
        content = {
            for (filter in filters) {
                Box(
                    Modifier.fillMaxHeight()
                        .pressable(Role.Tab) { ui.select(filter) }
                        .padding(horizontal = LabelPad)
                        .semantics { selected = ui.filter == filter }
                        .testTag(filter.tag),
                    contentAlignment = Alignment.Center,
                ) {
                    BasicText(
                        filter.label,
                        style = Abook.type.label,
                        color = { lerp(colors.text2, colors.text, (1f - abs(ui.position.value - filter.ordinal)).coerceIn(0f, 1f)) },
                        softWrap = false,
                    )
                }
            }
        },
        // Khung nhìn cố định (fillMaxWidth trước cuộn) -> trong khối đo, minWidth = bề rộng khung nhìn, maxWidth vô hạn.
        modifier = modifier.height(Dim.s48).fillMaxWidth().testTag("filter_row").fadeEdgesHorizontal(scroll).horizontalScroll(scroll).drawBehind {
            val position = ui.position.value
            val low = floor(position).toInt().coerceIn(0, filters.size - 1)
            val high = ceil(position).toInt().coerceIn(0, filters.size - 1)
            val t = position - low
            val left = spans[low * 2] + (spans[high * 2] - spans[low * 2]) * t
            val width = spans[low * 2 + 1] + (spans[high * 2 + 1] - spans[low * 2 + 1]) * t
            val thick = 3.dp.toPx()
            // Ô Tìm nở ra thì gạch chân co lại về chỗ cũ (không tắt mờ): tìm thì không còn "đang ở bộ lọc nào" nữa.
            drawRect(colors.accent, Offset(left, size.height - thick), Size(width * (1f - ui.search.value), thick))
        },
    ) { measurables, constraints ->
        val pad = LabelPad.roundToPx()
        val viewport = constraints.minWidth
        viewportWidth[0] = viewport
        val loose = Constraints(maxHeight = constraints.maxHeight)
        val placeables = measurables.map { it.measure(loose) }
        val ink = placeables.sumOf { it.width - 2 * pad }
        val (content, spread) = filterSpread(viewport, ink, placeables.size, FilterGapMin.roundToPx(), FilterGapMax.roundToPx())
        layout(content, constraints.maxHeight) {
            var x = 0
            for ((index, placeable) in placeables.withIndex()) {
                spans[index * 2] = x.toFloat()
                spans[index * 2 + 1] = (placeable.width - 2 * pad).toFloat()
                placeable.place(x - pad, 0)
                x += placeable.width - 2 * pad + spread
            }
        }
    }
}

/** Nút "Xếp theo" (biểu tượng ba vạch): mở menu nhỏ; báo toạ độ của nó cho nơi vẽ menu. */
@Composable
fun SortButton(ui: LibraryUiState, onCoordinates: (LayoutCoordinates) -> Unit, modifier: Modifier = Modifier) {
    Box(
        modifier.size(Dim.touch, Dim.s48).onGloballyPositioned(onCoordinates)
            .pressable { ui.openMenu() }
            .semantics { contentDescription = "Xếp theo" }
            .testTag("sort_button"),
        contentAlignment = Alignment.Center,
    ) {
        SortIcon(Abook.colors.text2)
    }
}

/**
 * Tìm: biểu tượng nở ra thành ô cả hàng (neo bên phải, bề rộng theo [LibraryUiState.search] trong pha dàn trang, nền chìm vẽ trong pha vẽ) - phủ lên chữ bộ lọc
 * như một tấm trượt ra, không mờ. Nhấn ✕ thu lại và xoá chữ đã gõ.
 */
@Composable
fun SearchBox(ui: LibraryUiState, modifier: Modifier = Modifier) {
    val colors = Abook.colors
    val focus = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    LaunchedEffect(ui.searchOpen) {
        if (ui.searchOpen) {
            try {
                focus.requestFocus()
            } catch (_: IllegalStateException) {
                // Ô chưa gắn vào cây: người dùng chạm vào ô là có tiêu điểm.
            }
        } else {
            keyboard?.hide()
        }
    }
    Row(
        modifier
            .layout { measurable, constraints ->
                val closed = Dim.touch.roundToPx()
                val width = (closed + (constraints.maxWidth - closed) * ui.search.value).roundToInt().coerceIn(closed, constraints.maxWidth)
                val placeable = measurable.measure(Constraints.fixed(width, closed))
                layout(width, closed) { placeable.place(0, 0) }
            }
            .clip(CircleShape)
            .drawBehind {
                if (ui.search.value > 0f) drawRoundRect(colors.bgSunken, cornerRadius = CornerRadius(size.height / 2))
            },
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier.size(Dim.touch).pressable { ui.openSearch() }.semantics { contentDescription = "Tìm sách" }.testTag("search_button"),
            contentAlignment = Alignment.Center,
        ) {
            SearchIcon(if (ui.searchOpen) colors.text else colors.text2)
        }
        if (ui.searchOpen) {
            BasicTextField(
                value = ui.query,
                onValueChange = ui::updateQuery,
                modifier = Modifier.weight(1f).focusRequester(focus).testTag("search_field"),
                singleLine = true,
                textStyle = Abook.type.body,
                cursorBrush = SolidColor(colors.accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { keyboard?.hide() }),
                decorationBox = { inner ->
                    Box(contentAlignment = Alignment.CenterStart) {
                        if (ui.query.isEmpty()) BasicText("Tên sách, tác giả, giọng", style = Abook.type.body.copy(color = colors.text3))
                        inner()
                    }
                },
            )
            Box(
                Modifier.size(Dim.touch).pressable { ui.clearOrClose() }.semantics { contentDescription = if (ui.query.isNotEmpty()) "Xoá ô tìm" else "Đóng ô tìm" }.testTag("search_close"),
                contentAlignment = Alignment.Center,
            ) {
                CloseIcon(colors.text2, size = 18.dp)
            }
        }
    }
}

/**
 * Menu "Xếp theo": bật ra từ góc nút (phóng từ góc trên phải, 120 ms), bóng vì là lớp nổi. Hàng đang chọn chữ hổ phách + dấu tích đầu dòng, giữ chỗ cho mọi hàng.
 * `anchor`: góc dưới phải của nút trong toạ độ của chỗ đặt menu. Chạm ra ngoài hay Back đóng.
 */
@Composable
fun SortMenu(ui: LibraryUiState, anchor: IntOffset, backEnabled: Boolean = true) {
    val open = ui.menuOpen
    val progress = remember { Animatable(0f) }
    var present by remember { mutableStateOf(false) }
    LaunchedEffect(open) {
        if (open) {
            present = true
            progress.animateTo(1f, Motion.MenuIn)
        } else {
            progress.animateTo(0f, Motion.MenuOut)
            present = false
        }
    }
    if (!present) return
    BackHandler(enabled = open && backEnabled) { ui.closeMenu() }
    val colors = Abook.colors
    val shape = RoundedCornerShape(Dim.radiusCover)
    Box(Modifier.fillMaxSize().pointerInput(Unit) { detectTapGestures { ui.closeMenu() } }.testTag("sort_menu")) {
        Column(
            Modifier
                .offset { IntOffset(anchor.x - MenuWidth.roundToPx(), anchor.y) }
                .width(MenuWidth)
                .graphicsLayer {
                    transformOrigin = TransformOrigin(1f, 0f)
                    val k = progress.value
                    scaleX = 0.9f + 0.1f * k
                    scaleY = 0.8f + 0.2f * k
                }
                .shadow(8.dp, shape)
                .clip(shape)
                .background(colors.panel)
                .border(1.dp, colors.line, shape)
                .pointerInput(Unit) { detectTapGestures { } }
                .padding(vertical = Dim.s4),
        ) {
            for (option in LibrarySort.entries) {
                val chosen = option == ui.sort
                Row(
                    Modifier.fillMaxWidth().height(Dim.s48).pressable { ui.chooseSort(option) }.padding(horizontal = Dim.s16).testTag("sort_${option.name}"),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(Dim.s24), contentAlignment = Alignment.CenterStart) {
                        if (chosen) CheckIcon(colors.accentText)
                    }
                    BasicText(option.label, style = Abook.type.body.copy(color = if (chosen) colors.accentText else colors.text))
                }
            }
        }
    }
}

private val MenuWidth = 220.dp

/** Chiều cao hàng bộ lọc + sắp xếp + tìm, và tiện ích gom lại: hàng bộ lọc chiếm phần còn lại. */
@Composable
fun FilterBar(ui: LibraryUiState, onSortCoordinates: (LayoutCoordinates) -> Unit, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(Dim.s48)) {
        Row(Modifier.fillMaxSize()) {
            FilterRow(ui, Modifier.weight(1f))
            SortButton(ui, onSortCoordinates)
            Spacer(Modifier.width(Dim.touch))
        }
        SearchBox(ui, Modifier.align(Alignment.CenterEnd))
    }
}
