package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextEquals
import androidx.compose.ui.test.junit4.v2.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithTag
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme

/** Các màn của S3 trên JVM với nguồn giả: tab Nhạc nền, "Thêm" mở ba màn con, Kịch bản, Cách đọc tên, Duyệt trước khi thu. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class StudioS3ScreenTest {
    @get:Rule
    val rule = createAndroidComposeRule<ComponentActivity>()

    private val scope = CoroutineScope(Dispatchers.Unconfined)
    private val never: suspend (Long) -> Unit = { awaitCancellation() }
    private val sheets = SheetHost()
    private val source = FakeStudioSource(listOf(studioBook(running = true)))
    private val hub = StudioHub(source, scope)
    private val opened = ArrayList<StudioSubKind>()

    private fun show(content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(false) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content(); SheetLayer(sheets) } } }
        rule.waitForIdle()
    }

    private fun project(tab: StudioTab) = StudioProjectState(hub.session(""), "b1", tab, never).also { state ->
        show { StudioProjectScreen(state, sheets, {}, {}, true) { opened += it } }
    }

    private fun tag(tag: String) = rule.onNodeWithTag(tag)
    private fun absent(tag: String) = assertEquals(0, rule.onAllNodesWithTag(tag).fetchSemanticsNodes().size)

    // ---- Nhạc nền ----

    @Test fun theSwitchSendsOnePutAndNothingIsHidden() {
        source.musicView = musicView(scenes = listOf(musicScene("s1")), tracks = mapOf("t1" to MusicTrack("Bài A", "Ai", "", "", "cc0")))
        project(StudioTab.Music)
        tag("studio_music_settings").assertIsDisplayed()
        tag("studio_music_enabled").performClick()
        rule.waitForIdle()
        val (endpoint, body, slow) = source.puts.single()
        assertEquals("music", endpoint)
        assertEquals(false, body.getBoolean("enabled"))
        assertEquals(false, slow)
    }

    @Test fun theAdvancedMoodsFoldIsOnlyThereWhenTheMachineHasTheModel() {
        source.moods = MoodsModel(installed = false, downloading = false, percent = null, error = "", downloadable = true)
        project(StudioTab.Music)
        absent("studio_music_advanced")
    }

    // ---- "Thêm" ----

    @Test fun theMoreMenuOpensEachSubPage() {
        source.books = listOf(studioBook(running = true, segmentsAnalyzed = 40, castLocked = true))
        project(StudioTab.Chapters)
        tag("studio_more").performClick()
        rule.waitForIdle()
        tag("studio_more_precast").assertIsDisplayed()
        tag("studio_more_script").assertIsDisplayed()
        tag("studio_more_readings").performClick()
        rule.waitForIdle()
        assertEquals(listOf(StudioSubKind.Readings), opened)
    }

    // ---- Kịch bản ----

    private fun script(): StudioScriptState {
        source.scriptContents = ScriptContents(true, listOf(ScriptEntry(1, 1, "Chương 1", 2, 1, 1, 0)))
        source.scriptChapters[1] = chapterScript(
            listOf(
                scriptLine("n1", "Trời mưa.", kind = "narration", label = "Người kể", current = "NARRATOR", editable = false),
                scriptLine("d1", "Chào anh.", seq = 2, hint = ScriptHint("who", "Chưa chắc ai nói", "Tom")),
            ),
        )
        return StudioScriptState(hub.session(""), "b1", hold = { awaitCancellation() }).also { state ->
            show { ScriptScreen(state, sheets, {}, true) }
        }
    }

    @Test fun theScriptShowsTheBooksTextAndTheDoubtNextToIt() {
        script()
        tag("studio_line_text_n1").assertTextEquals("Trời mưa.")
        tag("studio_line_text_d1").assertTextEquals("Chào anh.")
        tag("studio_line_hint_d1").assertIsDisplayed()
        absent("studio_line_edit_n1")
    }

    @Test fun pickingAnotherSpeakerOffersUndoAndSendsNothingYet() {
        script()
        tag("studio_line_who_d1").performScrollTo().performClick()
        rule.waitForIdle()
        tag("studio_person_TOM").performClick()
        rule.waitForIdle()
        tag("studio_undo_text").assertTextEquals("Đã ghi: câu này của Tom")
        assertTrue(source.writes.isEmpty())
    }

    // ---- Cách đọc tên ----

    @Test fun theNamesListSearchesAndOpensTheEditorInPlace() {
        source.readings = NameReadings(listOf(NameReading("Noah", "Nô-a", false, 4, null, false, null), NameReading("Kati", "Ka-ti", true, 9, null, false, null)), 0)
        val state = StudioReadingsState(hub.session(""), "b1", pause = never, hold = { awaitCancellation() })
        show { ReadingsScreen(state, {}, true) }
        tag("studio_reading_Noah").assertIsDisplayed()
        tag("studio_reading_Kati").assertIsDisplayed()
        tag("studio_reading_edit_Noah").performClick()
        rule.waitForIdle()
        tag("studio_reading_editor").assertIsDisplayed()
        tag("studio_reading_save").assertIsDisplayed()
    }

    // ---- Duyệt trước khi thu ----

    @Test fun theReviewStartsAtTheFirstOfFourStepsAndTheSkipButtonMovesOn() {
        source.books = listOf(studioBook(running = true, segmentsAnalyzed = 40, castLocked = true))
        val state = StudioProjectState(hub.session(""), "b1", StudioTab.Chapters, never)
        show { PrecastScreen(state, sheets, {}, {}, true) }
        tag("studio_precast_step").assertTextEquals("Bước 1/4")
        tag("studio_precast_skip").performScrollTo().performClick()
        rule.waitForIdle()
        tag("studio_precast_step").assertTextEquals("Bước 2/4")
    }
}
