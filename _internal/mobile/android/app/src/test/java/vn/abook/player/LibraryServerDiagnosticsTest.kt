package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import org.json.JSONArray
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** `GET /sync/v1/diagnostics` (a114): chỉ máy đã ghép (sai / thiếu mã -> 401 như mọi đường khác), trả JSON bản chẩn đoán, số dòng được kẹp. */
class LibraryServerDiagnosticsTest {
    private val token = "tok-ghep-noi"
    private val asked = mutableListOf<Int>()
    private val original = LibraryServer.diagnosticsSource

    @Before
    fun setUp() {
        val root = BookEditsFixtures.tempDir("abook-server-diag")
        BookEditsFixtures.useStoreRoot(root)
        val devices = File(root, "share.json")
        val hash = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }
        devices.writeText(JSONObject().put("devices", JSONObject().put(hash, JSONObject().put("name", "Máy tính thử").put("lastSeen", 1e12))).toString())
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, devices)
        LibraryServer.diagnosticsSource = { lines ->
            asked += lines
            JSONObject().put("schema", 1).put("app", JSONObject().put("versionName", "0.4.133")).put("log", JSONArray().put("dòng"))
        }
    }

    @After
    fun tearDown() {
        LibraryServer.diagnosticsSource = original
    }

    private fun get(path: String, bearer: String? = token): Pair<Int, JSONObject> {
        val out = ByteArrayOutputStream()
        val query = path.substringAfter('?', "")
        val headers = if (bearer == null) emptyMap() else mapOf("authorization" to "Bearer $bearer")
        LibraryServer.route(LibraryServer.Request("GET", path.substringBefore('?'), headers, ByteArray(0), query), out)
        val raw = String(out.toByteArray(), Charsets.UTF_8)
        return raw.substringAfter(" ").substringBefore(" ").toInt() to JSONObject(raw.substringAfter("\r\n\r\n"))
    }

    @Test
    fun a_paired_device_gets_the_report_and_the_line_count_is_clamped() {
        val (status, body) = get("/sync/v1/diagnostics?lines=50")
        assertEquals(200, status)
        assertEquals("0.4.133", body.getJSONObject("app").getString("versionName"))
        assertTrue(body.has("schema") && body.has("log"))
        get("/sync/v1/diagnostics")
        get("/sync/v1/diagnostics?lines=99999999")
        get("/sync/v1/diagnostics?lines=-4")
        assertEquals(listOf(50, Diagnostics.DEFAULT_LINES, Diagnostics.MAX_LINES, 1), asked)
    }

    @Test
    fun without_the_right_code_nothing_is_collected() {
        assertEquals(401, get("/sync/v1/diagnostics", bearer = null).first)
        assertEquals(401, get("/sync/v1/diagnostics", bearer = "ma-sai").first)
        assertTrue("không thu gì khi chưa xác thực", asked.isEmpty())
    }

    @Test
    fun the_other_routes_still_answer_as_before() {
        assertEquals(200, get("/sync/v1/library").first)
        assertEquals(404, get("/sync/v1/books/abc/diagnostics").first)
    }
}
