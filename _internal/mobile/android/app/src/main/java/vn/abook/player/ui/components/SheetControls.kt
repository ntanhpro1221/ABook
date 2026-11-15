package vn.abook.player.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import vn.abook.player.S
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Flat sections and compact rows shared by player sheets. */
@Composable
fun SheetSection(title: String, first: Boolean = false, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().padding(top = if (first) 0.dp else Dim.s16), verticalArrangement = Arrangement.spacedBy(Dim.s8)) {
        BasicText(title, style = Abook.type.caption.copy(color = Abook.colors.text2, fontWeight = FontWeight.Medium))
        content()
    }
}

@Composable
fun SheetRow(label: String, modifier: Modifier = Modifier, hint: String? = null, trailing: @Composable () -> Unit) {
    Row(modifier.fillMaxWidth().heightIn(min = Dim.s48), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(Dim.s12)) {
        Column(Modifier.weight(1f)) {
            BasicText(label, style = Abook.type.bodySmall.copy(color = Abook.colors.text))
            Reveal(hint != null) { RowHint(hint.orEmpty()) }
        }
        trailing()
    }
}

@Composable
fun SheetSwitch(label: String, checked: Boolean, onChange: (Boolean) -> Unit, tag: String, hint: String? = null) {
    val view = LocalView.current
    SheetRow(label, Modifier.pressable(Role.Switch) { vn.abook.player.Feedback.play("toggle", view); onChange(!checked) }
        .semantics { stateDescription = if (checked) S.s_bat_f26cbc4a else S.s_tat_3286064e }.testTag(tag), hint) { Switch(checked) }
}

@Composable
fun SheetLink(label: String, onClick: () -> Unit, tag: String, value: String? = null) {
    SheetRow(label, Modifier.pressable(onClick = onClick).testTag(tag)) {
        Reveal(value != null) { BasicText(value.orEmpty(), Modifier.widthIn(max = 180.dp), style = Abook.type.bodySmall.copy(color = Abook.colors.text2, textAlign = TextAlign.End)) }
        ChevronIcon(Abook.colors.text2)
    }
}
