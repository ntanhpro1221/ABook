package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test

/**
 * Thôi ghép hai phía, ghép lại không sinh dòng trùng - như máy tính (webui/sync.py, soát a27 lỗi 5): máy kia báo `POST /sync/v1/unpair` thì
 * điện thoại thu hồi mã của nó; cùng máy (cùng mã máy `id` gửi lúc ghép) ghép lại thì thay dòng cũ.
 */
class LibraryServerUnpairTest {
    private lateinit var root: File

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-server-unpair")
        BookEditsFixtures.useStoreRoot(root)
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, File(root, "share.json"))
    }

    private fun call(method: String, path: String, body: JSONObject = JSONObject(), token: String = ""): Pair<Int, JSONObject> {
        val out = ByteArrayOutputStream()
        val headers = if (token.isEmpty()) emptyMap() else mapOf("authorization" to "Bearer $token")
        LibraryServer.route(LibraryServer.Request(method, path, headers, body.toString().toByteArray()), out)
        val raw = String(out.toByteArray(), Charsets.UTF_8)
        return raw.substringAfter(" ").substringBefore(" ").toInt() to JSONObject(raw.substringAfter("\r\n\r\n"))
    }

    private fun pair(id: String): String {
        val code = LibraryServer.startPairing().getString("code")
        val (status, reply) = call("POST", "/sync/v1/pair", JSONObject().put("code", code).put("device", "Máy B").apply { if (id.isNotEmpty()) put("id", id) })
        assertEquals(200, status)
        return reply.getString("token")
    }

    @Test
    fun the_same_machine_pairing_again_replaces_its_row() {
        val first = pair("0123456789abcdef")
        pair("0123456789abcdef")
        assertEquals(1, LibraryServer.devices().length())
        assertEquals("mã cũ hết hiệu lực", 401, call("GET", "/sync/v1/library", token = first).first)
        pair("")
        assertEquals("máy không gửi mã máy: dòng riêng", 2, LibraryServer.devices().length())
    }

    @Test
    fun the_other_side_unpairing_revokes_its_token_here() {
        val token = pair("0123456789abcdef")
        assertEquals(200, call("POST", "/sync/v1/unpair", token = token).first)
        assertEquals(0, LibraryServer.devices().length())
        assertEquals(401, call("GET", "/sync/v1/library", token = token).first)
    }
}
