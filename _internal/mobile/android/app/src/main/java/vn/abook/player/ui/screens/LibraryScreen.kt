package vn.abook.player.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyGridState
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.ScreenHeader
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.BookRow
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import kotlin.math.max

private val CoverShape = RoundedCornerShape(Dim.radiusCover)

/** Số cột: 2 trên máy hẹp (<360 dp), 3 từ 360 dp, thêm một cột mỗi 120 dp (DESIGN.md §6 "Lưới bìa": điện thoại 2-3 cột). */
internal fun libraryColumns(widthDp: Int): Int = (widthDp / 120).coerceAtLeast(2)

/** Thư viện (P0): lưới bìa thật của lõi. `key` + `contentType` cho mọi mục; bìa nạp ngoài luồng chính, vẽ trong pha vẽ. */
@Composable
fun LibraryScreen(
    state: LibraryState,
    grid: LazyGridState,
    covers: CoverLoader,
    onOpen: (BookRow) -> Unit,
    modifier: Modifier = Modifier,
) {
    val books = (state as? LibraryState.Ready)?.books ?: return Box(modifier.fillMaxSize())
    val top = WindowInsets.statusBars.asPaddingValues().calculateTopPadding()
    if (books.isEmpty()) {
        Column(modifier.fillMaxSize().padding(top = top, start = Dim.margin, end = Dim.margin)) {
            ScreenHeader("Thư viện")
            BasicText("Chưa có sách", style = Abook.type.sectionTitle)
            Spacer(Modifier.height(Dim.s4))
            BasicText("Thêm sách để bắt đầu nghe.", style = Abook.type.bodySmall)
        }
        return
    }
    val widthDp = LocalConfiguration.current.screenWidthDp
    val columns = libraryColumns(widthDp)
    val density = LocalDensity.current
    val cell = (widthDp - 2f * Dim.margin.value - (columns - 1) * Dim.s12.value) / columns
    val coverWidth = with(density) { cell.dp.roundToPx() }
    val coverHeight = coverWidth * 3 / 2
    LazyVerticalGrid(
        columns = GridCells.Fixed(columns),
        state = grid,
        modifier = modifier.fillMaxSize().testTag("library_grid"),
        contentPadding = PaddingValues(start = Dim.margin, end = Dim.margin, top = top, bottom = Dim.s24),
        horizontalArrangement = Arrangement.spacedBy(Dim.s12),
        verticalArrangement = Arrangement.spacedBy(Dim.s16),
    ) {
        item(key = "header", span = { GridItemSpan(maxLineSpan) }, contentType = "header") {
            ScreenHeader("Thư viện", subtitle = "${books.size} cuốn")
        }
        items(books, key = { it.id }, contentType = { "book" }) { book ->
            BookCell(book, covers, coverWidth, coverHeight, onOpen)
        }
    }
}

@Composable
private fun BookCell(book: BookRow, covers: CoverLoader, widthPx: Int, heightPx: Int, onOpen: (BookRow) -> Unit) {
    Column(Modifier.fillMaxWidth().pressable { onOpen(book) }.testTag("book_cell")) {
        BookCover(book, covers, widthPx, heightPx, Modifier.fillMaxWidth())
        Spacer(Modifier.height(Dim.s8))
        BasicText(book.title, style = Abook.type.label, maxLines = 2, overflow = TextOverflow.Ellipsis)
        if (book.author.isNotEmpty()) BasicText(book.author, style = Abook.type.caption, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

/** Bìa 2:3 bo 12: ảnh thật (nạp ngoài luồng chính) hoặc ô chìm với chữ cái đầu. Ảnh đọc trong pha vẽ - nạp xong chỉ vẽ lại ô này. */
@Composable
fun BookCover(book: BookRow, covers: CoverLoader, widthPx: Int, heightPx: Int, modifier: Modifier = Modifier) {
    val path = book.coverPath
    val key = remember(path, book.coverStamp, widthPx) { path?.let { covers.key(it, book.coverStamp, widthPx) } }
    val image = remember(key) { mutableStateOf(key?.let(covers::peek)) }
    if (key != null && path != null && image.value == null) {
        LaunchedEffect(key) { image.value = covers.load(key, path, widthPx, heightPx) }
    }
    val sunken = Abook.colors.bgSunken
    Box(
        modifier.aspectRatio(2f / 3f).clip(CoverShape).background(sunken).drawBehind { image.value?.let { drawCover(it) } },
        contentAlignment = Alignment.Center,
    ) {
        if (path == null) {
            val letter = remember(book.title) { book.title.trim().firstOrNull()?.uppercaseChar()?.toString().orEmpty() }
            BasicText(letter, style = Abook.type.screenTitle.copy(color = Abook.colors.fg3))
        }
    }
}

/** Vẽ ảnh phủ kín ô, cắt giữa nếu tỉ lệ khác (không cấp phát: IntOffset / IntSize là giá trị). */
private fun DrawScope.drawCover(image: ImageBitmap) {
    val dw = size.width.toInt()
    val dh = size.height.toInt()
    if (dw <= 0 || dh <= 0) return
    val scale = max(dw.toFloat() / image.width, dh.toFloat() / image.height)
    val sw = (dw / scale).toInt().coerceIn(1, image.width)
    val sh = (dh / scale).toInt().coerceIn(1, image.height)
    drawImage(
        image,
        srcOffset = IntOffset((image.width - sw) / 2, (image.height - sh) / 2),
        srcSize = IntSize(sw, sh),
        dstSize = IntSize(dw, dh),
        filterQuality = FilterQuality.Low,
    )
}
