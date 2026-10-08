package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Điện thoại báo thêm TÊN BLUETOOTH của nó (`bluetoothName`) trong lời chào UDP, lời ghép và lời đáp thư viện (cùng một hàm
 * `identity`; lời ghép không chạy được trong JVM vì Base64 của Android, nên thử bằng lời đáp thư viện): Windows lưu tên Bluetooth người
 * dùng đặt, không phải tên máy ở Wi-Fi, nên máy tính cần nó để tự khớp thiết bị đã ghép (remote_books._match_paired). Không có
 * quyền / không có tên thì bỏ trường, lời đáp vẫn như cũ.
 */
class LibraryServerBluetoothNameTest {
    private lateinit var root: File
    private val token = "tok-ghep-noi"

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-share-btname")
        BookEditsFixtures.useStoreRoot(root)
        val devices = File(root, "share.json")
        val hash = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }
        devices.writeText(JSONObject().put("devices", JSONObject().put(hash, JSONObject().put("name", "Máy thử").put("lastSeen", 1e12))).toString())
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, devices)
    }

    @After
    fun tearDown() {
        LibraryServer.bluetoothNameSource = { "" }
    }

    private fun send(method: String, path: String, body: JSONObject? = null): JSONObject {
        val headers = if (body == null) mapOf("authorization" to "Bearer $token") else emptyMap()
        val out = ByteArrayOutputStream()
        LibraryServer.route(LibraryServer.Request(method, path, headers, body?.toString()?.toByteArray() ?: ByteArray(0)), out)
        val raw = String(out.toByteArray(), Charsets.UTF_8)
        assertTrue(raw, raw.startsWith("HTTP/1.1 200"))
        return JSONObject(raw.substringAfter("\r\n\r\n"))
    }

    @Test
    fun the_library_reply_carries_the_bluetooth_name_next_to_the_wifi_name() {
        LibraryServer.bluetoothNameSource = { "Pixel của An" }
        val reply = send("GET", "/sync/v1/library")
        assertEquals("Pixel của An", reply.getString("bluetoothName"))
        assertEquals(LibraryServer.name(), reply.getString("name"))
    }

    @Test
    fun without_a_name_or_when_the_lookup_fails_the_field_is_left_out() {
        LibraryServer.bluetoothNameSource = { "" }
        assertFalse(send("GET", "/sync/v1/library").has("bluetoothName"))
        LibraryServer.bluetoothNameSource = { throw SecurityException("thiếu BLUETOOTH_CONNECT") }
        val reply = send("GET", "/sync/v1/library")
        assertFalse(reply.has("bluetoothName"))
        assertEquals(LibraryServer.name(), reply.getString("name"))
    }
}
