package vn.abook.player.ui.components

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import vn.abook.player.ui.theme.Abook

/** Empty choices remain visible; the mark fades at the same position. */
@Composable
fun SelectionMark(selected: Boolean, modifier: Modifier = Modifier) {
    StateIcon(if (selected) LucidePaths.CHECK else LucidePaths.CIRCLE, if (selected) Abook.colors.accentText else Abook.colors.text3, modifier)
}
