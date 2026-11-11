package vn.abook.player.ui

import androidx.activity.ComponentActivity
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import vn.abook.player.ui.snapshot.captureRoboImage
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
import vn.abook.player.ui.theme.*
import vn.abook.player.ui.voice.*

/** Settings folds stay inside one group route. Music retains its existing route for dev/musiclib. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class NativeDevicesFlowTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val source = FakeDevicesSource().also {
        it.share = Share(running = true, port = 1, addresses = listOf("192.168.1.9"))
        it.storage = Storage(bytes = 300L * 1024 * 1024, free = 10L * 1024 * 1024 * 1024,
            entries = listOf(Stored("b", "Sách trên điện thoại", 300L * 1024 * 1024, false)))
    }
    private lateinit var shell: ShellState

    private fun show(group: SettingsGroup = SettingsGroup.Devices, dark: Boolean = false) {
        rule.setContent {
            AbookTheme(dark) {
                val scope = rememberCoroutineScope()
                shell = remember { ShellState(scope) }
                val player = remember { PlayerRepo(FakePlaybackCore(playerSnapshot(chapter = null)), scope, Dispatchers.Unconfined, { null }, { null }) }
                val devices = remember { DevicesState(source, scope, pollMs = 3_600_000) }
                val voiceSource = remember { FakeVoiceSource() }
                val voice = remember { VoiceState(voiceSource, scope, FakeSamplePlayer(), {}, 3_600_000, MineImports(voiceSource, scope)) }
                val env = remember { SettingsEnv(SettingsRepo(FakeSettingsCore(), scope, Dispatchers.Unconfined), ThemeReveal(scope), devices = devices, voice = voice) }
                AppShell(shell, LibraryState.Ready(emptyList()), player, CoverLoader(), env, sampleClock = false)
            }
        }
        rule.onNodeWithTag("tab_settings").performClick()
        rule.onNodeWithTag(group.tag).performClick()
        rule.waitForIdle()
    }

    private fun back() {
        rule.waitForIdle()
        rule.activityRule.scenario.onActivity { it.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
    }
    private fun depth(group: SettingsGroup) {
        assertEquals(1, shell.nav.stack.size)
        assertEquals(Destination.Settings(group), shell.nav.stack.top?.destination)
    }

    @Test fun aFoldAnimatesBothDirectionsWithoutAddingABackEntry() {
        show()
        rule.mainClock.autoAdvance = false
        rule.onNodeWithTag("devices_pair").performClick()
        rule.mainClock.advanceTimeBy(80)
        val opening = rule.onNodeWithTag("devices_pair_body").fetchSemanticsNode().boundsInRoot.height
        rule.mainClock.advanceTimeBy(1_000)
        val expanded = rule.onNodeWithTag("devices_pair_body").fetchSemanticsNode().boundsInRoot.height
        assertTrue("opening must have an intermediate height", opening > 0f && opening < expanded)
        rule.onNodeWithTag("devices_pair").performClick()
        rule.mainClock.advanceTimeBy(80)
        val closing = rule.onNodeWithTag("devices_pair_body").fetchSemanticsNode().boundsInRoot.height
        assertTrue("closing must have an intermediate height", closing > 0f && closing < expanded)
        rule.mainClock.advanceTimeBy(1_000)
        rule.mainClock.autoAdvance = true
        rule.onNodeWithTag("devices_pair_body").assertDoesNotExist()
        depth(SettingsGroup.Devices)
    }

    @Test fun pairAndShareExpandWithoutPushingScreensAndBackClosesTheSheetFirst() {
        show()
        for (tag in listOf("devices_pair", "devices_share")) {
            rule.onNodeWithTag(tag).performClick()
            depth(SettingsGroup.Devices)
            rule.onNodeWithTag("${tag}_body").assertIsDisplayed()
            rule.onRoot().captureRoboImage("src/test/snapshots/settings_${tag}_inline_light.png")
            rule.onNodeWithTag(tag).performScrollTo().performClick()
            rule.onNodeWithTag("${tag}_body").assertDoesNotExist()
            depth(SettingsGroup.Devices)
        }
        rule.onNodeWithTag("devices_storage").assertDoesNotExist()
        rule.onNodeWithTag("devices_name").performScrollTo().performClick()
        rule.onNodeWithTag("rename_sheet").assertIsDisplayed()
        depth(SettingsGroup.Devices)
        back()
        rule.onNodeWithTag("rename_sheet").assertDoesNotExist()
        depth(SettingsGroup.Devices)
        back()
        rule.onNodeWithTag("settings_screen").assertIsDisplayed()
        assertEquals(0, shell.nav.stack.size)
    }

    @Test fun memoryContainsBooksAndGeneratedReadingsInOneFold() {
        show(SettingsGroup.Advanced, dark = true)
        rule.onNodeWithTag("advanced_memory").performClick()
        rule.onNodeWithTag("storage_total").assertIsDisplayed()
        rule.onNodeWithText("Sách trên điện thoại").assertIsDisplayed()
        rule.onNodeWithTag("cache_clear").assertIsDisplayed()
        rule.onRoot().captureRoboImage("src/test/snapshots/settings_memory_inline_dark.png")
        depth(SettingsGroup.Advanced)
        rule.onNodeWithTag("advanced_memory").performScrollTo().performClick()
        rule.onNodeWithTag("storage_total").assertDoesNotExist()
        depth(SettingsGroup.Advanced)
        back()
        assertEquals(0, shell.nav.stack.size)
    }

    @Test fun keysExpandInlineAndTheirEditorReturnsToTheSameGroup() {
        show(SettingsGroup.Voice)
        rule.onNodeWithTag("settings_voice_screen").performScrollToNode(hasTestTag("voice_keys"))
        rule.onNodeWithTag("voice_keys").performClick()
        rule.onNodeWithTag("settings_voice_screen").performScrollToNode(hasTestTag("key_azure"))
        depth(SettingsGroup.Voice)
        rule.onNodeWithTag("settings_voice_screen").performScrollToNode(hasTestTag("key_viettel"))
        rule.onRoot().captureRoboImage("src/test/snapshots/settings_keys_inline_light.png")
        rule.onNodeWithTag("settings_voice_screen").performScrollToNode(hasTestTag("key_azure"))
        rule.onNodeWithTag("key_azure").performClick()
        rule.onNodeWithTag("key_sheet").assertIsDisplayed()
        back()
        rule.onNodeWithTag("key_sheet").assertDoesNotExist()
        depth(SettingsGroup.Voice)
        back()
        assertEquals(0, shell.nav.stack.size)
    }

    @Test fun everySettingsGroupIsAtMostOneScreenFromTheTab() {
        show()
        back()
        for (group in SettingsGroup.entries) {
            rule.onNodeWithTag(group.tag).performClick()
            depth(group)
            back()
            assertEquals(0, shell.nav.stack.size)
        }
        // VoicePage.Music is intentionally retained unchanged for the parallel music-library branch.
        assertEquals(listOf(VoicePage.Music), VoicePage.entries)
    }
}
