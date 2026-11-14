package vn.abook.player.ui.studio

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.ui.Modifier
import com.github.takahirom.roborazzi.RoborazziOptions
import com.github.takahirom.roborazzi.RoborazziTaskType
import vn.abook.player.ui.snapshot.captureRoboImage
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import org.json.JSONObject
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
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class ScriptScopeScreenTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val source = FakeStudioSource()
    private val session = StudioHub(source, CoroutineScope(Dispatchers.Unconfined)).session("")
    private val sheets = SheetHost()
    private fun show(privateWishes: Boolean = false): StudioScriptState {
        val fixture = JSONObject(File("../../../tests/fixtures/script_scope.json").readText())
        val lines = StudioScriptJson.chapter(JSONObject().put("lines", fixture.getJSONArray("lines"))).lines.take(12)
            .map { if (privateWishes) it else it.copy(wish = null, lineWish = null) }
        source.scriptContents = ScriptContents(true, listOf(ScriptEntry(1, 1, "Chương thử", 12, 10, 0, 0)))
        source.scriptChapters[1] = chapterScript(lines).copy(cast = listOf(ScriptPerson("OTHER", "Khách", 1)), others = emptyList(), scopeRevision = "fixture-v1")
        val state = StudioScriptState(session, "b1", hold = { awaitCancellation() })
        rule.setContent { AbookTheme(false) { Box(Modifier.fillMaxSize()) { ScriptScreen(state, sheets, {}); SheetLayer(sheets) } } }
        rule.waitForIdle()
        return state
    }

    @Test fun tenLinesInThreeTapsAndTheEntryWritesNothing() {
        val state = show()
        rule.onNodeWithTag("script_scope_open_s000").performScrollTo().performClick()
        rule.waitForIdle()
        assertTrue(source.writes.isEmpty())
        rule.onNodeWithTag("scope_person_OTHER").performScrollTo().performClick()
        rule.waitForIdle()
        System.getenv("M2G3_ARTIFACTS")?.let { dir ->
            rule.onNodeWithTag("sheet_layer").captureRoboImage(File(dir, "scope_android.png").path, RoborazziOptions(taskType = RoborazziTaskType.Record))
        }
        rule.onNodeWithTag("scope_apply").performClick()
        rule.waitForIdle()
        val body = state.decisions.held!!.decision.steps.single().body
        assertEquals(10, body.getJSONArray("lines").length())
        state.decisions.flush()
        assertEquals(10, source.writes.single().second.getJSONArray("lines").length())
    }

    @Test fun aChangedMarkerOrSourceRefusesTheOldPreview() {
        val state = show()
        rule.onNodeWithTag("script_scope_open_s000").performScrollTo().performClick()
        rule.onNodeWithTag("scope_person_OTHER").performScrollTo().performClick()
        source.scriptChapters[1] = source.scriptChapters.getValue(1).copy(scopeRevision = "fixture-v2")
        rule.onNodeWithTag("scope_apply").performClick()
        rule.waitForIdle()
        assertTrue(source.writes.isEmpty())
        assertEquals(null, state.decisions.held)
    }

    @Test fun privateWishesStayOutAndEachExceptionCostsOneTap() {
        val state = show(privateWishes = true)
        rule.onNodeWithTag("script_scope_open_s000").performScrollTo().performClick()
        rule.onNodeWithTag("scope_person_OTHER").performScrollTo().performClick()
        rule.onNodeWithTag("scope_line_s001").performScrollTo().performClick()
        rule.onNodeWithTag("scope_apply").performClick()
        rule.waitForIdle()
        val body = state.decisions.held!!.decision.steps.single().body
        val refs = body.getJSONArray("lines")
        val ids = (0 until refs.length()).map { refs.getJSONObject(it).getString("stableId") }
        assertEquals(7, ids.size)
        assertTrue(listOf("s001", "s002", "s004", "s003", "s008").none { it in ids })
    }
}
