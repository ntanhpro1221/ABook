package vn.ebookreader.player

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
 * Máy tính đổi mã sách (0.4.0, docs/BOOK_IDS.md): cuốn điện thoại tải hay nghe thẳng theo mã kiểu cũ đổi sang mã mới -
 * thư mục, gói sách, liên kết hồ sơ nghe, sổ dấu vân tay - thay vì hiện hai bản của một cuốn.
 */
class StoreRekeyTest {
    private lateinit var root: File
    private val old = "QzpcVXNlcnNcQW5oXEF1ZGlvYm9va3NcU8OhY2g" // "C:\Users\Anh\Audiobooks\Sách" mã hoá base64
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
            .put(old, JSONObject().put("chapters", JSONObject()).put("imported", false)).toString())
    }

    @Test
    fun a_book_downloaded_under_an_old_id_moves_with_its_listening_records() {
        assertEquals(listOf(old), Store.computerBooks())

        Store.rekey(old, new)

        assertFalse(File(root, "books/$old").exists())
        assertTrue(File(root, "books/$new/chapters/001.mp3").isFile)
        assertEquals(new, Store.manifest(new)!!.getString("id"))
        assertEquals("r-1", Store.knownActiveRecord(new))
        assertNull(Store.knownActiveRecord(old))
        assertTrue(JSONObject(File(root, "prints.json").readText()).has(new))
        assertEquals(listOf(new), Store.computerBooks())
    }

    @Test
    fun an_escaping_id_or_a_copy_already_under_the_new_id_changes_nothing() {
        Store.rekey(old, "../x")
        Store.rekey(old, "")
        File(root, "books/$new").mkdirs()
        File(root, "books/$new/book.json").writeText(JSONObject().put("id", new).toString())

        Store.rekey(old, new)

        assertTrue(File(root, "books/$old/chapters/001.mp3").isFile)
        assertEquals("r-1", Store.knownActiveRecord(old))
    }

    @Test
    fun a_streamed_book_moves_too_and_books_of_other_devices_stay_out_of_it() {
        val streamed = "QzpcU3RyZWFt"
        File(root, "books/$streamed").mkdirs()
        File(root, "books/$streamed/stream.json").writeText(JSONObject().put("id", streamed).toString())
        File(root, "books/pKEY_b2").mkdirs()
        File(root, "books/pKEY_b2/book.json").writeText(JSONObject().put("id", "pKEY_b2").put("source", "KEY").toString())

        assertEquals(setOf(old, streamed), Store.computerBooks().toSet())
        Store.rekey(streamed, "aaaaaaaaaaaaaaaaaaaaaaaa")

        assertEquals("aaaaaaaaaaaaaaaaaaaaaaaa", Store.streamManifest("aaaaaaaaaaaaaaaaaaaaaaaa")!!.getString("id"))
        assertNull(Store.streamManifest(streamed))
    }
}
