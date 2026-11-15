package vn.abook.player.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.Dp

// A menu nested in a scrollable sheet must use the visible sheet viewport,
// rather than the outer scroll container's larger content-measurement bound.
internal val LocalSheetViewportHeight = staticCompositionLocalOf { Dp.Unspecified }

/** Measure every menu row at its full height, then scroll the viewport on short screens. */
@Composable
fun SheetMenu(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val scroll = rememberScrollState()
    val viewport = LocalSheetViewportHeight.current
    val bounded = if (viewport != Dp.Unspecified) Modifier.heightIn(max = viewport) else Modifier
    Column(modifier.fillMaxWidth().then(bounded).fadeEdges(scroll).verticalScroll(scroll), content = content)
}
