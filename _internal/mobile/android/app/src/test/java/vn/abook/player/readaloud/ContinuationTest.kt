package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Clip phát luồng đứt giữa chừng (uxfix58; máy tính: listen/readAloud.ts `salvage`): phần đã về phát hết, phần tiếp là clip đuôi từ chữ đầu tiên chưa nghe, nối sau phần đã về
 * ([SeekPlan.resumeWord], [SeekPlan.tailWords] có `baseMs` + `prefix`, [Clip.baseMs]); và [LiveWords] báo chỗ đã nghe tới ([LiveClips.Target.words]).
 */
class ContinuationTest {
    private fun clip(duration: Long, words: List<Span>, from: Int = 0, base: Long = 0) = Clip(File("x.mp3"), duration, words, "edge:v", from, base)

    // ---- chữ đầu tiên chưa nghe -------------------------------------------------------------------------------------

    // Mốc tạm của máy chủ / LiveWords: chữ chưa tới bị dồn vào [chỗ nghe tới, hết âm thanh đã có] nên chỉ nhìn "kết thúc sau chỗ nghe tới" thì sót chữ.
    private val words = listOf(Span(0, 400), Span(450, 800), Span(800, 900), Span(900, 1_000), Span(1_000, 1_000))

    @Test
    fun theResumeWordIsTheFirstOneThatWasNotHeardToTheEnd() {
        assertEquals(1, SeekPlan.resumeWord(words, 700, 0)) // chữ 1 (450-800) mới nghe dở
        assertEquals(2, SeekPlan.resumeWord(words, 800, 0)) // chữ 1 vừa nghe hết
        assertEquals(0, SeekPlan.resumeWord(words, 100, 0))
    }

    @Test
    fun wordsSqueezedIntoTheEmptyEndOfTheAudioAreStillUnheard() {
        // Chữ 4 [1000, 1000] không có bề rộng: end > heard sai, nhưng start >= heard thì đúng là chưa nghe.
        assertEquals(4, SeekPlan.resumeWord(words, 1_000, 0))
    }

    @Test
    fun noWordsYetResumesFromTheFirstWordOfTheClipAndEverythingHeardRepeatsTheLastWord() {
        assertEquals(0, SeekPlan.resumeWord(emptyList(), 500, 0))
        assertEquals(3, SeekPlan.resumeWord(emptyList(), 500, 3)) // clip đuôi từ chữ 3: "từ đầu đoạn" là chữ 3
        assertEquals(4, SeekPlan.resumeWord(words, 5_000, 0)) // nghe hết cả: nhắc lại chữ cuối, không bỏ trống
    }

    @Test
    fun wordsBeforeTheFirstWordOfATailClipAreNeverChosen() {
        val tail = SeekPlan.tailWords(2, listOf(Span(0, 300), Span(300, 600)))
        assertEquals(listOf(Span(0, 0), Span(0, 0), Span(0, 300), Span(300, 600)), tail)
        assertEquals(2, SeekPlan.resumeWord(tail, 100, 2)) // chữ 0, 1 mốc [0, 0]: bỏ qua dù end (0) <= heard
        assertEquals(3, SeekPlan.resumeWord(tail, 300, 2))
    }

    // ---- ghép hai phần -----------------------------------------------------------------------------------------------

    @Test
    fun theContinuationWordsFollowTheHeardPartOnTheSameClock() {
        val heard = listOf(Span(0, 400), Span(450, 800), Span(800, 900))
        // Phần đã về dài 1000 ms, phần tiếp là clip đuôi từ chữ 2: chữ trước đó giữ mốc cũ, chữ 2 trở đi lệch `baseMs`.
        val joined = SeekPlan.tailWords(2, listOf(Span(120, 500), Span(550, 900)), 1_000, heard)
        assertEquals(listOf(Span(0, 400), Span(450, 800), Span(1_000, 1_500), Span(1_550, 1_900)), joined)
    }

    @Test
    fun theFirstContinuationWordStartsAtTheJoinSoThePreviousWordDoesNotFlash() {
        val joined = SeekPlan.tailWords(1, listOf(Span(140, 500)), 1_000, listOf(Span(0, 400)))
        assertEquals(Span(1_000, 1_500), joined[1])
    }

    @Test
    fun withoutHeardWordsThePrefixIsPaddedWithZeroes() {
        assertEquals(listOf(Span(0, 0), Span(0, 0), Span(500, 900)), SeekPlan.tailWords(2, listOf(Span(0, 400)), 500, emptyList()))
    }

    @Test
    fun aClipWithoutABaseKeepsTheOldTailWords() {
        assertEquals(listOf(Span(0, 0), Span(0, 500), Span(550, 900)), SeekPlan.tailWords(1, listOf(Span(60, 500), Span(550, 900))))
    }

    @Test
    fun aJoinedClipServesOnlyPlacesInsideItsFilePart() {
        val joined = clip(2_000, SeekPlan.tailWords(2, listOf(Span(0, 500), Span(550, 900)), 1_000, listOf(Span(0, 400), Span(450, 800))), from = 2, base = 1_000)
        assertTrue(SeekPlan.serves(joined, 2, 0))
        assertTrue(SeekPlan.serves(joined, 3, 0))
        assertFalse("chữ nằm trong phần đã về (file riêng, đã hết): đọc lại", SeekPlan.serves(joined, 1, 0))
        assertFalse(SeekPlan.serves(joined, -1, 600)) // thanh thời gian vào phần đầu
        assertTrue(SeekPlan.serves(joined, -1, 1_200))
        // Từ chữ 0 mà phần tiếp bắt đầu từ chữ 0 (không có mốc lúc đứt): chỗ trước `baseMs` cũng thuộc phần đã về.
        val whole = clip(2_000, SeekPlan.tailWords(0, listOf(Span(0, 500), Span(550, 900)), 1_000), base = 1_000)
        assertTrue(SeekPlan.serves(whole, 0, 0))
        assertFalse(SeekPlan.serves(whole, -1, 600))
    }

    @Test
    fun thePlaceInsideTheFileIsMeasuredFromTheStartOfThatFile() {
        val joined = clip(2_000, SeekPlan.tailWords(2, listOf(Span(0, 500), Span(550, 900)), 1_000, listOf(Span(0, 400), Span(450, 800))), from = 2, base = 1_000)
        assertEquals(0L, SeekPlan.offsetIn(joined, 2, 0)) // chữ 2 ở 1000 ms của đoạn = đầu file
        assertEquals(550L, SeekPlan.offsetIn(joined, 3, 0))
        assertEquals(200L, SeekPlan.offsetIn(joined, -1, 1_200))
        assertEquals(999L, SeekPlan.offsetIn(joined, -1, 9_999)) // kẹp vào file (dài 1000 ms), không vào đoạn
    }

    // ---- LiveWords báo chỗ đã nghe tới -------------------------------------------------------------------------------

    private class Recorder : LiveClips.Target {
        val heard = ArrayList<Long>()
        val durations = ArrayList<Long>()
        override fun accepting() = true
        override fun grew(file: File, total: Long) {}
        override fun words(words: List<Span>, durationMs: Long, heardMs: Long) {
            durations += durationMs
            heard += heardMs
        }
        override fun done(total: Long) {}
        override fun failed(error: Exception) {}
    }

    @Test
    fun liveWordsReportTheEndOfTheLastRealBoundaryAsTheHeardPlace() {
        val recorder = Recorder()
        val live = LiveWords("Một hai ba bốn", { it }, recorder, clock = { 0L })
        live.grew(File("x.mp3"), 12_000) // ~2 giây tiếng
        live.boundaries(listOf(Boundary(0, 400, "Một"), Boundary(450, 800, "hai")))
        assertEquals(listOf(800L), recorder.heard)
        assertTrue("âm thanh đã có dài hơn chỗ nghe tới", recorder.durations.single() >= 800)
    }
}
