package vn.abook.player.ui.nowplaying

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.SizeTransform
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.unit.sp
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.Dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.MotionMs

private val LocalPlayerCovers = staticCompositionLocalOf { CoverLoader() }

@Composable
fun PlayerCoverProvider(covers: CoverLoader, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalPlayerCovers provides covers, content = content)
}

/** Cover always decoded at requested display size on IO; cache is the app's existing byte-bounded loader. */
@Composable
fun PlayerCover(ref: CoverRef?, title: String, modifier: Modifier = Modifier, decodeSize: Dp? = null) {
    val covers = LocalPlayerCovers.current
    val density = LocalDensity.current
    // Decode at the final display-slot bound, never at intermediate shared-element sizes.
    val displaySize = decodeSize ?: minOf((LocalConfiguration.current.screenWidthDp - 40).dp, 320.dp)
    val requestPx = with(density) { displaySize.roundToPx().coerceAtLeast(1) }
    BoxWithConstraints(modifier.clip(RoundedCornerShape(12.dp)).background(Abook.colors.bgSunken), contentAlignment = Alignment.Center) {
        val width = requestPx
        val height = requestPx
        val cacheKey = ref?.let { covers.key(it.path, it.stamp, width) }
        val bitmap by produceState<ImageBitmap?>(cacheKey?.let(covers::peek), cacheKey) {
            value = if (ref != null && cacheKey != null) covers.load(cacheKey, ref.path, width, height) else null
        }
        if (bitmap != null) Image(bitmap!!, title, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        else BasicText(title.take(1).uppercase(), style = Abook.type.screenTitle.copy(
            fontSize = (maxWidth.value / 3f).sp, lineHeight = (maxWidth.value / 2f).sp,
        ))
    }
}

private object CoverTints {
    class Entry(val color: Color?)
    val values = android.util.LruCache<String, Entry>(32)
}

/** Dominant colour is sampled once off main for each cover reference, not each frame or player event. */
@Composable
fun rememberPlayerBackground(ref: CoverRef?): State<Color> {
    val colors = Abook.colors
    val covers = LocalPlayerCovers.current
    val tintKey = ref?.let { "${it.path}|${it.stamp}" }
    val dominant by produceState<Color?>(tintKey?.let { CoverTints.values.get(it)?.color }, ref) {
        val cached = tintKey?.let(CoverTints.values::get)
        value = if (cached != null) cached.color else if (ref == null) null else {
            val cacheKey = covers.key(ref.path, ref.stamp, 32)
            val image = covers.load(cacheKey, ref.path, 32, 32)
            withContext(Dispatchers.Default) {
                image?.asAndroidBitmap()?.let { bitmap ->
                    // Quantised histogram, no array proportional to image size. Weight saturated pixels over greys.
                    val bins = IntArray(512)
                    var best = 0
                    for (y in 0 until bitmap.height step maxOf(1, bitmap.height / 32)) {
                        for (x in 0 until bitmap.width step maxOf(1, bitmap.width / 32)) {
                            val c = bitmap.getPixel(x, y)
                            val r = (c shr 16) and 255; val g = (c shr 8) and 255; val b = c and 255
                            val bin = ((r shr 5) shl 6) or ((g shr 5) shl 3) or (b shr 5)
                            bins[bin] += 1 + (maxOf(r, g, b) - minOf(r, g, b)) / 32
                            if (bins[bin] > bins[best]) best = bin
                        }
                    }
                    Color(((best shr 6) * 32 + 16) / 255f, (((best shr 3) and 7) * 32 + 16) / 255f, ((best and 7) * 32 + 16) / 255f)
                }
            }
        }
        if (tintKey != null && cached == null) CoverTints.values.put(tintKey, CoverTints.Entry(value))
    }
    return animateColorAsState(dominant?.let { lerp(colors.bg, it, if (colors.dark) 0.12f else 0.06f) } ?: colors.bg,
        tween(MotionMs.SLOW), label = "cover-tint")
}

/** Every label replacement travels vertically through a clipped aperture. No default cross-fades. */
@Composable
fun RollingLabel(text: String, modifier: Modifier = Modifier, style: TextStyle = Abook.type.body) {
    AnimatedContent(
        targetState = text, modifier = modifier.clipToBounds(), label = "rolling-label",
        transitionSpec = {
            (slideInVertically(tween(MotionMs.MEDIUM)) { it } togetherWith
                slideOutVertically(tween(MotionMs.MEDIUM_OUT)) { -it }).using(SizeTransform(clip = true))
        },
    ) { value -> BasicText(value, style = style) }
}

/** Two four-point contours interpolate triangle -> pause bars. Path objects are reused in draw. */
@Composable
fun PlayMorph(
    playing: Boolean, onClick: () -> Unit,
    modifier: Modifier = Modifier, large: Boolean = true,
) {
    val colors = Abook.colors
    val view = LocalView.current
    val morph = animateFloatAsState(if (playing) 1f else 0f, tween(MotionMs.FAST), label = "play-path")
    val left = remember { Path() }
    val right = remember { Path() }
    val buttonSize = if (large) 72.dp else 44.dp
    Box(modifier.size(buttonSize).pressable {
        view.performHapticFeedback(android.view.HapticFeedbackConstants.CONTEXT_CLICK)
        onClick()
    }
        .semantics { contentDescription = if (playing) "Tạm dừng" else "Phát" }
        .drawBehind { drawCircle(colors.accent) }, contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(if (large) 32.dp else 24.dp)) {
            val p = morph.value
            val w = size.width; val h = size.height
            fun mix(a: Float, b: Float) = a + (b - a) * p
            left.reset()
            left.moveTo(w * 0.22f, h * mix(0.12f, 0.16f))
            left.lineTo(w * mix(0.5f, 0.43f), h * mix(0.28f, 0.16f))
            left.lineTo(w * mix(0.5f, 0.43f), h * mix(0.72f, 0.84f))
            left.lineTo(w * 0.22f, h * mix(0.88f, 0.84f)); left.close()
            right.reset()
            right.moveTo(w * mix(0.5f, 0.57f), h * mix(0.28f, 0.16f))
            right.lineTo(w * mix(0.88f, 0.78f), h * mix(0.5f, 0.16f))
            right.lineTo(w * mix(0.88f, 0.78f), h * mix(0.5f, 0.84f))
            right.lineTo(w * mix(0.5f, 0.57f), h * mix(0.72f, 0.84f)); right.close()
            val ink = colors.accentInk
            drawPath(left, ink); drawPath(right, ink)
        }
    }
}

@Composable
fun PlayerAction(label: String, glyph: String, onClick: () -> Unit, modifier: Modifier = Modifier) {
    Column(modifier.widthIn(min = 48.dp).pressable(onClick = onClick).padding(vertical = 8.dp)
        .semantics { contentDescription = label }, horizontalAlignment = Alignment.CenterHorizontally) {
        // Ô trên cùng một chiều cao (= ô icon 28 dp) dù là icon hay chữ ("1×", "12:30"): nhãn dưới của cả hàng nằm trên cùng một đường.
        Box(Modifier.height(28.dp), contentAlignment = Alignment.Center) {
            if (glyph == "◷" || glyph == "☷") PlayerGlyph(glyph)
            else RollingLabel(glyph, style = Abook.type.sectionTitle)
        }
        Spacer(Modifier.height(4.dp))
        RollingLabel(label, style = Abook.type.caption)
    }
}

/** Fixed vector geometry; no font fallback glyphs, per-frame Path/Stroke allocation or icon crossfades. */
@Composable
fun PlayerGlyph(glyph: String) {
    val color = Abook.colors.text
    val path = remember { Path() }
    val width = with(LocalDensity.current) { 1.8.dp.toPx() }
    val stroke = remember(width) { Stroke(width, cap = StrokeCap.Round, join = StrokeJoin.Round) }
    Box(Modifier.size(28.dp), contentAlignment = Alignment.Center) {
        Canvas(Modifier.fillMaxSize()) {
            val w = size.width; val h = size.height
            path.reset()
            when (glyph) {
                "⌄" -> {
                    path.moveTo(w * 0.25f, h * 0.38f); path.lineTo(w * 0.5f, h * 0.63f); path.lineTo(w * 0.75f, h * 0.38f)
                    drawPath(path, color, style = stroke)
                }
                "⋯" -> { for (i in 0..2) drawCircle(color, width, Offset(w * (0.25f + i * 0.25f), h / 2)) }
                "|‹", "›|" -> withTransform({ if (glyph == "›|") scale(-1f, 1f) }) {
                    path.moveTo(w * 0.7f, h * 0.25f); path.lineTo(w * 0.35f, h * 0.5f); path.lineTo(w * 0.7f, h * 0.75f); path.close()
                    drawPath(path, color)
                    drawLine(color, Offset(w * 0.25f, h * 0.25f), Offset(w * 0.25f, h * 0.75f), width, StrokeCap.Round)
                }
                "↶15", "15↷" -> withTransform({ if (glyph == "15↷") scale(-1f, 1f) }) {
                    drawArc(color, -90f, 300f, false, Offset(w * 0.15f, h * 0.12f), androidx.compose.ui.geometry.Size(w * 0.7f, h * 0.7f), style = stroke)
                    path.moveTo(w * 0.5f, h * 0.02f); path.lineTo(w * 0.37f, h * 0.12f); path.lineTo(w * 0.5f, h * 0.23f)
                    drawPath(path, color, style = stroke)
                }
                "◷" -> {
                    drawCircle(color, w * 0.34f, style = stroke)
                    path.moveTo(w * 0.5f, h * 0.28f); path.lineTo(w * 0.5f, h * 0.5f); path.lineTo(w * 0.66f, h * 0.56f)
                    drawPath(path, color, style = stroke)
                }
                "☷" -> {
                    for (i in 0..2) {
                        val y = h * (0.27f + i * 0.23f)
                        drawCircle(color, width * 0.65f, Offset(w * 0.2f, y))
                        drawLine(color, Offset(w * 0.38f, y), Offset(w * 0.8f, y), width, StrokeCap.Round)
                    }
                }
                "+", "−" -> {
                    drawLine(color, Offset(w * 0.22f, h / 2), Offset(w * 0.78f, h / 2), width, StrokeCap.Round)
                    if (glyph == "+") drawLine(color, Offset(w / 2, h * 0.22f), Offset(w / 2, h * 0.78f), width, StrokeCap.Round)
                }
            }
        }
        if (glyph == "↶15" || glyph == "15↷") BasicText("15", Modifier.padding(top = 2.dp),
            style = Abook.type.caption.copy(fontSize = 10.sp, lineHeight = 12.sp, fontWeight = FontWeight.Medium, color = color))
    }
}

/** Full-only parts begin their rise/scale at 40% of the shared transition, also on the way back. */
fun Modifier.playerReveal(progress: State<Float>): Modifier = graphicsLayer {
    val reveal = ((progress.value - 0.4f) / 0.6f).coerceIn(0f, 1f)
    translationY = (1f - reveal) * 32.dp.toPx()
    scaleX = 0.86f + reveal * 0.14f; scaleY = scaleX
    alpha = reveal
}
