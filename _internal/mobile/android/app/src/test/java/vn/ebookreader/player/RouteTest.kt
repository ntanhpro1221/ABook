package vn.ebookreader.player

import org.junit.Assert.assertEquals
import org.junit.Test

/** Tự chọn đường (Route.choose): Wi-Fi khi địa chỉ LAN thông, Bluetooth khi không - không bao giờ chờ ai. */
class RouteTest {
    private val lan = listOf("192.168.1.5:47630", "10.0.0.7:47630")

    @Test
    fun aReachableLanAddressWins() {
        val known = mapOf("192.168.1.5:47630" to false, "10.0.0.7:47630" to true)
        assertEquals(Route.Choice("10.0.0.7:47630", null), Route.choose(lan, "AA:BB:CC:DD:EE:FF") { known[it] })
    }

    @Test
    fun bluetoothWhenEveryLanAddressIsDown() {
        val known = mapOf("192.168.1.5:47630" to false, "10.0.0.7:47630" to false)
        assertEquals(Route.Choice(null, "AA:BB:CC:DD:EE:FF"), Route.choose(lan, "AA:BB:CC:DD:EE:FF") { known[it] })
    }

    @Test
    fun anUntriedLanAddressIsTriedFirstButNeverWithoutBluetoothFallingBack() {
        assertEquals(Route.Choice("192.168.1.5:47630", null), Route.choose(lan, "AA:BB:CC:DD:EE:FF") { null })
        val known = mapOf("192.168.1.5:47630" to false)
        assertEquals(Route.Choice("10.0.0.7:47630", null), Route.choose(lan, null) { known[it] })
    }

    @Test
    fun pairedOverBluetoothOnlyStaysOnBluetoothAndWithoutRoutesKeepsTheOldAddress() {
        assertEquals(Route.Choice(null, "AA:BB:CC:DD:EE:FF"), Route.choose(emptyList(), "AA:BB:CC:DD:EE:FF") { null })
        val known = mapOf("192.168.1.5:47630" to false, "10.0.0.7:47630" to false)
        assertEquals(Route.Choice("192.168.1.5:47630", null), Route.choose(lan, null) { known[it] })
    }
}
