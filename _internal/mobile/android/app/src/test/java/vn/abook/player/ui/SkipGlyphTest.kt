package vn.abook.player.ui

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.nowplaying.PlayerGlyph
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import java.io.File
import kotlin.math.abs

/**
 * Nút lùi / tới 15 giây: cung ở trên, số ở dưới, giữa hai phần luôn có một dải trống đo được (chủ sách 24-10 và 26-10: số chạm hay nằm trong vòng là
 * "xấu xí"). Đo trên điểm ảnh thật, không tin hình học trong mã.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class SkipGlyphTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test
    fun theNumberSitsBelowTheArcWithAClearGapInBothDirectionsAndThemes() {
        val darkState = mutableStateOf(false)
        rule.setContent {
            AbookTheme(darkState.value) {
                Row(Modifier.background(Abook.colors.bg)) {
                    Box(Modifier.testTag("back")) { PlayerGlyph("↶15") }
                    Box(Modifier.testTag("fwd")) { PlayerGlyph("15↷") }
                }
            }
        }
        for (dark in listOf(false, true)) {
            darkState.value = dark
            rule.waitForIdle()
            for (tag in listOf("back", "fwd")) {
                val file = "src/test/snapshots/skip_glyph_${tag}_${if (dark) "dark" else "light"}.png"
                rule.onNodeWithTag(tag).captureRoboImage(file)
                checkGap(BitmapFactory.decodeFile(File(file).absolutePath), "$tag ${if (dark) "tối" else "sáng"}")
            }
        }
    }

    private fun checkGap(map: Bitmap, where: String) {
        val bg = map.getPixel(0, 0)
        fun ink(x: Int, y: Int): Boolean {
            val c = map.getPixel(x, y)
            return abs(Color.red(c) - Color.red(bg)) + abs(Color.green(c) - Color.green(bg)) + abs(Color.blue(c) - Color.blue(bg)) > 64
        }
        val rows = (0 until map.height).map { y -> (0 until map.width).any { x -> ink(x, y) } }
        // Mọi nét nằm trong ô: hàng/cột ở mép không có mực.
        assertTrue("$where: mực chạm mép trên/dưới", !rows.first() && !rows.last())
        assertTrue("$where: mực chạm mép trái/phải", (0 until map.height).none { y -> ink(0, y) || ink(map.width - 1, y) })
        // Đúng hai khối mực theo chiều dọc (cung + mũi tên, rồi số), cách nhau ít nhất 1 dp = 3 điểm ảnh ở xxhdpi.
        val bands = mutableListOf<IntRange>()
        var start = -1
        for (y in rows.indices) {
            if (rows[y] && start < 0) start = y
            if (!rows[y] && start >= 0) { bands += start until y; start = -1 }
        }
        assertTrue("$where: cần hai khối (cung, số), có ${bands.size}: $bands", bands.size == 2)
        val gap = bands[1].first - bands[0].last - 1
        assertTrue("$where: khe giữa cung và số chỉ $gap điểm ảnh", gap >= 3)
        assertTrue("$where: số phải to hơn nét cung (khối dưới cao ${bands[1].count()})", bands[1].count() >= bands[0].count())
    }
}
