package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.nio.file.Files

/**
 * Edge nhận CÙNG chữ đem đọc với giọng trên máy, trên bộ ví dụ DÙNG CHUNG với Python (tests/fixtures/readaloud/spoken/, `tests/test_readaloud_spoken.py`): `layout.json` (chữ gốc ->
 * chuỗi gửi Edge + khoảng chữ đọc của từng chữ hiện; 21 ca đo a39 + 2 ca cách đọc riêng), `words.json` (mốc Edge báo trên chuỗi đọc -> mốc từng chữ hiện, tính tay).
 */
class SpokenTextTest {
    private val dir: File = File("../../../tests/fixtures/readaloud/spoken").also {
        if (!it.isDirectory) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }

    private fun load(name: String): JSONArray = JSONArray(File(dir, name).readText(Charsets.UTF_8))

    private fun readings(json: JSONObject): Map<String, String>? =
        json.optJSONObject("readings")?.let { table -> table.keys().asSequence().associateWith { table.getString(it) } }

    private fun origin(json: JSONObject): String? = if (json.isNull("origin")) null else json.getString("origin")

    @Test
    fun everySharedCaseGivesEdgeTheSameTextAsTheDesktop() {
        val cases = load("layout.json")
        assertTrue("thiếu ví dụ", cases.length() >= 20)
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val (said, spans) = SpokenText.layout(case.getString("text"), origin(case), readings(case))
            val id = case.getString("id")
            assertEquals("$id: chuỗi gửi Edge", case.getString("spoken"), said)
            val want = case.getJSONArray("spans")
            assertEquals("$id: số khoảng", want.length(), spans.size)
            for (k in spans.indices) {
                val expected = if (want.isNull(k)) null else SpokenText.Range(want.getJSONArray(k).getInt(0), want.getJSONArray(k).getInt(1))
                assertEquals("$id: khoảng của chữ $k", expected, spans[k])
            }
        }
    }

    @Test
    fun theWordsComeBackToTheShownTokens() {
        val cases = load("words.json")
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val (said, spans) = SpokenText.layout(case.getString("text"), origin(case), readings(case))
            val pieces = case.getJSONArray("boundaries")
            val boundaries = (0 until pieces.length()).map {
                val item = pieces.getJSONObject(it)
                Boundary(item.getLong("start"), item.getLong("end"), item.getString("text"))
            }
            val got = SpokenText.expandWords(WordTokens.map(said, boundaries, case.getLong("durationMs")), spans)
            val want = case.getJSONArray("words")
            assertEquals("${case.getString("note")}: số chữ", want.length(), got.size)
            for (k in got.indices) {
                assertEquals("${case.getString("note")}: chữ $k", listOf(want.getJSONArray(k).getLong(0), want.getJSONArray(k).getLong(1)), listOf(got[k].start, got[k].end))
            }
        }
    }

    @Test
    fun aParagraphThatNormalisesToNothingIsReadAsWritten() {
        assertEquals("*" to listOf(SpokenText.Range(0, 0)), SpokenText.layout("*", null))
    }

    /** Một giọng Edge giả: ghi lại chữ nó nhận, báo mỗi chữ 300 ms. */
    private class FakeEdge : Voice {
        override val id = "edge:vi-VN-HoaiMyNeural"
        override val extension = "mp3"
        val heard = ArrayList<String>()
        override fun synthesize(text: String, out: File): Clip {
            heard.add(text)
            out.writeBytes(ByteArray(10) { 1 })
            val words = text.split(" ").filter { it.isNotEmpty() }
            return Clip(out, words.size * 300L, words.indices.map { Span(it * 300L, it * 300L + 250) }, id)
        }
    }

    @Test
    fun edgeGetsTheNormalisedTextAndEachShownWordKeepsOneHighlight() {
        val voice = FakeEdge()
        val text = "Haaah, HP 1,500 và Otsuki-san."
        val clip = voice.synthesize(text, File.createTempFile("edge", ".mp3"), "ja", null)
        assertEquals("ha… a, hát pê 1500 và o-xu-ki-xan.", voice.heard.single())
        assertEquals(text.split(" ").size, clip.words.size)
        assertEquals(Span(0, 550), clip.words[0])
        assertTrue(clip.words.zipWithNext().all { (a, b) -> a.start <= a.end && a.end <= b.start })
    }

    @Test
    fun theCacheKeyOfEdgeIsNotTheRawOneAndFollowsTheOrigin() {
        val text = "Otsuki-san hỏi về Okayama."
        val edge = "edge:vi-VN-HoaiMyNeural"
        assertTrue(SpokenText.normalises(edge))
        assertFalse(SpokenText.normalises("azure:vi-VN-HoaiMyNeural") || SpokenText.normalises("vieneu:turbo/x") || SpokenText.normalises("device:vi"))
        assertEquals("ja+tn", ClipCache.reading(edge, text, "ja"))
        assertEquals("tn", ClipCache.reading(edge, text, null))
        assertNotEquals(ClipCache.reading(edge, text, "ja"), ClipCache.reading(edge, text, null))
        assertEquals("", ClipCache.reading("azure:vi-VN-HoaiMyNeural", text, "ja"))
        val dir = Files.createTempDirectory("spoken-cache").toFile()
        try {
            val cache = ClipCache(dir)
            val tmp = cache.temp("mp3").also { it.writeBytes(ByteArray(10) { 1 }) }
            cache.put(edge, text, tmp, "mp3", 900, listOf(Span(0, 900)), null, null)
            assertTrue(cache.contains(edge, text))
            assertEquals(ClipCache.key("edge", "vi-VN-HoaiMyNeural", text, "tn"), File(dir, "${ClipCache.key("edge", "vi-VN-HoaiMyNeural", text, "tn")}.json").name.removeSuffix(".json"))
            assertFalse("clip làm từ chữ thô (khoá cũ) không trúng", File(dir, "${ClipCache.key("edge", "vi-VN-HoaiMyNeural", text)}.json").isFile)
        } finally {
            dir.deleteRecursively()
        }
    }
}
