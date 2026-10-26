package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.Recomposer
import androidx.compose.runtime.remember
import androidx.compose.ui.test.assertIsSelected
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.assertContentDescriptionEquals
import androidx.compose.ui.test.assertCountEquals
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasContentDescription
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
import vn.abook.player.Playback
import vn.abook.player.ui.nowplaying.DemoReadAlongSource
import vn.abook.player.ui.nowplaying.ReadAlongSource
import vn.abook.player.ui.nowplaying.RepoNowPlayingModel
import vn.abook.player.ui.data.FakePlaybackCore
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.LoadRequest
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

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
    private val settingsCore = FakeSettingsCore()
    private val settings = SettingsRepo(settingsCore, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)

    private fun repo(playing: Boolean? = null): PlayerRepo {
        val core = FakePlaybackCore(playerSnapshot(chapter = if (playing == null) null else 1, playing = playing == true))
        return PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
    }

    private fun show(dark: Boolean = false, library: LibraryState = LibraryState.Ready(books), player: PlayerRepo = repo(), readAlong: ReadAlongSource = ReadAlongSource.None) {
        rule.setContent {
            AbookTheme(dark) {
                scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                AppShell(
                    shell, library, player, CoverLoader(1 shl 20), SettingsEnv(settings, ThemeReveal(scope)),
                    nowPlaying = remember(player, readAlong) { RepoNowPlayingModel(player, scope, readAlong) }, sampleClock = false,
                )
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
        rule.onNodeWithTag("settings_screen").assertIsDisplayed()
        shot("shell_settings_dark")
    }

    @Test
    fun settingsGroupSlidesInAndBackReturnsToTheList() {
        show()
        rule.onNodeWithTag("tab_settings").performClick()
        rule.onNodeWithTag("settings_look").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("settings_look_screen").assertIsDisplayed()
        assertEquals(1, shell.nav.stack.size)
        shot("shell_settings_look_light")
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithTag("settings_look_screen").assertDoesNotExist()
        rule.onNodeWithTag("settings_screen").assertIsDisplayed()
    }

    @Test
    fun settingsGroupPushHalfwayIsOnTheRightHalf() {
        show()
        rule.onNodeWithTag("tab_settings").performClick()
        rule.waitForIdle()
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("settings_sleep").performClick()
        rule.mainClock.advanceTimeBy(150)
        val left = rule.onNodeWithTag("settings_sleep_screen").getUnclippedBoundsInRoot().left
        assert(left > 0.dp && left < 360.dp) { "màn nhóm giữa chừng phải nằm giữa hai mép, left=$left" }
        rule.mainClock.autoAdvance = true
    }

    @Test
    fun bookScreenLightAndBack() {
        show()
        rule.onAllNodesWithTag("book_cell")[0].performClick()
        rule.onNodeWithTag("book_title").assertIsDisplayed()
        // Khung thử không có nguồn sách (BookSource.None): trang nói rõ chưa có chương, không có nút phát giả. Nút phát có ở BookScreenTest.
        rule.onNodeWithText("Sách chưa có chương nào nghe được trên máy này.").assertIsDisplayed()
        rule.onNodeWithText("Chương").assertDoesNotExist()
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

    // ---- cửa sổ Đang nghe nở ra từ thanh phát nhỏ thật ----

    private fun back() = rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }

    @Test
    fun tappingTheMiniPlayerOpensTheWindowAndBackClosesItLeavingTheLibraryAlone() {
        show(player = repo(playing = false))
        rule.waitForIdle()
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        assertEquals("Đang nghe không còn là màn con", 0, shell.nav.stack.size)
        shot("shell_now_playing_open_light")
        back()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
        rule.onNodeWithTag("library_grid").assertIsDisplayed()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        assertEquals(0, shell.nav.stack.size)
    }

    @Test
    fun midTransitionTheCoverFliesBetweenTheMiniAndTheFullPosition() {
        show(player = repo(playing = true))
        rule.waitForIdle()
        val mini = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("mini_open").performClick()
        rule.mainClock.advanceTimeBy(160)
        shot("shell_now_playing_mid_light")
        val mid = rule.onNodeWithTag("player_cover").getUnclippedBoundsInRoot()
        rule.mainClock.advanceTimeBy(1000)
        val full = rule.onNodeWithTag("player_cover").getUnclippedBoundsInRoot()
        // Bìa nhỏ nằm trong thanh phát ở đáy; bìa lớn ở giữa màn: giữa chừng nó đang ở khoảng giữa hai chỗ ấy, cả toạ độ lẫn cỡ.
        assert(mid.top < mini.top && mid.top > full.top) { "bìa giữa chừng phải nằm giữa thanh nhỏ và màn đầy: mini=$mini mid=$mid full=$full" }
        // Cỡ bìa giữa chừng do sharedBounds co giãn nội dung (ScaleToBounds) nên toạ độ bố cục vẫn là cỡ đầy; cỡ nhìn thấy kiểm trên ảnh shell_now_playing_mid_light.
        rule.mainClock.autoAdvance = true
    }

    @Test
    fun backWithTheWindowOpenOverABookPageClosesOnlyTheWindow() {
        show(player = repo(playing = false))
        rule.waitForIdle()
        rule.onNodeWithTag("tab_library").performClick()
        // Mở trang sách rồi cửa sổ (từ chỗ khác thanh nhỏ, vd. menu): Back đóng cửa sổ, trang sách vẫn nằm đó.
        rule.onAllNodesWithTag("book_cell")[0].performClick()
        rule.waitForIdle()
        rule.runOnUiThread { shell.window.open() }
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        back()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
        rule.onNodeWithTag("book_screen").assertIsDisplayed()
        assertEquals(1, shell.nav.stack.size)
    }

    @Test
    fun readAlongFromTheBookMenuLoadsTheBookPausedAndOpensTheWindowInReadingMode() {
        val core = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        val readable = List(3) { ListenBook("b$it", "Tên sách số ${it + 1}", "Tác giả", chaptersTotal = 5, chaptersAvailable = 5) }
        val repo = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { id -> LoadRequest(id, "Tên sách", "", listOf(Playback.Chapter(1, "Chương 1", "", 600.0, "texts/1.txt")), 1, 30.0, 1.0) }).also { it.attach() }
        show(library = LibraryState.Ready(readable), player = repo, readAlong = DemoReadAlongSource)
        rule.waitForIdle()
        rule.onNodeWithTag("mini_player").assertDoesNotExist()
        rule.onAllNodesWithTag("book_cell")[0].performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("book_more").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("menu_read").performClick()
        rule.waitForIdle()
        assertEquals("nạp dừng ở chỗ nghe tiếp, không tự phát", listOf(false), core.loads.map { it.autoplay })
        assertEquals(emptyList<String>(), core.calls)
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        rule.onNodeWithTag("mode_read").assertIsSelected()
        shot("shell_read_along_from_book_light")
        back()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
        rule.onNodeWithTag("book_screen").assertIsDisplayed()
        assertEquals(1, shell.nav.stack.size)
    }

    @Test
    fun theWindowOpenOrClosedLeavesExactlyOneListenerOnThePlaybackCore() {
        val core = FakePlaybackCore(playerSnapshot(playing = false))
        val repo = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
        show(player = repo)
        rule.waitForIdle()
        assertEquals(1, core.listeners.size)
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("mode_read").performClick()
        rule.waitForIdle()
        assertEquals(1, core.listeners.size)
        back()
        rule.waitForIdle()
        assertEquals(1, core.listeners.size)
    }

    @Test
    fun clockTicksRecomposeNeitherTheShellNorTheOpenWindow() {
        val core = FakePlaybackCore(playerSnapshot(playing = true))
        val repo = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
        show(player = repo)
        rule.waitForIdle()
        fun ticks(at: Double, step: Double) = rule.runOnUiThread { repeat(20) { core.emit(playerSnapshot(playing = true, position = at + it * step, kind = "tick")) } }
        fun changes() = Recomposer.runningRecomposers.value.sumOf { it.changeCount }
        var before = changes()
        ticks(20.0, 0.5)
        rule.waitForIdle()
        assertEquals("thanh nhỏ đóng: nhịp chỉ vẽ lại vạch tiến độ", before, changes())
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("mode_read").performClick()
        rule.waitForIdle()
        // Chữ mm:ss đổi mỗi giây (đúng một vùng nhỏ dựng lại); các nhịp trong CÙNG một giây thì không dựng lại gì - kể cả thanh tua, chữ Đọc theo.
        ticks(30.0, 0.0)
        rule.waitForIdle()
        before = changes()
        ticks(30.0, 0.04)
        rule.waitForIdle()
        assertEquals("cửa sổ mở: nhịp trong một giây không dựng lại gì", before, changes())
    }

    @Test
    fun theWindowContentIsNotComposedWhileCollapsed() {
        show(player = repo(playing = false))
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
        rule.onNodeWithTag("now_playing_bounds").assertDoesNotExist()
        rule.onNodeWithTag("mini_open").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertIsDisplayed()
        rule.onNodeWithTag("collapse_player").performClick()
        rule.waitForIdle()
        rule.onNodeWithTag("now_playing").assertDoesNotExist()
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

    // ---- một cửa "Đang nghe" ----

    @Test
    fun aFreshLaunchShowsTheLastBookPausedInTheMiniBarAndPlayStartsThatBookAtItsSpot() {
        // App vừa mở, lõi phát trống, người dùng đã nghe cuốn b3 tới chương 7, 12:04.
        val core = FakePlaybackCore(playerSnapshot(book = "", chapter = null), simulate = true)
        val last = LoadRequest("b3", books[3].title, "", emptyList(), 7, 724.0, 1.0)
        val repo = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }, { last }).also { it.attach() }
        show(player = repo)
        rule.waitForIdle()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        rule.onNodeWithTag("mini_play").assertContentDescriptionEquals("Phát")
        rule.onNodeWithText("Chương 7").assertIsDisplayed()
        // Một cửa: trên màn chỉ có MỘT nút phát / dừng, dù cuốn đang nghe cũng nằm trong lưới; thư viện không có hàng "Đang nghe".
        rule.onAllNodes(hasContentDescription("Phát") or hasContentDescription("Tạm dừng"), useUnmergedTree = true).assertCountEquals(1)
        rule.onNodeWithTag("continue_row").assertDoesNotExist()
        shot("shell_mini_restored_light")
        assertEquals("chưa phát gì", emptyList<String>(), core.calls)
        rule.onNodeWithTag("mini_play").performClick()
        rule.waitForIdle()
        assertEquals(listOf("toggle"), core.calls)
        assertEquals("phát đúng cuốn đã nạp, không nạp lại", listOf("b3"), core.loads.map { it.id })
        assertEquals(7, core.loads.single().startChapterId)
        assertEquals(724.0, core.loads.single().startSeconds, 0.0)
        assertEquals(true, repo.state.value.playing)
        assertEquals("b3", repo.state.value.bookId)
        assertEquals(724_000L, repo.clock.positionMs.value)
        rule.onNodeWithTag("mini_play").assertContentDescriptionEquals("Tạm dừng")
    }
}
