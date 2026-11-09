package vn.abook.player.readaloud

import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.Assume.assumeTrue
import java.io.File
import vn.abook.player.vieneu.VieneuUnits

class ReadingPunctuationTest {
    @Test
    fun corpusMatchesDesktopWhenProvided() {
        val path = System.getenv("ABOOK_READING_PARITY")
        assumeTrue("Optional private corpus export", path != null)
        var count = 0
        File(path!!).useLines(Charsets.UTF_8) { lines ->
            lines.forEach { line ->
                val case = JSONArray(line)
                assertEquals("Corpus line ${count + 1}", case.getString(1), ReadingPunctuation.separate(case.getString(0)))
                count++
            }
        }
        assertEquals(691890, count)
        println("Corpus parity: $count lines, 0 differences")
    }

    @Test
    fun desktopAndPhoneShareEveryBoundaryAndException() {
        val cases = JSONArray(File("../../../tests/fixtures/readaloud/reading_punctuation.json").readText(Charsets.UTF_8))
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val source = case.getString("source")
            val reading = case.getString("reading")
            assertEquals(source, reading, ReadingPunctuation.separate(source))
            assertEquals(source, reading, ReadingPunctuation.separate(reading))
            if (case.has("spoken")) {
                assertEquals(source, case.getString("spoken"), VieneuUnits.spokenTokens(VieneuUnits.tokens(source)).joinToString(" "))
            }
        }
    }

    @Test
    fun displayTokenCountAndListenerReadingRemainIntact() {
        assertEquals(listOf("lại. Khoảnh", "Chương", "bốn: hát pê"),
            VieneuUnits.spokenTokens(listOf("lại.Khoảnh", "Chương", "IV:HP")))
        assertEquals(listOf("đọc-riêng"),
            VieneuUnits.spokenTokens(listOf("Hello?What"), readings = mapOf("Hello?What" to "đọc riêng")))
    }
}
