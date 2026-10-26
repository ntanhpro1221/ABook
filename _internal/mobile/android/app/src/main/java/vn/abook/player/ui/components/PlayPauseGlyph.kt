package vn.abook.player.ui.components

import androidx.compose.animation.core.Animatable
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.Dp
import vn.abook.player.ui.motion.Motion

/**
 * Hình học nút phát <-> dừng trên lưới 24: mỗi hình là HAI tứ giác cùng thứ tự đỉnh. t = 0: tam giác phát (chia đôi theo chiều dọc); t = 1: hai thanh dừng.
 * Biến hình là nội suy tuyến tính từng đỉnh - nét vẽ chuyển động, không mờ chéo hai biểu tượng.
 */
object PlayPauseGeometry {
    const val GRID = 24f
    const val POINTS = 16

    // Đường tâm nét; vẽ thêm nét 2 đơn vị góc tròn nên mực = đúng lucide Play / Pause của bản web: tam giác x 5..21, hai thanh 5..10 và 14..19
    // (khe 4), cao 3..21. Bản cũ hai thanh chỉ cách nhau ~0,6 đơn vị - nhìn như một khối.
    private val play = floatArrayOf(
        6f, 4f, 13f, 8f, 13f, 16f, 6f, 20f,
        13f, 8f, 20f, 12f, 20f, 12f, 13f, 16f,
    )
    private val pause = floatArrayOf(
        6f, 4f, 9f, 4f, 9f, 20f, 6f, 20f,
        15f, 4f, 18f, 4f, 18f, 20f, 15f, 20f,
    )

    /** Ghi 16 số (x, y của 8 đỉnh: tứ giác trái rồi tứ giác phải) ở tiến trình `t` (0..1) vào `out`. */
    fun points(t: Float, out: FloatArray): FloatArray {
        val k = t.coerceIn(0f, 1f)
        for (i in 0 until POINTS) out[i] = play[i] + (pause[i] - play[i]) * k
        return out
    }
}

/** Nút phát / dừng vẽ tay: đổi `playing` thì biến hình trong 120 ms. Tiến trình đọc trong pha vẽ. */
@Composable
fun PlayPauseGlyph(playing: Boolean, color: Color, size: Dp, modifier: Modifier = Modifier) {
    val morph = remember { Animatable(if (playing) 1f else 0f) }
    LaunchedEffect(playing) { morph.animateTo(if (playing) 1f else 0f, Motion.GlyphMorph) }
    val points = remember { FloatArray(PlayPauseGeometry.POINTS) }
    val path = remember { Path() }
    Canvas(modifier.size(size)) { drawPlayPause(morph.value, color, points, path) }
}

/** Hình nút phát <-> dừng ở tiến trình `t` trong ô vuông của DrawScope; `points` và `path` là đồ dùng lại của nơi gọi (không cấp phát khi vẽ). Cửa sổ nhỏ PiP vẽ nút hệ thống bằng cùng hàm này. */
internal fun DrawScope.drawPlayPause(t: Float, color: Color, points: FloatArray, path: Path) {
    val unit = size.width / PlayPauseGeometry.GRID
    PlayPauseGeometry.points(t, points)
    val round = Stroke(width = 2f * unit, join = StrokeJoin.Round)
    for (shape in 0..1) {
        val at = shape * 8
        path.reset()
        path.moveTo(points[at] * unit, points[at + 1] * unit)
        for (corner in 1..3) path.lineTo(points[at + corner * 2] * unit, points[at + corner * 2 + 1] * unit)
        path.close()
        drawPath(path, color, style = Fill)
        drawPath(path, color, style = round)
    }
}
