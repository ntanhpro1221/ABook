package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import com.github.takahirom.roborazzi.captureRoboImage
import kotlinx.coroutines.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.data.*
import vn.abook.player.ui.devices.*
import vn.abook.player.ui.nav.Destination
import vn.abook.player.ui.screens.SettingsEnv
import vn.abook.player.ui.shell.*
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.theme.*

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class IA2NavigationTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private lateinit var shell: ShellState
    private val devicesSource = FakeDevicesSource()
    private val source = FakeStudioSource(listOf(studioBook("b1", title = "Dự án đang làm", running = true, canPause = true)))

    private fun show(computers: Int = 1, dark: Boolean = false, blockedFirst: Boolean = false) {
        devicesSource.studio = (0 until computers).map { StudioComputer(if (it == 0) "" else "desk$it", "Máy tính ${it + 1}", blockedFirst && it == 0) }
        rule.setContent {
            AbookTheme(dark) {
                val scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                val settings = remember { SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined) }
                val devices = remember { DevicesState(devicesSource, scope) }
                val player = remember { PlayerRepo(FakePlaybackCore(playerSnapshot(chapter = null)), scope, Dispatchers.Unconfined, { null }, { null }).also { it.attach(this) } }
                val hub = remember { StudioHub(source, scope) }
                val companion = remember { CompanionRepo(FakeCompanionCore()) { 1_000L } }
                AppShell(shell, LibraryState.Ready(emptyList()), player, CoverLoader(1 shl 20),
                    SettingsEnv(settings, ThemeReveal(scope), devices = devices), companion = companion, studio = hub, sampleClock = false)
            }
        }
    }

    private fun back() {
        rule.waitForIdle()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
    }

    @Test fun flowTapsProjectListIsOneTapAndBackReturnsToTheSameMachine() {
        show(computers = 2)
        var taps = 0
        rule.onNodeWithTag("tab_studio").performClick(); taps++
        rule.onNodeWithTag("studio_book_b1").assertIsDisplayed()
        rule.onNodeWithTag("studio_notices").assertExists()
        assertEquals(1, taps)
        assertEquals(0, shell.nav.stack.size)
        rule.onNodeWithTag("studio_open").assertDoesNotExist()
        rule.onNodeWithTag("studio_computer_desk1").performClick()
        rule.onNodeWithTag("studio_computer_desk1").assertIsSelected()
        assertTrue(source.libraryCalls.contains("desk1"))
        rule.onRoot().captureRoboImage("src/test/snapshots/shell_studio_paired_light.png")
        rule.onNodeWithTag("studio_book_b1").performClick()
        assertEquals(1, shell.nav.stack.size)
        assertEquals(Destination.StudioProject("desk1", "b1"), shell.nav.stack.top?.destination)
        back()
        rule.onNodeWithTag("studio_computer_desk1").assertIsSelected()
        rule.onNodeWithTag("studio_book_b1").assertIsDisplayed()
        assertEquals(0, shell.nav.stack.size)
    }

    @Test fun deviceLinksUseTheRootTabWhileNotificationsRetainTheirBackRoute() {
        show(computers = 2)
        rule.onNodeWithTag("tab_settings").performClick()
        rule.onNodeWithTag("settings_devices").performClick()
        rule.runOnUiThread { shell.scope.launch { shell.openStudio(StudioRequest("desk1", StudioRoute(), fromNotification = false)) } }
        rule.waitForIdle()
        assertEquals(0, shell.nav.stack.size)
        rule.onNodeWithTag("studio_computer_desk1").assertIsSelected()
        rule.runOnUiThread { shell.scope.launch { shell.openStudio(StudioRequest("", StudioRoute())) } }
        rule.waitForIdle()
        assertEquals(Destination.Studio(""), shell.nav.stack.top?.destination)
        back()
        rule.onNodeWithTag("studio_computer_desk1").assertIsSelected()
    }

    @Test fun aSingleMachineHasNoPickerAndPollingStopsAwayFromTheTab() {
        show()
        rule.onNodeWithTag("tab_studio").performClick()
        rule.onNodeWithTag("studio_book_b1").assertIsDisplayed()
        rule.onNodeWithTag("studio_computer_").assertDoesNotExist()
        rule.onRoot().captureRoboImage("src/test/snapshots/shell_studio_single_light.png")
        rule.onNodeWithTag("tab_settings").performClick()
        val calls = source.libraryCalls.size
        rule.mainClock.advanceTimeBy(30_000)
        rule.waitForIdle()
        assertEquals(calls, source.libraryCalls.size)
    }

    @Test fun aListenOnlyMachineDoesNotHideAnotherMachinesProjects() {
        show(computers = 2, blockedFirst = true)
        rule.onNodeWithTag("tab_studio").performClick()
        rule.onNodeWithTag("studio_book_b1").assertIsDisplayed()
        rule.onNodeWithTag("studio_computer_desk1").assertIsSelected()
        assertEquals(0, shell.nav.stack.size)
        rule.onNodeWithTag("studio_computer_").performClick()
        rule.onNodeWithTag("studio_retry").assertIsDisplayed()
        rule.onNodeWithTag("studio_notices").assertExists()
        assertEquals(0, shell.nav.stack.size)
    }

    @Test fun unpairedStudioConnectsToTheDevicesGroup() {
        show(computers = 0, dark = true)
        rule.onNodeWithTag("tab_studio").performClick()
        rule.onNodeWithTag("studio_connect").assertIsDisplayed()
        rule.onNodeWithTag("studio_notices").assertDoesNotExist()
        rule.onNodeWithTag("studio_alerts").assertDoesNotExist()
        rule.onNodeWithText("Nối máy tính để làm sách nói và xem tiến độ.").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/shell_studio_dark.png")
        rule.onNodeWithTag("studio_connect").performClick()
        assertEquals(Destination.Settings(SettingsGroup.Devices), shell.nav.stack.top?.destination)
        back()
        rule.onNodeWithTag("studio_connect").assertIsDisplayed()
    }
}
