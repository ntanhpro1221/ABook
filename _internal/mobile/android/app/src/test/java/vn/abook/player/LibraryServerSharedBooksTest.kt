package vn.abook.player

import java.io.ByteArrayOutputStream
import java.io.File
import java.security.MessageDigest
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Điện thoại chỉ chia sẻ cho máy đã ghép những cuốn NHẬP TỪ FILE, như máy tính chỉ chia sẻ `Sách đã nhập/` (webui/package_share.py): bản
 * soi sách của máy khác (tải từ máy tính, hay từ thiết bị ghép) mà chia sẻ lại thì hai máy cứ soi nhau mãi. Thư viện mang tác giả như máy
 * tính (`library_entry`), để máy kia tìm và sắp theo tác giả được.
 */
class LibraryServerSharedBooksTest {
    private lateinit var root: File
    private val token = "tok-ghep-noi"
    private val imported = "aaaaaaaaaaaaaaaaaaaaaaaa"
    private val fromComputer = "bbbbbbbbbbbbbbbbbbbbbbbb"
    private val fromPeer = "pcccccccccccccccccccccccc"

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-share-books")
        BookEditsFixtures.useStoreRoot(root)
        val devices = File(root, "share.json")
        val hash = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }
        devices.writeText(JSONObject().put("devices", JSONObject().put(hash, JSONObject().put("name", "Máy thử").put("lastSeen", 1e12))).toString())
        LibraryServer::class.java.getDeclaredField("devicesFile").apply { isAccessible = true }.set(LibraryServer, devices)
        book(imported, author = "Tác giả thử")
        Store.rememberChapters(imported, JSONObject(), imported = true) // mở từ file
        book(fromComputer)
        Store.rememberChapters(fromComputer, JSONObject(), imported = false) // tải từ máy tính chính
        book(fromPeer, source = "peer1") // tải từ thiết bị ghép
    }

    private fun book(id: String, author: String = "", source: String = "") {
        val dir = BookEditsFixtures.copyBase(Store.bookDir(id))
        val manifest = JSONObject(File(dir, "book.json").readText()).put("id", id)
        if (author.isNotEmpty()) manifest.put("author", author)
        if (source.isNotEmpty()) manifest.put("source", source).put("remoteId", "remote1").put("sourceKind", "computer")
        File(dir, "book.json").writeText(manifest.toString())
    }

    private fun get(path: String): Pair<Int, JSONObject> {
        val out = ByteArrayOutputStream()
        LibraryServer.route(LibraryServer.Request("GET", path, mapOf("authorization" to "Bearer $token"), ByteArray(0)), out)
        val raw = String(out.toByteArray(), Charsets.UTF_8)
        return raw.substringAfter(" ").substringBefore(" ").toInt() to JSONObject(raw.substringAfter("\r\n\r\n"))
    }

    @Test
    fun only_books_opened_from_a_file_are_listed_and_they_carry_the_author() {
        val (status, library) = get("/sync/v1/library")
        assertEquals(200, status)
        val books = library.getJSONArray("books")
        assertEquals(listOf(imported), (0 until books.length()).map { books.getJSONObject(it).getString("id") })
        assertEquals("Tác giả thử", books.getJSONObject(0).getString("author"))
    }

    @Test
    fun a_book_without_an_author_has_no_author_key() {
        File(Store.bookDir(imported), "book.json").let { file -> file.writeText(JSONObject(file.readText()).apply { remove("author") }.toString()) }
        val book = get("/sync/v1/library").second.getJSONArray("books").getJSONObject(0)
        assertFalse(book.has("author"))
    }

    @Test
    fun the_copy_of_another_machines_book_is_neither_listed_nor_served() {
        assertEquals(200, get("/sync/v1/books/$imported/manifest").first)
        assertEquals("Tác giả thử", get("/sync/v1/books/$imported/manifest").second.getString("author"))
        for (id in listOf(fromComputer, fromPeer)) {
            assertEquals(id, 404, get("/sync/v1/books/$id/manifest").first)
            assertEquals(id, 404, get("/sync/v1/books/$id/files/chapters/00001_645.mp3").first)
        }
        assertTrue(Store.isFileBook(imported) && !Store.isFileBook(fromComputer) && !Store.isFileBook(fromPeer))
    }
}
