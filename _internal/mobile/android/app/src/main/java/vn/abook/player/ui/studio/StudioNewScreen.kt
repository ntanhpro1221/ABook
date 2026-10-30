package vn.abook.player.ui.studio

import android.content.Context
import android.net.Uri
import android.provider.OpenableColumns
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.data.Choice
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import java.io.IOException

/**
 * "Sách mới" trên máy tính (NATIVE_REMOTE_STUDIO.md §6.12): ba bước Nguồn, Chương, Bắt đầu. Điện thoại gửi từng file truyện lên máy tính (nói trước mỗi tệp tối đa 17 MB), máy tính đọc ra
 * chương, bạn bỏ chương không muốn, rồi đặt tên và bấm "Bắt đầu". Chữ của truyện không bao giờ bị sửa ở đây.
 */
@Composable
fun StudioNewRoute(hub: StudioHub, computer: String, onBack: () -> Unit, onCreated: (String) -> Unit, active: Boolean) {
    val state = remember(hub, computer) { StudioNewState(hub.session(computer)) }
    StudioNewScreen(state, onBack, onCreated, active)
}

@Composable
fun StudioNewScreen(state: StudioNewState, onBack: () -> Unit, onCreated: (String) -> Unit, active: Boolean = true) {
    val session = state.session
    val context = LocalContext.current
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris -> state.add(uris.map { picked(context, it) }) }
    // Back lùi từng bước; ở bước đầu mới rời màn.
    BackHandler(enabled = active && state.step != NewStep.Source) { state.back() }
    LaunchedEffect(state.created) { state.created?.let { onCreated(it.id) } }
    BookForm(
        StudioNewText.TITLE, { if (state.step == NewStep.Source) onBack() else state.back() }, "studio_new",
        footer = if (session.listenOnly) null else ({ NewFooter(state) }),
    ) {
        if (session.listenOnly) {
            PermissionCard(session.name, session::retry)
        } else {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s4)) {
                RowHint(StudioNewText.stepOf(state.step) + " · " + state.step.label, Modifier.testTag("studio_new_step"))
                StageProgress { StudioNewLogic.stepFraction(state.step) }
            }
            SheetPages(state.step, { it.ordinal }, "studio_new_pages") { shown ->
                when (shown) {
                    NewStep.Source -> SourceStep(state, { picker.launch(arrayOf("*/*")) })
                    NewStep.Chapters -> ChaptersStep(state)
                    NewStep.Start -> StartStep(state)
                }
            }
        }
    }
}

/** Tên và cỡ của một tệp người dùng chọn; luồng chỉ mở khi gửi. */
private fun picked(context: Context, uri: Uri): PickedFile {
    var name = ""
    var size = 0L
    runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { cursor ->
            if (cursor.moveToFirst()) {
                name = cursor.getString(0).orEmpty()
                size = if (cursor.isNull(1)) 0L else cursor.getLong(1)
            }
        }
    }
    if (name.isEmpty()) name = uri.lastPathSegment.orEmpty().substringAfterLast('/')
    return PickedFile(name, size) { context.contentResolver.openInputStream(uri) ?: throw IOException(name) }
}

@Composable
private fun NewFooter(state: StudioNewState) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
        InlineProblem(state.problem, null, "studio_new_problem")
        when (state.step) {
            NewStep.Source -> PrimaryButton(
                if (state.scanning) StudioNewText.SCANNING else StudioNewText.NEXT, state::next, Modifier.fillMaxWidth().testTag("studio_new_next"), enabled = state.canScan,
            )
            NewStep.Chapters -> {
                PrimaryButton(if (state.scanning) StudioNewText.SCANNING else StudioNewText.NEXT, state::next, Modifier.fillMaxWidth().testTag("studio_new_next"), enabled = state.kept.isNotEmpty() && !state.scanning)
                TextAction(StudioNewText.BACK, state::back, "studio_new_back", Modifier.fillMaxWidth(), align = Alignment.Center)
            }
            NewStep.Start -> {
                PrimaryButton(if (state.creating) StudioNewText.CREATING else StudioNewText.CREATE, state::create, Modifier.fillMaxWidth().testTag("studio_new_create"), enabled = state.canCreate)
                TextAction(StudioNewText.BACK, state::back, "studio_new_back", Modifier.fillMaxWidth(), align = Alignment.Center)
            }
        }
    }
}

// ---- bước Nguồn ----

@Composable
private fun SourceStep(state: StudioNewState, pick: () -> Unit) {
    var pasted by remember { mutableStateOf("") }
    val list = rememberLazyListState()
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_new_source"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("lead", "lead") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                RowHint(StudioNewText.LEAD, Modifier.testTag("studio_new_lead"))
                // Giới hạn thật của đường gửi, nói TRƯỚC khi chọn (không để hỏng giữa chừng).
                Caption(StudioNewText.LIMIT_NOTE, Modifier.padding(top = Dim.s4).testTag("studio_new_limit"))
                PrimaryButton(StudioNewText.PICK, pick, Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("studio_new_pick"))
            }
        }
        item("paste", "paste") {
            Fold(StudioNewText.PASTE, "studio_new_paste", Modifier.padding(top = Dim.s8)) {
                BookField(null, pasted, { pasted = it }, "studio_new_paste_field", description = StudioNewText.PASTE_HINT, placeholder = StudioNewText.PASTE_HINT)
                TextAction(StudioNewText.PASTE_ADD, { state.addText(pasted); pasted = "" }, "studio_new_paste_add", Modifier.fillMaxWidth())
            }
        }
        if (state.rows.isEmpty()) {
            item("none", "status") { RowHint(StudioNewText.NO_SOURCE, Modifier.padding(top = Dim.s16).testTag("studio_new_none")) }
        } else {
            items(state.rows, key = { "row_${it.id}" }, contentType = { "row" }) { row -> UploadRow(state, row) }
        }
    }
}

@Composable
private fun UploadRow(state: StudioNewState, row: SourceRow) {
    val sending = row.status == UploadStatus.Sending
    val bad = row.status == UploadStatus.Failed || row.status == UploadStatus.TooBig || row.status == UploadStatus.NotStory
    val hint = when (row.status) {
        UploadStatus.Waiting -> StudioNewText.WAITING
        UploadStatus.Sending -> StudioNewText.sending(row) + " · " + StudioNewText.percent(state.progressOf(row))
        UploadStatus.Sent -> StudioNewText.SENT
        else -> row.problem
    }
    Column(Modifier.fillMaxWidth().testTag("studio_new_row_${row.id}")) {
        ListItem(
            row.name, Modifier, null, "studio_new_row_name", hint = hint, hintColor = if (bad) Abook.colors.danger else Abook.colors.text2, tickingHint = sending,
            trailing = {
                when (row.status) {
                    UploadStatus.Sending -> TextAction(StudioNewText.CANCEL, { state.remove(row.id) }, "studio_new_row_cancel_${row.id}")
                    UploadStatus.Failed -> TextAction(StudioNewText.RETRY, { state.retry(row.id) }, "studio_new_row_retry_${row.id}")
                    else -> TextAction(StudioNewText.REMOVE, { state.remove(row.id) }, "studio_new_row_remove_${row.id}")
                }
            },
            below = { if (sending) StageProgress { state.progressOf(row) } },
        )
        RowLine()
    }
}

// ---- bước Chương ----

@Composable
private fun ChaptersStep(state: StudioNewState) {
    val scan = state.scan
    val list = rememberLazyListState()
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_new_chapters"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("lead", "lead") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                RowHint(StudioNewText.CHAPTERS_LEAD)
                RowHint(StudioNewLogic.totals(state.kept), Modifier.padding(top = Dim.s4).testTag("studio_new_totals"), Abook.colors.text)
                for (line in scan?.errors.orEmpty() + scan?.notes.orEmpty()) Caption(line, Modifier.padding(top = Dim.s4).testTag("studio_new_scan_note"))
                if (scan != null && scan.existing.isNotEmpty()) {
                    BasicText(StudioNewText.EXISTING, style = Abook.type.bodyStrong, modifier = Modifier.padding(top = Dim.s12).testTag("studio_new_existing"))
                    for (book in scan.existing) RowHint("${book.title} · ${book.statusLabel}")
                }
            }
        }
        if (scan != null) {
            items(scan.files, key = { "chapter_${it.path}" }, contentType = { "chapter" }) { chapter -> ChapterRow(state, chapter) }
        }
    }
}

@Composable
private fun ChapterRow(state: StudioNewState, chapter: ScannedChapter) {
    val kept = state.isKept(chapter)
    val label = chapter.title.ifEmpty { chapter.name }
    val hint = listOfNotNull(
        chapter.matter.takeIf { it.isNotEmpty() }?.let { StudioNewText.MATTER },
        chapter.firstLine.takeIf { it.isNotEmpty() },
    ).joinToString(" · ").ifEmpty { null }
    Column(Modifier.fillMaxWidth().testTag("studio_new_chapter")) {
        SwitchRow(label, kept, { state.toggle(chapter.path) }, "studio_new_chapter_${chapter.path.hashCode()}", hint)
        if (chapter.splitChapters > 1) {
            RowHint(StudioNewText.SPLIT_NOTE, Modifier.testTag("studio_new_split_note"))
            TextAction(StudioNewText.splitAsk(chapter.splitChapters), { state.split(chapter) }, "studio_new_split_${chapter.path.hashCode()}", Modifier.fillMaxWidth(), align = Alignment.CenterStart)
        }
        RowLine()
    }
}

// ---- bước Bắt đầu ----

private data class ModelChoice(override val key: String, override val label: String) : Choice

@Composable
private fun StartStep(state: StudioNewState) {
    val list = rememberLazyListState()
    val hint = state.hint
    val models = state.models
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_new_start"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("title", "field") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                BookField(StudioNewText.TITLE_LABEL, state.title, state::editTitle, "studio_new_title")
            }
        }
        item("firstperson", "field") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s12)) {
                BookField(StudioNewText.FIRST_PERSON, state.firstPerson, state::editFirstPerson, "studio_new_first_person", placeholder = StudioNewText.FIRST_PERSON_PLACEHOLDER)
                RowHint(StudioNewText.FIRST_PERSON_HINT, Modifier.padding(top = Dim.s4))
                Reveal(hint != null && hint.suggestions.isNotEmpty() && state.firstPerson.isBlank()) {
                    Column(Modifier.fillMaxWidth()) {
                        for (name in hint?.suggestions.orEmpty().take(4)) {
                            TextAction(name, { state.editFirstPerson(name) }, "studio_new_suggest_${name.hashCode()}", Modifier.fillMaxWidth(), align = Alignment.CenterStart)
                        }
                    }
                }
            }
        }
        item("profile", "field") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                SectionTitle(StudioNewText.QUALITY, first = true)
                ChoiceRow(NewProfile.entries, state.profile, { picked, _ -> state.pickProfile(picked) }, Modifier.fillMaxWidth(), tag = "studio_new_profile")
                SheetPages(state.profile, { it.ordinal }, "studio_new_profile_about") { shown -> RowHint(shown.summary, Modifier.padding(top = Dim.s4)) }
            }
        }
        if (models != null && models.others.isNotEmpty()) {
            item("model", "field") {
                val choices = remember(models) { listOf(ModelChoice("", StudioNewText.MODEL_DEFAULT)) + models.others.map { ModelChoice(it.name, it.name) } }
                Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                    SectionTitle(StudioNewText.MODEL)
                    ChoiceRow(choices, choices.firstOrNull { it.key == state.model } ?: choices.first(), { picked, _ -> state.pickModel(picked.key) }, Modifier.fillMaxWidth(), tag = "studio_new_model")
                    RowHint(StudioNewText.MODEL_HINT, Modifier.padding(top = Dim.s4))
                }
            }
        }
        item("switches", "field") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                SwitchRow(StudioNewText.WAIT, state.wait, state::chooseWait, "studio_new_wait", StudioNewText.WAIT_HINT)
                RowLine()
                SwitchRow(StudioNewText.START_NOW, state.startNow, state::chooseStartNow, "studio_new_start_now", StudioNewText.START_NOW_HINT)
                RowLine()
            }
        }
    }
}
