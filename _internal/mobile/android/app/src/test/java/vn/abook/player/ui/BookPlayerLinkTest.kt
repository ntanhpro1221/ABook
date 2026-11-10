package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsNotDisplayed
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onRoot
import androidx.compose.ui.test.performClick
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
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
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.ownsBottomBar
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.studio.StudioTab
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

/**
 * Trang sách và trình phát của cùng một cuốn nối nhau 1 chạm trong khung thật (chủ sách 09-11: "không tìm thấy chỗ nào để mở vào giao diện player của quyển này"): DESIGN.md L3b, L3c.
 * Đếm chạm như flowTaps của web. Phần nút chính / dòng chương đang phát ở BookScreenTest (khung này không có nguồn chương).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class BookPlayerLinkTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val book = ListenBook("b1", "Tắt đèn", "Ngô Tất Tố")
    private val other = ListenBook("b2", "Số đỏ", "Vũ Trọng Phụng")
    private lateinit var shell: ShellState
    private var taps = 0

    private fun show(hasTrack: Boolean = true, dark: Boolean = false) {
        val core = FakePlaybackCore(playerSnapshot(chapter = if (hasTrack) 1 else null))
        val player = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach(this) }
        val settings = SettingsRepo(FakeSettingsCore(), CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)
        rule.setContent {
            AbookTheme(dark) {
                val scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                AppShell(shell, LibraryState.Ready(listOf(book, other)), player, CoverLoader(1 shl 20), SettingsEnv(settings, ThemeReveal(scope)), sampleClock = false, demo = true)
            }
        }
        rule.waitForIdle()
    }

    private fun push(destination: Destination) {
        rule.runOnUiThread { shell.nav.push(destination) }
        rule.waitForIdle()
    }

    private fun tap(tag: String) {
        taps++
        rule.onNodeWithTag(tag).performClick()
        rule.waitForIdle()
    }

    private fun openWindow() {
        rule.runOnUiThread { shell.window.open() }
        rule.waitForIdle()
        assertTrue(shell.window.expanded)
    }

    @Test
    fun miniBarStaysOnEveryScreenWithoutItsOwnBottomBar() {
        show()
        for (route in listOf(Destination.Book(book), Destination.Settings(SettingsGroup.Look), Destination.StudioProject("", "x", StudioTab.Chapters))) {
            push(route)
            rule.onNodeWithTag("mini_open").assertIsDisplayed()
            rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
            rule.waitForIdle()
        }
    }

    @Test
    fun miniBarOnABookPageOpensThePlayerInOneTap() {
        show()
        push(Destination.Book(book))
        tap("mini_open")
        assertTrue("trình phát phải mở", shell.window.expanded)
        assertEquals(1, taps)
    }

    @Test
    fun screensWithTheirOwnBottomBarHideTheMiniBar() {
        show()
        push(Destination.EditBook(book))
        rule.onNodeWithTag("mini_open").assertIsNotDisplayed()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        rule.onNodeWithTag("mini_open").assertIsDisplayed()
        push(Destination.Export(book, ExportFormat.Mp3))
        rule.onNodeWithTag("mini_open").assertIsNotDisplayed()
    }

    @Test
    fun theHideListIsExactlyTheScreensWithBottomBars() {
        val own = listOf(
            Destination.AddBook, Destination.ImportReview(1), Destination.ImportChapter(1, 0), Destination.EditBook(book), Destination.EditChapter(book, 1),
            Destination.CropCover(book, "content://x"), Destination.CoverSearch(book), Destination.Export(book), Destination.StudioNew(""),
        )
        assertTrue(own.all { it.ownsBottomBar() })
        assertFalse(Destination.Book(book).ownsBottomBar())
        assertFalse(Destination.Studio("").ownsBottomBar())
    }

    @Test
    fun aBookWithoutATrackHasNoStripUnderTheScreen() {
        show(hasTrack = false)
        push(Destination.Book(book))
        val screen = rule.onNodeWithTag("screen_top").getUnclippedBoundsInRoot()
        rule.onNodeWithTag("mini_player").assertDoesNotExist()
        val tab = rule.onNodeWithTag("tab_library").getUnclippedBoundsInRoot()
        assertEquals("the persistent tab bar keeps the same content baseline", tab.top.value - 1f, screen.bottom.value, 1f)
    }

    @Test
    fun theScreenStopsAboveTheMiniBarAndTheBarReachesTheBottom() {
        show()
        push(Destination.Book(book))
        val screen = rule.onNodeWithTag("screen_top").getUnclippedBoundsInRoot()
        val bar = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        assertEquals("màn dừng ngay trên thanh", bar.top.value, screen.bottom.value, 1f)
        // Màn con giữ thanh tab ở đúng đường gốc: thanh phát nhỏ đứng ngay trên vạch kẻ của thanh tab, không tự chừa đáy lần nữa.
        val tab = rule.onNodeWithTag("tab_library").getUnclippedBoundsInRoot()
        assertEquals("thanh phát nhỏ đứng trên thanh tab", tab.top.value - 1f, bar.bottom.value, 1f)
    }

    @Test
    fun coverOfTheLoadedBookOpensThePlayerInOneTap() {
        show()
        push(Destination.Book(book))
        tap("book_cover")
        assertTrue(shell.window.expanded)
        assertEquals("L3b: 1 chạm", 1, taps)
    }

    @Test
    fun coverOfAnotherBookDoesNothing() {
        show()
        push(Destination.Book(other))
        tap("book_cover")
        assertFalse(shell.window.expanded)
    }

    @Test
    fun bookNameInThePlayerOpensItsPageInOneTapAndBackReturnsHere() {
        show()
        openWindow()
        tap("player_book")
        assertEquals("L3c: 1 chạm", 1, taps)
        assertFalse("trình phát thu lại", shell.window.expanded)
        assertEquals(Destination.Book(book), shell.nav.stack.top?.destination)
        rule.onNodeWithTag("book_screen").assertIsDisplayed()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        assertTrue("Back về gốc", shell.nav.stack.isEmpty)
    }

    @Test
    fun bookNameDoesNotPushTheSamePageTwice() {
        show()
        push(Destination.Book(book))
        openWindow()
        tap("player_book")
        assertEquals(1, shell.nav.stack.size)
        assertFalse(shell.window.expanded)
    }

    @Test
    fun bookNameReturnsToThePageAlreadyInTheStack() {
        show()
        push(Destination.Book(book))
        push(Destination.Settings(SettingsGroup.Look))
        openWindow()
        tap("player_book")
        assertEquals(1, shell.nav.stack.size)
        assertEquals(Destination.Book(book), shell.nav.stack.top?.destination)
    }

    /**
     * Màn con: thanh tab + thanh phát nhỏ đứng đúng đường gốc. Dưới hàng tab chỉ MỘT lần chừa đáy theo inset đo trên máy thật (không phải hai lần, không phải sàn 24 dp cũ),
     * thanh phát nhỏ ngồi ngay trên vạch kẻ của thanh tab.
     */
    private fun subScreenBottomGap(insets: BottomInsets, expected: Float) {
        show()
        push(Destination.Book(book))
        rule.applyBottomInsets(insets)
        val root = rule.onRoot().getUnclippedBoundsInRoot()
        val tab = rule.onNodeWithTag("tab_library").getUnclippedBoundsInRoot()
        val mini = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        assertEquals("${insets.name}: hàng tab cách mép dưới", expected, (root.bottom - tab.bottom).value, 0.5f)
        assertEquals("${insets.name}: thanh phát nhỏ đứng trên thanh tab", tab.top.value - 1f, mini.bottom.value, 0.5f)
        assertEquals(expected, insets.clearance(rule.density.density).value, 0.5f)
    }

    @Test fun subScreenBottomBarsOppo() = subScreenBottomGap(OppoHiddenBar, 12f)

    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi")
    fun subScreenBottomBarsEmulatorGesture() = subScreenBottomGap(EmulatorGesture, 24f)

    @Test @Config(sdk = [35], qualifiers = "w411dp-h914dp-420dpi")
    fun subScreenBottomBarsEmulatorThreeButton() = subScreenBottomGap(EmulatorThreeButton, 48f)

    @Test
    fun shots() {
        show()
        push(Destination.Book(book))
        rule.onRoot().captureRoboImage("src/test/snapshots/link_book_mini_light.png")
        openWindow()
        rule.onRoot().captureRoboImage("src/test/snapshots/link_np_book_light.png")
    }

    @Test
    fun shotsDark() {
        show(dark = true)
        push(Destination.Book(book))
        rule.onRoot().captureRoboImage("src/test/snapshots/link_book_mini_dark.png")
        openWindow()
        rule.onRoot().captureRoboImage("src/test/snapshots/link_np_book_dark.png")
    }
}
