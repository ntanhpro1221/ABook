package vn.abook.player.readaloud

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

class SoundfixTest {
    @Test fun sharedSelfAuthoredSentencesPreserveShownWords() {
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/soundfix/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val text = case.getString("text")
            val readings = case.optJSONObject("readings")?.let { obj -> obj.keys().asSequence().associateWith { obj.getString(it) } }
            val shown = VieneuUnits.tokens(text)
            val said = VieneuUnits.spokenTokens(shown, "ja", readings, directEnglish = true)
            assertEquals(text, case.getString("said"), said.filter { it.isNotEmpty() }.joinToString(" "))
            val (display, units) = VieneuUnits.units(text, 256, "ja", readings, directEnglish = true)
            assertEquals(shown, display)
            assertEquals(text, case.getString("said"), units.flatMap { it.pieces }.joinToString(" "))
        }
    }

    @Test fun sharedDataAndCacheNamespaceMatchDesktop() {
        val disk = JSONObject(File("../../../abook/readaloud/sound_policy.json").readText(Charsets.UTF_8))
        assertEquals(disk.keys().asSequence().toSet(), Shouts.POLICY.keys().asSequence().toSet())
        for (key in disk.keys()) assertEquals(key, disk.get(key).toString(), Shouts.POLICY.get(key).toString())
        assertEquals(10, ClipCache.CACHE_RULES)
        assertEquals(8, Shouts.stretchReading("a" + "ha".repeat(100))!!.split(" ").size)
    }
}
