package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.screens.bookCompositionWidth
import vn.abook.player.ui.screens.bookLeftWidth
import vn.abook.player.ui.theme.WidthClass
import vn.abook.player.ui.theme.widthClass
import java.io.File

/** Khổ cửa sổ (DESIGN.md §5.5) trên điện thoại: năm khổ từ token sinh ra, mốc thuộc khổ trên; công thức hai cột của trang sách giống Qt / web. */
class WidthClassTest {
    @Test
    fun fiveClassesFromTheGeneratedTable() {
        assertEquals(listOf(0, 600, 840, 1200, 1600), WidthClass.entries.map { it.fromDp })
        assertEquals(WidthClass.COMPACT, widthClass(360f))
        assertEquals(WidthClass.COMPACT, widthClass(599.9f))
        assertEquals(WidthClass.MEDIUM, widthClass(600f))
        assertEquals(WidthClass.MEDIUM, widthClass(700f))
        assertEquals(WidthClass.EXPANDED, widthClass(840f))
        assertEquals(WidthClass.EXPANDED, widthClass(900f))
        assertEquals(WidthClass.LARGE, widthClass(1200f))
        assertEquals(WidthClass.LARGE, widthClass(1300f))
        assertEquals(WidthClass.EXTRA_LARGE, widthClass(1600f))
        assertTrue(widthClass(900f) >= WidthClass.EXPANDED && widthClass(700f) < WidthClass.EXPANDED)
    }

    @Test
    fun bookColumnsFollowTheQtFormula() {
        assertEquals(320f, bookLeftWidth(840f), 0.001f)
        assertEquals(320f, bookLeftWidth(700f), 0.001f)
        assertEquals(367.4f, bookLeftWidth(1630f), 0.01f)
        assertEquals(380f, bookLeftWidth(3000f), 0.001f)
        // 840: hai lề 20 ăn mất phần dư; rộng hơn thì cột chương dừng ở 640, cả khối không quá 1360.
        assertEquals(800f, bookCompositionWidth(840f), 0.001f)
        assertEquals(bookLeftWidth(1300f) + 32f + 640f, bookCompositionWidth(1300f), 0.001f)
        assertTrue(bookCompositionWidth(5000f) <= 1360f)
    }

    /** Màn native không tự viết số 600 / 840 / 1200 / 1600 để quyết bố cục: chỉ `widthClass` (tests/test_width_class_single_source.py làm cùng việc cho cả QML / TS). */
    @Test
    fun noScreenDecidesLayoutWithAHandWrittenBreakpoint() {
        val dir = File("src/main/java/vn/abook/player/ui")
        assertTrue(dir.isDirectory)
        val number = Regex("""\b(600|840|1200|1600)\b(\.dp)?""")
        val widthy = Regex("""(?i)(width|widthDp)\w*\s*(>=|<=|>|<)\s*(600|840|1200|1600)\b""")
        val found = dir.walkTopDown().filter { it.extension == "kt" && it.name != "Tokens.kt" }.flatMap { file ->
            file.readLines().withIndex().filter { (_, line) -> !line.trimStart().startsWith("//") && !line.trimStart().startsWith("*") && widthy.containsMatchIn(line) && number.containsMatchIn(line) }
                .map { (index, line) -> "${file.name}:${index + 1}: ${line.trim()}" }
        }.toList()
        assertEquals(found.joinToString("\n"), emptyList<String>(), found)
    }
}
