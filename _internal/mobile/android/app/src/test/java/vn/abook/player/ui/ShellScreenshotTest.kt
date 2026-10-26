package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.FakePlaybackCore
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme

/**
 * Khung native chạy trên JVM (Robolectric): ảnh chụp sáng / tối bằng Roborazzi (ghi: -Proborazzi.test.record=true; so: verifyRoborazziDebug) và
 * kịch bản bấm thật qua cây semantics. Chạy trong `testDebugUnitTest` không cần máy.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ShellScreenshotTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val books = List(12) { ListenBook("b$it", "Tên sách số ${it + 1} khá dài để xuống dòng", "Tác giả ${it + 1}") }
    private lateinit var shell: ShellState
    private lateinit var scope: CoroutineScope

    private fun repo(playing: Boolean? = null): PlayerRepo {
        val core = FakePlaybackCore(playerSnapshot(chapter = if (playing == null) null else 1, playing = playing == true))
        return PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
    }

    private fun show(dark: Boolean = false, library: LibraryState = LibraryState.Ready(books), player: PlayerRepo = repo()) {
        rule.setContent {
            AbookTheme(dark) {
                scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                AppShell(shell, library, player, CoverLoader(1 shl 20))
            }
        }
    }

    private fun shot(name: String) = rule.onRoot().captureRoboImage("src/test/snapshots/$name.png")

    @Test
    fun libraryLight() {
        show()
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
        rule.onNodeWithText("12 cuốn").assertIsDisplayed()
        rule.onNodeWithTag("mini_player").assertDoesNotExist()
        shot("shell_library_light")
    }

    @Test
    fun libraryDark() {
        show(dark = true)
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
        shot("shell_library_dark")
    }

    @Test
    fun emptyLibraryLight() {
        show(library = LibraryState.Ready(emptyList()))
        rule.onNodeWithText("Chưa có sách").assertIsDisplayed()
        shot("shell_empty_light")
    }

    @Test
    fun studioTabLight() {
        show()
        rule.onNodeWithTag("tab_studio").performClick()
        rule.onNodeWithText("Studio từ xa sắp có.").assertIsDisplayed()
        shot("shell_studio_light")
    }

    @Test
    fun settingsTabDark() {
        show(dark = true)
        rule.onNodeWithTag("tab_settings").performClick()
        rule.onNodeWithText("Cài đặt sắp có.").assertIsDisplayed()
        shot("shell_settings_dark")
    }

    @Test
    fun bookScreenLightAndBack() {
        show()
        rule.onAllNodesWithTag("book_cell")[0].performClick()
        rule.onNodeWithTag("book_title").assertIsDisplayed()
        rule.onNodeWithTag("book_primary").assertIsDisplayed()
        shot("shell_book_light")
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithTag("book_screen").assertDoesNotExist()
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
    }

    @Test
    fun pushHalfwayIsOnTheRightHalf() {
        show()
        rule.mainClock.autoAdvance = false
        rule.onAllNodesWithTag("book_cell")[0].performClick()
        rule.mainClock.advanceTimeBy(150)
        val left = rule.onNodeWithTag("book_screen").getUnclippedBoundsInRoot().left
        assert(left > 0.dp && left < 360.dp) { "màn con giữa chừng phải nằm giữa hai mép, left=$left" }
        shot("shell_push_mid_light")
        rule.mainClock.autoAdvance = true
    }

    @Test
    fun predictiveBackMovesTheScreenWithTheFinger() {
        show()
        rule.onAllNodesWithTag("book_cell")[0].performClick()
        rule.waitForIdle()
        for (back in listOf(0.25f, 0.5f, 0.75f)) {
            rule.runOnUiThread { scope.launch { shell.nav.dragBack(back) } }
            rule.waitForIdle()
            assertEquals(back * 360f, rule.onNodeWithTag("book_screen").getUnclippedBoundsInRoot().left.value, 1f)
        }
        rule.runOnUiThread { scope.launch { shell.nav.cancelBack() } }
        rule.waitForIdle()
        assertEquals(0f, rule.onNodeWithTag("book_screen").getUnclippedBoundsInRoot().left.value, 0.5f)
    }

    // ---- thanh phát nhỏ trong khung ----

    @Test
    fun miniPlayerSitsAboveTheTabBarOnEveryRootScreen() {
        show(player = repo(playing = true))
        rule.waitForIdle()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        val mini = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        val tabBar = rule.onNodeWithTag("tab_library").getUnclippedBoundsInRoot()
        assert(mini.bottom <= tabBar.top + 1.dp) { "thanh phát phải nằm trên thanh tab: mini=$mini tab=$tabBar" }
        shot("shell_mini_library_light")
        rule.onNodeWithTag("tab_studio").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        rule.onNodeWithTag("tab_settings").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
    }

    @Test
    fun tappingTheMiniPlayerOpensTheFullPlayerOnce() {
        show(player = repo(playing = false))
        rule.waitForIdle()
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing_screen").assertIsDisplayed()
        assertEquals(1, shell.nav.stack.size)
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing_screen").assertDoesNotExist()
    }

    @Test
    fun theMiniPlayerButtonTogglesPlayback() {
        val core = FakePlaybackCore(playerSnapshot(playing = false))
        val repo = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
        show(player = repo)
        rule.waitForIdle()
        rule.onNodeWithTag("mini_play").performClick()
        assertEquals(listOf("toggle"), core.calls)
    }
}
