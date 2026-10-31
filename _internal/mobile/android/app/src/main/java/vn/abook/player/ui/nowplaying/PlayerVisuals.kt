package vn.abook.player.ui.nowplaying

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.Animatable
import androidx.compose.ui.layout.Layout
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import vn.abook.player.ui.components.BasicText
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.unit.Density
import vn.abook.player.Playback
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.geometry.Size
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
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.Dp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import vn.abook.player.ui.components.ClockLabel
import vn.abook.player.ui.components.pressable
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.components.LucideIcon
import vn.abook.player.ui.components.LucidePaths
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.BeVietnamPro
import vn.abook.player.ui.components.GeneratedCover
import vn.abook.player.ui.theme.Dim
import vn.abook.player.ui.theme.MotionMs

private val LocalPlayerCovers = staticCompositionLocalOf { CoverLoader() }

@Composable
fun PlayerCoverProvider(covers: CoverLoader, content: @Composable () -> Unit) {
    CompositionLocalProvider(LocalPlayerCovers provides covers, content = content)
}

/** Decode width (px) of the player's cover: the final display slot of the window. */
@Composable
private fun playerCoverRequestPx(decodeSize: Dp? = null): Int {
    val density = LocalDensity.current
    val displaySize = decodeSize ?: minOf((LocalConfiguration.current.screenWidthDp - 40).dp, 320.dp)
    return with(density) { displaySize.roundToPx().coerceAtLeast(1) }
}

/**
 * Decodes the playing book's cover at the window's display size (and its tint sample) as soon as the track is known, off the main thread, so opening the window finds
 * both in the cache: the big cover is in the first frame and nothing is decoded while the window moves. Same keys as [PlayerCover] / [rememberPlayerBackground].
 */
@Composable
fun PrefetchPlayerCover(cover: kotlinx.coroutines.flow.Flow<CoverRef?>) {
    val covers = LocalPlayerCovers.current
    val requestPx = playerCoverRequestPx()
    LaunchedEffect(cover, covers, requestPx) {
        cover.collect { ref ->
            if (ref == null) return@collect
            covers.load(covers.key(ref.path, ref.stamp, requestPx), ref.path, requestPx, requestPx)
            covers.load(covers.key(ref.path, ref.stamp, 32), ref.path, 32, 32)
        }
    }
}

/** Cover always decoded at requested display size on IO; cache is the app's existing byte-bounded loader. No image: the same generated cover as the Library. */
@Composable
fun PlayerCover(ref: CoverRef?, title: String, modifier: Modifier = Modifier, decodeSize: Dp? = null) {
    val covers = LocalPlayerCovers.current
    // Decode at the final display-slot bound, never at intermediate shared-element sizes.
    val requestPx = playerCoverRequestPx(decodeSize)
    BoxWithConstraints(modifier.clip(RoundedCornerShape(Dim.radiusCover)).background(Abook.colors.bgSunken), contentAlignment = Alignment.Center) {
        if (ref == null) {
            // Tên đã có ngay dưới bìa: chữ trên bìa tự vẽ chỉ để nhìn, trình đọc màn hình không đọc hai lần.
            GeneratedCover(title, null, maxWidth, Modifier.fillMaxSize().clearAndSetSemantics {})
            return@BoxWithConstraints
        }
        val width = requestPx
        val height = requestPx
        val cacheKey = ref?.let { covers.key(it.path, it.stamp, width) }
        val bitmap by produceState<ImageBitmap?>(cacheKey?.let(covers::peek), cacheKey) {
            value = if (ref != null && cacheKey != null) covers.load(cacheKey, ref.path, width, height) else null
        }
        bitmap?.let { Image(it, title, Modifier.fillMaxSize(), contentScale = ContentScale.Crop) }
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

/** Nhãn đang chạy: chữ đang hiện, chữ đang đi ra (null khi đứng yên), tiến trình của chữ mới (1 = đã vào hẳn). */
@Stable
private class Roll(first: String) {
    var shown by mutableStateOf(first)
    var leaving by mutableStateOf<String?>(null)
    val progress = Animatable(1f)
}

/**
 * Every label replacement travels vertically through a clipped aperture (chữ mới trồi từ dưới 220 ms, chữ cũ đi lên 150 ms, khung đổi cỡ theo). No default cross-fades.
 * Không dùng AnimatedContent: mỗi nhãn tĩnh của Đang nghe (tên chương, tên sách, giờ, nhãn nút...) mang một AnimatedContent, ~0,8 ms dựng lần đầu mỗi cái trong trace
 * Perfetto (NATIVE_POLISH) và cả chục cái cùng lúc ở khung đầu của cửa sổ. Ở đây lúc đứng yên chỉ là một BasicText; hai chữ chỉ có trong lúc chạy,
 * toạ độ đọc trong pha dàn trang.
 */
@Composable
fun RollingLabel(text: String, modifier: Modifier = Modifier, style: TextStyle = Abook.type.body) {
    val roll = remember { Roll(text) }
    LaunchedEffect(text) {
        if (roll.shown == text) return@LaunchedEffect
        roll.leaving = roll.shown
        roll.shown = text
        roll.progress.snapTo(0f)
        roll.progress.animateTo(1f, tween(MotionMs.MEDIUM))
        roll.leaving = null
    }
    Layout(
        content = {
            BasicText(roll.shown, style = style)
            roll.leaving?.let { BasicText(it, style = style) }
        },
        modifier = modifier.clipToBounds(),
    ) { measurables, constraints ->
        val incoming = measurables[0].measure(constraints)
        val outgoing = measurables.getOrNull(1)?.measure(constraints)
        val p = roll.progress.value
        val width = if (outgoing == null) incoming.width else (outgoing.width + (incoming.width - outgoing.width) * p).toInt()
        val height = if (outgoing == null) incoming.height else (outgoing.height + (incoming.height - outgoing.height) * p).toInt()
        layout(width, height) {
            if (outgoing != null) {
                val out = (p * MotionMs.MEDIUM / MotionMs.MEDIUM_OUT).coerceAtMost(1f)
                outgoing.place(0, (-out * outgoing.height).toInt())
            }
            incoming.place(0, ((1f - p) * incoming.height).toInt())
        }
    }
}

/** Two four-point contours interpolate triangle -> pause bars. Path objects are reused in draw. */
@Composable
fun PlayMorph(
    playing: Boolean, onClick: () -> Unit,
    modifier: Modifier = Modifier, large: Boolean = true,
    /** Nhãn đọc màn hình; mặc định "Tạm dừng" / "Phát". Đang chờ âm thanh thì nói đang chờ gì ([PlayerText.toggleLabel]). */
    description: String? = null,
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
        .semantics { contentDescription = description ?: if (playing) "Tạm dừng" else "Phát" }
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

/** Biểu tượng của "Cửa sổ mini" (lucide picture-in-picture-2) trong [PlayerGlyph]. */
const val MINI_WINDOW_GLYPH = "⧉"

@Composable
fun PlayerAction(label: String, glyph: String, onClick: () -> Unit, modifier: Modifier = Modifier, clock: Boolean = false) {
    Column(modifier.widthIn(min = 48.dp).pressable(onClick = onClick).padding(vertical = 8.dp)
        .semantics { contentDescription = label }, horizontalAlignment = Alignment.CenterHorizontally) {
        // Ô trên cùng một chiều cao (= ô icon 28 dp) dù là icon hay chữ ("1×", "12:30"): nhãn dưới của cả hàng nằm trên cùng một đường.
        Box(Modifier.height(28.dp), contentAlignment = Alignment.Center) {
            if (glyph == "◷" || glyph == "☷" || glyph == MINI_WINDOW_GLYPH) PlayerGlyph(glyph)
            else if (clock) ClockLabel(glyph, style = Abook.type.sectionTitle)
            else RollingLabel(glyph, style = Abook.type.sectionTitle)
        }
        Spacer(Modifier.height(4.dp))
        RollingLabel(label, style = Abook.type.caption)
    }
}

/**
 * Biểu tượng của trình phát: hình lucide giống bản web (PlayerViews.tsx: ChevronDown, MoreHorizontal, SkipBack/SkipForward, Moon, ListOrdered,
 * Plus/Minus) trong ô 24 giữa nút 28; riêng lùi / tới 15 giây là hình riêng của web (drawSkip). Đường dịch một lần, không cấp phát khi vẽ.
 */
@Composable
fun PlayerGlyph(glyph: String) {
    val color = Abook.colors.text
    val path = remember { Path() }
    val skipNumber = if (glyph == "↶15" || glyph == "15↷") rememberSkipNumber(color) else null
    val data = when (glyph) {
        "⌄" -> LucidePaths.CHEVRON_DOWN
        "⋯" -> LucidePaths.ELLIPSIS
        "|‹" -> LucidePaths.SKIP_BACK
        "›|" -> LucidePaths.SKIP_FORWARD
        "◷" -> LucidePaths.MOON
        "☷" -> LucidePaths.LIST_ORDERED
        "⧉" -> LucidePaths.PICTURE_IN_PICTURE_2
        "+" -> LucidePaths.PLUS
        "−" -> LucidePaths.MINUS
        else -> null
    }
    Box(Modifier.size(28.dp), contentAlignment = Alignment.Center) {
        if (data != null) LucideIcon(data, color, size = 24.dp)
        else Canvas(Modifier.fillMaxSize()) { drawSkip(glyph == "15↷", color, path, skipNumber) }
    }
}

/**
 * Số "15" của nút lùi / tới, đo một lần (không đo lại mỗi khung). Cỡ theo dp chứ không theo sp: đây là hình vẽ, phóng chữ hệ thống không được làm số
 * chạm vào cung.
 */
@Composable
private fun rememberSkipNumber(color: Color): TextLayoutResult {
    val measurer = rememberTextMeasurer(cacheSize = 1)
    val density = LocalDensity.current
    return remember(color, density) { skipNumberLayout(measurer, density, color) }
}

/** Số của nút lùi / tới đã đo; cửa sổ nhỏ PiP (ui/pip) vẽ nút hệ thống ra ảnh bằng chính số này, nên đo ở hàm dùng chung chứ không ở composable. */
internal fun skipNumberLayout(measurer: TextMeasurer, density: Density, color: Color): TextLayoutResult {
    val style = with(density) {
        TextStyle(
            fontFamily = BeVietnamPro, fontWeight = FontWeight.SemiBold, fontSize = SKIP_NUMBER_SIZE.dp.toSp(),
            letterSpacing = (-0.2).dp.toSp(), fontFeatureSettings = "tnum", color = color,
        )
    }
    return measurer.measure(Playback.SKIP_SECONDS.toString(), style)
}

/**
 * Nút lùi / tới 15 giây - CÙNG hình với bản web (PlayerViews.tsx `skipIcon`, ô 24): cung nông ở trên (bán kính 8,5 qua (4,05; 9) và (19,95; 9)), mũi tên ở
 * đầu cung, số 15 to ở dưới. Chủ sách 24-10 và 26-10: vòng gần kín với số nhét bên trong "xấu xí" - số không bao giờ chạm nét; khe đo bằng điểm ảnh
 * trong SkipGlyphTest. Ô 24 đặt giữa ô 28 của nút.
 */
internal fun DrawScope.drawSkip(forward: Boolean, color: Color, path: Path, number: TextLayoutResult?) {
    val u = 24.dp.toPx() / 24f
    withTransform({
        translate((size.width - 24f * u) / 2f, (size.height - 24f * u) / 2f)
        if (!forward) scale(-1f, 1f, pivot = Offset(12f * u, 12f * u))
    }) {
        val stroke = Stroke(1.9f * u, cap = StrokeCap.Round, join = StrokeJoin.Round)
        drawArc(color, 200.73f, 138.54f, false, Offset(3.5f * u, 3.508f * u), Size(17f * u, 17f * u), style = stroke)
        path.reset()
        path.moveTo(20.94f * u, 6.17f * u); path.lineTo(19.95f * u, 9f * u); path.lineTo(17.34f * u, 7.53f * u)
        drawPath(path, color, style = stroke)
    }
    if (number == null) return
    // Chân số ở y = 22 (ô 24): mực số từ khoảng y 11,8 - cách đáy nét cung (y 9,95) gần 2 đơn vị.
    val left = (size.width - number.size.width) / 2f
    val top = (size.height - 24f * u) / 2f + SKIP_NUMBER_BASELINE * u - number.firstBaseline
    drawText(number, topLeft = Offset(left, top))
}

private const val SKIP_NUMBER_SIZE = 14.5f
private const val SKIP_NUMBER_BASELINE = 22f

/** Full-only parts begin their rise/scale at 40% of the shared transition, also on the way back. */
fun Modifier.playerReveal(progress: State<Float>): Modifier = graphicsLayer {
    val reveal = ((progress.value - 0.4f) / 0.6f).coerceIn(0f, 1f)
    translationY = (1f - reveal) * 32.dp.toPx()
    scaleX = 0.86f + reveal * 0.14f; scaleY = scaleX
    alpha = reveal
}
