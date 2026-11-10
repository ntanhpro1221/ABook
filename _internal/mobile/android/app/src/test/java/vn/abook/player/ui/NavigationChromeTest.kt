package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.height
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.runBlocking
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.player.MiniPlayer
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NavigationChromeTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    @Test fun deviceSelectorRemainsAvailableButOnlyPlayingPeersOccupyASingleLine() {
        val core = FakeCompanionCore()
        val connected = core.rows
        core.rows = JSONArray()
        val remote = CompanionRepo(core)
        val sheets = SheetHost()
        rule.setContent {
            AbookTheme(false) {
                val scope = rememberCoroutineScope()
                val local = PlayerRepo(FakePlaybackCore(JSONObject()), scope, Dispatchers.Unconfined, { null }, { null })
                Column {
                    OtherPlayersEntry(remote, sheets, local)
                    MiniPlayer(PlayerState(bookId = "b", bookTitle = "Book", chapterId = 1), { 0L }, CoverLoader(), {}, {},
                        onDevices = { sheets.show { dismiss -> OtherPlayersSheet(remote, local, dismiss) } })
                }
                SheetLayer(sheets)
            }
        }
        rule.onNodeWithTag("mini_devices").assertIsDisplayed()
        rule.onNodeWithTag("other_players").assertDoesNotExist()
        connected.getJSONObject(0).getJSONObject("state").put("playing", false)
        core.rows = connected
        rule.runOnIdle { runBlocking { remote.refresh() } }
        rule.onNodeWithTag("other_players").assertDoesNotExist()
        rule.onNodeWithTag("mini_devices").assertIsDisplayed()
        connected.getJSONObject(0).getJSONObject("state").put("playing", true)
        rule.runOnIdle { runBlocking { remote.refresh() } }
        rule.waitForIdle()
        rule.onNodeWithTag("other_players").assertIsDisplayed()
        org.junit.Assert.assertTrue(rule.onNodeWithTag("other_players").getUnclippedBoundsInRoot().height <= 36.dp)
        rule.onNodeWithTag("mini_devices").performClick()
        rule.onNodeWithTag("remote_players_sheet").assertIsDisplayed()
    }
}
