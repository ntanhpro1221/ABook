package vn.abook.player.ui.screens

import vn.abook.player.S

import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.formatSize

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
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.platform.LocalDensity
import vn.abook.player.ui.nowplaying.ReadInk
import vn.abook.player.ui.nowplaying.drawInkRects
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
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
import vn.abook.player.ui.components.ReadAlongIcon
import vn.abook.player.ui.components.ArrowRightLeftIcon
import vn.abook.player.ui.components.PlusIcon
import vn.abook.player.ui.components.TextCursorInputIcon
import vn.abook.player.ui.data.RecordAction
import vn.abook.player.ui.components.DeleteBookPage
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.DashedCircleIcon
import vn.abook.player.ui.components.BookAudioIcon
import vn.abook.player.ui.components.FolderDownIcon
import vn.abook.player.ui.components.HeadphonesIcon
import vn.abook.player.ui.components.MusicIcon
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.components.PencilIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.PlayPauseGlyph
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.SearchIcon
import vn.abook.player.ui.components.ShareIcon
import vn.abook.player.ui.components.ExportIcon
import vn.abook.player.ui.components.SaveIcon
import vn.abook.player.ui.components.TrashIcon
import vn.abook.player.ui.data.BookNotes
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
import vn.abook.player.ui.music.MusicKind
import vn.abook.player.ui.music.MusicPanel
import vn.abook.player.ui.music.MusicState
import vn.abook.player.ui.music.MusicText
import vn.abook.player.ui.music.PlayerMusic
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.insetSurface
import java.util.concurrent.ConcurrentHashMap
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

/** Các trang của bảng "Thêm": danh sách việc, nhạc nền của cuốn, xác nhận xoá. Đi sâu = trượt sang trái, Back = trượt ngược lại. */
private enum class MenuPage { Actions, Music, SaveAs, Delete }

/**
 * Bảng "Thêm" của trang sách (thay menu "…" của bản React): đã nghe xong / chưa, sửa thông tin, chia sẻ file sách, xoá khỏi máy (có bước xác nhận NGAY trong bảng);
 * việc cuốn này không làm được đứng thành hàng nhạt, không bấm được. `detail` null (trang chưa đọc xong): chỉ những việc không cần nó.
 */
@Composable
fun BookMenuSheet(
    book: ListenBook, detail: BookDetail?, source: BookSource, actions: BookScreenActions, dismiss: () -> Unit,
    music: MusicState? = null, playerMusic: PlayerMusic? = null, onRecord: (RecordAction) -> Unit = {}, notes: BookNotes? = null,
) {
    var page by remember { mutableStateOf(MenuPage.Actions) }
    // Một lần lưu cho cả hai đường (Lưu thay đổi ở trang việc, Lưu thành ở trang riêng): hộp chọn chỗ lưu của hệ thống trả về cùng một nơi.
    val save = rememberBookSave(book.id, source, notes, dismiss)
    BackHandler(enabled = page != MenuPage.Actions) { page = MenuPage.Actions }
    SheetPages(page, { it.ordinal }, "book_menu") { shown ->
        when (shown) {
            MenuPage.Actions -> MenuActions(
                book, detail, source, actions, dismiss, music, onEdit = { dismiss(); actions.edit(book) },
                onMusic = { page = MenuPage.Music }, onDelete = { page = MenuPage.Delete }, onRecord = onRecord,
                save = save, onSaveAs = { page = MenuPage.SaveAs },
            )
            MenuPage.SaveAs -> if (detail != null) SaveAsPage(detail, save)
            MenuPage.Music -> if (music != null) Column(Modifier.fillMaxWidth()) {
                BasicText(S.s_nhac_nen_271fb292, style = Abook.type.sectionTitle)
                RowHint(book.title)
                Spacer(Modifier.height(Dim.s8))
                MusicPanel(music, book.id, playerMusic)
            }
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
    music: MusicState?,
    onEdit: () -> Unit,
    onMusic: () -> Unit,
    onDelete: () -> Unit,
    onRecord: (RecordAction) -> Unit,
    save: BookSaveRun,
    onSaveAs: () -> Unit,
) {
    val colors = Abook.colors
    val scope = rememberCoroutineScope()
    // Hàng "Nhạc nền" nói ngay cuốn này đang nghe gì: sách chỉ có chữ chọn danh sách phát, sách nói theo nhạc người làm sách gắn; không có nhạc thì không có hàng.
    if (music != null) LaunchedEffect(book.id) { music.open(book.id) }
    val context = LocalContext.current
    var sharing by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    Column(Modifier.fillMaxWidth()) {
        BasicText(book.title, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s8))
        // Một hồ sơ thì không có chip "Hồ sơ nghe": các việc với hồ sơ duy nhất nằm ở đây (web: singleRecordActions); xoá hồ sơ ở cuối, cạnh xoá sách.
        val onlyRecord = detail?.records?.takeIf { it.size == 1 }
        if (onlyRecord != null) {
            MenuRow(S.s_ho_so_moi_5dfda9aa, tag = "menu_record_create", onClick = { onRecord(RecordAction.Create) }) { ink -> PlusIcon(ink) }
            MenuRow(S.s_chuyen_ho_so_a1c66184, tag = "menu_record_move", onClick = { onRecord(RecordAction.Move) }) { ink -> ArrowRightLeftIcon(ink) }
            MenuRow(S.s_doi_ten_ho_so_92440dab, tag = "menu_record_rename", onClick = { onRecord(RecordAction.Rename) }) { ink -> TextCursorInputIcon(ink) }
        }
        if (!book.textOnly) {
            val finished = book.progress.finished
            MenuRow(if (finished) S.s_chua_nghe_xong_6b821209 else S.s_da_nghe_xong_d276b702, tag = "menu_finished", onClick = {
                scope.launch {
                    source.setFinished(book.id, !finished)
                    dismiss()
                }
            }) { ink -> if (finished) DashedCircleIcon(ink) else CheckIcon(ink) }
        }
        MenuRow(S.s_sua_thong_tin_17e4a8a6, tag = "menu_edit", onClick = onEdit) { ink -> PencilIcon(ink) }
        MenuRow(S.s_giong_va_loi_doc_450320f6, "menu_studio_edit", unavailable = true,
            hint = if (book.remote != null) S.s_sua_o_may_goc_1a65caf0 else S.s_lam_o_studio_tren_may_tinh_c89f87a5) { ink -> PencilIcon(ink) }
        // Cuốn mở từ file / làm trên máy lưu được thành file sách kèm thay đổi của bạn (web: Lưu thay đổi, Lưu thành). "Lưu thay đổi" chỉ bấm được khi có gì để lưu.
        if (detail?.canShare == true) {
            MenuRow(
                S.s_luu_thay_doi_48ee3bfe, tag = "menu_save", unavailable = detail.unsaved == 0 || save.busy,
                hint = if (save.busy) S.s_dang_luu_e93f245d else null, onClick = save::saveKept,
            ) { ink -> SaveIcon(ink) }
            MenuRow(S.s_luu_thanh_13374e92, tag = "menu_save_as", onClick = onSaveAs) { ink -> ExportIcon(ink) }
        }
        if (detail?.canShare == true) {
            MenuRow(if (sharing) S.s_dang_dong_file_sach_6d7ee4ad else S.s_chia_se_8811b78c, tag = "menu_share", onClick = {
                if (sharing) return@MenuRow
                sharing = true
                scope.launch {
                    val chooser = source.share(book.id)
                    sharing = false
                    problem = if (chooser == null) S.s_chua_chia_se_duoc_sach_9b8501da else ""
                    if (chooser != null) {
                        dismiss()
                        context.startActivity(chooser)
                    }
                }
            }) { ink -> ShareIcon(ink) }
        }
        // Có chữ để đọc theo (chương audio có kịch bản, hay sách chỉ có chữ) thì bấm được; sách chưa có chương nào nghe được thì mờ đi, không hứa gì.
        MenuRow(S.s_doc_theo_df342819, tag = "menu_read", unavailable = !book.canReadAlong, onClick = {
            dismiss()
            actions.readAlong(book.id)
        }) { ink -> ReadAlongIcon(ink) }
        if (music != null) {
            val ui by music.ui.collectAsState()
            val mine = ui.book.takeIf { ui.bookId == book.id }
            // Hiện khi đã biết cuốn có nhạc (trượt vào cùng giá trị, không hiện hàng trống rồi điền sau); đọc hỏng thì vẫn hiện để vào trang thử lại.
            Reveal((mine != null && mine.kind != MusicKind.None) || (ui.failed && ui.bookId == book.id)) {
                MenuRow(S.s_nhac_nen_271fb292, tag = "menu_music", onClick = onMusic, value = MusicText.value(mine, ui.menu)) { ink -> MusicIcon(ink) }
            }
        }
        // Như web: sách có tiếng có hai hàng "Xuất MP3" / "Xuất M4B", sách chỉ có chữ có một hàng "Xuất sách nói" - mỗi hàng đúng icon của web.
        // Cuốn chưa có gì để xuất thì mờ đi, không hứa gì.
        val exportHint by actions.exportHint(book.id).collectAsState()
        if (book.textOnly) {
            MenuRow(
                S.s_xuat_sach_noi_219fb12a, tag = "menu_export", hint = exportHint, unavailable = book.chaptersTotal == 0,
                onClick = {
                    dismiss()
                    actions.export(book, null)
                },
            ) { ink -> HeadphonesIcon(ink) }
        } else {
            MenuRow(
                S.s_xuat_mp3_60946614, tag = "menu_export_mp3", hint = exportHint, unavailable = book.chaptersAvailable == 0,
                onClick = {
                    dismiss()
                    actions.export(book, ExportFormat.Mp3)
                },
            ) { ink -> FolderDownIcon(ink) }
            MenuRow(
                S.s_xuat_m4b_4a708187, tag = "menu_export_m4b", hint = exportHint, unavailable = book.chaptersAvailable == 0,
                onClick = {
                    dismiss()
                    actions.export(book, ExportFormat.M4b)
                },
            ) { ink -> BookAudioIcon(ink) }
        }
        Box(Modifier.fillMaxWidth().padding(vertical = Dim.s8).height(1.dp).background(colors.line))
        if (onlyRecord != null) MenuRow(S.s_xoa_ho_so_38a06d83, tag = "menu_record_delete", danger = true, onClick = { onRecord(RecordAction.Delete) }) { ink -> TrashIcon(ink) }
        // Cỡ về sau khi tấm đã mở: dòng phụ hiện dần tại chỗ (web: "Chiếm 148 MB" bên phải hàng).
        var bytes by remember { mutableStateOf<Long?>(null) }
        LaunchedEffect(book.id) { bytes = source.bytes(book.id) }
        MenuRow(S.s_xoa_khoi_thu_vien_79dbd32b, tag = "menu_delete", danger = true, hint = bytes?.let { S.s_chiem_0_ebd89982(formatSize(it)) }, onClick = onDelete) { ink -> TrashIcon(ink) }
        Reveal(save.problem.isNotEmpty()) { BasicText(save.problem, style = Abook.type.bodySmall.copy(color = colors.danger), modifier = Modifier.testTag("save_problem")) }
        Reveal(problem.isNotEmpty()) {
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
fun ChapterSheet(book: ListenBook, chapter: ChapterLine, source: BookSource, onListenFromStart: () -> Unit, dismiss: () -> Unit, notes: BookNotes? = null) {
    val colors = Abook.colors
    val scope = rememberCoroutineScope()
    var renaming by remember { mutableStateOf(false) }
    if (renaming) return RenameChapterPage(book, chapter, source, notes, dismiss) { renaming = false }
    Column(Modifier.fillMaxWidth().testTag("chapter_sheet")) {
        BasicText(chapter.title, style = Abook.type.sectionTitle)
        RowHint(book.title)
        Spacer(Modifier.height(Dim.s8))
        if (chapter.playable) {
            MenuRow(S.s_nghe_tu_dau_chuong_06c66bfc, tag = "chapter_from_start", onClick = {
                dismiss()
                onListenFromStart()
            }) { ink -> PlayPauseGlyph(false, ink, 20.dp) }
            MenuRow(if (chapter.done) S.s_chua_nghe_2fbea4c8 else S.s_da_nghe_xong_d276b702, tag = "chapter_done", onClick = {
                scope.launch {
                    source.setChapterDone(book.id, chapter.id, !chapter.done)
                    dismiss()
                }
            }) { ink -> if (chapter.done) DashedCircleIcon(ink) else CheckIcon(ink) }
        } else {
            BasicText(S.s_chuong_nay_chua_co_audio_53a41b55, style = Abook.type.body.copy(color = colors.text2), modifier = Modifier.padding(vertical = Dim.s12))
        }
        // Sách nghe thẳng từ máy khác thì tên chương sửa ở máy giữ sách (web: canEditLayer).
        if (book.remote == null) MenuRow(S.s_doi_ten_chuong_4c534649, tag = "chapter_rename", onClick = { renaming = true }) { ink -> TextCursorInputIcon(ink) }
    }
}

/** "Đổi tên chương": chỉ đổi tên hiển thị, giữ audio; "Về tên gốc" trả lại tên của người làm sách (web: RenameChapterDialog, ô "Tên chương"). */
@Composable
private fun RenameChapterPage(book: ListenBook, chapter: ChapterLine, source: BookSource, notes: BookNotes?, dismiss: () -> Unit, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var value by remember { mutableStateOf(chapter.title) }
    var busy by remember { mutableStateOf(false) }
    var problem by remember { mutableStateOf("") }
    val save = { revert: Boolean ->
        if (!busy) {
            busy = true
            scope.launch {
                val done = source.renameChapter(book.id, chapter.id, value.trim(), revert)
                busy = false
                val name = done.value
                if (name != null) {
                    dismiss()
                    notes?.say(S.s_da_doi_ten_chuong_0_e09362d6(name))
                } else {
                    problem = S.s_chua_doi_duoc_ten_chuong_1ff36fe9 + done.problem?.takeIf { it.isNotBlank() }?.let { " - $it" }.orEmpty()
                }
            }
        }
    }
    Column(Modifier.fillMaxWidth().imePadding().testTag("chapter_rename_page")) {
        BasicText(S.s_ten_chuong_9edb6c28, style = Abook.type.sectionTitle)
        Spacer(Modifier.height(Dim.s12))
        SheetField(value, { value = it.take(160) }, S.s_ten_chuong_9edb6c28, "chapter_rename_field", onDone = { if (value.isNotBlank()) save(false) })
        ProblemLine(problem, "chapter_rename_problem")
        Spacer(Modifier.height(Dim.s24))
        PrimaryButton(if (busy) S.s_dang_luu_e93f245d else S.s_luu_e91f26c0, { if (value.isNotBlank()) save(false) }, Modifier.fillMaxWidth().testTag("chapter_rename_save"), enabled = value.isNotBlank() && !busy)
        QuietButton(S.s_ve_ten_goc_643cd2e0, { save(true) }, "chapter_rename_original")
        QuietButton(S.s_thoi_e68f9e88, onBack, "chapter_rename_cancel")
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
        BasicText(S.s_tim_trong_sach_de3ccc5f, style = Abook.type.sectionTitle)
        RowHint(detail.book.title)
        Spacer(Modifier.height(Dim.s12))
        Row(
            Modifier.fillMaxWidth().heightIn(min = Dim.s48).insetSurface(colors)
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
                        Reveal(query.isEmpty()) { BasicText(S.s_chu_hay_cau_can_tim_41e570d3, style = Abook.type.body.copy(color = colors.text3)) }
                        inner()
                    }
                },
            )
        }
        Spacer(Modifier.height(Dim.s8))
        ClockLabel(BookSearch.status(query, progress), style = Abook.type.caption.copy(color = colors.text2), modifier = Modifier.testTag("find_status"))
        val hits = progress?.hits.orEmpty()
        Reveal(hits.isNotEmpty()) {
            Spacer(Modifier.height(Dim.s8))
            val list = rememberLazyListState()
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 360.dp).fadeEdges(list).testTag("find_results"), state = list) {
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
                addStyle(SpanStyle(color = colors.accentText, fontWeight = FontWeight.Bold), hit.matchStart, hit.matchEnd)
            }
        }
    }
    Column(Modifier.fillMaxWidth().pressable { onPick(hit) }.padding(vertical = Dim.s12).testTag("find_hit")) {
        // Chạm là nghe từ đâu: giờ phút của câu (sách nói), hay đầu chương (chương chỉ có chữ).
        val where = hit.start?.let { "$chapterTitle · ${Fmt.clock(it)}" } ?: S.s_0_tu_dau_chuong_5df8329a(chapterTitle)
        BasicText(where, style = Abook.type.caption.copy(color = colors.text2, fontWeight = FontWeight.Medium))
        Spacer(Modifier.height(Dim.s4))
        // Nền của chữ tìm thấy: SpanStyle.background chỉ vẽ được góc vuông, nên tự tô bo góc từ dàn chữ.
        var marks by remember(hit) { mutableStateOf<List<Rect>>(emptyList()) }
        val radius = with(LocalDensity.current) { Dim.radiusControl.toPx() }
        BasicText(text, Modifier.drawBehind { drawInkRects(marks, colors.accentSoft, radius) }, style = Abook.type.bodySmall.copy(color = colors.text),
            onTextLayout = { marks = ReadInk.rangeRects(it, hit.matchStart, hit.matchEnd, 0f, 0f) })
    }
}
