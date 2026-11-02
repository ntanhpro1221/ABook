package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.hasContentDescription
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onRoot
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.CoverLoader
import vn.abook.player.ui.data.DemoLibrary
import vn.abook.player.ui.data.FakePlaybackCore
import vn.abook.player.ui.data.FakeSettingsCore
import vn.abook.player.ui.data.LibraryState
import vn.abook.player.ui.data.ListenBook
import vn.abook.player.ui.data.PlayerRepo
import vn.abook.player.ui.data.SettingsGroup
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.export.ExportFormat
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.studio.StudioSubKind
import vn.abook.player.ui.studio.StudioTab
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal
import vn.abook.player.ui.voice.VoicePage
import java.io.File

/**
 * Mọi màn con phải dựng ra thứ gì đó dùng được và có lối ra, KỂ CẢ khi kho của nó không có (bản thử đo đạc không nối máy tính, không xuất sách: soát điện thoại thật 02-11
 * - "Nối máy tính", "Xuất MP3", "Xuất M4B" mở khung đen không nút ←). Khung ở đây giống bản thử: không kho nhập, sửa, xuất, Studio, máy tính, giọng. Mỗi [Destination] được đẩy
 * lên, phải có chữ, có nút "Quay lại", và Back đưa về gốc. Thêm một [Destination] mới mà quên khỏi danh sách dưới đây thì test thứ hai đỏ.
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ShellRoutesTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val books = DemoLibrary.books(6)
    private val book: ListenBook = books[0]
    private val textBook = ListenBook("t1", "Sách chỉ có chữ", "Tác giả", textOnly = true)

    private val routes: List<Destination> = listOf(
        Destination.AddBook,
        Destination.ImportReview(1),
        Destination.ImportChapter(1, 0),
        Destination.EditBook(book),
        Destination.EditChapter(book, 1),
        Destination.CropCover(book, "content://x"),
        Destination.CoverSearch(book),
        Destination.Book(book),
        Destination.Export(book, ExportFormat.Mp3),
        Destination.Export(book, ExportFormat.M4b),
        Destination.Export(textBook),
        *SettingsGroup.entries.map { Destination.Settings(it) }.toTypedArray(),
        *DevicesPage.entries.map { Destination.Devices(it) }.toTypedArray(),
        *VoicePage.entries.map { Destination.Voice(it) }.toTypedArray(),
        Destination.Studio(""),
        Destination.StudioNew(""),
        Destination.StudioProject("", "b", StudioTab.Chapters),
        *StudioSubKind.entries.map { Destination.StudioSub("", "b", it) }.toTypedArray(),
    )

    @Test
    fun everyDestinationIsListedHere() {
        val source = File("src/main/java/vn/abook/player/ui/nav/Nav.kt").readText()
        val declared = Regex("""(?m)^\s*(?:data class|data object|object)\s+(\w+).*:\s*Destination\s*$""").findAll(source).map { it.groupValues[1] }.toSet()
        assertTrue("không đọc được Destination từ Nav.kt: $declared", declared.size >= 15)
        val covered = routes.map { it::class.simpleName!! }.toSet()
        assertEquals("Destination chưa có trong ShellRoutesTest.routes", emptySet<String>(), declared - covered)
    }

    private lateinit var shell: ShellState
    private lateinit var scope: CoroutineScope

    private fun show(dark: Boolean) {
        val core = FakePlaybackCore(playerSnapshot(chapter = null, playing = false))
        val player = PlayerRepo(core, CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null }).also { it.attach() }
        val settings = SettingsRepo(FakeSettingsCore(), CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined)
        rule.setContent {
            AbookTheme(dark) {
                scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                AppShell(
                    shell, LibraryState.Ready(books), player, CoverLoader(1 shl 20), SettingsEnv(settings, ThemeReveal(scope)),
                    sampleClock = false, demo = true,
                )
            }
        }
    }

    private fun back() = rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }

    private fun walk(dark: Boolean) {
        show(dark)
        for (route in routes) {
            val name = route.toString().take(80)
            rule.runOnUiThread { shell.nav.push(route) }
            rule.waitForIdle()
            assertEquals("$name: màn không được đẩy lên", 1, shell.nav.stack.size)
            val texts = rule.onAllNodes(SemanticsMatcher.keyIsDefined(SemanticsProperties.Text)).fetchSemanticsNodes().size
            assertTrue("$name: màn trống (không có chữ nào)", texts >= 1)
            val backs = rule.onAllNodes(hasContentDescription("Quay lại")).fetchSemanticsNodes().size
            assertTrue("$name: không có nút ← (Quay lại)", backs >= 1)
            back()
            rule.waitForIdle()
            assertEquals("$name: Back không đưa về gốc", 0, shell.nav.stack.size)
        }
    }

    @Test fun everyRouteHasContentAndABackWayOutInDemoLight() = walk(dark = false)

    @Test fun everyRouteHasContentAndABackWayOutInDemoDark() = walk(dark = true)

    @Test
    fun theUnavailableScreenLooksRight() {
        show(dark = true)
        rule.runOnUiThread { shell.nav.push(Destination.Devices(DevicesPage.Pair)) }
        rule.waitForIdle()
        rule.onRoot().captureRoboImage("src/test/snapshots/shell_unavailable_dark.png")
    }
}
