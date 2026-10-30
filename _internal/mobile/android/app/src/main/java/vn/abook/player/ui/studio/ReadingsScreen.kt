package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import kotlinx.coroutines.launch
import vn.abook.player.ClipState
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.studio.parts.ClipButton
import vn.abook.player.ui.studio.parts.ClipProblem
import vn.abook.player.ui.studio.parts.DecisionStrip
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.studio.parts.UndoStrip
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * "Cách đọc tên" (NATIVE_REMOTE_STUDIO.md §6.10): mọi tên riêng máy đọc thế nào. Chạm "Sửa" mở ô một dòng ngay dưới tên: gõ, "Nghe thử", rồi "Lưu" (máy kiểm,
 * rồi giữ 15 giây cho "Hoàn tác"). Chữ gõ một mình (không có trong danh sách) cũng thêm được. Dòng ghi công máy gợi ý bỏ nằm riêng ở cuối, mặc định không áp.
 */
@Composable
fun ReadingsScreen(state: StudioReadingsState, onBack: () -> Unit, active: Boolean = true) {
    val session = state.session
    PollWhileVisible(active, session.retries) { state.run() }
    DisposableEffect(state) { onDispose { state.leave() } }
    val poll by state.poll.collectAsState()
    val clip = state.clip.collectClip()
    val data = poll.data?.let(state::shown)
    val blocked = session.listenOnly || poll.error is StudioError.ListenOnly
    BookForm(ReadingsText.TITLE, onBack, "studio_readings") {
        when {
            blocked -> PermissionCard(session.name, session::retry)
            data == null && poll.error == null -> BasicText(
                ReadingsText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2),
                modifier = Modifier.padding(top = Dim.s24).testTag("studio_readings_loading"),
            )
            data == null -> InlineProblem(poll.error?.let { StudioText.failure(it) }.orEmpty(), state::refreshSoon, "studio_readings_problem")
            else -> ReadingsList(state, data, clip, poll.error)
        }
    }
}

@Composable
private fun ReadingsList(state: StudioReadingsState, data: NameReadings, clip: ClipState, error: StudioError?) {
    val list = rememberLazyListState()
    var editing by rememberSaveable { mutableStateOf<String?>(null) }
    val found = ReadingsLogic.find(data.items, state.query)
    val typed = state.query.trim()
    val addable = ReadingsLogic.addable(state.query, found)
    val counted = data.items.count { it.lines > 0 }
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_readings_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("lead", "lead") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                Caption(ReadingsText.count(counted, state.analyzed), Modifier.testTag("studio_readings_count"))
                RowHint(ReadingsText.LEAD, Modifier.padding(top = Dim.s4))
                InlineProblem(error?.let { StudioText.failure(it) }.orEmpty(), state::refreshSoon, "studio_readings_stale")
            }
        }
        item("undo", "undo") {
            Column(Modifier.fillMaxWidth()) {
                DecisionStrip(state.decisions)
                if (state.notice.isNotEmpty()) UndoStrip(state.notice, null, state::dismissNotice, "studio_readings_notice", Modifier.padding(top = Dim.s12))
            }
        }
        if (state.offer.isNotEmpty()) item("offer", "offer") {
            TextAction(ReadingsText.sharedOffer(state.offer.size), state::applyShared, "studio_readings_offer", Modifier.fillMaxWidth(), Alignment.CenterStart)
        }
        item("search", "search") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8, bottom = Dim.s8)) {
                BookField(null, state.query, state::search, "studio_readings_search", description = ReadingsText.SEARCH, placeholder = ReadingsText.SEARCH)
            }
        }
        items(found.take(state.limit), key = { "reading_${it.surface}" }, contentType = { "reading" }) { item ->
            ReadingRow(state, item, clip, fresh = false, editing = editing == item.surface, onEdit = { editing = if (it) item.surface else null })
        }
        if (addable) item("fresh_$typed", "reading") {
            val fresh = remember(typed) { NameReading(typed, "", false, 0, null, false, null) }
            LaunchedEffect(typed) { state.askReach(typed) }
            ReadingRow(state, fresh, clip, fresh = true, editing = editing == typed, onEdit = { editing = if (it) typed else null })
        }
        if (found.isEmpty() && !addable && typed.isNotEmpty()) item("nomatch", "status") {
            RowHint(ReadingsText.NO_MATCH, Modifier.padding(top = Dim.s12).testTag("studio_readings_nomatch"))
        }
        if (found.size > state.limit) item("more", "more") {
            TextAction(ReadingsText.more(found.size - state.limit), state::more, "studio_readings_more", Modifier.fillMaxWidth(), Alignment.CenterStart)
        }
        if (data.unseen > 0 && typed.isEmpty()) item("unseen", "status") {
            Caption(ReadingsText.unseen(data.unseen), Modifier.padding(top = Dim.s8).testTag("studio_readings_unseen"))
        }
        if (state.credits.isNotEmpty()) item("credits", "credits") { Credits(state) }
        item("clip", "clip") { ClipProblem(clip) }
    }
}

/** Một tên: nút nghe câu mẫu, tên "đọc là ...", dòng phụ, và nút "Sửa" (hay ô sửa khi đang mở). */
@Composable
private fun ReadingRow(state: StudioReadingsState, item: NameReading, clip: ClipState, fresh: Boolean, editing: Boolean, onEdit: (Boolean) -> Unit) {
    val example = item.example
    val reach = if (fresh) state.reach else null
    Column(Modifier.fillMaxWidth().testTag("studio_reading_${item.surface}")) {
        Row(Modifier.fillMaxWidth().padding(top = Dim.s12), verticalAlignment = Alignment.Top) {
            if (example != null && example.hasAudio) {
                ClipButton(StudioReadingsState.sampleId(example), clip, { state.playSample(example) }, "studio_reading_play_${item.surface}")
            }
            Column(Modifier.weight(1f)) {
                BasicText(
                    if (item.spoken.isNotEmpty()) "${item.surface} đọc là “${ReadingsLogic.shown(item.spoken)}”" else item.surface,
                    style = Abook.type.bodyStrong, modifier = Modifier.testTag("studio_reading_title"),
                )
                val note = when {
                    fresh -> reach?.let(ReadingsLogic::reachSummary) ?: ReadingsText.SHARED_NONE
                    else -> ReadingsLogic.rowNote(item, state.analyzed, state.sharedHere(item))
                }
                RowHint(note, Modifier.padding(top = Dim.s4).testTag("studio_reading_note"))
            }
            if (!editing) TextAction(if (fresh) ReadingsText.add(item.surface) else ReadingsText.EDIT, { onEdit(true) }, "studio_reading_edit_${item.surface}")
        }
        if (editing) ReadingEditor(state, item, fresh, reach) { onEdit(false) }
        RowLine()
    }
}

/**
 * Ô sửa một cách đọc. Lưu = máy KIỂM trước ([StudioReadingsState.save]): chê thì lỗi hiện ngay dưới ô (kèm bản viết lại đúng nếu máy có), không biến thành một lần
 * gửi hỏng sau 15 giây. "Nghe thử" nhờ máy tính đọc một câu có tên ấy bằng cách đang gõ (tới ~2 phút); trong lúc chờ có "Huỷ".
 */
@Composable
private fun ReadingEditor(state: StudioReadingsState, item: NameReading, fresh: Boolean, reach: Reach?, onDone: () -> Unit) {
    val scope = rememberCoroutineScope()
    var value by remember(item.surface) { mutableStateOf(ReadingsLogic.shown(item.requested ?: item.spoken)) }
    var problem by remember(item.surface) { mutableStateOf("") }
    var suggestion by remember(item.surface) { mutableStateOf("") }
    var heard by remember(item.surface) { mutableStateOf("") }
    var busy by remember(item.surface) { mutableStateOf(false) }
    var everywhere by remember(item.surface) { mutableStateOf(ReadingsLogic.sharedEntry(state.shared, item.surface) != null) }
    val typed = value.trim()
    val never = reach?.never ?: item.never
    val trying = state.trying == item.surface
    val unchanged = !fresh && !everywhere && ReadingsLogic.asStored(item, typed) == (item.requested ?: item.spoken)

    fun clear() {
        problem = ""
        suggestion = ""
        heard = ""
    }

    fun save(spoken: String) {
        if (busy || spoken.isEmpty()) return
        busy = true
        clear()
        scope.launch {
            when (val checked = state.save(item, spoken, everywhere)) {
                ReadingCheck.Ok -> onDone()
                is ReadingCheck.Rejected -> {
                    problem = checked.message
                    suggestion = checked.suggestion
                }
                is ReadingCheck.Failed -> problem = checked.message
            }
            busy = false
        }
    }

    fun tryIt() {
        if (typed.isEmpty() || trying) return
        clear()
        heard = ReadingsText.TRYING
        state.tryReading(item.surface, typed) { outcome ->
            when (outcome) {
                is PreviewOutcome.Ready -> heard = VoiceLogic.previewCaption(outcome.preview.text, "")
                is PreviewOutcome.Rejected -> {
                    problem = outcome.message
                    suggestion = outcome.suggestion
                    heard = ""
                }
                is PreviewOutcome.Refused -> heard = outcome.text
            }
        }
    }

    Column(Modifier.fillMaxWidth().padding(top = Dim.s8, bottom = Dim.s12).testTag("studio_reading_editor")) {
        BookField(
            null, value, { value = it; clear() }, "studio_reading_field",
            description = ReadingsText.FIELD, placeholder = "vd ${item.spoken.ifEmpty { "Hên-khơ" }}",
        )
        InlineProblem(problem, null, "studio_reading_problem")
        if (suggestion.isNotEmpty()) {
            TextAction(WorkText.readingUse(suggestion), { value = suggestion; save(suggestion) }, "studio_reading_suggestion", align = Alignment.CenterStart)
        }
        if (never) RowHint(ReadingsLogic.neverText(item.surface), Modifier.padding(top = Dim.s4).testTag("studio_reading_never"), Abook.colors.danger)
        if (heard.isNotEmpty()) RowHint(heard, Modifier.padding(top = Dim.s4).testTag("studio_reading_heard"))
        SwitchRow(ReadingsText.EVERYWHERE, everywhere, { everywhere = it }, "studio_reading_everywhere")
        Column(Modifier.fillMaxWidth().padding(top = Dim.s8), verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(Dim.s8)) {
            if (trying) AnswerButton(ReadingsText.TRY_STOP, state::cancelTry, "studio_reading_cancel_try")
            else AnswerButton(ReadingsText.TRY, ::tryIt, "studio_reading_try", enabled = !busy && typed.isNotEmpty())
            AnswerButton(ReadingsText.SAVE, { save(typed) }, "studio_reading_save", primary = true, enabled = !busy && typed.isNotEmpty() && !never && !unchanged)
            AnswerButton(ReadingsText.CANCEL, { state.cancelTry(); onDone() }, "studio_reading_close")
        }
    }
}

/** Mục riêng cuối màn: dòng ghi công / xin ủng hộ máy gợi ý bỏ khỏi phần đọc. MẶC ĐỊNH KHÔNG ÁP; chữ của truyện không bao giờ bị sửa. */
@Composable
private fun Credits(state: StudioReadingsState) {
    Fold(ReadingsText.SUGGEST_TITLE, "studio_readings_credits", Modifier.padding(top = Dim.s24), summary = "${state.credits.size}") {
        RowHint(ReadingsText.SUGGEST_LEAD, Modifier.padding(bottom = Dim.s8))
        for ((index, group) in state.credits.withIndex()) {
            SwitchRow(
                ReadingsText.SUGGEST_SKIP, group.skipped, { state.skipLine(group, it) }, "studio_credit_$index",
                hint = "“${group.line}” · ${ReadingsLogic.where(group)}",
            )
        }
    }
}
