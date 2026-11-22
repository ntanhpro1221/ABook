package vn.abook.player.ui.components

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.expandVertically
import androidx.compose.animation.shrinkVertically
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.compositeOver
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.AbookColors
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/**
 * Fill of anything that floats over content (chip, plate, toast): a `*Soft` token is translucent in dark mode (accent-soft is 14 % amber), so on its own
 * it lets the text underneath read through (chủ sách 22-11: the story text showed through "Về chỗ vừa nghe"). Compose the tint over the panel colour:
 * the same hue as the in-flow highlight, fully opaque. `ui_parity_rules.py` L14 rejects a translucent fill on a floating layer.
 */
fun floatingFill(colors: AbookColors, tint: Color = colors.accentSoft): Color = tint.compositeOver(colors.panel)

/**
 * A one-line action that floats over content ("Về chỗ vừa nghe", "Tới câu đang nghe"). The label sits in the middle of the 48 dp pill both ways - a Box
 * centres it; BasicText with its own min height puts the line at the top of the box (chủ sách 22-11, L13). Opaque fill ([floatingFill]).
 */
@Composable
fun FloatingChip(text: String, tag: String, modifier: Modifier = Modifier, onClick: () -> Unit) {
    val colors = Abook.colors
    Box(
        modifier
            .heightIn(min = Dim.s48)
            .clip(RoundedCornerShape(Dim.radiusCover))
            .background(floatingFill(colors))
            .pressable(onClick = onClick)
            .testTag(tag)
            .padding(horizontal = Dim.s16, vertical = Dim.s8),
        contentAlignment = Alignment.Center,
    ) {
        BasicText(text, style = Abook.type.caption.copy(color = colors.accentText, fontWeight = FontWeight.Medium, textAlign = TextAlign.Center))
    }
}

/**
 * Enter / leave of a floating chip: fade + a short rise from below (ui-motion-always: never a hard cut; reduced motion keeps the fade).
 * [inFlow]: the chip takes its own room in a column (a short window has no free band to float in), so it opens its height as well, like [Reveal].
 */
@Composable
fun FloatingReveal(visible: Boolean, modifier: Modifier = Modifier, inFlow: Boolean = false, content: @Composable () -> Unit) {
    if (vn.abook.player.ui.motion.rememberReducedMotion()) {
        vn.abook.player.ui.motion.ReducedFade(visible) { Box(modifier) { content() } }
        return
    }
    AnimatedVisibility(
        visible = visible,
        modifier = modifier,
        enter = fadeIn(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) +
            slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 2 } +
            (if (inFlow) expandVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate), expandFrom = Alignment.Top) else EnterTransition.None),
        exit = fadeOut(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) +
            slideOutVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { it / 2 } +
            (if (inFlow) shrinkVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate), shrinkTowards = Alignment.Top) else ExitTransition.None),
    ) {
        content()
    }
}
