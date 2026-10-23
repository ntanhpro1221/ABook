package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.file.Files

/** Soát bảo mật a109: màu bìa mang url(...) và cổng audio Cast không trần. */
class A109SecurityTest {
    private val tracker = "url(https://tracker.invalid/a109-reader-unique)"

    @Test fun a_cover_colour_is_only_a_plain_hex_colour() {
        for (bad in listOf(tracker, "red", "#abc", "#GGGGGG", "#aabbccdd", "#aabbcc;background:url(x)", "", null, 7, JSONObject()))
            assertEquals("accepted: $bad", "", BookEdits.cleanColor(bad))
        assertEquals("#a1b2c3", BookEdits.cleanColor("#a1b2c3"))
        assertEquals("#a1b2c3", BookEdits.cleanColor(" #A1B2C3 "))
    }

    @Test fun a_foreign_manifest_or_book_file_loses_a_tracking_colour_but_keeps_a_real_one() {
        val tracked = JSONObject().put("cover", JSONObject().put("file", "cover.jpg").put("color", tracker).put("width", 1).put("height", 1))
        BookEdits.scrubCoverColor(tracked)
        assertFalse(tracked.getJSONObject("cover").has("color"))
        assertEquals("cover.jpg", tracked.getJSONObject("cover").getString("file"))
        val real = JSONObject().put("cover", JSONObject().put("file", "cover.jpg").put("color", "#0A141E"))
        BookEdits.scrubCoverColor(real)
        assertEquals("#0a141e", real.getJSONObject("cover").getString("color"))
        BookEdits.scrubCoverColor(JSONObject()) // sách không có bìa: không sao
    }

    @Test fun the_peer_manifest_gate_scrubs_the_colour() {
        val manifest = JSONObject("""{"title":"x","chapters":[],"cover":{"file":"cover.jpg","color":"$tracker"}}""")
        PeerPaths.checkManifest(manifest)
        assertFalse(manifest.getJSONObject("cover").has("color"))
    }

    @Test fun the_listed_cover_never_carries_a_tracking_colour() {
        val listed = JSONObject().put("cover", JSONObject().put("version", 3).put("color", tracker))
        val same = JSONObject().put("cover", JSONObject().put("version", 3).put("color", JSONObject.NULL))
        assertFalse("hai bên cùng không màu thì không phải đã đổi", StreamRefresh.stale(same, listed.put("chaptersAvailable", 0).put("title", "").put("author", "")))
    }

    @Test fun the_budget_counts_per_address_and_overall_and_releases() {
        val budget = ConnectionBudget(total = 3, perIp = 2)
        assertTrue(budget.take("a")); assertTrue(budget.take("a")); assertFalse(budget.take("a"))
        assertTrue(budget.take("b")); assertFalse(budget.take("c"))
        budget.release("a")
        assertTrue(budget.take("c"))
        for (who in listOf("a", "b", "c", "a", "a")) budget.release(who) // thừa: không âm
        assertEquals(0, budget.active())
        assertTrue(budget.take("a")); assertTrue(budget.take("a"))
    }

    @Test fun the_header_deadline_is_total_not_per_read() {
        assertEquals(10_000L, ConnectionBudget.headerRemainingMs(1_000, 1_000))
        assertTrue(ConnectionBudget.headerRemainingMs(1_000, 10_999) > 0)
        assertTrue("đọc từng byte mỗi giây vẫn hết hạn", ConnectionBudget.headerRemainingMs(1_000, 11_000) <= 0)
        assertTrue(ConnectionBudget.headerRemainingMs(1_000, 5_000, limitMs = 3_000) <= 0)
    }

    @Test fun a_flood_of_silent_sockets_from_one_address_is_cut_at_the_cap_and_real_requests_still_work() {
        val folder = Files.createTempDirectory("a109").toFile()
        val audio = File(folder, "1.mp3").apply { writeBytes(ByteArray(2_000) { 7 }) }
        val media = Dlna.Media("127.0.0.1")
        val held = mutableListOf<Socket>()
        try {
            val url = media.share(audio, "127.0.0.1")
            val port = java.net.URI(url).port
            repeat(ConnectionBudget.MAX_PER_IP) {
                held += Socket().apply { connect(InetSocketAddress("127.0.0.1", port), 2_000); getOutputStream().write("GET /c/x HTTP/1.1\r\nX: ".toByteArray()) }
            }
            val extra = Socket().apply { connect(InetSocketAddress("127.0.0.1", port), 2_000); soTimeout = 3_000 }
            held += extra
            assertEquals("kết nối vượt trần bị đóng ngay", -1, extra.getInputStream().read())
        } finally {
            held.forEach { runCatching { it.close() } }
            media.close()
            folder.deleteRecursively()
        }
    }
}
