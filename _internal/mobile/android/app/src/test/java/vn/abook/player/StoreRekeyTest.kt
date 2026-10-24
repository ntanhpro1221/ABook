package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Cuốn mở từ file được máy tính nhận ra (Store.adopt): đổi sang mã của máy tính - thư mục, gói sách, liên kết hồ sơ nghe,
 * sổ dấu vân tay - thay vì hiện hai bản của một cuốn; việc đổi mã đi qua journal nên tắt ngang vẫn làm nốt.
 */
class StoreRekeyTest {
    private lateinit var root: File
    private val old = "f-cua-dien-thoai"
    private val new = "0123456789abcdef01234567"

    @Before
    fun setUp() {
        root = Files.createTempDirectory("abook-rekey").toFile()
        // Store là object: đặt thư mục và bỏ bộ đệm hồ sơ bằng phản chiếu cho từng test JVM.
        Store::class.java.getDeclaredField("root").apply { isAccessible = true }.set(null, root)
        Store::class.java.getDeclaredField("recordsCache").apply { isAccessible = true }.set(null, null)
        File(root, "books/$old/chapters").mkdirs()
        File(root, "books/$old/chapters/001.mp3").writeText("x")
        File(root, "books/$old/book.json").writeText(JSONObject().put("id", old).put("title", "Sách").toString())
        File(root, "records.json").writeText(JSONObject().put("version", 2)
            .put("records", JSONObject().put("r-1", JSONObject().put("name", "Mặc định")))
            .put("links", JSONObject().put(old, JSONObject().put("records", JSONArray().put("r-1")).put("active", "r-1")))
            .put("deleted", JSONObject()).toString())
        File(root, "prints.json").writeText(JSONObject()
            .put(old, JSONObject().put("chapters", JSONObject()).put("imported", true)).toString())
    }

    @Test
    fun a_book_opened_from_a_file_moves_with_its_listening_records() {
        Store.adopt(old, new)

        assertFalse(File(root, "books/$old").exists())
        assertTrue(File(root, "books/$new/chapters/001.mp3").isFile)
        assertEquals(new, Store.manifest(new)!!.getString("id"))
        assertEquals("r-1", Store.knownActiveRecord(new))
        assertNull(Store.knownActiveRecord(old))
        assertTrue(JSONObject(File(root, "prints.json").readText()).has(new))
    }

    @Test
    fun restart_finishes_a_journal_whose_directory_already_moved() {
        File(root, "rekey_journal.json").writeText(JSONObject().put(old,
            JSONObject().put("to", new).put("adopt", false)).toString())
        assertTrue(File(root, "books/$old").renameTo(File(root, "books/$new")))
        Store.adopt(old, new)
        assertEquals("r-1", Store.knownActiveRecord(new))
        assertNull(Store.knownActiveRecord(old))
        assertEquals(new, Store.rawManifest(new)!!.getString("id"))
        assertTrue(JSONObject(File(root, "prints.json").readText()).has(new))
        // A second restart is harmless even after some writes were already completed.
        Store.adopt(old, new)
        assertEquals("r-1", Store.knownActiveRecord(new))
    }

    @Test
    fun retry_after_a_failed_links_write_still_commits_links_before_clearing_the_journal() {
        val blocker = File(root, "records.json.part").apply { mkdirs() }
        assertTrue(runCatching { Store.adopt(old, new) }.isFailure)
        assertTrue(File(root, "rekey_journal.json").isFile)
        assertTrue(blocker.delete())
        Store.recoverRekeys()
        val links = JSONObject(File(root, "records.json").readText()).getJSONObject("links")
        assertFalse(links.has(old))
        assertEquals("r-1", links.getJSONObject(new).getString("active"))
    }

    @Test
    fun a_journal_that_cannot_go_on_is_dropped_without_failing_the_app_start() {
        File(root, "rekey_journal.json").writeText(JSONObject()
            .put("gone1", JSONObject().put("to", "gone2").put("adopt", false)) // sách đã bị xoá: không còn thư mục nào
            .put("../x", JSONObject().put("to", new)).toString())
        Store.recoverRekeys()
        assertEquals(0, JSONObject(File(root, "rekey_journal.json").readText()).length())
        assertEquals("r-1", Store.knownActiveRecord(old))
    }

    @Test
    fun an_escaping_id_or_a_copy_already_under_the_new_id_changes_nothing() {
        runCatching { Store.adopt(old, "../x") }
        runCatching { Store.adopt(old, "") }
        File(root, "books/$new").mkdirs()
        File(root, "books/$new/book.json").writeText(JSONObject().put("id", new).toString())

        Store.adopt(old, new)

        assertTrue(File(root, "books/$old/chapters/001.mp3").isFile)
        assertEquals("r-1", Store.knownActiveRecord(old))
    }
}
