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
        val pin = "ab".repeat(32)
        val peer = JSONObject().put("fingerprint", pin).put("addresses", JSONArray()).put("bt", "AA:BB:CC:DD:EE:FF")
        val reply = JSONObject().put("addresses", JSONArray().put("192.168.0.230:47630").put("100.73.36.27:47630"))
        PeerAddresses.learn(peer, reply.getJSONArray("addresses"), pin)
        assertEquals(listOf("192.168.0.230:47630", "100.73.36.27:47630"), PeerAddresses.ordered(peer))
        assertEquals("AA:BB:CC:DD:EE:FF", peer.getString("bt"))
    }

    @Test fun tcpHintAdmissionDropsSurplusWithoutQueueing() {
        val release = java.util.concurrent.CountDownLatch(1)
        val started = java.util.concurrent.CountDownLatch(2)
        val attempts = java.util.concurrent.atomic.AtomicInteger()
        val probe: (String) -> Boolean = {
            attempts.incrementAndGet()
            started.countDown()
            release.await(2, java.util.concurrent.TimeUnit.SECONDS)
            false
        }
        try {
            Route.pick(listOf("10.77.0.1:1", "10.77.0.2:1"), null, probe = probe)
            org.junit.Assert.assertTrue(started.await(1, java.util.concurrent.TimeUnit.SECONDS))
            repeat(20) { i -> Route.pick((1..8).map { "peer-$i-$it:1" }, null, probe = probe) }
            assertEquals(2, Route.pendingProbes())
            assertEquals(2, attempts.get())
        } finally {
            release.countDown()
            repeat(100) { if (Route.pendingProbes() > 0) Thread.sleep(5) }
        }
        assertEquals(0, Route.pendingProbes())
    }

    @Test fun manualHostnameRecoversAfterStaleFailureWithoutDnsHintJobs() {
        val target = "recovery-phone.local:47630"
        assertEquals(target, Route.pick(listOf(target), "bt").lan)
        Route.markDown(target)
        assertEquals("bt", Route.pick(listOf(target), "bt").bluetooth)
        assertEquals(target, Route.pick(listOf(target), "bt", now = System.currentTimeMillis() + Route.FRESH_MS + 1).lan)
    }

}
