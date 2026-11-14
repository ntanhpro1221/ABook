package vn.abook.player.ui.studio

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.StudioPaths

class StudioEditContractTest {
    private fun assertJson(label: String, expected: Any?, actual: Any?) {
        when {
            expected is JSONObject && actual is JSONObject -> {
                assertEquals(label, expected.keys().asSequence().toSet(), actual.keys().asSequence().toSet())
                expected.keys().forEach { key -> assertJson("$label.$key", expected.get(key), actual.get(key)) }
            }
            expected is JSONArray && actual is JSONArray -> {
                assertEquals(label, expected.length(), actual.length())
                for (i in 0 until expected.length()) assertJson("$label[$i]", expected.get(i), actual.get(i))
            }
            expected is Number && actual is Number -> assertEquals(label, expected.toDouble(), actual.toDouble(), 0.0)
            else -> assertEquals(label, expected, actual)
        }
    }
    private val person = castMember("LUCIEN", "Lucien")
    private val target = castMember("NATASHA", "Natasha")
    private val narrator = scriptLine("c1s0", "Đèn sân đã sáng.", kind = "narration", current = "NARRATOR", editable = false).copy(emotion = "neutral", intensity = 0)

    @Test fun twelveSharedCasesProduceTheWebRequestBodies() {
        val cases = JSONArray(File("../../../tests/fixtures/studio_edits/cases.json").readText())
        assertEquals(12, cases.length())
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val id = case.getString("id")
            if (case.optString("transport") == "listen-only") continue // exercised through the state guard
            val speaker = ScriptPerson(case.optString("speaker", "NATASHA"), "Natasha", 2, case.optString("newGender"))
            val decision = when (case.getString("op")) {
                "assign" -> ScriptEdits.assign(case.getJSONArray("ids").let { ids -> (0 until ids.length()).map { scriptLine(ids.getString(it), "Xin đặt ghế ở đây.") } }, speaker)
                "delivery" -> ScriptEdits.delivery(narrator, case.getString("kind"), "neutral", 0, speaker)!!
                "rename" -> StudioPeopleEdits.rename(person, "Bác Trực", listOf(person, target))
                "gender" -> StudioPeopleEdits.gender(person, "female")
                "merge" -> StudioPeopleEdits.merge(person, target)
                "unmerge" -> StudioPeopleEdits.unmerge(person.copy(mergedInto = "NATASHA", mergedAt = 42.0), JSONObject("""{"items":[{"section":"speakers","requestedAt":42,"keys":["c1s1","c1s2"]}]}"""))!!
                else -> error(id)
            }
            val expected = case.getJSONArray("expected")
            assertEquals(id, expected.length(), decision.steps.size)
            decision.steps.forEachIndexed { n, step ->
                val wanted = expected.getJSONObject(n)
                assertEquals(id, wanted.getString("endpoint"), step.endpoint)
                assertJson(id, wanted.getJSONObject("body"), step.body)
                assertTrue(StudioPaths.write("b1", step.endpoint).endsWith("/" + step.endpoint))
                assertFalse(step.body.has("text"))
            }
        }
    }

    @Test fun narrationNeedsARealPersonAndNewPeopleUseTwoRequests() {
        assertNull(ScriptEdits.delivery(narrator, "thought", "neutral", 0, null))
        assertNull(ScriptEdits.delivery(narrator, "thought", "neutral", 0, ScriptLogic.FIXED.first()))
        val decision = ScriptEdits.delivery(narrator, "thought", "sad", 2, ScriptPerson("Bác Trực", "Bác Trực", 0, "male"))!!
        assertEquals(listOf("line", "speaker"), decision.steps.map { it.endpoint })
        assertFalse(decision.steps[0].body.has("speaker"))
        assertEquals("sad", decision.steps[0].body.getString("emotion"))
        assertEquals(2, decision.steps[0].body.getInt("intensity"))
        assertTrue(decision.rollbackLine)
    }

    @Test fun missingHashesInvalidDeliveryAndStaleMergesFailClosed() {
        assertNull(ScriptEdits.delivery(narrator.copy(textSha256 = ""), "dialogue", "neutral", 0, ScriptPerson("NATASHA", "Natasha", 1)))
        assertNull(ScriptEdits.delivery(narrator, "unknown", "neutral", 0, null))
        assertNull(ScriptEdits.delivery(narrator, "narration", "wrong", 0, null))
        assertNull(ScriptEdits.delivery(narrator, "narration", "sad", 4, null))
        assertNull(StudioPeopleEdits.unmerge(person.copy(mergedAt = 42.0), JSONObject("""{"items":[{"section":"speakers","requestedAt":43,"key":"c1s1"}]}""")))
        assertNull(StudioPeopleEdits.unmerge(person, JSONObject()))
        assertEquals("Bình thường", ScriptEdits.deliveryText("neutral", 0))
        assertEquals("Buồn · rất mạnh", ScriptEdits.deliveryText("sad", 3))
    }

    @Test fun heldBatchOnlyChangesSelectedLinesAndNeverSourceText() {
        val lines = listOf("a", "b", "c").map { scriptLine(it, "Xin đặt ghế ở đây.") }
        val original = chapterScript(lines)
        val decision = ScriptEdits.assign(listOf(lines[0], lines[2]), ScriptPerson("TOM", "Tom", 1))
        val shown = ScriptLogic.withHeld(original, decision)
        assertEquals(listOf("TOM", "KATI", "TOM"), shown.lines.map(ScriptLogic::speaker))
        assertEquals(original.lines.map { it.text }, shown.lines.map { it.text })
        assertEquals(listOf("a", "c"), ScriptEdits.visible(shown, ScriptFilter.All, "ghế", "TOM").map { it.line.stableId })
        assertEquals(listOf("a", "c"), ScriptEdits.visible(shown, ScriptFilter.All, "GHE", "TOM").map { it.line.stableId })
        assertTrue(decision.summary.contains("2"))
    }
}
