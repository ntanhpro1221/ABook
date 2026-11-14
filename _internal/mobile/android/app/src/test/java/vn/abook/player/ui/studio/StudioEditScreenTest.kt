package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import kotlinx.coroutines.*
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import vn.abook.player.StudioError
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.components.SheetHost
import vn.abook.player.ui.components.SheetLayer
import vn.abook.player.ui.theme.Abook
import vn.abook.player.ui.theme.AbookTheme
import com.github.takahirom.roborazzi.captureRoboImage
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.RoborazziTaskType

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
@OptIn(com.github.takahirom.roborazzi.ExperimentalRoborazziApi::class)
class StudioEditScreenTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Unconfined)
    private val source = FakeStudioSource(listOf(studioBook(running = true)))
    private val session = StudioHub(source, scope).session("")
    private val sheets = SheetHost()
    private val gate = CompletableDeferred<Unit>()
    private val state = StudioScriptState(session, "b1", first = 1, hold = { gate.await() })
    private fun tag(value: String) = rule.onNodeWithTag(value)
    private fun tap(value: String) {
        if (rule.onAllNodesWithTag(value).fetchSemanticsNodes().isEmpty() && value.startsWith("studio_line_"))
            tag("studio_script_list").performScrollToNode(hasTestTag(value))
        if (!tag(value).isDisplayed()) tag(value).performScrollTo()
        tag(value).performClick()
        rule.waitForIdle()
    }

    @After fun close() { scope.cancel() }

    private fun show(dark: Boolean = false, content: @Composable () -> Unit) {
        rule.setContent { AbookTheme(dark) { Box(Modifier.fillMaxSize().background(Abook.colors.bg)) { content(); SheetLayer(sheets) } } }
        rule.waitForIdle()
    }

    private fun script(dark: Boolean = false) {
        val lines = listOf(
            scriptLine("n", "Đèn sân đã sáng.", kind = "narration", current = "NARRATOR", editable = false).copy(emotion = "neutral", intensity = 0),
            scriptLine("a", "Xin đặt ghế ở đây.").copy(emotion = "neutral", intensity = 0),
            scriptLine("b", "Tôi sẽ lấy thêm nước.").copy(emotion = "neutral", intensity = 0),
        )
        source.scriptContents = ScriptContents(true, listOf(ScriptEntry(1, 1, "Sân nhỏ", 3, 2, 0, 0)))
        source.scriptChapters[1] = chapterScript(lines)
        show(dark) { ScriptScreen(state, sheets, {}) }
    }

    @Test fun existingPersonTakesExactlyTwoTapsAndUndoWritesNothing() {
        script()
        tap("studio_line_who_a")
        tap("studio_person_TOM")
        assertEquals("TOM", state.decisions.held!!.decision.steps.single().body.getString("speaker"))
        assertTrue(source.writes.isEmpty())
        tap("studio_undo_undo")
        gate.complete(Unit)
        assertTrue(source.writes.isEmpty())
    }

    @Test fun createPersonUsesTheChosenGenderAndKeepsTheSource() {
        script()
        tap("studio_line_who_a")
        tap("studio_script_new")
        tag("studio_script_new_name").performTextInput("Bác Trực")
        tap("studio_script_new_male")
        val body = state.decisions.held!!.decision.steps.single().body
        assertEquals("Bác Trực", body.getString("speaker"))
        assertEquals("male", body.getString("newGender"))
        assertEquals("Xin đặt ghế ở đây.", state.shown()!!.lines[1].text)
    }

    @Test fun narrationToThoughtRequiresAPersonAndOffersUndo() {
        script()
        tap("studio_line_delivery_n")
        tap("studio_delivery_kind_thought")
        tag("studio_delivery_save").assertIsNotEnabled()
        tap("studio_person_TOM")
        tap("studio_delivery_save")
        val body = state.decisions.held!!.decision.steps.single().body
        assertEquals("thought", body.getString("kind"))
        assertEquals("TOM", body.getString("speaker"))
        tag("studio_undo_text").assertExists()
        assertTrue(source.writes.isEmpty())
    }

    @Test fun touchSelectionDeselectsWithoutAddingUnselectedIds() {
        script()
        tap("studio_script_select")
        tap("studio_line_select_a")
        tap("studio_line_select_b")
        tap("studio_line_select_a")
        tap("studio_script_assign_selected")
        tap("studio_person_TOM")
        val refs = state.decisions.held!!.decision.steps.single().body.getJSONArray("lines")
        assertEquals(1, refs.length())
        assertEquals("b", refs.getJSONObject(0).getString("stableId"))
    }

    @Test fun networkFailureRestoresTheLineAndExplainsWhy() {
        script()
        source.writeError = { StudioError.Offline() }
        tap("studio_line_who_a")
        tap("studio_person_TOM")
        rule.runOnIdle { gate.complete(Unit) }
        rule.waitForIdle()
        assertEquals(1, source.writes.size)
        assertTrue(state.notice.isNotEmpty())
        assertEquals("KATI", ScriptLogic.speaker(state.shown()!!.lines[1]))
    }

    @Test fun listenOnlyShowsThePermissionCardAndNoEditingControls() {
        session.note(StudioError.ListenOnly())
        script()
        assertTrue(rule.onAllNodesWithTag("studio_line_who_a").fetchSemanticsNodes().isEmpty())
        assertTrue(source.writes.isEmpty())
    }

    @Test fun mergeMenuUsesTheSameCanonicalNamesAndHold() {
        val project = StudioProjectState(session, "b1", hold = { gate.await() })
        val a = castMember("LUCIEN", "Lucien")
        val b = castMember("NATASHA", "Natasha")
        show { CastPersonSheet(project, a, listOf(a, b), {}, {}) }
        tap("studio_person_merge")
        tap("studio_person_merge_NATASHA")
        tap("studio_person_merge_save")
        val body = project.decisions.held!!.decision.steps.single().body
        assertEquals("LUCIEN", body.getString("from"))
        assertEquals("NATASHA", body.getString("into"))
        assertTrue(source.writes.isEmpty())
    }

    @Test fun renameUsesTheCanonicalKeyAndIsVisibleImmediately() {
        val project = StudioProjectState(session, "b1", hold = { gate.await() })
        val person = castMember("LUCIEN", "Lucien")
        show { CastPersonSheet(project, person, listOf(person), {}, {}) }
        tap("studio_person_rename")
        tag("studio_person_name").performTextReplacement("Bác Trực")
        tap("studio_person_rename_save")
        val (endpoint, body) = source.writes.single()
        assertEquals("characters/rename", endpoint)
        assertEquals("LUCIEN", body.getString("character"))
        assertEquals("Bác Trực", body.getString("name"))
    }

    @Test fun genderUsesTheVoiceRequestAndCanBeUndoneBeforeSending() {
        val project = StudioProjectState(session, "b1", hold = { gate.await() })
        val person = castMember("LUCIEN", "Lucien")
        show { CastPersonSheet(project, person, listOf(person), {}, {}) }
        tap("studio_person_gender")
        tap("studio_person_gender_female")
        tap("studio_person_gender_save")
        val step = project.decisions.held!!.decision.steps.single()
        assertEquals("voice", step.endpoint)
        assertEquals("female", step.body.getString("gender"))
        rule.runOnIdle { project.decisions.undo(); gate.complete(Unit) }
        assertTrue(source.writes.isEmpty())
    }

    @Test fun unmergeWithdrawsThePendingGroupFromTheMenu() {
        val project = StudioProjectState(session, "b1", hold = { gate.await() })
        val person = castMember("LUCIEN", "Lucien").copy(mergedInto = "NATASHA", mergedAt = 42.0)
        source.pending = JSONObject("""{"items":[{"section":"speakers","requestedAt":42,"keys":["a","b"]}]}""")
        show { CastPersonSheet(project, person, listOf(person), {}, {}) }
        tap("studio_person_unmerge")
        val (endpoint, body) = source.writes.single()
        assertEquals("speaker", endpoint)
        assertTrue(body.getBoolean("withdraw"))
        assertEquals(42.0, body.getDouble("requestedAt"), 0.0)
        assertEquals(2, body.getJSONArray("lines").length())
    }

    @Test fun darkModeCanOpenTheDeliverySheet() {
        script(dark = true)
        tap("studio_line_delivery_a")
        tag("studio_delivery_sheet").assertIsDisplayed()
        tap("studio_delivery_emotion")
        tap("studio_emotion_sad")
        tap("studio_delivery_save")
        assertEquals("sad", state.decisions.held!!.decision.steps.single().body.getString("emotion"))
    }

    @Test fun recordLightEditingSheetForVisualReview() {
        script()
        tap("studio_line_who_a")
        tap("studio_script_new")
        rule.onRoot().captureRoboImage("build/m2g1/people_light.png", RoborazziOptions(taskType = RoborazziTaskType.Record))
    }

    @Test fun recordDarkEditingSheetForVisualReview() {
        script(dark = true)
        tap("studio_line_delivery_n")
        tap("studio_delivery_kind_thought")
        rule.onRoot().captureRoboImage("build/m2g1/delivery_dark.png", RoborazziOptions(taskType = RoborazziTaskType.Record))
    }
}
