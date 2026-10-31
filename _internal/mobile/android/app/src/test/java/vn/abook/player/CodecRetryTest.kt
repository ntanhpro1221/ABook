package vn.abook.player

import org.junit.Assert.assertEquals
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Dựng Nối thử lại MỘT lần khi codec vừa tạo bị hệ thống thu hồi (PLAN_loop §45.4): [LoopSeam.startOnce] với codec giả.
 * `start` ném IllegalStateException như `configure()` của MediaCodec ở trạng thái Released.
 */
class CodecRetryTest {
    private class Fake(val id: Int) {
        var released = false
    }

    private fun run(failures: Int): Triple<Result<Fake>, List<Fake>, Int> {
        val made = mutableListOf<Fake>()
        var starts = 0
        val result = runCatching {
            LoopSeam.startOnce(
                make = { Fake(made.size).also { made += it } },
                start = { if (starts++ < failures) throw IllegalStateException("configure() in Released state") },
                release = { it.released = true },
                pauseMs = 0,
            )
        }
        return Triple(result, made, starts)
    }

    @Test
    fun aCodecThatStartsIsUsedWithoutASecondOne() {
        val (result, made, starts) = run(failures = 0)
        assertSame(made[0], result.getOrThrow())
        assertEquals(1, made.size)
        assertEquals(1, starts)
        assertTrue(made.none { it.released })
    }

    @Test
    fun aReclaimedCodecIsReleasedAndTheSecondOneIsUsed() {
        val (result, made, starts) = run(failures = 1)
        assertSame(made[1], result.getOrThrow())
        assertEquals(2, made.size)
        assertEquals(2, starts)
        assertTrue(made[0].released)
        assertTrue(!made[1].released)
    }

    @Test
    fun twoFailuresGiveUpAfterReleasingBoth() {
        val (result, made, starts) = run(failures = 2)
        assertTrue(result.exceptionOrNull() is IllegalStateException)
        assertEquals(2, made.size)
        assertEquals(2, starts)
        assertTrue(made.all { it.released })
    }

    @Test
    fun otherErrorsAreNotRetried() {
        val made = mutableListOf<Fake>()
        try {
            LoopSeam.startOnce(
                make = { Fake(made.size).also { made += it } },
                start = { throw IllegalArgumentException("định dạng sai") },
                release = { it.released = true },
                pauseMs = 0,
            )
            fail("phải ném lỗi")
        } catch (e: IllegalArgumentException) {
            assertEquals(1, made.size)
            assertTrue(made[0].released)
        }
    }
}
