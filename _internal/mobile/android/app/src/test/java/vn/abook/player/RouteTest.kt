package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
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

    /** Danh sách thư viện báo lại các đường (SyncLink.refreshRoutes): địa chỉ Tailscale có sau lúc ghép được học. */
    @Test
    fun theLibraryListingTeachesAddressesAddedAfterPairing() {
        val reply = JSONObject().put("routes", JSONObject()
            .put("lan", JSONArray().put("192.168.0.230").put("100.73.36.27")).put("port", 47630).put("bluetooth", ""))
        val (lan, port, bluetooth) = SyncLink.refreshed(reply, "AA:BB:CC:DD:EE:FF")!!
        assertEquals(listOf("192.168.0.230", "100.73.36.27"), JSONArray(lan).let { array -> List(array.length()) { array.getString(it) } })
        assertEquals(47630, port)
        assertEquals("AA:BB:CC:DD:EE:FF", bluetooth) // máy tính đang tắt Bluetooth: giữ địa chỉ đã biết
        assertEquals(null, SyncLink.refreshed(JSONObject().put("books", JSONArray()), "")) // máy tính bản cũ: không đổi gì
    }
}
