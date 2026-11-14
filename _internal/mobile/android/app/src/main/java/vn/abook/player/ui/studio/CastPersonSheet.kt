package vn.abook.player.ui.studio

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch
import vn.abook.player.NameRules
import vn.abook.player.S
import vn.abook.player.StudioErrors
import vn.abook.player.ui.addbook.BookField
import vn.abook.player.ui.addbook.FieldGroup
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.GitMergeIcon
import vn.abook.player.ui.components.MenuRow
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.SheetPages
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.components.TextCursorInputIcon
import vn.abook.player.ui.components.UserRoundIcon
import vn.abook.player.ui.screens.PickRow
import vn.abook.player.ui.studio.parts.AnswerButton
import vn.abook.player.ui.theme.Abook

private enum class CastPersonPage { Menu, Rename, Gender, Merge }

@Composable
internal fun CastPersonSheet(project: StudioProjectState, person: CastMember, people: List<CastMember>, dismiss: () -> Unit, voice: () -> Unit) {
    var page by remember { mutableStateOf(CastPersonPage.Menu) }
    var name by remember { mutableStateOf(person.displayName) }
    var query by remember { mutableStateOf("") }
    var target by remember { mutableStateOf<CastMember?>(null) }
    var gender by remember { mutableStateOf("") }
    var problem by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    fun commit(decision: WorkDecision) {
        if (!project.session.listenOnly) { project.decisions.hold(decision); dismiss() }
    }
    BackHandler(page != CastPersonPage.Menu) { page = CastPersonPage.Menu }
    SheetPages(page, { it.ordinal }, "studio_cast_person") { shown ->
        FieldGroup(Modifier.fillMaxWidth().heightIn(max = 520.dp).verticalScroll(rememberScrollState()).testTag("studio_cast_person_${shown.name.lowercase()}")) {
            when (shown) {
                CastPersonPage.Menu -> {
                    BasicText(person.displayName, style = Abook.type.sectionTitle)
                    TextAction(S.s_doi_giong_94b6b371, voice, "studio_person_voice")
                    MenuRow(S.s_gop_vao_nguoi_khac_8f5c461d, "studio_person_merge", unavailable = person.lines <= 0, onClick = { page = CastPersonPage.Merge }) { GitMergeIcon(it) }
                    MenuRow(S.s_doi_ten_a2a0dc70, "studio_person_rename", onClick = { page = CastPersonPage.Rename }) { TextCursorInputIcon(it) }
                    MenuRow(S.s_doi_gioi_tinh_8fde2c62, "studio_person_gender", unavailable = person.voice == null || person.lines <= 0, onClick = { page = CastPersonPage.Gender }) { UserRoundIcon(it) }
                    Reveal(person.mergedInto != null) {
                        TextAction(S.s_bo_gop_d7199137, {
                            if (!busy && !project.session.listenOnly) {
                                busy = true
                                project.session.scope.launch {
                                    try {
                                        val details = project.session.source.pendingChanges(project.session.computer, project.bookId)
                                        val decision = StudioPeopleEdits.unmerge(person, details)
                                        if (decision == null) problem = S.s_lan_gop_nay_da_duoc_ap_hoac_da_bi_thay_ban_a6f706a3 else commit(decision)
                                    } catch (cancelled: CancellationException) { throw cancelled }
                                    catch (error: Throwable) {
                                        val failure = StudioErrors.of(error)
                                        project.session.note(failure)
                                        problem = StudioText.failure(failure)
                                    } finally { busy = false }
                                }
                            }
                        }, "studio_person_unmerge")
                    }
                }
                CastPersonPage.Rename -> {
                    BasicText(S.s_doi_ten_0_d6845bbc(person.displayName), style = Abook.type.sectionTitle)
                    RowHint(S.s_chi_doi_ten_hien_thi_giu_giong_va_audio_1f7110c8)
                    BookField(null, name, { name = it }, "studio_person_name", description = S.s_ten_moi_cua_0_ac5dd137(person.displayName))
                    val decision = runCatching { StudioPeopleEdits.rename(person, name, people) }
                    Reveal(name.isNotBlank() && decision.isFailure) { RowHint(decision.exceptionOrNull()?.message.orEmpty(), color = Abook.colors.danger) }
                    AnswerButton(S.s_luu_e91f26c0, { decision.getOrNull()?.let(::commit) }, "studio_person_rename_save", primary = true, enabled = name.isNotBlank() && decision.isSuccess)
                    Reveal(person.originalName != null) { TextAction(S.s_ve_ten_goc_643cd2e0, { commit(StudioPeopleEdits.rename(person, "", people)) }, "studio_person_original") }
                }
                CastPersonPage.Gender -> {
                    BasicText(S.s_gioi_tinh_cua_0_ce17d919(person.displayName), style = Abook.type.sectionTitle)
                    RowHint(WorkText.REDO_MORE)
                    for ((value, label) in listOf("male" to S.s_nam_22dd59c8, "female" to S.s_nu_e15bc11c))
                        PickRow(label, null, gender == value, { gender = value }, "studio_person_gender_$value")
                    AnswerButton(S.s_ghi_lai_923c1fd4, { commit(StudioPeopleEdits.gender(person, gender)) }, "studio_person_gender_save", primary = true, enabled = gender.isNotEmpty())
                }
                CastPersonPage.Merge -> {
                    BasicText(S.s_gop_nhan_vat_37b51bd5, style = Abook.type.sectionTitle)
                    RowHint(S.s_moi_cau_cua_0_va_cac_phan_sau_dung_nguoi_b_75a7c03f(person.displayName))
                    BookField(null, query, { query = it }, "studio_person_merge_search", description = S.s_tim_nguoi_trong_truyen_a1507054, placeholder = S.s_tim_nguoi_trong_truyen_a1507054)
                    for (other in people.filter { it.name != person.name && it.voice != null && ScriptEdits.matches(it.displayName, query) })
                        PickRow(other.displayName, other.pendingVoice?.label ?: other.voice?.label, target?.name == other.name, { target = other }, "studio_person_merge_${other.name}")
                    AnswerButton(S.s_gop_2380bed6, { target?.let { commit(StudioPeopleEdits.merge(person, it)) } }, "studio_person_merge_save", primary = true, enabled = target != null)
                }
            }
            Reveal(problem.isNotEmpty()) { RowHint(problem, color = Abook.colors.danger) }
        }
    }
}
