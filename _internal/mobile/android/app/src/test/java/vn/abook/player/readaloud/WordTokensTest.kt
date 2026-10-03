package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Ánh xạ mốc của giọng đọc sang từng chữ, trên bộ ví dụ DÙNG CHUNG với Python (các file .json trong tests/fixtures/readaloud, README.md ở đó viết thuật toán): mỗi file một ca,
 * `words` tính tay. Cộng thêm các điều bất biến (đúng số chữ, không giảm, không quá độ dài) và đường của giọng máy (mảnh kèm gợi ý vị trí ký tự).
 */
class WordTokensTest {
    private val dir: File = File("../../../tests/fixtures/readaloud").also {
        if (!it.isDirectory) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }

    private fun cases(): List<Pair<String, JSONObject>> =
        dir.listFiles { f -> f.name.endsWith(".json") }!!.sortedBy { it.name }.map { it.name to JSONObject(it.readText(Charsets.UTF_8)) }

    private fun boundaries(json: JSONObject): List<Boundary> {
        val array = json.getJSONArray("boundaries")
        return (0 until array.length()).map {
            val item = array.getJSONObject(it)
            Boundary(item.getLong("start"), item.getLong("end"), item.getString("text"), item.optInt("char", -1))
        }
    }

    @Test
    fun everySharedFixtureMapsToTheHandComputedWords() {
        val all = cases()
        assertTrue("thiếu ví dụ", all.size >= 10)
        for ((name, json) in all) {
            val want = json.getJSONArray("words")
            val got = WordTokens.map(json.getString("text"), boundaries(json), json.getLong("durationMs"))
            assertEquals("$name: số chữ", want.length(), got.size)
            for (i in got.indices) {
                assertEquals(
                    "$name: chữ $i (${json.getString("note")})",
                    listOf(want.getJSONArray(i).getLong(0), want.getJSONArray(i).getLong(1)), listOf(got[i].start, got[i].end),
                )
            }
        }
    }

    @Test
    fun everyFixtureKeepsTheInvariants() {
        for ((name, json) in cases()) {
            val duration = json.getLong("durationMs")
            val got = WordTokens.map(json.getString("text"), boundaries(json), duration)
            assertEquals(name, WordTokens.count(json.getString("text")), got.size)
            var last = 0L
            for (span in got) {
                assertTrue("$name: bắt đầu không giảm", span.start >= last)
                assertTrue("$name: kết thúc không trước bắt đầu", span.end >= span.start)
                assertTrue("$name: không quá độ dài", span.end <= duration)
                last = span.start
            }
        }
    }

    @Test
    fun countsTokensTheWayTheWordsViewDoes() {
        assertEquals(5, WordTokens.count("Xin chào — các bạn."))
        assertEquals(0, WordTokens.count("   "))
        assertEquals(2, WordTokens.count("a　b"))
    }

    @Test
    fun noBoundariesSpreadsTheDurationByWordLength() {
        val got = WordTokens.map("Một hai ba", emptyList(), 1000)
        assertEquals(listOf(Span(0, 375), Span(375, 750), Span(750, 1000)), got)
    }

    @Test
    fun theSameWordTwiceInARowMatchesTwoDifferentTokens() {
        val got = WordTokens.map("rất rất hay", listOf(Boundary(0, 200, "rất"), Boundary(300, 500, "rất"), Boundary(500, 900, "hay")), 1000)
        assertEquals(listOf(Span(0, 200), Span(300, 500), Span(500, 900)), got)
    }

    @Test
    fun deviceBoundariesWithCharHintsLandOnTheirOwnWords() {
        // Giọng máy báo từng chữ kèm vị trí ký tự; chữ đầu bị bộ đọc bỏ qua thì chữ sau vẫn đúng chỗ nhờ gợi ý.
        val text = "và và và"
        val got = WordTokens.map(text, listOf(Boundary(500, 800, "và", 3), Boundary(800, 1200, "và", 6)), 1500)
        assertEquals(Span(0, 500), got[0])
        assertEquals(Span(500, 800), got[1])
        assertEquals(Span(800, 1200), got[2])
    }

    @Test
    fun emptyTextHasNoWords() {
        assertEquals(emptyList<Span>(), WordTokens.map("   ", listOf(Boundary(0, 100, "x")), 100))
    }

    @Test
    fun boundariesPastTheEndOfTheClipAreClamped() {
        val got = WordTokens.map("ab cd", listOf(Boundary(0, 500, "ab"), Boundary(500, 5000, "cd")), 900)
        assertEquals(Span(500, 900), got[1])
    }
}
