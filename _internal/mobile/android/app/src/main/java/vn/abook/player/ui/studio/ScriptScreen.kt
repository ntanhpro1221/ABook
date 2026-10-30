package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.ClipState
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.screens.PickRow
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.studio.parts.ClipButton
import vn.abook.player.ui.studio.parts.ClipProblem
import vn.abook.player.ui.studio.parts.DecisionStrip
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * "Kịch bản" (NATIVE_REMOTE_STUDIO.md §6.8): cả chương đọc như kịch bản. Chạm tên người nói để đổi người (bảng chọn, giữ 15 giây cho "Hoàn tác"); chạm "Sửa chữ"
 * để đổi chữ ĐEM ĐỌC của câu - chữ của sách không bao giờ bị sửa. Đổi chương bằng "Đổi chương" hay hai nút trước / sau.
 */
@Composable
fun ScriptScreen(state: StudioScriptState, sheets: SheetHost, onBack: () -> Unit, active: Boolean = true) {
    val session = state.session
    PollWhileVisible(active, session.retries) { state.run() }
    DisposableEffect(state) { onDispose { state.leave() } }
    val clip = state.clip.collectClip()
    val blocked = session.listenOnly || state.error is StudioError.ListenOnly
    BookForm(ScriptText.TITLE, onBack, "studio_script") {
        val contents = state.contents
        val script = state.shown()
        when {
            blocked -> PermissionCard(session.name, session::retry)
            contents == null && state.error == null -> BasicText(
                ScriptText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2),
                modifier = Modifier.padding(top = Dim.s24).testTag("studio_script_loading"),
            )
            contents == null -> InlineProblem(state.error?.let { StudioText.failure(it) }.orEmpty(), state::retry, "studio_script_problem")
            else -> ScriptBody(state, contents, script, clip, sheets)
        }
    }
}

@Composable
private fun ScriptBody(state: StudioScriptState, contents: ScriptContents, script: ChapterScript?, clip: ClipState, sheets: SheetHost) {
    val list = rememberLazyListState()
    var editing by rememberSaveable { mutableStateOf<String?>(null) }
    val entry = contents.chapters.firstOrNull { it.chapterId == state.chapter }
    val shown = script?.let { ScriptLogic.visible(it.lines, state.filter) }.orEmpty()
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_script_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("head", "head") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                DisclosureRow(
                    entry?.let(ScriptLogic::chapterLabel) ?: ScriptText.CHAPTERS, { sheets.show { dismiss -> ChaptersSheet(state, contents, dismiss) } }, "studio_script_chapters",
                    summary = entry?.let(ScriptLogic::extras),
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    if (script?.previous != null) TextAction(ScriptText.PREVIOUS, { state.open(script.previous) }, "studio_script_previous", align = Alignment.CenterStart)
                    else Spacer(Modifier)
                    if (script?.next != null) TextAction(ScriptText.NEXT, { state.open(script.next) }, "studio_script_next")
                }
                DisclosureRow(filterName(state.filter, script), { sheets.show { dismiss -> FilterSheet(state, script, dismiss) } }, "studio_script_filter")
                InlineProblem(state.error?.let { StudioText.failure(it) }.orEmpty(), state::retry, "studio_script_stale")
            }
        }
        item("undo", "undo") { DecisionStrip(state.decisions) }
        if (!contents.castReady) item("not_ready", "status") {
            RowHint(ScriptText.NOT_READY, Modifier.padding(top = Dim.s12).testTag("studio_script_not_ready"))
        }
        if (script == null && state.error == null) item("loading_chapter", "status") {
            RowHint(ScriptText.LOADING, Modifier.padding(top = Dim.s12).testTag("studio_script_chapter_loading"))
        }
        if (script != null && shown.isEmpty()) item("empty", "status") {
            RowHint(ScriptText.EMPTY, Modifier.padding(top = Dim.s12).testTag("studio_script_empty"))
        }
        if (script != null) {
            items(shown, key = { "line_${it.line.stableId}_${it.context}" }, contentType = { "line" }) { row ->
                LineRow(state, script, row, clip, sheets, editing == row.line.stableId, { editing = if (it) row.line.stableId else null })
            }
        }
        item("clip", "clip") { ClipProblem(clip) }
    }
}

/** Một câu: người nói (chạm để đổi), chữ của sách, chữ đem đọc nếu đã đổi, và "Sửa chữ". Câu ngữ cảnh (trước chỗ nghi) mờ và không có nút. */
@Composable
private fun LineRow(state: StudioScriptState, script: ChapterScript, row: ShownLine, clip: ClipState, sheets: SheetHost, editing: Boolean, onEdit: (Boolean) -> Unit) {
    val line = row.line
    Column(Modifier.fillMaxWidth().then(if (row.context) Modifier.alpha(0.6f) else Modifier).testTag("studio_line_${line.stableId}")) {
        Row(Modifier.fillMaxWidth().padding(top = Dim.s12), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                val label = ScriptLogic.speakerLabel(line).ifEmpty { ScriptText.NARRATION }
                if (line.editable && !row.context) {
                    TextAction(label, { sheets.show { dismiss -> PeopleSheet(state, script, line, dismiss) } }, "studio_line_who_${line.stableId}", align = Alignment.CenterStart)
                } else {
                    BasicText(label, style = Abook.type.label, modifier = Modifier.testTag("studio_line_who_${line.stableId}"))
                }
                val pending = line.wish?.state == "pending"
                Caption(listOfNotNull(ScriptText.line(line.seq), ScriptText.PENDING.takeIf { pending }, ScriptText.CONTEXT.takeIf { row.context }).joinToString(" · "))
            }
            if (line.hasAudio && !row.context) ClipButton(StudioScriptState.clipId(line), clip, { state.play(line) }, "studio_line_play_${line.stableId}")
        }
        BasicText(line.text, style = Abook.type.body, modifier = Modifier.padding(top = Dim.s4).testTag("studio_line_text_${line.stableId}"))
        val spoken = line.lineWish?.spoken ?: line.spoken
        if (!spoken.isNullOrEmpty() && !editing) {
            RowHint("${ScriptText.READ_AS}: $spoken", Modifier.padding(top = Dim.s4).testTag("studio_line_spoken_${line.stableId}"))
        }
        val hint = line.hint
        if (hint != null && !row.context) RowHint(ScriptText.suggest(hint.note, hint.suggest), Modifier.padding(top = Dim.s4).testTag("studio_line_hint_${line.stableId}"), Abook.colors.accentText)
        if (editing) SpokenEditor(state, line) { onEdit(false) }
        else if (line.editable && !row.context) TextAction(ScriptText.SPOKEN, { onEdit(true) }, "studio_line_edit_${line.stableId}", align = Alignment.CenterStart)
        RowLine()
    }
}

/** Ô "Chữ đem đọc": chỉ đổi điều máy đọc; ô trống hay đúng chữ sách là đọc đúng chữ của sách. */
@Composable
private fun SpokenEditor(state: StudioScriptState, line: ScriptLine, onDone: () -> Unit) {
    val start = (line.lineWish?.spoken ?: line.spoken).orEmpty().ifEmpty { line.text }
    var value by remember(line.stableId) { mutableStateOf(start) }
    Column(Modifier.fillMaxWidth().padding(top = Dim.s8, bottom = Dim.s12).testTag("studio_line_editor")) {
        BookField(null, value, { value = it }, "studio_line_field", description = ScriptText.SPOKEN)
        RowHint(ScriptText.SPOKEN_HINT, Modifier.padding(top = Dim.s4))
        Column(Modifier.fillMaxWidth().padding(top = Dim.s8), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
            AnswerButton(ScriptText.SAVE, { state.speak(line, value); onDone() }, "studio_line_save", primary = true, enabled = ScriptLogic.spokenChange(line, value) != null)
            AnswerButton(ScriptText.ORIGINAL, { value = line.text; state.speak(line, line.text); onDone() }, "studio_line_original", enabled = !(line.lineWish?.spoken ?: line.spoken).isNullOrEmpty())
            AnswerButton(ScriptText.CANCEL, onDone, "studio_line_close")
        }
    }
}

@Composable
private fun PeopleSheet(state: StudioScriptState, script: ChapterScript, line: ScriptLine, dismiss: () -> Unit) {
    val current = ScriptLogic.speaker(line)
    Column(Modifier.fillMaxWidth().testTag("studio_script_people")) {
        BasicText(ScriptText.WHO, style = Abook.type.sectionTitle)
        Spacer(Modifier.padding(top = Dim.s8))
        val list1 = rememberLazyListState()
        LazyColumn(Modifier.heightIn(max = 420.dp).fadeEdges(list1), state = list1) {
            items(ScriptLogic.people(script), key = { "person_${it.value}" }) { person ->
                PickRow(person.label, if (person.lines > 0) "${person.lines} câu" else null, person.value == current, { dismiss(); state.assign(line, person) }, "studio_person_${person.value}")
            }
        }
    }
}

@Composable
private fun ChaptersSheet(state: StudioScriptState, contents: ScriptContents, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("studio_script_chapters_sheet")) {
        BasicText(ScriptText.CHAPTERS, style = Abook.type.sectionTitle)
        Spacer(Modifier.padding(top = Dim.s8))
        val list2 = rememberLazyListState()
        LazyColumn(Modifier.heightIn(max = 420.dp).fadeEdges(list2), state = list2) {
            items(contents.chapters, key = { "chapter_${it.chapterId}" }) { entry ->
                PickRow(ScriptLogic.chapterLabel(entry), ScriptLogic.extras(entry).ifEmpty { null }, entry.chapterId == state.chapter, { dismiss(); state.open(entry.chapterId) }, "studio_script_chapter_${entry.chapterId}")
            }
        }
    }
}

@Composable
private fun FilterSheet(state: StudioScriptState, script: ChapterScript?, dismiss: () -> Unit) {
    Column(Modifier.fillMaxWidth().testTag("studio_script_filter_sheet")) {
        for (option in ScriptFilter.entries) {
            PickRow(filterName(option, script), null, option == state.filter, { dismiss(); state.filter = option }, "studio_script_filter_${option.name.lowercase()}")
        }
    }
}

/** Tên bộ lọc; "Máy nghi" kèm số chỗ nghi của chương đang xem. */
private fun filterName(filter: ScriptFilter, script: ChapterScript?): String =
    if (filter == ScriptFilter.Doubt && script != null) ScriptText.doubt(ScriptLogic.doubts(script.lines)) else filter.label
