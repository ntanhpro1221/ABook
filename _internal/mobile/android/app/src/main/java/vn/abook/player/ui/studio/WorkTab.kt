package vn.abook.player.ui.studio

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.MutableState
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
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ClipState
import vn.abook.player.StudioErrors
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.DisclosureRow
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.PrimaryButton
import vn.abook.player.ui.components.QuietButton
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.screens.PickRow
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.studio.parts.ClipProblem
import vn.abook.player.ui.studio.parts.LineSample
import vn.abook.player.ui.studio.parts.SideBySide
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/** Thẻ nhóm nhiều người: chừa bấy nhiêu nút đầu trên thẻ, phần còn lại nằm trong "Người khác" (web `MAX_CHIPS` = 6; điện thoại hẹp hơn nên 4). */
private const val SHOWN_CHOICES = 4

/** Thẻ có ba vai không phải tên riêng: luôn nằm trên thẻ, không bị đẩy vào "Người khác". */
private val GENERIC_PEOPLE = setOf("Người kể", "Người kể đọc tất cả", "Vai phụ không tên")

/** Thẻ chỉ xem trước bấy nhiêu câu ví dụ trên thẻ (web `PICK_PREVIEW`); còn lại mở bằng "Chọn câu". */
private const val PREVIEW_LINES = 3

/**
 * Tab "Việc cần duyệt" (NATIVE_REMOTE_STUDIO.md §6.4): một bộ bài, mỗi lần MỘT thẻ. Quyết xong thẻ trượt đi, thẻ kế trượt vào, và quyết định được giữ
 * 15 giây cho "Hoàn tác" ([DecisionStrip] ở đầu nội dung các tab). Bấm "Bỏ qua" đưa thẻ xuống cuối bộ bài, không gửi gì.
 */
@Composable
internal fun WorkDeck(state: StudioProjectState, book: StudioBook, sheets: SheetHost, goReview: () -> Unit, modifier: Modifier = Modifier) {
    val work = state.work
    val poll by work.poll.collectAsState()
    val clip = work.clip.collectClip()
    val view = poll.data
    val deck = work.deck(view)
    val top = deck.firstOrNull()
    Column(modifier.fillMaxWidth().testTag("studio_work")) {
        when {
            view == null && poll.error == null -> BasicText(
                WorkText.WORK_LOADING, style = Abook.type.body.copy(color = Abook.colors.text2),
                modifier = Modifier.padding(top = Dim.s24).testTag("studio_work_loading"),
            )
            view == null -> Unit
            top == null -> EmptyDeck(state.live)
            else -> {
                val waiting = WorkLogic.waitingChanges(view.items.filter { it.requested != null })
                Column(Modifier.fillMaxWidth().padding(top = Dim.s16)) {
                    ClockLabel(WorkText.left(deck.size), Modifier.testTag("studio_work_count"), Abook.type.label)
                    RowHint(WorkLogic.inboxLead(book), Modifier.padding(top = Dim.s4).testTag("studio_work_lead"))
                    if (waiting > 0) Caption("${WorkText.waiting(waiting)} - ${WorkLogic.pendingNote(WorkLogic.applyWhen(book))}", Modifier.padding(top = Dim.s4).testTag("studio_work_waiting"))
                }
                AnimatedContent(
                    targetState = top,
                    contentKey = { it.key },
                    transitionSpec = {
                        slideInHorizontally(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 4 } togetherWith
                            slideOutHorizontally(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { -it / 4 }
                    },
                    label = "studio_card",
                ) { item ->
                    WorkCard(item, deck.size, state, sheets, clip, goReview)
                }
            }
        }
        InlineProblem(poll.error?.let { StudioText.failure(it) }.orEmpty(), work::refreshSoon, "studio_work_problem")
        ClipProblem(clip)
    }
}

@Composable
private fun EmptyDeck(live: Boolean) {
    Column(Modifier.fillMaxWidth().padding(top = Dim.s24).testTag("studio_work_empty")) {
        BasicText(WorkText.WORK_EMPTY_TITLE, style = Abook.type.sectionTitle)
        RowHint(WorkText.WORK_EMPTY, Modifier.padding(top = Dim.s8))
        if (live) RowHint(WorkText.WORK_EMPTY_LIVE, Modifier.padding(top = Dim.s4))
    }
}

/** Một thẻ: nhãn kiểu, tiêu đề, vì sao hỏi, vài câu ví dụ, rồi các nút trả lời theo mẫu của thẻ ([WorkLogic.template]). */
@Composable
private fun WorkCard(item: WorkItem, deckSize: Int, state: StudioProjectState, sheets: SheetHost, clip: ClipState, goReview: () -> Unit) {
    val work = state.work
    val template = WorkLogic.template(item)
    Column(Modifier.fillMaxWidth().padding(top = Dim.s16).testTag("studio_card_${item.kind.key}")) {
        Caption(item.kind.label, Modifier.testTag("studio_card_kind"))
        BasicText(item.title, style = Abook.type.sectionTitle, modifier = Modifier.padding(top = Dim.s4).testTag("studio_card_title"))
        if (item.problem.isNotEmpty()) RowHint(item.problem, Modifier.padding(top = Dim.s8).testTag("studio_card_problem"))
        if (item.affected > 0) Caption(WorkText.affected(item.affected), Modifier.padding(top = Dim.s8).testTag("studio_card_affected"))
        if (item.current.isNotEmpty() && (template == CardTemplate.Choose || template == CardTemplate.Voice)) {
            RowHint(WorkText.using(item.current), Modifier.padding(top = Dim.s4).testTag("studio_card_using"))
        }
        val samples = if (template == CardTemplate.Listen) emptyList() else item.examples.take(PREVIEW_LINES)
        Column(Modifier.fillMaxWidth().padding(top = if (samples.isEmpty()) 0.dp else Dim.s12), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
            for (example in samples) {
                LineSample(
                    example, clip, StudioWorkState.clipId(example), if (example.hasAudio) ({ work.playExample(example) }) else null,
                    "studio_example_${example.segmentId}",
                )
            }
        }
        Column(Modifier.fillMaxWidth().padding(top = Dim.s16), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
            when (template) {
                CardTemplate.Choose -> if (item.narratorSection != null) NarratorAnswers(item, state, sheets) else SpeakerAnswers(item, state, sheets)
                CardTemplate.Reading -> ReadingAnswers(item, state)
                CardTemplate.Voice -> VoiceAnswers(item, state, sheets)
                CardTemplate.Listen -> {
                    RowHint(WorkText.LISTEN_LINE)
                    AnswerButton(WorkText.LISTEN_OPEN, goReview, "studio_card_listen", primary = true)
                }
                CardTemplate.Refused -> AnswerButton(WorkText.REFUSED_DROP, { WorkDecisions.dropRefused(item)?.let(work::decide) }, "studio_card_drop")
                CardTemplate.Plain -> RowHint(WorkText.PLAIN_LINE, Modifier.testTag("studio_card_plain"))
            }
        }
        if (deckSize > 1) QuietButton(WorkText.SKIP, { work.skip(item.key) }, "studio_card_skip", Modifier.padding(top = Dim.s8))
    }
}

// ---- thẻ chọn người nói ----

private fun scopeOptions(item: WorkItem): List<Option<WorkScope>> = listOf(
    Option(WorkScope.Alternate, WorkText.scope(WorkScope.Alternate, item.scopeLabels, item.lines?.size ?: 0, item.allLines?.size ?: 0)),
    Option(WorkScope.All, WorkText.scope(WorkScope.All, item.scopeLabels, item.lines?.size ?: 0, item.allLines?.size ?: 0)),
)

@Composable
private fun SpeakerAnswers(item: WorkItem, state: StudioProjectState, sheets: SheetHost) {
    val work = state.work
    var scope by rememberSaveable(item.key) { mutableStateOf(WorkScope.Alternate) }
    val left = remember(item.key) { mutableStateOf(emptySet<String>()) }
    val lines = item.lines.orEmpty()
    val picked: List<LineRef>? = if (item.pick) WorkLogic.pickedLines(lines, left.value) else null
    val none = (picked ?: lines).isEmpty()
    val choices = item.choices.orEmpty()
    val shown = choices.filterIndexed { index, choice -> index < SHOWN_CHOICES || choice.label in GENERIC_PEOPLE }
    val more = choices.filter { it !in shown }
    fun pick(speaker: String, gender: String? = null) = work.decide(WorkDecisions.speaker(item, speaker, scope, picked, gender))

    if (item.allLines != null && item.lines != null) {
        val options = scopeOptions(item)
        RowHint(WorkText.SCOPE_LEAD)
        ChoiceRow(options, options.first { it.value == scope }, { chosen, _ -> scope = chosen.value }, Modifier.fillMaxWidth(), "studio_scope")
        Caption(WorkText.scopeNote(item.scopeLabels), Modifier.testTag("studio_scope_note"))
    }
    if (item.pick) {
        DisclosureRow(
            WorkText.PICK_LINES, { sheets.show { dismiss -> PickSheet(item, work, left, dismiss) } }, "studio_pick",
            summary = WorkLogic.pickNote(picked?.size ?: 0, lines.size),
        )
        RowLine()
    }
    shown.forEachIndexed { index, choice ->
        AnswerButton(
            choice.label, { pick(choice.value) }, "studio_choice_$index",
            primary = index == 0 && item.kind != WorkKind.Unnamed && item.suggested, enabled = !none,
        )
    }
    item.currentValue?.let { current -> AnswerButton(WorkText.keepName(item), { pick(current) }, "studio_keep", enabled = !none) }
    item.newPerson?.let { name -> AnswerButton(item.newPersonLabel ?: "Tạo nhân vật", { pick(name, "unknown") }, "studio_new_person", enabled = !none) }
    if (item.keepGroups.isNotEmpty()) AnswerButton(item.keepLabel ?: "Giữ nguyên", { WorkDecisions.keepAll(item)?.let(work::decide) }, "studio_keep_all")
    if (item.kind != WorkKind.Alias) {
        TextAction(WorkText.OTHER_PERSON, { sheets.show { dismiss -> OtherPersonSheet(more, none) { speaker, gender -> dismiss(); pick(speaker, gender) } } }, "studio_other", align = Alignment.CenterStart)
    }
}

/** "Người khác": những người không nằm trên thẻ, hay đặt tên một người mới kèm giới (bấm giới là lưu). */
@Composable
private fun OtherPersonSheet(more: List<WorkChoice>, none: Boolean, choose: (speaker: String, gender: String?) -> Unit) {
    var name by remember { mutableStateOf("") }
    val typed = name.trim()
    val list = rememberLazyListState()
    Column(Modifier.fillMaxWidth().testTag("studio_other_sheet")) {
        BasicText(WorkText.OTHER_SHEET_TITLE, style = Abook.type.sectionTitle)
        if (more.isNotEmpty()) {
            LazyColumn(Modifier.fillMaxWidth().padding(top = Dim.s8).heightIn(max = 224.dp).fadeEdges(list), state = list) {
                items(more, key = { it.value }) { choice ->
                    Column(Modifier.fillMaxWidth()) {
                        ListItem(choice.label, Modifier, { if (!none) choose(choice.value, null) }, "studio_other_${choice.value}")
                        RowLine()
                    }
                }
            }
            RowHint(WorkText.NEW_PERSON_HINT, Modifier.padding(top = Dim.s12))
        }
        Spacer(Modifier.height(Dim.s8))
        BookField(null, name, { name = it }, "studio_other_name", description = WorkText.NEW_PERSON_FIELD, placeholder = WorkText.NEW_PERSON_FIELD)
        RowHint(WorkText.NEW_GENDER_LEAD, Modifier.padding(top = Dim.s12, bottom = Dim.s8))
        SideBySide {
            for ((gender, label) in listOf("male" to WorkText.GENDER_MALE, "female" to WorkText.GENDER_FEMALE, "unknown" to WorkText.GENDER_UNKNOWN)) {
                AnswerButton(label, { choose(typed, gender) }, "studio_other_$gender", Modifier.weight(1f), enabled = typed.isNotEmpty() && !none)
            }
        }
    }
}

/** "Chọn câu": thẻ nhóm lớn cho bỏ chọn từng câu; câu đã bỏ chọn không bị đổi người nói. */
@Composable
private fun PickSheet(item: WorkItem, work: StudioWorkState, left: MutableState<Set<String>>, dismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    var extra by remember { mutableStateOf(emptyList<WorkExample>()) }
    var total by remember { mutableStateOf(item.examplesTotal) }
    var problem by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(false) }
    val shown = (item.examples + extra).distinctBy { it.stableId }
    val lines = item.lines.orEmpty()
    val list = rememberLazyListState()
    Column(Modifier.fillMaxWidth().testTag("studio_pick_sheet")) {
        BasicText(WorkText.PICK_LINES, style = Abook.type.sectionTitle)
        Caption(WorkLogic.pickNote(WorkLogic.pickedLines(lines, left.value).size, lines.size), Modifier.padding(top = Dim.s4).testTag("studio_pick_note"))
        LazyColumn(Modifier.fillMaxWidth().padding(top = Dim.s8).heightIn(max = 320.dp).fadeEdges(list), state = list) {
            items(shown, key = { it.stableId }) { example ->
                PickRow(example.text, example.chapterTitle, example.stableId !in left.value, { left.value = WorkLogic.toggleLine(left.value, example.stableId) }, "studio_pick_${example.segmentId}")
            }
            if (WorkLogic.hasMoreExamples(shown.size, total)) {
                item("more") {
                    TextAction(
                        if (loading) WorkText.LOADING else WorkLogic.moreText(shown.size, total ?: shown.size),
                        {
                            if (!loading) {
                                loading = true
                                problem = ""
                                scope.launch {
                                    try {
                                        val page = work.moreExamples(item, shown.size)
                                        extra = extra + page.examples
                                        total = page.total
                                    } catch (cancelled: kotlinx.coroutines.CancellationException) {
                                        throw cancelled
                                    } catch (error: Throwable) {
                                        problem = StudioText.failure(StudioErrors.of(error))
                                    }
                                    loading = false
                                }
                            }
                        },
                        "studio_pick_more",
                        Modifier.fillMaxWidth(),
                        Alignment.CenterStart,
                    )
                }
            }
        }
        InlineProblem(problem, null, "studio_pick_problem")
        Spacer(Modifier.height(Dim.s12))
        SideBySide {
            AnswerButton(WorkText.PICK_ALL, { left.value = emptySet() }, "studio_pick_all", Modifier.weight(1f))
            AnswerButton(WorkText.PICK_NONE, { left.value = lines.map { it.stableId }.toSet() }, "studio_pick_none", Modifier.weight(1f))
        }
        Spacer(Modifier.height(Dim.s8))
        PrimaryButton(WorkText.DONE, dismiss, Modifier.fillMaxWidth().testTag("studio_pick_done"))
    }
}

// ---- thẻ người kể của đoạn ----

@Composable
private fun NarratorAnswers(item: WorkItem, state: StudioProjectState, sheets: SheetHost) {
    val work = state.work
    val section = item.narratorSection ?: return
    val buttons = WorkLogic.narratorButtons(item.current, section.heading)
    if (section.appliesNote.isNotEmpty()) RowHint(section.appliesNote, Modifier.testTag("studio_narrator_note"))
    AnswerButton(buttons.accept, { WorkDecisions.narrator(item, "accept")?.let(work::decide) }, "studio_narrator_accept", primary = true)
    AnswerButton(buttons.keep, { WorkDecisions.narrator(item, "keep")?.let(work::decide) }, "studio_narrator_keep")
    TextAction(
        WorkText.NARRATOR_OTHER, { sheets.show { dismiss -> NarratorSheet(section) { narrator -> dismiss(); WorkDecisions.narrator(item, "choose", narrator)?.let(work::decide) } } },
        "studio_narrator_other", align = Alignment.CenterStart,
    )
}

@Composable
private fun NarratorSheet(section: NarratorSection, choose: (String) -> Unit) {
    var name by remember { mutableStateOf("") }
    val typed = name.trim()
    Column(Modifier.fillMaxWidth().testTag("studio_narrator_sheet")) {
        BasicText(WorkText.NARRATOR_OTHER, style = Abook.type.sectionTitle)
        for (choice in section.choices) {
            ListItem(choice.label, Modifier, { choose(choice.value) }, "studio_narrator_${choice.value}")
            RowLine()
        }
        Spacer(Modifier.height(Dim.s12))
        BookField(null, name, { name = it }, "studio_narrator_name", description = WorkText.NARRATOR_FIELD, placeholder = WorkText.NARRATOR_FIELD)
        Spacer(Modifier.height(Dim.s12))
        PrimaryButton(WorkText.NARRATOR_SET, { choose(typed) }, Modifier.fillMaxWidth().testTag("studio_narrator_set"), enabled = typed.isNotEmpty())
    }
}

// ---- thẻ cách đọc tên ----

/**
 * "Đúng rồi, giữ ..." hay gõ cách đọc khác. Cách gõ được máy kiểm (`pronunciation/check`) TRƯỚC khi giữ 15 giây: nghe được thì mới lưu được, nên lỗi hiện ngay
 * dưới ô gõ chứ không biến thành một lần gửi hỏng sau 15 giây. "Nghe thử" nhờ máy đọc một câu có tên ấy bằng cách đang gõ.
 */
@Composable
private fun ReadingAnswers(item: WorkItem, state: StudioProjectState) {
    val work = state.work
    val scope = rememberCoroutineScope()
    var value by remember(item.key) { mutableStateOf(item.current) }
    var problem by remember(item.key) { mutableStateOf("") }
    var suggestion by remember(item.key) { mutableStateOf("") }
    var heard by remember(item.key) { mutableStateOf("") }
    var busy by remember(item.key) { mutableStateOf(false) }
    val typed = value.trim()

    fun save(spoken: String) {
        if (busy || spoken.isEmpty()) return
        busy = true
        problem = ""
        suggestion = ""
        scope.launch {
            when (val checked = work.checkReading(item, spoken)) {
                ReadingCheck.Ok -> work.decide(WorkDecisions.pronunciation(item, spoken))
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
        if (busy || typed.isEmpty()) return
        busy = true
        problem = ""
        suggestion = ""
        heard = WorkText.READING_TRYING
        scope.launch {
            when (val outcome = work.previewReading(item, typed)) {
                is PreviewOutcome.Ready -> {
                    work.playPreview(outcome.preview)
                    heard = VoiceLogic.previewCaption(outcome.preview.text, "")
                }
                is PreviewOutcome.Rejected -> {
                    problem = outcome.message
                    suggestion = outcome.suggestion
                    heard = ""
                }
                is PreviewOutcome.Refused -> heard = outcome.text
            }
            busy = false
        }
    }

    AnswerButton(WorkText.readingKeep(item.current), { work.decide(WorkDecisions.pronunciation(item, item.current)) }, "studio_reading_keep", primary = true)
    RowHint(WorkText.READING_OR, Modifier.padding(top = Dim.s4))
    BookField(
        null, value, { value = it; problem = ""; suggestion = ""; heard = "" }, "studio_reading_field",
        description = WorkText.readingField(item.surface.orEmpty()), placeholder = "vd ${item.current}",
    )
    InlineProblem(problem, null, "studio_reading_problem")
    if (suggestion.isNotEmpty()) {
        TextAction(WorkText.readingUse(suggestion), { value = suggestion; save(suggestion) }, "studio_reading_suggestion", align = Alignment.CenterStart)
    }
    if (heard.isNotEmpty()) RowHint(heard, Modifier.testTag("studio_reading_heard"))
    AnswerButton(WorkText.READING_TRY, ::tryIt, "studio_reading_try", enabled = !busy && typed.isNotEmpty())
    AnswerButton(WorkText.READING_SAVE, { save(typed) }, "studio_reading_save", primary = true, enabled = !busy && typed.isNotEmpty() && typed != item.current)
}

// ---- thẻ giọng / giới ----

@Composable
private fun VoiceAnswers(item: WorkItem, state: StudioProjectState, sheets: SheetHost) {
    val work = state.work
    item.voiceChoices.orEmpty().forEachIndexed { index, choice ->
        AnswerButton(choice.label, { work.decide(WorkDecisions.voice(item, choice)) }, "studio_voice_$index", primary = choice.recommended, hint = choice.note)
    }
    if (item.keepCharacters.isNotEmpty()) AnswerButton(item.keepLabel ?: "Giữ nguyên", { WorkDecisions.voiceKeep(item)?.let(work::decide) }, "studio_voice_keep")
    item.pickVoice?.let { person ->
        TextAction(WorkText.VOICE_OTHER, { openVoiceSheet(state, sheets, person.name, person.displayName) }, "studio_voice_other", align = Alignment.CenterStart)
    }
}
