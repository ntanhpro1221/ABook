package vn.abook.player.ui.components

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.data.UndoDelete
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** In the root's layout: pushes content, never covers the mini player; Back dismisses the action. */
@Composable
fun UndoBar(deletions: UndoDelete, backEnabled: Boolean = true, aboveNavigation: Boolean = false) {
    val ids by deletions.undoable.collectAsState()
    val showing by deletions.showing.collectAsState()
    val problem by deletions.problem.collectAsState()
    val notice by deletions.notice.collectAsState()
    val message by deletions.message.collectAsState()
    val visible = showing || problem.isNotEmpty() || notice.isNotEmpty()
    val now = if (problem.isNotEmpty()) problem else if (notice.isNotEmpty()) notice else message
    // Lúc thanh trượt ra, chữ giữ nguyên câu cuối đã hiện (không nhảy sang câu khác giữa chừng).
    val last = remember { arrayOf(now) }
    if (visible) last[0] = now
    val shown = last[0]
    BackHandler(enabled = backEnabled && visible) { deletions.dismiss() }
    Reveal(visible) {
        Row(Modifier.fillMaxWidth().background(Abook.colors.panel).then(if (aboveNavigation) Modifier else Modifier.navigationBarsPadding()).heightIn(min = Dim.s48).padding(horizontal = Dim.margin).testTag("undo_bar"), verticalAlignment = Alignment.CenterVertically) {
            BasicText(shown, style = Abook.type.bodySmall, modifier = Modifier.weight(1f).padding(vertical = Dim.s12))
            if (showing && ids.isNotEmpty()) {
                Spacer(Modifier.width(Dim.s16))
                TextAction("Hoàn tác", deletions::undo, "undo_delete")
            }
        }
    }
}
