package vn.abook.player.ui

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Chỗ chừa đáy màn có MỘT cửa (`components/Insets.kt`: [vn.abook.player.ui.components.gestureBarPadding], `gestureSafe`, `navigationClearance`).
 * Lỗi điện thoại thật 05-11: ColorOS cử chỉ ẩn vạch báo inset đáy 0, mà ai tự đọc `navigationBars` thì đặt nút trong dải vuốt của hệ thống - bấm không trúng.
 * Máy dò: ngoài Insets.kt, không file nào được đọc inset đáy của thanh hệ thống trực tiếp. `systemBars` / `safeDrawing` chỉ được dùng khi bọc trong `gestureSafe(`.
 */
class BottomInsetScanTest {
    private val main = File("src/main/java")

    private val bare = listOf(
        "navigationBarsPadding", "WindowInsets.navigationBars", "systemBarsPadding", "safeDrawingPadding", "safeContentPadding",
        "WindowInsets.safeGestures", "WindowInsets.mandatorySystemGestures", "WindowInsets.tappableElement",
    )
    private val wrapped = listOf("WindowInsets.systemBars", "WindowInsets.safeDrawing", "WindowInsets.safeContent")

    private fun sources() = main.walkTopDown().filter { it.isFile && it.extension == "kt" }
        .filter { it.invariantSeparatorsPath != File("src/main/java/vn/abook/player/ui/components/Insets.kt").invariantSeparatorsPath }.toList()

    @Test
    fun noOneReadsTheBottomSystemInsetOutsideTheSharedHelper() {
        assertTrue("không thấy mã nguồn để quét", sources().size > 100)
        val found = ArrayList<String>()
        for (file in sources()) file.readLines().forEachIndexed { index, raw ->
            val line = raw.trim()
            if (line.startsWith("//") || line.startsWith("*") || line.startsWith("/*")) return@forEachIndexed
            if (line.startsWith("import ")) return@forEachIndexed
            val code = line.substringBefore("//")
            bare.filter { it in code }.forEach { found += "${file.path}:${index + 1} dùng $it trực tiếp" }
            wrapped.filter { it in code && "gestureSafe(" !in code }.forEach { found += "${file.path}:${index + 1} dùng $it không qua gestureSafe(...)" }
        }
        assertTrue("Chừa đáy phải qua components/Insets.kt (gestureBarPadding / gestureSafe / navigationClearance):\n" + found.joinToString("\n"), found.isEmpty())
    }

    @Test
    fun theScannerSeesTheKindOfLineItGuardsAgainst() {
        // Chống "xanh vì mù": chính file dùng chung phải chứa các dòng mà máy dò cấm ở nơi khác.
        val helper = File("src/main/java/vn/abook/player/ui/components/Insets.kt").readText()
        assertTrue(helper.contains("WindowInsets.navigationBars"))
        assertTrue(bare.any { it in helper })
    }
}
