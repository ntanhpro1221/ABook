package vn.abook.player.ui

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật bộ biểu tượng (chủ sách 26-10, "bộ icon xem cho hẳn hỏi"): mọi icon là hình lucide của bản web qua Icons.kt / LucidePaths.kt, không vẽ tay ở chỗ
 * khác; cỡ icon hàng / menu là mặc định 20 dp, chỗ nào khác cỡ phải có lý do ghi ở đây.
 */
class IconRulesTest {
    private val root = File("src/main/java/vn/abook/player/ui")

    /** File được vẽ bằng lệnh vẽ thô - và vì sao (không phải icon). */
    private val drawingAllowed = mapOf(
        "components/Icons.kt" to "bộ vẽ lucide",
        "components/BookCover.kt" to "nền bìa sinh",
        "components/Sheet.kt" to "viền mảnh cạnh trên của tờ ở nền tối (sheetEdge)",
        "components/Controls.kt" to "công tắc, mũi tên > (lucide qua drawLucide)",
        "components/PlayPauseGlyph.kt" to "biến hình phát <-> dừng (mực = lucide Play / Pause)",
        "nowplaying/PlayerVisuals.kt" to "nút ±15 hình riêng của web, nút phát lớn biến hình",
        "nowplaying/NowPlayingScreen.kt" to "thanh tua, công tắc Nghe | Đọc theo",
        "nowplaying/ReadAlongPane.kt" to "tô câu / từ đang đọc",
        "screens/LibraryChrome.kt" to "nền ô tìm",
        "theme/ThemeReveal.kt" to "vòng lan đổi giao diện",
        "editbook/CoverCrop.kt" to "khung cắt ảnh bìa",
    )

    /** Chỗ được đổi cỡ icon khỏi mặc định 20 dp - và vì sao. */
    private val sizeAllowed = mapOf(
        "editbook/EditBookScreen.kt" to "bút trong huy hiệu tròn nhỏ trên bìa",
        "nowplaying/PlayerVisuals.kt" to "icon trình phát 24 như web",
        "screens/LibraryChrome.kt" to "dấu + cạnh chữ 'Thêm sách', X trong ô tìm",
        "music/MusicPanel.kt" to "icon 16 trong nút chữ như nút ghost size-4 của web (Đổi bài, Chọn)",
        "screens/BookTabs.kt" to "icon 14 trong chip hồ sơ / nút nghe thử / dòng giọng (size-3.5 của web), icon 28 của ghi chú trống (size-7)",
        "screens/BookScreen.kt" to "icon 28 của trang \"Không tìm thấy sách này\" (như ghi chú trống)",
    )

    private fun sources() = root.walkTopDown().filter { it.isFile && it.extension == "kt" }.map { it.relativeTo(root).invariantSeparatorsPath to it.readText() }

    @Test
    fun onlyListedFilesDrawShapesByHand() {
        val draw = Regex("""\bdraw(Line|Path|Arc|Circle|RoundRect|Oval)\(""")
        val offenders = sources().filter { (path, text) -> path !in drawingAllowed && draw.containsMatchIn(text) }.map { it.first }.toList()
        assertTrue("Vẽ tay ngoài danh sách (icon phải dùng Icons.kt / LucidePaths): $offenders", offenders.isEmpty())
    }

    @Test
    fun iconsKeepTheirDefaultSizeExceptListedPlaces() {
        val override = Regex("""\b[A-Z][A-Za-z]*Icon\([^)]*\bsize\s*=""")
        val offenders = sources().filter { (path, text) -> path != "components/Icons.kt" && path !in sizeAllowed && override.containsMatchIn(text) }
            .map { it.first }.toList()
        assertTrue("Icon đổi cỡ ngoài danh sách (hàng / menu dùng mặc định 20 dp): $offenders", offenders.isEmpty())
    }
}
