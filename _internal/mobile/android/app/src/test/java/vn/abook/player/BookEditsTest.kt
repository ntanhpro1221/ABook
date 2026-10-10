package vn.abook.player

import java.io.File
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

/**
 * Lớp sửa của người nghe (BookEdits) so với bản Python (webui/book_edits.py) qua bộ ví dụ dùng chung
 * tests/fixtures/book_edits/: mỗi ca `edits/<ca>.json` áp lên `base/` phải ra đúng `expected/<ca>.json`, mỗi file `invalid/` bị
 * từ chối, mỗi ca `merge/` hợp ra đúng kết quả, và `MusicGain` tính lại đúng `gainDb` mà người làm sách đã ghi.
 */
class BookEditsTest {
    private val base: JSONObject by lazy { BookEditsFixtures.obj("base/book.json") }
    private val cast: JSONObject by lazy { BookEditsFixtures.obj("base/cast.json") }

    private fun assertJson(what: String, expected: Any?, actual: Any?) {
        if (!StrictJson.equal(expected, actual)) {
            fail("$what khác bộ ví dụ.\n--- mong đợi ---\n${StrictJson.dumps(expected)}\n--- thực tế ---\n${StrictJson.dumps(actual)}")
        }
    }

    private fun refusal(block: () -> Unit): String {
        try {
            block()
        } catch (error: BookEdits.EditsError) {
            return error.message.orEmpty()
        }
        fail("lẽ ra bị từ chối")
        return ""
    }

    private fun withoutPackage(book: JSONObject): JSONObject =
        (BookEdits.deepCopy(book) as JSONObject).also { it.remove("package") }

    @Test
    fun the_shared_fixtures_are_all_there() {
        assertTrue(BookEditsFixtures.cases("edits").size >= 10)
        assertTrue(BookEditsFixtures.cases("invalid").size >= 60)
        assertTrue(BookEditsFixtures.cases("merge").size >= 7)
        assertTrue(BookEditsFixtures.cases("contract").size >= 12)
    }

    @Test
    fun every_valid_edits_file_parses_and_dumps_back_to_the_same_bytes() {
        for (name in BookEditsFixtures.cases("edits")) {
            val bytes = BookEditsFixtures.bytes("edits/$name.json")
            val edits = BookEdits.parse(bytes)
            assertEquals("$name: dump(parse(file)) giữ nguyên từng byte", String(bytes, Charsets.UTF_8), String(BookEdits.dump(edits), Charsets.UTF_8))
            assertJson("$name: parse(dump)", edits, BookEdits.parse(BookEdits.dump(edits)))
            assertTrue("$name: LF, có xuống dòng cuối", String(bytes, Charsets.UTF_8).endsWith("}\n") && !String(bytes, Charsets.UTF_8).contains('\r'))
        }
    }

    @Test
    fun every_edits_case_applied_to_the_base_book_is_what_python_produced() {
        for (name in BookEditsFixtures.cases("edits")) {
            val edits = BookEdits.parse(BookEditsFixtures.bytes("edits/$name.json"))
            val expected = BookEditsFixtures.obj("expected/$name.json")
            assertJson("$name: book.json", expected.getJSONObject("manifest"), withoutPackage(BookEdits.applyManifest(base, edits)))
            assertJson("$name: cast.json", expected.getJSONObject("cast"), BookEdits.applyCast(cast, edits, base))
            val chapters = base.getJSONArray("chapters")
            for (index in 0 until chapters.length()) {
                val chapter = chapters.getJSONObject(index)
                val script = BookEditsFixtures.obj("base/${chapter.getString("script")}")
                assertJson("$name: ${chapter.getString("script")}", expected.getJSONObject("scripts").getJSONObject(chapter.get("id").toString()),
                    BookEdits.applyScript(script, cast, edits, chapter))
            }
        }
    }

    @Test
    fun the_word_timings_of_a_line_pass_through_a_rename_untouched() {
        // `words` (mốc từng chữ, webui/word_timing.py) nằm trong từng câu của scripts/<n>.json: đổi tên người nói không được làm rơi hay đổi chúng.
        val person = cast.getJSONArray("characters").getJSONObject(0)
        val edits = BookEdits.validate(StrictJson.parse("""{"format": "abook-edits", "version": 1, "characters": {"${person.getString("name")}": "Tên Mới"}}"""))
        val spoken = JSONArray("[[100, 400], [400, 900]]")
        val narrated = JSONArray("[[0, 250]]")
        val script = JSONObject().put("chapterId", 1).put("segments", JSONArray()
            .put(JSONObject().put("text", "một hai").put("speaker", person.getString("displayName")).put("words", spoken))
            .put(JSONObject().put("text", "ba").put("speaker", "").put("words", narrated))
            .put(JSONObject().put("text", "bốn").put("speaker", "")))
        val shown = BookEdits.applyScript(script, cast, edits, null).getJSONArray("segments")
        assertEquals("Tên Mới", shown.getJSONObject(0).getString("speaker"))
        assertJson("words của câu đổi tên", spoken, shown.getJSONObject(0).get("words"))
        assertJson("words của câu không đổi", narrated, shown.getJSONObject(1).get("words"))
        assertFalse("câu chưa căn vẫn không có words", shown.getJSONObject(2).has("words"))
    }

    @Test
    fun a_series_file_renames_its_parts_and_a_chapter_by_its_shared_id() {
        val series = BookEditsFixtures.obj("series/book.json")
        val edits = BookEdits.validate(StrictJson.parse("""{"format": "abook-edits", "version": 1, "title": "Tên khác",
            "chapters": {"200001": {"title": "Chương Một"}}}"""))
        assertJson("cả bộ", BookEditsFixtures.obj("expected/series_title_and_chapter.json").getJSONObject("manifest"),
            withoutPackage(BookEdits.applyManifest(series, edits)))
    }

    @Test
    fun every_invalid_file_is_refused_whole() {
        for (name in BookEditsFixtures.cases("invalid")) {
            val message = refusal { BookEdits.parse(BookEditsFixtures.bytes("invalid/$name.json")) }
            assertTrue("$name: có câu báo bằng tiếng Việt", message.isNotBlank())
        }
    }

    @Test
    fun refusals_say_the_same_thing_as_python() {
        fun said(json: String) = refusal { BookEdits.parse(json.toByteArray(Charsets.UTF_8)) }
        val head = """"format": "abook-edits", "version": 1"""
        assertEquals("Phần sửa của sách bị hỏng.", said("{"))
        assertEquals("Phần sửa của sách bị hỏng.", said("""{$head, "music": {"levelDb": NaN}}"""))
        assertEquals("Phần sửa của sách có mục lạ.", said("[]"))
        assertEquals("Phần sửa của sách có mục lạ.", said("""{$head, "pins": []}"""))
        assertEquals("Phần ý muốn chờ Studio trong phần sửa không hợp lệ hay quá dài.", said("""{$head, "wishes": []}"""))
        assertEquals("Phần ý muốn chờ Studio trong phần sửa không hợp lệ hay quá dài.", said("""{$head, "wishes": {"dreams": {}}}"""))
        assertEquals("Phần ý muốn chờ Studio trong phần sửa không hợp lệ hay quá dài.", said("""{$head, "wishes": {"retakes": {}}}"""))
        assertEquals("Một ý muốn thu lại câu trong phần sửa không hợp lệ.", said("""{$head, "wishes": {"retakes": {"c1_s1": {"requested_at": 1.5}}}}"""))
        assertEquals("Một ý muốn gộp tên trong phần sửa không hợp lệ.", said("""{$head, "wishes": {"aliases": [{"alias": "A", "person": "B"}]}}"""))
        assertEquals("Phần sửa của sách không đúng định dạng hay mới hơn app - hãy cập nhật app.", said("""{"format": "abook-edits", "version": 2}"""))
        assertEquals("Tên sách trong phần sửa không hợp lệ.", said("""{$head, "title": "Tên  sách"}"""))
        assertEquals("Tên sách trong phần sửa không hợp lệ.", said("""{$head, "title": "Tên\tsách"}"""))
        assertEquals("Tên hiện của một nhân vật trong phần sửa không hợp lệ.", said("""{$head, "characters": {"LUCIEN": ""}}"""))
        assertEquals("Phần đổi tên nhân vật không hợp lệ hay quá dài.", said("""{$head, "characters": ["LUCIEN"]}"""))
        assertEquals("Một mục đổi tên chương không hợp lệ.", said("""{$head, "chapters": {"x": {"title": "A"}}}"""))
        assertEquals("Tên một chương trong phần sửa không hợp lệ.", said("""{$head, "chapters": {"1": {"title": ""}}}"""))
        assertEquals("Mức nhạc nền trong phần sửa nằm ngoài khoảng cho phép.", said("""{$head, "music": {"levelDb": -3}}"""))
        assertEquals("Mức nhạc nền trong phần sửa nằm ngoài khoảng cho phép.", said("""{$head, "music": {"levelDb": "-20"}}"""))
        assertEquals("Phần sửa nhạc nền không hợp lệ.", said("""{$head, "music": {"enabled": 1}}"""))
        assertEquals("Danh sách đoạn nhạc im lặng trong phần sửa không hợp lệ.", said("""{$head, "music": {"silenced": ["1:0", "1:0"]}}"""))
        assertEquals("Ảnh bìa trong phần sửa không hợp lệ.", said("""{$head, "cover": {"color": "red", "width": 1, "height": 1, "version": 1}}"""))
        assertEquals("Ảnh bìa trong phần sửa không hợp lệ.", said("""{$head, "cover": {"color": "", "width": 1.0, "height": 1, "version": 1}}"""))
    }

    @Test
    fun refusals_about_pinned_tracks_say_the_same_thing_as_python() {
        val sha = "0123456789abcdef0123456789abcdef01234567"
        fun music(vararg fields: String) = "{\"format\": \"abook-edits\", \"version\": 1, \"music\": {${fields.joinToString(", ")}}}".toByteArray(Charsets.UTF_8)
        fun said(vararg fields: String) = refusal { BookEdits.parse(music(*fields)) }
        val pins = "\"pins\": {\"1:0\": \"local:$sha\"}"
        val tracks = "\"tracks\": {\"$sha\": {\"ext\": \"wav\", \"title\": \"Bài\", \"duration\": 1.5, \"lufs\": -20}}"
        fun entry(body: String) = "\"tracks\": {\"$sha\": {$body}}"
        assertEquals(1, BookEdits.count(BookEdits.parse(music(pins, tracks))))
        val badPins = "Danh sách đoạn nhạc đã đổi bài trong phần sửa không hợp lệ."
        assertEquals(badPins, said("\"pins\": {\"x\": \"local:$sha\"}", tracks))
        assertEquals(badPins, said("\"pins\": {\"1:0\": \"https://x/y.mp3\"}", tracks))
        assertEquals(badPins, said("\"pins\": [\"local:$sha\"]", tracks))
        val mismatch = "Nhạc đã chọn trong phần sửa không khớp với các đoạn đổi bài."
        assertEquals(mismatch, said(pins))
        assertEquals(mismatch, said(tracks))
        assertEquals(mismatch, said(pins, "\"tracks\": {\"$sha\": {\"ext\": \"wav\"}, \"${"1".repeat(40)}\": {\"ext\": \"wav\"}}"))
        val badTrack = "Thông tin một bài nhạc trong phần sửa không hợp lệ."
        assertEquals(badTrack, said(pins, entry("\"ext\": \"exe\"")))
        assertEquals(badTrack, said(pins, entry("\"ext\": \"wav\", \"path\": \"/x\"")))
        assertEquals(badTrack, said(pins, entry("\"ext\": \"wav\", \"title\": \" Bài\"")))
        assertEquals(badTrack, said(pins, entry("\"ext\": \"wav\", \"title\": \"\"")))
        assertEquals(badTrack, said(pins, entry("\"ext\": \"wav\", \"duration\": 0")))
        assertEquals(badTrack, said(pins, entry("\"ext\": \"wav\", \"lufs\": 21")))
        assertEquals(badTrack, said(pins, entry("\"ext\": \"wav\", \"lufs\": \"-23\"")))
        assertEquals("Phần sửa nhạc nền không hợp lệ.", said("\"fade\": 2"))
    }

    @Test
    fun a_boolean_is_not_a_number_and_a_title_is_cut_at_160_code_points() {
        val head = """"format": "abook-edits", "version": 1"""
        refusal { BookEdits.parse("""{$head, "version": true}""".toByteArray()) }
        refusal { BookEdits.parse("""{$head, "music": {"levelDb": true}}""".toByteArray()) }
        refusal { BookEdits.parse("""{$head, "cover": {"color": "", "width": true, "height": 1, "version": 1}}""".toByteArray()) }
        BookEdits.parse("""{$head, "title": "${"a".repeat(160)}"}""".toByteArray())
        refusal { BookEdits.parse("""{$head, "title": "${"a".repeat(161)}"}""".toByteArray()) }
        // 160 điểm mã nhưng 320 đơn vị UTF-16: đếm theo điểm mã như Python
        BookEdits.parse("""{$head, "title": "${"😀".repeat(160)}"}""".toByteArray())
        refusal { BookEdits.parse("""{$head, "title": "${"😀".repeat(161)}"}""".toByteArray()) }
        BookEdits.parse("""{$head, "characters": {"A": "${"b".repeat(80)}"}}""".toByteArray())
        refusal { BookEdits.parse("""{$head, "characters": {"A": "${"b".repeat(81)}"}}""".toByteArray()) }
    }

    @Test
    fun caps_on_size_and_counts_refuse_the_whole_file() {
        val head = """"format": "abook-edits", "version": 1"""
        val big = """{$head, "title": "${"a".repeat(1024 * 1024)}"}""".toByteArray()
        assertEquals("Phần sửa của sách quá lớn.", refusal { BookEdits.parse(big) })
        fun characters(count: Int) = """{$head, "characters": {${(0 until count).joinToString(",") { "\"N$it\": \"x\"" }}}}""".toByteArray()
        BookEdits.parse(characters(2000))
        assertEquals("Phần đổi tên nhân vật không hợp lệ hay quá dài.", refusal { BookEdits.parse(characters(2001)) })
        fun chapters(count: Int) = """{$head, "chapters": {${(1..count).joinToString(",") { "\"$it\": {\"title\": \"x\"}" }}}}""".toByteArray()
        BookEdits.parse(chapters(5000))
        assertEquals("Phần đổi tên chương không hợp lệ hay quá dài.", refusal { BookEdits.parse(chapters(5001)) })
        fun cues(count: Int) = """{$head, "music": {"silenced": [${(1..count).joinToString(",") { "\"1:$it\"" }}]}}""".toByteArray()
        BookEdits.parse(cues(5000))
        assertEquals("Danh sách đoạn nhạc im lặng trong phần sửa không hợp lệ.", refusal { BookEdits.parse(cues(5001)) })
    }

    @Test
    fun too_many_wishes_refuse_the_whole_file() {
        val head = """"format": "abook-edits", "version": 1"""
        val sha = "a".repeat(64)
        fun retakes(count: Int) = """{$head, "wishes": {"retakes": {${(0 until count).joinToString(",") { "\"c1_s$it\": {\"requested_at\": 1.5, \"text_sha256\": \"$sha\"}" }}}}}""".toByteArray()
        BookEdits.parse(retakes(5000))
        assertEquals("Phần ý muốn chờ Studio trong phần sửa không hợp lệ hay quá dài.", refusal { BookEdits.parse(retakes(5001)) })
    }

    @Test
    fun clean_text_matches_the_server_rules() {
        assertEquals("Tên mới", BookEdits.cleanText("  Tên \t mới \n", 160))
        assertEquals("a b", BookEdits.cleanText("a\u0007b", 160))
        assertEquals("a b", BookEdits.cleanText("a\u00a0\u00a0b", 160)) // dấu cách cứng cũng là khoảng trắng
        assertEquals("Việt", BookEdits.cleanText("Vie\u0302\u0323t", 160)) // NFC: ê + dấu nặng ghép thành ệ
        assertEquals("abc", BookEdits.cleanText("abcdef", 3))
        assertEquals("ab", BookEdits.cleanText("ab cdef", 3)) // cắt rồi bỏ dấu cách thừa ở cuối
        assertEquals("😀😀", BookEdits.cleanText("😀😀😀", 2))
        assertEquals("", BookEdits.cleanText(null, 160))
        assertEquals("5", BookEdits.cleanText(5, 160))
        assertEquals("", BookEdits.cleanText(JSONObject.NULL, 160))
    }

    @Test
    fun every_merge_case_gives_what_python_gave() {
        for (name in BookEditsFixtures.cases("merge")) {
            val case = BookEditsFixtures.obj("merge/$name.json")
            val local = BookEdits.validate(case.getJSONObject("local"))
            val incoming = BookEdits.validate(case.getJSONObject("incoming"))
            val (merged, report) = BookEdits.merge(local, incoming)
            assertJson("$name: kết quả hợp", case.getJSONObject("merged"), merged)
            assertJson("$name: báo cáo", case.getJSONObject("report"), report)
        }
    }

    @Test
    fun every_sent_case_gives_what_python_gave() {
        assertTrue(BookEditsFixtures.cases("sent").size >= 9)
        for (name in BookEditsFixtures.cases("sent")) {
            val case = BookEditsFixtures.obj("sent/$name.json")
            val previous = case.getJSONObject("previous")
            val current = BookEdits.validate(case.getJSONObject("current"))
            val sent = case.optJSONObject("sent")?.let { BookEdits.validate(it) }
            val folder = BookEditsFixtures.tempDir("abook-sent")
            BookEdits.save(folder, current)
            // Cái đã gửi rồi người nghe bỏ đi: gói gửi mang nó để máy kia gỡ theo, sổ mới không còn nhắc tới nó.
            val removed = if (sent != null) BookEdits.removedMarks(sent, previous) else JSONObject()
            val marks = if (sent != null) BookEdits.sentMarks(sent, BookEdits.forgetMarks(previous, removed)) else previous
            if (sent != null) BookEdits.subtract(folder, sent, null)
            val left = BookEdits.load(folder)
            val rest = BookEdits.unmarked(left, marks)
            val waiting = BookEdits.removedMarks(left, marks)
            assertJson("$name: cái gói gửi đi bảo gỡ", case.optJSONObject("removed") ?: JSONObject(), removed)
            assertJson("$name: sổ đã gửi", case.getJSONObject("marks"), marks)
            assertJson("$name: lớp sửa còn lại", case.getJSONObject("left"), left)
            assertJson("$name: phần chưa gửi", case.getJSONObject("unmarked"), rest)
            assertJson("$name: còn phải báo gỡ", case.optJSONObject("removeLater") ?: JSONObject(), waiting)
            assertEquals("$name: số chưa gửi", case.getInt("pending"), BookEdits.count(rest) + BookEdits.countRemoved(waiting))
        }
    }

    @Test
    fun the_gain_formula_reproduces_what_the_book_maker_wrote() {
        val music = base.getJSONObject("music")
        val tracks = music.getJSONObject("tracks")
        val level = music.getDouble("levelDb")
        assertEquals(-18.0, level, 0.0)
        val cues = music.getJSONObject("chapters").getJSONArray("1")
        val wanted = listOf(-7.39, -28.19)
        for (index in 0 until cues.length()) {
            val cue = cues.getJSONObject(index)
            val track = tracks.getJSONObject(cue.getString("track"))
            assertEquals(cue.getDouble("gainDb"), MusicGain.cueGainDb(level, track.getDouble("lufs"), track.getDouble("speechBand")), 0.0)
            assertEquals(wanted[index], cue.getDouble("gainDb"), 0.0)
        }
        // Thiếu số đo: trung vị danh mục, không bù; không bao giờ khuếch đại (> 0)
        assertEquals(-16.9897 - 20.0 + 16.6, MusicGain.cueGainDb(-20.0, null, null), 0.006)
        assertEquals(0.0, MusicGain.cueGainDb(-6.0, -40.0, 0.3), 0.0)
    }

    @Test
    fun a_new_level_recomputes_every_cue_with_the_same_formula() {
        val edits = BookEdits.parse(BookEditsFixtures.bytes("edits/music_level_and_silence.json"))
        val shown = BookEdits.applyManifest(base, edits).getJSONObject("music")
        assertEquals(-24.0, shown.getDouble("levelDb"), 0.0)
        val cue = shown.getJSONObject("chapters").getJSONArray("1").getJSONObject(0)
        assertEquals(MusicGain.cueGainDb(-24.0, -26.0, 0.1), cue.getDouble("gainDb"), 0.0)
        assertEquals("mốc 1:60000 đã cho im lặng", 1, shown.getJSONObject("chapters").getJSONArray("1").length())
        // lớp sách không bị đụng tới
        assertEquals(-7.39, base.getJSONObject("music").getJSONObject("chapters").getJSONArray("1").getJSONObject(0).getDouble("gainDb"), 0.0)
    }

    @Test
    fun cue_keys_round_half_to_even_like_python() {
        assertEquals("1:60000", BookEdits.cueKey(1, 60.0))
        assertEquals("1:0", BookEdits.cueKey("1", 0.0))
        assertEquals("7:62", BookEdits.cueKey(7, 0.0625)) // 62,5 ms -> 62 (nửa-chẵn), không phải 63
        assertEquals("7:188", BookEdits.cueKey(7, 0.1875)) // 187,5 ms -> 188
    }

    @Test
    fun part_titles_follow_the_new_title_without_stacking_suffixes() {
        assertEquals("Tên", BookEdits.baseTitle("Tên · Phần 2"))
        assertEquals("Tên", BookEdits.baseTitle("Tên (phần 2)"))
        assertEquals("Tên", BookEdits.baseTitle("Tên - PHẦN 12"))
        assertEquals("Tên · Tập 1", BookEdits.baseTitle("Tên · Tập 1"))
        assertEquals("· Phần 3", BookEdits.baseTitle("· Phần 3")) // bỏ hậu tố mà không còn gì: giữ nguyên tên
        assertEquals("Tên · Phần 3", BookEdits.continuedTitle("Tên · Phần 2", 3))
    }

    @Test
    fun saving_writes_stable_bytes_and_an_empty_edit_removes_both_files() {
        val folder = BookEditsFixtures.tempDir("abook-edits-save")
        val edits = BookEdits.empty().put("title", "Của tôi").put("cover", JSONObject().put("color", "#112233").put("width", 1L)
            .put("height", 2L).put("version", 3L))
        BookEdits.save(folder, edits)
        File(folder, BookEdits.EDITS_COVER).apply { parentFile?.mkdirs() }.writeBytes(byteArrayOf(1))
        assertEquals(2, BookEdits.count(BookEdits.load(folder)))
        BookEdits.save(folder, BookEdits.empty())
        assertFalse(File(folder, BookEdits.EDITS_FILE).exists())
        assertFalse("bìa sửa đi cùng", File(folder, BookEdits.EDITS_COVER).exists())
        // bìa không còn là đối tượng thì file bìa sửa bị xoá
        File(folder, BookEdits.EDITS_COVER).apply { parentFile?.mkdirs() }.writeBytes(byteArrayOf(1))
        BookEdits.save(folder, BookEdits.empty().put("title", "x"))
        assertFalse(File(folder, BookEdits.EDITS_COVER).exists())
    }

    @Test
    fun the_author_is_set_cleared_and_restored_like_python() {
        val folder = BookEditsFixtures.copyBase(BookEditsFixtures.tempDir("abook-edits-author"))
        assertEquals("Tên người", BookEdits.setAuthor(folder, "  Tên \t người  "))
        assertEquals("Tên người", BookEdits.applyManifest(BookEdits.rawBook(folder), BookEdits.load(folder)).getString("author"))
        assertEquals(1, BookEdits.count(BookEdits.load(folder)))
        // Sách vốn không có tác giả: bỏ tên là hết thay đổi.
        assertEquals("", BookEdits.setAuthor(folder, "   "))
        assertFalse(File(folder, BookEdits.EDITS_FILE).exists())
        // Sách vốn có tác giả: bỏ tên là một thay đổi thật (ghi "" chứ không bỏ khoá); đặt lại đúng tên gốc thì hết.
        val book = BookEdits.rawBook(folder).put("author", "Người làm sách")
        File(folder, "book.json").writeText(book.toString())
        assertEquals("", BookEdits.setAuthor(folder, ""))
        assertEquals("", BookEdits.load(folder).getString("author"))
        assertFalse(BookEdits.applyManifest(BookEdits.rawBook(folder), BookEdits.load(folder)).has("author"))
        assertEquals("Người làm sách", BookEdits.setAuthor(folder, "Người làm sách"))
        assertFalse(File(folder, BookEdits.EDITS_FILE).exists())
    }

    @Test
    fun a_missing_or_broken_edits_file_is_just_no_edits() {
        val folder = BookEditsFixtures.tempDir("abook-edits-load")
        assertTrue(BookEdits.isEmpty(BookEdits.load(folder)))
        File(folder, BookEdits.EDITS_FILE).writeText("không phải JSON")
        assertTrue(BookEdits.isEmpty(BookEdits.load(folder)))
    }

    @Test
    fun the_strict_reader_behaves_like_python_json_loads() {
        assertTrue(StrictJson.parse("1") is Long)
        assertTrue(StrictJson.parse("1.0") is Double)
        assertTrue("số lớn không tràn", StrictJson.parse("123456789012345678901234567890") is java.math.BigInteger)
        assertTrue("1e999 là float vô hạn, không phải số hợp lệ", StrictJson.parse("1e999") is StrictJson.NonFinite)
        assertEquals("b", (StrictJson.parse("""{"a": 1, "a": "b"}""") as JSONObject).getString("a")) // khoá trùng: bản sau thắng
        for (bad in listOf("", "{", "[1,]", "{\"a\":1,}", "'a'", "NaN", "Infinity", "-Infinity", "01", "1.", ".5", "\"\u0001\"", "\"\\x\"",
            "{a: 1}", "[1] x", "\uFEFF{}", "// c\n{}", "tru")) {
            try {
                StrictJson.parse(bad)
                fail("lẽ ra là JSON hỏng: $bad")
            } catch (expected: StrictJson.ParseError) {
            }
        }
        assertEquals("€", StrictJson.parse("\"\\u20ac\""))
        assertEquals("😀", StrictJson.parse("\"\\ud83d\\ude00\""))
    }

    @Test
    fun the_writer_prints_python_style_json() {
        assertEquals("{\n \"a\": [\n  1,\n  2.0\n ],\n \"b\": {},\n \"c\": [],\n \"d\": null,\n \"e\": \"x\\\"y\\n\"\n}",
            StrictJson.dumps(linkedMapOf("a" to listOf(1, 2.0), "b" to emptyMap<String, Any>(), "c" to emptyList<Any>(), "d" to null, "e" to "x\"y\n")))
        assertEquals("20.0", StrictJson.pyFloat(20.0))
        assertEquals("-24.0", StrictJson.pyFloat(-24.0))
        assertEquals("1e-05", StrictJson.pyFloat(0.00001))
        assertEquals("0.0001", StrictJson.pyFloat(0.0001))
        assertEquals("1.5e+20", StrictJson.pyFloat(1.5e20))
        assertEquals("12345678.0", StrictJson.pyFloat(12345678.0))
        assertEquals("0.1", StrictJson.pyFloat(0.1))
    }
}
