package vn.abook.player.ui.components

import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import vn.abook.player.ui.motion.SwapContent
import vn.abook.player.ui.theme.Abook

const val PENDING_DELAY_MS = 180L

@Composable
fun pendingVisible(pending: Boolean): Boolean {
    var visible by remember { mutableStateOf(false) }
    LaunchedEffect(pending) { visible = false; if (pending) { delay(PENDING_DELAY_MS); visible = true } }
    return pending && visible
}

/** Fixed slot, crossfade/scale only. No translation on a status icon. */
@Composable
fun <T> StateIcon(state: T, modifier: Modifier = Modifier, content: @Composable (T) -> Unit) =
    SwapContent(state, contentKey = { it }, modifier = modifier, inPlace = true, content = content)

@Composable
fun PendingIndicator(pending: Boolean, modifier: Modifier = Modifier, color: Color = Abook.colors.accentText, content: @Composable () -> Unit = {}) {
    val visible = pendingVisible(pending)
    StateIcon(visible, modifier.size(20.dp)) { if (it) BusyRing(color = color) else content() }
}
