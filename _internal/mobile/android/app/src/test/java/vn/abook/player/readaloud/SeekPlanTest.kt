package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** Chạm vào một chữ trong màn đọc là nghe từ ĐÚNG chữ ấy: tua trong đoạn đã có, đoạn chưa đọc, và cách chỉ `{segment, word}`. */
class SeekPlanTest {
    private fun clip(duration: Long, words: List<Span> = emptyList()) = Clip(File("x.mp3"), duration, words, "edge:v")

    /** Ba đoạn; đoạn 0 và 1 đã đọc (9 s và 12 s, đoạn 1 có mốc chữ), đoạn 2 chưa. */
    private fun timeline() = VirtualTimeline(intArrayOf(140, 280, 70)).also {
        it.setDuration(0, 9_000)
        it.setDuration(1, 12_000)
    }

    private val clips = mapOf(
        0 to clip(9_000),
        1 to clip(12_000, listOf(Span(0, 500), Span(500, 1_200), Span(4_000, 4_600))),
    )

    @Test
    fun exactSecondsInsideAKnownQueuedClipSeekWithinTheClipNotToItsStart() {
        // 9 000 + 4 250 ms từ đầu chương = 4 250 ms trong đoạn 1.
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { true }, 13_250, -1, -1) as SeekPlan.Plan.InClip
        assertEquals(1, plan.segment)
        assertEquals(4_250, plan.positionMs)
    }

    @Test
    fun aKnownClipThatLeftTheQueueIsReadAgainFromTheSamePlace() {
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { false }, 13_250, -1, -1) as SeekPlan.Plan.Synthesize
        assertEquals(1, plan.segment)
        assertEquals(4_250, plan.offsetMs)
    }

    @Test
    fun aParagraphNotReadYetWaitsForItsClipThenStartsAtTheTouchedOffset() {
        // Đoạn 2 bắt đầu ở 21 000 ms; chạm 2 300 ms sau đó.
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { true }, 23_300, -1, -1) as SeekPlan.Plan.Synthesize
        assertEquals(2, plan.segment)
        assertEquals(2_300, plan.offsetMs)
        assertEquals(-1, plan.word)
    }

    @Test
    fun segmentAndWordWinOverSeconds() {
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { true }, 0, 1, 2) as SeekPlan.Plan.InClip
        assertEquals(1, plan.segment)
        assertEquals("đầu chữ thứ 2 của đoạn 1", 4_000, plan.positionMs)
    }

    @Test
    fun segmentAndWordOnAnUnreadParagraphResolveOnceItsWordsAreKnown() {
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { true }, 0, 2, 3) as SeekPlan.Plan.Synthesize
        assertEquals(2, plan.segment)
        assertEquals(3, plan.word)
        // Khi đoạn 2 đọc xong, mốc chữ 3 của nó quyết chỗ bắt đầu.
        val arrived = clip(5_000, listOf(Span(0, 300), Span(300, 800), Span(800, 1_500), Span(1_500, 2_100)))
        assertEquals(1_500, SeekPlan.offsetIn(arrived, plan.word, plan.offsetMs))
    }

    @Test
    fun aWordTheClipHasNoTimingForStartsAtTheParagraphStart() {
        val arrived = clip(5_000, emptyList())
        assertEquals(0, SeekPlan.offsetIn(arrived, 4, 777))
    }

    @Test
    fun theOffsetNeverRunsPastTheClip() {
        val arrived = clip(3_000)
        assertEquals(2_999, SeekPlan.offsetIn(arrived, -1, 50_000))
        assertEquals(0, SeekPlan.offsetIn(arrived, -1, -5))
    }

    @Test
    fun aSegmentNumberOutOfRangeIsClamped() {
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { true }, 0, 99, -1) as SeekPlan.Plan.Synthesize
        assertEquals(2, plan.segment)
        assertTrue(plan.offsetMs == 0L)
    }

    @Test
    fun secondsBeyondTheChapterLandInTheLastParagraph() {
        val plan = SeekPlan.plan(timeline(), { clips[it] }, { true }, 10_000_000, -1, -1)
        assertEquals(2, (plan as SeekPlan.Plan.Synthesize).segment)
    }
}
