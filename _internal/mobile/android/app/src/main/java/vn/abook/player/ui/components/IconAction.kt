package vn.abook.player.ui.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import vn.abook.player.ui.theme.Dim

/** Icon-only action: a 48dp touch target and an explicit spoken name. */
@Composable
fun IconAction(description: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier, pending: Boolean = false, glyph: @Composable () -> Unit) {
    // `pending`: the action is waiting for its answer - the glyph crossfades to the shared spinner in place and a repeat tap is ignored.
    Box(modifier.size(Dim.s48).pressable(onClick = { if (!pending) onClick() }).semantics { contentDescription = description }.testTag(tag),
        contentAlignment = Alignment.Center) { StateIcon(pendingVisible(pending)) { waiting -> if (waiting) BusyRing() else glyph() } }
}
