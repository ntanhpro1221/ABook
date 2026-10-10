package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/** "Xoá khỏi điện thoại" có Hoàn tác: chỗ chờ `.trash-pending` (TrashPending) và đường Store đi qua nó. */
class TrashPendingTest {
    private lateinit var root: File
    private var now = 1_000_000L

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-trash").toFile()
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        makeBook("a1")
        makeBook("b2")
    }

    private fun makeBook(id: String) {
        File(root, "books/$id/chapters").mkdirs()
        File(root, "books/$id/book.json").writeText("""{"id":"$id","title":"Sách $id"}""")
        File(root, "books/$id/chapters/001.mp3").writeText("audio-$id")
        File(root, "books/$id/edits.json").writeText("""{"title":"sửa $id"}""")
    }

    private fun pending() = TrashPending(root) { now }
    private fun pendingFolders() = File(root, ".trash-pending").listFiles().orEmpty().toList()

    @Test
    fun hold_moves_the_whole_book_out_of_the_library_and_undo_brings_it_back_intact() {
        val trash = pending()
        val token = trash.hold(File(root, "books/a1"), "a1")!!
        assertEquals(32, token.length)
        assertFalse(File(root, "books/a1").exists())
        assertTrue(File(root, "books/b2").isDirectory)
        assertTrue(File(root, ".trash-pending/$token/a1/chapters/001.mp3").isFile)

        val meta = trash.restore(token)
        assertEquals("a1", meta.getString("id"))
        assertEquals("audio-a1", File(root, "books/a1/chapters/001.mp3").readText())
        assertEquals("""{"title":"sửa a1"}""", File(root, "books/a1/edits.json").readText())
        assertTrue("chỗ chờ trống thì thư mục cũng đi", pendingFolders().isEmpty())
    }

    @Test
    fun an_unknown_or_used_token_is_refused() {
        val trash = pending()
        assertThrows(TrashPending.NotPending::class.java) { trash.restore("0".repeat(32)) }
        assertThrows(TrashPending.NotPending::class.java) { trash.restore("../books") }
        val token = trash.hold(File(root, "books/a1"), "a1")!!
        trash.restore(token)
        assertThrows(TrashPending.NotPending::class.java) { trash.restore(token) }
        assertTrue(File(root, "books/a1/book.json").isFile)
    }

    @Test
    fun undo_refuses_when_the_old_place_was_taken_and_keeps_the_book_waiting() {
        val trash = pending()
        val token = trash.hold(File(root, "books/a1"), "a1")!!
        makeBook("a1") // tải lại cuốn cùng mã trong lúc chờ
        assertThrows(TrashPending.Occupied::class.java) { trash.restore(token) }
        assertEquals("audio-a1", File(root, ".trash-pending/$token/a1/chapters/001.mp3").readText())
    }

    @Test
    fun sweep_deletes_only_what_is_past_the_deadline() {
        val trash = pending()
        val old = trash.hold(File(root, "books/a1"), "a1")!!
        now += (TrashPending.UNDO_SECONDS - 5) * 1000L
        val fresh = trash.hold(File(root, "books/b2"), "b2")!!
        now += 6_000L // a1 đã 31 s, b2 mới 6 s
        val purged = mutableListOf<String>()
        assertEquals(1, trash.sweep { purged += it.getString("id") })
        assertEquals(listOf("a1"), purged)
        assertFalse(File(root, ".trash-pending/$old").exists())
        assertTrue(File(root, ".trash-pending/$fresh/b2/chapters/001.mp3").isFile)
        assertThrows(TrashPending.NotPending::class.java) { trash.restore(old) }
        trash.restore(fresh)
    }

    @Test
    fun sweep_everything_at_startup_deletes_even_fresh_ones_and_removes_the_empty_folder() {
        val trash = pending()
        trash.hold(File(root, "books/a1"), "a1")!!
        trash.hold(File(root, "books/b2"), "b2")!!
        assertEquals(0, trash.sweep(everything = true))
        assertFalse(File(root, ".trash-pending").exists())
        assertFalse(File(root, "books/a1").exists())
    }

    @Test
    fun a_failed_purge_leaves_the_book_and_a_half_purge_cannot_be_undone() {
        val trash = pending()
        val token = trash.hold(File(root, "books/a1"), "a1")!!
        // dọn dở: meta đã bỏ nhưng thư mục chưa xoá hết -> không còn Hoàn tác ra cuốn thiếu file
        File(root, ".trash-pending/$token/meta.json").delete()
        assertThrows(TrashPending.NotPending::class.java) { trash.restore(token) }
        assertEquals(0, trash.sweep())
        assertFalse(File(root, ".trash-pending/$token").exists())
        // onPurge văng -> cuốn còn nguyên chờ lần sau
        val again = trash.hold(File(root, "books/b2"), "b2")!!
        now += 60_000L
        assertEquals(1, trash.sweep { error("không dọn được") })
        assertTrue(File(root, ".trash-pending/$again/b2/chapters/001.mp3").isFile)
    }

    @Test
    fun the_library_scan_never_sees_the_waiting_book() {
        val token = Store.holdBook("a1")!!
        assertEquals(listOf("b2"), Store.bookIds())
        assertEquals(listOf("b2"), Store.books().map { it.getString("id") })
        assertEquals(setOf("b2"), Store.bookSizes().keys)
        assertTrue(File(root, ".trash-pending/$token").isDirectory)
    }

    @Test
    fun the_companion_data_follows_the_book_back_and_is_cleared_only_when_deleted_for_good() {
        Store.rememberChapters("a1", JSONObject().put("chapters/001.mp3", JSONObject().put("size", 9).put("sha256", "ab")), imported = true)
        Store.rememberChapters("b2", JSONObject().put("chapters/001.mp3", JSONObject().put("size", 9).put("sha256", "cd")), imported = true)

        val token = Store.holdBook("a1")!!
        assertEquals("sổ nhận diện chưa bị đụng khi mới vào chỗ chờ", "ab", Store.chapterPrints("a1").getJSONObject("chapters/001.mp3").getString("sha256"))
        Store.undoBook(token)
        assertEquals("ab", Store.chapterPrints("a1").getJSONObject("chapters/001.mp3").getString("sha256"))
        assertTrue(Store.isImported("a1"))
        assertEquals("audio-a1", File(root, "books/a1/chapters/001.mp3").readText())

        Store.holdBook("a1")!!
        assertEquals(0, Store.sweepTrash(everything = true))
        assertEquals("xoá hẳn thì sổ cũng sạch", 0, Store.chapterPrints("a1").length())
        assertEquals("sổ của cuốn khác còn", 1, Store.chapterPrints("b2").length())
        assertFalse(File(root, "books/a1").exists())
    }

    @Test
    fun a_book_reloaded_under_the_same_id_keeps_its_ledger_when_the_old_copy_is_swept() {
        Store.rememberChapters("a1", JSONObject().put("chapters/001.mp3", JSONObject().put("size", 9).put("sha256", "ab")), imported = false)
        Store.holdBook("a1")!!
        makeBook("a1")
        assertEquals(0, Store.sweepTrash(everything = true))
        assertEquals(1, Store.chapterPrints("a1").length())
        assertTrue(File(root, "books/a1/book.json").isFile)
    }

    @Test
    fun holdBook_refuses_a_bad_id_and_deletes_straight_when_the_book_is_not_there() {
        for (id in listOf("", "..", "../books", "a 1")) assertThrows(IllegalArgumentException::class.java) { Store.holdBook(id) }
        assertTrue(File(root, "books/a1/book.json").isFile)
        assertNull(Store.holdBook("khong-co"))
        assertNotNull(Store.holdBook("b2"))
    }
}
