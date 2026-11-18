package vn.abook.player.ui.studio

import vn.abook.player.ui.addbook.FieldGroup
import androidx.compose.foundation.layout.imePadding
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.toggleableState
import androidx.compose.ui.state.ToggleableState
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import kotlinx.coroutines.CancellationException
import org.json.JSONArray
import org.json.JSONObject
import vn.abook.player.S
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.CheckIcon
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.motion.ContentLayout
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.motion.rememberReducedMotion
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

enum class ScriptScopeMode(val label: String) {
    Line(S.s_cau_nay_ee66e104), Scene(S.s_scope_scene), Chapter(S.s_scope_chapter), Manual(S.s_scope_manual),
}

object ScriptScopeLogic {
    fun candidates(lines: List<ScriptLine>, anchor: String, mode: ScriptScopeMode, start: Int, end: Int): List<ScriptLine> {
        val base = lines.firstOrNull { it.stableId == anchor } ?: return emptyList()
        if (mode == ScriptScopeMode.Scene && base.scene == null) return emptyList()
        if (mode == ScriptScopeMode.Manual && (start < 0 || end < start)) return emptyList()
        return lines.filter { it.editable && ScriptLogic.isSpeech(it) && (it.scopeSpeaker ?: it.current) == (base.scopeSpeaker ?: base.current) &&
            (mode != ScriptScopeMode.Line || it.stableId == anchor) &&
            (mode != ScriptScopeMode.Scene || it.scene == base.scene) &&
            (mode != ScriptScopeMode.Manual || it.seq in start..end) }
    }

    fun conflict(line: ScriptLine) = line.wish != null || line.lineWish != null
    fun selected(lines: List<ScriptLine>, toggled: Set<String>) = lines.filter { conflict(it) == (it.stableId in toggled) }

    fun decision(lines: List<ScriptLine>, person: ScriptPerson, script: ChapterScript? = null): WorkDecision {
        val body = JSONObject().put("speaker", person.value).put("newGender", person.newGender)
            .put("lines", JSONArray().apply { lines.forEach { put(JSONObject().put("stableId", it.stableId).put("textSha256", it.textSha256)) } })
            .put("seen", JSONObject().apply { lines.forEach { put(it.stableId, it.wish?.value ?: "") } })
        return WorkDecision("scope:${lines.first().stableId}", S.s_scope_count(lines.size, 0), listOf(WorkStep("speaker", body)),
            scopeChapter = script?.chapterId, scopeRevision = script?.scopeRevision.orEmpty())
    }
}

/** Uses the same sheet, controls, copy and request as a single-line correction. */
@Composable
fun ScriptScopeSheet(state: StudioScriptState, script: ChapterScript, line: ScriptLine, dismiss: () -> Unit) {
    var mode by remember { mutableStateOf(if (line.scene == null) ScriptScopeMode.Line else ScriptScopeMode.Scene) }
    val range = remember { if (line.scene == null) listOf(line) else script.lines.filter { it.scene == line.scene } }
    var start by remember { mutableStateOf((range.first().seq + 1).toString()) }
    var end by remember { mutableStateOf((range.last().seq + 1).toString()) }
    var toggled by remember { mutableStateOf(emptySet<String>()) }
    var query by remember { mutableStateOf("") }
    var person by remember { mutableStateOf<ScriptPerson?>(null) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()
    val reduced = rememberReducedMotion()
    val candidates = ScriptScopeLogic.candidates(script.lines, line.stableId, mode, (start.toIntOrNull() ?: 0) - 1, (end.toIntOrNull() ?: 0) - 1)
    val chosen = ScriptScopeLogic.selected(candidates, toggled)
    Column(Modifier.fillMaxWidth().imePadding().heightIn(max = 640.dp).testTag("script_scope"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BasicText(S.s_scope_title, style = Abook.type.sectionTitle)
        val list = rememberLazyListState()
        LazyColumn(Modifier.weight(1f, fill = false).fadeEdges(list), state = list, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item("controls") {
        FieldGroup(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        RowHint(if (line.scene == null) S.s_scope_no_markers else S.s_scope_marker_note)
        FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        for (option in ScriptScopeMode.entries) {
            ScopeChoice(option.label, mode == option, !busy && (option != ScriptScopeMode.Scene || line.scene != null), "scope_mode_${option.name.lowercase()}") { mode = option; toggled = emptySet() }
        }
        }
        Reveal(mode == ScriptScopeMode.Manual) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Column(Modifier.weight(1f)) {
                BookField(S.s_scope_start, start, { start = it }, "scope_start", keyboard = KeyboardType.Number)
                }
                Column(Modifier.weight(1f)) {
                BookField(S.s_scope_end, end, { end = it }, "scope_end", keyboard = KeyboardType.Number)
                }
            }
        }
        SwapContent(person, contentKey = { picked -> picked != null }, layout = ContentLayout.Column) { picked ->
            if (picked != null) TextAction(S.s_scope_target(picked.label), { person = null }, "scope_target", align = Alignment.CenterStart)
            else Column(Modifier.fillMaxWidth()) {
                BookField(null, query, { query = it }, "scope_search", description = S.s_tim_nguoi_noi_70e3871e, placeholder = S.s_tim_nguoi_noi_70e3871e)
                val found = ScriptLogic.people(script).filter { it.value != ScriptLogic.NARRATOR && fold(it.label).contains(fold(query.trim())) }.take(8)
                for (item in found) ScopeRow(item.label, null, item.value == line.current, false, "scope_person_${item.value}", avatarPerson = item) { person = item }
                Reveal(query.isNotBlank() && found.isEmpty()) {
                    FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        for ((gender, label) in listOf("male" to S.s_nam_22dd59c8, "female" to S.s_nu_e15bc11c, "unknown" to S.s_khong_ro_8af7da78)) {
                            TextAction(label, { person = ScriptPerson(query.trim(), query.trim(), 0, gender) }, "scope_new_$gender")
                        }
                    }
                }
            }
        }
        SwapContent(chosen.size, candidates.count(ScriptScopeLogic::conflict), contentKey = { count, conflicts -> "$count:$conflicts" }, layout = ContentLayout.Column) { count, conflicts ->
            RowHint(S.s_scope_count(count, conflicts), Modifier.testTag("scope_count"))
        }
        RowHint(S.s_scope_before_after(line.label, person?.label ?: S.s_scope_pick))
        }
        }
            items(candidates, key = { it.stableId }) { item ->
                Box(Modifier.animateItem(fadeInSpec = tween(if (reduced) MotionMs.REDUCED_FADE_MS else MotionMs.MEDIUM, easing = Motion.Decelerate),
                    placementSpec = tween(if (reduced) 0 else MotionMs.MEDIUM, easing = Motion.Standard),
                    fadeOutSpec = tween(if (reduced) MotionMs.REDUCED_FADE_MS else MotionMs.MEDIUM_OUT, easing = Motion.Accelerate))) {
                ScopeRow("${item.seq + 1}. ${item.text}", (if (ScriptScopeLogic.conflict(item)) S.s_scope_conflict + "\n" else "") + S.s_scope_before_after(ScriptLogic.speakerLabel(item), person?.label ?: S.s_scope_pick), item in chosen,
                    true, "scope_line_${item.stableId}") { toggled = if (item.stableId in toggled) toggled - item.stableId else toggled + item.stableId }
                }
            }
        }
        Reveal(error.isNotEmpty()) { RowHint(error, Modifier.testTag("scope_error")) }
        AnswerButton(S.s_scope_apply, {
            val target = person ?: return@AnswerButton
            busy = true
            scope.launch {
                try {
                    val fresh = state.session.source.castingChapter(state.session.computer, state.bookId, script.chapterId)
                    if (script.scopeRevision.isEmpty() || fresh.scopeRevision != script.scopeRevision) {
                        state.reload()
                        error = S.s_scope_changed
                    }
                    else { state.decisions.hold(ScriptScopeLogic.decision(chosen, target, script)); dismiss() }
                } catch (cancelled: CancellationException) { throw cancelled }
                catch (_: Exception) { error = S.s_scope_changed }
                finally { busy = false }
            }
        }, "scope_apply", primary = true, enabled = !busy && person != null && chosen.isNotEmpty())
    }
}

private fun fold(text: String) = java.text.Normalizer.normalize(text, java.text.Normalizer.Form.NFD)
    .replace(Regex("[\\u0300-\\u036f]"), "").replace('đ', 'd').replace('Đ', 'D').lowercase()

@Composable
internal fun ScopeChoice(label: String, active: Boolean, enabled: Boolean, tag: String, onClick: () -> Unit) {
    Box(Modifier.heightIn(min = 40.dp)
        .border(if (active) 1.dp else 0.dp, if (active) Abook.colors.controlLine else androidx.compose.ui.graphics.Color.Transparent, RoundedCornerShape(Dim.radiusControl))
        .then(if (enabled) Modifier.pressable(Role.RadioButton, onClick = onClick) else Modifier.semantics { disabled() })
        .semantics { selected = active }.padding(horizontal = 12.dp, vertical = 8.dp).testTag(tag), contentAlignment = Alignment.Center) {
        BasicText(label, style = Abook.type.label.copy(color = if (!enabled) Abook.colors.text3 else if (active) Abook.colors.text else Abook.colors.accentText))
    }
}

/** Selection changes the check mark only, matching the web and Qt previews. */
@Composable
private fun ScopeRow(label: String, hint: String?, picked: Boolean, multiple: Boolean, tag: String, avatarPerson: ScriptPerson? = null, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().heightIn(min = Dim.s48)
        .pressable(if (multiple) Role.Checkbox else Role.Button, onClick = onClick)
        .semantics { if (multiple) toggleableState = if (picked) ToggleableState.On else ToggleableState.Off }
        .padding(8.dp).testTag(tag), verticalAlignment = Alignment.Top) {
        Box(Modifier.size(20.dp)) { vn.abook.player.ui.components.SelectionMark(picked) }
        Spacer(Modifier.width(8.dp))
        SwapContent(avatarPerson, contentKey = { avatarPerson -> avatarPerson != null }, layout = ContentLayout.Row) { avatarPerson ->
          if (avatarPerson != null) {
            vn.abook.player.ui.components.PersonAvatar(avatarPerson.value, avatarPerson.avatar, size = 24.dp)
            Spacer(Modifier.width(8.dp))
          }
        }
        Column(Modifier.weight(1f)) {
            BasicText(label, style = Abook.type.bodySmall)
            Reveal(hint != null) { RowHint(hint.orEmpty()) }
        }
    }
}
