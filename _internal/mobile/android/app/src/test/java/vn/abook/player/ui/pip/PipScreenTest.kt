package vn.abook.player.ui.pip

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.text.BasicText
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.FakePlaybackCore
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.PlayerState
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.nowplaying.RepoNowPlayingModel
import vn.abook.player.ui.nowplaying.ReadAlongSource
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.screens.SettingsGroupScreen
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

/**
 * Cửa sổ nhỏ (PiP) trong giao diện: nội dung PiP sáng / tối (ảnh Roborazzi), nút "Cửa sổ mini" ở Đang nghe (chỉ khi máy cho PiP), khung chỉ còn nội dung PiP
 * và đóng mọi lớp phủ khi vào PiP, công tắc "Tự mở cửa sổ mini" ở Cài đặt.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class PipScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val books = List(4) { ListenBook("b$it", "Tên sách số ${it + 1}", "Tác giả ${it + 1}") }
    private lateinit var shell: ShellState
    private val settingsCore = FakeSettingsCore()
    private val settings = SettingsRepo(settingsCore, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)

    private fun repo(playing: Boolean = true, position: Double = 150.0): PlayerRepo {
        val core = FakePlaybackCore(playerSnapshot(chapter = 1, playing = playing, position = position, duration = 600.0))
        return PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
    }

    private fun showShell(pip: PipControl?, dark: Boolean = false, player: PlayerRepo = repo()) {
        rule.setContent {
            AbookTheme(dark) {
                val scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                AppShell(
                    shell, LibraryState.Ready(books), player, CoverLoader(1 shl 20), SettingsEnv(settings, ThemeReveal(scope), pip = pip),
                    nowPlaying = remember(player) { RepoNowPlayingModel(player, scope, ReadAlongSource.None) }, sampleClock = false, pip = pip,
                )
            }
        }
        rule.waitForIdle()
    }

    private fun pipContent(dark: Boolean) {
        val state = PlayerState(bookId = "b1", bookTitle = "Tắt đèn", chapterId = 1, chapterTitle = "Chương 1", playing = true, durationMs = 600_000)
        rule.setContent {
            AbookTheme(dark) {
                Box(Modifier.size(240.dp, 360.dp)) { PipContent(state, { 150_000L }, CoverLoader(1 shl 20)) }
            }
        }
        rule.waitForIdle()
    }

    @Test
    fun pipContentLight() {
        pipContent(dark = false)
        rule.onNodeWithTag("pip_content").assertIsDisplayed()
        rule.onNodeWithTag("pip_progress").assertIsDisplayed()
        rule.onNodeWithTag("pip_content").captureRoboImage("src/test/snapshots/pip_content_light.png")
    }

    @Test
    fun pipContentDark() {
        pipContent(dark = true)
        rule.onNodeWithTag("pip_content").assertIsDisplayed()
        rule.onNodeWithTag("pip_content").captureRoboImage("src/test/snapshots/pip_content_dark.png")
    }

    @Test
    fun theProgressStripIsThinAndAtTheBottomAndCarriesNoText() {
        pipContent(dark = false)
        val frame = rule.onNodeWithTag("pip_content").getUnclippedBoundsInRoot()
        val strip = rule.onNodeWithTag("pip_progress").getUnclippedBoundsInRoot()
        assertEquals(3f, (strip.bottom - strip.top).value, 0.01f)
        assertEquals(frame.bottom.value, strip.bottom.value, 0.01f)
        assertEquals((frame.right - frame.left).value, (strip.right - strip.left).value, 0.01f)
    }

    @Test
    fun nowPlayingHasTheMiniWindowButtonOnlyWhenPipIsAvailable() {
        showShell(PipControl(available = false))
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        assertEquals(0, rule.onAllNodesWithTagCount("player_mini"))
    }

    @Test
    fun theMiniWindowButtonEntersPipAtOnce() {
        var entered = 0
        showShell(PipControl(available = true) { entered++ })
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("player_mini").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/pip_now_playing_button_light.png")
        rule.onNodeWithTag("player_mini").performClick()
        assertEquals(1, entered)
    }

    @Test
    fun theMiniWindowButtonShowsInTheDarkNowPlayingToo() {
        showShell(PipControl(available = true), dark = true)
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("player_mini").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/pip_now_playing_button_dark.png")
    }

    @Test
    fun inPipTheShellDrawsOnlyThePipContentAndClosesEverySheet() {
        val pip = PipControl(available = true)
        showShell(pip)
        rule.runOnUiThread { shell.sheets.show { BasicText("Bảng thử") } }
        rule.waitForIdle()
        assertTrue(shell.sheets.current != null)
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        rule.runOnUiThread { pip.active = true }
        rule.waitForIdle()
        rule.onNodeWithTag("pip_content").assertIsDisplayed()
        assertEquals(0, rule.onAllNodesWithTagCount("tab_library"))
        assertEquals(0, rule.onAllNodesWithTagCount("mini_player"))
        assertNull("bảng trượt đã đóng như Back", shell.sheets.current)
    }

    @Test
    fun leavingPipOpensTheFullAppOnNowPlaying() {
        val pip = PipControl(available = true)
        showShell(pip)
        rule.runOnUiThread { pip.active = true }
        rule.waitForIdle()
        rule.runOnUiThread { pip.active = false }
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
    }

    private fun showListen(pip: PipControl?) {
        rule.setContent {
            AbookTheme(false) {
                val scope = rememberCoroutineScope()
                val env = remember { SettingsEnv(settings, ThemeReveal(scope), pip = pip) }
                Box(Modifier.size(360.dp, 780.dp)) { SettingsGroupScreen(SettingsGroup.Listen, env, vn.abook.player.ui.components.SheetHost(), onBack = {}) }
            }
        }
        rule.waitForIdle()
    }

    @Test
    fun theSwitchIsInListenSettingsOnByDefaultAndSavesWhenToggled() {
        showListen(PipControl(available = true))
        rule.onNodeWithTag("auto_pip").assertIsDisplayed()
        assertTrue(settings.state.value.autoPip)
        rule.onNodeWithTag("auto_pip").performClick()
        assertFalse(settings.state.value.autoPip)
        assertFalse(settingsCore.saved.last().getBoolean("autoPip"))
        rule.onNodeWithTag("auto_pip").performClick()
        assertTrue(settings.state.value.autoPip)
    }

    @Test
    fun theSwitchIsHiddenWhenPipIsNotAvailable() {
        showListen(PipControl(available = false))
        assertEquals(0, rule.onAllNodesWithTagCount("auto_pip"))
    }

    private fun androidx.compose.ui.test.junit4.ComposeContentTestRule.onAllNodesWithTagCount(tag: String) =
        onAllNodesWithTag(tag).fetchSemanticsNodes().size
}
