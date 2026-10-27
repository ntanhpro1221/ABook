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
import androidx.compose.animation.core.Transition
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.rememberTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import androidx.lifecycle.compose.LocalLifecycleOwner
import kotlinx.coroutines.launch
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/** Both back and swipe seek the same Compose transition used to open the container. */
@Stable
class NowPlayingWindowState(private val scope: CoroutineScope) {
    var otherPlayers: (() -> Unit)? = null

    /** Vào cửa sổ nhỏ (PiP) ngay; null = máy / app không cho PiP thì Đang nghe không có nút "Cửa sổ mini". */
    var miniWindow: (() -> Unit)? = null
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

    /** "Đọc theo" từ trang sách: mở thẳng ở chế độ đọc. */
    fun openReading() {
        reading = true
        open()
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

/** Overlay clipping follows the very same progress as the shared container, in both directions: square at both ends (the bar and the screen), rounded in flight. */
private class ContainerShape(private val progress: State<Float>) : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline {
        val p = progress.value
        val radius = with(density) { Dim.radiusSheet.toPx() } * 4f * p * (1f - p)
        return Outline.Rounded(RoundRect(0f, 0f, size.width, size.height, CornerRadius(radius)))
    }
}

/** What the real mini player (in the root tabs) needs to turn into the window: the window state, its transition, the shared scope. */
@Stable
class NowPlayingLink(
    val window: NowPlayingWindowState,
    val transition: Transition<Boolean>,
    val progress: State<Float>,
    val shared: SharedTransitionScope,
    internal val shape: Shape,
)

val LocalNowPlaying = staticCompositionLocalOf<NowPlayingLink?> { null }

/**
 * The window layer at the root of the app: one [SharedTransitionLayout] holds the app (`content`, with the real mini player somewhere in it) and, above it,
 * the full window - composed only while it is expanding or expanded. Descendants reach the transition through [LocalNowPlaying] ([NowPlayingSource]).
 * Its Back handler is registered after everything `content` composes first, so while the window is expanded Back closes the window and never pops a screen.
 */
@Composable
fun NowPlayingLayer(
    model: NowPlayingModel,
    window: NowPlayingWindowState = rememberNowPlayingWindowState(),
    sampleClock: Boolean = true,
    content: @Composable () -> Unit,
) {
    val transition = rememberTransition(window.transition, label = "now-playing-window")
    val progress = transition.animateFloat(transitionSpec = { tween(MotionMs.SLOW, easing = LinearEasing) }, label = "window-geometry") { if (it) 1f else 0f }
    val shape = remember(progress) { ContainerShape(progress) }
    // Only visible lifecycle frames sample the core clock. Nothing in this layer reads its changing values.
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(model, window, sampleClock, lifecycle) {
        if (sampleClock) samplePlayerClock(lifecycle, model, snapshotFlow { window.expanded })
    }
    SharedTransitionLayout(Modifier.fillMaxSize()) {
        val link = remember(window, transition, progress, shape, this) { NowPlayingLink(window, transition, progress, this, shape) }
        CompositionLocalProvider(LocalNowPlaying provides link) {
            Box(Modifier.fillMaxSize()) {
                content()
                // After `content` on purpose: the last handler registered is asked first, so Back closes the open window before anything the screens set up.
                // A sheet that opens later (shell sheets, the window's own) registers after this and still wins - "Back with a sheet open closes only the sheet".
                PredictiveBackHandler(enabled = window.expanded && !window.sheetOpen) { events ->
                    try {
                        events.collect { window.dragClose(it.progress) }
                        window.settleClose(commit = true)
                    } catch (cancelled: CancellationException) {
                        window.settleClose(commit = false)
                        throw cancelled
                    }
                }
                transition.AnimatedVisibility(
                    visible = { it }, enter = EnterTransition.None, exit = ExitTransition.None,
                    modifier = Modifier.align(Alignment.TopStart),
                ) {
                    val parts = remember(this@SharedTransitionLayout, this) { SharedPlayerParts(this@SharedTransitionLayout, this) }
                    val state by model.state.collectAsState()
                    Box(
                        Modifier.testTag("now_playing_bounds").sharedBounds(
                            rememberSharedContentState(NowPlayingPart.Container), this,
                            enter = EnterTransition.None, exit = ExitTransition.None,
                            boundsTransform = { _, _ -> tween(MotionMs.SLOW, easing = LinearEasing) },
                            resizeMode = SharedTransitionScope.ResizeMode.scaleToBounds(ContentScale.FillBounds, Alignment.TopStart),
                            placeholderSize = SharedTransitionScope.PlaceholderSize.AnimatedSize,
                            clipInOverlayDuringTransition = OverlayClip(shape),
                        ).fillMaxSize()
                            // The window owns every touch inside it: nothing reaches the screens underneath, in reading mode too.
                            .pointerInput(Unit) {}
                            .dismissPlayerOnDrag(window, !window.reading && !window.sheetOpen),
                    ) {
                        NowPlayingScreen(state, model, window, parts, progress, Modifier.fillMaxSize().testTag("now_playing"))
                    }
                }
            }
        }
    }
}

/**
 * The real mini player's side of the morph: wraps it in the window transition's `AnimatedVisibility(!expanded)` and hands over the container's shared bounds
 * (`modifier`, to put on the bar) and the Cover / Chapter / Book / Play parts (`part(NowPlayingPart.Cover)`...). Without a window layer (previews, tests) it is a plain bar.
 */
@Composable
fun NowPlayingSource(content: @Composable (modifier: Modifier, part: @Composable (NowPlayingPart) -> Modifier) -> Unit) {
    val link = LocalNowPlaying.current
    if (link == null) {
        content(Modifier) { Modifier }
        return
    }
    with(link.shared) {
        link.transition.AnimatedVisibility(visible = { !it }, enter = EnterTransition.None, exit = ExitTransition.None) {
            val parts = remember(link.shared, this) { SharedPlayerParts(link.shared, this) }
            val part = remember(parts) { @Composable { which: NowPlayingPart -> parts.element(which) } }
            content(
                Modifier.sharedBounds(
                    rememberSharedContentState(NowPlayingPart.Container), this,
                    enter = EnterTransition.None, exit = ExitTransition.None,
                    boundsTransform = { _, _ -> tween(MotionMs.SLOW, easing = LinearEasing) },
                    resizeMode = SharedTransitionScope.ResizeMode.scaleToBounds(ContentScale.FillBounds, Alignment.TopStart),
                    clipInOverlayDuringTransition = OverlayClip(link.shape),
                ),
                part,
            )
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
