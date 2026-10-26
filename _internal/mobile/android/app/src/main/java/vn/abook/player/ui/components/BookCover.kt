package vn.abook.player.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.foundation.text.TextAutoSize
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import vn.abook.player.ui.data.CoverArt
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.CoverRef
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.BeVietnamPro
import vn.abook.player.ui.theme.Dim
import kotlin.math.max

private val CoverShape = RoundedCornerShape(Dim.radiusCover)
private val SmallShape = RoundedCornerShape(Dim.radiusControl)

/**
 * Bìa 2:3 bo 12 (bo 8 ở cỡ nhỏ): ảnh thật nạp ngoài luồng chính và vẽ trong pha vẽ, hoặc - sách không có ảnh - bìa tự vẽ như shared/cover.ts
 * (nền chéo, vòng cung mờ từ góc dưới, tên sách, nhãn tập). `small`: chỉ nhãn ngắn ("16" hay hai chữ cái đầu), cho thanh phát nhỏ và hàng danh sách.
 * `width` là bề rộng ô để chọn cỡ giải mã và cỡ chữ; chiều cao theo 2:3.
 */
@Composable
fun BookCover(
    cover: CoverRef?,
    title: String,
    part: Int?,
    covers: CoverLoader,
    width: Dp,
    modifier: Modifier = Modifier,
    small: Boolean = false,
) {
    val density = LocalDensity.current
    val widthPx = with(density) { width.roundToPx() }
    val heightPx = widthPx * 3 / 2
    val path = cover?.path
    val stamp = cover?.stamp ?: 0L
    val key = remember(path, stamp, widthPx) { path?.let { covers.key(it, stamp, widthPx) } }
    val image = remember(key) { mutableStateOf(key?.let(covers::peek)) }
    if (key != null && path != null && image.value == null) {
        LaunchedEffect(key) { image.value = covers.load(key, path, widthPx, heightPx) }
    }
    val shape = if (small) SmallShape else CoverShape
    val sunken = Abook.colors.bgSunken
    if (path != null) {
        Box(modifier.aspectRatio(2f / 3f).clip(shape).background(sunken).drawBehind { image.value?.let { drawCover(it) } })
        return
    }
    val style = remember(title) { CoverArt.style(title) }
    val from = Color(style.from)
    val to = Color(style.to)
    val ink = Color(style.ink)
    Box(
        modifier.aspectRatio(2f / 3f).clip(shape).drawBehind {
            drawRect(Brush.linearGradient(listOf(from, to), start = Offset.Zero, end = Offset(size.width * 0.42f, size.height)))
            val center = Offset(if (style.arcsFromRight) size.width else 0f, size.height)
            for ((index, radius) in ARCS.withIndex()) {
                drawCircle(ink.copy(alpha = 0.09f + index * 0.025f), radius * size.height, center, style = Stroke(width = 1.dp.toPx()))
            }
        },
    ) {
        if (small) {
            val label = remember(title, part) { CoverArt.label(title, part) }
            BookInitials(label, ink, width, Modifier.align(Alignment.Center))
        } else {
            PlaceholderText(title, part, ink, width)
        }
    }
}

private val ARCS = floatArrayOf(0.28f, 0.46f, 0.64f, 0.82f, 1.0f)

@Composable
private fun BookInitials(label: String, ink: Color, width: Dp, modifier: Modifier) {
    val density = LocalDensity.current
    val size = with(density) { (width.value * 0.34f).dp.toSp() }
    BasicText(label, modifier, style = TextStyle(fontFamily = BeVietnamPro, fontWeight = FontWeight.Bold, fontSize = size, color = ink))
}

@Composable
private fun PlaceholderText(title: String, part: Int?, ink: Color, width: Dp) {
    val density = LocalDensity.current
    val (main, sub) = remember(title, part) { CoverArt.splitTitle(title, part) }
    val titleSize = with(density) { (width.value * 0.115f).dp.toSp() }
    val subSize = with(density) { (width.value * 0.075f).dp.toSp() }
    val pad = (width.value * 0.08f).dp
    // Tên chiếm phần trên, nhãn tập nằm riêng ở đáy: tên không bao giờ chạy xuống dưới nhãn hay quá mép bìa.
    Column(Modifier.fillMaxSize().padding(pad)) {
        BasicText(
            main,
            style = TextStyle(fontFamily = BeVietnamPro, fontWeight = FontWeight.Bold, fontSize = titleSize, lineHeight = 1.18.em, color = Color.White),
            // Tên dài thì thu cỡ chữ cho vừa phần còn lại của bìa chứ không cắt (luật: không bao giờ cắt chữ của người dùng).
            autoSize = TextAutoSize.StepBased(minFontSize = 2.sp, maxFontSize = titleSize, stepSize = 0.25.sp),
            modifier = Modifier.weight(1f).fillMaxWidth().testTag("cover_title"),
        )
        if (sub.isNotEmpty()) {
            Spacer(Modifier.height(pad / 2))
            BasicText(
                sub.uppercase(),
                style = TextStyle(fontFamily = BeVietnamPro, fontWeight = FontWeight.Medium, fontSize = subSize, color = ink),
                softWrap = false,
                autoSize = TextAutoSize.StepBased(minFontSize = 2.sp, maxFontSize = subSize, stepSize = 0.25.sp),
                modifier = Modifier.background(Color.Black.copy(alpha = 0.28f)).padding(horizontal = 4.dp, vertical = 2.dp).testTag("cover_part"),
            )
        }
    }
}

/** Vẽ ảnh phủ kín ô, cắt giữa nếu tỉ lệ khác (không cấp phát: IntOffset / IntSize là giá trị). */
private fun DrawScope.drawCover(image: ImageBitmap) {
    val dw = size.width.toInt()
    val dh = size.height.toInt()
    if (dw <= 0 || dh <= 0) return
    val scale = max(dw.toFloat() / image.width, dh.toFloat() / image.height)
    val sw = (dw / scale).toInt().coerceIn(1, image.width)
    val sh = (dh / scale).toInt().coerceIn(1, image.height)
    drawImage(
        image,
        srcOffset = IntOffset((image.width - sw) / 2, (image.height - sh) / 2),
        srcSize = IntSize(sw, sh),
        dstSize = IntSize(dw, dh),
        filterQuality = FilterQuality.Low,
    )
}
