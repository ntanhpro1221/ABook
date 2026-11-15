package vn.abook.player.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** A list footer is an action: accent icon and label, with the standard press response. */
@Composable
fun InlineActionRow(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier, icon: String = LucidePaths.PLUS) {
    Row(modifier.fillMaxWidth().heightIn(min = Dim.s48)
        .semantics { contentDescription = label }.pressable(onClick = onClick).testTag(tag)
        .padding(vertical = Dim.s12), verticalAlignment = Alignment.CenterVertically) {
        LucideIcon(icon, Abook.colors.accentText, Modifier.testTag("action_row_icon"))
        Spacer(Modifier.width(Dim.s12))
        BasicText(label, Modifier.weight(1f).testTag("action_row_label"), Abook.type.label.copy(color = Abook.colors.accentText))
    }
}
