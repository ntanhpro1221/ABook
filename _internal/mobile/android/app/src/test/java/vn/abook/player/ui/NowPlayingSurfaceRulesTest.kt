package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật mặt nền của trình phát (soát điện thoại thật 13-11: một khối đen dưới chữ Đọc theo): màn Đang nghe vẽ nền theo màu bìa sách, các bảng trượt của nó nền
 * `panel`. Thành phần nào bên trong tự tô `Abook.colors.bg` (nền chung của app) sẽ hiện thành một mảng khác màu đè lên - dải nút "Tới câu đang nghe" ở
 * ReadAlongPane là ca thật, dòng Hoàn tác ở TonePage cùng loại. Trong ui/nowplaying không chỗ nào được tô nền bằng `Abook.colors.bg`: để trong suốt
 * cho màu bìa / nền bảng lộ ra. Bản web cùng luật: dải neo Đọc theo dùng nền mặt đọc `--read-bg` (ui/src/listen/readingDockSurface.test.ts).
 */
class NowPlayingSurfaceRulesTest {
    private val root = File("src/main/java/vn/abook/player/ui/nowplaying")
    private val appGround = Regex("""\.background\(\s*Abook\.colors\.bg\s*[,)]""")

    private fun offences(name: String, text: String): List<String> = text.lines().mapIndexedNotNull { index, line ->
        val trimmed = line.trimStart()
        if (trimmed.startsWith("//") || trimmed.startsWith("*")) null
        else if (appGround.containsMatchIn(line)) "$name dòng ${index + 1}: tô nền Abook.colors.bg trên mặt trình phát" else null
    }

    @Test
    fun the_player_never_paints_the_app_ground_over_its_tint() {
        val files = root.walkTopDown().filter { it.isFile && it.extension == "kt" }.toList()
        assertTrue("không tìm thấy mã trình phát ở $root", files.isNotEmpty())
        val found = files.flatMap { offences(it.relativeTo(root).invariantSeparatorsPath, it.readText()) }
        assertEquals(emptyList<String>(), found)
    }

    @Test
    fun the_rule_catches_a_planted_fill() {
        val planted = "        Box(Modifier.fillMaxWidth().height(Dim.s48).background(Abook.colors.bg)\n"
        assertEquals(1, offences("planted.kt", planted).size)
        assertEquals(0, offences("planted.kt", "        Box(Modifier.background(Abook.colors.panel))\n").size)
    }
}
