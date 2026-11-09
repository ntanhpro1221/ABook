package vn.abook.player.ui.nowplaying

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

/** Hình tô chữ bo góc, luật dòng đi theo từ, và mốc từ từ JSON tới được chỗ tô. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35])
class ReadInkTest {
    private fun line(left: Float, top: Float, right: Float, bottom: Float) = InkLine(left, top, right, bottom)

    @Test fun twoLinesOfEqualWidthAreOneBlockWithFourRoundedCorners() {
        val corners = ReadInk.outline(listOf(line(0f, 0f, 100f, 30f), line(0f, 30f, 100f, 60f)), 8f)
        assertEquals("các dòng cùng lề nối liền, không có cạnh ngang giữa", 4, corners.size)
        for (corner in corners) {
            assertTrue("góc phải được bo: $corner", corner.fromX != corner.cornerX || corner.fromY != corner.cornerY)
            assertTrue("góc phải được bo: $corner", corner.toX != corner.cornerX || corner.toY != corner.cornerY)
        }
        assertEquals(0f, corners[0].cornerX, 0f); assertEquals(0f, corners[0].cornerY, 0f)
        assertEquals(8f, corners[0].fromY, 0f); assertEquals(8f, corners[0].toX, 0f)
    }

    @Test fun aRaggedRightEdgeBecomesRoundedStepsNotBoxes() {
        // Như ảnh chủ sách: dòng 1, 2 dài, dòng 3 ngắn; mép phải lệch cả ở dòng 1-2.
        val corners = ReadInk.outline(listOf(line(0f, 0f, 200f, 30f), line(0f, 30f, 180f, 60f), line(0f, 60f, 90f, 90f)), 8f)
        assertEquals(8, corners.size)
        val steps = corners.filter { it.cornerX == 180f && it.cornerY == 30f || it.cornerX == 90f && it.cornerY == 60f }
        assertEquals("góc lõm ở chỗ mép phải thụt vào cũng bo", 2, steps.size)
    }

    @Test fun theRadiusNeverExceedsHalfOfAShortStep() {
        val corners = ReadInk.outline(listOf(line(0f, 0f, 100f, 30f), line(0f, 30f, 96f, 60f)), 8f)
        val step = corners.first { it.cornerX == 100f && it.cornerY == 30f }
        assertEquals("bậc 4 px: bán kính còn 2 px, viền không tự cắt", 28f, step.fromY, 0.001f)
        assertEquals(98f, step.toX, 0.001f)
    }

    @Test fun anEmptyLineDrawsNothing() {
        assertTrue(ReadInk.outline(listOf(line(5f, 0f, 5f, 30f)), 8f).isEmpty())
        assertTrue(ReadInk.outline(emptyList(), 8f).isEmpty())
    }

    private val words = listOf(WordTiming(0, 100, 0, 3), WordTiming(100, 200, 4, 7), WordTiming(200, 300, 8, 11))
    private val lineOf = { offset: Int -> offset / 4 } // mỗi từ một dòng

    @Test fun theLineFollowsTheWordNotTheSentence() {
        assertEquals(0, ReadFollow.lineAt(words, 10, lineOf))
        assertEquals(1, ReadFollow.lineAt(words, 150, lineOf))
        assertEquals(2, ReadFollow.lineAt(words, 250, lineOf))
    }

    @Test fun aLongPauseAfterTheLastWordKeepsItsLineInsteadOfJumpingBack() {
        assertEquals("từ cuối đã tắt", -1, ReadAlongLookup.word(words, 300 + 401))
        assertEquals(2, ReadFollow.lineAt(words, 300 + 401, lineOf))
    }

    @Test fun aSentenceWithoutWordMarksStaysOnItsFirstLine() {
        assertEquals(0, ReadFollow.lineAt(emptyList(), 5000, lineOf))
    }

    /** Hồi quy: có mốc từ trong kịch bản (cả sách thu sẵn lẫn đọc ngay) thì mỗi mốc phải ra được một từ để tô. */
    private fun assertEveryWordLights(paragraph: ReadParagraph, count: Int) {
        assertEquals(count, paragraph.words.size)
        for ((index, word) in paragraph.words.withIndex()) assertEquals(index, ReadAlongLookup.word(paragraph.words, word.startMs))
    }

    @Test fun recordedScriptWordsReachTheHighlight() {
        val script = JSONObject("""{"timed":true,"segments":[{"text":"Chương 4: Killer Cage","start":0.0,"end":1.645,"words":[[80,350],[350,620],[620,1000],[1000,1600]]}]}""")
        assertEveryWordLights(ReadAlongLookup.parse(script).single(), 4)
    }

    @Test fun readNowScriptWordsReachTheHighlight() {
        // Đúng hình ReadAloud.script: chữ ở "paragraphs", mốc ở "segments", đồng hồ ảo.
        val script = JSONObject("""{"active":true,"paragraphs":["Một hai ba"],"segments":[{"index":0,"start":1.0,"end":2.0,"timed":true,"words":[[1000,1300],[1300,1600],[1600,2000]]}]}""")
        val paragraph = ReadAlongLookup.parse(script).single()
        assertTrue(paragraph.timed)
        assertEveryWordLights(paragraph, 3)
    }
}
