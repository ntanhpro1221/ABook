package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Ảnh chụp Roborazzi chỉ có hai chỗ ở: ảnh chuẩn trong `src/test/snapshots/` (verifyRoborazziDebug so với đó), hoặc ảnh dò xét ở
 * `build/icon_probe/` được ghi cứng bằng `RoborazziTaskType.Record` nên không bao giờ tham gia so. Một ảnh ra chỗ khác (từng là `build/shots/`)
 * làm verify báo "original file ... was not found" ở mọi lần chạy; luật này bắt ngay trong test thường thay vì đợi verify.
 */
class SnapshotPathRulesTest {
    private val tests = File("src/test/java")
    private val baseline = "src/test/snapshots/"
    private val probe = "build/icon_probe/"
    private val call = Regex("""captureRoboImage\(\s*(.*)$""")
    private val identifier = Regex("""^\w+""")

    /** Vi phạm của một file (đã đọc thành dòng), dạng "dòng N: lý do". Chỉ xét dòng gọi captureRoboImage; dòng chú thích và import bị bỏ. */
    private fun offences(lines: List<String>): List<String> {
        val code = lines.mapIndexed { index, raw -> index + 1 to raw }.filter { (_, raw) ->
            val trimmed = raw.trimStart()
            !(trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*") || trimmed.startsWith("import "))
        }
        val out = mutableListOf<String>()
        for ((number, raw) in code) {
            val arg = call.find(raw)?.groupValues?.get(1) ?: continue
            // Đối số là chuỗi: xét ngay dòng này. Là tên biến: xét dòng khai báo `val tên = ...` trong file.
            val name = if (arg.startsWith("\"")) null else identifier.find(arg)?.value
            val pathLine = if (name == null) raw else code.firstOrNull { Regex("""\b(val|var)\s+$name\b""").containsMatchIn(it.second) }?.second
            if (pathLine == null || (name == null && !arg.startsWith("\""))) {
                out += "dòng $number: không đọc được đường dẫn ảnh (${raw.trim()}); dùng chuỗi hoặc `val` cùng file"
                continue
            }
            val ok = baseline in pathLine || (probe in pathLine && "RoborazziTaskType.Record" in raw)
            if (!ok) out += "dòng $number: ${raw.trim()} (ảnh phải ở $baseline, hoặc $probe kèm RoborazziTaskType.Record trên chính dòng gọi)"
        }
        return out
    }

    @Test
    fun everyCaptureLandsInTheBaselineFolderOrAnUnverifiedProbe() {
        assertTrue("không thấy ${tests.absolutePath}", tests.isDirectory)
        val files = tests.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "SnapshotPathRulesTest.kt" }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 50)
        // Chỉ file có chụp ảnh: test khác (đọc/ghi bìa .png, mime) có chuỗi .png không liên quan.
        val shooters = files.filter { "captureRoboImage" in it.readText() }
        assertTrue("không còn test nào chụp ảnh? luật này đang quét nhầm chỗ", shooters.size >= 10)
        val offenders = shooters.flatMap { file -> offences(file.readLines()).map { "${file.relativeTo(tests).invariantSeparatorsPath} $it" } }
        assertTrue("Ảnh chụp ra ngoài $baseline (verifyRoborazziDebug sẽ không có ảnh chuẩn để so): $offenders", offenders.isEmpty())
    }

    @Test
    fun theRuleCatchesStrayPathsAndLetsBaselinesAndProbesThrough() {
        assertEquals(1, offences(listOf("""rule.onRoot().captureRoboImage("build/shots/n.png")""")).size)
        assertEquals(1, offences(listOf("""rule.onRoot().captureRoboImage("out/n.png")""")).size)
        assertEquals(1, offences(listOf("""rule.onRoot().captureRoboImage(file)""")).size)
        assertEquals(1, offences(listOf("""val file = "build/icon_probe/a.png"""", """rule.onRoot().captureRoboImage(file)""")).size)
        assertEquals(1, offences(listOf("""val file = "build/shots/a.png"""", """x.captureRoboImage(file, roborazziOptions = RoborazziOptions(taskType = RoborazziTaskType.Record))""")).size)
        assertEquals(0, offences(listOf("""rule.onRoot().captureRoboImage("src/test/snapshots/n.png")""")).size)
        assertEquals(0, offences(listOf("""val file = "src/test/snapshots/a.png"""", """rule.onRoot().captureRoboImage(file)""")).size)
        assertEquals(
            0,
            offences(listOf("""val file = "build/icon_probe/a.png"""", """x.captureRoboImage(file, roborazziOptions = RoborazziOptions(taskType = RoborazziTaskType.Record))""")).size,
        )
        assertEquals(0, offences(listOf("""// captureRoboImage("build/shots/x.png")""", """import com.github.takahirom.roborazzi.captureRoboImage""")).size)
        assertEquals(0, offences(listOf("""val image = File(cacheDir, "cover.png")""")).size)
    }
}
