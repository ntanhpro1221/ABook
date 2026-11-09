package vn.abook.player.readaloud

import java.io.File
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import vn.abook.player.vieneu.VieneuUnits

class JapaneseFallbackTest {
    @Test fun sharedReadingOwnership() {
        val cases = org.json.JSONArray(File("../../../tests/fixtures/readaloud/japanese_fallback/ownership.json").readText(Charsets.UTF_8))
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val text = c.getString("text")
            val origin = if (c.isNull("origin")) null else c.getString("origin")
            val toks = text.split(" ")
            assertEquals(text, c.getString("said"), VieneuUnits.spokenTokens(toks, origin, directEnglish = true).joinToString(" "))
            val first = Names.splitToken(toks.first()).second
            assertTrue(text, "đã-chọn" in VieneuUnits.spokenTokens(toks, origin, readings = mapOf(first to "đã chọn"), directEnglish = true).first())
        }
    }

    @Test fun sharedBookEvidenceAndPresentation() {
        val cases = org.json.JSONArray(File("../../../tests/fixtures/readaloud/japanese_fallback/book_evidence.json").readText(Charsets.UTF_8))
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val token = c.getString("token")
            val origin = if (c.isNull("origin")) null else c.getString("origin")
            assertEquals(token, if (c.isNull("reading")) null else c.getString("reading"), JapanesePolicy.reading(token, origin))
            if (c.has("spoken")) assertEquals(token, listOf(c.getString("spoken")), VieneuUnits.spokenTokens(listOf(token), origin, directEnglish = true))
        }
    }

    @Test fun sharedPolicyAndFallbackFixture() {
        val policy = JSONObject(File("../../../abook/readaloud/japanese_policy.json").readText(Charsets.UTF_8))
        assertEquals(policy.getString("namespace"), JapanesePolicy.NAMESPACE)
        assertEquals("auto", JapanesePolicy.PROVENANCE)
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/japanese_fallback/cases.json").readText(Charsets.UTF_8)).getJSONArray("cases")
        assertTrue(cases.length() >= 58)
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val token = c.getString("token")
            val origin = if (c.isNull("origin")) null else c.getString("origin")
            val found = Romanization.readingWithFlags(token, origin)
            assertEquals(token, if (c.isNull("reading")) null else c.getString("reading"), found?.text)
            val flags = c.getJSONArray("flags")
            assertEquals(token, (0 until flags.length()).map { flags.getString(it) }, found?.flags ?: emptyList<String>())
            assertEquals(token, c.getString("said"), VieneuUnits.spokenTokens(c.getString("text").split(" "), origin, directEnglish = true).joinToString(" "))
        }
    }

    @Test fun japaneseNamesDoNotEnterKeepEnglish() {
        for (word in listOf("Tanaka", "Nakata", "Haruto")) assertNull(word, EnglishPolicy.reading(word, "ja"))
        assertTrue(VieneuUnits.readingTag("Tôi ghi tên.", null, directEnglish = true).endsWith(JapanesePolicy.NAMESPACE))
    }

    @Test fun sharedGeneralRoutingFixture() {
        val cases = JSONObject(File("../../../tests/fixtures/readaloud/japanese_fallback/cases.json").readText(Charsets.UTF_8)).getJSONArray("routing")
        for (i in 0 until cases.length()) {
            val c = cases.getJSONObject(i)
            val toks = c.getString("text").split(" ")
            val contextual = JapanesePolicy.contextualNames(toks)
            val actual = toks.indices.filter { index ->
                val (before, core, after) = Names.splitToken(toks[index])
                before.lastOrNull()?.isDigit() != true && !Regex("^[-–]?[0-9]").containsMatchIn(after) &&
                    JapanesePolicy.reading(core, null, index in contextual) != null
            }
            val expected = c.getJSONArray("indices")
            assertEquals(c.getString("text"), (0 until expected.length()).map { expected.getInt(it) }, actual)
        }
        for (word in listOf("Abe", "Jin", "Aya", "Rita", "Tina", "Mary", "Rachel")) {
            assertNull(word, JapanesePolicy.reading(word, null))
            if (word == "Aya") assertNotNull(word, JapanesePolicy.reading(word, "ja"))
            else assertNull(word, JapanesePolicy.reading(word, "ja"))
        }
        assertNotNull(JapanesePolicy.reading("Anime", null))
        assertNotNull(JapanesePolicy.reading("Anime", "ja"))
        assertEquals(3, JapanesePolicy.syllables("Tanaka"))
        assertEquals(2, JapanesePolicy.syllables("Satou"))
        assertEquals(0, JapanesePolicy.syllables("English"))
    }
}
