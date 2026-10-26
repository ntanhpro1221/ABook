package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Test

/** Giọng của máy không bao giờ hiện mã Android ("vi-vn-x-gft-local") cho người nghe. */
class DeviceVoiceLabelTest {
    @Test
    fun oneVoiceIsJustTheLanguage() = assertEquals("Tiếng Việt", DeviceTts.label(0, 1))

    @Test
    fun severalVoicesAreNumberedInTheOrderTheDeviceGives() {
        assertEquals(listOf("Tiếng Việt 1", "Tiếng Việt 2", "Tiếng Việt 3"), (0 until 3).map { DeviceTts.label(it, 3) })
    }
}
