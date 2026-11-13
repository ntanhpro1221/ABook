package vn.abook.player.ui.motion

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.key.onPreviewKeyEvent
import androidx.compose.ui.input.pointer.PointerEventPass
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.withContext
import vn.abook.player.ui.theme.MotionMs

enum class ContentLayout { Box, Column, Row }

/** Snapshot the values used by a branch, not just its Boolean. The outgoing lambda
 * keeps its own nullable values and smart casts until the shared transition ends.
 * contentKey excludes clocks and polling data that do not actually change branches. */
@Composable
fun <T> SwapContent(
    value: T,
    contentKey: (T) -> Any?,
    layout: ContentLayout = ContentLayout.Box,
    modifier: Modifier = Modifier,
    spacing: Dp = 0.dp,
    content: @Composable (T) -> Unit,
) {
    if (rememberReducedMotion()) {
        ReducedSwap(value, contentKey, layout, modifier, spacing, content)
    } else {
        AnimatedContent(
            targetState = value,
            modifier = modifier,
            contentKey = contentKey,
            transitionSpec = {
                (fadeIn(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) +
                    slideInVertically(tween(MotionMs.MEDIUM, easing = Motion.Decelerate)) { it / 8 }) togetherWith
                    (fadeOut(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) +
                        slideOutVertically(tween(MotionMs.MEDIUM_OUT, easing = Motion.Accelerate)) { -it / 8 })
            },
            label = "conditional-content",
        ) { snapshot -> ContentGroup(layout, contentKey(snapshot) == contentKey(value), spacing) { content(snapshot) } }
    }
}

@Composable
private fun ContentGroup(layout: ContentLayout, active: Boolean = true, spacing: Dp = 0.dp, content: @Composable () -> Unit) {
    val modifier = if (active) Modifier else Modifier.clearAndSetSemantics {}.onPreviewKeyEvent { true }.pointerInput(Unit) {
        awaitPointerEventScope {
            while (true) awaitPointerEvent(PointerEventPass.Initial).changes.forEach { it.consume() }
        }
    }
    when (layout) {
        ContentLayout.Box -> Box(modifier) { content() }
        ContentLayout.Column -> Column(modifier, verticalArrangement = Arrangement.spacedBy(spacing)) { content() }
        ContentLayout.Row -> Row(modifier, horizontalArrangement = Arrangement.spacedBy(spacing), verticalAlignment = Alignment.CenterVertically) { content() }
    }
}

private data class RetainedValue<T>(val value: T)

/** OS animation scale zero still has a real fade, on the same clock as ReducedFade. */
@Composable
private fun <T> ReducedSwap(value: T, keyOf: (T) -> Any?, layout: ContentLayout, modifier: Modifier, spacing: Dp, content: @Composable (T) -> Unit) {
    val key = keyOf(value)
    var current by remember { mutableStateOf(RetainedValue(value)) }
    var previous by remember { mutableStateOf<RetainedValue<T>?>(null) }
    var lastKey by remember { mutableStateOf(key) }
    val alpha = remember { Animatable(1f) }
    if (key != lastKey) {
        previous = current
        lastKey = key
    }
    current = RetainedValue(value)
    LaunchedEffect(key) {
        if (previous != null) {
            alpha.snapTo(0f)
            withContext(FadeDurationScale) { alpha.animateTo(1f, tween(MotionMs.REDUCED_FADE_MS)) }
            previous = null
        }
    }
    Box(modifier) {
        previous?.let { old ->
            Box(Modifier.graphicsLayer { this.alpha = 1f - alpha.value }) { ContentGroup(layout, false, spacing) { content(old.value) } }
        }
        Box(Modifier.graphicsLayer { this.alpha = alpha.value }) { ContentGroup(layout, spacing = spacing) { content(value) } }
    }
}

@Composable
fun <A, B> SwapContent(a: A, b: B, contentKey: (A, B) -> Any?, layout: ContentLayout = ContentLayout.Box, modifier: Modifier = Modifier, spacing: Dp = 0.dp, content: @Composable (A, B) -> Unit) =
    SwapContent(Pair(a, b), { contentKey(it.first, it.second) }, layout, modifier, spacing) { content(it.first, it.second) }

@Composable
fun <A, B, C> SwapContent(a: A, b: B, c: C, contentKey: (A, B, C) -> Any?, layout: ContentLayout = ContentLayout.Box, modifier: Modifier = Modifier, spacing: Dp = 0.dp, content: @Composable (A, B, C) -> Unit) =
    SwapContent(Triple(a, b, c), { contentKey(it.first, it.second, it.third) }, layout, modifier, spacing) { content(it.first, it.second, it.third) }

@Composable
fun <A, B, C, D> SwapContent(a: A, b: B, c: C, d: D, contentKey: (A, B, C, D) -> Any?, layout: ContentLayout = ContentLayout.Box, modifier: Modifier = Modifier, spacing: Dp = 0.dp, content: @Composable (A, B, C, D) -> Unit) =
    SwapContent(Pair(Pair(a, b), Pair(c, d)), { contentKey(it.first.first, it.first.second, it.second.first, it.second.second) }, layout, modifier, spacing) {
        content(it.first.first, it.first.second, it.second.first, it.second.second)
    }
