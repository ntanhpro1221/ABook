package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Điện thoại nói cùng lời với máy tính khi ghép (webui/sync.py `wrong_code_message`, remote_books.py `Computers.pair`): nhập sai mã thì
 * đếm lùi số lần thử, đủ 5 lần thì mã bị huỷ; ghép bằng địa chỉ của chính điện thoại này thì bị từ chối trước khi gửi mã.
 */
class PairingWordsTest {
    @Before
    fun setUp() {
        val root = BookEditsFixtures.tempDir("abook-pairing-words")
        BookEditsFixtures.useStoreRoot(root)
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, File(root, "share.json"))
        LibraryServer.cancelPairing()
    }

    private fun tryCode(code: String): Pair<Int, String> {
        val out = ByteArrayOutputStream()
        val body = JSONObject().put("code", code).put("device", "Máy thử").toString().toByteArray()
        LibraryServer.route(LibraryServer.Request("POST", "/sync/v1/pair", emptyMap(), body), out)
        val raw = String(out.toByteArray(), Charsets.UTF_8)
        return raw.substringAfter(" ").substringBefore(" ").toInt() to JSONObject(raw.substringAfter("\r\n\r\n")).optString("error")
    }

    @Test
    fun wrongCodesCountDownThenTheCodeIsCancelled() {
        val code = LibraryServer.startPairing().getString("code")
        val wrong = if (code == "000000") "111111" else "000000"
        for (left in 4 downTo 1) {
            val (status, error) = tryCode(wrong)
            assertEquals(403, status)
            assertEquals("Mã ghép nối sai - còn $left lần thử (sai 5 lần mã sẽ bị huỷ)", error)
        }
        val (_, last) = tryCode(wrong)
        assertEquals("Nhập sai 5 lần nên mã đã bị huỷ - tạo mã mới ở máy kia rồi nhập lại", last)
        // Mã đã huỷ: ngay cả mã đúng cũng không vào được nữa.
        assertEquals(403, tryCode(code).first)
        assertTrue(LibraryServer.blocked)
    }

    @Test
    fun withoutAnActiveCodeTheWordsSayToMakeANewOne() {
        LibraryServer.cancelPairing()
        val (status, error) = tryCode("123456")
        assertEquals(403, status)
        assertEquals("Mã ghép nối sai hoặc đã hết hạn - tạo mã mới ở máy kia", error)
    }

    @Test
    fun theLeftoverWordsMatchTheComputer() {
        assertEquals("Mã ghép nối sai - còn 3 lần thử (sai 5 lần mã sẽ bị huỷ)", LibraryServer.wrongCodeText(false, true, 2))
        assertEquals("Mã ghép nối sai hoặc đã hết hạn - tạo mã mới ở máy kia", LibraryServer.wrongCodeText(false, false, 0))
    }

    @Test
    fun ownAddressWithOwnPortIsRefused() {
        val own = listOf("192.168.1.20")
        assertTrue(SyncLink.isOwnAddress("192.168.1.20", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress(" 192.168.1.20 ", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("127.0.0.1", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("LocalHost", 47630, 47630, own))
        // Máy khác, hay cùng địa chỉ nhưng cổng khác (một dịch vụ khác của máy này), thì không phải chính mình.
        assertFalse(SyncLink.isOwnAddress("192.168.1.21", 47630, 47630, own))
        assertFalse(SyncLink.isOwnAddress("192.168.1.20", 47631, 47630, own))
    }

    @Test
    fun ownIpv6AndMappedLoopbackAreRefusedToo() {
        val own = listOf("192.168.1.20", "2402:800:1::20", "fe80::1234%wlan0")
        assertTrue(SyncLink.isOwnAddress("::1", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("[::1]", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("0:0:0:0:0:0:0:1", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("::ffff:127.0.0.1", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("::ffff:192.168.1.20", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("2402:800:1::20", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("[2402:0800:0001:0000:0000:0000:0000:0020]", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("fe80::1234%12", 47630, 47630, own))
        assertTrue(SyncLink.isOwnAddress("127.5.6.7", 47630, 47630, own))
        assertFalse(SyncLink.isOwnAddress("2402:800:1::21", 47630, 47630, own))
        assertFalse(SyncLink.isOwnAddress("::ffff:192.168.1.21", 47630, 47630, own))
        assertFalse(SyncLink.isOwnAddress("may-khac.local", 47630, 47630, own)) // tên chữ không tra DNS: máy khác
        assertFalse(SyncLink.isOwnAddress("2402:800:1::20", 47631, 47630, own))
    }

    @Test
    fun refuseSelfSaysWhatToDo() {
        val error = runCatching { SyncLink.refuseSelf("127.0.0.1", LibraryServer.PORT) }.exceptionOrNull()
        assertEquals("Đây là địa chỉ của chính máy này - nhập địa chỉ máy kia", error?.message)
        SyncLink.refuseSelf("203.0.113.9", LibraryServer.PORT) // máy khác: không ném
    }

    @Test
    fun theCertificateWordsOfferTheWayOut() {
        assertTrue("Thôi ghép" in Pin.CHANGED && "ghép lại" in Pin.CHANGED)
    }
}
