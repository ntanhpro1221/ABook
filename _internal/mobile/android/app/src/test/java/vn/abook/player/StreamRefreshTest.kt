package vn.abook.player

import java.io.File
import java.nio.file.Files
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test

class StreamRefreshTest {
    @Test fun the_library_summary_does_not_need_the_full_cover_dimensions_or_filename() {
        val cached = JSONObject("""{"title":"Sách","chaptersAvailable":2,"cover":{"version":2,"color":"#112233","width":96,"height":128,"file":"cover.jpg"}}""")
        val summary = JSONObject("""{"title":"Sách","chaptersAvailable":2,"cover":{"version":2,"color":"#112233"}}""")
        assertFalse(StreamRefresh.stale(cached, summary))
        summary.getJSONObject("cover").put("version", 3)
        assertTrue(StreamRefresh.stale(cached, summary))
    }

    @Test fun a_cover_change_refreshes_a_peer_even_when_its_title_and_chapters_stay_the_same() {
        val cases = JSONArray(File("../../../tests/fixtures/listening_records/stream_covers.json").readText())
        for (i in 0 until cases.length()) {
            val case = cases.getJSONObject(i)
            val old = JSONObject().put("title", "Sách").put("chaptersAvailable", 2).put("cover", case.get("old"))
            val fresh = JSONObject(old.toString()).put("cover", case.get("new"))
            assertEquals(case.getString("name"), case.getBoolean("fetch"), StreamRefresh.coverNeeded(old, fresh, case.getBoolean("exists")))
            if (case.getString("name") == "cover_only_changed" || case.getString("name") == "cover_removed") {
                assertTrue(case.getString("name"), StreamRefresh.stale(old, fresh))
            }
        }
    }

    @Test fun changing_a_cached_cover_removes_old_bytes_so_a_failed_fetch_will_be_retried() {
        val folder = Files.createTempDirectory("abook-stream-cover").toFile()
        val cover = File(folder, "cover.jpg").apply { writeText("old") }
        val edited = File(folder, "edits/cover.jpg").apply { parentFile.mkdirs(); writeText("edited") }
        val old = JSONObject("""{"cover":{"version":1}}""")
        val fresh = JSONObject("""{"cover":{"version":2}}""")
        StreamRefresh.invalidateCover(folder, old, fresh)
        assertFalse(cover.exists())
        assertEquals("edited", edited.readText())
        // Manifest mới đã cất, nhưng lần tải ảnh thất bại: lần mở sau vẫn cần tải.
        assertTrue(StreamRefresh.coverNeeded(fresh, fresh, cover.isFile))
        cover.writeText("new")
        StreamRefresh.invalidateCover(folder, fresh, fresh)
        assertEquals("new", cover.readText())
        assertFalse(StreamRefresh.coverNeeded(fresh, fresh, cover.isFile))
    }

    private fun pack(version: String, words: String?, vararg chapters: Pair<Int, String>): JSONObject {
        val list = JSONArray()
        for ((id, sha) in chapters) list.put(JSONObject().put("id", id).put("sha256", sha).put("script", "scripts/$id.json"))
        return JSONObject().put("version", version).put("chapters", list).apply { if (words != null) put("wordsVersion", words) }
    }

    private fun scriptsFolder(vararg ids: Int): File {
        val folder = Files.createTempDirectory("abook-stream-scripts").toFile()
        for (id in ids) File(folder, "scripts/$id.json").apply { parentFile.mkdirs(); writeText("chu $id") }
        return folder
    }

    @Test fun a_new_chapter_keeps_the_scripts_of_the_chapters_already_heard() {
        val folder = scriptsFolder(1, 2, 3)
        val old = pack("v1", null, 1 to "a", 2 to "b", 3 to "c")
        val fresh = pack("v2", null, 1 to "a", 2 to "b", 3 to "c", 4 to "d")
        StreamRefresh.invalidateScripts(folder, old, fresh)
        for (id in 1..3) assertEquals("chu $id", File(folder, "scripts/$id.json").readText())
    }

    @Test fun only_the_re_recorded_or_removed_chapter_loses_its_script() {
        val folder = scriptsFolder(1, 2, 3)
        val old = pack("v1", null, 1 to "a", 2 to "b", 3 to "c")
        val fresh = pack("v2", null, 1 to "a", 2 to "B", 4 to "d")
        StreamRefresh.invalidateScripts(folder, old, fresh)
        assertTrue(File(folder, "scripts/1.json").isFile)
        assertFalse(File(folder, "scripts/2.json").exists())
        assertFalse(File(folder, "scripts/3.json").exists())
    }

    @Test fun a_new_word_alignment_drops_every_script_and_a_first_manifest_drops_nothing() {
        val folder = scriptsFolder(1, 2)
        StreamRefresh.invalidateScripts(folder, pack("v1", "w1", 1 to "a", 2 to "b"), pack("v2", "w2", 1 to "a", 2 to "b"))
        assertFalse(File(folder, "scripts").exists())
        val kept = scriptsFolder(1)
        StreamRefresh.invalidateScripts(kept, null, pack("v1", null, 1 to "a"))
        assertTrue(File(kept, "scripts/1.json").isFile)
    }

    @Test fun the_stored_cast_is_replaced_not_deleted_and_a_failed_fetch_is_retried() {
        val folder = Files.createTempDirectory("abook-stream-cast").toFile()
        val v1 = JSONObject().put("version", "v1")
        val v2 = JSONObject().put("version", "v2")
        assertTrue(StreamRefresh.castNeeded(folder, v1))
        File(folder, "cast.json").writeText("cu")
        StreamRefresh.castFetched(folder, v1)
        assertFalse(StreamRefresh.castNeeded(folder, v1))
        // Gói đổi: bản cũ còn nguyên cho tới khi tải được bản mới; chưa tải được thì lần mở sau vẫn cần tải.
        assertTrue(StreamRefresh.castNeeded(folder, v2))
        assertEquals("cu", File(folder, "cast.json").readText())
        File(folder, "cast.json").writeText("moi")
        StreamRefresh.castFetched(folder, v2)
        assertFalse(StreamRefresh.castNeeded(folder, v2))
    }
}
