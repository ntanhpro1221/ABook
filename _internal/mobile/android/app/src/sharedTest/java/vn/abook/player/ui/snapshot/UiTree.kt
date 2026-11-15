package vn.abook.player.ui.snapshot

import androidx.compose.ui.graphics.isSpecified
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.text.TextLayoutResult
import org.json.JSONArray
import org.json.JSONObject

internal object UiTree {
    fun describe(captured: SemanticsNode, image: String): JSONObject {
        val density = captured.layoutInfo.density.density
        val origin = captured.boundsInWindow
        val start = checkNotNull(unmerged(captured)) { "Cannot resolve unmerged UI tree for captured node ${captured.id}" }
        val nodes = JSONArray()
        walk(start, -1, nodes, density, origin.left, origin.top)
        return JSONObject()
            .put("schema", 1)
            .put("platform", "android")
            .put("image", image)
            .put("unit", "dp")
            .put("merged", start === captured && captured.mergingEnabled)
            .put("width", origin.width / density)
            .put("height", origin.height / density)
            .put("nodes", nodes)
    }

    /** Resolve the same node in its window's unmerged semantics tree. */
    private fun unmerged(node: SemanticsNode): SemanticsNode? {
        val owner = node.root ?: return null
        return find(owner.semanticsOwner.unmergedRootSemanticsNode, node.id)
    }

    private fun find(node: SemanticsNode, id: Int): SemanticsNode? {
        if (node.id == id) return node
        for (child in node.children) find(child, id)?.let { return it }
        return null
    }

    private fun walk(node: SemanticsNode, parent: Int, out: JSONArray, density: Float, dx: Float, dy: Float) {
        val config = node.config
        val id = out.length()
        val position = node.positionInWindow
        val visible = node.boundsInWindow
        val entry = JSONObject()
            .put("id", id)
            .put("parent", parent)
            .put("bounds", box(position.x, position.y, position.x + node.size.width, position.y + node.size.height, density, dx, dy))
            .put("visible", box(visible.left, visible.top, visible.right, visible.bottom, density, dx, dy))
        config.getOrNull(SemanticsProperties.Role)?.let { entry.put("role", it.toString().lowercase()) }
        config.getOrNull(SemanticsProperties.TestTag)?.let { entry.put("tag", it) }
        val text = config.getOrNull(SemanticsProperties.Text)?.joinToString(" ") { it.text }
            ?: config.getOrNull(SemanticsProperties.EditableText)?.text
        text?.let { entry.put("text", it) }
        config.getOrNull(SemanticsProperties.ContentDescription)?.let { entry.put("description", it.joinToString(" ")) }
        config.getOrNull(SemanticsProperties.Selected)?.let { entry.put("selected", it) }
        config.getOrNull(SemanticsProperties.ToggleableState)?.let { entry.put("toggle", it.toString().lowercase()) }
        if (config.contains(SemanticsProperties.SelectableGroup)) entry.put("selectable_group", true)
        if (config.contains(SemanticsProperties.Heading)) entry.put("heading", true)
        if (config.contains(SemanticsProperties.EditableText)) entry.put("editable", true)
        if (config.contains(SemanticsActions.OnClick)) entry.put("clickable", true)
        if (config.getOrNull(vn.abook.player.ui.components.VisualIcon) == true) entry.put("icon", true)
        if (config.getOrNull(vn.abook.player.ui.components.VisualImage) == true) entry.put("graphic", true)
        if (config.contains(SemanticsProperties.Disabled)) entry.put("disabled", true)
        if (text != null) layout(node)?.let { result ->
            val style = result.layoutInput.style
            if (style.fontSize.isSp) entry.put("font_size", style.fontSize.value.toDouble())
            style.fontWeight?.let { entry.put("font_weight", it.weight) }
            if (style.color.isSpecified) entry.put("color", String.format("#%06x", style.color.toArgb() and 0xffffff))
            config.getOrNull(vn.abook.player.ui.components.VisualTextColor)?.let { entry.put("color", String.format("#%06x", it and 0xffffff)) }
            entry.put("line_count", result.lineCount)
            val lines = JSONArray()
            for (line in 0 until result.lineCount) {
                lines.put(JSONObject()
                    .put("bounds", box(position.x + result.getLineLeft(line), position.y + result.getLineTop(line),
                        position.x + result.getLineRight(line), position.y + result.getLineBottom(line), density, dx, dy))
                    .put("text", result.layoutInput.text.text.substring(result.getLineStart(line), result.getLineEnd(line))))
            }
            entry.put("lines", lines)
        }
        out.put(entry)
        for (child in node.children) walk(child, id, out, density, dx, dy)
    }

    private fun layout(node: SemanticsNode): TextLayoutResult? {
        val action = node.config.getOrNull(SemanticsActions.GetTextLayoutResult)?.action ?: return null
        val results = mutableListOf<TextLayoutResult>()
        return if (runCatching { action(results) }.getOrDefault(false)) results.firstOrNull() else null
    }

    private fun box(left: Float, top: Float, right: Float, bottom: Float, density: Float, dx: Float, dy: Float) = JSONArray()
        .put(round((left - dx) / density)).put(round((top - dy) / density))
        .put(round((right - dx) / density)).put(round((bottom - dy) / density))

    private fun round(value: Float) = Math.round(value * 100) / 100.0
}
