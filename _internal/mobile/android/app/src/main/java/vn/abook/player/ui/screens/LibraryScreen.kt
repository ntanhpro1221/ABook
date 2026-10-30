package vn.abook.player.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.core.tween
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.rememberPresence
import vn.abook.player.ui.theme.MotionMs
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import vn.abook.player.ui.components.TextAction
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.RemoteIcon
import vn.abook.player.ui.components.ScreenHeader
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.Library
import vn.abook.player.ui.data.LibraryFilter
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenLogic
import vn.abook.player.ui.data.ShelfTile
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.roundToInt
import vn.abook.player.ui.components.fadeEdges

/** Việc mà Thư viện nhờ nơi khác làm (mở trang sách, phát ngay, thêm sách) - tách khỏi màn để thử và để dựng ảnh chụp. */
@Stable
class LibraryActions(
    val openBook: (ListenBook) -> Unit,
    val playNow: (String) -> Unit,
    val addBook: () -> Unit,
    /** "Nối máy" ở thư viện trống: tới màn ghép với máy tính; null = không có (bản thử). */
    val connect: (() -> Unit)? = null,
)

/** Số cột: 2 trên máy hẹp (<360 dp), 3 từ 360 dp, thêm một cột mỗi 120 dp (DESIGN.md §6 "Lưới bìa": điện thoại 2-3 cột). */
internal fun libraryColumns(widthDp: Int): Int = (widthDp / 120).coerceAtLeast(2)

/**
 * Thư viện (DESIGN.md §7): đầu màn + "Thêm sách", bộ lọc / xếp / tìm, lưới bìa luôn mở (bộ nhiều tập gom một bìa, chạm mở bảng các tập,
 * giữ bìa là phát). KHÔNG có hàng "Đang nghe": cuốn đang nghe chỉ hiện và chỉ điều khiển ở thanh phát nhỏ (một cửa duy nhất).
 * Mọi mục lưới có `key` + `contentType`; chuyển động chạy theo khung (vạch, trượt lưới, ô tìm) chỉ đọc trong pha vẽ / dàn trang.
 */
@Composable
fun LibraryScreen(
    state: LibraryState,
    ui: LibraryUiState,
    grid: LazyGridState,
    covers: CoverLoader,
    sheets: SheetHost,
    actions: LibraryActions,
    modifier: Modifier = Modifier,
    backEnabled: Boolean = true,
    /** Thẻ "Tối qua" ở đầu lưới (sau đầu trang); null = không có (bản thử). */
    recap: (@Composable (List<ListenBook>) -> Unit)? = null,
) {
    val books = (state as? LibraryState.Ready)?.books ?: return Box(modifier.fillMaxSize())
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    val coords = remember { arrayOfNulls<LayoutCoordinates>(2) }
    var anchor by remember { mutableStateOf(IntOffset.Zero) }
    LaunchedEffect(ui.menuOpen) {
        val root = coords[0]
        val button = coords[1]
        if (ui.menuOpen && root != null && button != null && root.isAttached && button.isAttached) {
            val at = root.localPositionOf(button, Offset.Zero)
            anchor = IntOffset((at.x + button.size.width).roundToInt(), (at.y + button.size.height).roundToInt())
        }
    }
    // Back đóng ô tìm trước - chỉ khi màn này đang là màn trên cùng (không bị trang sách phủ, không ở tab khác).
    BackHandler(enabled = backEnabled && ui.searchOpen) { ui.closeSearch() }
    Box(modifier.fillMaxSize().onGloballyPositioned { coords[0] = it }) {
        LibraryGrid(books, ui, grid, covers, sheets, actions, top, recap) { coords[1] = it }
        SortMenu(ui, anchor, backEnabled)
    }
}

@Composable
private fun LibraryGrid(
    books: List<ListenBook>,
    ui: LibraryUiState,
    grid: LazyGridState,
    covers: CoverLoader,
    sheets: SheetHost,
    actions: LibraryActions,
    top: Dp,
    recap: (@Composable (List<ListenBook>) -> Unit)?,
    onSortCoordinates: (LayoutCoordinates) -> Unit,
) {
    val view = remember(books, ui.shown, ui.query, ui.sort) { Library.view(books, ui.shown, ui.query, ui.sort) }
    val tiles = rememberPresence(view.tiles) { it.key }
    val widthDp = LocalConfiguration.current.screenWidthDp
    val columns = libraryColumns(widthDp)
    val cell = ((widthDp - 2f * Dim.margin.value - (columns - 1) * Dim.s12.value) / columns).dp
    val gridWidthPx = with(LocalDensity.current) { widthDp.dp.toPx() }
    LazyVerticalGrid(
        columns = GridCells.Fixed(columns),
        state = grid,
        modifier = Modifier.fillMaxSize().testTag("library_grid").fadeEdges(grid),
        contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, top = top, bottom = Dim.s24),
        horizontalArrangement = Arrangement.spacedBy(Dim.s12),
        verticalArrangement = Arrangement.spacedBy(Dim.s16),
    ) {
        // Đầu trang + hàng lọc là MỘT ô: khoảng cách lưới (16) không cộng thêm vào lề dưới của đầu trang thành một khoảng trống lớn trên hàng lọc.
        item(key = "header", span = { GridItemSpan(maxLineSpan) }, contentType = "header") {
            Column {
                ScreenHeader("Thư viện", subtitle = if (books.isEmpty()) null else "${books.size} cuốn", trailing = { AddBookButton(actions.addBook) })
                vn.abook.player.ui.components.Reveal(books.isNotEmpty()) { FilterBar(ui, onSortCoordinates) }
            }
        }
        if (recap != null) item(key = "recap", span = { GridItemSpan(maxLineSpan) }, contentType = "recap") { recap(books) }
        if (tiles.isEmpty()) {
            item(key = "none", span = { GridItemSpan(maxLineSpan) }, contentType = "none") {
                if (books.isEmpty()) Column {
                    BasicText("Chưa có sách trên máy", style = Abook.type.sectionTitle)
                    RowHint("Thêm sách của bạn để bắt đầu nghe.")
                    actions.connect?.let { TextAction("Nối máy", it, "library_connect", align = Alignment.CenterStart) }
                } else NoMatch(ui.query.trim(), ui.filter)
            }
        } else {
            items(tiles, key = { it.item.key }, contentType = { if (it.item is ShelfTile.Series) "series" else "single" }) { tile ->
                AnimatedVisibility(tile.visible, modifier = Modifier.animateItem(fadeInSpec = null, fadeOutSpec = null),
                    enter = expandVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) + slideInVertically(tween(MotionMs.MEDIUM)) { it / 4 },
                    exit = shrinkVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) + slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { it / 4 }) {
                    BookTile(tile.item, ui, covers, cell, gridWidthPx, sheets, actions)
                }
            }
        }
    }
}

@Composable
private fun NoMatch(query: String, filter: LibraryFilter) {
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s32)) {
        BasicText(if (query.isEmpty()) "Không có sách ở đây" else "Không tìm thấy sách nào khớp “$query”", style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s4))
        BasicText(
            if (query.isNotEmpty()) "Thử tên sách hoặc tác giả khác." else when (filter) {
                LibraryFilter.All -> "Thư viện chưa có sách nào."
                LibraryFilter.Listening -> "Chưa nghe dở cuốn nào - chọn một cuốn để bắt đầu."
                LibraryFilter.New -> "Cuốn nào cũng đã được nghe ít nhất một đoạn."
                LibraryFilter.Finished -> "Chưa có cuốn nào nghe xong."
            },
            style = Abook.type.bodySmall,
        )
    }
}

/** Một ô của lưới: bìa 2:3 (kèm dấu nguồn / số tập / vạch tiến độ), tên tối đa 2 dòng, dòng phụ. Trượt ngang theo bộ lọc qua [LibraryUiState.slide]. */
@Composable
private fun BookTile(
    tile: ShelfTile,
    ui: LibraryUiState,
    covers: CoverLoader,
    cell: Dp,
    gridWidthPx: Float,
    sheets: SheetHost,
    actions: LibraryActions,
) {
    val haptic = LocalHapticFeedback.current
    val series = tile as? ShelfTile.Series
    val single = tile as? ShelfTile.Single
    val lead = series?.first ?: single!!.book
    val title = series?.label ?: lead.title
    val onClick = {
        if (series != null) sheets.show { dismiss -> SeriesSheet(series, covers, actions.openBook, dismiss) } else actions.openBook(lead)
    }
    val onLong = {
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        actions.playNow((series?.playTarget ?: lead).id)
    }
    Column(
        Modifier.fillMaxWidth()
            .graphicsLayer { translationX = ui.slide.value * gridWidthPx }
            .pressable(onLongClick = onLong, onClick = onClick)
            .testTag(if (series != null) "series_cell" else "book_cell"),
    ) {
        Box(Modifier.fillMaxWidth()) {
            BookCover(lead.cover, title, if (series != null) null else lead.part, covers, cell, Modifier.fillMaxWidth())
            if (series?.hasRemote ?: (lead.remote != null)) {
                // Dưới bìa (tên bìa nằm ở đầu), góc phải: chip số tập / nhãn ở góc trái.
                Box(Modifier.align(Alignment.BottomEnd).padding(Dim.s4).padding(bottom = 3.dp).size(22.dp).clip(CircleShape).background(Color.Black.copy(alpha = 0.5f)), contentAlignment = Alignment.Center) {
                    RemoteIcon(Color.White, Modifier.semantics { contentDescription = "Có sách trên máy khác" })
                }
            }
            if (series != null) {
                CoverChip("${series.books.size} ${series.unit}", Modifier.align(Alignment.BottomStart).padding(Dim.s4).padding(bottom = 3.dp))
            } else if (single?.badge != null) {
                CoverChip(single.badge, Modifier.align(Alignment.BottomStart).padding(Dim.s4).padding(bottom = 3.dp))
            }
            val fraction = if (series == null) lead.progress.fraction else 0f
            if (fraction > 0.005f && fraction < 0.995f) {
                val accent = Abook.colors.accent
                Box(
                    Modifier.align(Alignment.BottomStart).fillMaxWidth().height(3.dp).drawBehind {
                        drawRect(Color.Black.copy(alpha = 0.3f))
                        drawRect(accent, Offset.Zero, Size(size.width * fraction, size.height))
                    },
                )
            }
        }
        Spacer(Modifier.height(Dim.s8))
        BasicText(title, style = Abook.type.label)
        vn.abook.player.ui.components.Reveal(series?.hasRemote ?: (lead.remote != null)) {
            BasicText(ListenLogic.remotePlace(lead), style = Abook.type.caption)
        }
        val sub = when {
            !lead.textOnly && lead.chaptersAvailable == 0 -> vn.abook.player.ui.data.ProductionText.upcoming(lead)
            lead.producing -> vn.abook.player.ui.data.ProductionText.upcoming(lead)
            lead.textOnly && lead.author.isBlank() -> "Chỉ có chữ"
            single != null && single.twin -> ListenLogic.progressText(lead)
            else -> lead.author
        }
        if (sub.isNotEmpty()) BasicText(sub, style = Abook.type.caption)
    }
}

@Composable
private fun CoverChip(text: String, modifier: Modifier) {
    val colors = Abook.colors
    Box(modifier.clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bg.copy(alpha = 0.92f)).padding(horizontal = 6.dp, vertical = 2.dp)) {
        BasicText(text, style = Abook.type.caption.copy(color = colors.text, fontWeight = FontWeight.Medium))
    }
}
