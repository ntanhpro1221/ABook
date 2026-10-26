package vn.abook.player.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.ui.components.BookOpenIcon
import vn.abook.player.ui.components.DeleteBookPage
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.DashedCircleIcon
import vn.abook.player.ui.components.ExportIcon
import vn.abook.player.ui.components.PencilIcon
import vn.abook.player.ui.components.PlayPauseGlyph
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.SearchIcon
import vn.abook.player.ui.components.ShareIcon
import vn.abook.player.ui.components.TrashIcon
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.BookDetail
import vn.abook.player.ui.data.BookSearch
import vn.abook.player.ui.data.BookSource
import vn.abook.player.ui.data.ChapterLine
import vn.abook.player.ui.data.FindHit
import vn.abook.player.ui.data.FindProgress
import vn.abook.player.ui.data.FoldedChapter
import vn.abook.player.ui.data.Fmt
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import java.util.concurrent.ConcurrentHashMap

/** Các trang của bảng "Thêm": danh sách việc, xác nhận xoá. Đi sâu = trượt sang trái, Back = trượt ngược lại. */
private enum class MenuPage { Actions, Delete }

/**
 * Bảng "Thêm" của trang sách (thay menu "…" của bản React): đã nghe xong / chưa, sửa thông tin, chia sẻ file sách, xoá khỏi máy (có bước xác nhận NGAY trong bảng);
 * việc lõi native chưa làm được ở giao diện này đứng thành hàng "Sắp có" rõ ràng, không bấm được. `detail` null (trang chưa đọc xong): chỉ những việc không cần nó.
 */
@Composable
fun BookMenuSheet(book: ListenBook, detail: BookDetail?, source: BookSource, actions: BookScreenActions, dismiss: () -> Unit) {
    var page by remember { mutableStateOf(MenuPage.Actions) }
    BackHandler(enabled = page != MenuPage.Actions) { page = MenuPage.Actions }
    SheetPages(page, { it.ordinal }, "book_menu") { shown ->
        when (shown) {
            MenuPage.Actions -> MenuActions(book, detail, source, actions, dismiss, onEdit = { dismiss(); actions.edit(book) }, onDelete = { page = MenuPage.Delete })
            MenuPage.Delete -> DeletePage(book, source, actions, dismiss, onKeep = { page = MenuPage.Actions })
        }
    }
}

@Composable
private fun MenuActions(
    book: ListenBook,
    detail: BookDetail?,
    source: BookSource,
    actions: BookScreenActions,
    dismiss: () -> Unit,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    val colors = Abook.colors
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    var sharing by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth()) {
        BasicText(book.title, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        if (!book.textOnly) {
            val finished = book.progress.finished
            MenuRow(if (finished) "Chưa nghe xong" else "Đã nghe xong", tag = "menu_finished", onClick = {
                scope.launch {
                    source.setFinished(book.id, !finished)
                    dismiss()
                }
            }) { ink -> if (finished) DashedCircleIcon(ink) else CheckIcon(ink) }
        }
        MenuRow("Sửa thông tin", tag = "menu_edit", onClick = onEdit) { ink -> PencilIcon(ink) }
        if (detail?.canShare == true) {
            MenuRow(if (sharing) "Đang đóng file sách" else "Chia sẻ file sách", tag = "menu_share", onClick = {
                if (sharing) return@MenuRow
                sharing = true
                scope.launch {
                    val chooser = source.share(book.id)
                    sharing = false
                    problem = if (chooser == null) "Chưa đóng được file sách để chia sẻ." else ""
                    if (chooser != null) {
                        dismiss()
                        context.startActivity(chooser)
                    }
                }
            }) { ink -> ShareIcon(ink) }
        }
        // Có chữ để đọc theo (chương audio có kịch bản, hay sách chỉ có chữ) thì bấm được; sách chưa có chương nào nghe được thì mờ đi, không hứa gì.
        MenuRow("Đọc theo", tag = "menu_read", unavailable = !book.canReadAlong, onClick = {
            dismiss()
            actions.readAlong(book.id)
        }) { ink -> BookOpenIcon(ink) }
        MenuRow("Xuất MP3 hay M4B", tag = "menu_export", soon = true) { ink -> ExportIcon(ink) }
        Box(Modifier.fillMaxWidth().padding(vertical = Dim.s8).height(1.dp).background(colors.line))
        MenuRow("Xoá khỏi máy", tag = "menu_delete", danger = true, onClick = onDelete) { ink -> TrashIcon(ink) }
        if (problem.isNotEmpty()) {
            Spacer(Modifier.height(Dim.s4))
            BasicText(problem, style = Abook.type.bodySmall.copy(color = colors.danger))
        }
    }
}

/** Bước xác nhận xoá, ngay trong bảng ([DeleteBookPage] - cũng là bước xác nhận của danh sách Dung lượng). */
@Composable
private fun DeletePage(book: ListenBook, source: BookSource, actions: BookScreenActions, dismiss: () -> Unit, onKeep: () -> Unit) {
    DeleteBookPage(book.title, book.remote?.deviceName, { source.delete(book.id) }, { dismiss(); actions.deleted() }, onKeep)
}

/** Bảng của một chương ("…" cuối hàng): nghe từ đầu chương, đánh dấu đã nghe xong / chưa nghe. */
@Composable
fun ChapterSheet(book: ListenBook, chapter: ChapterLine, source: BookSource, onListenFromStart: () -> Unit, dismiss: () -> Unit) {
    val colors = Abook.colors
    val scope = rememberCoroutineScope()
    Column(Modifier.fillMaxWidth().testTag("chapter_sheet")) {
        BasicText(chapter.title, style = Abook.type.sectionTitle)
        BasicText(book.title, style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s8))
        if (chapter.playable) {
            MenuRow("Nghe từ đầu chương", tag = "chapter_from_start", onClick = {
                dismiss()
                onListenFromStart()
            }) { ink -> PlayPauseGlyph(false, ink, 20.dp) }
            MenuRow(if (chapter.done) "Chưa nghe" else "Đã nghe xong", tag = "chapter_done", onClick = {
                scope.launch {
                    source.setChapterDone(book.id, chapter.id, !chapter.done)
                    dismiss()
                }
            }) { ink -> if (chapter.done) DashedCircleIcon(ink) else CheckIcon(ink) }
        } else {
            BasicText("Chương này chưa có audio.", style = Abook.type.body.copy(color = colors.text2), modifier = Modifier.padding(vertical = Dim.s12))
        }
    }
}

/** Chờ người gõ ngừng tay chừng này (ms) rồi mới tìm. */
private const val TYPING_MS = 250L

/**
 * "Tìm trong sách": gõ chữ / câu, kết quả hiện dần theo thứ tự chương (cả câu, chỗ khớp tô hổ phách nhạt). Chạm một kết quả là nghe từ câu ấy (sách nói có mốc
 * từng câu), hay từ đầu chương (chương chỉ có chữ). Chữ đã chuẩn hoá chỉ giữ trong lúc bảng mở; tìm chạy ngoài luồng chính.
 */
@Composable
fun FindInBookSheet(detail: BookDetail, source: BookSource, onPick: (FindHit) -> Unit) {
    val colors = Abook.colors
    val focus = remember { FocusRequester() }
    val keyboard = LocalSoftwareKeyboardController.current
    var query by remember { mutableStateOf("") }
    var progress by remember { mutableStateOf<FindProgress?>(null) }
    val cache = remember { ConcurrentHashMap<Int, FoldedChapter>() }
    val bookId = detail.book.id
    val chapters = detail.chapters
    val titles = remember(chapters) { chapters.associate { it.id to it.title } }
    LaunchedEffect(Unit) {
        try {
            focus.requestFocus()
        } catch (_: IllegalStateException) {
            // Ô chưa gắn vào cây: người dùng chạm vào ô là có tiêu điểm.
        }
    }
    LaunchedEffect(query) {
        progress = null
        if (BookSearch.foldedQuery(query).isEmpty()) return@LaunchedEffect
        delay(TYPING_MS)
        withContext(Dispatchers.Default) {
            BookSearch.run(
                chapters,
                query,
                cache,
                load = { lot ->
                    for (chapter in lot) {
                        val passages = source.passages(bookId, chapter)
                        cache[chapter.id] = if (passages == null) FoldedChapter(emptyList(), emptyList(), failed = true) else BookSearch.folded(passages)
                    }
                },
                onUpdate = { progress = it },
            )
        }
    }
    Column(Modifier.fillMaxWidth().imePadding().testTag("find_sheet")) {
        BasicText("Tìm trong sách", style = Abook.type.sectionTitle)
        BasicText(detail.book.title, style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s12))
        Row(
            Modifier.fillMaxWidth().heightIn(min = Dim.s48).clip(RoundedCornerShape(Dim.radiusControl)).background(colors.bgSunken)
                .padding(horizontal = Dim.s12),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            SearchIcon(colors.text3)
            Spacer(Modifier.width(Dim.s8))
            BasicTextField(
                value = query,
                onValueChange = { query = it },
                modifier = Modifier.weight(1f).padding(vertical = Dim.s12).focusRequester(focus).testTag("find_field"),
                textStyle = Abook.type.body,
                cursorBrush = SolidColor(colors.accent),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { keyboard?.hide() }),
                decorationBox = { inner ->
                    Box(contentAlignment = Alignment.CenterStart) {
                        if (query.isEmpty()) BasicText("Chữ hay câu cần tìm", style = Abook.type.body.copy(color = colors.text3))
                        inner()
                    }
                },
            )
        }
        Spacer(Modifier.height(Dim.s8))
        BasicText(BookSearch.status(query, progress), style = Abook.type.caption.copy(color = colors.text2), modifier = Modifier.testTag("find_status"))
        val hits = progress?.hits.orEmpty()
        if (hits.isNotEmpty()) {
            Spacer(Modifier.height(Dim.s8))
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 360.dp).testTag("find_results")) {
                items(hits, key = { "${it.chapterId}:${it.index}" }, contentType = { "hit" }) { hit ->
                    FindRow(hit, titles[hit.chapterId].orEmpty(), onPick)
                }
            }
        }
    }
}

@Composable
private fun FindRow(hit: FindHit, chapterTitle: String, onPick: (FindHit) -> Unit) {
    val colors = Abook.colors
    val text = remember(hit, colors) {
        buildAnnotatedString {
            append(hit.text)
            if (hit.matchEnd > hit.matchStart && hit.matchEnd <= hit.text.length) {
                addStyle(SpanStyle(background = colors.accentSoft, color = colors.accentText, fontWeight = FontWeight.Bold), hit.matchStart, hit.matchEnd)
            }
        }
    }
    Column(Modifier.fillMaxWidth().pressable { onPick(hit) }.padding(vertical = Dim.s12).testTag("find_hit")) {
        // Chạm là nghe từ đâu: giờ phút của câu (sách nói), hay đầu chương (chương chỉ có chữ).
        val where = hit.start?.let { "$chapterTitle · ${Fmt.clock(it)}" } ?: "$chapterTitle · từ đầu chương"
        BasicText(where, style = Abook.type.caption.copy(color = colors.text2, fontWeight = FontWeight.Medium))
        Spacer(Modifier.height(Dim.s4))
        BasicText(text, style = Abook.type.bodySmall.copy(color = colors.text))
    }
}
