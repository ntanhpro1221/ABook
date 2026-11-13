package vn.abook.player.ui.screens

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import vn.abook.player.S

import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.ProgressFill
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.text.style.TextOverflow
import vn.abook.player.ui.data.CoverArt
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
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.semantics.clearAndSetSemantics
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
import androidx.compose.foundation.shape.RoundedCornerShape
import vn.abook.player.ui.components.BasicText
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
import vn.abook.player.ui.motion.bookCoverSource
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.BookCover
import vn.abook.player.ui.components.BookCoverShape
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
import vn.abook.player.ui.theme.coverOverlay
import kotlin.math.roundToInt
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.Reveal

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
    backEnabled: () -> Boolean = { true },
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
    SearchBack(ui, backEnabled)
    Box(modifier.fillMaxSize().onGloballyPositioned { coords[0] = it }) {
        LibraryGrid(books, ui, grid, covers, sheets, actions, top, recap) { coords[1] = it }
        SortMenu(ui, anchor, backEnabled)
    }
}

/** Back đóng ô tìm. Đọc `backEnabled` (trạng thái của tab / ngăn xếp) ở riêng chỗ này, để đổi tab không dựng lại cả màn Thư viện. */
@Composable
private fun SearchBack(ui: LibraryUiState, backEnabled: () -> Boolean) {
    BackHandler(enabled = backEnabled() && ui.searchOpen) { ui.closeSearch() }
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
    val widthDp = LocalConfiguration.current.screenWidthDp
    val columns = libraryColumns(widthDp)
    val cell = ((widthDp - 2f * Dim.margin.value - (columns - 1) * Dim.s12.value) / columns).dp
    val selected = remember(books, ui.filter, ui.query, ui.sort) { Library.view(books, ui.filter, ui.query, ui.sort) }
    LaunchedEffect(ui) { snapshotFlow { ui.pager.settledPage }.collect { ui.settled(it) } }
    Column(Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxWidth().padding(top = top, start = Dim.margin, end = Dim.margin)) {
            ScreenHeader(S.s_thu_vien_58145555, trailing = { AddBookButton(actions.addBook) }, bottomGap = if (books.isEmpty()) Dim.s16 else 0.dp)
            vn.abook.player.ui.components.Reveal(books.isNotEmpty()) { FilterBar(ui, selected.shown, onSortCoordinates) }
        }
        HorizontalPager(state = ui.pager, beyondViewportPageCount = if (books.isEmpty()) 0 else 1,
            modifier = Modifier.weight(1f).fillMaxWidth().clipToBounds().testTag("library_pages"),
            key = { LibraryFilter.entries[it] }) { page ->
            val filter = LibraryFilter.entries[page]
            val view = remember(books, filter, ui.query, ui.sort) { Library.view(books, filter, ui.query, ui.sort) }
            val tiles = rememberPresence(view.tiles) { it.key }
            val pageGrid = if (page == 0) grid else rememberLazyGridState()
            val active = page == ui.pager.currentPage
            Box(Modifier.fillMaxSize().then(if (active) Modifier else Modifier.clearAndSetSemantics {})) {
            LazyVerticalGrid(
                columns = GridCells.Fixed(columns), state = pageGrid,
                // The fixed header already keeps this viewport below the status bar.
                modifier = Modifier.fillMaxSize().then(if (active) Modifier.testTag("library_grid") else Modifier).fadeEdges(pageGrid, startInset = 0.dp),
                contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, top = Dim.s16, bottom = Dim.s24),
                horizontalArrangement = Arrangement.spacedBy(Dim.s12), verticalArrangement = Arrangement.spacedBy(Dim.s16),
            ) {
                if (recap != null) item(key = "recap", span = { GridItemSpan(maxLineSpan) }, contentType = "recap") { recap(books) }
                if (tiles.isEmpty()) {
                    item(key = "none", span = { GridItemSpan(maxLineSpan) }, contentType = "none") {
                            SwapContent(books, contentKey = { books -> books.isEmpty() }, layout = ContentLayout.Box) { books ->
                                if (books.isEmpty()) Column {
                                    BasicText(S.s_chua_co_sach_30843cb2, style = Abook.type.sectionTitle)
                                    RowHint(S.s_them_sach_cua_ban_de_bat_dau_nghe_ac868e6f)
                                    actions.connect?.let { TextAction(S.s_noi_may_ebc41ba4, it, "library_connect", align = Alignment.CenterStart) }
                                } else NoMatch(ui.query.trim(), filter)
                            }
                    }
                } else {
                    items(tiles, key = { it.item.key }, contentType = { if (it.item is ShelfTile.Series) "series" else "single" }) { tile ->
                        androidx.compose.animation.AnimatedVisibility(tile.visible, modifier = Modifier.animateItem(fadeInSpec = null, fadeOutSpec = null),
                            enter = androidx.compose.animation.fadeIn(tween(MotionMs.MEDIUM_OUT)) + slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 4 },
                            exit = androidx.compose.animation.fadeOut(tween(MotionMs.MEDIUM_OUT)) + slideOutVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { it / 4 }) {
                            BookTile(tile.item, covers, cell, sheets, actions, active)
                        }
                    }
                }
            }
            }
        }
    }
}

@Composable
private fun NoMatch(query: String, filter: LibraryFilter) {
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s32)) {
        BasicText(if (query.isEmpty()) S.s_chua_co_sach_30843cb2 else S.s_khong_tim_thay_sach_nao_khop_0_3e17643f(query), style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s4))
        BasicText(
            if (query.isNotEmpty()) S.s_thu_ten_sach_hoac_tac_gia_khac_65849efa else when (filter) {
                LibraryFilter.All -> S.s_thu_vien_chua_co_sach_nao_0d9c9f45
                LibraryFilter.Listening -> S.s_chua_nghe_do_cuon_nao_chon_mot_cuon_de_bat_eac6b96e
                LibraryFilter.New -> S.s_cuon_nao_cung_da_duoc_nghe_it_nhat_mot_doa_dfabac48
                LibraryFilter.Finished -> S.s_chua_co_cuon_nao_nghe_xong_8d430580
            },
            style = Abook.type.bodySmall,
        )
    }
}

/**
 * Một ô của lưới: bìa 2:3 (kèm dấu nguồn / số tập / vạch tiến độ), tên 2 dòng DÀNH SẴN, dòng phụ 1 dòng cắt "…" - mọi ô một hàng cao bằng nhau
 * (DESIGN.md §6, soát 10-11 L5/L11). Bìa tự vẽ đã in tên (và nhãn tập) thì dưới bìa chỉ còn dòng phụ, chỗ của tên vẫn giữ: không in tên hai lần, không in
 * "Tập 2" hai lần. The pager moves whole pages without deforming individual covers.
 */
@Composable
private fun BookTile(
    tile: ShelfTile,
    covers: CoverLoader,
    cell: Dp,
    sheets: SheetHost,
    actions: LibraryActions,
    active: Boolean,
) {
    val view = LocalView.current
    val series = tile as? ShelfTile.Series
    val single = tile as? ShelfTile.Single
    val lead = series?.first ?: single!!.book
    val title = series?.label ?: lead.title
    // Bìa tự vẽ (không ảnh) in tên sách ngay trên bìa: dưới bìa khỏi in lại.
    val drawn = lead.cover?.path == null
    val onClick = {
        if (series != null) sheets.show { dismiss -> SeriesSheet(series, covers, actions.openBook, dismiss) } else actions.openBook(lead)
    }
    val onLong = {
        vn.abook.player.Feedback.play("longPress", view)
        actions.playNow((series?.playTarget ?: lead).id)
    }
    Column(
        Modifier.fillMaxWidth()
            .pressable(onLongClick = onLong, onClick = onClick)
            .then(if (active) Modifier.testTag(if (series != null) "series_cell" else "book_cell") else Modifier),
    ) {
        Box(Modifier.fillMaxWidth().bookCoverSource(lead.id).clip(BookCoverShape).then(if (active) Modifier.testTag("library_cover") else Modifier)) {
            BookCover(lead.cover, title, if (series != null) null else lead.part, covers, cell, Modifier.fillMaxWidth())
            SwapContent(series, contentKey = { series -> series != null }, layout = ContentLayout.Box, modifier = Modifier.align(Alignment.BottomStart)) { series ->
                if (series != null) {
                    CoverChip("${series.books.size} ${series.unit}", Modifier.padding(Dim.s4).padding(bottom = 4.dp))
                } else SwapContent(single, drawn, title, lead, contentKey = { single, drawn, title, lead -> single?.badge != null && !(drawn && CoverArt.splitTitle(title, lead.part).second.isNotEmpty()) }, layout = ContentLayout.Box) { single, drawn, title, lead ->
                    if (single?.badge != null && !(drawn && CoverArt.splitTitle(title, lead.part).second.isNotEmpty())) {
                        CoverChip(single.badge, Modifier.padding(Dim.s4).padding(bottom = 4.dp))
                    }
                }
            }
            val fraction = if (series == null) lead.progress.fraction else 0f
            if (ProgressFill.of(fraction) > 0f && fraction < 0.995f) {
                // Một hình với web/Qt: vạch sát đáy, cao 4, rãnh --cover-overlay, cắt theo đúng khung bo của bìa (clip ở trên).
                val accent = Abook.colors.accent
                val track = Abook.colors.coverOverlay
                Box(
                    Modifier.align(Alignment.BottomStart).fillMaxWidth().height(Dim.s4).drawBehind {
                        drawRect(track)
                        drawRect(accent, Offset.Zero, Size(size.width * fraction, size.height))
                    },
                )
            }
        }
        Spacer(Modifier.height(Dim.s8))
        val detail = when {
            !lead.textOnly && lead.chaptersAvailable == 0 -> vn.abook.player.ui.data.ProductionText.upcoming(lead)
            lead.producing -> vn.abook.player.ui.data.ProductionText.upcoming(lead)
            lead.textOnly && lead.author.isBlank() -> S.s_chi_co_chu_bf879f2c
            single != null && single.twin -> ListenLogic.progressText(lead)
            else -> lead.author
        }
        // Sách ở máy khác: dấu máy tính nhỏ đầu dòng phụ như web/Qt (không đè lên bìa); nơi để nằm trong tên đọc màn hình của dấu ấy.
        val remote = series?.hasRemote ?: (lead.remote != null)
        val sub = detail
        val name: @Composable () -> Unit = {
            // cắt-có-chủ-ý: tên dưới bìa giữ đúng 2 dòng để mọi ô một hàng cao bằng nhau; tên đầy đủ ở trang sách và trình đọc màn hình.
            BasicText(title, Modifier.fillMaxWidth().testTag("tile_title"), style = Abook.type.label, minLines = 2, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
        val line: @Composable () -> Unit = {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dim.s4)) {
                SwapContent(remote, contentKey = { remote -> remote }, layout = ContentLayout.Row) { remote ->
                    if (remote) RemoteIcon(Abook.colors.text3, Modifier.semantics {
                        contentDescription = if (series != null) S.s_co_sach_tren_may_khac_3b7cdd88 else ListenLogic.remotePlace(lead)
                    }, size = 12.dp)
                }
                // cắt-có-chủ-ý: dòng phụ một dòng (tác giả / tình trạng), phần đầu là thứ quan trọng.
                BasicText(sub, Modifier.weight(1f).testTag("tile_sub"), style = Abook.type.caption, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
        if (drawn) {
            line()
            // Chỗ của tên vẫn dành sẵn (trong suốt, không đọc lên) để ô cao bằng ô có ảnh bìa bên cạnh.
            Box(Modifier.alpha(0f).clearAndSetSemantics { }) { name() }
        } else {
            name()
            line()
        }
    }
}

@Composable
private fun CoverChip(text: String, modifier: Modifier) {
    val colors = Abook.colors
    Box(modifier.clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bg.copy(alpha = 0.92f)).padding(horizontal = 8.dp, vertical = 4.dp)) {
        BasicText(text, style = Abook.type.caption.copy(color = colors.text, fontWeight = FontWeight.Medium))
    }
}
