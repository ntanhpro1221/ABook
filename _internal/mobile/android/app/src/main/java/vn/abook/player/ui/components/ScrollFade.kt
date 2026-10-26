package vn.abook.player.ui.components

import androidx.compose.foundation.gestures.ScrollableState
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.unit.Dp
import vn.abook.player.ui.theme.Dim

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
fun Modifier.fadeEdges(state: ScrollableState, edge: Dp = ScrollFadeEdge): Modifier = graphicsLayer {
    compositingStrategy = if (state.canScrollBackward || state.canScrollForward) CompositingStrategy.Offscreen else CompositingStrategy.Auto
}.drawWithContent {
    drawContent()
    val top = state.canScrollBackward
    val bottom = state.canScrollForward
    if (!top && !bottom) return@drawWithContent
    val fraction = (edge.toPx() / size.height).coerceIn(0f, 0.5f)
    drawRect(
        Brush.verticalGradient(
            0f to (if (top) Color.Transparent else Color.Black), fraction to Color.Black,
            1f - fraction to Color.Black, 1f to (if (bottom) Color.Transparent else Color.Black),
        ),
        blendMode = BlendMode.DstIn,
    )
}
