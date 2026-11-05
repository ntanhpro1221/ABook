package vn.abook.player.vieneu

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import vn.abook.player.readaloud.SpokenText
import java.io.File

/**
 * Pauses and number patches (docs/TEXT_NORMALIZATION.md tier 5 + tier 2) on the case set SHARED with Python (tests/fixtures/readaloud/spoken/reading_forms.json,
 * `tests/test_readaloud_reading_forms.py`): the phone's VieNeu units and the text sent to Edge say exactly what the desktop says, word for word.
 */
class ReadingFormsTest {
    private val file: File = File("../../../tests/fixtures/readaloud/spoken/reading_forms.json").also {
        if (!it.isFile) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }

    @Test
    fun everySharedCaseIsReadLikeTheDesktop() {
        val cases = JSONObject(file.readText(Charsets.UTF_8)).getJSONArray("cases")
        assertTrue("thiếu ví dụ", cases.length() >= 80)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val id = case.getString("id")
            val text = case.getString("text")
            val (_, units) = VieneuUnits.units(text, 256)
            assertEquals("$id: VieNeu", case.getString("said"), units.flatMap { it.pieces }.filter { it.isNotEmpty() }.joinToString(" "))
            assertEquals("$id: Edge", case.getString("said"), SpokenText.layout(text, null, null).first)
        }
    }

    @Test
    fun aHesitationInsideASentenceDoesNotCutTheSentence() {
        val (_, units) = VieneuUnits.units("Tôi... tôi không biết. Ừm… Vâng.", 256)
        assertEquals(listOf(listOf("Tôi, tôi không biết.", "Ừm…", "Vâng.")), units.map { it.pieces.toList() })
    }

    @Test
    fun numbersUpToThreeHundredNinetyNineInWords() = assertEquals(
        listOf("bốn mươi", "bốn mươi mốt", "bốn mươi bốn", "bốn mươi lăm", "chín mươi chín", "một trăm", "một trăm lẻ một", "một trăm lẻ năm",
            "một trăm mười", "một trăm mười lăm", "một trăm hai mươi mốt", "hai trăm", "ba trăm lẻ năm", "ba trăm chín mươi chín"),
        listOf(40, 41, 44, 45, 99, 100, 101, 105, 110, 115, 121, 200, 305, 399).map(VieneuUnits::vietnameseNumber))
}
