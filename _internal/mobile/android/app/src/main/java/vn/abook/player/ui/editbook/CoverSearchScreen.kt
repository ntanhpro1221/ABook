package vn.abook.player.ui.editbook

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.grid.rememberLazyGridState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.data.ListenLogic
import vn.abook.player.ui.devices.CreepProgress
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/*
 * "Tìm ảnh bìa" của Sửa sách (web: CoverSearchPanel - một bước của hộp Sửa sách, ở đây là một màn con, Back về Sửa sách): iTunes, Open Library, Google Books theo tên
 * bộ truyện, qua đúng đường lõi bản web gọi (`GET /cover/search`, `PUT /cover {url}` của LocalStudio). Truyện mạng dịch thường không có trên các nguồn này, nên chỉ là gợi
 * ý: bạn chọn, không bao giờ tự đặt. Không có ảnh nào thì mời chọn ảnh trên máy (rồi cắt như "Chọn ảnh").
 */

/** Màn tìm bìa của một cuốn. Bìa đổi trong lúc màn này đứng trên cùng (ảnh tìm được, hay ảnh trên máy vừa cắt xong) là xong việc: về Sửa sách. */
@Composable
fun CoverSearchRoute(editor: BookEditor, fallbackTitle: String, onBack: () -> Unit, crop: (String) -> Unit, active: Boolean = true) {
    val state by editor.state.collectAsState()
    val ui by editor.covers.collectAsState()
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri -> uri?.let { crop(it.toString()) } }
    // Một lần rời màn, dù bìa đổi và lời "đã đặt" về cùng lúc.
    val left = remember { booleanArrayOf(false) }
    val leave: () -> Unit = { if (!left[0]) { left[0] = true; onBack() } }
    // Bìa lúc mở màn (ghi khi sách đã đọc xong): khác nó là bìa vừa đổi.
    val firstCover = remember { ArrayList<CoverRef?>(1) }
    state.saved?.let { if (firstCover.isEmpty()) firstCover += it.cover }
    LaunchedEffect(editor) {
        val title = editor.state.value.saved?.title ?: fallbackTitle
        editor.openCoverSearch(ListenLogic.seriesOf(title).series.ifEmpty { title })
    }
    DisposableEffect(editor) { onDispose { editor.stopCoverSearch() } }
    LaunchedEffect(active, state.saved?.cover) { if (active && firstCover.isNotEmpty() && state.saved?.cover != firstCover[0]) leave() }
    CoverSearchScreen(
        ui, leave, editor::setCoverQuery, editor::searchCovers, { found -> editor.chooseCover(found) { leave() } },
        { picker.launch(arrayOf("image/*")) }, editor::thumbnail,
    )
}

private enum class CoverStage { Searching, Failed, Nothing, Found }

@Composable
fun CoverSearchScreen(
    ui: CoverSearchUi, onBack: () -> Unit, setQuery: (String) -> Unit, search: () -> Unit, choose: (FoundCover) -> Unit, pickFile: () -> Unit,
    thumbnail: suspend (String) -> ImageBitmap?,
) {
    BookForm("Tìm ảnh bìa", onBack, "cover_search_screen", footer = {
        InlineProblem(if (ui.failed.isNotEmpty() && !ui.searching) "Bạn hãy kiểm tra kết nối rồi tìm lại các nguồn bìa." else "", search, "cover_sources_problem")
        InlineProblem(if (ui.unset != null) "Bạn hãy kiểm tra kết nối rồi đặt lại ảnh bìa." else "", ui.unset?.let { found -> { choose(found) } }, "cover_choose_problem")
    }) {
        RowHint("Bạn chọn ảnh từ các nguồn sách hoặc trên máy.", Modifier.padding(top = Dim.s4))
        Spacer(Modifier.height(Dim.s12))
        BookField(
            null, ui.query, setQuery, "cover_query", description = "Tên sách để tìm bìa", placeholder = "Tên sách (tiếng Anh thường cho nhiều kết quả hơn)",
            trailing = { TextAction("Tìm", search, "cover_search_go") },
        )
        val stage = when {
            ui.searching || !ui.searched -> CoverStage.Searching
            ui.error -> CoverStage.Failed
            ui.nothing -> CoverStage.Nothing
            else -> CoverStage.Found
        }
        // Khung chờ -> kết quả (hay lời mời chọn ảnh trên máy): trượt lên ngắn, không thay cứng.
        AnimatedContent(
            targetState = stage,
            transitionSpec = {
                (slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 8 } + fadeIn(tween(MotionMs.MEDIUM)))
                    .togetherWith(slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it / 8 } + fadeOut(tween(MotionMs.FAST_OUT)))
                    .using(SizeTransform(clip = false))
            },
            label = "cover-search",
            modifier = Modifier.weight(1f).fillMaxWidth().padding(top = Dim.s16),
        ) { shown ->
            when (shown) {
                CoverStage.Searching -> CoverSkeleton()
                CoverStage.Failed -> Column(Modifier.fillMaxWidth()) {
                    InlineProblem("Bạn hãy kiểm tra kết nối rồi tìm lại ảnh bìa.", search, "cover_search_problem")
                }
                CoverStage.Nothing -> Column(Modifier.fillMaxWidth().padding(top = Dim.s24).testTag("cover_nothing"), horizontalAlignment = Alignment.CenterHorizontally) {
                    BasicText("Bạn hãy chọn ảnh trên máy", style = Abook.type.sectionTitle)
                    Spacer(Modifier.height(Dim.s16))
                    PrimaryButton("Chọn ảnh", pickFile, Modifier.fillMaxWidth().testTag("cover_pick_file"))
                }
                CoverStage.Found -> CoverGrid(ui, choose, thumbnail)
            }
        }
    }
}

/** Lưới ảnh tìm được: ô 2:3 bo như điều khiển, tên dưới ảnh tối đa hai dòng, nguồn một dòng. Ảnh đang được đặt làm bìa thì mờ đi; lúc ấy không chọn ảnh khác được. */
@Composable
private fun CoverGrid(ui: CoverSearchUi, choose: (FoundCover) -> Unit, thumbnail: suspend (String) -> ImageBitmap?) {
    val grid = rememberLazyGridState()
    LazyVerticalGrid(
        columns = GridCells.Adaptive(120.dp),
        state = grid,
        modifier = Modifier.fillMaxSize().testTag("cover_results").fadeEdges(grid),
        contentPadding = PaddingValues(bottom = Dim.s16),
        horizontalArrangement = Arrangement.spacedBy(Dim.s12),
        verticalArrangement = Arrangement.spacedBy(Dim.s16),
    ) {
        items(ui.shown, key = { it.url }, contentType = { "cover" }) { found ->
            FoundCoverTile(found, ui.choosing, choose, thumbnail)
        }
    }
}

@Composable
private fun FoundCoverTile(found: FoundCover, choosing: String?, choose: (FoundCover) -> Unit, thumbnail: suspend (String) -> ImageBitmap?) {
    val colors = Abook.colors
    val image by produceState<ImageBitmap?>(null, found.thumb) { value = thumbnail(found.thumb) }
    val busy = choosing == found.url
    // Đang đặt một ảnh: không chọn ảnh khác được; ảnh đang đặt có thanh "đang làm" ngay dưới (không làm mờ cả lưới - đổi chỉ bằng độ mờ là cứng).
    Column(
        Modifier.fillMaxWidth().then(if (choosing == null) Modifier.pressable { choose(found) } else Modifier.semantics { disabled() })
            .semantics { contentDescription = if (found.author.isEmpty()) "${found.title} (${found.provider})" else "${found.title} - ${found.author} (${found.provider})" }
            .testTag("cover_found_${found.url}"),
    ) {
        Box(Modifier.fillMaxWidth().aspectRatio(2f / 3f).clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bgSunken)) {
            image?.let { Image(it, null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
        }
        Reveal(busy) { Box(Modifier.fillMaxWidth().semantics { contentDescription = "Đang đặt ảnh bìa" }.testTag("cover_setting")) { CreepProgress() } }
        BasicText(found.title, style = Abook.type.caption.copy(color = colors.text), modifier = Modifier.padding(top = Dim.s8))
        BasicText(found.provider, style = Abook.type.caption.copy(color = colors.text3))
    }
}

/** Đang tìm: khung xám đúng hình bốn ô bìa (DESIGN.md §2 "đang tải"), không vòng xoay. */
@Composable
private fun CoverSkeleton() {
    val colors = Abook.colors
    Column(Modifier.fillMaxWidth().semantics { contentDescription = "Đang tìm ảnh bìa" }.testTag("cover_searching")) {
        for (row in 0 until 2) {
            androidx.compose.foundation.layout.Row(Modifier.fillMaxWidth().padding(bottom = Dim.s16), horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
                for (cell in 0 until 2) {
                    Box(Modifier.weight(1f).aspectRatio(2f / 3f).clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bgSunken))
                }
            }
        }
    }
}
