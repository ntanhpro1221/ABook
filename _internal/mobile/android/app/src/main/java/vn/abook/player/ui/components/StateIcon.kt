package vn.abook.player.ui.components

import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp

/** DESIGN 5.2: glyph changes fade in place; this is not a content transition. Same in-place
 * cross-fade + scale as every other status icon ([StateIcon] over SwapContent), web and Qt. */
@Composable
fun StateIcon(icon: String, color: Color, modifier: Modifier = Modifier) =
    StateIcon(icon, modifier.size(20.dp)) { shown -> LucideIcon(shown, color) }
