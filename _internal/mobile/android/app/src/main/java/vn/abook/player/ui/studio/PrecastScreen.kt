package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.StudioError
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.StageProgress
import vn.abook.player.ui.components.SwitchRow
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.studio.parts.DecisionStrip
import vn.abook.player.ui.studio.parts.PermissionCard
import vn.abook.player.ui.studio.parts.PollWhileVisible
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/**
 * "Duyệt trước khi thu" (NATIVE_REMOTE_STUDIO.md §6.9): bốn bước (nhân vật và giọng, cách đọc tên, ai nói câu này, xong), mỗi bước hiện thẻ việc của nó từng thẻ
 * một - cùng thẻ, cùng hàng chờ "Hoàn tác" với tab "Việc cần duyệt". Bước nào cũng bỏ qua được. Một nút chính: "Duyệt xong", hay "Thu âm" khi sách đang chờ.
 * `openReadings`: mở màn "Cách đọc tên" đầy đủ.
 */
@Composable
fun PrecastScreen(state: StudioProjectState, sheets: SheetHost, onBack: () -> Unit, openReadings: () -> Unit, active: Boolean = true) {
    val session = state.session
    val poll by state.poll.collectAsState()
    val retries = session.retries
    PollWhileVisible(active, retries) { state.run() }
    PollWhileVisible(active, retries) { state.precast.run() }
    PollWhileVisible(active, retries) { state.work.run() }
    PollWhileVisible(active, retries) { state.cast.run() }
    DisposableEffect(state) { onDispose { state.leave() } }
    val book = poll.data?.book
    val blocked = session.listenOnly || poll.error is StudioError.ListenOnly
    BookForm(PrecastText.TITLE, onBack, "studio_precast") {
        when {
            blocked -> PermissionCard(session.name, session::retry)
            book == null && poll.error == null -> LoadingText()
            book == null -> InlineProblem(poll.error?.let { StudioText.failure(it) }.orEmpty(), state::refreshSoon, "studio_precast_problem")
            else -> PrecastBody(state, book, sheets, onBack, openReadings)
        }
    }
}

@Composable
private fun LoadingText() {
    BasicText(PrecastText.LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.padding(top = Dim.s24).testTag("studio_precast_loading"))
}

@Composable
private fun PrecastBody(state: StudioProjectState, book: StudioBook, sheets: SheetHost, onBack: () -> Unit, openReadings: () -> Unit) {
    val precast = state.precast
    val view = precast.poll.collectAsState().value
    val workPoll = state.work.poll.collectAsState().value
    val castPoll = state.cast.poll.collectAsState().value
    val work = workPoll.data
    val cast = castPoll.data
    val clip = state.work.clip.collectClip()
    val data = view.data
    if (data == null || work == null || cast == null) {
        val failure = view.error ?: workPoll.error ?: castPoll.error
        if (failure == null) LoadingText() else InlineProblem(StudioText.failure(failure), state::refreshSoon, "studio_precast_problem")
        return
    }
    val hiding = state.decisions.hiding()
    val items = work.items.filter { it.key !in hiding }
    val castCards = PrecastLogic.castItems(items)
    val nameCards = PrecastLogic.nameItems(items)
    val lineCards = PrecastLogic.lineItems(items, data.upcoming.map { it.id })
    val people = cast.characters.take(PrecastLogic.TOP_PEOPLE)
    val step = precast.step
    val total = PrecastStep.entries.size
    val list = rememberLazyListState()
    LazyColumn(Modifier.fillMaxSize().fadeEdges(list).testTag("studio_precast_list"), state = list, contentPadding = PaddingValues(bottom = Dim.s16)) {
        item("head", "head") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
                if (book.precastHeld) RowHint(PrecastText.HELD, Modifier.testTag("studio_precast_held"), Abook.colors.accentText)
                RowHint(PrecastText.LEAD, Modifier.padding(top = Dim.s4))
                if (PrecastLogic.showWait(data)) {
                    SwitchRow(PrecastText.WAIT, data.wait, { precast.setWait(it) }, "studio_precast_wait", hint = PrecastLogic.waitHint(data))
                }
                InlineProblem(precast.problem, null, "studio_precast_wait_problem")
                Fold(PrecastText.WHEN, "studio_precast_when") { RowHint(PrecastLogic.freeNote(data), Modifier.padding(bottom = Dim.s8).testTag("studio_precast_free")) }
            }
        }
        item("undo", "undo") { DecisionStrip(state.decisions) }
        item("steps", "steps") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                ClockLabel(PrecastText.step(step.ordinal + 1, total), Modifier.testTag("studio_precast_step"), Abook.type.label)
                StageProgress { (step.ordinal + 1) / total.toFloat() }
                BasicText(step.label, style = Abook.type.sectionTitle, modifier = Modifier.padding(top = Dim.s12).testTag("studio_precast_step_title"))
                val count = PrecastLogic.count(step, castCards, nameCards, lineCards, people.size)
                if (count.isNotEmpty()) Caption(count, Modifier.padding(top = Dim.s4).testTag("studio_precast_count"))
            }
        }
        item("step_${step.name}", "step") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s8).testTag("studio_precast_${step.name.lowercase()}")) {
                when (step) {
                    PrecastStep.Cast -> {
                        RowHint(PrecastText.CAST_LEAD)
                        for (person in people) {
                            ListItem(
                                person.displayName, Modifier, { openVoiceSheet(state, sheets, person.name, person.displayName) }, "studio_precast_person_${person.name}",
                                hint = person.voice?.label.orEmpty().ifEmpty { "${person.lines} câu" }, chevron = true,
                            )
                            RowLine()
                        }
                        if (castCards.isNotEmpty()) {
                            BasicText(PrecastText.CAST_UNSURE, style = Abook.type.sectionTitle, modifier = Modifier.padding(top = Dim.s16))
                            Caption(PrecastText.castUnsure(castCards.size), Modifier.padding(top = Dim.s4))
                        }
                        castCards.firstOrNull()?.let { WorkCard(it, castCards.size, state, sheets, clip) {} }
                    }
                    PrecastStep.Names -> {
                        RowHint(PrecastText.namesLead(nameCards.size))
                        nameCards.firstOrNull()?.let { WorkCard(it, nameCards.size, state, sheets, clip) {} }
                        DisclosureRow(PrecastText.NAMES_OPEN, openReadings, "studio_precast_readings", Modifier.padding(top = Dim.s16))
                    }
                    PrecastStep.Lines -> {
                        RowHint(PrecastText.linesLead(PrecastLogic.lineCount(lineCards), PrecastLogic.chapterRange(data.upcoming), data.upcoming.isNotEmpty()))
                        lineCards.firstOrNull()?.let { WorkCard(it, lineCards.size, state, sheets, clip) {} }
                    }
                    PrecastStep.Done -> {
                        BasicText(PrecastText.DONE_TITLE, style = Abook.type.sectionTitle, modifier = Modifier.padding(top = Dim.s16))
                        RowHint(PrecastText.done(book), Modifier.padding(top = Dim.s8).testTag("studio_precast_done"))
                    }
                }
            }
        }
        item("actions", "actions") {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s24), verticalArrangement = Arrangement.spacedBy(Dim.s8), horizontalAlignment = Alignment.Start) {
                if (step == PrecastStep.Done) {
                    if (book.precastHeld) PrimaryButton(PrecastText.RECORD, { state.send(StudioCommand.Pause(false)); onBack() }, Modifier.fillMaxWidth().testTag("studio_precast_record"), enabled = !state.busy)
                    else PrimaryButton(PrecastText.FINISH, onBack, Modifier.fillMaxWidth().testTag("studio_precast_finish"))
                    QuietButton(PrecastText.BACK, onBack, "studio_precast_back")
                } else {
                    PrimaryButton(PrecastText.NEXT, precast::next, Modifier.fillMaxWidth().testTag("studio_precast_next"))
                    QuietButton(PrecastText.SKIP, precast::next, "studio_precast_skip")
                }
                InlineProblem(state.problem, state::retryLast, "studio_problem")
            }
        }
    }
}
