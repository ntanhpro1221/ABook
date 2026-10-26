package vn.abook.player.ui.addbook

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

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
    AddBookScreen(state, onBack, { files.launch(arrayOf("*/*")) }, { folder.launch(null) }, onReview, queue::retry, onOpen) { id ->
        val progress = queue.progress(id).collectAsState()
        val read: () -> Float = { progress.value }
        read
    }
}

@Composable
fun AddBookScreen(
    state: ImportState, onBack: () -> Unit, pickFiles: () -> Unit, pickFolder: () -> Unit,
    review: (Long) -> Unit, retry: (Long) -> Unit, openBook: (String) -> Unit,
    progress: @Composable (Long) -> (() -> Float) = { { 0.35f } },
) {
    BookForm("Thêm sách", onBack, "add_book_screen", footer = {
        PrimaryButton("Chọn file", pickFiles, Modifier.fillMaxWidth().testTag("pick_books"))
        BookAction("Thư mục TXT", pickFolder, Modifier.fillMaxWidth().testTag("pick_folder"))
    }) {
        LazyColumn(Modifier.fillMaxSize().testTag("import_queue"), verticalArrangement = Arrangement.spacedBy(Dim.s16)) {
            item("intro", "intro") {
                Column {
                    BasicText(if (state.items.isEmpty()) "Sách của bạn" else "Hàng đợi nhập", style = Abook.type.sectionTitle)
                    Spacer(Modifier.height(Dim.s8))
                    BasicText(if (state.items.isEmpty()) "Bạn chọn EPUB, DOCX, TXT, PDF hoặc file ABook. Có thể chọn nhiều file." else
                        "Bạn có thể quay lại Thư viện; hàng đợi vẫn được giữ.", style = Abook.type.bodySmall)
                }
            }
            items(state.items, key = { it.id }, contentType = { "import" }) { item ->
                Column(Modifier.fillMaxWidth().animateItem(fadeInSpec = null, fadeOutSpec = null).animateContentSize().testTag("import_${item.id}")) {
                    BasicText(item.name, style = Abook.type.bodyStrong)
                    BasicText(item.stage.label, style = Abook.type.bodySmall)
                    if (item.stage == ImportStage.Reading || item.stage == ImportStage.Adding || item.stage == ImportStage.Review) {
                        StageProgress(progress(item.id))
                    }
                    BookProblem(item.problem)
                    when (item.stage) {
                        ImportStage.Review -> BookAction("Xem trước", { review(item.id) }, Modifier.testTag("review_${item.id}"))
                        ImportStage.Error -> BookAction("Thử lại", { retry(item.id) }, Modifier.testTag("retry_${item.id}"))
                        ImportStage.Added, ImportStage.Existing -> item.bookId?.let { id -> BookAction("Mở sách", { openBook(id) }) }
                        else -> Unit
                    }
                }
            }
            item("end", "space") { Spacer(Modifier.height(Dim.s16)) }
        }
    }
}

/** Milestones, not estimated byte percentages. The changing value is read only by the draw lambda. */
@Composable
private fun StageProgress(progress: () -> Float) {
    val track = Abook.colors.line
    val ink = Abook.colors.accent
    Canvas(Modifier.fillMaxWidth().padding(top = Dim.s8).height(3.dp)) {
        drawRect(track)
        drawRect(ink, size = size.copy(width = size.width * progress().coerceIn(0f, 1f)))
    }
}

@Composable
fun ImportReviewRoute(queue: ImportQueue, itemId: Long, onBack: () -> Unit) {
    val state by queue.state.collectAsState()
    // Completion returns one layer to the queue, never leaves a stale review visible.
    LaunchedEffect(state.currentId) { if (state.currentId != itemId) onBack() }
    ImportReviewScreen(state, onBack, queue::choose, queue::revise, queue::add, queue::skip)
}

@Composable
fun ImportReviewScreen(
    state: ImportState, onBack: () -> Unit, choose: ((ImportChoices) -> ImportChoices) -> Unit,
    revise: ((ImportChoices) -> ImportChoices) -> Unit, add: () -> Unit, skip: () -> Unit,
) {
    val preview = state.preview
    val choice = state.choices
    BookForm("Xem trước", onBack, "import_review_screen", footer = {
        BookProblem(state.problem)
        if (!state.busy && preview != null) PrimaryButton(
            if (preview.existingId != null && !choice.separate) "Dùng sách có" else "Thêm sách",
            add, Modifier.fillMaxWidth().testTag("confirm_import"),
        ) else BasicText("Đang xử lý file", style = Abook.type.bodySmall)
    }) {
        if (preview != null) LazyColumn(Modifier.fillMaxSize().testTag("import_review"), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
            item("metadata", "metadata") {
                Column {
                    BookField("Tên sách", choice.title, { value -> choose { it.copy(title = value) } }, "import_title", !state.busy)
                    if (preview.author.isNotEmpty()) BasicText(preview.author, style = Abook.type.bodySmall)
                    BasicText("${choice.picked.size} / ${preview.chapters.size} chương", style = Abook.type.bodySmall)
                    if (preview.existingId != null) BookChoice("Thêm bản riêng", choice.separate, { choose { it.copy(separate = !it.separate) } },
                        "File này đã có trong Thư viện.", enabled = !state.busy)
                    if (preview.splitOffer > 0) BookChoice("Tách chương", choice.split, { revise { it.copy(split = !it.split) } },
                        "Theo ${preview.splitHeadings} dòng tiêu đề trong file.", enabled = !state.busy)
                }
            }
            if (preview.footnoteCount > 0) item("footnotes", "footnotes") {
                Column {
                    BasicText("${preview.footnoteCount} chú thích", style = Abook.type.sectionTitle)
                    if (preview.footnoteExample.isNotEmpty()) BasicText(preview.footnoteExample, style = Abook.type.bodySmall)
                    BasicText("Bạn chọn mới đổi phần đọc.", style = Abook.type.bodySmall)
                    if (preview.footnoteMarks > 0) BookChoice("Bỏ số gọi", choice.hideMarks,
                        { revise { it.copy(hideMarks = !it.hideMarks) } }, enabled = !state.busy)
                    BookChoice("Chú cuối chương", choice.notes == "end", { revise { it.copy(notes = if (it.notes == "end") "" else "end") } }, enabled = !state.busy)
                    BookChoice("Bỏ lời chú", choice.notes == "drop", { revise { it.copy(notes = if (it.notes == "drop") "" else "drop") } }, enabled = !state.busy)
                }
            }
            val groups = ImportLogic.groups(ImportLogic.forPicked(preview, choice))
            if (groups.isNotEmpty()) item("suggestion_heading", "heading") {
                Column {
                    BasicText("Gợi ý đọc", style = Abook.type.sectionTitle)
                    BasicText("Bạn chọn dòng cần bỏ đọc. Chữ gốc vẫn được giữ.", style = Abook.type.bodySmall)
                }
            }
            items(groups, key = { "suggestion_${it.line}" }, contentType = { "suggestion" }) { group ->
                BookChoice("Bỏ đọc dòng", group.line in choice.skipped,
                    { choose { it.copy(skipped = if (group.line in it.skipped) it.skipped - group.line else it.skipped + group.line) } },
                    "“${group.line}” · ${group.chapters.size} chương", "suggestion_${group.line}", !state.busy)
            }
            item("chapter_heading", "heading") { BasicText("Chương trong sách", style = Abook.type.sectionTitle) }
            items(preview.chapters, key = { "chapter_${it.index}" }, contentType = { "chapter" }) { row ->
                Column {
                    BookChoice(row.title, row.index in choice.picked,
                        { choose { it.copy(picked = if (row.index in it.picked) it.picked - row.index else it.picked + row.index) } },
                        row.note, "import_chapter_${row.index}", !state.busy)
                    BookField("Tên chương", choice.names[row.index] ?: row.title,
                        { value -> choose { it.copy(names = it.names + (row.index to value)) } }, "import_name_${row.index}", !state.busy)
                }
            }
            items(preview.notes.distinct(), key = { "note_$it" }, contentType = { "note" }) { note ->
                BasicText(note, style = Abook.type.bodySmall)
            }
            item("skip", "action") { BookAction("Bỏ cuốn này", skip, enabled = !state.busy) }
        }
    }
}
