package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/** Nạp sẵn engine giọng trên máy lúc mở trang sách (livejoin3; máy tính: tests/test_readaloud_preload.py). */
class EnginePreloadTest {
    private val gib = 1L shl 30

    @Test
    fun aPhoneShortOfBatteryOrMemoryDoesNotPreload() {
        assertFalse("pin 15 % không sạc", EnginePreload.spare(charging = false, percent = 15, availableBytes = 4 * gib))
        assertTrue("pin yếu mà đang sạc", EnginePreload.spare(charging = true, percent = 15, availableBytes = 4 * gib))
        assertTrue("đúng 20 %", EnginePreload.spare(charging = false, percent = 20, availableBytes = 4 * gib))
        assertFalse("RAM trống dưới 1 GiB", EnginePreload.spare(charging = true, percent = 100, availableBytes = gib / 2))
        assertTrue(EnginePreload.spare(charging = false, percent = 80, availableBytes = gib))
    }

    @Test
    fun onlyVoicesWithAnEngineAreLoaded() {
        assertTrue(EnginePreload.hasEngine("supertonic:F1"))
        assertTrue(EnginePreload.hasEngine("vieneu:nano/Đức Trí"))
        assertFalse(EnginePreload.hasEngine("edge:vi-VN-HoaiMyNeural"))
        assertFalse(EnginePreload.hasEngine("device:vi"))
        assertFalse(EnginePreload.start(null, "edge:vi-VN-HoaiMyNeural", spare = true) { error("không được nạp") })
    }

    @Test
    fun loadsOnceInTheBackgroundAndOnlyWhenThereIsSpare() {
        val started = CountDownLatch(1)
        val release = CountDownLatch(1)
        val done = CountDownLatch(1)
        var loads = 0
        assertFalse("không dư: không nạp", EnginePreload.start(null, "supertonic:F1", spare = false) { loads++ })
        assertTrue(EnginePreload.start(null, "supertonic:F1", spare = true) { loads++; started.countDown(); release.await(5, TimeUnit.SECONDS); done.countDown() })
        assertTrue(started.await(5, TimeUnit.SECONDS))
        assertFalse("đang nạp: bỏ trùng", EnginePreload.start(null, "supertonic:F1", spare = true) { loads++ })
        release.countDown()
        assertTrue(done.await(5, TimeUnit.SECONDS))
        assertEquals(1, loads)
    }

    @Test
    fun aFailedLoadIsOnlyALostHeadStart() {
        val tried = CountDownLatch(1)
        assertTrue(EnginePreload.start(null, "vieneu:nano/Đức Trí", spare = true) { tried.countDown(); error("chưa tải") })
        assertTrue(tried.await(5, TimeUnit.SECONDS))
        Thread.sleep(50)
        val again = CountDownLatch(1)
        assertTrue("lần sau thử lại được", EnginePreload.start(null, "vieneu:nano/Đức Trí", spare = true) { again.countDown() })
        assertTrue(again.await(5, TimeUnit.SECONDS))
    }
}
