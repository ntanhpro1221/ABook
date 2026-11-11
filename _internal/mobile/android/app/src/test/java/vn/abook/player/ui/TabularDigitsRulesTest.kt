package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật R2 (soát thiết kế 10-11, DESIGN.md 5.5): chữ số đều độ rộng (`tnum`) làm "1" hở hai bên - "1 2 chương", "1 0 phút". Nó chỉ đúng cho số đổi tại chỗ,
 * và số đổi tại chỗ đi qua [vn.abook.player.ui.components.ClockLabel]. Mọi chỗ khác dùng số tỉ lệ. Thêm chỗ được phép thì ghi tên file và lý do ở đây.
 */
class TabularDigitsRulesTest {
    private val sources = File("src/main/java")
    private val allowed = mapOf(
        "vn/abook/player/ui/components/ClockLabel.kt" to "đồng hồ, phần trăm, đếm ngược đổi tại chỗ",
    )

    internal fun uses(text: String): List<Int> =
        text.lines().withIndex().filter { (_, line) -> Regex("\"[^\"]*\\btnum\\b[^\"]*\"|FontFeature").containsMatchIn(line.substringBefore("//")) }.map { it.index + 1 }

    @Test
    fun tabularDigitsOnlyInClockLabel() {
        assertTrue(sources.isDirectory)
        val found = sources.walkTopDown().filter { it.extension == "kt" }.flatMap { file ->
            val path = file.relativeTo(sources).invariantSeparatorsPath
            if (path in allowed) emptySequence() else uses(file.readText()).asSequence().map { "$path:$it" }
        }.toList()
        assertEquals("tnum ngoài ClockLabel (số trong câu phải là số tỉ lệ):\n${found.joinToString("\n")}", emptyList<String>(), found)
    }

    @Test
    fun allowedFilesStillExist() {
        for (path in allowed.keys) assertTrue(path, File(sources, path).isFile)
    }

    @Test
    fun theRuleSeesTnumAndNothingElse() {
        assertEquals(listOf(1), uses("val s = style.merge(TextStyle(fontFeatureSettings = \"tnum\"))"))
        assertEquals(listOf(2), uses("x\nstyle.copy(fontFeatureSettings = \"lnum, tnum\")"))
        assertEquals(emptyList<Int>(), uses("// không tnum ở đây\nval tnumber = 1"))
    }
}
