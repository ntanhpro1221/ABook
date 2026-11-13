package vn.abook.player.ui.components

import androidx.compose.animation.core.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.graphics.graphicsLayer
import vn.abook.player.ui.motion.rememberReducedMotion
import vn.abook.player.ui.theme.MotionMs

/** Same 0.6 to 1, 1.6 second pulse as web and Qt; reduced motion keeps the placeholder still. */
fun Modifier.skeletonPulse(): Modifier = composed {
    val reduced = rememberReducedMotion()
    if (reduced) this else {
        val transition = rememberInfiniteTransition(label = "skeleton")
        val opacity by transition.animateFloat(
            initialValue = 1f, targetValue = MotionMs.SKELETON_LOW,
            animationSpec = infiniteRepeatable(tween(MotionMs.SKELETON_PERIOD_MS / 2, easing = LinearEasing), RepeatMode.Reverse),
            label = "skeleton-opacity",
        )
        graphicsLayer { alpha = opacity }
    }
}
