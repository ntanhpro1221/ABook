package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Khoá CPU / Wi-Fi giữ trong lúc đi lấy clip người nghe đang chờ ([FetchWake], soát a47 mục 6): giữ khi có lượt chờ, nhả khi lượt cuối xong / người nghe tạm dừng, vé của đợt cũ
 * không nhả hộ lượt mới. Khoá thật chỉ thử được trên máy; ở đây là khoá giả.
 */
class FetchWakeTest {
    private class FakeLocks : FetchWake.Locks {
        var held = false
        var wifi = false
        var acquires = 0
        override fun acquire(timeoutMs: Long, network: Boolean) { held = true; wifi = wifi || network; acquires += 1 }
        override fun release() { held = false; wifi = false }
    }

    private val locks = FakeLocks()
    @Before
    fun setUp() {
        FetchWake.releaseAll()
        FetchWake.factory = { locks }
    }

    @After
    fun tearDown() {
        FetchWake.releaseAll()
    }

    @Test
    fun heldWhileAnyWaitedFetchRunsAndReleasedWhenTheLastOneEnds() {
        val first = FetchWake.hold()
        assertTrue(locks.held)
        val second = FetchWake.hold()
        FetchWake.release(first)
        assertTrue("còn một lượt chờ: vẫn giữ", locks.held)
        FetchWake.release(second)
        assertFalse(locks.held)
        assertEquals(0, FetchWake.heldCount())
    }

    @Test
    fun pausingReleasesAtOnceAndALateReleaseOfAnOldFetchDoesNotDropANewOnesLock() {
        val old = FetchWake.hold()
        FetchWake.releaseAll() // người nghe tạm dừng
        assertFalse(locks.held)
        val fresh = FetchWake.hold() // bấm phát, lượt mới
        assertTrue(locks.held)
        FetchWake.release(old) // lượt cũ về muộn
        assertTrue("vé đợt cũ không nhả hộ lượt mới", locks.held)
        FetchWake.release(fresh)
        assertFalse(locks.held)
    }

    @Test
    fun anOnDeviceVoiceHoldsOnlyTheCpu() {
        // gap2: giọng trên máy đọc đoạn người nghe đang chờ (hàng đợi cạn, màn tắt) - CPU phải thức, Wi-Fi thì không cần.
        val local = FetchWake.hold(network = false)
        assertTrue(locks.held)
        assertFalse(locks.wifi)
        val online = FetchWake.hold()
        assertTrue(locks.wifi)
        FetchWake.release(local)
        FetchWake.release(online)
        assertFalse(locks.held)
        assertFalse(locks.wifi)
    }

    @Test
    fun releaseWithoutHoldIsHarmless() {
        FetchWake.release(0)
        FetchWake.release(0)
        assertEquals(0, FetchWake.heldCount())
        assertFalse(locks.held)
    }
}
