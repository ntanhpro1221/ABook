package vn.abook.player.ui

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import androidx.compose.ui.text.TextLayoutResult
import org.junit.Assert.assertTrue

/**
 * Máy dò dùng chung cho test cỡ chữ lớn (fontScale 1.3): mọi chữ đang vẽ trên màn phải vừa khung của nó - không chữ nào bị cắt im lặng.
 * Đo bằng chiều cao tự nhiên của đoạn chữ so với khung đã cấp và mép phải từng dòng so với bề ngang khung (không dùng `hasVisualOverflow`: ở fontScale khác 1
 * nó báo sai cho mọi ô chữ trên Robolectric). Dòng bị "…" (maxLines + Ellipsis) cũng là cắt: khung khi ấy vừa khít đoạn chữ đã cắt nên phép đo trên
 * không thấy - hỏi thẳng isLineEllipsized (left174: "Nghe tiếp · Chương 3: Một cái t…" lọt qua máy dò này). Trả về số ô chữ đã kiểm.
 */
fun SemanticsNodeInteractionsProvider.assertNoTextOverflow(): Int {
    val nodes = onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsActions.GetTextLayoutResult), useUnmergedTree = true).fetchSemanticsNodes()
    assertTrue("không thấy ô chữ nào để kiểm", nodes.isNotEmpty())
    val offenders = ArrayList<String>()
    for (node in nodes) {
        val layouts = mutableListOf<TextLayoutResult>()
        node.config[SemanticsActions.GetTextLayoutResult].action!!(layouts)
        for (layout in layouts) {
            val natural = layout.multiParagraph.height
            val widest = (0 until layout.lineCount).maxOfOrNull { layout.getLineRight(it) } ?: 0f
            if ((0 until layout.lineCount).any { layout.isLineEllipsized(it) }) {
                offenders += "\"${layout.layoutInput.text.text.take(60)}\" bị cắt \"…\""
            } else if (natural > node.size.height + 1f || widest > node.size.width + 1f) {
                offenders += "\"${layout.layoutInput.text.text.take(60)}\" tự nhiên ${natural}x${widest} khung ${node.size} dòng ${layout.lineCount}"
            }
        }
    }
    assertTrue("chữ bị cắt: " + offenders.joinToString(" | "), offenders.isEmpty())
    return nodes.size
}
