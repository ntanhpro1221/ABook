package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

class BookEditsCrashTest {
    private fun folder(): File = BookEditsFixtures.tempDir("edits-crash").also {
        File(it, "book.json").writeText(BookEditsFixtures.obj("base/book.json").toString())
        File(it, "edits").mkdirs()
        File(it, BookEdits.EDITS_COVER).writeBytes(byteArrayOf(1, 2, 3))
        BookEdits.save(it, JSONObject().put("version", 1).put("title", "Tên mới")
            .put("cover", JSONObject().put("color", "#123456").put("width", 10).put("height", 10).put("version", 1)))
        File(it, BookEdits.EDITS_FILE + ".part").mkdirs() // lỗi ghi ngay trước commit JSON
    }

    @Test
    fun remove_cover_keeps_the_asset_when_the_json_commit_fails() {
        val folder = folder()
        assertTrue(runCatching { BookEdits.removeCover(folder) }.isFailure)
        assertTrue(BookEdits.load(folder).opt("cover") is JSONObject)
        assertTrue("JSON cũ còn trỏ tới bìa", File(folder, BookEdits.EDITS_COVER).isFile)
    }

    @Test
    fun remove_cover_drops_the_asset_once_the_json_is_committed() {
        val folder = folder()
        File(folder, BookEdits.EDITS_FILE + ".part").deleteRecursively()
        BookEdits.removeCover(folder)
        assertTrue(BookEdits.load(folder).isNull("cover"))
        assertTrue("không để ảnh bìa mồ côi", !File(folder, BookEdits.EDITS_COVER).exists())
    }

    @Test
    fun subtract_keeps_the_asset_when_the_json_commit_fails() {
        val folder = folder()
        val sent = JSONObject().put("version", 1).put("cover", BookEdits.load(folder).getJSONObject("cover"))
        val cover = File(folder, BookEdits.EDITS_COVER).readBytes()
        assertTrue(runCatching { BookEdits.subtract(folder, sent, cover) }.isFailure)
        assertTrue("JSON cũ còn trỏ tới bìa", File(folder, BookEdits.EDITS_COVER).isFile)
    }
}
