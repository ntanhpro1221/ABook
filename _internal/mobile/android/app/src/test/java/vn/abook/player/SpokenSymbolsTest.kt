package vn.abook.player

import org.json.JSONArray
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/** SpokenSymbols.toWords phải ra đúng chữ của `text_processing.spoken_symbols_to_words`: bộ ví dụ dùng chung tests/fixtures/book_edits/spoken_symbols.json. */
class SpokenSymbolsTest {
    @Test
    fun everySharedCaseSaysWhatTheProducerSays() {
        val cases = BookEditsFixtures.json("spoken_symbols.json") as JSONArray
        assertTrue(cases.length() >= 30)
        for (index in 0 until cases.length()) {
            val case = cases.getJSONObject(index)
            assertEquals(case.getString("text"), case.getString("spoken"), SpokenSymbols.toWords(case.getString("text")))
        }
    }

    @Test
    fun aSlashBetweenTwoUnitsStaysAndOneBetweenWordsIsAPause() {
        assertEquals("Xe chạy 60 km/h", SpokenSymbols.toWords("Xe chạy 60 km/h"))
        assertEquals("Mở, đóng cửa", SpokenSymbols.toWords("Mở/đóng cửa"))
    }
}
