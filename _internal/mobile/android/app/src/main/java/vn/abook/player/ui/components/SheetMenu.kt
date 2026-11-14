package vn.abook.player.ui.components

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/** Measure every menu row at its full height, then scroll the viewport on short screens. */
@Composable
fun SheetMenu(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val scroll = rememberScrollState()
    Column(modifier.fillMaxWidth().fadeEdges(scroll).verticalScroll(scroll), content = content)
}
