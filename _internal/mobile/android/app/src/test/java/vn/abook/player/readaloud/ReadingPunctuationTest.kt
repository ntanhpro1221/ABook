package vn.abook.player.readaloud

import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File
import vn.abook.player.vieneu.VieneuUnits

class ReadingPunctuationTest {
    @Test
    fun desktopAndPhoneShareEveryBoundaryAndException() {
        val cases = JSONArray(File("../../../tests/fixtures/readaloud/reading_punctuation.json").readText(Charsets.UTF_8))
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val source = case.getString("source")
            val reading = case.getString("reading")
            assertEquals(source, reading, ReadingPunctuation.separate(source))
            assertEquals(source, reading, ReadingPunctuation.separate(reading))
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
