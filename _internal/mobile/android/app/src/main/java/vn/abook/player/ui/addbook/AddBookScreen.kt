package vn.abook.player.ui.addbook

import android.content.Intent
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.paneTitle
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
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
            state.currentId?.takeIf { state.preview != null }?.let { id ->
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
    LaunchedEffect(unfinished) { if (unfinished <= 1) asking = false }
    val leave: () -> Unit = {
        // Đang ghi một cuốn vào Thư viện mà hàng còn cuốn khác: chờ nó xong rồi mới hỏi (như web). Một cuốn thì đóng như cũ, hàng giữ nguyên.
        if (asking) asking = false
        else if (unfinished <= 1) onBack()
        else if (state.items.none { it.stage == ImportStage.Adding }) asking = true
    }
    BackHandler(enabled = active && (asking || unfinished > 1)) { leave() }
    AddBookScreen(
        state, leave, { files.launch(arrayOf("*/*")) }, { folder.launch(null) }, onReview, queue::retry, onOpen,
        leaving = if (asking) unfinished else 0, stay = { asking = false },
        dropRest = { if (queue.dropRest()) { asking = false; onBack() } },
    ) { id ->
        val progress = queue.progress(id).collectAsState()
        val read: () -> Float = { progress.value }
        read
    }
}

/**
 * Thêm sách. Chưa chọn gì (người dùng đã đóng hộp chọn file): một câu việc cần làm + một dòng các định dạng, "Chọn file" ở đáy, "Thư mục TXT" dưới nó.
 * Đã chọn: mỗi file là một hàng (biểu tượng file · tên · trạng thái); hàng xong / chờ xem là CẢ hàng bấm được, hàng lỗi có "Thử lại" ở đuôi.
 * `leaving` > 0: đang hỏi trước khi đóng giữa hàng ("Còn N cuốn chưa thêm..."): chân màn khép hai nút chọn file, mở lời hỏi + "Quay lại thêm sách" / "Bỏ phần còn lại".
 */
@Composable
fun AddBookScreen(
    state: ImportState, onBack: () -> Unit, pickFiles: () -> Unit, pickFolder: () -> Unit,
    review: (Long) -> Unit, retry: (Long) -> Unit, openBook: (String) -> Unit,
    leaving: Int = 0, stay: () -> Unit = {}, dropRest: () -> Unit = {},
    progress: @Composable (Long) -> (() -> Float) = { { 0.35f } },
) {
    // Số cuốn giữ lại trong lúc lời hỏi khép (không đổi thành "Còn 0 cuốn" giữa chừng).
    val lastCount = remember { intArrayOf(0) }
    if (leaving > 0) lastCount[0] = leaving
    BookForm("Thêm sách", onBack, "add_book_screen", footer = {
        Reveal(leaving == 0) {
            Column(Modifier.fillMaxWidth()) {
                PrimaryButton("Chọn file sách", pickFiles, Modifier.fillMaxWidth().testTag("pick_books"))
                TextAction("Chọn thư mục TXT", pickFolder, "pick_folder", Modifier.fillMaxWidth(), align = Alignment.Center)
            }
        }
        Reveal(leaving > 0) {
            Column(Modifier.fillMaxWidth().semantics { paneTitle = "Đóng khi còn sách chưa thêm" }.testTag("leave_confirm")) {
                BasicText(ImportLogic.leaveQuestion(lastCount[0]), style = Abook.type.bodyStrong, modifier = Modifier.padding(bottom = Dim.s12).testTag("leave_question"))
                PrimaryButton("Quay lại thêm sách", stay, Modifier.fillMaxWidth().testTag("leave_stay"))
                TextAction("Bỏ phần còn lại", dropRest, "leave_drop", Modifier.fillMaxWidth(), align = Alignment.Center)
            }
        }
    }) {
        if (state.items.isEmpty()) {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s16).testTag("add_empty")) {
                BasicText("Chọn sách từ máy bạn", style = Abook.type.sectionTitle)
                Spacer(Modifier.height(Dim.s4))
                BasicText("EPUB, DOCX, TXT, PDF hoặc file ABook.", style = Abook.type.bodySmall)
            }
        } else {
            val list = rememberLazyListState()
            LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("import_queue"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
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

@Composable
private fun ImportRow(
    item: ImportItem, review: (Long) -> Unit, retry: (Long) -> Unit, openBook: (String) -> Unit,
    progress: @Composable (Long) -> (() -> Float),
) {
    val colors = Abook.colors
    val failed = item.stage == ImportStage.Error
    val open: (() -> Unit)? = when {
        item.stage == ImportStage.Review -> ({ review(item.id) })
        item.stage in setOf(ImportStage.Added, ImportStage.Existing) && item.bookId != null -> ({ openBook(item.bookId) })
        else -> null
    }
    ListItem(
        title = item.name,
        onClick = open,
        tag = if (item.stage == ImportStage.Review) "review_${item.id}" else "open_${item.id}",
        hint = if (failed) item.problem.ifEmpty { item.stage.label } else item.stage.label,
        hintColor = if (failed) colors.danger else colors.text2,
        leading = { if (item.folder) FolderIcon(colors.text2) else FileIcon(colors.text2) },
        trailing = if (failed) ({ TextAction("Thử lại", { retry(item.id) }, "retry_${item.id}") }) else null,
        chevron = open != null,
        below = if (item.stage == ImportStage.Reading || item.stage == ImportStage.Adding) ({ StageProgress(progress(item.id)) }) else null,
    )
}

@Composable
fun ImportReviewRoute(queue: ImportQueue, itemId: Long, onBack: () -> Unit, openChapter: (Int) -> Unit) {
    val state by queue.state.collectAsState()
    // Thêm xong thì lùi một lớp về hàng đợi, không để lại bản xem trước đã cũ.
    LaunchedEffect(state.currentId) { if (state.currentId != itemId) onBack() }
    ImportReviewScreen(state, onBack, queue::choose, queue::revise, queue::add, queue::skip, openChapter)
}

/** Cách xử lý lời chú: loại trừ nhau trong lõi (`FootnoteChoice.notes` là MỘT giá trị "", "end" hay "drop"), nên là một hàng chọn-một. */
private enum class NoteMode(val code: String, override val label: String) : Choice {
    Keep("", "Giữ nguyên"), End("end", "Cuối chương"), Drop("drop", "Bỏ lời chú");

    override val key: String get() = name.lowercase()
}

/**
 * Xem trước một cuốn: tên ở đầu, một dòng thông tin (tác giả · số chương), rồi các phần theo thứ tự việc cần quyết - gợi ý đọc, chú thích, chương. Mọi lựa chọn mặc
 * định TẮT (ABook không tự bỏ chữ của truyện). "Thêm sách" ghim ở đáy; "Bỏ cuốn này" là việc duy nhất ở cuối danh sách.
 */
@Composable
fun ImportReviewScreen(
    state: ImportState, onBack: () -> Unit, choose: ((ImportChoices) -> ImportChoices) -> Unit,
    revise: ((ImportChoices) -> ImportChoices) -> Unit, add: () -> Unit, skip: () -> Unit,
    openChapter: (Int) -> Unit = {},
) {
    val preview = state.preview
    val choice = state.choices
    BookForm("Xem trước", onBack, "import_review_screen", footer = {
        InlineProblem(state.problem, tag = "import_problem")
        InlineProblem(if (preview != null && !ImportLogic.canAdd(preview, choice)) ImportLogic.NOTHING_PICKED else "", tag = "import_none_picked")
        if (preview != null) PrimaryButton(
            when {
                state.busy -> "Đang xử lý"
                preview.existingId != null && !choice.separate -> "Dùng sách có"
                else -> "Thêm sách"
            },
            add, Modifier.fillMaxWidth().testTag("confirm_import"), enabled = !state.busy && ImportLogic.canAdd(preview, choice),
        )
    }) {
        val list = rememberLazyListState()
        if (preview != null) LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("import_review"), state = list) {
            item("metadata", "metadata") {
                Column(Modifier.padding(top = Dim.s16)) {
                    BookField(null, choice.title, { value -> choose { it.copy(title = value) } }, "import_title", !state.busy, "Tên sách")
                    val meta = listOfNotNull(preview.author.takeIf { it.isNotEmpty() }, "${choice.picked.size} / ${preview.chapters.size} chương")
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(meta.joinToString(" · "), style = Abook.type.bodySmall, modifier = Modifier.testTag("import_meta"))
                }
            }
            if (preview.existingId != null || preview.splitOffer > 0) item("options", "options") {
                Column(Modifier.padding(top = Dim.sectionGap)) {
                    if (preview.existingId != null) SwitchRow("Thêm bản riêng", choice.separate, { choose { it.copy(separate = !it.separate) } },
                        "separate_copy", hint = "File này đã có trong Thư viện.")
                    if (preview.existingId != null && preview.splitOffer > 0) RowLine()
                    if (preview.splitOffer > 0) SwitchRow("Tách chương", choice.split, { revise { it.copy(split = !it.split) } },
                        "split_chapters", hint = "Theo ${preview.splitHeadings} dòng tiêu đề trong file.")
                }
            }
            val groups = ImportLogic.groups(ImportLogic.forPicked(preview, choice))
            if (groups.isNotEmpty()) {
                item("suggestion_heading", "heading") { SectionTitle("Gợi ý phần đọc") }
                items(groups, key = { "suggestion_${it.line}" }, contentType = { "suggestion" }) { group ->
                    Column {
                        SwitchRow("Bỏ đọc dòng", group.line in choice.skipped,
                            { choose { it.copy(skipped = if (group.line in it.skipped) it.skipped - group.line else it.skipped + group.line) } },
                            "suggestion_${group.line}", hint = "“${group.line}” · ${group.chapters.size} chương")
                        RowLine()
                    }
                }
            }
            if (preview.footnoteCount > 0) item("footnotes", "footnotes") {
                Column {
                    SectionTitle("Chú thích")
                    Caption("${preview.footnoteCount} chú thích trong file", Modifier.testTag("footnote_count"))
                    if (preview.footnoteExample.isNotEmpty()) {
                        Spacer(Modifier.height(Dim.s12))
                        QuoteSample(preview.footnoteExample, Modifier.testTag("footnote_example"))
                    }
                    Spacer(Modifier.height(Dim.s8))
                    if (preview.footnoteMarks > 0) {
                        SwitchRow("Bỏ số gọi", choice.hideMarks, { revise { it.copy(hideMarks = !it.hideMarks) } }, "hide_marks",
                            hint = "${preview.footnoteMarks} số gọi trong chữ")
                        RowLine()
                    }
                    ChoiceSetting("Lời chú", NoteMode.entries, NoteMode.entries.first { it.code == choice.notes },
                        { mode, _ -> revise { it.copy(notes = mode.code) } }, "footnote_notes")
                }
            }
            item("chapter_heading", "heading") {
                // Nhiều chương: "Chọn hết" / "Bỏ chọn hết" ở cuối hàng tiêu đề (web: cạnh số chương đã tích).
                if (preview.chapters.size > 1) {
                    Row(Modifier.fillMaxWidth().padding(top = Dim.sectionGap).heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically) {
                        BasicText("Chương", style = Abook.type.sectionTitle, modifier = Modifier.weight(1f))
                        TextAction("Chọn hết", { choose { it.copy(picked = ImportLogic.all(preview)) } }, "pick_all_chapters")
                        Spacer(Modifier.width(Dim.s16))
                        TextAction("Bỏ chọn hết", { choose { it.copy(picked = emptySet()) } }, "pick_no_chapters")
                    }
                } else SectionTitle("Chương")
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
            items(preview.notes.distinct(), key = { "note_$it" }, contentType = { "note" }) { note ->
                Caption(note, Modifier.padding(top = Dim.s12))
            }
            item("skip", "action") {
                TextAction("Bỏ cuốn này", skip, "skip_book", Modifier.padding(top = Dim.s24, bottom = Dim.s16).fillMaxWidth(), align = Alignment.CenterStart)
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
                    .semantics { stateDescription = if (kept) "Giữ" else "Bỏ" }.testTag("${tag}_keep"),
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
    BookForm("Tên chương", onBack, "import_chapter_screen") {
        if (row != null) Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
            val current = state.choices.names[index] ?: row.title
            BookField(null, current, { value -> choose { it.copy(names = it.names + (index to value)) } }, "chapter_title", description = "Tên chương")
            if (ImportLogic.renamed(current, row.title)) {
                Spacer(Modifier.height(Dim.s16))
                RevertName(row.title, { choose { it.copy(names = it.names - index) } })
            }
        }
    }
}
