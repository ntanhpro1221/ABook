package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Bài nhạc nền hỏng trên điện thoại (MusicFailures, phần sổ sách của MusicBed) - cùng luật với RETRY_MS của ui/src/listen/musicBed.ts
 * (musicBed.test.ts): nhạc của sách hỏng thì đoạn ấy im lặng, RETRY_MS sau thử lại; phát được thì xoá; hỏng cả phiên thì không thử lại.
 */
class MusicFailuresTest {
    private var clock = 1_000_000L
    private val failures = MusicFailures { clock }
    private val calm = "music/" + "a".repeat(40) + ".mp3"
    private val sibling = "music/" + "b".repeat(40) + ".mp3"
    private val cues = listOf(
        MusicCues.Cue(0.0, 300.0, calm, -8.0),
        MusicCues.Cue(300.0, 500.0, sibling, -2.0, sibling = true),
    )

    @Test
    fun a_failed_book_track_is_silent_until_retry_ms_then_comes_back() {
        assertEquals(calm, MusicCues.at(cues, 10.0, failures)?.track)
        failures.drop(calm, retry = true)
        assertNull(MusicCues.at(cues, 10.0, failures))
        clock += MusicFailures.RETRY_MS - 1
        assertNull(MusicCues.at(cues, 120.0, failures))
        clock += 1
        assertEquals(calm, MusicCues.at(cues, 120.0, failures)?.track)
    }

    @Test
    fun only_the_failed_track_is_silent_and_the_sibling_cue_keeps_its_handover_flag() {
        failures.drop(calm, retry = true)
        assertNull(MusicCues.at(cues, 10.0, failures))
        val next = MusicCues.at(cues, 310.0, failures)
        assertEquals(sibling, next?.track)
        assertTrue(next!!.sibling)
    }

    @Test
    fun success_clears_so_the_next_failure_waits_a_full_retry_ms() {
        failures.drop(calm, retry = true)
        clock += MusicFailures.RETRY_MS
        assertFalse(failures.isFailed(calm))
        failures.forget(calm)
        clock += 60_000
        failures.drop(calm, retry = true)
        clock += MusicFailures.RETRY_MS - 1
        assertTrue(failures.isFailed(calm))
        clock += 1
        assertFalse(failures.isFailed(calm))
    }

    @Test
    fun a_track_dropped_for_the_session_never_comes_back_and_due_ones_are_taken_once() {
        failures.drop(calm, retry = false)
        failures.drop(sibling, retry = true)
        assertEquals(emptySet<String>(), failures.takeDue())
        clock += MusicFailures.RETRY_MS * 100
        assertEquals(setOf(sibling), failures.takeDue())
        assertEquals(emptySet<String>(), failures.takeDue())
        assertTrue(failures.isFailed(calm))
        assertNull(MusicCues.at(cues, 10.0, failures))
        failures.clear()
        assertFalse(failures.isFailed(calm))
    }
}
