package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.unit.dp
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.*
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.*
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.screens.*
import vn.abook.player.ui.shell.*
import vn.abook.player.ui.theme.*

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class GapReviewTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun shellUndoLight() = shellBar(false, false)
    @Test fun shellUndoDark() = shellBar(true, false)
    @Test fun shellDeleteFailureLight() = shellBar(false, true)
    @Test fun shellDeleteFailureDark() = shellBar(true, true)

    private fun shellBar(dark: Boolean, failure: Boolean) {
        val all = listOf(ListenBook("b1", "Dế Mèn phiêu lưu ký", "Tô Hoài"), ListenBook("b2", "Tắt đèn", "Ngô Tất Tố"))
        var library by mutableStateOf<LibraryState>(LibraryState.Ready(all))
        lateinit var deletes: UndoDelete
        lateinit var scope: CoroutineScope
        val playback = FakePlaybackCore(playerSnapshot(playing = true), simulate = true)
        val companion = CompanionRepo(FakeCompanionCore())
        runBlocking { companion.refresh() }
        rule.setContent {
            AbookTheme(dark) {
                scope = rememberCoroutineScope()
                val shell = remember { ShellState(scope) }
                val player = remember { PlayerRepo(playback, scope, Dispatchers.Unconfined, { null }, { null }) }
                LaunchedEffect(Unit) { player.attach() }
                deletes = remember { UndoDelete(scope, { if (failure) "Chưa xoá được" else null }, {
                    library = LibraryState.Ready(all.filterNot { deletes.contains(it.id) })
                }, player::bookRemoved) }
                val settings = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined), ThemeReveal(scope)) }
                AppShell(shell, library, player, CoverLoader(), settings, sampleClock = false, deletions = deletes, companion = companion)
            }
        }
        rule.waitForIdle()
        val miniBefore = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        val tabsBefore = rule.onNodeWithTag("tab_library").getUnclippedBoundsInRoot()
        val contentBefore = rule.onNodeWithTag("library_grid").getUnclippedBoundsInRoot()
        rule.mainClock.autoAdvance = false
        rule.runOnUiThread { scope.launch { deletes.remove("b2") } }
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(64)
        val middle = rule.onNodeWithTag("library_grid").getUnclippedBoundsInRoot()
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        val after = rule.onNodeWithTag("library_grid").getUnclippedBoundsInRoot()
        assertTrue("Content makes room with motion", middle.bottom < contentBefore.bottom && middle.bottom > after.bottom)
        if (failure) {
            rule.mainClock.advanceTimeBy(28_000)
            rule.waitForIdle()
            rule.onNodeWithText("Chưa xoá được").assertIsDisplayed()
            rule.onNodeWithTag("undo_delete").assertDoesNotExist()
        }
        rule.onNodeWithTag("undo_bar").assertIsDisplayed()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        rule.onNodeWithTag("other_players").assertIsDisplayed()
        for (tag in listOf("tab_library", "tab_studio", "tab_settings")) rule.onNodeWithTag(tag).assertIsDisplayed()
        val bar = rule.onNodeWithTag("undo_bar").getUnclippedBoundsInRoot()
        val remote = rule.onNodeWithTag("other_players").getUnclippedBoundsInRoot()
        val mini = rule.onNodeWithTag("mini_player").getUnclippedBoundsInRoot()
        val tabs = rule.onNodeWithTag("tab_library").getUnclippedBoundsInRoot()
        assertTrue(bar.bottom <= remote.top && remote.bottom <= mini.top && mini.bottom <= tabs.top)
        assertEquals(miniBefore, mini)
        assertEquals(tabsBefore, tabs)
        rule.onRoot().captureRoboImage("src/test/snapshots/gap1b_shell_${if (failure) "error" else "undo"}_${if (dark) "dark" else "light"}.png")
        if (failure) {
            rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        } else {
            rule.onNodeWithTag("undo_delete").performClick()
        }
        rule.waitForIdle()
        rule.onNodeWithTag("undo_bar").assertDoesNotExist()
        rule.onNodeWithTag("mini_player").assertIsDisplayed()
        assertTrue(playback.calls.isEmpty())
        rule.onNodeWithTag("mini_play").performClick()
        rule.onNodeWithTag("tab_studio").performClick()
        rule.onNodeWithTag("tab_studio").assertIsSelected()
        assertEquals(listOf("toggle"), playback.calls)
    }

    @Test fun deviceKindsLight() = kinds(false)
    @Test fun deviceKindsDark() = kinds(true)
    private fun kinds(dark: Boolean) {
        val core = FakeCompanionCore()
        core.rows = JSONArray()
        val names = listOf("Máy tính phòng làm việc bên cạnh cửa sổ", "Điện thoại", "Loa phòng khách", "TV phòng ngủ", "Bộ phát", "Google Cast")
        for ((i, kind) in listOf("computer", "phone", "speaker", "tv", "media", "speaker").withIndex()) {
            core.rows.put(JSONObject().put("device", "d$i").put("kind", kind).put("name", names[i]).put("via", if (i == 5) "cast" else ""))
        }
        val repo = CompanionRepo(core)
        runBlocking { repo.refresh() }
        assertEquals(listOf("computer", "phone", "speaker", "tv", "media", "speaker"), repo.state.value.players.map { it.kind })
        val local = PlayerRepo(FakePlaybackCore(playerSnapshot(book = "", chapter = null)), CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined, { null }, { null })
        val host = SheetHost()
        rule.setContent {
            AbookTheme(dark) {
                LaunchedEffect(Unit) { host.show { OtherPlayersSheet(repo, local, it) } }
                SheetLayer(host)
            }
        }
        rule.waitForIdle()
        val icon = rule.onNode(hasTestTag("row_leading") and hasAnyAncestor(hasTestTag("remote_d0")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        val title = rule.onNode(hasTestTag("row_title") and hasAnyAncestor(hasTestTag("remote_d0")), useUnmergedTree = true).getUnclippedBoundsInRoot()
        assertEquals("Kind icon follows the first line, even for a wrapping device name", title.top.value + 12f, ((icon.top + icon.bottom) / 2).value, 0.5f)
        assertTrue(title.bottom - title.top > icon.bottom - icon.top)
        for (i in 0..5) rule.onNode(hasTestTag("row_leading") and hasAnyAncestor(hasTestTag("remote_d$i")), useUnmergedTree = true).assertIsDisplayed()
        rule.assertIconLedTextColumns()
        rule.onRoot().captureRoboImage("src/test/snapshots/gap1b_device_kinds_${if (dark) "dark" else "light"}.png")
    }
}
