package vn.abook.player.ui.music.library

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.S
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.snapshot.captureRoboImage
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h480dp-xxhdpi")
class MusicControlsSnapshotTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()

    private fun states(dark: Boolean) {
        val source = FakeLibrarySource()
        val state = LibraryState(source, CoroutineScope(Dispatchers.Unconfined), SilentPreview(), io = Dispatchers.Unconfined)
        state.open()
        val track = state.ui.value.index!!.tracks.first { it.link in source.onDisk }
        val ui = mutableStateOf(state.ui.value.copy(downloaded = emptySet()))
        rule.setContent {
            AbookTheme(dark) {
                Column(Modifier.fillMaxSize().background(Abook.colors.bg).padding(16.dp)) {
                    TrackRow(track, ui.value, state, onOpen = {})
                }
            }
        }
        rule.waitUntil(timeoutMillis = vn.abook.player.TestTime.ms(5_000)) {
            rule.onAllNodesWithTag("music_art_image", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty()
        }
        val theme = if (dark) "dark" else "light"
        fun shot(name: String) {
            // The generated artwork is drawn on Dispatchers.Default, which waitForIdle does not wait for.
            rule.waitUntil(5_000) { rule.onAllNodesWithTag("music_art_image", useUnmergedTree = true).fetchSemanticsNodes().isNotEmpty() }
            rule.waitForIdle()
            val node = rule.onAllNodes(isRoot()).onFirst()
            node.captureRoboImage("src/test/snapshots/music_controls_${name}_$theme.png")
        }
        shot("download")
        val button = rule.onNodeWithTag("download_${track.link.hashCode()}")
        val initialBounds = button.fetchSemanticsNode().boundsInRoot
        rule.runOnUiThread { ui.value = ui.value.copy(active = mapOf(track.link to Loading(320, 1000))) }
        rule.onNodeWithContentDescription(S.s_stop_download).assertHasClickAction()
        shot("progress")
        assertEquals(initialBounds, button.fetchSemanticsNode().boundsInRoot)
        rule.runOnUiThread { ui.value = ui.value.copy(active = mapOf(track.link to Loading(0, null))) }
        shot("connecting")
        assertEquals(initialBounds, button.fetchSemanticsNode().boundsInRoot)
        rule.runOnUiThread { ui.value = ui.value.copy(active = emptyMap(), downloaded = setOf(track.link)) }
        // "Downloaded" is a status, not a hidden delete button: removing it lives in the track sheet behind the confirmation.
        val status = rule.onNodeWithTag("download_${track.link.hashCode()}", useUnmergedTree = true)
        status.assertContentDescriptionEquals(S.s_da_tai_b7362bbf)
        status.assertHasNoClickAction()
        shot("downloaded")
        assertEquals(initialBounds, button.fetchSemanticsNode().boundsInRoot)
        assertTrue(source.onDisk.contains(track.link))
        rule.runOnUiThread { ui.value = ui.value.copy(previewing = track.link, previewLoading = true, previewPosition = 32.0, previewDuration = track.duration ?: 180.0) }
        rule.mainClock.advanceTimeBy(vn.abook.player.ui.components.PENDING_DELAY_MS + 32L)
        rule.waitForIdle()
        shot("buffering")
        rule.runOnUiThread { ui.value = ui.value.copy(previewLoading = false) }
        rule.onNodeWithContentDescription(S.s_music_seek).assertExists()
        shot("playing")
        rule.runOnUiThread { ui.value = ui.value.copy(previewPaused = true) }
        shot("paused")
    }

    @Test fun controlsLight() = states(false)
    @Test fun controlsDark() = states(true)

    @Test fun destructiveActionWaitsForSuccessAndRetainsRetryAfterFailure() {
        val pending = mutableStateOf(false)
        val problem = mutableStateOf("")
        val open = mutableStateOf(true)
        var calls = 0
        rule.setContent { AbookTheme(false) {
            vn.abook.player.ui.components.DestructiveConfirm(open.value, "Xoá bản tải?", "Air Prelude", { open.value = false },
                { calls++; pending.value = true; problem.value = "" }, pending = pending.value, problem = problem.value)
        } }
        rule.onNodeWithTag("destructive_accept").performClick()
        rule.onNodeWithTag("destructive_accept").performClick()
        rule.onNodeWithTag("destructive_cancel").performClick()
        assertEquals(1, calls)
        rule.onNodeWithTag("destructive_confirm").assertIsDisplayed()
        rule.runOnUiThread { problem.value = "Disk busy"; pending.value = false }
        rule.onNodeWithTag("destructive_accept").performClick()
        assertEquals(2, calls)
        rule.runOnUiThread { pending.value = false }
        rule.waitForIdle()
        assertFalse(open.value)
    }

    @Test fun destructiveActionOwnsTheReturnedJobWhileItsModelIsStillPreparing() {
        val job = kotlinx.coroutines.Job()
        val open = mutableStateOf(true)
        var calls = 0
        rule.setContent { AbookTheme(false) {
            vn.abook.player.ui.components.DestructiveConfirm(open.value, "Xoá bản tải?", "Air Prelude", { open.value = false },
                { calls++; job }, pending = false)
        } }
        rule.onNodeWithTag("destructive_accept").performClick()
        rule.onNodeWithTag("destructive_accept").performClick()
        rule.onNodeWithTag("destructive_cancel").performClick()
        rule.onNodeWithTag("destructive_confirm").assertIsDisplayed()
        assertEquals(1, calls)
        rule.runOnUiThread { job.complete() }
        rule.waitForIdle()
        assertFalse(open.value)
    }
}
