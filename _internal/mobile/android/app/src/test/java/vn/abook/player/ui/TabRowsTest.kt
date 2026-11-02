package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.ScrollingTabs
import vn.abook.player.ui.studio.StudioTab
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.Dim
import java.io.File

/**
 * Hàng mục (tab) không bao giờ xuống dòng (soát điện thoại thật 02-11: dự án Studio ở 360 dp xếp hai hàng, gạch chân chỉ nằm một hàng). Hết chỗ thì cuộn ngang
 * ([ScrollingTabs], cùng thành phần với trang sách). Thử ở 360 dp, 360 dp chữ 1,3 lần và 320 dp chữ 1,3 lần, sáng và tối.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class TabRowsTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private fun show(dark: Boolean = false) {
        rule.setContent {
            AbookTheme(dark) {
                var tab by remember { mutableStateOf(StudioTab.Chapters) }
                Box(Modifier.fillMaxSize().background(Abook.colors.bg).padding(horizontal = Dim.margin)) {
                    ScrollingTabs(StudioTab.entries, tab, { tab = it }, label = { it.label }, tag = { "studio_tab_${it.key}" }, rowTag = "studio_tabs")
                }
            }
        }
        rule.waitForIdle()
    }

    private fun assertOneRowAndReachable() {
        val tops = StudioTab.entries.map { rule.onNodeWithTag("studio_tab_${it.key}").getUnclippedBoundsInRoot().top }
        assertEquals("mọi mục cùng một hàng: $tops", 1, tops.distinct().size)
        val bar = rule.onNodeWithTag("studio_tabs").getUnclippedBoundsInRoot()
        assertTrue("thanh cao một hàng (48 dp), không phải hai: ${bar.bottom - bar.top}", bar.bottom - bar.top <= Dim.s48 + 1.dp)
        for (tab in StudioTab.entries) {
            rule.onNodeWithTag("studio_tab_${tab.key}").performScrollTo()
            val box = rule.onNodeWithTag("studio_tab_${tab.key}").getUnclippedBoundsInRoot()
            assertTrue("${tab.label} nằm trong khung sau khi cuộn", box.left >= bar.left - 0.5.dp && box.right <= bar.right + 0.5.dp)
        }
        // Chạm được từng mục.
        rule.onNodeWithTag("studio_tab_${StudioTab.Music.key}").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("studio_tab_${StudioTab.Chapters.key}").performScrollTo().performClick()
    }

    @Test fun studioTabsAreOneScrollingRowAt360() {
        show()
        assertOneRowAndReachable()
    }

    @Test @Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi", fontScale = 1.3f)
    fun studioTabsAreOneScrollingRowAt360WithBigText() {
        show(dark = true)
        rule.onRoot().captureRoboImage("src/test/snapshots/tabs_studio_360_big_dark.png")
        assertOneRowAndReachable()
    }

    @Test @Config(sdk = [35], qualifiers = "w320dp-h700dp-xxhdpi", fontScale = 1.3f)
    fun studioTabsAreOneScrollingRowAt320WithBigText() {
        show()
        assertOneRowAndReachable()
    }

    @Test fun studioTabsLookRightAt360() {
        show(dark = true)
        rule.onRoot().captureRoboImage("src/test/snapshots/tabs_studio_360_dark.png")
    }

    /** Một lớp lỗi, một luật: bộ mục (xếp "...Tab.entries") không đi qua ChoiceRow (hàng chọn-một cho phép xuống dòng); chúng dùng ScrollingTabs. */
    @Test fun noTabSetGoesThroughTheWrappingChoiceRow() {
        val root = File("src/main/java/vn/abook/player/ui")
        val offenders = root.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .filter { Regex("""\bChoiceRow\(\s*\w*Tab\.entries""").containsMatchIn(it.readText()) }.map { it.name }.toList()
        assertTrue("hàng mục dùng ChoiceRow (sẽ xuống dòng ở màn hẹp), dùng ScrollingTabs: $offenders", offenders.isEmpty())
    }
}
