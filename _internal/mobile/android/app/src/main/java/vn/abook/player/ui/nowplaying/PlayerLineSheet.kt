package vn.abook.player.ui.nowplaying

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.S
import vn.abook.player.ui.components.*
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.studio.parts.DecisionStrip
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

@Composable
internal fun PlayerLineLayer(editor: PlayerLineEditor?) {
    if (editor == null) return
    val host = remember { SheetHost() }
    SideEffect {
        host.keepOpen = { if (editor.step != "menu") { editor.step = "menu"; true } else false }
    }
    val selection = editor.selected
    var shown by remember { mutableStateOf<PlayerLineEditor.Selection?>(null) }
    LaunchedEffect(selection) {
        if (selection == null) host.dismiss()
        else {
            shown = selection
            host.show { dismiss -> PlayerLineSheet(editor) { editor.close(); dismiss() } }
        }
    }
    LaunchedEffect(host.current) {
        if (host.current == null && shown != null) { shown = null; editor.close() }
    }
    SheetLayer(host)
}

@Composable
internal fun PlayerLineSheet(editor: PlayerLineEditor, dismiss: () -> Unit) {
    val selection = editor.selected ?: return
    val snapshot = editor.snapshot
    val line = editor.line
    val bodyLimit = LocalConfiguration.current.screenHeightDp.dp * 0.75f
    val scroll = rememberScrollState()
    Column(Modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll).testTag("player_line_editor"), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BasicText(when (editor.step) {
            "speaker" -> if (line?.kind == "thought") S.s_ai_nghi_cau_nay_1d5dd20c else S.s_ai_noi_cau_nay_39d97e95
            "delivery" -> S.s_cach_doc_cau_nay_d8d0b9f1
            else -> S.s_sua_cau_nay_a82aec43
        }, style = Abook.type.sectionTitle)
        BasicText(selection.paragraph.text, style = Abook.type.bodySmall)
        RowHint(S.s_player_line_waiting_audio)
        Reveal(selection.paragraph.line?.editable != true) { RowHint(S.s_file_sach_nay_lam_bang_abook_ban_cu_nen_ch_45df1722) }
        Reveal(editor.loading) { RowHint(S.s_dang_tai_kich_ban_0eea9c53) }
        Reveal(editor.problem.isNotEmpty() || snapshot?.blocked.orEmpty().isNotEmpty()) {
            RowHint(editor.problem.ifEmpty { snapshot?.blocked.orEmpty() }, color = Abook.colors.danger)
        }
        editor.decisions?.let { DecisionStrip(it) }
        SheetPages(editor.step, { when (it) { "speaker" -> 1; "delivery" -> 2; else -> 0 } }, "player_line_pages") { step ->
            Column(Modifier.fillMaxWidth()) {
                if (line != null && snapshot != null) when (step) {
                    "speaker" -> ScriptPeoplePicker(snapshot.script, ScriptLogic.speaker(line), showTitle = false) { editor.assign(it) }
                    "delivery" -> ScriptDeliveryEditor(snapshot.script, line, { editor.step = "menu" }, reading = true, showTitle = false, modifier = Modifier.heightIn(max = bodyLimit), save = editor::delivery)
                    else -> {
                        LineAction(if (line.kind == "thought") S.s_ai_nghi_cau_nay_0656af4f else S.s_ai_noi_cau_nay_0e00a5c7,
                            LucidePaths.USER_ROUND, editor.enabled && ScriptLogic.isSpeech(line), "player_line_who",
                            note = if (!ScriptLogic.isSpeech(line)) S.s_loi_ke_khong_co_nguoi_noi_muon_gan_nguoi_d_a62c8bf9 else line.wish?.let { S.s_dang_cho_may_lam_sach_0_712ab9de(it.label) } ?: S.s_hien_la_0_d6cdb2e8(line.label)) { editor.step = "speaker" }
                        LineAction(S.s_cach_doc_cau_50f2072a, LucidePaths.MESSAGE_SQUARE_QUOTE, editor.enabled, "player_line_delivery", note = S.s_loai_cau_cam_xuc_chu_dem_doc_483deab7) { editor.step = "delivery" }
                        LineAction(S.s_nghe_thu_fa024065, LucidePaths.PLAY, line.hasAudio, "player_line_sample", action = editor::sample)
                        LineAction(S.s_thu_lai_cau_nay_034c2834, LucidePaths.ROTATE_CCW, editor.enabled && line.hasAudio && !snapshot.retake, "player_line_retake",
                            note = when { !line.hasAudio -> S.s_chuong_nay_chua_co_audio_chua_co_gi_de_thu_47e4d310; snapshot.retake -> S.s_da_ghi_dang_cho_may_lam_sach_7335a8a2; else -> S.s_doc_lai_mot_lan_khac_giong_nhu_cu_a0908dad }, chevron = false, action = editor::retake)
                    }
                }
                TextAction(if (step == "menu") S.s_dong_5d54c2a1 else S.s_quay_lai_6d793582,
                    { if (step == "menu") dismiss() else editor.step = "menu" }, "player_line_back")
            }
        }
    }
}

@Composable
private fun LineAction(label: String, icon: String, enabled: Boolean, tag: String, note: String? = null, chevron: Boolean = true, action: () -> Unit) {
    ListItem(label, onClick = { if (enabled) action() }, tag = tag, hint = note, chevron = chevron,
        modifier = Modifier.clip(RoundedCornerShape(Dim.radiusCover)).padding(horizontal = 12.dp).then(if (enabled) Modifier else Modifier.alpha(0.6f).semantics { disabled() }),
        titleStyle = Abook.type.bodySmall.copy(fontWeight = FontWeight.Medium), leadingWidth = 20.dp, leadingGap = 16.dp,
        leading = { LucideIcon(icon, Abook.colors.text2) })
}
