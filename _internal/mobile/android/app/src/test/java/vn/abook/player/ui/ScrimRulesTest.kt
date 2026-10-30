package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Nền tối sau lớp nổi (`colors.scrim`) phải đậm / nhạt dần theo lớp, không bật tắt (chủ sách 30-10: "nền mờ của cửa sổ nó phải fade chứ?").
 * Quét chữ: mọi chỗ vẽ màu scrim (`drawRect`, `background`) phải mang một alpha (tiến độ của lớp); vẽ màu scrim trơn là bật tắt.
 */
class ScrimRulesTest {
    private val scrimVar = Regex("""\bval\s+(\w+)\s*=\s*(?:Abook\.)?colors\.scrim\b""")

    private fun scan(name: String, source: String): List<String> {
        val code = MotionScan.stripComments(source)
        val names = scrimVar.findAll(code).map { Regex.escape(it.groupValues[1]) } + sequenceOf("""(?:Abook\.)?colors\.scrim""")
        val bare = Regex("""\b(drawRect|background)\(\s*(${names.joinToString("|")})\s*\)""")
        return bare.findAll(code).map { "$name:${code.substring(0, it.range.first).count { c -> c == '\n' } + 1} ${it.value}" }.toList()
    }

    @Test
    fun `scrim is always drawn with the layer's progress`() {
        val dir = File("src/main/java/vn/abook/player/ui")
        assertTrue("không thấy ${dir.absolutePath}", dir.isDirectory)
        val files = dir.walkTopDown().filter { it.extension == "kt" }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 8)
        val users = files.filter { scrimVar.containsMatchIn(it.readText()) }
        assertTrue("không còn chỗ nào dùng colors.scrim - máy dò quét sai chỗ?", users.size >= 2)
        assertEquals(emptyList<String>(), files.flatMap { scan(it.name, it.readText()) })
    }

    @Test
    fun `bare scrim is caught and alpha passes`() {
        assertEquals(1, scan("t.kt", "val scrim = Abook.colors.scrim\nBox(Modifier.drawBehind { drawRect(scrim) })").size)
        assertEquals(1, scan("t.kt", "val dim = colors.scrim\nModifier.background(dim)").size)
        assertEquals(1, scan("t.kt", "Modifier.background(Abook.colors.scrim)").size)
        assertEquals(0, scan("t.kt", "val scrim = Abook.colors.scrim\nModifier.drawBehind { drawRect(scrim, alpha = progress.value) }").size)
        assertEquals(0, scan("t.kt", "val scrim = colors.scrim\n// drawRect(scrim)\nval x = 1").size)
    }
}
