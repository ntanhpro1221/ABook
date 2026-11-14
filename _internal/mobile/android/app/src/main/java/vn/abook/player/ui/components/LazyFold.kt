package vn.abook.player.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.mapSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.hideFromAccessibility
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import vn.abook.player.ui.motion.FadeDurationScale
import vn.abook.player.ui.motion.rememberReducedMotion
import vn.abook.player.ui.motion.Motion
import vn.abook.player.ui.theme.MotionMs

/** One owner per scrolling surface. Group state survives item disposal and process recreation. */
@Stable
class LazyFoldState internal constructor(private val scope: CoroutineScope, reduced: Boolean) {
    internal var reduced by mutableStateOf(reduced)
    internal class Group(initial: Boolean) {
        var open by mutableStateOf(initial)
        var retained by mutableStateOf(initial)
        val progress = Animatable(if (initial) 1f else 0f)
        var animation: Job? = null
    }
    internal val groups = mutableMapOf<String, Group>()
    internal fun group(key: String, defaultOpen: Boolean) = groups.getOrPut(key) { Group(defaultOpen) }
    fun setOpen(key: String, open: Boolean) {
        val group = group(key, false)
        if (group.open != open) toggle(group)
    }
    internal fun toggle(group: Group) {
        group.animation?.cancel()
        group.open = !group.open
        if (group.open) group.retained = true
        group.animation = scope.launch {
            val duration = if (reduced) MotionMs.REDUCED_FADE_MS else if (group.open) MotionMs.MEDIUM else MotionMs.MEDIUM_OUT
            val easing = if (group.open) Motion.Decelerate else Motion.Accelerate
            if (reduced) withContext(FadeDurationScale) { group.progress.animateTo(if (group.open) 1f else 0f, tween(duration, easing = easing)) }
            else group.progress.animateTo(if (group.open) 1f else 0f, tween(duration, easing = easing))
            if (!group.open) group.retained = false
        }
    }
}

@Composable
fun rememberLazyFoldState(): LazyFoldState {
    val scope = rememberCoroutineScope()
    val reduced = rememberReducedMotion()
    val saver = remember(scope) { mapSaver(
        save = { state: LazyFoldState -> state.groups.mapValues { it.value.open } },
        restore = { saved -> LazyFoldState(scope, reduced).also { state -> saved.forEach { (key, value) -> state.group(key, value as Boolean) } } },
    ) }
    return rememberSaveable(saver = saver) { LazyFoldState(scope, reduced) }.also { it.reduced = reduced }
}

/**
 * Children belong to the OUTER lazy list. Opening never composes offscreen children or animates their measurement.
 * Visible rows slide on layers; existing neighbours use lazy placement. Keep exits until the shared motion finishes.
 * A zero-height reveal per row would make the lazy list compose every row to fill its viewport, so never use it here.
 */
fun <T> LazyListScope.foldItems(
    state: LazyFoldState,
    title: String,
    tag: String,
    rows: List<T>,
    key: (T) -> String,
    modifier: Modifier = Modifier,
    summary: String? = null,
    defaultOpen: Boolean = false,
    contentType: String = tag,
    onOpen: (() -> Unit)? = null,
    header: (@Composable () -> Unit)? = null,
    footer: (@Composable () -> Unit)? = null,
    content: @Composable (Int, T) -> Unit,
) {
    val group = state.group(tag, defaultOpen)
    item(key = tag, contentType = "fold-heading") {
        LaunchedEffect(Unit) { if (group.open) onOpen?.invoke() }
        FoldHeading(title, tag, summary, group.open, { state.toggle(group); if (group.open) onOpen?.invoke() }, modifier.animateItem(fadeInSpec = null, fadeOutSpec = null))
    }
    revealItems(state, tag, rows, key, contentType, header, footer, content)
}

/** A group controlled by an existing action row, with the same lazy body and motion as foldItems. */
fun <T> LazyListScope.revealItems(
    state: LazyFoldState, tag: String, rows: List<T>, key: (T) -> String,
    contentType: String = tag, header: (@Composable () -> Unit)? = null, footer: (@Composable () -> Unit)? = null,
    content: @Composable (Int, T) -> Unit,
) {
    val group = state.group(tag, false)
    if (group.retained) {
        if (header != null) item(key = "$tag:lead", contentType = "fold-lead") { header() }
        itemsIndexed(rows, key = { _, row -> "$tag:${key(row)}" }, contentType = { _, _ -> contentType }) { index, row ->
            Box(Modifier.fillMaxWidth().animateItem(fadeInSpec = null, fadeOutSpec = null)
                .graphicsLayer {
                    if (state.reduced) alpha = group.progress.value
                    else translationY = (1f - group.progress.value) * -8.dp.toPx()
                }.then(if (group.open) Modifier else Modifier.semantics { hideFromAccessibility() })
                .testTag("${tag}_body"), propagateMinConstraints = true) { content(index, row) }
        }
        if (footer != null) item(key = "$tag:footer", contentType = "fold-footer") { footer() }
    }
}
