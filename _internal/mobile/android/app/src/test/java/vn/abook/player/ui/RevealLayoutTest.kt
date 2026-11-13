package vn.abook.player.ui

import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.getUnclippedBoundsInRoot
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.unit.DpRect
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.MusicLibrary
import vn.abook.player.ui.components.BasicText
import vn.abook.player.ui.components.ConfirmPage
import vn.abook.player.ui.components.Reveal
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.music.library.FakeLibrarySource
import vn.abook.player.ui.music.library.Label
import vn.abook.player.ui.music.library.LibraryIndex
import vn.abook.player.ui.music.library.LibrarySource
import vn.abook.player.ui.music.library.LibraryState
import vn.abook.player.ui.music.library.SilentPreview
import vn.abook.player.ui.music.library.TrackSheet
import vn.abook.player.ui.screens.BookTab
import vn.abook.player.ui.screens.BookTabs
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.theme.AbookTheme

/** Actual content bounds, including the reduced-motion Box path. All data is synthetic. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class RevealLayoutTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val resolver get() = RuntimeEnvironment.getApplication().contentResolver

    @After fun restoreScale() {
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f)
    }

    private fun show(reduced: Boolean, content: @Composable () -> Unit) {
        Settings.Global.putFloat(resolver, Settings.Global.ANIMATOR_DURATION_SCALE, if (reduced) 0f else 1f)
        rule.setContent { AbookTheme(false) { content() } }
        rule.waitForIdle()
    }

    private fun bounds(tag: String) = rule.onNodeWithTag(tag, useUnmergedTree = true).getUnclippedBoundsInRoot()
    private fun text(text: String) = rule.onNodeWithText(text, useUnmergedTree = true).getUnclippedBoundsInRoot()
    private fun below(first: DpRect, second: DpRect, gap: Float = 0f) {
        assertTrue("Expected vertical gap >= $gap: $first then $second", second.top.value - first.bottom.value >= gap - 0.5f)
    }
    private fun after(first: DpRect, second: DpRect, gap: Float) {
        assertTrue("Expected horizontal gap >= $gap: $first then $second", second.left.value - first.right.value >= gap - 0.5f)
    }

    @Test fun confirmSpacing() = confirm(false)
    @Test fun confirmSpacingReduced() = confirm(true)
    private fun confirm(reduced: Boolean) {
        show(reduced) { ConfirmPage("Test action", "confirm_layout", listOf("Check the setting."), "Try again.") {} }
        below(text("Check the setting."), bounds("confirm_layout_problem"), 8f)
    }

    @Test fun chapterCountSpacing() = chapterCount(false)
    @Test fun chapterCountSpacingReduced() = chapterCount(true)
    private fun chapterCount(reduced: Boolean) {
        show(reduced) { BookTabs(BookTab.entries, BookTab.Chapters, 12, {}) }
        after(text(BookTab.Chapters.label), text("12"), 8f)
    }

    private fun project(source: FakeStudioSource, tab: StudioTab): StudioProjectState {
        val hub = StudioHub(source, CoroutineScope(Dispatchers.Unconfined))
        return StudioProjectState(hub.session(""), "b1", tab, { awaitCancellation() })
    }

    @Test fun redoHintPrecedesHelp() = redo(false)
    @Test fun redoHintPrecedesHelpReduced() = redo(true)
    private fun redo(reduced: Boolean) {
        val source = FakeStudioSource(listOf(studioBook(running = true)))
        source.reviewPages[""] = emptyReview().copy(redoChapters = listOf(1, 2))
        val state = project(source, StudioTab.Review)
        show(reduced) { StudioProjectScreen(state, SheetHost(), {}, {}) }
        rule.onNodeWithTag("studio_review_redo_more").performScrollTo()
        below(bounds("studio_review_redo"), bounds("studio_review_redo_more"))
    }

    @Test fun castingHeadingPrecedesCaption() = casting(false)
    @Test fun castingHeadingPrecedesCaptionReduced() = casting(true)
    private fun casting(reduced: Boolean) {
        val source = FakeStudioSource(listOf(studioBook(running = true, segmentsAnalyzed = 40, castLocked = true)))
        source.workView = WorkView(listOf(workItem(kind = WorkKind.Gender, key = "layout", title = "Choose a role", examples = emptyList())), emptyMap())
        val state = project(source, StudioTab.Chapters)
        show(reduced) { PrecastScreen(state, SheetHost(), {}, {}, true) }
        rule.onNodeWithText(PrecastText.castUnsure(1)).performScrollTo()
        below(text(PrecastText.CAST_UNSURE), text(PrecastText.castUnsure(1)), 4f)
    }

    @Test fun emotionBarsHaveSeparateRows() = emotions(false)
    @Test fun emotionBarsHaveSeparateRowsReduced() = emotions(true)
    private fun emotions(reduced: Boolean) {
        val link = "https://music.example/layout.mp3"
        val raw = JSONObject().put("title", "Test track").put("creator", "Test artist").put("duration", 60)
            .put("license", "cc0").put("emotions", JSONObject().put("joy", 0.9).put("peace", 0.6).put("wonder", 0.3))
        val source = object : LibrarySource by FakeLibrarySource() {
            override fun load() = LibraryIndex(MusicLibrary.tracksOf(mapOf(link to raw)), emptyList(), emptyList(),
                listOf(Label("joy", "Joy"), Label("peace", "Peace"), Label("wonder", "Wonder")))
        }
        val state = LibraryState(source, CoroutineScope(Dispatchers.Unconfined), SilentPreview(), io = Dispatchers.Unconfined)
        state.open()
        show(reduced) { TrackSheet(state, link, {}) }
        rule.onNodeWithTag("emotion_wonder").performScrollTo()
        below(bounds("emotion_joy"), bounds("emotion_peace"))
        below(bounds("emotion_peace"), bounds("emotion_wonder"))
        val first = bounds("emotion_joy")
        assertTrue(first.bottom - first.top >= 28.dp)
    }

    @Test fun verticalBoundsSurviveEnterAndExit() = frames(false, false)
    @Test fun verticalBoundsSurviveEnterAndExitReduced() = frames(true, false)
    @Test fun horizontalBoundsSurviveEnterAndExit() = frames(false, true)
    @Test fun horizontalBoundsSurviveEnterAndExitReduced() = frames(true, true)
    private fun frames(reduced: Boolean, horizontal: Boolean) {
        var visible by mutableStateOf(false)
        val children: @Composable () -> Unit = {
            BasicText("One", Modifier.testTag("first"))
            if (horizontal) Spacer(Modifier.width(8.dp)) else Spacer(Modifier.height(8.dp))
            BasicText("Two", Modifier.testTag("second"))
            if (horizontal) Spacer(Modifier.width(4.dp)) else Spacer(Modifier.height(4.dp))
            BasicText("Three", Modifier.testTag("third"))
        }
        show(reduced) { Reveal(visible) { if (horizontal) Row { children() } else Column { children() } } }
        fun checkBounds() {
            val first = bounds("first")
            val second = bounds("second")
            val third = bounds("third")
            if (horizontal) { after(first, second, 8f); after(second, third, 4f) }
            else { below(first, second, 8f); below(second, third, 4f) }
            assertTrue(first.right > first.left && first.bottom > first.top)
        }
        rule.mainClock.autoAdvance = false
        rule.runOnIdle { visible = true }
        rule.waitForIdle()
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(32)
        rule.waitForIdle()
        checkBounds()
        rule.mainClock.advanceTimeBy(500)
        rule.waitForIdle()
        checkBounds()
        rule.runOnIdle { visible = false }
        rule.waitForIdle()
        rule.mainClock.advanceTimeByFrame()
        rule.mainClock.advanceTimeBy(32)
        rule.waitForIdle()
        checkBounds()
        rule.mainClock.advanceTimeBy(500)
        rule.mainClock.autoAdvance = true
        rule.waitForIdle()
        rule.onNodeWithTag("first").assertDoesNotExist()
        rule.onNodeWithTag("second").assertDoesNotExist()
        rule.onNodeWithTag("third").assertDoesNotExist()
    }
}
