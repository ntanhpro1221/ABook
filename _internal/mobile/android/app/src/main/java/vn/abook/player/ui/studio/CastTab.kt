package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import vn.abook.player.ClipState
import vn.abook.player.StudioPolling
import vn.abook.player.ui.components.Caption
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.InlineProblem
import vn.abook.player.ui.components.ListItem
import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.RowLine
import vn.abook.player.ui.components.SectionTitle
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.studio.parts.ClipButton
import vn.abook.player.ui.studio.parts.ClipProblem
import vn.abook.player.ui.studio.parts.SideBySide
import vn.abook.player.ui.studio.parts.collectClip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Những gì tab "Nhân vật" đọc từ các luồng (lần hỏi gần nhất, tiếng đang phát). */
@Immutable
class CastData(val poll: StudioPolling.Poll<Cast>, val clip: ClipState)

@Composable
internal fun rememberCastData(cast: StudioCastState): CastData {
    val poll by cast.poll.collectAsState()
    return CastData(poll, cast.clip.collectClip())
}

/** Mở bảng giọng của một nhân vật (`character` = khoá sổ, "NARRATOR" cho người kể). Dùng cho tab Nhân vật và nút "Chọn giọng khác" của thẻ việc. */
internal fun openVoiceSheet(state: StudioProjectState, sheets: SheetHost, character: String, displayName: String) {
    sheets.show { dismiss ->
        val sheet = remember { state.cast.voiceSheet(character, displayName) }
        VoiceSheet(sheet, dismiss)
    }
}

/**
 * Tab "Nhân vật" (NATIVE_REMOTE_STUDIO.md §6.6): người kể, nhân vật chính, vai phụ; mỗi người một hàng với giọng đang đọc và nút nghe một câu của họ. Chạm hàng mở
 * bảng giọng. Dàn mang từ phần trước chỉ để xem (giọng đã khoá).
 */
internal fun LazyListScope.castTab(cast: StudioCastState, data: CastData, state: StudioProjectState, sheets: SheetHost, slide: Modifier) {
    val loaded = data.poll.data
    item("cast_notice", "cast_notice") {
        Column(Modifier.fillMaxWidth().then(slide)) {
            InlineProblem(data.poll.error?.let { StudioText.failure(it) }.orEmpty(), cast::refreshSoon, "studio_cast_problem")
            ClipProblem(data.clip)
        }
    }
    if (loaded == null) {
        if (data.poll.error == null) item("cast_loading", "status") {
            BasicText(WorkText.CAST_LOADING, style = Abook.type.body.copy(color = Abook.colors.text2), modifier = Modifier.then(slide).padding(top = Dim.s24).testTag("studio_cast_loading"))
        }
        return
    }
    if (loaded.characters.isEmpty() && loaded.extras.isEmpty() && loaded.carried.isEmpty()) {
        item("cast_empty", "status") {
            Column(Modifier.fillMaxWidth().then(slide).padding(top = Dim.s24).testTag("studio_cast_empty")) {
                BasicText(WorkText.CAST_EMPTY, style = Abook.type.sectionTitle)
                RowHint(WorkText.CAST_EMPTY_HINT, Modifier.padding(top = Dim.s8))
            }
        }
    }
    item("cast_narrator", "member") {
        val narrator = loaded.narrator
        Column(Modifier.fillMaxWidth().then(slide)) {
            SectionTitle(WorkText.CAST_NARRATOR, first = true)
            ListItem(
                narrator.profile?.label ?: narrator.voice.ifEmpty { WorkText.CAST_NO_VOICE },
                Modifier, { openVoiceSheet(state, sheets, "NARRATOR", WorkText.CAST_NARRATOR) }, "studio_cast_narrator",
                hint = narrator.pendingVoice?.let { WorkText.pendingVoice(it.label) } ?: WorkText.castLines(narrator.lines),
                hintColor = Abook.colors.text2, chevron = true,
            )
            RowLine()
        }
    }
    members(WorkText.CAST_MAIN, "main", loaded.characters, cast, data.clip, state, sheets, slide, true)
    members(WorkText.CAST_EXTRAS, "extra", loaded.extras, cast, data.clip, state, sheets, slide, true)
    members(WorkText.CAST_CARRIED, "carried", loaded.carried, cast, data.clip, state, sheets, slide, false)
}

private fun LazyListScope.members(
    title: String, group: String, people: List<CastMember>, cast: StudioCastState, clip: ClipState, state: StudioProjectState, sheets: SheetHost, slide: Modifier, editable: Boolean,
) {
    if (people.isEmpty()) return
    item("cast_${group}_title", "section") { SectionTitle(title, modifier = Modifier.then(slide)) }
    items(people, key = { "cast_${group}_${it.name}" }, contentType = { "member" }) { member ->
        Column(Modifier.fillMaxWidth().then(slide)) {
            ListItem(
                member.displayName,
                Modifier,
                if (editable) ({ openVoiceSheet(state, sheets, member.name, member.displayName) }) else null,
                "studio_cast_${member.name}",
                hint = memberHint(member),
                trailing = if (member.sampleId != null) ({ ClipButton(StudioCastState.sampleId(member), clip, { cast.playSample(member) }, "studio_cast_play_${member.name}") }) else null,
                chevron = editable && member.sampleId == null,
            )
            RowLine()
        }
    }
}

/** Dòng phụ của một hàng: giọng đang đọc, số câu, rồi điều đang chờ (giọng mới chọn, chờ gộp, tên gốc). */
private fun memberHint(member: CastMember): String = listOfNotNull(
    member.voice?.label ?: WorkText.CAST_NO_VOICE,
    WorkText.castLines(member.lines),
    member.pendingVoice?.let { WorkText.pendingVoice(it.label) },
    member.mergedInto?.let { WorkText.mergedInto(it) },
    member.originalName?.let { WorkText.renamed(it) },
).joinToString(" · ")

// ---- bảng giọng ----

/**
 * Bảng "Giọng của {tên}" (web `VoicePicker.tsx`): mọi giọng dùng được, lọc theo giới, nghe thử từng giọng (câu mẫu chung, hay một câu của chính nhân vật), chọn.
 * Chọn xong bảng đóng và dải "Hoàn tác" hiện ở đầu tab; giọng khác giới với nhân vật thì hỏi trước.
 */
@Composable
internal fun VoiceSheet(sheet: VoiceSheetState, dismiss: () -> Unit) {
    val scope = rememberCoroutineScope()
    LaunchedEffect(sheet) { sheet.load() }
    DisposableEffect(sheet) { onDispose { sheet.release() } }
    val clip = sheet.clip.collectClip()
    val choices = sheet.choices
    Column(Modifier.fillMaxWidth().testTag("studio_voice_sheet")) {
        BasicText(WorkText.voiceTitle(sheet.displayName), style = Abook.type.sectionTitle)
        when {
            choices == null && sheet.loading -> RowHint(WorkText.VOICE_LOADING, Modifier.padding(top = Dim.s12).testTag("studio_voice_loading"))
            choices == null -> InlineProblem(sheet.problem, { scope.launch { sheet.load() } }, "studio_voice_problem")
            else -> VoiceBody(sheet, choices, clip, dismiss)
        }
    }
}

private val genderOptions = GenderFilter.entries.map { Option(it, it.label) }

@Composable
private fun VoiceBody(sheet: VoiceSheetState, choices: VoiceChoices, clip: ClipState, dismiss: () -> Unit) {
    val pending = choices.pending
    Column(Modifier.fillMaxWidth().padding(top = Dim.s8)) {
        if (pending != null) {
            RowHint(WorkText.voicePending(pending.name), Modifier.testTag("studio_voice_pending"))
            TextAction(WorkText.VOICE_KEEP_CURRENT, { sheet.keepCurrent(); dismiss() }, "studio_voice_keep", Modifier.fillMaxWidth(), Alignment.CenterStart)
        }
        choices.rerecord?.let { RowHint(VoiceLogic.rerecordText(sheet.displayName, it), Modifier.testTag("studio_voice_rerecord")) }
        val crossing = sheet.crossing
        if (crossing != null) {
            Column(Modifier.fillMaxWidth().padding(top = Dim.s12).testTag("studio_voice_crossing"), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
                RowHint(WorkText.voiceCross(sheet.displayName, crossing.gender, crossing.name))
                SideBySide {
                    AnswerButton(WorkText.VOICE_CROSS_YES, { if (sheet.answerCrossing(true)) dismiss() }, "studio_voice_cross_yes", Modifier.weight(1f), primary = true)
                    AnswerButton(WorkText.VOICE_CROSS_NO, { sheet.answerCrossing(false) }, "studio_voice_cross_no", Modifier.weight(1f))
                }
            }
        }
        val filter = sheet.filter
        ChoiceRow(genderOptions, genderOptions.first { it.value == filter }, { picked, _ -> sheet.pickFilter(picked.value) }, Modifier.fillMaxWidth().padding(top = Dim.s8), "studio_voice_filter")
        if (sheet.said.isNotEmpty()) RowHint(sheet.said, Modifier.padding(top = Dim.s8).testTag("studio_voice_said"))
        val groups = VoiceLogic.groups(VoiceLogic.byGender(choices.voices, filter))
        val labels = VoiceLogic.groupLabels(groups)
        if (groups.isEmpty()) RowHint(WorkText.VOICE_NO_VOICES, Modifier.padding(top = Dim.s12).testTag("studio_voice_none"))
        val list = rememberLazyListState()
        LazyColumn(Modifier.fillMaxWidth().padding(top = Dim.s8).heightIn(max = 340.dp).fadeEdges(list).testTag("studio_voice_list"), state = list) {
            groups.forEachIndexed { index, group ->
                if (group.engine == "vieneu" || groups.size == 1) {
                    item("group_${group.engine}", "group") { Caption(labels[index], Modifier.padding(top = Dim.s8)) }
                    items(group.voices, key = { it.key }, contentType = { "voice" }) { voice -> VoiceRow(sheet, voice, clip, filter, dismiss) }
                } else {
                    item("group_${group.engine}", "fold") {
                        Fold(labels[index], "studio_voice_group_${group.engine}", summary = group.label, defaultOpen = group.voices.any { it.current || it.pending }) {
                            for (voice in group.voices) VoiceRow(sheet, voice, clip, filter, dismiss)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun VoiceRow(sheet: VoiceSheetState, voice: VoiceEntry, clip: ClipState, filter: GenderFilter, dismiss: () -> Unit) {
    val pending = sheet.choices?.pending
    val taken = sheet.narrator && voice.takenBy.isNotEmpty()
    val chosen = voice.pending
    val heardId = sheet.heardClip(voice)
    val tryLabel = when {
        sheet.asking == voice.key -> WorkText.VOICE_TRYING
        heardId != null && clip.playing == heardId -> WorkText.STOP
        else -> WorkText.VOICE_TRY
    }
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s12).testTag("studio_voice_${voice.key}")) {
        Row(verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f)) {
                BasicText(voice.name, style = Abook.type.bodyStrong)
                val meta = VoiceLogic.meta(voice, filter == GenderFilter.All)
                if (meta.isNotEmpty()) RowHint(meta, Modifier.padding(top = 2.dp))
                if (!voice.installed) Caption(WorkText.VOICE_NOT_INSTALLED, Modifier.padding(top = Dim.s4))
            }
            if (voice.preview) ClipButton(sheet.sampleClip(voice), clip, { sheet.playSample(voice) }, "studio_voice_play_${voice.key}")
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextAction(tryLabel, { sheet.tryVoice(voice) }, "studio_voice_try_${voice.key}", Modifier.weight(1f), Alignment.CenterStart)
            val label = when {
                chosen -> WorkText.VOICE_CHOSEN
                voice.current && pending == null -> WorkText.VOICE_IN_USE
                else -> WorkText.VOICE_CHOOSE
            }
            val enabled = !taken && voice.installed && !chosen && !(voice.current && pending == null)
            TextAction(label, { if (enabled && sheet.choose(voice)) dismiss() }, "studio_voice_choose_${voice.key}", Modifier, Alignment.CenterEnd)
        }
        RowLine(Modifier.padding(top = Dim.s4))
    }
}
