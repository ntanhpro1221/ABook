package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

/** Ghép lại cùng một máy ở địa chỉ khác (IP <-> tên .local <-> Tailscale) vẫn là một thiết bị (soát a93 lỗi 2). */
class PeersRepairTest {
    private fun peers() = JSONObject()
        .put("aaaa1111", JSONObject().put("host", "192.168.1.20").put("port", 47630).put("fingerprint", "AB12CD"))
        .put("bbbb2222", JSONObject().put("host", "may-khac.local").put("port", 47630).put("fingerprint", "FF00EE"))

    @Test fun the_same_certificate_at_a_new_address_reuses_the_old_key() {
        assertEquals("aaaa1111", Peers.existingKey(peers(), "100.64.0.7", 47630, "ab12cd"))
        assertEquals("bbbb2222", Peers.existingKey(peers(), "may-khac.tailnet", 47631, "FF00EE"))
    }

    @Test fun an_unknown_certificate_at_a_known_address_still_replaces_that_address() {
        assertEquals("aaaa1111", Peers.existingKey(peers(), "192.168.1.20", 47630, "999999"))
        assertEquals("aaaa1111", Peers.existingKey(peers(), "192.168.1.20", 47630, ""))
    }

    @Test fun a_new_machine_gets_no_existing_key() {
        assertNull(Peers.existingKey(peers(), "192.168.1.99", 47630, "123456"))
        assertNull(Peers.existingKey(JSONObject(), "192.168.1.20", 47630, "AB12CD"))
    }
}
