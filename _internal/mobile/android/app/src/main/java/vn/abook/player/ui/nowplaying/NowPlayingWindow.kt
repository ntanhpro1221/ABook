@file:OptIn(androidx.compose.animation.ExperimentalSharedTransitionApi::class)

package vn.abook.player.ui.nowplaying

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.animation.AnimatedVisibilityScope
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.SharedTransitionLayout
import androidx.compose.animation.SharedTransitionScope
import androidx.compose.animation.core.SeekableTransitionState
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.rememberTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.layout
import androidx.compose.ui.unit.Constraints
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.constrainWidth
import androidx.compose.ui.unit.constrainHeight
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.MotionMs

/** Both back and swipe seek the same Compose transition used to open the container. */
@Stable
class NowPlayingWindowState(private val scope: CoroutineScope) {
    val transition = SeekableTransitionState(false)
    var reading by mutableStateOf(false)
    var sheet by mutableStateOf(PlayerSheet.Speed)
        private set
    var sheetOpen by mutableStateOf(false)
        private set
    private var motion: Job? = null
    val expanded: Boolean get() = transition.currentState || transition.targetState

    fun open() {
        motion?.cancel()
        motion = scope.launch { transition.animateTo(true, tween(MotionMs.SLOW)) }
    }
    fun close() {
        sheetOpen = false
        motion?.cancel()
        motion = scope.launch { transition.animateTo(false, tween(MotionMs.SLOW_OUT)) }
    }
    suspend fun dragClose(progress: Float) {
        motion?.cancel()
        transition.seekTo(progress.coerceIn(0f, 1f), targetState = false)
    }
    suspend fun settleClose(commit: Boolean) {
        transition.animateTo(!commit, tween(if (commit) MotionMs.SLOW_OUT else MotionMs.SLOW))
    }
    fun openSheet(sheet: PlayerSheet) { this.sheet = sheet; sheetOpen = true }
    fun closeSheet() { sheetOpen = false }
}

/** Overlay clipping follows the very same progress as the shared container, in both directions. */
private class ContainerShape(private val progress: State<Float>) : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val radius = with(density) { 12.dp.toPx() } * (1f - progress.value)
        return Outline.Rounded(RoundRect(0f, 0f, size.width, size.height, CornerRadius(radius)))
    }
}

/** Stand-in mini bar + full window. The real mini bar reuses NowPlayingPart keys and [SharedPlayerParts]. */
@Composable
fun NowPlayingHost(
    model: NowPlayingModel,
    window: NowPlayingWindowState = rememberNowPlayingWindowState(),
    sampleClock: Boolean = true,
    content: @Composable () -> Unit,
) {
    val state by model.state.collectAsState()
    val transition = rememberTransition(window.transition, label = "now-playing-window")
    val progress = transition.animateFloat(transitionSpec = { tween(MotionMs.SLOW, easing = LinearEasing) }, label = "window-geometry") { if (it) 1f else 0f }
    val shape = remember(progress) { ContainerShape(progress) }
    PredictiveBackHandler(enabled = window.expanded && !window.sheetOpen) { events ->
        try {
            events.collect { window.dragClose(it.progress) }
            window.settleClose(commit = true)
        } catch (cancelled: CancellationException) {
            window.settleClose(commit = false)
            throw cancelled
        }
    }
    // Only visible lifecycle frames sample the core clock. Nothing in this host reads its changing values.
    LaunchedEffect(model, state.playing, window.expanded) {
        model.position.sample()
        if (state.playing && window.expanded && sampleClock) while (true) withFrameNanos { model.position.sample() }
    }
    SharedTransitionLayout(Modifier.fillMaxSize()) {
      Box(Modifier.fillMaxSize()) {
        content()
        if (state.bookId.isNotEmpty()) {
            transition.AnimatedVisibility(
                visible = { !it }, enter = EnterTransition.None, exit = ExitTransition.None,
                modifier = Modifier.align(Alignment.BottomCenter).padding(horizontal = 20.dp)
                    .navigationBarsPadding().padding(bottom = 64.dp),
            ) {
                val parts = SharedPlayerParts(this@SharedTransitionLayout, this)
                MiniPlayerStandIn(state, model, parts,
                    Modifier.sharedBounds(
                        rememberSharedContentState(NowPlayingPart.Container), this,
                        enter = EnterTransition.None, exit = ExitTransition.None,
                        boundsTransform = { _, _ -> tween(MotionMs.SLOW, easing = LinearEasing) },
                        resizeMode = SharedTransitionScope.ResizeMode.scaleToBounds(ContentScale.FillBounds, Alignment.TopStart),
                        clipInOverlayDuringTransition = OverlayClip(shape),
                    ).clip(RoundedCornerShape(12.dp)), window::open, progress)
            }
            transition.AnimatedVisibility(
                visible = { it }, enter = EnterTransition.None, exit = ExitTransition.None,
                modifier = Modifier.align(Alignment.TopStart),
            ) {
                val parts = SharedPlayerParts(this@SharedTransitionLayout, this)
                Box(
                    Modifier.testTag("now_playing_bounds").sharedBounds(
                        rememberSharedContentState(NowPlayingPart.Container), this,
                        enter = EnterTransition.None, exit = ExitTransition.None,
                        boundsTransform = { _, _ -> tween(MotionMs.SLOW, easing = LinearEasing) },
                        resizeMode = SharedTransitionScope.ResizeMode.scaleToBounds(ContentScale.FillBounds, Alignment.TopStart),
                        placeholderSize = SharedTransitionScope.PlaceholderSize.AnimatedSize,
                        clipInOverlayDuringTransition = OverlayClip(shape),
                    ).fillMaxSize().dismissPlayerOnDrag(window, !window.reading && !window.sheetOpen),
                ) {
                    NowPlayingScreen(state, model, window, parts, progress, Modifier.fillMaxSize().testTag("now_playing"))
                }
            }
        }
      }
    }
}

@Composable
fun rememberNowPlayingWindowState(): NowPlayingWindowState {
    val scope = rememberCoroutineScope()
    return remember(scope) { NowPlayingWindowState(scope) }
}

/** Modifier factory deliberately shared by mini and full views: each key occurs exactly once per view. */
@Stable
class SharedPlayerParts(
    private val shared: SharedTransitionScope,
    private val visibility: AnimatedVisibilityScope,
) {
    @Composable
    fun element(part: NowPlayingPart, modifier: Modifier = Modifier): Modifier = with(shared) {
        val geometry = remember(part) { SharedContentLayout() }
        modifier.sharedElement(rememberSharedContentState(part), visibility,
            boundsTransform = { _, _ -> tween(MotionMs.SLOW, easing = LinearEasing) })
            .layout { measurable, constraints ->
                // Preserve final text wrapping and decoded image size while the sharedElement supplies moving bounds.
                val fixed = geometry.target
                val child = measurable.measure(if (isLookingAhead || fixed == IntSize.Zero) constraints else Constraints.fixed(fixed.width, fixed.height))
                if (isLookingAhead || fixed == IntSize.Zero) geometry.target = IntSize(child.width, child.height)
                val width = if (isLookingAhead) child.width else constraints.constrainWidth(child.width)
                val height = if (isLookingAhead) child.height else constraints.constrainHeight(child.height)
                layout(width, height) {
                    child.placeWithLayer(0, 0) {
                        transformOrigin = TransformOrigin(0f, 0f)
                        val sx = if (child.width > 0) width.toFloat() / child.width else 1f
                        val sy = if (child.height > 0) height.toFloat() / child.height else 1f
                        scaleX = minOf(sx, sy); scaleY = scaleX
                    }
                }
            }
    }
}

private class SharedContentLayout { var target = IntSize.Zero }

@Composable
fun Modifier.dismissPlayerOnDrag(window: NowPlayingWindowState, enabled: Boolean): Modifier {
    val scope = rememberCoroutineScope()
    val view = LocalView.current
    return pointerInput(window, enabled) {
        if (enabled) {
            var drag = 0f
            var height = 1f
            detectVerticalDragGestures(
                onDragStart = { drag = 0f; height = view.height.toFloat().coerceAtLeast(1f) },
                onVerticalDrag = { change, amount ->
                    change.consume()
                    drag = (drag + amount).coerceAtLeast(0f)
                    scope.launch { window.dragClose(drag / height) }
                },
                onDragEnd = { scope.launch { window.settleClose(drag / height > 0.2f) } },
                onDragCancel = { scope.launch { window.settleClose(false) } },
            )
        }
    }
}

@Composable
private fun MiniPlayerStandIn(
    state: NowPlayingState, model: NowPlayingModel, parts: SharedPlayerParts,
    modifier: Modifier, onOpen: () -> Unit, progress: State<Float>,
) {
    Row(modifier.fillMaxWidth().background(Abook.colors.panel).pressable(onClick = onOpen)
        .padding(8.dp).testTag("mini_player"), verticalAlignment = Alignment.CenterVertically) {
        PlayerCover(state.cover, state.bookTitle, parts.element(NowPlayingPart.Cover, Modifier.size(44.dp)), decodeSize = 44.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            RollingLabel(state.chapterTitle, parts.element(NowPlayingPart.Chapter), Abook.type.label)
            RollingLabel(state.bookTitle, parts.element(NowPlayingPart.Book), Abook.type.caption)
        }
        PlayMorph(state.playing, model::toggle, progress, parts.element(NowPlayingPart.Play), large = false)
    }
}
