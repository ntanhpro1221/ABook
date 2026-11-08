package vn.abook.player.readaloud

import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

class EnglishDirectTest {
    @Test
    fun sharedSentencesHaveTheSameReadingAsDesktop() {
        val fixture = JSONObject(File("../../../tests/fixtures/readaloud/english_direct/cases.json").readText(Charsets.UTF_8))
        val cases = fixture.getJSONArray("cases")
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val text = case.getString("text")
            val origin = if (case.isNull("origin")) null else case.getString("origin")
            val readings = case.optJSONObject("readings")?.let { obj -> obj.keys().asSequence().associateWith { obj.getString(it) } }
            assertEquals(text, case.getString("said"), VieneuUnits.spokenTokens(VieneuUnits.tokens(text), origin, readings, directEnglish = true).joinToString(" "))
            val units = VieneuUnits.units(text, 256, origin, readings, directEnglish = true).second
            assertEquals(text, case.getString("said"), units.flatMap { it.pieces }.joinToString(" "))
        }
    }

    @Test
    fun policyDataAndCacheAreVersionedTogether() {
        val policy = JSONObject(File("../../../abook/readaloud/english_policy.json").readText(Charsets.UTF_8))
        assertEquals(policy.getInt("version"), EnglishPolicy.VERSION)
        assertEquals("auto", EnglishPolicy.PROVENANCE)
        assertTrue(EnglishPolicy.ACRONYMS.containsAll(listOf("UDF", "MIT", "GPS", "DNA", "ID")))
        assertEquals("direct-en${EnglishPolicy.VERSION}+jp-fallback4", VieneuUnits.readingTag("Tôi kiểm GPS.", null, directEnglish = true))
        assertEquals("", VieneuUnits.readingTag("Tôi kiểm GPS.", null))
    }
}
