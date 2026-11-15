package vn.abook.player.ui.components

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import vn.abook.player.ui.motion.rememberReducedMotion
import vn.abook.player.ui.theme.MotionMs

/** DESIGN 5.2: glyph changes fade in place; this is not a content transition. */
@Composable
fun StateIcon(icon: String, color: Color, modifier: Modifier = Modifier) {
    val duration = if (rememberReducedMotion()) MotionMs.REDUCED_FADE_MS else MotionMs.FAST
    Crossfade(targetState = icon, modifier = modifier.size(20.dp), animationSpec = tween(duration), label = "icon_state") { shown ->
        LucideIcon(shown, color)
    }
}
