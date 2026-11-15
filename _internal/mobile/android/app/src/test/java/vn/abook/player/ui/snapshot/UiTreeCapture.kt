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
