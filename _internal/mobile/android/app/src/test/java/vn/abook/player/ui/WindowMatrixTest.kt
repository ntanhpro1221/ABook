package vn.abook.player.ui

import android.content.res.Configuration
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.semantics.getOrNull
import androidx.compose.ui.test.*
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.*
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.nav.Tab
import vn.abook.player.ui.nowplaying.*
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.components.BasicText
import androidx.compose.foundation.layout.Column
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal
import java.io.File

/** Exercise the actual shell, screens and sheets through resize on one retained instance. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w1280dp-h1000dp-mdpi")
class WindowMatrixTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private data class Frame(val width: Int, val height: Int, val font: Float = 1f)
    private val frame = mutableStateOf(Frame(360, 780))
    private lateinit var shell: ShellState
    private val model = FakeNowPlayingModel()
    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val books = DemoLibrary.books(12)
    private val core = FakePlaybackCore(playerSnapshot(chapter = 1))
    private val player = PlayerRepo(core, scope, Dispatchers.Unconfined, { null }, { null }).also { it.attach(this) }
    private val music = vn.abook.player.ui.music.library.LibraryState(
        vn.abook.player.ui.music.library.FakeLibrarySource(), scope, vn.abook.player.ui.music.library.SilentPreview(), {}, Dispatchers.Unconfined)

    private fun show() {
        rule.setContent {
            val current = frame.value
            val config = Configuration(LocalConfiguration.current).apply {
                screenWidthDp = current.width; screenHeightDp = current.height; fontScale = current.font
            }
            val density = LocalDensity.current
            CompositionLocalProvider(LocalConfiguration provides config, LocalDensity provides Density(density.density, current.font)) {
                AbookTheme(false) {
                    val uiScope = rememberCoroutineScope()
                    shell = remember { ShellState(uiScope) }
                    val settings = remember { SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined) }
                    val studio = remember { StudioHub(FakeStudioSource().also { it.books = listOf(studioBook("matrix", title = "Dự án kiểm tra cửa sổ", running = true, canPause = true)) }, scope) }
                    Box(Modifier.requiredSize(current.width.dp, current.height.dp).testTag("matrix_frame"), contentAlignment = Alignment.TopStart) {
                        AppShell(shell, LibraryState.Ready(books), player, remember { CoverLoader() },
                            remember { SettingsEnv(settings, ThemeReveal(uiScope), musicLibrary = music) },
                            books = remember { DemoBookSource { books } }, nowPlaying = model, sampleClock = false, demo = true, studio = studio)
                    }
                }
            }
        }
        rule.waitForIdle()
    }

    private fun matrix(name: String, check: () -> Unit = {}) {
        val frames = listOf(360 to 780, 800 to 360, 640 to 320, 600 to 240, 320 to 240, 240 to 200)
        for (font in listOf(1f, 1.3f, 2f)) for ((w, h) in frames) {
            rule.runOnIdle { frame.value = Frame(w, h, font) }
            rule.waitForIdle()
            check()
            val nodes = rule.onAllNodes(SemanticsMatcher("text layout") { it.config.contains(SemanticsActions.GetTextLayoutResult) }, useUnmergedTree = true).fetchSemanticsNodes()
            val viewport = rule.onNodeWithTag("matrix_frame").fetchSemanticsNode().boundsInRoot
            var overflow = 0
            for (node in nodes) {
                assertTrue("$name invalid width", node.size.width >= 0)
                assertTrue("$name invalid height", node.size.height >= 0)
                val results = mutableListOf<TextLayoutResult>()
                node.config[SemanticsActions.GetTextLayoutResult].action?.invoke(results)
                val visible = node.boundsInRoot.overlaps(viewport) && node.boundsInRoot.width > 0 && node.boundsInRoot.height > 0 &&
                    generateSequence(node) { it.parent }.none { it.config.contains(SemanticsProperties.HideFromAccessibility) }
                if (visible) {
                    fun clipped(result: TextLayoutResult): Boolean =
                        result.layoutInput.maxLines == Int.MAX_VALUE &&
                            (result.multiParagraph.height > result.size.height + 1f ||
                                (0 until result.lineCount).any { result.getLineRight(it) > result.size.width + 1f })
                    overflow += results.count(::clipped)
                    System.getenv("ABOOK_WINDOW_REPORT")?.let { path ->
                        for (result in results.filter(::clipped)) {
                            File(path + ".overflow.txt").appendText("$name $w/$h font=$font ${result.size} ${result.layoutInput.text.text.take(120)}\n")
                        }
                    }
                }
            }
            // Overflow includes deliberate ellipsis and viewport-edge clipping; preserve it for magnified review.
            System.getenv("ABOOK_WINDOW_REPORT")?.let { path -> File(path).appendText("$name,$w,$h,$font,${nodes.size},$overflow\n") }
        }
    }

    @Test fun library() { show(); matrix("library") }
    @Test fun book() {
        show(); rule.runOnIdle { shell.nav.push(Destination.Book(books[1])) }; rule.waitForIdle()
        matrix("book") { rule.onNodeWithTag("book_screen").assertExists() }
    }
    @Test fun settings() {
        show(); rule.runOnIdle { shell.tabs.select(Tab.Settings) }; rule.waitForIdle()
        matrix("settings")
    }
    @Test fun studio() {
        show(); rule.runOnIdle { shell.tabs.select(Tab.Studio) }; rule.waitForIdle()
        matrix("studio")
    }
    @Test fun music() {
        show(); rule.runOnIdle { shell.tabs.select(Tab.Music) }; rule.waitForIdle()
        matrix("music") { rule.onNodeWithTag("music_screen").assertExists() }
    }
    @Test fun listeningAndReadingKeepPlaybackAcrossResize() {
        show(); rule.runOnIdle { shell.window.open() }; rule.waitForIdle()
        matrix("listen")
        rule.runOnIdle { shell.window.reading = true }
        matrix("read") { assertTrue(shell.window.reading) }
        assertFalse("resize must not seek, restart or toggle audio", model.actions.any { it == "toggle" || it.startsWith("seek") || it.startsWith("jump") || it == "restart" })
    }
    @Test fun playerSheetsRemainOpenAcrossResize() {
        show(); rule.runOnIdle { shell.window.open() }; rule.waitForIdle()
        for (sheet in PlayerSheet.entries) {
            rule.runOnIdle { shell.window.openSheet(sheet) }; rule.waitForIdle()
            matrix("sheet-$sheet") { assertEquals(sheet, shell.window.sheet); assertTrue(shell.window.sheetOpen) }
        }
    }

    @Test fun manuallyScrolledReadingAnchorSurvivesMovingBetweenColumns() {
        show()
        rule.runOnIdle { shell.window.reading = true; shell.window.open() }
        rule.waitForIdle()
        val viewport = shell.window.readViewport(model.state.value.bookId, model.state.value.chapterId)
        rule.runOnIdle {
            viewport.following.value = false
            runBlocking { viewport.list.scrollToItem(30, 7) }
        }
        rule.waitForIdle()
        for ((width, height) in listOf(800 to 360, 640 to 320, 360 to 780)) {
            rule.runOnIdle { frame.value = Frame(width, height) }
            rule.waitForIdle()
            assertSame(viewport, shell.window.readViewport(model.state.value.bookId, model.state.value.chapterId))
            assertEquals(30, viewport.list.firstVisibleItemIndex)
            assertFalse(viewport.following.value)
        }
    }

    @Test fun genericSheetAndSortMenuStayScrollableInShortWindows() {
        show()
        rule.runOnIdle {
            shell.sheets.show {
                Column {
                    repeat(20) { BasicText("Hàng kiểm tra cửa sổ số $it") }
                    BasicText("Hàng cuối cùng", Modifier.testTag("matrix_sheet_last"))
                }
            }
        }
        rule.waitForIdle()
        matrix("generic-sheet") { assertNotNull(shell.sheets.current) }
        rule.onNodeWithTag("matrix_sheet_last").performScrollTo().assertIsDisplayed()
        rule.runOnIdle { shell.sheets.dismiss(); shell.library.openMenu() }
        rule.waitForIdle()
        matrix("sort-menu") { rule.onNodeWithTag("sort_menu").assertExists() }
    }

    @Test fun settingsGroupsAndStudioPages() {
        show()
        val destinations = SettingsGroup.entries.map { "settings-${it.name}" to Destination.Settings(it) } +
            listOf("studio-home" to Destination.Studio("")) +
            StudioTab.entries.map { "studio-${it.name}" to Destination.StudioProject("", "matrix", it) } +
            StudioSubKind.entries.map { "studio-sub-${it.name}" to Destination.StudioSub("", "matrix", it) }
        for ((name, destination) in destinations) {
            rule.runOnIdle { shell.nav.popToRoot() }; rule.waitForIdle()
            rule.runOnIdle { shell.nav.push(destination) }; rule.waitForIdle()
            matrix(name)
        }
    }
}
