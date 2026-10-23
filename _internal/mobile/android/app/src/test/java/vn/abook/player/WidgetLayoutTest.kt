package vn.abook.player

import java.io.File
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.*
import org.junit.Test
import org.w3c.dom.Element

class WidgetLayoutTest {
    private val ns = "http://schemas.android.com/apk/res/android"
    private fun children(e: Element): List<Element> = (0 until e.childNodes.length)
        .mapNotNull { e.childNodes.item(it) as? Element }
    private fun attr(e: Element, key: String) = e.getAttributeNS(ns, key)
    private fun dp(e: Element, key: String): Int = attr(e, key).removeSuffix("dp").toIntOrNull() ?: 0
    private fun padding(e: Element, side: String) =
        if (e.hasAttributeNS(ns, "padding$side")) dp(e, "padding$side") else dp(e, "padding")
    private fun margins(e: Element, axis: Boolean) = if (axis)
        dp(e, "layout_marginStart") + dp(e, "layout_marginEnd")
        else dp(e, "layout_marginTop") + dp(e, "layout_marginBottom")
    private fun pads(e: Element, axis: Boolean) = if (axis)
        padding(e, "Start") + padding(e, "End") else padding(e, "Top") + padding(e, "Bottom")
    private fun horizontal(e: Element) = e.tagName == "LinearLayout" && attr(e, "orientation") == "horizontal"

    // Read shipped XML, including the nested timer label, instead of copying control widths.
    private fun minimum(e: Element, axis: Boolean): Int {
        val key = if (axis) "layout_width" else "layout_height"
        if (attr(e, key).endsWith("dp") && dp(e, key) > 0) return dp(e, key)
        // Bound text height in XML: selection must not guess Android font metrics.
        if (!axis && e.tagName == "TextView") error("Unbounded text height: ${attr(e, "id")}")
        val sizes = children(e).map { minimum(it, axis) + margins(it, axis) }
        val content = if (e.tagName == "LinearLayout" && horizontal(e) == axis) sizes.sum()
            else sizes.maxOrNull() ?: 0
        return pads(e, axis) + content
    }

    private fun fits(e: Element, width: Int, height: Int) {
        val id = attr(e, "id").ifEmpty { e.tagName }
        assertTrue("$id: width $width < ${minimum(e, true)}", width >= minimum(e, true))
        assertTrue("$id: height $height < ${minimum(e, false)}", height >= minimum(e, false))
        if (children(e).isEmpty()) return
        val insideW = width - pads(e, true)
        val insideH = height - pads(e, false)
        val row = horizontal(e)
        val kids = children(e)
        fun base(child: Element, axis: Boolean): Int {
            val key = if (axis) "layout_width" else "layout_height"
            return when (attr(child, key)) {
                "match_parent" -> (if (axis) insideW else insideH) - margins(child, axis)
                "wrap_content" -> minimum(child, axis)
                else -> dp(child, key)
            }
        }
        val fixed = kids.sumOf { base(it, row) + margins(it, row) }
        val weights = kids.sumOf { attr(it, "layout_weight").toDoubleOrNull() ?: 0.0 }
        val remaining = (if (row) insideW else insideH) - fixed
        assertTrue("$id: overflowing children by ${-remaining} dp", remaining >= 0)
        for (child in kids) {
            val extra = if (weights > 0) (remaining * (attr(child, "layout_weight").toDoubleOrNull() ?: 0.0) / weights).toInt() else 0
            fits(child, base(child, true) + if (row) extra else 0,
                base(child, false) + if (row) 0 else extra)
        }
    }

    private fun xml(size: WidgetLayout.Size): Element {
        val name = when (size) {
            WidgetLayout.Size.SMALL -> "widget_player_small"
            WidgetLayout.Size.MEDIUM -> "widget_player_medium"
            WidgetLayout.Size.LARGE -> "widget_player"
        }
        return DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
            .newDocumentBuilder().parse(File("src/main/res/layout/$name.xml")).documentElement
    }

    @Test fun thresholdsMatchTheActualXmlInBothDimensions() {
        val sizes = listOf(
            Triple(WidgetLayout.Size.SMALL, WidgetLayout.SMALL_WIDTH_DP, WidgetLayout.SMALL_HEIGHT_DP),
            Triple(WidgetLayout.Size.MEDIUM, WidgetLayout.MEDIUM_WIDTH_DP, WidgetLayout.MEDIUM_HEIGHT_DP),
            Triple(WidgetLayout.Size.LARGE, WidgetLayout.LARGE_WIDTH_DP, WidgetLayout.LARGE_HEIGHT_DP),
        )
        for ((size, width, height) in sizes) {
            val root = xml(size)
            assertEquals(minimum(root, true), width)
            assertEquals(minimum(root, false), height)
            fits(root, width, height)
            assertEquals(size, WidgetLayout.select(width, height))
            if (size != WidgetLayout.Size.SMALL) {
                assertNotEquals(size, WidgetLayout.select(width - 1, height))
                assertNotEquals(size, WidgetLayout.select(width, height - 1))
            }
        }
        assertTrue(WidgetLayout.MEDIUM_WIDTH_DP <= 250)
        assertTrue(WidgetLayout.MEDIUM_HEIGHT_DP in 96..110)
    }

    @Test fun everyGridSizeUsesTheRichestFittingLayoutWithoutClipping() {
        for (width in listOf(110, 180, 220, 250, 300, 360)) {
            for (height in listOf(64, 96, 128)) {
                val richest = WidgetLayout.Size.values().last { size ->
                    val root = xml(size)
                    minimum(root, true) <= width && minimum(root, false) <= height
                }
                val selected = WidgetLayout.select(width, height)
                assertEquals("${width}x$height", richest, selected)
                fits(xml(selected), width, height)
            }
        }
        assertEquals(WidgetLayout.Size.SMALL, WidgetLayout.select(220, 200))
        assertEquals(WidgetLayout.Size.SMALL, WidgetLayout.select(500, 64))
        assertEquals(WidgetLayout.Size.MEDIUM, WidgetLayout.select(500, 121))
    }

    @Test fun mediumAndLargeExposeTheSameBindableViewsAndFullTimerLabel() {
        fun elements(root: Element): List<Element> = listOf(root) + children(root).flatMap { elements(it) }
        fun views(size: WidgetLayout.Size) = elements(xml(size)).filter { attr(it, "id").isNotEmpty() }
            .associateBy { attr(it, "id") }
        val large = views(WidgetLayout.Size.LARGE)
        val medium = views(WidgetLayout.Size.MEDIUM)
        assertEquals(large.keys, medium.keys)
        for (size in listOf(large, medium)) {
            val label = size.getValue("@+id/widget_sleep_text")
            assertTrue(dp(label, "layout_width") >= 64)
            assertEquals("1", attr(label, "maxLines"))
            assertEquals("end", attr(label, "ellipsize"))
            for (id in listOf("widget_back", "widget_toggle", "widget_forward", "widget_sleep")) {
                val control = size.getValue("@+id/$id")
                assertTrue(minimum(control, true) >= 40)
                assertTrue(minimum(control, false) >= 40)
            }
        }
    }

    @Test fun launcherMinimumAndInitialLayoutKeepSmallControlsVisible() {
        val provider = DocumentBuilderFactory.newInstance().apply { isNamespaceAware = true }
            .newDocumentBuilder().parse(File("src/main/res/xml/widget_player_info.xml")).documentElement
        val width = dp(provider, "minResizeWidth")
        val height = dp(provider, "minResizeHeight")
        assertTrue(width <= 110)
        assertTrue(height <= 64)
        fits(xml(WidgetLayout.Size.SMALL), width, height)
        assertEquals("@layout/widget_player_small", attr(provider, "initialLayout"))
        assertEquals("@layout/widget_player_medium", attr(provider, "previewLayout"))
    }
}
