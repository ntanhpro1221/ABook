package vn.abook.player

import java.io.File
import org.json.JSONObject
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Thôi ghép một thiết bị xoá thư mục các cuốn nghe thẳng của nó - kể cả phần sửa chưa gửi (docs/EDITING.md, P2d). Phần đếm sửa chưa gửi,
 * gửi trước rồi mới gỡ, và từ chối thôi ghép khi chưa chọn bỏ (Peers.unsent / sendUnsent / refuseIfUnsent) không được để mất lặng lẽ.
 */
class PeersUnpairTest {
    private lateinit var root: File
    private val base get() = BookEditsFixtures.file("base")

    @Before
    fun setUp() {
        root = BookEditsFixtures.tempDir("abook-unpair")
        BookEditsFixtures.useStoreRoot(root)
        LocalStudio.clock = { 1_790_950_256L }
        LocalStudio.now = { 1_790_950_256.0 }
        EditsSync.clock = { 1_790_960_000L }
        EditsSync.refresh = null
        EditsSync.changed = null
    }

    @After
    fun tearDown() {
        LocalStudio.now = { System.currentTimeMillis() / 1000.0 }
        EditsSync.clock = { System.currentTimeMillis() / 1000 }
        EditsSync.refresh = null
        EditsSync.changed = null
    }

    /** Cuốn nghe thẳng của thiết bị `key` (chỉ `stream.json`), chưa sửa gì. */
    private fun streamed(key: String, remote: String, kind: String): String {
        val id = Peers.localId(key, remote)
        val dir = Store.bookDir(id)
        dir.mkdirs()
        val manifest = BookEdits.rawBook(base).put("id", id).put("source", key).put("remoteId", remote).put("sourceKind", kind)
        File(dir, "stream.json").writeText(manifest.toString())
        return id
    }

    private fun rename(id: String, title: String) =
        assertEquals(200, LocalStudio.handle("PUT", "/api/books/$id/title", JSONObject().put("title", title)).first)

    private fun accepted() = JSONObject().put("applied", 1).put("skipped", 0).put("requests", 0).put("waiting", 0).put("skippedWishes", 0).toString()

    @Test
    fun only_the_unsent_edits_of_that_device_streamed_books_are_counted() {
        val one = streamed("k1", "b1", "computer")
        val two = streamed("k1", "b2", "computer")
        streamed("k1", "b3", "computer") // không sửa gì: không tính
        val other = streamed("k2", "b1", "computer") // thiết bị khác: không tính
        rename(one, "Tên một")
        rename(two, "Tên hai")
        rename(other, "Của máy khác")
        // cuốn đã tải của chính thiết bị này giữ nguyên khi thôi ghép (có book.json): sửa của nó không mất nên không tính
        val downloaded = Peers.localId("k1", "b4")
        BookEditsFixtures.copyBase(Store.bookDir(downloaded))
        File(Store.bookDir(downloaded), "book.json").writeText(BookEdits.rawBook(base).put("source", "k1").put("sourceKind", "computer").toString())
        rename(downloaded, "Đã tải")

        val unsent = Peers.unsent("k1")
        assertEquals(listOf(one, two), unsent.books.map { it.id })
        assertEquals(listOf("Tên một", "Tên hai"), unsent.books.map { it.title })
        assertEquals(2, unsent.changes)
        assertEquals(1, Peers.unsent("k2").changes)
        assertEquals(0, Peers.unsent("k3").books.size)
    }

    @Test
    fun forgetting_is_refused_while_edits_are_unsent_unless_the_listener_chose_to_drop_them() {
        val id = streamed("k1", "b1", "phone")
        rename(id, "Chỉ ở đây")
        val error = assertThrows(IllegalStateException::class.java) { Peers.refuseIfUnsent("k1", discard = false) }
        assertTrue(error.message!!.contains("1 cuốn còn 1 thay đổi chưa gửi"))
        assertTrue(File(Store.bookDir(id), "edits.json").isFile) // từ chối thì không đụng gì
        Peers.refuseIfUnsent("k1", discard = true) // đã chọn bỏ: không từ chối
        Peers.refuseIfUnsent("k9", discard = false) // thiết bị không có sửa nào: như cũ
    }

    @Test
    fun sending_first_sends_every_book_and_leaves_nothing_to_lose() {
        val one = streamed("k1", "b1", "computer")
        val two = streamed("k1", "b2", "computer")
        rename(one, "Tên một")
        rename(two, "Tên hai")
        val sent = mutableListOf<String>()
        Peers.sendUnsent("k1") { id ->
            sent += id
            EditsSync.push(id) { accepted() }
        }
        assertEquals(listOf(one, two), sent)
        assertEquals(0, Peers.unsent("k1").books.size)
        Peers.refuseIfUnsent("k1", discard = false) // giờ thôi ghép không còn gì để mất
        assertEquals(0, BookEdits.count(BookEdits.load(Store.bookDir(one))))
    }

    @Test
    fun a_failed_send_stops_and_keeps_every_edit_that_was_not_sent() {
        val one = streamed("k1", "b1", "computer")
        val two = streamed("k1", "b2", "computer")
        rename(one, "Tên một")
        rename(two, "Tên hai")
        val error = assertThrows(java.io.IOException::class.java) {
            Peers.sendUnsent("k1") { id -> EditsSync.push(id) { if (id == two) throw java.io.IOException("mất mạng") else accepted() } }
        }
        assertTrue(error.message!!.contains("Chưa tới được máy tính"))
        assertEquals(listOf(two), Peers.unsent("k1").books.map { it.id })
        assertEquals("Tên hai", BookEdits.load(Store.bookDir(two)).getString("title"))
        assertThrows(IllegalStateException::class.java) { Peers.refuseIfUnsent("k1", discard = false) }
    }

    @Test
    fun an_edit_made_while_sending_is_not_lost_silently() {
        val id = streamed("k1", "b1", "computer")
        rename(id, "Tên một")
        val error = assertThrows(IllegalStateException::class.java) {
            Peers.sendUnsent("k1") { book -> EditsSync.push(book) { rename(book, "Đổi tiếp"); accepted() } }
        }
        assertTrue(error.message!!.contains("Còn 1 thay đổi"))
        assertEquals("Đổi tiếp", BookEdits.load(Store.bookDir(id)).getString("title"))
    }
}
