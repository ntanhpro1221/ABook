package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.ui.theme.DarkPalette
import vn.abook.player.ui.theme.LightPalette
import java.io.File
import kotlin.math.pow

/**
 * Luật MẶT CHÌM (soát điện thoại thật 02-11): ở chế độ tối ô nhập, thẻ câu mẫu, nút phụ tô `bg-sunken` (#0c0b0a) còn TỐI hơn nền (#121110) và không viền, nên gần như vô hình.
 * Hai nửa:
 *  1. Số: viền điều khiển (`--control-line`, DESIGN.md §5.1, sinh vào Tokens.kt) phải đạt >= 3:1 trên CẢ nền trang LẪN mặt chìm, ở hai giao diện. 3:1 là ngưỡng WCAG 1.4.11
 *     cho đường biên của thành phần điều khiển, cũng là ngưỡng DESIGN.md ghi cho chính token này. Tính từ hằng token, không phải số viết tay.
 *  2. Nguồn: mọi mặt chìm của ô / thẻ / nút đi qua `Modifier.insetSurface` (nền + viền). Tô thẳng `bgSunken` chỉ được ở file đã kê (rãnh tiến độ, khung chờ, ảnh bìa trống,
 *     nền PiP, đường ray công tắc phân đoạn: hình, không phải ô); thêm file mới vào danh sách là một quyết định phải có lý do.
 */
class InsetSurfaceRulesTest {
    private fun channel(argb: Long, shift: Int): Double {
        val c = ((argb shr shift) and 0xFF) / 255.0
        return if (c <= 0.03928) c / 12.92 else ((c + 0.055) / 1.055).pow(2.4)
    }

    private fun luminance(argb: Long) = 0.2126 * channel(argb, 16) + 0.7152 * channel(argb, 8) + 0.0722 * channel(argb, 0)

    private fun ratio(a: Long, b: Long): Double {
        val (hi, lo) = luminance(a).let { x -> luminance(b).let { y -> if (x >= y) x to y else y to x } }
        return (hi + 0.05) / (lo + 0.05)
    }

    @Test
    fun theInsetEdgeReaches3To1OnThePageAndOnTheSunkenFillInBothThemes() {
        val cases = mapOf(
            "sáng" to listOf(LightPalette.CONTROL_LINE to LightPalette.BG, LightPalette.CONTROL_LINE to LightPalette.BG_SUNKEN, LightPalette.CONTROL_LINE to LightPalette.PANEL),
            "tối" to listOf(DarkPalette.CONTROL_LINE to DarkPalette.BG, DarkPalette.CONTROL_LINE to DarkPalette.BG_SUNKEN, DarkPalette.CONTROL_LINE to DarkPalette.PANEL),
        )
        for ((theme, pairs) in cases) for ((edge, ground) in pairs) {
            val r = ratio(edge, ground)
            assertTrue("viền điều khiển giao diện $theme chỉ ${"%.2f".format(r)}:1 trên #${ground.toString(16).takeLast(6)} (cần >= 3:1)", r >= 3.0)
        }
    }

    @Test
    fun theFillAloneWouldNotHaveBeenEnoughInDark() {
        // Chứng cứ vì sao cần viền: mặt chìm tối so với nền chỉ ~1,05:1 - nếu ai đổi token mà cho rằng "tông bề mặt" đủ thì con số này nói không.
        assertTrue(ratio(DarkPalette.BG_SUNKEN, DarkPalette.BG) < 1.3)
    }

    private val root = File("src/main/java/vn/abook/player/ui")

    /** File được tô thẳng `bgSunken` (hình, không phải điều khiển) và lý do. */
    private val shapesOnly = mapOf(
        "components/BookCover.kt" to "bìa trống / khung chờ ảnh",
        "editbook/CoverSearchScreen.kt" to "ô ảnh bìa đang tải",
        "music/MusicPanel.kt" to "rãnh thanh tiến độ",
        "nowplaying/NowPlayingScreen.kt" to "đường ray của công tắc phân đoạn (núm panel nằm trên)",
        "nowplaying/PlayerVisuals.kt" to "nền ô bìa",
        "pip/PipContent.kt" to "nền cửa sổ mini",
        "screens/BookScreen.kt" to "khung chờ hàng chương",
        "screens/BookTabs.kt" to "khung chờ dòng lịch sử",
        "screens/SettingsVoice.kt" to "rãnh thanh tiến độ",
        "screens/LibraryChrome.kt" to "ô tìm kéo ra: tự vẽ nền VÀ viền controlLine (kiểm bên dưới)",
    )

    fun strayFills(files: List<Pair<String, List<String>>>): List<String> = files.flatMap { (path, lines) ->
        if (path.startsWith("theme/") || path in shapesOnly) emptyList()
        else lines.mapIndexedNotNull { i, line -> if (line.substringBefore("//").contains("bgSunken")) "$path:${i + 1}: ${line.trim()}" else null }
    }

    @Test
    fun everyInsetControlGoesThroughInsetSurface() {
        val files = root.walkTopDown().filter { it.isFile && it.extension == "kt" }.map { it.relativeTo(root).invariantSeparatorsPath to it.readLines() }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size > 50)
        val stray = strayFills(files)
        assertTrue("Tô thẳng bgSunken ngoài theme/ (dùng Modifier.insetSurface, hay thêm file vào shapesOnly kèm lý do):\n${stray.joinToString("\n")}", stray.isEmpty())
        for (path in shapesOnly.keys) assertTrue("$path trong shapesOnly nhưng không còn dùng bgSunken - bỏ khỏi danh sách", files.first { it.first == path }.second.any { it.contains("bgSunken") })
        val search = files.first { it.first == "screens/LibraryChrome.kt" }.second.joinToString("\n")
        assertTrue("ô tìm của Thư viện tự vẽ nền chìm thì phải tự vẽ cả viền controlLine", search.contains("controlLine"))
        // Ô nhập chung (BookField) và các mặt chìm có việc đều qua insetSurface.
        for (path in listOf("addbook/BookForms.kt", "studio/parts/WorkParts.kt", "screens/BookPeople.kt", "screens/BookSheets.kt", "components/ListParts.kt")) {
            assertTrue("$path phải dùng insetSurface", files.first { it.first == path }.second.any { it.contains("insetSurface(") })
        }
    }

    @Test
    fun theRuleCatchesAStrayFillAndLetsListedShapesThrough() {
        val bad = listOf("studio/NewCard.kt" to listOf("Box(Modifier.clip(RoundedCornerShape(Dim.radiusControl)).background(Abook.colors.bgSunken))"))
        assertEquals(1, strayFills(bad).size)
        val ok = listOf("music/MusicPanel.kt" to listOf("Box(Modifier.background(Abook.colors.bgSunken))"), "studio/Ok.kt" to listOf("Modifier.insetSurface(Abook.colors) // bgSunken + viền"))
        assertEquals(0, strayFills(ok).size)
    }
}
