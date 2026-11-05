package vn.abook.player.ui

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.junit4.ComposeContentTestRule
import androidx.compose.ui.test.onRoot
import vn.abook.player.ui.components.GestureBar
import kotlin.math.roundToInt

/**
 * Máy dò "hộp chạm nhỏ hơn chữ vẽ" (lỗi điện thoại thật 05-11: "Thay bằng file này" nằm sát đáy máy cử chỉ ẩn vạch - chữ vẽ ở 36 dp trên mép, hộp chạm bị cắt còn nửa, bấm trúng là hệ thống nuốt).
 * Với MỌI nút bấm được trong cây ngữ nghĩa CHƯA gộp:
 *  - cao >= 48 dp (kích thước thật, không cắt theo cha);
 *  - mọi chữ con nằm gọn trong hộp chạm (sai số 1 px);
 *  - hộp chạm nằm trên thanh điều hướng: đáy không quá `rootHeight - max(inset đáy, GestureBar)`. Robolectric không có thanh điều hướng (inset 0) = đúng ca ColorOS giấu vạch cử chỉ.
 * Trả về danh sách vi phạm (rỗng = sạch) và số nút đã soát.
 */
class TouchReport(val checked: Int, val problems: List<String>)

fun ComposeContentTestRule.touchBoxProblems(screen: String, gestureBarDp: Float = GestureBar.value, minDp: Float = 48f, skipTags: Set<String> = emptySet()): TouchReport {
    val root = onRoot(useUnmergedTree = true).fetchSemanticsNode()
    val density = density.density
    val rootHeight = root.size.height
    val problems = ArrayList<String>()
    var checked = 0

    fun label(node: SemanticsNode): String {
        val tag = node.config.getOrNull(SemanticsProperties.TestTag)
        val text = textsOf(node).firstOrNull()
        val description = node.config.getOrNull(SemanticsProperties.ContentDescription)?.firstOrNull()
        return listOfNotNull(tag, text?.let { "\"$it\"" }, description?.let { "[$it]" }).joinToString(" ").ifEmpty { "(nút không tên)" }
    }

    fun visit(node: SemanticsNode) {
        val tag = node.config.getOrNull(SemanticsProperties.TestTag)
        if (node.config.contains(SemanticsActions.OnClick) && tag !in skipTags) {
            checked++
            val top = node.positionInRoot.y
            val bottom = top + node.size.height
            val left = node.positionInRoot.x
            val right = left + node.size.width
            val name = "$screen: ${label(node)}"
            val minPx = minDp * density
            if (node.size.height + 0.5f < minPx) problems += "$name cao ${(node.size.height / density).roundToInt()} dp (< ${minDp.roundToInt()} dp)"
            val limit = rootHeight - gestureBarDp * density
            if (bottom > limit + 1f) problems += "$name: đáy hộp chạm ${(bottom / density).roundToInt()} dp, thấp hơn mép trên vạch cử chỉ ${(limit / density).roundToInt()} dp"
            for (inner in descendants(node)) {
                if (inner.config.getOrNull(SemanticsProperties.Text) == null) continue
                val t = inner.positionInRoot.y
                val b = t + inner.size.height
                val l = inner.positionInRoot.x
                val r = l + inner.size.width
                if (t < top - 1f || b > bottom + 1f || l < left - 1f || r > right + 1f) {
                    problems += "$name: chữ \"${textsOf(inner).firstOrNull()}\" [$l,$t][$r,$b] ra ngoài hộp chạm [$left,$top][$right,$bottom]"
                }
            }
        }
        node.children.forEach(::visit)
    }
    visit(root)
    return TouchReport(checked, problems)
}

private fun textsOf(node: SemanticsNode): List<String> =
    (node.config.getOrNull(SemanticsProperties.Text)?.map { it.text } ?: emptyList()) + node.children.flatMap(::textsOf)

private fun descendants(node: SemanticsNode): List<SemanticsNode> = node.children.flatMap { listOf(it) + descendants(it) }
