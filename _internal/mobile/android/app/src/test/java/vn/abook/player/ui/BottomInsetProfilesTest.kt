package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.shell.TabBar
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/**
 * Thanh tab với inset đo trên máy thật ([SystemInsets.kt]): đáy hàng tab cách mép đúng một lần chừa đáy của luật chung (components/Insets.kt).
 * OPPO cử chỉ ẩn vạch: 4 dp vùng nuốt + 8 dp thở = 12 dp (sàn 24 dp cũ thừa 12 dp - khoảng trống chủ sách chê); emulator cử chỉ / 3 nút: đúng thanh điều hướng như số đo cũ.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BottomInsetProfilesTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private fun tabGap(insets: BottomInsets, expected: Float) {
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                val tabs = remember { TabState(scope) }
                Column(Modifier.fillMaxSize().background(Abook.colors.bg)) { Box(Modifier.weight(1f)); TabBar(tabs) }
            }
        }
        rule.applyBottomInsets(insets)
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        val tab = rule.onNodeWithTag(Tab.Library.tag).getUnclippedBoundsInRoot()
        assertEquals("${insets.name}: hàng tab cách mép dưới", expected, (root.bottom - tab.bottom).value, 0.5f)
        assertEquals(expected, insets.clearance(rule.density.density).value, 0.5f)
    }

    @Test fun oppoHiddenBar() = tabGap(OppoHiddenBar, 12f)

    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi")
    fun emulatorGesture() = tabGap(EmulatorGesture, 24f)

    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi")
    fun emulatorThreeButton() = tabGap(EmulatorThreeButton, 48f)
}
