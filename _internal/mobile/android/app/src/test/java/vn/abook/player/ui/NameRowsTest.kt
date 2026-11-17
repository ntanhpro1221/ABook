package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.devices.DeviceKind
import vn.abook.player.ui.devices.DeviceRow
import vn.abook.player.ui.devices.Paired
import vn.abook.player.ui.devices.Reach
import vn.abook.player.ui.screens.PickRow
import vn.abook.player.ui.snapshot.captureRoboImage
import vn.abook.player.ui.snapshot.UiTree
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Tên dữ liệu vẫn nguyên vẹn sau OneLineFit, kể cả khi cỡ đáy phải xuống dòng. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NameRowsTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun rows(dark: Boolean, fontScale: Float) {
        val device = "Máy xách tay của gia đình ở phòng đọc sách trên tầng hai"
        val person = "Người lữ khách mang chiếc áo choàng xanh đứng bên cửa sổ phía đông"
        var opened = 0
        var picked = 0
        rule.setContent {
            val density = LocalDensity.current
            CompositionLocalProvider(LocalDensity provides Density(density.density, fontScale)) {
                AbookTheme(dark) {
                  Box(Modifier.fillMaxSize().background(Abook.colors.bg)) {
                    Column(Modifier.fillMaxWidth().background(Abook.colors.panel).padding(horizontal = 24.dp).testTag("name_rows")) {
                        DeviceRow(Paired("long", device, DeviceKind.Computer, reach = Reach.Ok), { opened++ }, {})
                        PickRow(person, "12 câu · Chương 1", false, { picked++ }, "long_person")
                        PickRow("An", null, true, {}, "short_person")
                    }
                  }
                }
            }
        }
        rule.onNodeWithText(device).assertExists()
        rule.onNodeWithText(person).assertExists()
        assertTrue(rule.assertNoTextOverflow() >= 4)
        val tree = UiTree.describe(rule.onNodeWithTag("name_rows").fetchSemanticsNode(), "name_rows.png")
        val nodes = tree.getJSONArray("nodes")
        val fittedNames = (0 until nodes.length()).map { nodes.getJSONObject(it) }
            .filter { it.optString("type") == "OneLineFit" }.map { it.optString("text") }
        assertTrue("device name carries the component marker", device in fittedNames)
        assertTrue("profile name carries the component marker", person in fittedNames)
        rule.onNodeWithTag("name_rows").captureRoboImage("src/test/snapshots/name_rows_${if (fontScale > 1f) "font130_" else ""}${if (dark) "dark" else "light"}.png")
        rule.onNodeWithTag("device_long").performClick()
        rule.onNodeWithTag("long_person").performClick()
        assertEquals(1, opened)
        assertEquals(1, picked)
    }

    @Test fun light() = rows(false, 1f)
    @Test fun dark() = rows(true, 1f)
    @Test fun largeLight() = rows(false, 1.3f)
    @Test fun largeDark() = rows(true, 1.3f)
}
