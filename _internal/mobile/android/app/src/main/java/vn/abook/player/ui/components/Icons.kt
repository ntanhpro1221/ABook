package vn.abook.player.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalDensity
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

/** Nét 2 dp đầu tròn, dựng một lần cho mỗi biểu tượng (không cấp phát trong pha vẽ). */
@Composable
private fun rememberStroke(width: Dp = 2.dp): Stroke {
    val px = with(LocalDensity.current) { width.toPx() }
    return remember(px) { Stroke(width = px, cap = StrokeCap.Round) }
}

/** "Thêm" (menu "…"): ba chấm ngang. */
@Composable
fun MoreIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 22.dp) {
    Canvas(modifier.icon(size)) {
        val s = this.size.width
        val r = s * 0.085f
        for (i in 0..2) drawCircle(color, r, Offset(s * (0.2f + 0.3f * i), s * 0.5f))
    }
}

/** "Từ đầu": vòng cung ngược chiều kim đồng hồ, mũi tên ở đầu trên trái. */
@Composable
fun RestartIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 22.dp) {
    val stroke = rememberStroke()
    Canvas(modifier.icon(size)) {
        val s = this.size.width
        val w = stroke.width
        drawArc(color, 200f, 290f, useCenter = false, topLeft = Offset(s * 0.18f, s * 0.18f), size = Size(s * 0.64f, s * 0.64f), style = stroke)
        // Mũi tên ở đầu cung (góc 200°, bên trái hơi dưới tâm): hai nét.
        val tip = Offset(s * 0.2f, s * 0.39f)
        drawLine(color, tip, Offset(s * 0.16f, s * 0.16f), w, StrokeCap.Round)
        drawLine(color, tip, Offset(s * 0.42f, s * 0.36f), w, StrokeCap.Round)
    }
}

/** Chương chưa có audio: vòng nét đứt. */
@Composable
fun DashedCircleIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 18.dp) {
    val stroke = rememberStroke(1.5.dp)
    Canvas(modifier.icon(size)) {
        val s = this.size.width
        val box = Size(s * 0.72f, s * 0.72f)
        val at = Offset(s * 0.14f, s * 0.14f)
        for (i in 0 until 8) drawArc(color, i * 45f + 8f, 26f, useCenter = false, topLeft = at, size = box, style = stroke)
    }
}

/** "Sửa thông tin": bút chì chéo. */
@Composable
fun PencilIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        drawLine(color, Offset(s * 0.2f, s * 0.8f), Offset(s * 0.74f, s * 0.26f), w * 2.2f, StrokeCap.Round)
        drawLine(color, Offset(s * 0.14f, s * 0.86f), Offset(s * 0.3f, s * 0.86f), w, StrokeCap.Round)
    }
}

/** "Chia sẻ": ba nút nối hai nét. */
@Composable
fun ShareIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        val a = Offset(s * 0.72f, s * 0.2f)
        val b = Offset(s * 0.28f, s * 0.5f)
        val c = Offset(s * 0.72f, s * 0.8f)
        drawLine(color, a, b, w, StrokeCap.Round)
        drawLine(color, b, c, w, StrokeCap.Round)
        drawCircle(color, s * 0.12f, a)
        drawCircle(color, s * 0.12f, b)
        drawCircle(color, s * 0.12f, c)
    }
}

/** "Xoá khỏi máy": thùng rác. */
@Composable
fun TrashIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    val stroke = rememberStroke()
    Canvas(modifier.icon(size)) {
        val w = stroke.width
        val s = this.size.width
        drawLine(color, Offset(s * 0.16f, s * 0.26f), Offset(s * 0.84f, s * 0.26f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.4f, s * 0.14f), Offset(s * 0.6f, s * 0.14f), w, StrokeCap.Round)
        drawRoundRect(color, Offset(s * 0.26f, s * 0.26f), Size(s * 0.48f, s * 0.6f), CornerRadius(s * 0.06f), style = stroke)
    }
}

/** "Đọc theo": cuốn sách mở. */
@Composable
fun BookOpenIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    val stroke = rememberStroke()
    Canvas(modifier.icon(size)) {
        val w = stroke.width
        val s = this.size.width
        drawRoundRect(color, Offset(s * 0.1f, s * 0.22f), Size(s * 0.4f, s * 0.58f), CornerRadius(s * 0.05f), style = stroke)
        drawRoundRect(color, Offset(s * 0.5f, s * 0.22f), Size(s * 0.4f, s * 0.58f), CornerRadius(s * 0.05f), style = stroke)
        drawLine(color, Offset(s * 0.5f, s * 0.22f), Offset(s * 0.5f, s * 0.8f), w, StrokeCap.Round)
    }
}

/** "Xuất": mũi tên xuống trên một vạch đáy. */
@Composable
fun ExportIcon(color: Color, modifier: Modifier = Modifier, size: Dp = 20.dp) {
    Canvas(modifier.icon(size)) {
        val w = 2.dp.toPx()
        val s = this.size.width
        drawLine(color, Offset(s * 0.5f, s * 0.14f), Offset(s * 0.5f, s * 0.64f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.3f, s * 0.46f), Offset(s * 0.5f, s * 0.66f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.7f, s * 0.46f), Offset(s * 0.5f, s * 0.66f), w, StrokeCap.Round)
        drawLine(color, Offset(s * 0.18f, s * 0.86f), Offset(s * 0.82f, s * 0.86f), w, StrokeCap.Round)
    }
}
