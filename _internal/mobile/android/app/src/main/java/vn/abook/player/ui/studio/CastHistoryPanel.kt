package vn.abook.player.ui.studio

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.S
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.Fold
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.RowHint
import vn.abook.player.ui.components.TextAction
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

@Composable
internal fun CastHistoryPanel(items: List<CastHistoryItem>, busy: String?, problem: String, editable: Boolean,
                              undo: (String) -> Unit, modifier: Modifier = Modifier) {
    Fold(S.s_lich_su_0a235708, "cast_history", modifier) {
        Reveal(problem.isNotEmpty()) { RowHint(problem) }
        Reveal(items.isEmpty()) { RowHint(S.s_cast_history_manual) }
        items.forEach { item ->
            Row(Modifier.fillMaxWidth().padding(vertical = Dim.s12), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    BasicText(S.s_cast_history_row(item.source.ifEmpty { S.s_cast_history_group }, item.target, item.lines), style = Abook.type.body)
                    SwapContent(item.state, contentKey = { it }) { state ->
                        when (state) {
                            "pending" -> RowHint(S.s_cho_ap_dung_77a52853)
                            "undone" -> RowHint(S.s_da_hoan_tac_2ef55fca)
                            else -> RowHint("")
                        }
                    }
                    Reveal(item.conflicts > 0) { RowHint(S.s_cast_history_conflicts(item.conflicts)) }
                    Reveal(item.state == "pending") { RowHint(S.s_cast_history_audio) }
                    Reveal(item.aliasConflicts > 0) { RowHint(S.s_cast_history_alias_conflicts(item.aliasConflicts)) }
                }
                Reveal(editable && item.state == "applied") {
                    SwapContent(busy == null, contentKey = { it }) { available ->
                        if (available) TextAction(S.s_hoan_tac_e72ff675, { undo(item.operationId) }, "cast_undo_${item.operationId}")
                        else RowHint(S.s_cho_ap_dung_77a52853)
                    }
                }
            }
        }
    }
}
