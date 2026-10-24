package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class PeerAddressesTest {
    private val pin = "ab".repeat(32)

    @Test fun malformedReadContractUsesSharedFixture() {
        val rows = JSONArray(java.io.File("../../../tests/fixtures/peer_addresses_malformed.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val peer = row.getJSONObject("entry")
            PeerAddresses.migrate(peer)
            val expected = row.getJSONArray("expected").let { array -> (0 until array.length()).map { array.getString(it) } }
            assertEquals(row.getString("name"), expected, PeerAddresses.ordered(peer))
            assertFalse(PeerAddresses.migrate(peer))
            assertTrue(peer.getJSONArray("addresses").length() <= 8)
        }
    }

    @Test fun mappedIpv6UsesEmbeddedIpv4ScopeFromSharedFixture() {
        val rows = JSONArray(java.io.File("../../../tests/fixtures/peer_addresses.json").readText())
        val peer = JSONObject().put("fingerprint", pin).put("addresses", JSONArray())
        val values = JSONArray()
        val accepted = mutableSetOf<String>()
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val address = row.getString("address")
            assertEquals(address, row.getBoolean("valid"), PeerAddresses.valid(address, true) != null)
            values.put(address)
            if (row.getBoolean("valid")) accepted += row.optString("canonical", address)
        }
        PeerAddresses.learn(peer, values, pin)
        assertEquals(accepted, PeerAddresses.ordered(peer).toSet())
    }

    @Test fun fullSuccessfulHistoryMakesRoomForAdvertisedHostAndPort() {
        val old = (1..8).map { "10.0.0.$it:47630" }
        val peer = JSONObject().put("fingerprint", pin).put("addresses", JSONArray(old.mapIndexed { index, address ->
            JSONObject().put("address", address).put("lastSuccess", index + 1)
        }))
        val fresh = listOf("192.168.7.8:47631", "100.73.1.2:47632")
        PeerAddresses.learn(peer, JSONArray(fresh), pin, old.last(), at = 20.0)
        assertEquals(8, peer.getJSONArray("addresses").length())
        assertEquals(old.last(), PeerAddresses.ordered(peer).first())
        assertTrue(PeerAddresses.ordered(peer).containsAll(fresh))
        val entries = peer.getJSONArray("addresses")
        for (i in 0 until entries.length()) if (entries.getJSONObject(i).getString("address") in fresh)
            assertEquals(0.0, entries.getJSONObject(i).getDouble("lastSuccess"), 0.0)
    }

    @Test fun legacyHostBecomesFirstRouteExactlyOnce() {
        val peer = JSONObject().put("host", "100.73.1.2").put("port", 47630).put("fingerprint", pin)
        assertTrue(PeerAddresses.migrate(peer))
        assertEquals(listOf("100.73.1.2:47630"), PeerAddresses.ordered(peer))
        assertEquals(0.0, peer.getJSONArray("addresses").getJSONObject(0).getDouble("lastSuccess"), 0.0)
        assertFalse(PeerAddresses.migrate(peer))
        peer.put("addresses", JSONArray())
        assertFalse(PeerAddresses.migrate(peer))
        assertTrue(PeerAddresses.ordered(peer).isEmpty())
    }

    @Test fun wrongFingerprintCannotTeachAnAddressOrSuccess() {
        val peer = JSONObject().put("fingerprint", pin).put("addresses", JSONArray())
        assertFalse(PeerAddresses.learn(peer, JSONArray().put("192.168.1.8:47630"), "cd".repeat(32), "192.168.1.8:47630"))
        assertFalse(PeerAddresses.learn(peer, JSONArray().put("192.168.1.8:47630"), pin, claimed = "cd".repeat(32)))
        assertTrue(PeerAddresses.ordered(peer).isEmpty())
    }

    @Test fun boundedDeduplicatedListKeepsLastWorkingRouteFirst() {
        val peer = JSONObject().put("fingerprint", pin).put("addresses", JSONArray())
        val values = JSONArray((1..20).map { "10.0.0.$it:47630" })
        PeerAddresses.learn(peer, values, pin, "100.64.1.2:47630", at = 20.0)
        assertEquals(8, peer.getJSONArray("addresses").length())
        assertEquals("100.64.1.2:47630", PeerAddresses.ordered(peer).first())
        PeerAddresses.learn(peer, JSONArray().put("[fd00::7]:47630").put("[fd00::7]:47630"), pin, "[fd00::7]:47630", at = 30.0)
        assertEquals(8, peer.getJSONArray("addresses").length())
        assertEquals("[fd00::7]:47630", PeerAddresses.ordered(peer).first())
        assertEquals("fd00::7" to 47630, PeerAddresses.split("[fd00::7]:47630"))
    }

    @Test fun advertisementsRejectLoopbackLinkLocalAndNames() {
        for (address in listOf("127.0.0.1:47630", "169.254.1.2:47630", "[::1]:47630", "[fe80::1]:47630", "0.0.0.0:47630", "name.local:47630")) {
            assertNull(address, PeerAddresses.valid(address, advertised = true))
        }
        assertEquals("[fd00::7]:47630", PeerAddresses.valid("[fd00::7]:47630", advertised = true))
    }

    @Test fun discoveryPortBoundsAreCheckedBeforeProbe() {
        for (port in listOf("0", "65536", "9".repeat(100), "-1", "4295014926")) {
            assertNull(PeerAddresses.valid("192.168.1.8:$port", true))
            assertNull(PeerAddresses.discoveryEndpoint("192.168.1.8", port))
        }
        assertNull(PeerAddresses.discoveryEndpoint("192.168.1.8", 47630.5))
        assertNull(PeerAddresses.discoveryEndpoint("192.168.1.8", null))
        assertEquals("192.168.1.8:47630", PeerAddresses.discoveryEndpoint("192.168.1.8", 47630))
        assertEquals("192.168.1.8:65535", PeerAddresses.valid("192.168.1.8:65535", true))
    }

    @Test fun deadFirstAddressFallsThroughToTheOtherBeforeHttp() {
        val attempted = java.util.Collections.synchronizedList(mutableListOf<String>())
        val targets = listOf("100.64.19.7:47630", "192.168.19.7:47630")
        targets.forEach(Route::markDown)
        val chosen = Route.resolve(targets) { attempted += it; it == targets[1] }
        assertEquals(targets[1], chosen)
        assertEquals(targets, attempted)
    }

    @Test fun mediaRequestsPinTheSelectedPeerWhenRouteHistoriesOverlap() {
        Pin.forPeer(pin) {
            assertEquals(pin, Pin.expected("192.168.1.8", 47630))
            Pin.forPeer("cd".repeat(32)) { assertEquals("cd".repeat(32), Pin.expected("192.168.1.8", 47630)) }
            assertEquals(pin, Pin.expected("192.168.1.8", 47630))
        }
    }

    @Test fun addressListsWithNamesAreRedactedFromFileAndLogcat() {
        val message = """routes addresses=[{"address":"private-phone.local:47630","lastSuccess":42},{"address":"[fd00::7]:47630"}] failed"""
        val scrubbed = AppLog.scrub(message)
        assertFalse(scrubbed, scrubbed.contains("private-phone"))
        assertFalse(scrubbed, scrubbed.contains("fd00"))
        assertTrue(scrubbed, scrubbed.contains("failed"))
        assertFalse(AppLog.logcatText("failure", IllegalStateException(message)).contains("private-phone"))
        assertEquals("addresses=*** failed", AppLog.scrub("addresses=[private-phone.local:47630, [fd00::7]:47630] failed"))
    }

    @Test fun semanticAliasesShareSlotsAndPreserveMaximumSuccessFromSharedFixture() {
        val rows = JSONArray(java.io.File("../../../tests/fixtures/peer_address_aliases.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            val aliases = row.getJSONArray("aliases")
            for (j in 0 until aliases.length()) assertEquals(row.getString("canonical"),
                PeerAddresses.valid(aliases.getString(j), row.getBoolean("advertised")))
        }
        val aliases = rows.getJSONObject(0).getJSONArray("aliases")
        val active = rows.getJSONObject(0).getString("canonical")
        val live = rows.getJSONObject(1).getString("canonical")
        val values = (0 until aliases.length()).map { aliases.getString(it) } + live
        val peer = JSONObject().put("fingerprint", pin).put("addresses", JSONArray()
            .put(JSONObject().put("address", aliases.getString(1)).put("lastSuccess", 9))
            .put(JSONObject().put("address", aliases.getString(2)).put("lastSuccess", 2)))
        PeerAddresses.learn(peer, JSONArray(values), pin)
        assertEquals(listOf(active, live), PeerAddresses.ordered(peer))
        assertEquals(9.0, peer.getJSONArray("addresses").getJSONObject(0).getDouble("lastSuccess"), 0.0)
        assertEquals(listOf(active, live), PeerAddresses.candidates(values))
        PeerAddresses.learn(peer, JSONArray((1..12).map { "10.0.0.$it:47630" }), pin)
        assertEquals(active, PeerAddresses.ordered(peer).first())
        assertEquals(8, peer.getJSONArray("addresses").length())
    }

    @Test fun discoveryUsesOriginalJsonIntegerContractFromSharedFixture() {
        val rows = JSONArray(java.io.File("../../../tests/fixtures/peer_discovery_ports.json").readText())
        for (i in 0 until rows.length()) {
            val row = rows.getJSONObject(i)
            assertEquals(row.toString(), row.getBoolean("valid"), PeerAddresses.discoveryEndpoint("192.168.1.8", row.opt("port")) != null)
        }
        for (host in listOf("127.0.0.1", "169.254.1.1", "::1", "fe80::1", "0.0.0.0"))
            assertNull(PeerAddresses.discoveryEndpoint(host, 47630))
    }

}
