package vn.abook.player.ui.snapshot

import androidx.compose.ui.graphics.isSpecified
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsNode
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.SemanticsNodeInteraction
import androidx.compose.ui.text.TextLayoutResult
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.RoborazziTaskType
import com.github.takahirom.roborazzi.provideRoborazziContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest
import com.github.takahirom.roborazzi.captureRoboImage as roborazziCapture

/**
 * Preserve Roborazzi verification and record a fresh image/tree pair under build/design_lint.
 * (bước 2, soát thiết kế 10-11): hộp (dp, so với ảnh; `bounds` = hộp đầy đủ, `visible` = phần còn thấy sau khi bị cắt), vai,
 * chữ, cỡ chữ (sp), độ đậm, số dòng, màu chữ, trạng thái chọn. Cây lấy từ cây ngữ nghĩa CHƯA gộp để mỗi dòng chữ có kiểu riêng.
 * Ảnh dò xét (`build/icon_probe/`) không có cây: design_lint chỉ đọc ảnh chuẩn.
 *
 * Test gọi y như hàm gốc (`rule.onRoot().captureRoboImage("src/test/snapshots/x.png")`), chỉ đổi import sang gói này.
 */
fun SemanticsNodeInteraction.`captureRoboImage`(
    filePath: String,
    roborazziOptions: RoborazziOptions = provideRoborazziContext().options,
) {
    requireSnapshotVerify(filePath, roborazziOptions)
    roborazziCapture(filePath, roborazziOptions)
    if (!filePath.replace('\\', '/').contains("src/test/snapshots/")) return
    recordSnapshotProof(filePath, roborazziOptions)
    val name = File(filePath).name.removeSuffix(".png")
    val image = File("build/design_lint/$name.png")
    image.parentFile?.mkdirs()
    // Record the actual frame even when normal unit tests do not update goldens.
    roborazziCapture(image.path, roborazziOptions.copy(taskType = RoborazziTaskType.Record))
    val out = File(image.parentFile, "$name.tree.json")
    out.parentFile?.mkdirs()
    val tree = UiTree.describe(fetchSemanticsNode(), image.name)
    tree.put("image_sha256", MessageDigest.getInstance("SHA-256").digest(image.readBytes()).joinToString("") { "%02x".format(it) })
    out.writeText(tree.toString())
}

/** Bitmap-only widget captures obey the same Verify/proof contract as Compose. */
fun android.graphics.Bitmap.captureRoboImage(
    filePath: String,
    roborazziOptions: RoborazziOptions = provideRoborazziContext().options,
) {
    requireSnapshotVerify(filePath, roborazziOptions)
    roborazziCapture(filePath, roborazziOptions)
    if (!filePath.replace('\\', '/').contains("src/test/snapshots/")) return
    recordSnapshotProof(filePath, roborazziOptions)
}

private fun requireSnapshotVerify(filePath: String, roborazziOptions: RoborazziOptions) {
    if (System.getenv("ABOOK_SNAPSHOT_PROOFS") != null && filePath.replace('\\', '/').contains("src/test/snapshots/")) {
        check(roborazziOptions.taskType == RoborazziTaskType.Verify) { "Release gate requires Verify, never Record" }
    }
}

private fun recordSnapshotProof(filePath: String, roborazziOptions: RoborazziOptions) {
    System.getenv("ABOOK_SNAPSHOT_PROOFS")?.let { directory ->
        check(roborazziOptions.taskType == RoborazziTaskType.Verify) { "Release gate requires Verify, never Record" }
        val golden = File(filePath).canonicalFile
        val root = File("src/test/snapshots").canonicalFile
        val relative = golden.relativeTo(root).invariantSeparatorsPath
        check(!relative.startsWith("../")) { "Golden outside snapshot root" }
        val proof = JSONObject().put("snapshot", relative).put("status", "verified")
            .put("golden_sha256", MessageDigest.getInstance("SHA-256").digest(golden.readBytes()).joinToString("") { "%02x".format(it) })
        val key = MessageDigest.getInstance("SHA-256").digest(relative.toByteArray(Charsets.UTF_8)).joinToString("") { "%02x".format(it) }
        File(directory, "$key.json").writeText(proof.toString())
    }
}

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
        if (config.contains(SemanticsActions.OnClick)) entry.put("clickable", true)
        if (config.contains(SemanticsProperties.Disabled)) entry.put("disabled", true)
        if (text != null) layout(node)?.let { result ->
            val style = result.layoutInput.style
            if (style.fontSize.isSp) entry.put("font_size", style.fontSize.value.toDouble())
            style.fontWeight?.let { entry.put("font_weight", it.weight) }
            if (style.color.isSpecified) entry.put("color", String.format("#%06x", style.color.toArgb() and 0xffffff))
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
