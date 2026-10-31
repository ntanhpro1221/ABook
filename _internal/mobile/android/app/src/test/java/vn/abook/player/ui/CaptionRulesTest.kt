package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/**
 * [vn.abook.player.ui.components.Caption] là MỘT dòng tin phụ (12, mực phụ). Hai Caption liền nhau là một đoạn văn dựng bằng chữ phụ: các dòng dính nhau, dòng
 * xuống hàng cao hơn dòng đơn (từng gặp ở "File này có bản thu khác" và Studio). Đoạn giải thích dùng chữ 16 mực phụ cách nhau 8, như [ConfirmPage].
 */
class CaptionRulesTest {
    private val sources = File("src/main/java")

    private fun stacked(lines: List<String>): List<Int> =
        (0 until lines.size - 1).filter { lines[it].trimStart().startsWith("Caption(") && lines[it + 1].trimStart().startsWith("Caption(") }.map { it + 1 }

    @Test
    fun noTwoCaptionsStackIntoAParagraph() {
        val found = sources.walkTopDown().filter { it.extension == "kt" }.flatMap { file ->
            stacked(file.readLines()).map { "${file.relativeTo(sources)}:$it" }
        }.toList()
        assertEquals("Caption xếp chồng thành đoạn văn (dùng chữ body mực phụ cách 8):\n${found.joinToString("\n")}", emptyList<String>(), found)
    }

    @Test
    fun theRuleSeesStackedCaptionsAndNothingElse() {
        assertEquals(listOf(1), stacked(listOf("    Caption(a)", "    Caption(b)")))
        assertEquals(emptyList<Int>(), stacked(listOf("Caption(a)", "Spacer(Modifier.height(Dim.s8))", "Caption(b)")))
        assertEquals(emptyList<Int>(), stacked(listOf("BasicText(a)", "Caption(b)")))
    }
}
