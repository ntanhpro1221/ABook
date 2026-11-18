package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.click
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performTouchInput
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.nav.NavState
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nav.TabState
import vn.abook.player.ui.player.MiniPlayer
import vn.abook.player.ui.shell.ShellFrame
import vn.abook.player.ui.shell.TabBar
import vn.abook.player.ui.theme.AbookTheme

/**
 * Soát 18-11 (lần 4 thêm thanh báo và nút phát của thanh phát nhỏ): ba lớp chrome của [ShellFrame] (thanh tab, thanh phát nhỏ + dải chừa đáy, thanh báo) đè lên danh sách cuộn của màn. Cú bấm trên chúng - vào nút
 * lẫn vào phần đệm - không bao giờ tới dòng danh sách nằm dưới; nút của chính lớp vẫn chạy. Bản floatingLayer chia chạm với anh em (82cb3968e) làm dòng dưới
 * nhận cú bấm TRƯỚC (tab không đổi, dòng mở ra) - ca này đỏ trên bản ấy.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ShellTapThroughTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun chromeOverAListKeepsItsTaps() {
        val opened = ArrayList<Int>()
        var nowPlaying = 0
        var toggled = 0
        var undone = 0
        lateinit var tabs: TabState
        val playing = PlayerState(bookId = "b1", bookTitle = "Dế Mèn phiêu lưu ký", chapterId = 4, chapterTitle = "Chương 4", playing = true, durationMs = 600_000)
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                val nav = remember { NavState(scope) }
                tabs = remember { TabState(scope) }
                ShellFrame(
                    nav,
                    stack = {
                        // Dòng danh sách phủ kín màn, kể cả phần nằm dưới thanh phát nhỏ và thanh tab.
                        LazyColumn(Modifier.fillMaxSize().testTag("rows")) {
                            items((0 until 80).toList()) { i ->
                                Box(Modifier.fillMaxWidth().height(40.dp).clickable { opened += i }.testTag("row_$i")) { BasicText("Dòng $i") }
                            }
                        }
                    },
                    // Thanh báo / hoàn tác (BARS): một nút "Hoàn tác" trên một dải rộng hơn nó.
                    bars = {
                        Box(Modifier.fillMaxWidth().height(56.dp).testTag("bar")) {
                            Box(Modifier.size(40.dp).clickable { undone++ }.testTag("bar_undo"))
                        }
                    },
                    miniBar = { MiniPlayer(playing, { 150_000L }, CoverLoader(1 shl 20), { toggled++ }, { nowPlaying++ }) },
                    tabBar = { Box(Modifier.testTag("tab_host")) { TabBar(tabs) } },
                )
            }
        }
        rule.waitForIdle()
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        val mini = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        val host = rule.onNodeWithTag("tab_host").getUnclippedBoundsInRoot()
        // Có dòng nằm dưới thật: không thì ca này xanh vì mù.
        assertTrue("rows must reach under the chrome", rule.onNodeWithTag("rows").getUnclippedBoundsInRoot().bottom >= root.bottom)

        rule.onNodeWithTag(Tab.Studio.tag).performTouchInput { click(center) }
        rule.waitForIdle()
        assertEquals("a tap on a tab switches the tab", Tab.Studio.ordinal, tabs.selected)
        assertEquals("a tap on a tab reached the row under it", emptyList<Int>(), opened)

        rule.onNodeWithTag("mini_player").performTouchInput { click(Offset(width * 0.45f, height / 2f)) }
        rule.waitForIdle()
        assertEquals("a tap on the mini player body opens Now Playing", 1, nowPlaying)
        assertEquals("a tap on the mini player reached the row under it", emptyList<Int>(), opened)

        // Nút phát / dừng của thanh phát nhỏ vẫn bấm được trong lớp chặn, và không mở Đang nghe hay dòng dưới.
        rule.onNodeWithTag("mini_play").performTouchInput { click(center) }
        rule.waitForIdle()
        assertEquals("the mini player play button toggles playback", 1, toggled)
        assertEquals(1, nowPlaying)
        assertEquals("a tap on the play button reached the row under it", emptyList<Int>(), opened)

        // Thanh báo: nút của nó chạy; chỗ trống của dải (ngoài nút) không tới dòng dưới.
        rule.onNodeWithTag("bar_undo").performTouchInput { click(center) }
        rule.onNodeWithTag("bar").performTouchInput { click(Offset(width - 4f, height / 2f)) }
        rule.waitForIdle()
        assertEquals("the bar's own button runs", 1, undone)
        assertEquals("a tap on the message bar reached the row under it", emptyList<Int>(), opened)

        // Phần đệm: mép trên của thanh tab, mép trên của thanh phát nhỏ (vạch tiến độ) - và giữ lâu.
        val density = rule.density.density
        rule.onRoot().performTouchInput {
            click(Offset(host.left.value * density + 2f, host.top.value * density + 1f))
            click(Offset(mini.right.value * density - 2f, mini.top.value * density + 1f))
            longClick(Offset(mini.left.value * density + width * 0.3f, mini.top.value * density + 2f))
        }
        rule.waitForIdle()
        assertEquals("a tap on the chrome padding reached a row", emptyList<Int>(), opened)
    }
}
