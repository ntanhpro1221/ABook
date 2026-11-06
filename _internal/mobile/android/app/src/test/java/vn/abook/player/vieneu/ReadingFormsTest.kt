package vn.abook.player.vieneu

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import vn.abook.player.readaloud.SpokenText
import vn.abook.player.readaloud.Span
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
            val (shown, units) = VieneuUnits.units(text, 256)
            assertEquals("$id: source", text.split(" "), shown)
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
    fun bookLabelsPreserveSourceTimingAndListenerReadings() {
        val text = "Xem Chap.12 nhé."
        val (shown, _) = VieneuUnits.units(text, 256)
        assertEquals(listOf("Xem", "Chap.12", "nhé."), shown)
        val (said, spans) = SpokenText.layout(text, null, null)
        assertEquals("Xem chương 12 nhé.", said)
        assertEquals(listOf(SpokenText.Range(0, 0), SpokenText.Range(1, 2), SpokenText.Range(3, 3)), spans)
        assertEquals(listOf(Span(0, 100), Span(100, 500), Span(500, 700)),
            SpokenText.expandWords(listOf(Span(0, 100), Span(100, 300), Span(300, 500), Span(500, 700)), spans))
        for (origin in listOf(null, "ja", "ko"))
            assertEquals("chương 12", VieneuUnits.spokenTokens(shown, origin)[1])
        assertEquals("Xem mục-riêng nhé.", SpokenText.layout(text, null, mapOf("Chap.12" to "mục riêng")).first)
    }

    @Test
    fun numbersUpToThreeHundredNinetyNineInWords() = assertEquals(
        listOf("bốn mươi", "bốn mươi mốt", "bốn mươi bốn", "bốn mươi lăm", "chín mươi chín", "một trăm", "một trăm lẻ một", "một trăm lẻ năm",
            "một trăm mười", "một trăm mười lăm", "một trăm hai mươi mốt", "hai trăm", "ba trăm lẻ năm", "ba trăm chín mươi chín"),
        listOf(40, 41, 44, 45, 99, 100, 101, 105, 110, 115, 121, 200, 305, 399).map(VieneuUnits::vietnameseNumber))

    @Test
    fun typographicHonorificsReuseExistingReadingsForEveryOrigin() {
        for (origin in listOf(null, "ja", "ko"))
            for (hyphen in "‐‑‒–")
                for (word in listOf("Himuro-kun", "jii-chan", "Aria-chan", "Haruto-san"))
                    assertEquals(VieneuUnits.spokenTokens(listOf(word), origin),
                        VieneuUnits.spokenTokens(listOf(word.replace('-', hyphen)), origin))
    }

    @Test
    fun nextFormsPreserveOverridesAndTiming() {
        for (word in listOf("v.v.", "Himuro–kun")) {
            val text = "Đọc $word nhé."
            val (said, spans) = SpokenText.layout(text, null, null)
            assertEquals(3, spans.size)
            val intervals = said.split(" ").indices.map { Span(it * 100L, (it + 1) * 100L) }
            val mapped = SpokenText.expandWords(intervals, spans)
            assertEquals(3, mapped.size)
            assertEquals(intervals.first(), mapped.first())
            assertEquals(intervals.last(), mapped.last())
            val key = word.trimEnd('.')
            val tail = if (word.endsWith('.')) "." else ""
            assertEquals("Đọc mục-riêng$tail nhé.", SpokenText.layout(text, null, mapOf(key to "mục riêng")).first)
        }
    }
}
