package vn.abook.player.ui.addbook

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.components.BackButton
import vn.abook.player.ui.components.ScreenHeader
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim

/** Shared form chrome; the title gets the remaining width and wraps independently of Back. */
@Composable
fun BookForm(title: String, onBack: () -> Unit, tag: String, footer: (@Composable () -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().background(Abook.colors.bg).windowInsetsPadding(WindowInsets.safeDrawing)
        .imePadding().padding(horizontal = Dim.margin).testTag(tag)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            BackButton(onBack)
            ScreenHeader(title, Modifier.weight(1f))
        }
        Column(Modifier.weight(1f), content = content)
        if (footer != null) Column(Modifier.fillMaxWidth().padding(vertical = Dim.s12)) { footer() }
    }
}

@Composable
fun BookField(label: String, value: String, onChange: (String) -> Unit, tag: String, enabled: Boolean = true) {
    Column(Modifier.fillMaxWidth().padding(vertical = Dim.s8)) {
        BasicText(label, style = Abook.type.bodySmall)
        Spacer(Modifier.height(Dim.s8))
        BasicTextField(value, onChange, enabled = enabled, textStyle = Abook.type.body,
            cursorBrush = SolidColor(Abook.colors.accentText),
            modifier = Modifier.fillMaxWidth().heightIn(min = Dim.s48).clip(RoundedCornerShape(Dim.radiusControl))
                .background(Abook.colors.bgSunken).padding(Dim.s12).semantics { contentDescription = label }.testTag(tag))
    }
}

@Composable
fun BookAction(label: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true) {
    Box(modifier.heightIn(min = Dim.s48).then(if (enabled) Modifier.pressable(onClick = onClick) else Modifier)
        .padding(vertical = Dim.s12), contentAlignment = Alignment.CenterStart) {
        BasicText(label, style = Abook.type.bodyStrong.copy(color = if (enabled) Abook.colors.accentText else Abook.colors.text3))
    }
}

@Composable
fun BookChoice(label: String, selected: Boolean, onClick: () -> Unit, note: String = "", tag: String = "", enabled: Boolean = true) {
    Row(Modifier.fillMaxWidth().heightIn(min = Dim.s48)
        .then(if (enabled) Modifier.pressable(Role.Checkbox, onClick = onClick) else Modifier)
        .semantics { this.selected = selected }.testTag(tag).padding(vertical = Dim.s8), verticalAlignment = Alignment.Top) {
        BasicText(if (selected) "✓" else "□", style = Abook.type.bodyStrong.copy(color = Abook.colors.accentText),
            modifier = Modifier.width(32.dp))
        Column(Modifier.weight(1f)) {
            BasicText(label, style = Abook.type.body.copy(color = if (selected) Abook.colors.accentText else Abook.colors.text))
            if (note.isNotEmpty()) BasicText(note, style = Abook.type.bodySmall)
        }
    }
}

@Composable
fun BookProblem(message: String) {
    AnimatedVisibility(message.isNotEmpty(), enter = expandVertically() + slideInVertically { -it / 2 },
        exit = shrinkVertically() + slideOutVertically { -it / 2 }) {
        BasicText(message, style = Abook.type.bodySmall.copy(color = Abook.colors.danger),
            modifier = Modifier.fillMaxWidth().padding(vertical = Dim.s8).testTag("book_problem"))
    }
}
