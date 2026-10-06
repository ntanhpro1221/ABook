package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File

/**
 * Dòng ngăn cảnh của đọc to ("***", "◆", "*" đứng riêng một đoạn) trên bộ ví dụ DÙNG CHUNG với pytest (test_a_listen_scene_break_rule_is_shared.py, luật gốc
 * text_processing.is_scene_break_line) và vitest (textScript.test.ts): cùng hằng số, cùng cách phân loại dòng, cùng cách chia đoạn và quãng lặng.
 */
class SceneBreakTest {
    private val cases: JSONObject = File("../../../tests/fixtures/scene_break/cases.json").also {
        if (!it.isFile) fail("Không thấy bộ ví dụ dùng chung: ${it.absoluteFile}")
    }.readText(Charsets.UTF_8).let(::JSONObject)

    private fun strings(array: JSONArray): List<String> = (0 until array.length()).map { array.getString(it) }

    @Test
    fun hasTheConstantsOfThePythonRule() {
        assertEquals(cases.getInt("ms"), Paragraphs.SCENE_BREAK_MS)
        assertEquals(cases.getString("ruleGlyphs"), Paragraphs.SCENE_BREAK_RULE_GLYPHS)
        assertEquals(cases.getString("aloneGlyphs"), Paragraphs.SCENE_BREAK_ALONE_GLYPHS)
        assertEquals(cases.getString("ornamentGlyphs"), Paragraphs.SCENE_BREAK_ORNAMENT_GLYPHS)
        assertEquals(cases.getInt("minRuleGlyphs"), Paragraphs.SCENE_BREAK_MIN_RULE_GLYPHS)
        assertEquals(cases.getInt("maxGlyphs"), Paragraphs.SCENE_BREAK_MAX_GLYPHS)
    }

    @Test
    fun classifiesTheSharedLines() {
        val separators = strings(cases.getJSONArray("separators"))
        val lone = strings(cases.getJSONArray("loneSeparators"))
        val not = strings(cases.getJSONArray("notSeparators"))
        assertTrue(separators.isNotEmpty() && lone.isNotEmpty() && not.isNotEmpty())
        assertEquals(emptyList<String>(), separators.filter { !Paragraphs.isSceneBreakLine(it) || !Paragraphs.isSceneBreakLine(it, alone = true) })
        assertEquals(emptyList<String>(), not.filter { Paragraphs.isSceneBreakLine(it) || Paragraphs.isSceneBreakLine(it, alone = true) })
        // một-hai dấu kẻ chỉ là ngăn cảnh khi đứng riêng một đoạn
        assertEquals(emptyList<String>(), lone.filter { Paragraphs.isSceneBreakLine(it) || !Paragraphs.isSceneBreakLine(it, alone = true) })
        val max = cases.getInt("maxGlyphs")
        assertTrue(Paragraphs.isSceneBreakLine("*".repeat(max)))
        assertTrue(!Paragraphs.isSceneBreakLine("*".repeat(max + 1)))
    }

    @Test
    fun splitsAndPausesLikeTheSharedCases() {
        val all = cases.getJSONArray("paragraphs")
        assertTrue(all.length() >= 10)
        for (i in 0 until all.length()) {
            val case = all.getJSONObject(i)
            val name = case.getString("name")
            val split = Paragraphs.split(case.getString("text"))
            assertEquals("$name: đoạn", strings(case.getJSONArray("paragraphs")), split.map { it.text })
            assertEquals("$name: of", strings(case.getJSONArray("paragraphs")), Paragraphs.of(case.getString("text")))
            val breaks = case.getJSONArray("breaks")
            assertEquals("$name: cờ ngăn cảnh", (0 until breaks.length()).map { breaks.getBoolean(it) }, split.map { it.sceneBreak })
            val gaps = case.getJSONArray("gapsMs")
            assertEquals("$name: quãng lặng", (0 until gaps.length()).map { gaps.getInt(it) }, Paragraphs.sceneBreakGaps(split).toList())
        }
    }

    @Test
    fun anEllipsisBetweenSeparatorsDoesNotCutTheRun() {
        val items = listOf("A.", "***", "...", "◆", "B.").map { Paragraphs.Paragraph(it, Paragraphs.isSceneBreakLine(it)) }
        assertEquals(listOf(0, Paragraphs.SCENE_BREAK_MS, 0, 0, 0), Paragraphs.sceneBreakGaps(items).toList())
    }

    @Test
    fun speakableMeansALetterOrADigit() {
        assertTrue(Paragraphs.isSpeakable("Đã 1"))
        assertTrue(Paragraphs.isSpeakable("½"))
        assertTrue(!Paragraphs.isSpeakable("* * *"))
        assertTrue(!Paragraphs.isSpeakable("…"))
    }
}
