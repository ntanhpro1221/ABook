package vn.abook.player.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.PlayPauseGlyph
import vn.abook.player.ui.components.RemoteIcon
import vn.abook.player.ui.components.ScreenHeader
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.Library
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.ListenLogic
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.data.ShelfTile
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.roundToInt

/** Việc mà Thư viện nhờ nơi khác làm (mở trang sách, phát, mở trình phát, thêm sách) - tách khỏi màn để thử và để dựng ảnh chụp. */
@Stable
class LibraryActions(
    val openBook: (ListenBook) -> Unit,
    val togglePlay: (String) -> Unit,
    val playNow: (String) -> Unit,
    val openNowPlaying: () -> Unit,
    val addBook: () -> Unit,
)

/** Số cột: 2 trên máy hẹp (<360 dp), 3 từ 360 dp, thêm một cột mỗi 120 dp (DESIGN.md §6 "Lưới bìa": điện thoại 2-3 cột). */
internal fun libraryColumns(widthDp: Int): Int = (widthDp / 120).coerceAtLeast(2)

/**
 * Thư viện (DESIGN.md §7): đầu màn + "Thêm sách", hàng "Đang nghe" lớn, bộ lọc / xếp / tìm, lưới bìa luôn mở (bộ nhiều tập gom một bìa, chạm mở bảng các tập,
 * giữ bìa là phát). Mọi mục lưới có `key` + `contentType`; chuyển động chạy theo khung (vạch, trượt lưới, ô tìm) chỉ đọc trong pha vẽ / dàn trang.
 */
@Composable
fun LibraryScreen(
    state: LibraryState,
    ui: LibraryUiState,
    grid: LazyGridState,
    player: PlayerState,
    covers: CoverLoader,
    sheets: SheetHost,
    actions: LibraryActions,
    modifier: Modifier = Modifier,
    backEnabled: Boolean = true,
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
        if (books.isEmpty()) {
            Column(Modifier.fillMaxSize().padding(top = top, start = Dim.margin, end = Dim.margin)) {
                ScreenHeader("Thư viện", trailing = { AddBookButton(actions.addBook) })
                BasicText("Chưa có sách", style = Abook.type.sectionTitle)
                Spacer(Modifier.height(Dim.s4))
                BasicText("Thêm sách để bắt đầu nghe.", style = Abook.type.bodySmall)
            }
        } else {
            LibraryGrid(books, ui, grid, player, covers, sheets, actions, top) { coords[1] = it }
        }
        SortMenu(ui, anchor, backEnabled)
    }
}

@Composable
private fun LibraryGrid(
    books: List<ListenBook>,
    ui: LibraryUiState,
    grid: LazyGridState,
    player: PlayerState,
    covers: CoverLoader,
    sheets: SheetHost,
    actions: LibraryActions,
    top: Dp,
    onSortCoordinates: (LayoutCoordinates) -> Unit,
) {
    val view = remember(books, ui.shown, ui.query, ui.sort, player.bookId) {
        Library.view(books, ui.shown, ui.query, ui.sort, player.bookId.ifEmpty { null })
    }
    val widthDp = LocalConfiguration.current.screenWidthDp
    val columns = libraryColumns(widthDp)
    val cell = ((widthDp - 2f * Dim.margin.value - (columns - 1) * Dim.s12.value) / columns).dp
    val gridWidthPx = with(LocalDensity.current) { widthDp.dp.toPx() }
    LazyVerticalGrid(
        columns = GridCells.Fixed(columns),
        state = grid,
        modifier = Modifier.fillMaxSize().testTag("library_grid"),
        contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, top = top, bottom = Dim.s24),
        horizontalArrangement = Arrangement.spacedBy(Dim.s12),
        verticalArrangement = Arrangement.spacedBy(Dim.s16),
    ) {
        item(key = "header", span = { GridItemSpan(maxLineSpan) }, contentType = "header") {
            ScreenHeader("Thư viện", subtitle = "${books.size} cuốn", trailing = { AddBookButton(actions.addBook) })
        }
        view.listening?.let { book ->
            item(key = "continue", span = { GridItemSpan(maxLineSpan) }, contentType = "continue") {
                ContinueRow(book, player, covers, actions, Modifier.padding(bottom = Dim.s8))
            }
        }
        item(key = "filters", span = { GridItemSpan(maxLineSpan) }, contentType = "filters") {
            FilterBar(ui, onSortCoordinates)
        }
        if (view.tiles.isEmpty()) {
            item(key = "none", span = { GridItemSpan(maxLineSpan) }, contentType = "none") { NoMatch() }
        } else {
            items(view.tiles, key = { it.key }, contentType = { if (it is ShelfTile.Series) "series" else "single" }) { tile ->
                BookTile(tile, ui, covers, cell, gridWidthPx, sheets, actions)
            }
        }
    }
}

@Composable
private fun NoMatch() {
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s32)) {
        BasicText("Không có sách nào", style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s4))
        BasicText("Thử bộ lọc hay từ khoá khác.", style = Abook.type.bodySmall)
    }
}

/**
 * "Đang nghe": hàng lớn không khung - bìa, tên, chỗ nghe tiếp, vạch tiến độ, nút phát tròn. Chạm hàng là nghe tiếp (đang phát rồi thì mở trình phát); nút tròn phát / dừng.
 */
@Composable
private fun ContinueRow(book: ListenBook, player: PlayerState, covers: CoverLoader, actions: LibraryActions, modifier: Modifier) {
    val colors = Abook.colors
    val current = player.bookId == book.id
    val playing = current && player.playing
    val resume = book.resume
    val where = when {
        current && player.chapterTitle.isNotEmpty() -> player.chapterTitle
        resume != null -> Fmt.resumeWhere(resume.chapterTitle, resume.at)
        else -> ListenLogic.progressText(book)
    }
    val fraction = book.progress.fraction
    Row(
        modifier.fillMaxWidth().pressable { if (playing) actions.openNowPlaying() else actions.playNow(book.id) }.testTag("continue_row"),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BookCover(book.cover, book.title, book.part, covers, 80.dp, Modifier.width(80.dp))
        Spacer(Modifier.width(Dim.s16))
        Column(Modifier.weight(1f)) {
            BasicText("Đang nghe", style = Abook.type.caption.copy(color = colors.accentText, fontWeight = FontWeight.Medium))
            BasicText(book.title, style = Abook.type.sectionTitle)
            BasicText(where, style = Abook.type.bodySmall)
            Spacer(Modifier.height(Dim.s8))
            Box(
                Modifier.fillMaxWidth().height(3.dp).clip(RoundedCornerShape(2.dp)).drawBehind {
                    drawRect(colors.line)
                    drawRect(colors.accent, Offset.Zero, Size(size.width * fraction, size.height))
                },
            )
            if (book.remote != null) {
                Spacer(Modifier.height(Dim.s4))
                BasicText(ListenLogic.remotePlace(book), style = Abook.type.caption)
            }
        }
        Spacer(Modifier.width(Dim.s12))
        Box(
            Modifier.size(56.dp).pressable { actions.togglePlay(book.id) }.clip(CircleShape).background(colors.accent)
                .semantics { contentDescription = if (playing) "Tạm dừng" else "Phát" }.testTag("continue_play"),
            contentAlignment = Alignment.Center,
        ) {
            PlayPauseGlyph(playing, colors.accentInk, 28.dp)
        }
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
                    RemoteIcon(Color.White)
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
        val sub = when {
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
