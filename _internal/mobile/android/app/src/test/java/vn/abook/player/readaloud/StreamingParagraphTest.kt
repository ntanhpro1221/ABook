package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Đoạn đang phát LUỒNG trên điện thoại (uxfix60, soát a59p; máy tính: listen/readAloud.ts) - phần quyết định thuần tính toán mà ReadAloud dùng:
 *  - tua / bấm chữ trong đoạn đang về ([SeekPlan.plan] với `growing`): nhảy trong phần đã về, không bỏ đi đọc lại;
 *  - đứt khi mọi chữ đã có tiếng ([SeekPlan.allHeard]): coi như xong, không đọc lại chữ cuối;
 *  - mốc chữ tạm cho màn đọc ([SeekPlan.shownLiveWords]): chữ chưa có tiếng không lóe;
 *  - một chỗ hỏng một lời báo ([FailureNotice]);
 *  - độ dài còn lại của clip đã xong không âm ([LiveClips.Entry.remainingFrom]).
 */
class StreamingParagraphTest {
    /** Ba đoạn ước lượng (10 s, 20 s, 5 s); đoạn 1 đang phát luồng. */
    private fun timeline() = VirtualTimeline(intArrayOf(140, 280, 70))

    // Đoạn 1 đang về: đã có 3 000 ms tiếng, mốc thật tới 2 000 ms (chữ 0-2), chữ 3-5 chưa có tiếng (dồn ở cuối phần đã về).
    private val tentative = listOf(Span(0, 600), Span(650, 1_300), Span(1_350, 2_000), Span(2_000, 3_000), Span(3_000, 3_000), Span(3_000, 3_000))
    private fun growingClip(words: List<Span> = tentative, from: Int = 0, base: Long = 0, received: Long = 3_000) = Clip(File("live.mp3"), base + received, words, "edge:v", from, base)
    private val growing = SeekPlan.Growing(heardMs = 2_000, receivedMs = 3_000)

    private fun plan(ms: Long, segment: Int = -1, word: Int = -1, clip: Clip = growingClip(), live: SeekPlan.Growing = growing) =
        SeekPlan.plan(timeline(), { if (it == 1) clip else null }, { it == 1 }, ms, segment, word, growing = { if (it == 1) live else null })

    // ---- L2: tua trong đoạn đang về --------------------------------------------------------------------------------

    @Test
    fun draggingInsideWhatHasArrivedSeeksWithinTheStreamingItem() {
        // Đoạn 1 bắt đầu ở 10 000 ms của chương; kéo tới 11 500 = 1 500 ms trong đoạn (đã có tiếng). Trước uxfix60: đọc lại cả đoạn.
        val inClip = plan(11_500) as SeekPlan.Plan.InClip
        assertEquals(1, inClip.segment)
        assertEquals(1_500, inClip.positionMs)
    }

    @Test
    fun draggingPastWhatHasArrivedStopsAtTheEndOfIt() {
        val inClip = plan(25_000) as SeekPlan.Plan.InClip // 15 s trong đoạn, mới về 3 s
        assertEquals(2_999, inClip.positionMs)
    }

    @Test
    fun clickingAWordThatHasBeenSpokenJumpsToItInTheStreamingItem() {
        val inClip = plan(0, segment = 1, word = 2) as SeekPlan.Plan.InClip
        assertEquals(1_350, inClip.positionMs)
    }

    @Test
    fun clickingAWordWithoutAudioYetAsksForATailClipFromIt() {
        val synth = plan(0, segment = 1, word = 4) as SeekPlan.Plan.Synthesize
        assertEquals(1, synth.segment)
        assertEquals(4, synth.word)
        // Chữ 3 bắt đầu đúng ở chỗ mốc thật dừng (2 000): mốc của nó chỉ là chỗ dồn - cũng clip đuôi.
        assertTrue(plan(0, segment = 1, word = 3) is SeekPlan.Plan.Synthesize)
    }

    @Test
    fun theFirstWordOfAStreamingTailClipIsPlayableBeforeAnyBoundaryArrives() {
        // Clip đuôi từ chữ 2 vừa có byte đầu, chưa có mốc nào: bấm lại chữ 2 là đầu mục đang về, không xin clip đuôi mới.
        val tail = growingClip(SeekPlan.tailWords(2, emptyList()) + listOf(Span(0, 0)), from = 2, received = 400)
        val inClip = plan(0, segment = 1, word = 2, clip = tail, live = SeekPlan.Growing(0, 400)) as SeekPlan.Plan.InClip
        assertEquals(0, inClip.positionMs)
    }

    @Test
    fun withoutAGrowingParagraphPlanningIsUnchanged() {
        val clip = growingClip()
        val inClip = SeekPlan.plan(timeline(), { if (it == 1) clip else null }, { it == 1 }, 0, 1, 4) as SeekPlan.Plan.InClip
        assertEquals(2_999, inClip.positionMs) // clip đã xong: mốc của chữ 4 là mốc thật, nhảy thẳng (kẹp trong file)
    }

    // ---- L8c: đứt khi mọi chữ đã có tiếng ------------------------------------------------------------------------

    @Test
    fun aClipThatBreaksAfterEveryWordWasSpokenCountsAsDone() {
        val spoken = listOf(Span(0, 600), Span(650, 1_300), Span(1_350, 2_000))
        assertTrue(SeekPlan.allHeard(spoken, 2_000, 0))
        assertTrue(SeekPlan.allHeard(spoken, 2_400, 0))
        assertFalse("chữ cuối mới nghe dở", SeekPlan.allHeard(spoken, 1_800, 0))
        assertFalse("chữ chưa có tiếng (dồn ở cuối)", SeekPlan.allHeard(tentative, 2_000, 0))
        assertFalse(SeekPlan.allHeard(emptyList(), 5_000, 0))
        assertFalse("clip đuôi chưa có chữ nào của nó", SeekPlan.allHeard(SeekPlan.tailWords(3, emptyList()), 5_000, 3))
    }

    // ---- L9: chữ chưa có tiếng không lóe --------------------------------------------------------------------------

    /** Bộ tô của màn đọc: chữ cuối có đầu <= vị trí. */
    private fun lit(words: List<Span>, positionMs: Long): Int = words.indexOfLast { it.start <= positionMs }

    @Test
    fun wordsWithoutAudioStayOutOfReachSoTheHighlightWaitsOnTheLastSpokenWord() {
        // Tiếng đã chạy qua mốc thật cuối cùng (2 000) tới 2 500: trước uxfix60 chữ sáng nhảy sang chữ 5 (cuối đoạn) rồi quay về.
        assertEquals(3, lit(tentative, 2_500))
        val shown = SeekPlan.shownLiveWords(tentative, 0, 2_000, 20_000)
        assertEquals(2, lit(shown, 2_500))
        assertEquals(2, lit(shown, 20_000)) // đồng hồ đoạn kẹp ở độ dài ước (20 000): không bao giờ chạm chữ chưa có tiếng
        assertEquals(shown.subList(0, 3), tentative.subList(0, 3))
        assertEquals(List(3) { Span(20_001, 20_001) }, shown.subList(3, 6))
        // Chỗ nối khi đứt vẫn tìm đúng chữ chưa nghe.
        assertEquals(3, SeekPlan.resumeWord(shown, 2_000, 0))
    }

    @Test
    fun theFirstWordOfATailClipKeepsItsMarkSoThePreviousWordDoesNotFlash() {
        val words = SeekPlan.tailWords(2, listOf(Span(140, 500), Span(500, 500)))
        val shown = SeekPlan.shownLiveWords(words, 2, 0, 9_000)
        assertEquals(Span(0, 500), shown[2])
        assertEquals(Span(9_001, 9_001), shown[3])
        assertEquals(listOf(Span(0, 0), Span(0, 0)), shown.subList(0, 2))
    }

    @Test
    fun parkedWordsStayAfterSpokenWordsEvenWhenAudioRunsPastTheEstimate() {
        val words = listOf(Span(0, 4_000), Span(4_100, 6_000), Span(6_000, 6_500))
        val shown = SeekPlan.shownLiveWords(words, 0, 6_000, 5_000) // tiếng dài hơn ước lượng 5 s
        assertEquals(Span(6_000, 6_000), shown[2])
        assertTrue(shown.zipWithNext().all { (a, b) -> a.start <= b.start })
    }

    // ---- L10: một chỗ hỏng một lời báo -------------------------------------------------------------------------

    @Test
    fun anAutomaticRetryOfTheSameSpotThatFailsAgainOnlyUpdatesTheNotice() {
        val notices = FailureNotice()
        assertTrue(notices.shouldNotify(3, 7))
        notices.retryingByItself() // dịch vụ trả lời lại -> máy tự hỏi lại đoạn 7
        assertFalse(notices.shouldNotify(3, 7))
        notices.retryingByItself()
        assertFalse("hỏi lại tự động lần nữa vẫn là chỗ cũ", notices.shouldNotify(3, 7))
    }

    @Test
    fun aListenerActionOrAnotherSpotMeansANewNotice() {
        val notices = FailureNotice()
        notices.shouldNotify(3, 7)
        notices.retryingByItself()
        notices.forget() // người nghe bấm "Thử lại" / tua
        assertTrue(notices.shouldNotify(3, 7))
        notices.retryingByItself()
        assertTrue("chỗ khác hỏng: báo", notices.shouldNotify(3, 8))
        assertTrue("không phải máy tự hỏi lại: báo", notices.shouldNotify(3, 8))
    }

    @Test
    fun anAutomaticRetryWithoutAnEarlierNoticeStillNotifies() {
        val notices = FailureNotice()
        notices.retryingByItself()
        assertTrue(notices.shouldNotify(1, 1))
    }

    // ---- L8f: tua quá cuối clip đã xong ---------------------------------------------------------------------------

    @Test
    fun theRemainingLengthOfAFinishedClipIsNeverNegative() {
        val entry = LiveClips.create()
        entry.grew(File("x.mp3"), 600)
        assertNull("còn đang lớn: chưa biết", entry.remainingFrom(100))
        entry.finish(1_000)
        assertEquals(900L, entry.remainingFrom(100))
        assertEquals(0L, entry.remainingFrom(1_000))
        assertEquals(0L, entry.remainingFrom(5_000))
    }
}
