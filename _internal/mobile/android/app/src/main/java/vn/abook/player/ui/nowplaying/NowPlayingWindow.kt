package vn.abook.player.ui.nowplaying

import androidx.activity.compose.PredictiveBackHandler
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.RoundRect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.GraphicsLayerScope
import androidx.compose.ui.graphics.Outline
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.TransformOrigin
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.LayoutCoordinates
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.hideFromAccessibility
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.LayoutDirection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

/**
 * The window opens from the mini bar and closes back into it. [progress] (0 = the bar, 1 = the whole window) is the only value that runs per frame, and it is read
 * ONLY in graphicsLayer blocks and draw lambdas: open, close, swipe and predictive back all drive it, nothing is measured or composed while it moves. The window is
 * composed and laid out once at its final size while still hidden ([WindowFlight.ready] = false); the container and the four shared parts (cover, chapter, book,
 * play) then fly as layer translations / scales between the rectangles measured once at the start of the motion. (Shared-element bounds relaid the whole app,
 * lookahead included, on every frame: 781 ms main-thread CPU per 8 open/close cycles on the emulator.)
 */
@Stable
class NowPlayingWindowState(private val scope: CoroutineScope) {
    var otherPlayers: (() -> Unit)? = null

    /** Tới Cài đặt > Giọng đọc (khối lỗi "Tải giọng VieNeu", "Xem trong Cài đặt"); null = không có đường ấy. */
    var voiceSettings: (() -> Unit)? = null

    /** Dáng chữ của Đọc theo (cỡ chữ, giãn dòng): nhớ giữa các lần mở qua [onLook]. */
    var look by mutableStateOf(ReadLook())

    /** Nhớ dáng chữ vừa đổi; null = không nhớ (bản thử). */
    var onLook: ((ReadLook) -> Unit)? = null
    fun changeLook(next: ReadLook) {
        if (next == look) return
        look = next
        onLook?.invoke(next)
    }

    /** "Về thư viện" sau khi nghe hết sách: thu cửa sổ, về tab Thư viện; null = không có (bản thử). */
    var toLibrary: (() -> Unit)? = null

    /** Vào cửa sổ nhỏ (PiP) ngay; null = máy / app không cho PiP thì Đang nghe không có nút "Cửa sổ mini". */
    var miniWindow: (() -> Unit)? = null

    /** 0 = thanh phát nhỏ, 1 = cả cửa sổ. Chỉ đọc trong pha vẽ (graphicsLayer / drawBehind). */
    val progress = Animatable(0f)
    private val progressState: State<Float> = progress.asState()
    internal val flight = WindowFlight()

    /** The window is composed: from the build frame of an opening until its closing motion has ended. */
    var shown by mutableStateOf(false)
        private set
    var reading by mutableStateOf(false)

    /** Số phút của lần hẹn giờ gần nhất: tấm Hẹn giờ mời "Bật lại N phút" khi hẹn giờ vừa tắt tiếng (web: 30 lúc đầu). */
    var lastSleepMinutes by mutableIntStateOf(30)
    var sheet by mutableStateOf(PlayerSheet.Speed)
        private set
    var sheetOpen by mutableStateOf(false)
        private set
    private var motion: Job? = null
    private var dragging = false
    val expanded: Boolean get() = shown

    /** The progress as a State for the screen's reveal parts (they read it in graphicsLayer, never in composition). */
    internal fun progressState(): State<Float> = progressState

    /** Where the window container is now, in the overlay's pixels (what the user sees: the bar at 0, the whole layer at 1). */
    internal fun containerBounds(width: Float, height: Float): Rect = flight.container(progress.value, width, height)

    fun open() {
        motion?.cancel()
        motion = scope.launch {
            if (!shown) {
                flight.ready = false
                progress.snapTo(0f)
                // The window is composed and laid out hidden; the overlay's first layout (same frame) opens the gate, and only then are the rectangles
                // of the bar and of the parts known. The motion starts on the very next frame: no waiting frames.
                val laidOut = CompletableDeferred<Unit>()
                flight.laidOut = laidOut
                shown = true
                withTimeoutOrNull(250) { laidOut.await() }
                flight.laidOut = null
            }
            dragging = false
            flight.capture()
            progress.animateTo(1f, tween(MotionMs.SLOW))
        }
    }

    /** "Đọc theo" từ trang sách: mở thẳng ở chế độ đọc. */
    fun openReading() {
        reading = true
        open()
    }
    fun close() {
        sheetOpen = false
        if (!shown) return
        motion?.cancel()
        motion = scope.launch {
            flight.capture()
            progress.animateTo(0f, tween(MotionMs.SLOW_OUT))
            shown = false
        }
    }
    suspend fun dragClose(progress: Float) {
        motion?.cancel()
        if (!dragging) { dragging = true; flight.capture() }
        this.progress.snapTo(1f - progress.coerceIn(0f, 1f))
    }
    suspend fun settleClose(commit: Boolean) {
        dragging = false
        flight.capture()
        if (commit) {
            progress.animateTo(0f, tween(MotionMs.SLOW_OUT))
            shown = false
        } else {
            progress.animateTo(1f, tween(MotionMs.SLOW))
        }
    }
    fun openSheet(sheet: PlayerSheet) { this.sheet = sheet; sheetOpen = true }
    fun closeSheet() { sheetOpen = false }
}

/**
 * The rectangles of one motion: the bar and its parts (sources, registered by the real mini player) and the window's parts (targets, registered by
 * [SharedPlayerParts]), converted ONCE by [capture] into the overlay's coordinates. Layer blocks only read the numbers below; [ready] is the one state they observe.
 */
@Stable
internal class WindowFlight {
    /** False while the window is composed but not yet measured: the container is invisible and the bar is still the only thing on screen. */
    var ready by mutableStateOf(false)
    var density: Density = Density(1f)
    var overlay: LayoutCoordinates? = null

    /** Completed by the overlay's first layout while an opening waits for it. */
    var laidOut: CompletableDeferred<Unit>? = null
    var bar: LayoutCoordinates? = null
    private val count = NowPlayingPart.entries.size
    val sources = arrayOfNulls<LayoutCoordinates>(count)
    val targets = arrayOfNulls<LayoutCoordinates>(count)
    private var barRect = Rect.Zero
    private val has = BooleanArray(count)
    private val shiftX = FloatArray(count)
    private val shiftY = FloatArray(count)
    private val scale0 = FloatArray(count)

    fun capture() {
        val root = overlay?.takeIf { it.isAttached } ?: return
        val w = root.size.width.toFloat()
        val h = root.size.height.toFloat()
        barRect = bar?.takeIf { it.isAttached }?.let { rect(root, it) } ?: Rect(0f, h - 64f * density.density, w, h)
        for (i in 0 until count) {
            val from = sources[i]?.takeIf { it.isAttached }?.let { rect(root, it) }
            val targetCoordinates = targets[i]?.takeIf { it.isAttached }
            val to = targetCoordinates?.let { rect(root, it) }
            has[i] = from != null && to != null && to.width > 0.5f && to.height > 0.5f && from.width > 0.5f && from.height > 0.5f
            if (!has[i]) continue
            // A part may sit under a scaled parent layer (the small cover in reading mode): a layer shift is in the part's own units.
            val inherited = (to!!.width / targetCoordinates!!.size.width.coerceAtLeast(1)).coerceAtLeast(1e-3f)
            shiftX[i] = (from!!.left - to.left) / inherited
            shiftY[i] = (from.top - to.top) / inherited
            scale0[i] = minOf(from.width / to.width, from.height / to.height)
        }
        ready = true
    }

    private fun rect(root: LayoutCoordinates, c: LayoutCoordinates): Rect =
        Rect(root.localPositionOf(c, Offset.Zero), root.localPositionOf(c, Offset(c.size.width.toFloat(), c.size.height.toFloat())))

    fun container(p: Float, width: Float, height: Float): Rect = Rect(
        barRect.left * (1f - p), barRect.top * (1f - p),
        barRect.right + (width - barRect.right) * p, barRect.bottom + (height - barRect.bottom) * p,
    )

    /**
     * The container's layer block: clip to the rectangle that grows from the bar to the whole layer, corners round in flight and square at both ends.
     * The window is transparent at progress 0 and fully there from [FADE_IN] on: at both ends of the motion the screen shows the real mini bar, untouched
     * (its own cover, initials or art, its own text weights), never the window's scaled copy of them, so nothing swaps when the motion starts or lands.
     */
    fun GraphicsLayerScope.reveal(progress: State<Float>) {
        if (!ready) { alpha = 0f; return }
        val p = progress.value
        if (p >= 1f) return
        val a = windowAlpha(p)
        if (a < 1f) {
            alpha = a
            compositingStrategy = CompositingStrategy.ModulateAlpha
        }
        val r = container(p, size.width, size.height)
        shape = RevealShape(r.left, r.top, r.right, r.bottom, Dim.radiusSheet.toPx() * 4f * p * (1f - p))
        clip = true
    }

    /** A part's layer block: the part is laid out at its final size and flies from the bar part's rectangle (scaled uniformly, top-left anchored). */
    fun GraphicsLayerScope.fly(index: Int, progress: State<Float>) {
        if (!ready || !has[index]) return
        val p = progress.value
        if (p >= 1f) return
        transformOrigin = TransformOrigin(0f, 0f)
        val s = scale0[index] + (1f - scale0[index]) * p
        scaleX = s
        scaleY = s
        translationX = shiftX[index] * (1f - p)
        translationY = shiftY[index] * (1f - p)
    }
}

/** How much of the window shows at progress `p`: nothing at 0 (the real bar), all of it from [FADE_IN]. */
internal fun windowAlpha(p: Float): Float = (p / FADE_IN).coerceIn(0f, 1f)

/** Progress at which the window has faded fully in over the bar (and from which it starts to fade out on the way back). */
private const val FADE_IN = 0.08f

private data class RevealShape(val left: Float, val top: Float, val right: Float, val bottom: Float, val radius: Float) : Shape {
    override fun createOutline(size: Size, layoutDirection: LayoutDirection, density: Density): Outline =
        Outline.Rounded(RoundRect(left, top, right, bottom, CornerRadius(radius)))
}

/** What the real mini player (in the root tabs) needs to turn into the window: the window state, whose flight holds the rectangles. */
@Stable
class NowPlayingLink(val window: NowPlayingWindowState)

val LocalNowPlaying = staticCompositionLocalOf<NowPlayingLink?> { null }

/**
 * The window layer at the root of the app: `content` (with the real mini player somewhere in it) and, above it, the full window - composed only while it is
 * opening, open or closing. Descendants reach the state through [LocalNowPlaying] ([NowPlayingSource]).
 * Its Back handler is registered after everything `content` composes first, so while the window is expanded Back closes the window and never pops a screen.
 */
@Composable
fun NowPlayingLayer(
    model: NowPlayingModel,
    window: NowPlayingWindowState = rememberNowPlayingWindowState(),
    sampleClock: Boolean = true,
    content: @Composable () -> Unit,
) {
    val flight = window.flight
    flight.density = LocalDensity.current
    val progress = remember(window) { window.progressState() }
    // Only visible lifecycle frames sample the core clock. Nothing in this layer reads its changing values.
    LaunchedEffect(model, window, sampleClock) {
        val playing = model.state.map { it.playing }.distinctUntilChanged()
        val open = snapshotFlow { window.expanded }.distinctUntilChanged()
        combine(playing, open) { isPlaying, isOpen -> isPlaying && isOpen }.collectLatest { running ->
            model.position.sample()
            if (running && sampleClock) while (true) withFrameNanos { model.position.sample() }
        }
    }
    PrefetchPlayerCover(remember(model) { model.state.map { it.cover }.distinctUntilChanged() })
    val link = remember(window) { NowPlayingLink(window) }
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
            if (window.shown) {
                val state by model.state.collectAsState()
                val parts = remember(window) { SharedPlayerParts(flight, progress) }
                Box(
                    Modifier.testTag("now_playing_bounds").fillMaxSize()
                        .onGloballyPositioned { flight.overlay = it; flight.laidOut?.complete(Unit) }
                        .graphicsLayer { with(flight) { reveal(progress) } }
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

/**
 * The real mini player's side of the motion: hands over the modifier that registers the bar (`modifier`, to put on the bar) and the Cover / Chapter / Book / Play
 * parts (`part(NowPlayingPart.Cover)`...), whose rectangles the window flies from. The bar stays composed under the window and is hidden from accessibility while the
 * window is up. Without a window layer (previews, tests) it is a plain bar.
 */
@Composable
fun NowPlayingSource(content: @Composable (modifier: Modifier, part: @Composable (NowPlayingPart) -> Modifier) -> Unit) {
    val link = LocalNowPlaying.current
    if (link == null) {
        content(Modifier) { Modifier }
        return
    }
    val window = link.window
    val flight = window.flight
    val parts = remember(flight) {
        Array(NowPlayingPart.entries.size) { i -> Modifier.onGloballyPositioned { flight.sources[i] = it } }
    }
    val part = remember(parts) { @Composable { which: NowPlayingPart -> parts[which.ordinal] } }
    val bar = remember(window) {
        Modifier.onGloballyPositioned { flight.bar = it }.semantics { if (window.expanded) hideFromAccessibility() }
    }
    content(bar, part)
}

@Composable
fun rememberNowPlayingWindowState(): NowPlayingWindowState {
    val scope = rememberCoroutineScope()
    return remember(scope) { NowPlayingWindowState(scope) }
}

/** Modifier factory deliberately shared by mini and full views: each key occurs exactly once per view. */
@Stable
class SharedPlayerParts internal constructor(
    flight: WindowFlight,
    progress: State<Float>,
) {
    private val modifiers: Array<Modifier> = Array(NowPlayingPart.entries.size) { i ->
        // The inner empty layer keeps the part's drawing recorded once: the flight only moves the outer one.
        Modifier.onGloballyPositioned { flight.targets[i] = it }.graphicsLayer { with(flight) { fly(i, progress) } }.graphicsLayer {}
    }

    /** The flight layers are outermost, so the caller's modifiers (test tag, press, hit area) travel with the part. */
    fun element(part: NowPlayingPart, modifier: Modifier = Modifier): Modifier = modifiers[part.ordinal].then(modifier)
}

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
