package vn.abook.player.ui

import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.theme.AbookColors
import vn.abook.player.ui.theme.DarkColors
import vn.abook.player.ui.theme.LightColors
import java.io.File

/**
 * Biểu tượng phụ (sắp xếp, tìm, đóng) phải rõ ít nhất 3:1 so với nền (DESIGN.md; soát điện thoại thật 02-11: dấu mờ cạnh hàng lọc "rất nhạt"). Màu biểu tượng phụ là
 * `text2`, nên đo `text2` trên `bg` và `panel` ở cả hai chủ đề; thêm nữa, mã nguồn thư viện không được tô biểu tượng bằng `fg3`/`text3` (mờ hơn 3:1 ở nền sáng).
 */
class IconContrastTest {
    private fun ratio(a: Color, b: Color): Double {
        val hi = maxOf(a.luminance(), b.luminance()).toDouble()
        val lo = minOf(a.luminance(), b.luminance()).toDouble()
        return (hi + 0.05) / (lo + 0.05)
    }

    private fun check(name: String, colors: AbookColors) {
        for ((surface, bg) in listOf("bg" to colors.bg, "panel" to colors.panel)) {
            val r = ratio(colors.text2, bg)
            assertTrue("$name text2 trên $surface chỉ $r:1 (< 3:1)", r >= 3.0)
        }
    }

    @Test fun secondaryIconsReachThreeToOneInLight() = check("sáng", LightColors)

    @Test fun secondaryIconsReachThreeToOneInDark() = check("tối", DarkColors)

    @Test fun libraryChromeDoesNotPaintIconsWithTheFaintTokens() {
        val source = File("src/main/java/vn/abook/player/ui/screens/LibraryChrome.kt").readText()
        val faint = Regex("""\w+Icon\(\s*(?:[\w.]*\.)?(?:fg3|text3)\b""").findAll(source).map { it.value }.toList()
        assertTrue("biểu tượng tô màu quá nhạt: $faint", faint.isEmpty())
    }
}
