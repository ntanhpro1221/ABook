package vn.abook.player.ui.nowplaying

import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.text.TextLayoutResult
import kotlin.math.abs
import kotlin.math.hypot
import kotlin.math.min

/** Một dòng chữ cần tô, theo px trong khung của đoạn. */
internal data class InkLine(val left: Float, val top: Float, val right: Float, val bottom: Float)

/** Một góc của viền đã bo: đường thẳng tới ([fromX], [fromY]), cong qua đỉnh ([cornerX], [cornerY]) tới ([toX], [toY]). */
internal data class InkCorner(
    val fromX: Float, val fromY: Float,
    val cornerX: Float, val cornerY: Float,
    val toX: Float, val toY: Float,
)

/**
 * Hình tô chữ trên điện thoại: một khối liền bo góc thay vì mỗi dòng một hộp vuông (`getPathForRange`, `SpanStyle.background` đều cho góc vuông). Bán kính là
 * `Dim.radiusControl`, cùng `--radius-control` của web và `Theme.radiusControl` của Qt.
 */
internal object ReadInk {
    /** Đi theo chiều kim đồng hồ quanh các dòng liền nhau; nơi các dòng lệch nhau là một bậc, có cả góc lồi lẫn góc lõm. Thuần số để test được trên JVM. */
    fun outline(lines: List<InkLine>, radius: Float): List<InkCorner> {
        val solid = lines.filter { it.right > it.left && it.bottom > it.top }
        if (solid.isEmpty()) return emptyList()
        val points = ArrayList<Pair<Float, Float>>(solid.size * 4)
        points += solid.first().left to solid.first().top
        for ((index, line) in solid.withIndex()) {
            points += line.right to line.top
            points += line.right to (solid.getOrNull(index + 1)?.top ?: line.bottom)
        }
        points += solid.last().left to solid.last().bottom
        for (index in solid.lastIndex downTo 1) {
            points += solid[index].left to solid[index].top
            points += solid[index - 1].left to solid[index].top
        }
        val vertices = simplify(points)
        return vertices.indices.map { index ->
            val (x, y) = vertices[index]
            val (px, py) = vertices[(index + vertices.size - 1) % vertices.size]
            val (nx, ny) = vertices[(index + 1) % vertices.size]
            val before = hypot(px - x, py - y)
            val after = hypot(nx - x, ny - y)
            val r = min(radius, min(before, after) / 2f)
            InkCorner(x + (px - x) / before * r, y + (py - y) / before * r, x, y, x + (nx - x) / after * r, y + (ny - y) / after * r)
        }
    }

    /** Bỏ điểm trùng và điểm nằm giữa cạnh thẳng: dòng cùng lề không tạo góc. */
    private fun simplify(points: List<Pair<Float, Float>>): List<Pair<Float, Float>> {
        val distinct = ArrayList<Pair<Float, Float>>(points.size)
        for (point in points) if (distinct.lastOrNull() != point) distinct += point
        if (distinct.size > 1 && distinct.first() == distinct.last()) distinct.removeAt(distinct.lastIndex)
        return distinct.indices.filter { index ->
            val (x, y) = distinct[index]
            val (px, py) = distinct[(index + distinct.size - 1) % distinct.size]
            val (nx, ny) = distinct[(index + 1) % distinct.size]
            !((abs(px - x) < EPSILON && abs(nx - x) < EPSILON) || (abs(py - y) < EPSILON && abs(ny - y) < EPSILON))
        }.map { distinct[it] }
    }

    fun path(lines: List<InkLine>, radius: Float): Path {
        val path = Path()
        val corners = outline(lines, radius)
        val last = corners.lastOrNull() ?: return path
        path.moveTo(last.toX, last.toY)
        for (corner in corners) {
            path.lineTo(corner.fromX, corner.fromY)
            path.quadraticTo(corner.cornerX, corner.cornerY, corner.toX, corner.toY)
        }
        path.close()
        return path
    }

    /** Các dòng của cả đoạn chữ, thở [pad] px hai bên (0,2em như `.read-along-active` của web). */
    fun paragraphLines(layout: TextLayoutResult, pad: Float): List<InkLine> = List(layout.lineCount) { line ->
        InkLine(layout.getLineLeft(line) - pad, layout.getLineTop(line), layout.getLineRight(line) + pad, layout.getLineBottom(line))
    }

    /** Mảnh của khoảng chữ [from, until) trên từng dòng nó đi qua (một chữ quá dài có thể gãy dòng). */
    fun rangeRects(layout: TextLayoutResult, from: Int, until: Int, padX: Float, insetY: Float): List<Rect> {
        val length = layout.layoutInput.text.length
        if (from < 0 || until > length || from >= until) return emptyList()
        val first = layout.getLineForOffset(from)
        val last = layout.getLineForOffset(until - 1)
        return (first..last).map { line ->
            val start = maxOf(from, layout.getLineStart(line))
            val end = minOf(until, layout.getLineEnd(line))
            val left = layout.getBoundingBox(start).left
            val right = layout.getBoundingBox((end - 1).coerceAtLeast(start)).right
            Rect(left - padX, layout.getLineTop(line) + insetY, right + padX, layout.getLineBottom(line) - insetY)
        }
    }

    private const val EPSILON = 0.01f
}

/** Tô các mảnh chữ bo góc; không cấp phát đối tượng nào ngoài lời gọi vẽ. */
internal fun DrawScope.drawInkRects(rects: List<Rect>, color: Color, radius: Float) {
    val corner = CornerRadius(radius)
    for (index in rects.indices) {
        val rect = rects[index]
        drawRoundRect(color, Offset(rect.left, rect.top), Size(rect.width, rect.height), corner)
    }
}
