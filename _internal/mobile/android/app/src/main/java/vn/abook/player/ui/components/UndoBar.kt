package vn.abook.player.ui.components

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.BasicText
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
    var count by remember { mutableIntStateOf(1) }
    if (ids.isNotEmpty()) count = ids.size
    BackHandler(enabled = backEnabled && (showing || problem.isNotEmpty())) { deletions.dismiss() }
    Reveal(showing || problem.isNotEmpty()) {
        Row(Modifier.fillMaxWidth().background(Abook.colors.panel).then(if (aboveNavigation) Modifier else Modifier.navigationBarsPadding()).heightIn(min = Dim.s48).padding(horizontal = Dim.margin).testTag("undo_bar"), verticalAlignment = Alignment.CenterVertically) {
            BasicText(if (problem.isNotEmpty()) problem else if (count == 1) "Đã bỏ sách" else "Đã bỏ $count cuốn", style = Abook.type.bodySmall, modifier = Modifier.weight(1f).padding(vertical = Dim.s12))
            if (showing && ids.isNotEmpty()) {
                Spacer(Modifier.width(Dim.s16))
                TextAction("Hoàn tác", deletions::undo, "undo_delete")
            }
        }
    }
}
