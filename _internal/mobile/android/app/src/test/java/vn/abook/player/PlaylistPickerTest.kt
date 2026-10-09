package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Máy tự chọn danh sách phát cho "Nghe ngay" (Playlists.pick & co) phải ra ĐÚNG mã và điểm như bản Python (webui/music_playlist.py) trên bộ ví dụ
 * dùng chung tests/fixtures/playlist_picker/cases.json (sinh bằng `python -m tests.playlist_picker_fixtures` từ bản tham chiếu LLM_Train/music/
 * listen_genre): chọn từ chữ từng thể loại, tên không dấu, chương phụ bị bỏ, mốc 6.000 ký tự, hoà theo `order`, dưới `min_score` về mặc định; và
 * luật nào được dùng - của mục lục khi hợp lệ, không thì bản đóng kèm (cùng file abook/webui/assets/playlist_picker.json với máy tính).
 */
class PlaylistPickerTest {
    private val shared: JSONObject by lazy {
        val file = File("../../../tests/fixtures/playlist_picker/cases.json")
        assertTrue("Không thấy bộ ví dụ dùng chung: ${file.absoluteFile} (chạy test từ mobile/android/app)", file.isFile)
        JSONObject(file.readText(Charsets.UTF_8))
    }
    private val bundled: JSONObject by lazy {
        val file = File("../../../abook/webui/assets/playlist_picker.json")
        assertTrue("Không thấy luật đóng kèm: ${file.absoluteFile}", file.isFile)
        JSONObject(file.readText(Charsets.UTF_8))
    }

    private fun chapters(item: JSONObject): Sequence<String> = (0 until item.getJSONArray("chapters").length()).asSequence().map { item.getJSONArray("chapters").getString(it) }

    @Test
    fun the_bundled_picker_is_the_reference_lexicon() {
        assertTrue(StrictJson.equal(shared.getJSONObject("picker"), bundled))
        assertTrue(Playlists.validPicker(bundled))
    }

    @Test
    fun every_shared_case_gives_the_same_code_and_scores_as_python() {
        val cases = shared.getJSONArray("cases")
        assertTrue(cases.length() >= 12)
        for (index in 0 until cases.length()) {
            val item = cases.getJSONObject(index)
            val name = item.getString("name")
            val picker = if (item.has("picker")) item.opt("picker") as? JSONObject else shared.getJSONObject("picker")
            val expected = if (item.isNull("expect")) null else item.getString("expect")
            assertEquals(name, expected, Playlists.pick(picker, item.getString("title"), chapters(item)))
            val scores = Playlists.pickScores(picker, item.getString("title"), chapters(item))
            if (item.isNull("scores")) {
                assertNull(name, scores)
            } else {
                val want = item.getJSONObject("scores")
                assertEquals(name, want.keys().asSequence().toSet(), scores!!.keys)
                for (code in want.keys()) assertEquals("$name / $code", want.getDouble(code), scores.getValue(code), 1e-9)
            }
        }
    }

    @Test
    fun the_manifest_picker_is_used_only_when_valid_else_the_bundled_one() {
        val cases = shared.getJSONArray("selection")
        assertTrue(cases.length() >= 10)
        for (index in 0 until cases.length()) {
            val item = cases.getJSONObject(index)
            val name = item.getString("name")
            val manifest = item.opt("manifest") as? JSONObject
            val (picker, source) = Playlists.usablePicker(manifest, bundled)
            assertEquals(name, item.getString("source"), source)
            assertNotNull(name, picker)
            assertTrue(name, StrictJson.equal(if (source == "manifest") manifest!!.getJSONObject("playlistPicker") else bundled, picker))
            assertEquals(name, item.getString("expect"), Playlists.pick(picker, item.getString("title"), chapters(item)))
        }
        // không có cả hai: không tự chọn
        assertEquals(null to "none", Playlists.usablePicker(null, null))
    }

    @Test
    fun the_picker_reads_chapters_lazily_and_stops_once_it_has_enough_text() {
        var read = 0
        val chapters = (0 until 10).asSequence().map { read++; "Một câu tự đặt, chẳng có từ khoá nào cả. ".repeat(60) }
        Playlists.pick(bundled, "Sách thử", chapters)
        assertTrue("đã đọc $read chương", read < 10)
    }

    @Test
    fun a_text_book_is_picked_from_its_own_text_and_the_result_is_cached_per_book_picker_and_version() {
        val root = BookEditsFixtures.tempDir("abook-pick")
        val dir = File(root, "pick-text-book").apply { mkdirs() }
        File(dir, "texts").mkdirs()
        val case = shared.getJSONArray("cases").let { cases -> (0 until cases.length()).map { cases.getJSONObject(it) }.first { it.getString("name") == "horror_from_the_text" } }
        val text = case.getJSONArray("chapters").getString(0).replace("\n", "\r\n") // Python đọc \r\n thành \n: độ dài chương như nhau
        File(dir, "texts/1.txt").writeText(text)
        val chapter = JSONObject().put("id", 1).put("state", "text").put("text", "texts/1.txt")
        File(dir, "book.json").writeText(JSONObject().put("title", case.getString("title")).put("chapters", JSONArray().put(chapter)).toString())
        assertEquals("horror", Playlists.autoPlaylist(dir, null, bundled))
        // đệm theo (mã sách, nguồn luật, version): sửa chữ sau đó không đổi kết quả của cùng luật, đổi sang luật khác thì chọn lại
        File(dir, "texts/1.txt").writeText("")
        assertEquals("horror", Playlists.autoPlaylist(dir, null, bundled))
        val newer = JSONObject(bundled.toString()).put("version", 99)
        assertEquals("fantasy_adventure", Playlists.autoPlaylist(dir, null, newer))
        // sách có chương audio, hay không có chương: không tự chọn
        File(dir, "book.json").writeText(JSONObject().put("title", "x").put("chapters", JSONArray().put(JSONObject().put("id", 1).put("file", "chapters/1.mp3"))).toString())
        assertNull(Playlists.autoPlaylist(File(root, "khac").apply { mkdirs(); File(this, "book.json").writeText(File(dir, "book.json").readText()) }, null, bundled))
    }

    @Test
    fun turning_off_the_machines_pick_in_settings_leaves_a_book_with_no_choice_without_music() {
        val dir = File(BookEditsFixtures.tempDir("abook-pick-off"), "pick-off-book").apply { mkdirs() }
        File(dir, "texts").mkdirs()
        File(dir, "texts/1.txt").writeText("Một câu tự đặt, chẳng có từ khoá nào cả. ".repeat(60))
        val chapter = JSONObject().put("id", 1).put("state", "text").put("text", "texts/1.txt")
        File(dir, "book.json").writeText(JSONObject().put("title", "Sách thử").put("chapters", JSONArray().put(chapter)).toString())
        try {
            Playlists.autoEnabled = false
            assertNull(Playlists.autoPlaylist(dir, null, bundled))
        } finally {
            Playlists.autoEnabled = true
        }
        assertTrue(Playlists.autoPlaylist(dir, null, bundled) != null)
    }

    /** Thời gian `pick` trên ca dài nhất của bộ ví dụ - đo trên JVM (máy tính), KHÔNG phải điện thoại; số trên máy Android: PlaylistPickTimingTest. */
    @Test
    fun pick_time_on_the_longest_case_on_the_jvm() {
        val cases = shared.getJSONArray("cases")
        val longest = (0 until cases.length()).map { cases.getJSONObject(it) }.filter { !it.has("picker") }
            .maxByOrNull { item -> chapters(item).sumOf { it.length } }!!
        repeat(20) { Playlists.pick(bundled, longest.getString("title"), chapters(longest)) } // khởi động JIT
        val started = System.nanoTime()
        repeat(200) { Playlists.pick(bundled, longest.getString("title"), chapters(longest)) }
        val millis = (System.nanoTime() - started) / 1e6 / 200
        println("PICK_JVM ca=${longest.getString("name")} ${"%.2f".format(millis)} ms mỗi lần (200 lần)")
        assertTrue("pick chậm: $millis ms", millis < 500)
    }
}
