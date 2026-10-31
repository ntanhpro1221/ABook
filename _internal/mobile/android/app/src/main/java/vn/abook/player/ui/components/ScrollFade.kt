package vn.abook.player.ui.components

import androidx.compose.foundation.gestures.ScrollableState
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithCache
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Paint
import androidx.compose.ui.graphics.drawscope.clipRect
import androidx.compose.ui.graphics.drawscope.drawIntoCanvas
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.Dp
import vn.abook.player.ui.theme.Dim
import kotlin.math.ceil
import kotlin.math.max
import kotlin.math.min

/** Bề cao mép mờ của mọi vùng cuộn; web dùng đúng số này (`SCROLL_FADE` ở ui/src/shared/scrollFade.ts). */
val ScrollFadeEdge: Dp = Dim.s24

/**
 * Mép mờ của vùng cuộn dọc (DESIGN.md §4.5: không gì cụt cứng): nội dung chạy dưới tiêu đề, tay nắm bảng trượt, thanh nút hay thanh phát thì mờ dần [edge]
 * thay vì bị cắt ngang. Chỉ mờ ở phía còn cuộn được - đầu danh sách không mờ mép trên, cuối danh sách không mờ mép dưới. Nhận mọi [ScrollableState]
 * (`LazyListState`, `LazyGridState`, `ScrollState`).
 *
 * Đặt TRƯỚC `verticalScroll(state)` trong chuỗi modifier (để mặt nạ theo khung nhìn, không theo nội dung). Vị trí cuộn chỉ đọc trong pha vẽ; khi không có gì
 * để cuộn thì không dựng lớp vẽ riêng. Máy dò `ScrollFadeRulesTest` bắt vùng cuộn nào quên nó.
 */
fun Modifier.fadeEdges(state: ScrollableState, edge: Dp = ScrollFadeEdge): Modifier = fade(state, edge, horizontal = false)

/**
 * Cùng mép mờ cho hàng cuộn NGANG (chip, tab): mờ ở đầu / cuối còn cuộn được, như `useRowFade` bên web. Đặt TRƯỚC `horizontalScroll(state)` trong chuỗi modifier.
 */
fun Modifier.fadeEdgesHorizontal(state: ScrollableState, edge: Dp = ScrollFadeEdge): Modifier = fade(state, edge, horizontal = true)

/**
 * Mép mờ không dùng lớp ngoài màn nguyên khung nhìn (trước đây `CompositingStrategy.Offscreen` + mặt nạ DstIn: một kết cấu GPU bằng cả vùng cuộn, ~7 MB cho lưới Thư viện,
 * mỗi vùng cuộn một cái - phần lớn bộ nhớ đồ hoạ của app, và mỗi khung phải đổi đích vẽ). Nội dung (một lớp riêng của nó, vẽ lại bằng `drawRenderNode` rẻ) được vẽ MỘT lần
 * cho phần giữa không mặt nạ, và một lần cho mỗi dải mép bằng lớp tạm chỉ cao đúng [edge]: dải đó nhân mặt nạ DstIn y như trước. Điểm ảnh ra giống hệt: dải và phần giữa
 * khớp nhau ở biên nguyên điểm ảnh, mặt nạ ngoài đoạn chuyển màu là đặc (đen) nên phần giữa không cần mặt nạ.
 */
private fun Modifier.fade(state: ScrollableState, edge: Dp, horizontal: Boolean): Modifier = drawWithCache {
    val length = if (horizontal) size.width else size.height
    val edgePx = min(edge.toPx(), length / 2f)
    val band = ceil(edgePx)
    val lower = max(length - band, band) // hai dải không bao giờ chồng nhau
    // Mặt nạ: trong suốt ở mép ngoài -> đặc sau edgePx; dải cuối là ảnh phản chiếu của dải đầu.
    val startMask = if (horizontal) Brush.horizontalGradient(0f to Color.Transparent, 1f to Color.Black, startX = 0f, endX = edgePx)
    else Brush.verticalGradient(0f to Color.Transparent, 1f to Color.Black, startY = 0f, endY = edgePx)
    val endMask = if (horizontal) Brush.horizontalGradient(0f to Color.Black, 1f to Color.Transparent, startX = length - edgePx, endX = length)
    else Brush.verticalGradient(0f to Color.Black, 1f to Color.Transparent, startY = length - edgePx, endY = length)
    val layerPaint = Paint()
    onDrawWithContent {
        val start = state.canScrollBackward
        val end = state.canScrollForward
        if ((!start && !end) || length <= 0f) {
            drawContent()
            return@onDrawWithContent
        }
        val from = if (start) band else 0f
        val to = if (end) lower else length
        if (horizontal) clipRect(from, 0f, to, size.height) { this@onDrawWithContent.drawContent() }
        else clipRect(0f, from, size.width, to) { this@onDrawWithContent.drawContent() }
        if (start) {
            val bounds = if (horizontal) Rect(0f, 0f, band, size.height) else Rect(0f, 0f, size.width, band)
            maskedBand(bounds, layerPaint, startMask) { this@onDrawWithContent.drawContent() }
        }
        if (end) {
            val bounds = if (horizontal) Rect(lower, 0f, length, size.height) else Rect(0f, lower, size.width, length)
            maskedBand(bounds, layerPaint, endMask) { this@onDrawWithContent.drawContent() }
        }
    }
}.graphicsLayer {}

/** Vẽ [content] trong [bounds] vào lớp tạm cỡ [bounds], rồi nhân mặt nạ [mask] (DstIn) - phần trong suốt của mặt nạ làm nội dung biến mất. */
private inline fun androidx.compose.ui.graphics.drawscope.DrawScope.maskedBand(
    bounds: Rect, paint: Paint, mask: Brush, crossinline content: androidx.compose.ui.graphics.drawscope.DrawScope.() -> Unit,
) {
    clipRect(bounds.left, bounds.top, bounds.right, bounds.bottom) {
        drawIntoCanvas { canvas -> canvas.saveLayer(bounds, paint) }
        content()
        drawRect(mask, topLeft = bounds.topLeft, size = bounds.size, blendMode = BlendMode.DstIn)
        drawIntoCanvas { canvas -> canvas.restore() }
    }
}
