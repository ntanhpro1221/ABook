package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật KHUNG CHỜ (soát điện thoại thật 02-11, bản demo: danh sách chương trống, "Lịch sử" hiện khung chờ mãi): mọi khung chờ (skeleton) phải kết thúc thành dữ liệu, trạng thái
 * rỗng có chữ, hoặc lỗi - kể cả khi nguồn không có dữ liệu. Hai nửa:
 *  1. Danh sách file có khung chờ là CỐ ĐỊNH: thêm khung chờ ở file mới là một quyết định phải kê vào đây, kèm tên trạng thái kết thúc của nó.
 *  2. Mỗi file trong danh sách phải còn nhắc tới trạng thái kết thúc đã kê (cờ "đã đọc" / thất bại / rỗng) - bỏ nhánh kết thúc đi thì máy dò đỏ.
 * Việc "nguồn không dữ liệu thì khung chờ biến mất" của trang sách có test dựng thật ở BookTabsScreenTest.
 */
class SkeletonEndsScanTest {
    private val root = File("src/main/java/vn/abook/player/ui")

    /** File có khung chờ -> các dấu hiệu nhánh kết thúc phải có trong file (đủ cả ba khi có). */
    private val endings = mapOf(
        "screens/BookScreen.kt" to listOf("ui.loaded", "noChapters"),
        "screens/BookTabs.kt" to listOf("loaded", "history_empty", "cast_empty"),
        "editbook/CoverSearchScreen.kt" to listOf("CoverStage.Failed", "CoverStage.Nothing"),
        "music/MusicPanel.kt" to listOf("ui.failed"),
        "screens/SettingsVoice.kt" to listOf("VoiceList.Failed"),
    )

    private val skeletonCall = Regex("""\b\w*Skeleton\w*\s*\(""")

    private fun skeletonFiles(): Set<String> = root.walkTopDown().filter { it.isFile && it.extension == "kt" }
        .filter { f -> f.readLines().any { l -> val t = l.trimStart(); !t.startsWith("//") && !t.startsWith("*") && !t.startsWith("/*") && skeletonCall.containsMatchIn(l) } }
        .map { it.relativeTo(root).invariantSeparatorsPath }.toSet()

    @Test
    fun everyFileWithASkeletonIsListedWithItsEnding() {
        assertTrue("không thấy ${root.absolutePath}", root.isDirectory)
        assertEquals("File có khung chờ khác danh sách đã kê (kê trạng thái kết thúc của khung mới vào `endings`)", endings.keys, skeletonFiles())
    }

    @Test
    fun everyListedFileStillHasItsEndingBranches() {
        for ((file, marks) in endings) {
            val text = File(root, file).readText()
            for (mark in marks) assertTrue("$file không còn nhánh kết thúc '$mark' của khung chờ", text.contains(mark))
        }
    }
}
