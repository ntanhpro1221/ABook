package vn.abook.player.ui.studio

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ScriptScopeTest {
    private val fixture get() = JSONObject(File("../../../tests/fixtures/script_scope.json").readText())
    private fun strings(json: JSONObject, key: String): List<String> = json.optJSONArray(key)?.let { array -> (0 until array.length()).map(array::getString) }.orEmpty()

    @Test fun sharedIds() {
        val data = fixture
        val all = StudioScriptJson.chapter(JSONObject().put("lines", data.getJSONArray("lines"))).lines
        val cases = data.getJSONArray("cases")
        for (at in 0 until cases.length()) {
            val sample = cases.getJSONObject(at)
            val lines = if (sample.optBoolean("noMarkers")) all.map { it.copy(scene = null) } else all
            val mode = ScriptScopeMode.entries.first { it.name.lowercase() == sample.getString("mode") }
            val candidates = ScriptScopeLogic.candidates(lines, sample.getString("anchor"), mode, sample.getInt("start"), sample.getInt("end"))
            assertEquals(sample.getString("name"), strings(sample, "ids"), candidates.map { it.stableId })
            assertEquals(strings(sample, "selected"), ScriptScopeLogic.selected(candidates, strings(sample, "toggled").toSet()).map { it.stableId })
        }
    }

    @Test fun groupUsesExistingSpeakerContractAndPreservesSource() {
        val lines = StudioScriptJson.chapter(JSONObject().put("lines", fixture.getJSONArray("lines"))).lines
        val chosen = ScriptScopeLogic.selected(ScriptScopeLogic.candidates(lines, "s000", ScriptScopeMode.Scene, 0, 999), emptySet())
        val decision = ScriptScopeLogic.decision(chosen, ScriptPerson("Khách mới", "Khách mới", 0, "unknown"))
        val step = decision.steps.single()
        assertEquals("speaker", step.endpoint)
        assertEquals(8, step.body.getJSONArray("lines").length())
        assertEquals("unknown", step.body.getString("newGender"))
        assertFalse(step.body.has("alias"))
        assertFalse(step.body.has("text"))
        assertFalse(step.body.getJSONObject("seen").has("s002"))
    }

    @Test fun editsDuringTheUndoHoldCannotOverwriteANewerDecision() {
        val source = FakeStudioSource()
        val session = StudioHub(source, CoroutineScope(Dispatchers.Unconfined)).session("")
        val gate = CompletableDeferred<Unit>()
        val after = ArrayList<Boolean>()
        val decisions = StudioDecisions(session, "b1", { gate.await() }) { after += it }
        val line = scriptLine("one", "Câu tự viết.")
        val script = chapterScript(listOf(line)).copy(scopeRevision = "before")
        source.scriptChapters[1] = script
        decisions.hold(ScriptScopeLogic.decision(listOf(line), ScriptPerson("OTHER", "Khách", 0), script))
        source.scriptChapters[1] = script.copy(scopeRevision = "after")
        gate.complete(Unit)
        assertEquals(0, source.writes.size)
        assertEquals(listOf(false), after)
    }
}
