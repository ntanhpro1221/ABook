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
}
