package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.shell.TabBar
import vn.abook.player.ui.shell.TabHost
import vn.abook.player.ui.theme.AbookTheme

/** Đổi tab qua lại không dựng lại tab nào (đo trên máy thật: dựng lại lúc bắt đầu trượt là khung 31 ms). */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class TabHostTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val composed = HashMap<Tab, Int>()
    private lateinit var tabs: TabState

    private fun show(precompose: Boolean = false) {
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                tabs = remember { TabState(scope) }
                if (precompose) LaunchedEffect(Unit) { tabs.precomposeRest() }
                Column(Modifier.fillMaxSize()) {
                    TabHost(tabs, Modifier.weight(1f)) { tab ->
                        SideEffect { composed[tab] = (composed[tab] ?: 0) + 1 }
                        BasicText("Nội dung ${tab.label}", Modifier.fillMaxWidth().height(40.dp).testTag("content_${tab.name}"))
                    }
                    TabBar(tabs)
                }
            }
        }
    }

    @Test
    fun `switching tabs back and forth composes each tab once`() {
        show()
        assertEquals("chỉ tab đầu được dựng lúc mở", mapOf(Tab.Library to 1), composed.toMap())
        for (tab in listOf(Tab.Studio, Tab.Library, Tab.Studio, Tab.Settings, Tab.Studio, Tab.Library, Tab.Settings)) {
            rule.onNodeWithTag(tab.tag).performClick()
            rule.waitForIdle()
        }
        assertEquals(1, composed[Tab.Studio])
        assertEquals(1, composed[Tab.Library])
        assertEquals(1, composed[Tab.Settings])
    }

    @Test
    fun `a tab that was shown stays in the tree after sliding away`() {
        show()
        rule.onNodeWithTag(Tab.Studio.tag).performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("content_Studio").assertIsDisplayed()
        // Thư viện đã trượt ra ngoài màn nhưng vẫn ở trong cây (giữ trạng thái), không bị bỏ đi.
        assertEquals(1, composed[Tab.Library])
        assertTrue(tabs.isVisited(Tab.Library))
    }

    @Test
    fun `the rest of the tabs are composed ahead while idle`() {
        rule.mainClock.autoAdvance = false
        show(precompose = true)
        rule.mainClock.advanceTimeBy(100)
        assertFalse("chưa tới 300 ms thì chưa dựng trước", tabs.isVisited(Tab.Studio))
        rule.mainClock.advanceTimeBy(1000)
        assertTrue(tabs.isVisited(Tab.Studio))
        assertTrue(tabs.isVisited(Tab.Settings))
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        for (tab in Tab.entries) assertEquals("tab ${tab.name} chỉ dựng một lần", 1, composed[tab])
        // Rồi đổi tab vẫn không dựng lại.
        rule.onNodeWithTag(Tab.Settings.tag).performClick()
        rule.waitForIdle()
        for (tab in Tab.entries) assertEquals(1, composed[tab])
    }
}
