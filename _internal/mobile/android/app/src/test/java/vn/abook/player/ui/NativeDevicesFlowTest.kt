package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.assertEquals
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
import vn.abook.player.ui.data.SettingsRepo
import vn.abook.player.ui.data.playerSnapshot
import vn.abook.player.ui.devices.DeviceLinks
import vn.abook.player.ui.devices.DevicesPage
import vn.abook.player.ui.devices.DevicesState
import vn.abook.player.ui.devices.FakeDevicesSource
import vn.abook.player.ui.devices.Share
import vn.abook.player.ui.devices.Storage
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.shell.AppShell
import vn.abook.player.ui.shell.ShellState
import vn.abook.player.ui.theme.AbookTheme
import vn.abook.player.ui.theme.ThemeReveal

/** Ba màn Thiết bị trong khung thật: Cài đặt -> nhóm Thiết bị -> màn con, Back lùi từng lớp một đúng đường đã vào. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NativeDevicesFlowTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val source = FakeDevicesSource().also {
        it.share = Share(running = true, port = 1, addresses = listOf("192.168.1.9"))
        it.storage = Storage(bytes = 5, free = 5)
    }
    private lateinit var shell: ShellState

    private fun show() {
        rule.setContent {
            AbookTheme {
                val scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                val player = remember { PlayerRepo(FakePlaybackCore(playerSnapshot(chapter = null)), scope, Dispatchers.Unconfined, { null }, { null }) }
                val devices = remember { DevicesState(source, CoroutineScope(Dispatchers.Unconfined), DeviceLinks(), pollMs = 3_600_000) }
                val env = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), CoroutineScope(Dispatchers.Unconfined), Dispatchers.Unconfined), ThemeReveal(scope), devices = devices) }
                AppShell(shell, LibraryState.Ready(listOf(ListenBook("b", "Sách"))), player, CoverLoader(), env, sampleClock = false)
            }
        }
        rule.onNodeWithTag("tab_settings").performClick()
        rule.onNodeWithTag("settings_devices").performClick()
        rule.waitForIdle()
    }

    private fun back() {
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
    }

    @Test
    fun eachDevicesScreenOpensFromTheGroupPageAndBackReturnsThere() {
        show()
        rule.onNodeWithTag("settings_devices_screen").assertIsDisplayed()
        rule.onNodeWithText("Đang bật").assertIsDisplayed()
        for ((tag, page, screen) in listOf(
            Triple("devices_pair", DevicesPage.Pair, "pair_screen"),
            Triple("devices_share", DevicesPage.Share, "share_screen"),
            Triple("devices_storage", DevicesPage.Storage, "storage_screen"),
        )) {
            rule.onNodeWithTag(tag).performClick()
            rule.waitForIdle()
            rule.onNodeWithTag(screen).assertIsDisplayed()
            assertEquals(Destination.Devices(page), shell.nav.stack.top?.destination)
            assertEquals(2, shell.nav.stack.size)
            back()
            rule.onNodeWithTag("settings_devices_screen").assertIsDisplayed()
            rule.onNodeWithTag(screen).assertDoesNotExist()
            assertEquals(1, shell.nav.stack.size)
        }
        back()
        rule.onNodeWithTag("settings_screen").assertIsDisplayed()
    }
}
