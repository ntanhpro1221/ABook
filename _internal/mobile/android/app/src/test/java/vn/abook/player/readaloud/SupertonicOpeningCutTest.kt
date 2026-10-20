package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.vieneu.NumpyRandomState
import vn.abook.player.vieneu.VieneuUnits
import java.io.File

/** The first unit of a Supertonic paragraph is cut short (livejoin2): the same cases as the desktop (tests/fixtures/supertonic/opening_cut.json, tests/test_supertonic_opening_cut.py). */
class SupertonicOpeningCutTest {
    private val cases = JSONObject(File("../../../tests/fixtures/supertonic/opening_cut.json").readText(Charsets.UTF_8)).getJSONArray("cases")

    @Test
    fun everySharedCaseIsCutTheSameWay() {
        assertTrue(cases.length() >= 8)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            val (tokens, units) = SupertonicText.units(case.getString("text"), if (case.isNull("origin")) null else case.getString("origin"), null)
            val expected = case.getJSONArray("units")
            assertEquals(case.getString("name"), expected.length(), units.size)
            for ((at, unit) in units.withIndex()) {
                val want = expected.getJSONObject(at)
                assertEquals(case.getString("name"), want.getString("text"), unit.text(tokens))
                assertEquals(case.getString("name"), (0 until want.getJSONArray("pieces").length()).map { want.getJSONArray("pieces").getString(it) }, unit.pieces)
            }
        }
    }

    @Test
    fun onlyTheFirstUnitIsCutAndEveryWordIsInExactlyOneUnit() {
        for (index in 0 until cases.length()) {
            val text = cases.getJSONObject(index).getString("text")
            val (tokens, plain) = VieneuUnits.units(text, SupertonicText.MAX_CHARS)
            val (_, units) = SupertonicText.units(text)
            assertEquals(0, units.first().first)
            assertEquals(tokens.size - 1, units.last().last)
            assertTrue(units.zipWithNext().all { (a, b) -> a.last + 1 == b.first })
            if (units.size != plain.size) {
                assertEquals(plain.size + 1, units.size)
                assertEquals(plain.drop(1).map { it.first to it.last }, units.drop(2).map { it.first to it.last })
            }
        }
    }

    @Test
    fun aParagraphOfOneLongUnitIsReadAsTwoTakes() {
        val engine = object : SupertonicSynth {
            override val sampleRate = 44_100
            val calls = ArrayList<String>()
            override fun infer(text: String, name: String, random: NumpyRandomState, speed: Double): FloatArray {
                calls.add(text)
                return FloatArray(44_100) { 0.1f }
            }
        }
        val text = cases.getJSONObject(1).getString("text")
        SupertonicSpeaker(null) { pieces -> pieces.joinToString(" ") }.speak(engine, "F1", text)
        assertEquals(2, engine.calls.size)
        assertTrue("the first take is the short opening", engine.calls[0].length <= SupertonicText.OPENING_MAX)
    }
}
