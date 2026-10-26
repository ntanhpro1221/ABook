package vn.abook.player.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.Composable
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.*
import vn.abook.player.ui.nowplaying.PlayerGlyph
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import java.io.File
import kotlin.math.abs

/**
 * Bảng soát mọi biểu tượng native (chủ sách 26-10: "bộ icon xem cho hẳn hỏi"): mỗi icon ở cỡ thật trong ô của nó, sáng + tối, để nhìn phóng to; máy đo
 * từng icon: có mực, mực không chạm mép ô (không bị cắt), tâm mực không lệch quá 1/6 ô (trừ hình lệch có chủ ý của lucide).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w411dp-h1400dp-xxhdpi")
class IconSheetTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private val icons: List<Pair<String, @Composable (androidx.compose.ui.graphics.Color) -> Unit>> = listOf(
        "Plus" to { c -> PlusIcon(c) }, "Search" to { c -> SearchIcon(c) }, "Close" to { c -> CloseIcon(c) },
        "Sort" to { c -> SortIcon(c) }, "Check" to { c -> CheckIcon(c) }, "Remote" to { c -> RemoteIcon(c) },
        "More" to { c -> MoreIcon(c) }, "Restart" to { c -> RestartIcon(c) }, "DashedCircle" to { c -> DashedCircleIcon(c) },
        "Pencil" to { c -> PencilIcon(c) }, "Share" to { c -> ShareIcon(c) }, "Trash" to { c -> TrashIcon(c) },
        "BookOpen" to { c -> BookOpenIcon(c) }, "Export" to { c -> ExportIcon(c) }, "Voice" to { c -> VoiceIcon(c) },
        "Headphones" to { c -> HeadphonesIcon(c) }, "Moon" to { c -> MoonIcon(c) }, "Theme" to { c -> ThemeIcon(c) },
        "Devices" to { c -> DevicesIcon(c) }, "Wrench" to { c -> WrenchIcon(c) }, "File" to { c -> FileIcon(c) },
        "Folder" to { c -> FolderIcon(c) }, "Image" to { c -> ImageIcon(c) }, "Laptop" to { c -> LaptopIcon(c) },
        "Phone" to { c -> PhoneIcon(c) }, "Bluetooth" to { c -> BluetoothIcon(c) }, "Chevron" to { c -> ChevronIcon(c) },
        "Download" to { c -> DownloadIcon(c) }, "Upload" to { c -> UploadIcon(c) }, "Key" to { c -> KeyIcon(c) }, "PlayS" to { c -> PlayIcon(c) }, "Stop" to { c -> StopIcon(c) },
        "ChevronOpen" to { c -> ChevronIcon(c, turn = { 1f }) },
        "P ⌄" to { _ -> PlayerGlyph("⌄") }, "P ⋯" to { _ -> PlayerGlyph("⋯") }, "P prev" to { _ -> PlayerGlyph("|‹") },
        "P next" to { _ -> PlayerGlyph("›|") }, "P back15" to { _ -> PlayerGlyph("↶15") }, "P fwd15" to { _ -> PlayerGlyph("15↷") },
        "P sleep" to { _ -> PlayerGlyph("◷") }, "P chapters" to { _ -> PlayerGlyph("☷") }, "P plus" to { _ -> PlayerGlyph("+") },
        "P minus" to { _ -> PlayerGlyph("−") }, "Play" to { c -> PlayPauseGlyph(false, c, 24.dp) }, "Pause" to { c -> PlayPauseGlyph(true, c, 24.dp) },
        "Back" to { _ -> BackButton({}) },
    )

    /** Hình lệch tâm có chủ ý: tam giác phát (tâm quang học), mũi tên ">" dồn phải và "←" dồn trái - mũi nhọn chạm mép ô theo luật mép cột. */
    private val offCenterOk = setOf("Chevron", "ChevronOpen", "Play", "Back")
    private val touchesEdgeOk = setOf("Chevron", "ChevronOpen", "Back")

    @Test
    fun everyIconHasInkInsideItsBoxAndSitsCentered() {
        val dark = mutableStateOf(false)
        val solo = mutableStateOf<String?>(null)
        rule.setContent {
            AbookTheme(dark.value) {
                val alone = solo.value
                // Đo: một icon đứng riêng giữa nền trống (không dính mực hàng bên cạnh).
                if (alone != null) Box(Modifier.background(Abook.colors.bg).padding(12.dp)) {
                    Box(Modifier.testTag("solo")) { icons.first { it.first == alone }.second(Abook.colors.text) }
                } else Column(Modifier.background(Abook.colors.bg).padding(8.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    for (row in icons.chunked(3)) {
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            for ((name, draw) in row) {
                                Row(Modifier.width(128.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Box { draw(Abook.colors.text) }
                                    Spacer(Modifier.width(4.dp))
                                    BasicText(name, style = Abook.type.caption)
                                }
                            }
                        }
                    }
                }
            }
        }
        val problems = mutableListOf<String>()
        for (mode in listOf(false, true)) {
            dark.value = mode
            rule.waitForIdle()
            val tag = if (mode) "dark" else "light"
            rule.onRoot().captureRoboImage("src/test/snapshots/icon_sheet_$tag.png")
        }
        dark.value = false
        for ((name, _) in icons) {
            solo.value = name
            rule.waitForIdle()
            val file = "build/icon_probe/${name.replace(' ', '_')}.png"
            rule.onNodeWithTag("solo").captureRoboImage(file)
            problems += measure(BitmapFactory.decodeFile(File(file).absolutePath), name)
        }
        assertTrue(problems.joinToString("\n"), problems.isEmpty())
    }

    private fun measure(map: Bitmap, name: String): List<String> {
        val bg = map.getPixel(0, 0).let { if (Color.alpha(it) == 0) Color.WHITE else it }
        var minX = map.width; var minY = map.height; var maxX = -1; var maxY = -1
        for (y in 0 until map.height) for (x in 0 until map.width) {
            val c = map.getPixel(x, y)
            if (abs(Color.red(c) - Color.red(bg)) + abs(Color.green(c) - Color.green(bg)) + abs(Color.blue(c) - Color.blue(bg)) > 96) {
                if (x < minX) minX = x; if (x > maxX) maxX = x; if (y < minY) minY = y; if (y > maxY) maxY = y
            }
        }
        if (maxX < 0) return listOf("$name: không có mực")
        val out = mutableListOf<String>()
        if (name !in touchesEdgeOk && (minX == 0 || minY == 0 || maxX == map.width - 1 || maxY == map.height - 1)) out += "$name: mực chạm mép ô (có thể bị cắt) ${map.width}x${map.height} [$minX,$minY..$maxX,$maxY]"
        val dx = (minX + maxX) / 2f - (map.width - 1) / 2f
        val dy = (minY + maxY) / 2f - (map.height - 1) / 2f
        if (name !in offCenterOk && (abs(dx) > map.width / 6f || abs(dy) > map.height / 6f)) out += "$name: lệch tâm dx=$dx dy=$dy (ô ${map.width})"
        println("ICON $name box=${map.width}x${map.height} ink=[$minX,$minY..$maxX,$maxY] dx=$dx dy=$dy")
        return out
    }
}
