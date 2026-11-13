package vn.abook.player.ui.devices

import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.motion.ContentLayout

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import vn.abook.player.ui.addbook.BookForm
import vn.abook.player.ui.components.fadeEdges
import vn.abook.player.ui.theme.Dim

/** Shared content has a single scroller: the settings group when embedded, its own page in fixtures. */
@Composable
internal fun DeviceSettingsContent(
    title: String, onBack: () -> Unit, tag: String, embedded: Boolean,
    footer: (@Composable ColumnScope.() -> Unit)? = null,
    trailing: (@Composable () -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    SwapContent(embedded, contentKey = { embedded -> embedded }, layout = ContentLayout.Box) { embedded ->
        if (embedded) {
            Column(Modifier.fillMaxWidth().testTag(tag)) {
                SwapContent(trailing, contentKey = { trailing -> trailing != null }, layout = ContentLayout.Column) { trailing ->
                    if (trailing != null) Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) { trailing() }
                }
                content()
                SwapContent(footer, contentKey = { footer -> footer != null }, layout = ContentLayout.Column) { footer ->
                    if (footer != null) Column(Modifier.fillMaxWidth().padding(vertical = Dim.s12), content = footer)
                }
            }
        } else {
            BookForm(title, onBack, tag, footer, trailing) {
                val scroll = rememberScrollState()
                Column(Modifier.fillMaxSize().fadeEdges(scroll).verticalScroll(scroll), content = content)
            }
        }
    }
}
