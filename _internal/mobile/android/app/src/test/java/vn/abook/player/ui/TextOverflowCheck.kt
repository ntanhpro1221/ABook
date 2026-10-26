package vn.abook.player.ui

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.SemanticsNodeInteractionsProvider
import androidx.compose.ui.text.TextLayoutResult
import org.junit.Assert.assertTrue

/**
 * Máy dò dùng chung cho test cỡ chữ lớn (fontScale 1.3): mọi chữ đang vẽ trên màn phải vừa khung của nó - không chữ nào bị cắt im lặng.
 * Đo bằng chiều cao tự nhiên của đoạn chữ so với khung đã cấp và mép phải từng dòng so với bề ngang khung (không dùng `hasVisualOverflow`: ở fontScale khác 1
 * nó báo sai cho mọi ô chữ trên Robolectric). Trả về số ô chữ đã kiểm, để test chắc là có kiểm cái gì đó.
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
            if (natural > node.size.height + 1f || widest > node.size.width + 1f) {
                offenders += "\"${layout.layoutInput.text.text.take(60)}\" tự nhiên ${natural}x${widest} khung ${node.size} dòng ${layout.lineCount}"
            }
        }
    }
    assertTrue("chữ bị cắt: " + offenders.joinToString(" | "), offenders.isEmpty())
    return nodes.size
}
