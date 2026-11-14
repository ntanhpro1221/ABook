package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import vn.abook.player.NameRules
import vn.abook.player.S
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.FieldGroup
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.ChoiceRow
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.Option
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.screens.PickRow
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.studio.parts.SideBySide
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

/** Existing people remain a single tap. A typed new name is validated against canonical and displayed names. */
@Composable
internal fun ScriptPeoplePicker(script: ChapterScript, current: String, allowNarrator: Boolean = true, allowCreate: Boolean = true, onPick: (ScriptPerson) -> Unit) {
    var query by remember { mutableStateOf("") }
    var creating by remember { mutableStateOf(false) }
    var name by remember { mutableStateOf("") }
    val people = ScriptLogic.people(script).filter { allowNarrator || it.value != ScriptLogic.NARRATOR }
    FieldGroup(Modifier.fillMaxWidth().heightIn(max = 520.dp).verticalScroll(rememberScrollState()).testTag("studio_script_people")) {
        BasicText(ScriptText.WHO, style = Abook.type.sectionTitle)
        BookField(null, query, { query = it }, "studio_people_search", description = S.s_tim_nguoi_noi_70e3871e, placeholder = S.s_tim_nguoi_noi_70e3871e)
        val list = rememberLazyListState()
        LazyColumn(Modifier.heightIn(max = 224.dp).fadeEdges(list), state = list) {
            items(people.filter { ScriptEdits.matches(it.label, query) }, key = { it.value }) { person ->
                PickRow(person.label, if (person.lines > 0) S.s_0_cau_2a1e6590(person.lines) else null, person.value == current, { onPick(person) }, "studio_person_${person.value}")
            }
        }
        Reveal(allowCreate) { TextAction(S.s_tao_nhan_vat_18e9a09a, { creating = !creating }, "studio_script_new") }
        Reveal(allowCreate && creating) {
            Column {
                BookField(null, name, { name = it }, "studio_script_new_name", description = WorkText.NEW_PERSON_FIELD, placeholder = WorkText.NEW_PERSON_FIELD)
                val valid = runCatching { NameRules.person(name, people.flatMap { listOf(it.label, it.value) }) }
                Reveal(name.isNotBlank() && valid.isFailure) { RowHint(valid.exceptionOrNull()?.message.orEmpty(), color = Abook.colors.danger) }
                SideBySide {
                    for ((gender, label) in listOf("male" to WorkText.GENDER_MALE, "female" to WorkText.GENDER_FEMALE, "unknown" to WorkText.GENDER_UNKNOWN)) {
                        AnswerButton(label, { valid.getOrNull()?.let { onPick(ScriptPerson(it, it, 0, gender)) } }, "studio_script_new_$gender", Modifier.weight(1f), enabled = valid.isSuccess)
                    }
                }
            }
        }
    }
}

@Composable
internal fun ScriptDeliverySheet(state: StudioScriptState, script: ChapterScript, line: ScriptLine, dismiss: () -> Unit) {
    val pending = line.lineWish?.takeIf { it.state == "pending" }
    var kind by remember { mutableStateOf(pending?.kind?.ifEmpty { line.kind } ?: line.kind) }
    var emotion by remember { mutableStateOf(pending?.emotion?.ifEmpty { line.emotion ?: "neutral" } ?: line.emotion ?: "neutral") }
    var intensity by remember { mutableStateOf(pending?.intensity ?: line.intensity ?: 0) }
    var person by remember { mutableStateOf<ScriptPerson?>(null) }
    val needsPerson = line.kind == "narration" && kind != "narration"
    Column(Modifier.fillMaxWidth().verticalScroll(rememberScrollState()).testTag("studio_delivery_sheet")) {
        BasicText(S.s_cach_doc_cau_nay_d8d0b9f1, style = Abook.type.sectionTitle)
        BasicText(S.s_loai_doan_4c243930, style = Abook.type.bodySmall)
        val kinds = ScriptEdits.kinds.map { Option(it.first, it.second) }
        ChoiceRow(kinds, kinds.first { it.value == kind }, { picked, _ -> kind = picked.value }, tag = "studio_delivery_kind")
        Reveal(needsPerson) {
            SwapContent(person, contentKey = { person -> person == null }, layout = ContentLayout.Column) { shown ->
                if (shown == null) ScriptPeoplePicker(script, "", allowNarrator = false) { person = it }
                else TextAction(shown.label, { person = null }, "studio_delivery_person")
            }
        }
        Fold(S.s_cam_xuc_05c1aee0, "studio_delivery_emotion", summary = ScriptEdits.deliveryText(emotion, intensity)) {
            Column {
                Reveal(line.emotion != null) {
                    Column {
                        for ((value, label) in ScriptEdits.emotions) {
                            PickRow(label, null, value == emotion, { emotion = value }, "studio_emotion_$value")
                        }
                    }
                }
                Reveal(line.intensity != null) {
                    Column {
                        BasicText(S.s_muc_10267bc5, style = Abook.type.bodySmall)
                        val levels = ScriptEdits.levels.mapIndexed { value, label -> Option(value, label) }
                        ChoiceRow(levels, levels.first { it.value == intensity }, { picked, _ -> intensity = picked.value }, tag = "studio_delivery_intensity")
                        RowHint(S.s_may_giu_muc_trong_tam_giong_doc_duoc_thi_t_0b46ded3)
                    }
                }
            }
        }
        RowHint(ScriptText.PENDING, Modifier.padding(top = Dim.s8))
        AnswerButton(if (needsPerson && person == null) S.s_chon_nguoi_noi_truoc_f3e512e0 else S.s_luu_cho_cau_nay_6402d7a6, { if (state.delivery(line, kind, emotion, intensity, person)) dismiss() }, "studio_delivery_save", primary = true,
            enabled = ScriptEdits.delivery(line, kind, emotion, intensity, person) != null)
    }
}
