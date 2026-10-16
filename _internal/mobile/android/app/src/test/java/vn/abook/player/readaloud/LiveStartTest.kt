package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Quyết định phát luồng (uxfix57): lượt đọc nào phát luồng, clip đuôi khi bấm giữa đoạn, và luật dùng / bỏ clip đuôi ([SeekPlan]). */
class LiveStartTest {
    private fun clip(duration: Long, words: List<Span> = emptyList(), from: Int = 0) = Clip(File("x.mp3"), duration, words, "edge:v", from)

    private val text = "Một hai ba bốn năm sáu bảy tám."

    // ---- LivePolicy ---------------------------------------------------------------------------------------------------------

    @Test
    fun onlyTheParagraphTheListenerWaitsForOnEdgeStreams() {
        assertTrue(LivePolicy.streams("edge:vi-VN-HoaiMyNeural", online = true, rank = 0, probe = false, waitingOffsetMs = null, waitingWord = -1))
        assertTrue(LivePolicy.streams("edge:vi-VN-HoaiMyNeural", true, 0, false, 0L, -1)) // đầu chương / nhảy tới đầu đoạn
        assertFalse("rank >= 1 (đọc trước) không phát luồng", LivePolicy.streams("edge:v", true, 1, false, null, -1))
        assertFalse("hỏi thăm ngầm", LivePolicy.streams("edge:v", true, 0, true, null, -1))
        assertFalse("giọng khác", LivePolicy.streams("azure:v", true, 0, false, null, -1))
        assertFalse("giọng khác", LivePolicy.streams("device:vi", true, 0, false, null, -1))
        assertFalse("giọng khác", LivePolicy.streams("vieneu:turbo/x", true, 0, false, null, -1))
        assertFalse("không trực tuyến", LivePolicy.streams("edge:v", false, 0, false, null, -1))
    }

    @Test
    fun aTimeBarSeekDeepIntoAnUnreadParagraphReadsItWholeButAWordTapStreams() {
        assertFalse(LivePolicy.streams("edge:v", true, 0, false, 23_000L, -1)) // thanh thời gian giữa đoạn: chỗ ấy ở sâu trong clip
        assertTrue(LivePolicy.streams("edge:v", true, 0, false, 0L, 5)) // bấm chữ: clip đuôi
    }

    // ---- clip đuôi ----------------------------------------------------------------------------------------------------------

    @Test
    fun theTailStartsAtTheTappedWordOnlyWhenStreamingAndOnlyForAWordInTheMiddle() {
        assertEquals(3, SeekPlan.tailFrom(3, text, true))
        assertEquals("bốn năm sáu bảy tám.", SeekPlan.tailText(text, 3))
        assertEquals(0, SeekPlan.tailFrom(3, text, false)) // không phát luồng: đọc cả đoạn như cũ
        assertEquals(0, SeekPlan.tailFrom(0, text, true)) // đầu đoạn: cả đoạn
        assertEquals(0, SeekPlan.tailFrom(-1, text, true)) // không bấm chữ
        assertEquals(0, SeekPlan.tailFrom(8, text, true)) // quá chữ cuối
        assertEquals(7, SeekPlan.tailFrom(7, text, true)) // chính chữ cuối
        assertEquals("tám.", SeekPlan.tailText(text, 7))
        // Chữ đếm theo \S+ như WordTokens: khoảng trắng kép và xuống dòng không đổi cách đếm.
        val spaced = "Một  hai\nba   bốn"
        assertEquals("ba   bốn", SeekPlan.tailText(spaced, 2))
        assertEquals(3, WordTokens.count(SeekPlan.tailText(spaced, 1)))
    }

    @Test
    fun tailWordsKeepEveryWordOfTheParagraphAndZeroTheOnesBeforeTheTap() {
        val tail = listOf(Span(100, 500), Span(550, 900))
        val words = SeekPlan.tailWords(3, tail)
        assertEquals(5, words.size)
        assertEquals(listOf(Span(0, 0), Span(0, 0), Span(0, 0)), words.take(3))
        assertEquals(tail, words.drop(3))
    }

    @Test
    fun aTailClipServesOnlyListeningInsideIt() {
        val tail = clip(4_000, SeekPlan.tailWords(3, listOf(Span(100, 500), Span(550, 900))), from = 3)
        assertTrue(SeekPlan.serves(tail, 3, 0)) // chính chữ bắt đầu
        assertTrue(SeekPlan.serves(tail, 4, 0))
        assertFalse("bấm chữ trước chữ đuôi: đọc đầy đủ", SeekPlan.serves(tail, 2, 0))
        assertFalse(SeekPlan.serves(tail, 0, 0))
        assertTrue("tua theo thời gian vào giữa clip đuôi", SeekPlan.serves(tail, -1, 1_500))
        assertFalse("tua thanh thời gian về đầu đoạn: bỏ clip đuôi", SeekPlan.serves(tail, -1, 0))
        assertTrue(SeekPlan.serves(clip(4_000), 0, 0)) // clip đầy đủ phục vụ mọi chỗ
        assertTrue(SeekPlan.serves(clip(4_000), -1, 0))
    }

    private fun timeline() = VirtualTimeline(intArrayOf(100, 200)).also {
        it.setDuration(0, 5_000)
        it.setDuration(1, 3_000) // clip đuôi của đoạn 1 ngắn hơn cả đoạn
    }

    @Test
    fun theSeekPlanUsesATailClipOnlyForPlacesInsideItAndOtherwiseReadsTheParagraphAgain() {
        val tail = clip(3_000, SeekPlan.tailWords(2, listOf(Span(200, 800), Span(900, 1_400), Span(1_500, 2_200))), from = 2)
        val clips = mapOf(1 to tail)
        // Chữ 3 nằm trong clip đuôi: nhảy tới mốc của chữ 3 (chữ 1 của clip đuôi).
        val inside = SeekPlan.plan(timeline(), { clips[it] }, { true }, 0, 1, 3) as SeekPlan.Plan.InClip
        assertEquals(900, inside.positionMs)
        // Chữ 1 ở trước chữ đuôi: đọc đoạn ấy lại (clip đầy đủ hay clip đuôi mới), nhớ chữ để phát từ đó.
        val before = SeekPlan.plan(timeline(), { clips[it] }, { true }, 0, 1, 1) as SeekPlan.Plan.Synthesize
        assertEquals(1, before.segment)
        assertEquals(1, before.word)
        // Tua thanh thời gian về đúng đầu đoạn: bỏ clip đuôi.
        val start = SeekPlan.plan(timeline(), { clips[it] }, { true }, 5_000, -1, -1) as SeekPlan.Plan.Synthesize
        assertEquals(1, start.segment)
        assertEquals(0, start.offsetMs)
        // Giữa clip đuôi theo thời gian: ở lại trong nó.
        val middle = SeekPlan.plan(timeline(), { clips[it] }, { true }, 5_000 + 1_200, -1, -1) as SeekPlan.Plan.InClip
        assertEquals(1_200, middle.positionMs)
    }
}
