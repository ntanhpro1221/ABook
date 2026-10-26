package vn.abook.player.ui.components

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.MotionMs

/** Keep state-changing action labels moving vertically, using the same touch target as TextAction. */
@Composable
fun MovingTextAction(label: String, onClick: () -> Unit, tag: String, modifier: Modifier = Modifier, align: Alignment = Alignment.CenterEnd) {
    AnimatedContent(label, modifier, transitionSpec = {
        slideInVertically(tween(MotionMs.FAST, easing = Motion.Decelerate)) { it } togetherWith
            slideOutVertically(tween(MotionMs.FAST_OUT, easing = Motion.Accelerate)) { -it }
    }, label = "action_label") { shown -> TextAction(shown, onClick, tag, align = align) }
}
