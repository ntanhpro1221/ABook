package vn.abook.player.ui.addbook

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import vn.abook.player.S
import vn.abook.player.Work
import vn.abook.player.WorkStep

import vn.abook.player.ui.data.dotJoined
import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.toggleableState
import androidx.compose.ui.state.ToggleableState
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ChoiceSetting
import vn.abook.player.ui.components.FileIcon
import vn.abook.player.ui.components.FolderIcon
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuoteSample
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.Switch
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.onFirstLine
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.components.fadeEdges
import androidx.compose.foundation.lazy.rememberLazyListState

@Composable
fun AddBookRoute(queue: ImportQueue, onBack: () -> Unit, onReview: (Long) -> Unit, onOpen: (String) -> Unit, autoPick: Boolean = false, active: Boolean = true) {
    val state by queue.state.collectAsState()
    val context = LocalContext.current
    val files = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        for (uri in uris) runCatching { context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
        queue.enqueue(uris.map { it.toString() })
    }
    val folder = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { uri ->
        uri?.let {
            runCatching { context.contentResolver.takePersistableUriPermission(it, Intent.FLAG_GRANT_READ_URI_PERMISSION) }
            queue.enqueue(listOf(it.toString()), folder = true)
        }
    }
    var picked by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) {
        if (autoPick && !picked && state.items.isEmpty()) { picked = true; files.launch(arrayOf("*/*")) }
    }
    LaunchedEffect(active, state.currentId, state.preview, state.items) {
        if (active && autoPick) {
            state.currentId?.takeIf { state.preview != null || state.packageReview != null }?.let { id ->
                if (queue.takeAutoReview(id)) onReview(id)
            }
            state.items.singleOrNull()?.takeIf { it.stage in setOf(ImportStage.Added, ImportStage.Existing) }?.let { item ->
                item.bookId?.let { id -> if (queue.takeAutoOpen(item.id)) onOpen(id) }
            }
        }
    }
    // Đóng khi hàng còn hơn một cuốn chưa thêm: hỏi ngay ở chân màn, không bỏ cả hàng im lặng (web AddBook `confirmLeave`). Back lần nữa = "Quay lại thêm sách".
    val unfinished = ImportLogic.unfinished(state.items)
    var asking by rememberSaveable { mutableStateOf(false) }
    var choosingAgain by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(unfinished) { if (unfinished <= 1) asking = false }
    val leave: () -> Unit = {
        choosingAgain = false
        // Đang ghi một cuốn vào Thư viện mà hàng còn cuốn khác: chờ nó xong rồi mới hỏi (như web). Một cuốn thì đóng như cũ, hàng giữ nguyên.
        if (asking) asking = false
        else if (unfinished <= 1) onBack()
        else if (state.items.none { it.stage == ImportStage.Adding }) asking = true
    }
    BackHandler(enabled = active && (asking || unfinished > 1)) { leave() }
    AddBookScreen(
        state, leave, {
            if (unfinished > 1) { choosingAgain = true; asking = true } else files.launch(arrayOf("*/*"))
        }, { folder.launch(null) }, onReview, queue::retry, onOpen,
        leaving = if (asking) unfinished else 0, stay = { asking = false },
        dropRest = { if (queue.dropRest()) { asking = false; if (choosingAgain) files.launch(arrayOf("*/*")) else onBack() } },
        choosingAgain = choosingAgain,
        addRest = queue::addRest,
    ) { id ->
        queue.progress(id).collectAsState()
    }
}

/**
 * Thêm sách. Chưa chọn gì (người dùng đã đóng hộp chọn file): một dòng các định dạng (cùng chữ với lời đầu hộp Thêm sách của web), "Chọn file" ở đáy,
 * "Thư mục TXT" dưới nó.
 * Đã chọn: mỗi file là một hàng (biểu tượng file · tên · trạng thái); hàng xong / chờ xem là CẢ hàng bấm được, hàng lỗi có "Thử lại" ở đuôi.
 * `leaving` > 0: đang hỏi trước khi đóng giữa hàng ("Còn N cuốn chưa thêm..."): chân màn khép hai nút chọn file, mở lời hỏi + "Quay lại thêm sách" / "Bỏ phần còn lại".
 */
@Composable
fun AddBookScreen(
    state: ImportState, onBack: () -> Unit, pickFiles: () -> Unit, pickFolder: () -> Unit,
    review: (Long) -> Unit, retry: (Long) -> Unit, openBook: (String) -> Unit,
    leaving: Int = 0, stay: () -> Unit = {}, dropRest: () -> Unit = {},
    addRest: () -> Unit = {},
    choosingAgain: Boolean = false,
    progress: @Composable (Long) -> State<Work> = { remember { mutableStateOf(Work(WorkStep.Read)) } },
) {
    // Số cuốn giữ lại trong lúc lời hỏi khép (không đổi thành "Còn 0 cuốn" giữa chừng).
    val lastCount = remember { intArrayOf(0) }
    if (leaving > 0) lastCount[0] = leaving
    BookForm(S.s_them_sach_2a9d3708, onBack, "add_book_screen", footer = {
        Reveal(leaving == 0) {
            Column(Modifier.fillMaxWidth()) {
                Reveal(state.items.size > 1 && ImportLogic.unfinished(state.items) > 0 && !state.busy && !state.addingRest) {
                    TextAction(S.s_them_phan_con_lai_45b70e44, addRest, "add_rest", Modifier.fillMaxWidth(), align = Alignment.Center)
                }
                PrimaryButton(S.s_chon_file_sach_1f25282c, pickFiles, Modifier.fillMaxWidth().testTag("pick_books"))
                TextAction(S.s_chon_thu_muc_txt_dd0d140c, pickFolder, "pick_folder", Modifier.fillMaxWidth(), align = Alignment.Center)
            }
        }
        Reveal(leaving > 0) {
            Column(Modifier.fillMaxWidth().semantics { paneTitle = S.s_dong_khi_con_sach_chua_them_0406a915 }.testTag("leave_confirm")) {
                BasicText(if (choosingAgain) ImportLogic.rechooseQuestion(lastCount[0]) else ImportLogic.leaveQuestion(lastCount[0]), style = Abook.type.bodyStrong, modifier = Modifier.padding(bottom = Dim.s12).testTag("leave_question"))
                PrimaryButton(S.s_quay_lai_them_sach_e5ac9359, stay, Modifier.fillMaxWidth().testTag("leave_stay"))
                TextAction(if (choosingAgain) S.s_bo_va_chon_lai_89f7d490 else S.s_bo_phan_con_lai_63a3c314, dropRest, "leave_drop", Modifier.fillMaxWidth(), align = Alignment.Center)
            }
        }
    }) {
        SwapContent(state, contentKey = { state -> state.items.isEmpty() }, layout = ContentLayout.Box) { state ->
            if (state.items.isEmpty()) {
                Column(Modifier.fillMaxWidth().padding(top = Dim.s16).testTag("add_empty")) {
                    BasicText(S.s_epub_docx_pdf_co_chu_txt_hoac_file_abook_c_cc969e7b, style = Abook.type.bodySmall)
                }
            } else {
                val list = rememberLazyListState()
                LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("import_queue"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
                    item("summary", "summary") {
                        val summary = ImportLogic.summary(state.items)
                        Reveal(summary.isNotEmpty()) { Caption(summary, Modifier.testTag("import_summary"), ticking = true) }
                        Reveal(state.notice.isNotEmpty()) { Caption(state.notice) }
                    }
                    items(state.items, key = { it.id }, contentType = { "import" }) { item ->
                        Column(Modifier.fillMaxWidth().animateItem(fadeInSpec = null, fadeOutSpec = null).animateContentSize().testTag("import_${item.id}")) {
                            ImportRow(item, review, retry, openBook, progress)
                            RowLine(start = 36.dp)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ImportRow(
    item: ImportItem, review: (Long) -> Unit, retry: (Long) -> Unit, openBook: (String) -> Unit,
    progress: @Composable (Long) -> State<Work>,
) {
    val colors = Abook.colors
    val failed = item.stage == ImportStage.Error
    val working = item.stage == ImportStage.Reading || item.stage == ImportStage.Adding
    val work = if (working) progress(item.id) else null
    val open: (() -> Unit)? = when {
        item.stage == ImportStage.Review -> ({ review(item.id) })
        item.stage in setOf(ImportStage.Added, ImportStage.Existing) && item.bookId != null -> ({ openBook(item.bookId) })
        else -> null
    }
    ListItem(
        title = item.name,
        onClick = open,
        tag = if (item.stage == ImportStage.Review) "review_${item.id}" else "open_${item.id}",
        hint = if (failed) item.problem.ifEmpty { item.stage.label } else if (working) ImportLogic.workLabel(work!!.value) else item.stage.label,
        hintColor = if (failed) colors.danger else colors.text2,
        leading = { SwapContent(item, contentKey = { item -> item.folder }, layout = ContentLayout.Box) { item ->
            if (item.folder) FolderIcon(colors.text2) else FileIcon(colors.text2)
        } },
        trailing = if (failed) ({ TextAction(S.s_thu_lai_c58d068c, { retry(item.id) }, "retry_${item.id}") }) else null,
        chevron = open != null,
        below = if (working) ({
            // Thanh theo việc thật: phần đã xong của cả hàng; bước chưa biết tổng thì chạy liên tục.
            val bar = work!!
            val known by remember { derivedStateOf { bar.value.fraction != null } }
            StageProgress(known) { bar.value.fraction ?: 0f }
        }) else null,
    )
}

@Composable
fun ImportReviewRoute(queue: ImportQueue, itemId: Long, onBack: () -> Unit, openChapter: (Int) -> Unit) {
    val state by queue.state.collectAsState()
    // Thêm xong thì lùi một lớp về hàng đợi, không để lại bản xem trước đã cũ.
    LaunchedEffect(state.currentId) { if (state.currentId != itemId) onBack() }
    SwapContent(state, contentKey = { state -> state.packageReview != null }, layout = ContentLayout.Box) { state ->
        if (state.packageReview != null) PackageReviewScreen(state, onBack, queue::keepPackage, queue::add)
        else ImportReviewScreen(state, onBack, queue::choose, queue::revise, queue::add, queue::skip, openChapter)
    }
}

/** Cách xử lý lời chú: loại trừ nhau trong lõi (`FootnoteChoice.notes` là MỘT giá trị "", "end" hay "drop"), nên là một hàng chọn-một. */
private enum class NoteMode(val code: String, override val label: String) : Choice {
    Keep("", S.s_giu_nguyen_1b550a12), End("end", S.s_cuoi_chuong_8e067450), Drop("drop", S.s_bo_loi_chu_b3d90294);

    override val key: String get() = name.lowercase()
}

/**
 * Xem trước một cuốn: tên ở đầu, một dòng thông tin (tác giả · số chương), rồi các phần theo thứ tự việc cần quyết - gợi ý đọc, chú thích, chương. Mọi lựa chọn mặc
 * định TẮT (ABook không tự bỏ chữ của truyện). "Thêm vào thư viện" ghim ở đáy; "Bỏ cuốn này" là việc duy nhất ở cuối danh sách. Cuốn đã có trong thư viện:
 * "Bỏ cuốn này" thành nút chính ở đáy (như web) và không lặp ở cuối danh sách.
 */
@Composable
fun ImportReviewScreen(
    state: ImportState, onBack: () -> Unit, choose: ((ImportChoices) -> ImportChoices) -> Unit,
    revise: ((ImportChoices) -> ImportChoices) -> Unit, add: () -> Unit, skip: () -> Unit,
    openChapter: (Int) -> Unit = {},
) {
    val preview = state.preview
    val choice = state.choices
    // Cuốn đã có (và không thêm bản riêng): nút chính bỏ cuốn này, dùng cuốn có sẵn - như "Bỏ cuốn này" của hàng nhiều file trên web.
    val known = preview?.existingId != null && !choice.separate
    // Nhiều file: "Sách 2/5 · Xem trước" như tên hộp của web.
    val at = state.items.indexOfFirst { it.id == state.currentId }
    val label = if (state.items.size > 1 && at >= 0) S.s_sach_0_1_77b98415(at + 1, state.items.size) else ""
    val title = if (label.isEmpty()) S.s_xem_truoc_4282388c else S.s_0_xem_truoc_0b80ebc7(label)
    val adding = state.items.firstOrNull { it.id == state.currentId }?.stage == ImportStage.Adding
    BookForm(title, onBack, "import_review_screen", footer = {
        InlineProblem(state.problem, tag = "import_problem")
        InlineProblem(if (preview != null && !ImportLogic.canAdd(preview, choice)) ImportLogic.NOTHING_PICKED else "", tag = "import_none_picked")
        SwapContent(preview, contentKey = { preview -> preview != null }, layout = ContentLayout.Box) { preview ->
            if (preview != null) PrimaryButton(
            when {
                state.busy -> if (adding) S.s_dang_them_457edcc3 else S.s_dang_doc_1b09d2d9
                known -> if (state.items.size == 1) S.s_mo_cuon_do_75ab80a2 else S.s_bo_cuon_nay_ba5f36fe
                else -> S.s_them_vao_thu_vien_cc27dafc
            },
            add, Modifier.fillMaxWidth().testTag("confirm_import"), enabled = !state.busy && ImportLogic.canAdd(preview, choice),
            )
        }
    }) {
        val list = rememberLazyListState()
        SwapContent(preview, contentKey = { preview -> preview != null }, layout = ContentLayout.Box) { preview ->
            if (preview != null) LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("import_review"), state = list) {
                item("metadata", "metadata") {
                    Column(Modifier.padding(top = Dim.s16)) {
                        BookField(null, choice.title, { value -> choose { it.copy(title = value) } }, "import_title", !state.busy, S.s_ten_sach_d54846eb,
                        placeholder = S.s_ten_hien_thi_trong_thu_vien_c48c7ac6)
                        val meta = listOfNotNull(preview.author.takeIf { it.isNotEmpty() }, S.s_0_1_chuong_505874dc(choice.picked.size, preview.chapters.size))
                        Spacer(Modifier.height(Dim.s8))
                        BasicText(meta.dotJoined(), style = Abook.type.bodySmall, modifier = Modifier.testTag("import_meta"))
                    }
                }
                if (preview.existingId != null || preview.splitOffer > 0) item("options", "options") {
                    Column(Modifier.padding(top = Dim.sectionGap)) {
                        SwapContent(preview, contentKey = { preview -> preview.existingId != null }, layout = ContentLayout.Column) { preview ->
                            if (preview.existingId != null) {
                                Caption(if (preview.sameSource) S.s_da_them_tu_file_nay_roi_42fe4ad5 else S.s_cuon_nay_da_co_trong_thu_vien_2aae08e1)
                                SwitchRow(if (preview.sameSource) S.s_van_them_ban_moi_f4832361 else S.s_them_ban_rieng_fe9759e4, choice.separate, { choose { it.copy(separate = !it.separate) } },
                                "separate_copy", hint = if (preview.sameSource) S.s_ban_da_them_file_nay_thanh_0_1_chuong_68248830(preview.existingTitle, preview.existingChapters)
                                else S.s_cuon_nay_da_co_trong_thu_vien_0_d8728110(preview.existingTitle))
                            }
                        }
                        SwapContent(preview, contentKey = { preview -> preview.existingId != null && preview.splitOffer > 0 }, layout = ContentLayout.Column) { preview ->
                            if (preview.existingId != null && preview.splitOffer > 0) RowLine()
                        }
                        Reveal(preview.splitOffer > 0) { SwitchRow(S.s_tach_chuong_2f1df570, choice.split, { revise { it.copy(split = !it.split) } },
                            "split_chapters", hint = ImportLogic.splitHint(preview)) }
                    }
                }
                val groups = ImportLogic.groups(ImportLogic.forPicked(preview, choice))
                if (groups.isNotEmpty()) {
                    item("suggestion_heading", "heading") { SectionTitle(S.s_goi_y_phan_doc_b268d95e) }
                    items(groups, key = { "suggestion_${it.line}" }, contentType = { "suggestion" }) { group ->
                        Column {
                            SwitchRow(S.s_bo_doc_dong_3e82a7fd, group.line in choice.skipped,
                            { choose { it.copy(skipped = if (group.line in it.skipped) it.skipped - group.line else it.skipped + group.line) } },
                            "suggestion_${group.line}", hint = "“${group.line}” · ${ImportLogic.where(group.chapters)}")
                            RowLine()
                        }
                    }
                }
                if (preview.footnoteCount > 0) item("footnotes", "footnotes") {
                    Column {
                        SectionTitle(S.s_chu_thich_fc0aa279)
                        Caption(S.s_0_chu_thich_trong_file_be2ecbf5(preview.footnoteCount), Modifier.testTag("footnote_count"))
                        Reveal(preview.footnoteExample.isNotEmpty()) {
                            Spacer(Modifier.height(Dim.s12))
                            QuoteSample(preview.footnoteExample, Modifier.testTag("footnote_example"))
                        }
                        Spacer(Modifier.height(Dim.s8))
                        Reveal(preview.footnoteMarks > 0) {
                            SwitchRow(S.s_bo_so_goi_b8d25593, choice.hideMarks, { revise { it.copy(hideMarks = !it.hideMarks) } }, "hide_marks",
                            hint = S.s_0_so_goi_trong_chu_bo_cac_con_so_nhu_2_hay_10ac572b(preview.footnoteMarks))
                            RowLine()
                        }
                        ChoiceSetting(S.s_loi_chu_eca33b1a, NoteMode.entries, NoteMode.entries.first { it.code == choice.notes },
                        { mode, _ -> revise { it.copy(notes = mode.code) } }, "footnote_notes")
                        // Cùng câu với web (FootnoteChoices.tsx): hàng chọn-một không có lời riêng cho từng lựa chọn nên một câu giải thích cả ba.
                        Caption(S.s_ban_chon_giu_nguyen_de_giu_loi_chu_nhu_tro_fa013ff9, Modifier.padding(top = Dim.s4).testTag("footnote_notes_help"))
                    }
                }
                item("chapter_heading", "heading") {
                    // Nhiều chương: "Chọn hết" / "Bỏ chọn hết" ở cuối hàng tiêu đề (web: cạnh số chương đã tích).
                    SwapContent(preview, contentKey = { preview -> preview.chapters.size > 1 }, layout = ContentLayout.Box) { preview ->
                        if (preview.chapters.size > 1) {
                            Row(Modifier.fillMaxWidth().padding(top = Dim.sectionGap).heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically) {
                                BasicText(S.s_chuong_2d157977, style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
                                TextAction(S.s_chon_het_9e8a7c2c, { choose { it.copy(picked = ImportLogic.all(preview)) } }, "pick_all_chapters")
                                Spacer(Modifier.width(Dim.s16))
                                TextAction(S.s_bo_chon_het_669fa50d, { choose { it.copy(picked = emptySet()) } }, "pick_no_chapters")
                            }
                        } else SectionTitle(S.s_chuong_2d157977)
                    }
                }
                items(preview.chapters, key = { "chapter_${it.index}" }, contentType = { "chapter" }) { row ->
                    val kept = row.index in choice.picked
                    val shown = choice.names[row.index]?.takeIf { it.isNotBlank() } ?: row.title
                    Column {
                        ChapterPickRow(
                        title = shown, kept = kept,
                        hint = if (shown.trim() != row.title.trim()) row.title else row.note.takeIf { it.isNotEmpty() },
                        onKeep = { choose { it.copy(picked = if (row.index in it.picked) it.picked - row.index else it.picked + row.index) } },
                        onOpen = { openChapter(row.index) }, tag = "import_chapter_${row.index}", enabled = !state.busy,
                        )
                        RowLine(start = 56.dp)
                    }
                }
                if (preview.notes.isNotEmpty()) item("notes_heading", "heading") { SectionTitle(S.s_dinh_dang_36b746b6) }
                items(preview.notes.distinct(), key = { "note_$it" }, contentType = { "note" }) { note ->
                    Caption(note, Modifier.padding(top = Dim.s12))
                }
                if (!known) item("skip", "action") {
                    TextAction(S.s_bo_cuon_nay_ba5f36fe, skip, "skip_book", Modifier.padding(top = Dim.s24, bottom = Dim.s16).fillMaxWidth(), align = Alignment.CenterStart)
                }
            }
        }
    }
}

/**
 * Hàng chương: công tắc giữ / bỏ ở đầu hàng, tên chương (chạm mở màn đặt tên) và mũi tên ở cuối. Công tắc và mũi tên cùng thẳng dòng đầu của tên; chương bỏ thì tên
 * nhạt đi. `hint`: tên gốc khi đã đổi tên, hay ghi chú của chương.
 */
@Composable
private fun ChapterPickRow(title: String, kept: Boolean, hint: String?, onKeep: () -> Unit, onOpen: () -> Unit, tag: String, enabled: Boolean) {
    val colors = Abook.colors
    Row(Modifier.fillMaxWidth().testTag(tag), verticalAlignment = Alignment.Top) {
        Box(Modifier.onFirstLine()) {
            Box(
                Modifier.size(56.dp, Dim.s48).then(if (enabled) Modifier.pressable(Role.Switch, onClick = onKeep) else Modifier)
                    .semantics { toggleableState = ToggleableState(kept) }.testTag("${tag}_keep"),
                contentAlignment = Alignment.CenterStart,
            ) { Switch(kept) }
        }
        ListItem(
            title, Modifier.weight(1f), onClick = onOpen, tag = "${tag}_name", hint = hint, hintColor = colors.text3,
            titleColor = if (kept) colors.text else colors.text3, chevron = true,
        )
    }
}

/** Màn tên một chương của cuốn đang xem trước: một ô; "Về tên gốc" chỉ khi tên đã khác bản gốc. */
@Composable
fun ImportChapterRoute(queue: ImportQueue, index: Int, onBack: () -> Unit) {
    val state by queue.state.collectAsState()
    ImportChapterScreen(state, index, onBack, queue::choose)
}

@Composable
fun ImportChapterScreen(state: ImportState, index: Int, onBack: () -> Unit, choose: ((ImportChoices) -> ImportChoices) -> Unit) {
    val row = state.preview?.chapters?.firstOrNull { it.index == index }
    BookForm(S.s_ten_chuong_9edb6c28, onBack, "import_chapter_screen") {
        SwapContent(row, contentKey = { row -> row != null }, layout = ContentLayout.Box) { row ->
            if (row != null) Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                val current = state.choices.names[index] ?: row.title
                BookField(null, current, { value -> choose { it.copy(names = it.names + (index to value)) } }, "chapter_title", description = S.s_ten_chuong_9edb6c28)
                Reveal(ImportLogic.renamed(current, row.title)) {
                    Spacer(Modifier.height(Dim.s16))
                    RevertName(row.title, { choose { it.copy(names = it.names - index) } })
                }
            }
        }
    }
}
