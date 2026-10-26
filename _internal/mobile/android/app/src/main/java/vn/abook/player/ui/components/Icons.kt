package vn.abook.player.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/* Biểu tượng vẽ tay trên lưới 24 (không thư viện biểu tượng): nét 2 dp, đầu tròn. */

private fun Modifier.icon(size: Dp) = size(size)

@Composable
fun PlusIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val c = this.size.width / 2
        val r = this.size.width * 0.38f
        drawLine(color, Offset(c - r, c), Offset(c + r, c), w, StrokeCap.Round)
        drawLine(color, Offset(c, c - r), Offset(c, c + r), w, StrokeCap.Round)
    }
}

@Composable
fun SearchIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 22.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        drawCircle(color, radius = s * 0.30f, center = Offset(s * 0.43f, s * 0.43f), style = Stroke(w))
        drawLine(color, Offset(s * 0.66f, s * 0.66f), Offset(s * 0.88f, s * 0.88f), w, StrokeCap.Round)
    }
}

@Composable
fun CloseIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        drawLine(color, Offset(s * 0.22f, s * 0.22f), Offset(s * 0.78f, s * 0.78f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.78f, s * 0.22f), Offset(s * 0.22f, s * 0.78f), w, StrokeCap.Round)
    }
}

/** Xếp theo: ba vạch ngắn dần. */
@Composable
fun SortIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 22.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        drawLine(color, Offset(s * 0.18f, s * 0.28f), Offset(s * 0.82f, s * 0.28f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.18f, s * 0.50f), Offset(s * 0.64f, s * 0.50f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.18f, s * 0.72f), Offset(s * 0.46f, s * 0.72f), w, StrokeCap.Round)
    }
}

/** Dấu chọn ở đầu dòng menu. */
@Composable
fun CheckIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 18.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        drawLine(color, Offset(s * 0.18f, s * 0.54f), Offset(s * 0.42f, s * 0.76f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.42f, s * 0.76f), Offset(s * 0.84f, s * 0.26f), w, StrokeCap.Round)
    }
}

/** Dấu nguồn của sách ở máy khác: màn hình nhỏ có chân đế. */
@Composable
fun RemoteIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 14.dp) {
    Canvas(modifier.icon(size)) {
        val w = 1.5.dp.toPx()
        val s = this.size.width
        drawRoundRect(color, Offset(s * 0.1f, s * 0.14f), Size(s * 0.8f, s * 0.56f), CornerRadius(s * 0.1f), Stroke(w))
        drawLine(color, Offset(s * 0.5f, s * 0.7f), Offset(s * 0.5f, s * 0.86f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.3f, s * 0.88f), Offset(s * 0.7f, s * 0.88f), w, StrokeCap.Round)
    }
}
