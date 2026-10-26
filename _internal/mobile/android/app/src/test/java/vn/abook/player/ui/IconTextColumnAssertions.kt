package vn.abook.player.ui

import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.test.junit4.ComposeTestRule
import androidx.compose.ui.test.onRoot
import org.junit.Assert.assertTrue

private fun SemanticsNode.subtree(): List<SemanticsNode> = listOf(this) + children.flatMap { it.subtree() }
private fun SemanticsNode.tag() = config.getOrNull(SemanticsProperties.TestTag)

/** Check actual, unclipped text coordinates, including lines inside Reveal and lazy-row descendants. */
fun SemanticsNodeInteraction.assertIconLedTextColumn() = assertIconLedTextColumn(fetchSemanticsNode())

private fun assertIconLedTextColumn(row: SemanticsNode) {
    val nodes = row.subtree()
    val title = nodes.single { it.tag() == "row_title" }
    val leading = nodes.single { it.tag() == "row_leading" }
    val left = title.positionInRoot.x
    assertTrue("Title must follow its leading slot", left > leading.positionInRoot.x)
    for (text in nodes.filter { it.config.getOrNull(SemanticsProperties.Text) != null }) {
        if (text.positionInRoot.y + 1f < title.positionInRoot.y) continue
        assertTrue("Text ${text.config[SemanticsProperties.Text]} starts left of title: ${text.positionInRoot.x} < $left",
            text.positionInRoot.x + 1f >= left)
    }
}

/** Apply to every rendered ListItem / MenuRow with a leading slot on a surface, including ListItem.below. */
fun ComposeTestRule.assertIconLedTextColumns() {
    val nodes = onRoot(useUnmergedTree = true).fetchSemanticsNode().subtree()
    for (leading in nodes.filter { it.tag() == "row_leading" }) {
        var row = leading.parent
        while (row != null && row.subtree().none { it.tag() == "row_title" }) row = row.parent
        checkNotNull(row) { "Leading slot has no title" }
        // ListItem's Row holds the title; its enclosing Column also owns the supporting content.
        val parent = row.parent
        if (parent != null && parent.children.any { it.tag() == "row_below" }) row = parent
        assertIconLedTextColumn(row)
    }
}
