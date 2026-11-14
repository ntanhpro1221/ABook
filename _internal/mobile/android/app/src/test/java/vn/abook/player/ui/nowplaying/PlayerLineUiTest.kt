package vn.abook.player.ui.nowplaying

import androidx.activity.ComponentActivity
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.ui.Modifier
import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.compose.ui.test.*
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File
import vn.abook.player.ui.createAndroidComposeRule
import vn.abook.player.ui.studio.*
import vn.abook.player.ui.theme.AbookTheme

@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [35], qualifiers = "w360dp-h780dp-xxhdpi")
class PlayerLineUiTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private class Clock : PlayerPosition {
        override val milliseconds: State<Long> = mutableLongStateOf(3500)
        override val sleepRemainingMs: State<Long> = mutableLongStateOf(0)
        override fun sample() {}
    }
    private val clock = Clock()
    private val sent = ArrayList<String>()
    private var seeks = 0
    private fun fixture() = JSONArray(File("../../../tests/fixtures/player_line/cases.json").readText()).getJSONObject(0)
    private fun show(row: JSONObject): PlayerLineEditor {
        val paragraph = ReadAlongLookup.parse(JSONObject().put("timed", true).put("segments", JSONArray().put(row.getJSONObject("source")))).single()
        val source = object : PlayerLineSource {
            override val decisionsSource: StudioSource = object : StudioSource by FakeStudioSource() {
                override suspend fun write(computer: String, id: String, step: WorkStep, slow: Boolean): JSONObject { sent += step.endpoint; return JSONObject().put("requestedAt", 10) }
            }
            override suspend fun load(bookId: String, chapter: Int, paragraph: ReadParagraph) = PlayerLineLogic.snapshot(chapter, paragraph, row.getJSONObject("cast"), row.getJSONObject("wishes"))
        }
        val editor = PlayerLineEditor(source, CoroutineScope(Dispatchers.Unconfined))
        rule.setContent {
            AbookTheme(false) {
                Box(Modifier.fillMaxSize()) {
                    ReadAlongPane(ReadAlongState("book", 1, listOf(paragraph)), clock, Modifier.fillMaxSize(),
                        onListen = { seeks++ }, onEdit = { editor.open("book", 1, it) }, editing = editor.selected != null)
                    PlayerLineLayer(editor)
                }
            }
        }
        return editor
    }

    @Test fun playEditAndBackKeepTheClockAndScrollAndUseThreeOperations() {
        val editor = show(fixture())
        val before = rule.onNodeWithTag("paragraph_0").getUnclippedBoundsInRoot()
        rule.onNodeWithTag("paragraph_0").performTouchInput { longClick() }
        rule.onNodeWithTag("player_line_editor").assertExists()
        val shot = File("build/outputs/player-line-android.png").also { it.parentFile?.mkdirs() }
        val view = rule.activity.window.decorView
        val bitmap = Bitmap.createBitmap(view.width, view.height, Bitmap.Config.ARGB_8888)
        rule.runOnUiThread { view.draw(Canvas(bitmap)) }
        shot.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        rule.onNodeWithTag("player_line_who").performClick()
        rule.onNodeWithTag("studio_person_AN").performClick()
        assertEquals(0, seeks)
        assertEquals(3500L, clock.milliseconds.value)
        assertEquals("AN", editor.decisions!!.held!!.decision.steps.single().body.getString("speaker"))
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        assertNull(editor.selected)
        assertEquals(listOf("speaker"), sent)
        assertEquals(before, rule.onNodeWithTag("paragraph_0").getUnclippedBoundsInRoot())
    }

    @Test fun backFromPeopleReturnsToTheSentenceBeforeClosing() {
        val editor = show(fixture())
        rule.onNodeWithTag("paragraph_0").performTouchInput { longClick() }
        rule.onNodeWithTag("player_line_who").performClick()
        rule.runOnUiThread { rule.activity.onBackPressedDispatcher.onBackPressed() }
        rule.waitForIdle()
        assertEquals("menu", editor.step); assertNotNull(editor.selected); assertEquals(0, seeks); assertTrue(sent.isEmpty())
    }

    @Test fun oldScriptExplainsTheMissingIdentityAndCannotAssign() {
        val row = fixture(); row.getJSONObject("source").remove("textSha256")
        show(row)
        rule.onNodeWithTag("paragraph_0").performTouchInput { longClick() }
        rule.onNodeWithTag("player_line_who").assertIsNotEnabled()
        rule.onNodeWithTag("player_line_delivery").assertIsNotEnabled()
        assertEquals(0, seeks); assertTrue(sent.isEmpty())
    }
}
