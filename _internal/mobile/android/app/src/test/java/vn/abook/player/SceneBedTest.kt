package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * Nhạc nền theo cảnh trên điện thoại, phần quyết định và phần đặt lại mốc của [MusicBed]: khi nào một cuốn theo cảnh ([Playlists.sceneMode], bảng quyết định như
 * `_scene_mode` của server.py), mốc thô của máy thành mốc [MusicCues.Cue] mà trình phát chơi ([SceneBed]: gain từ số đo của bài, đoạn nghe được), và mốc đặt lại khi
 * đồng hồ đọc có giây mới / người nghe nhảy.
 */
class SceneBedTest {
    @Before
    fun loadMix() {
        MusicCues.mix = MusicMix.parse(File("../../../abook/webui/assets/music_mix.json").readText())
    }

    // ---- bảng quyết định ----------------------------------------------------------------------------------------------------------------------

    private fun chapter(text: Boolean, audio: Boolean = false): JSONObject {
        val item = JSONObject().put("id", 1)
        if (text) item.put("text", "texts/1.txt")
        if (audio) item.put("file", "audio/1.mp3")
        return item
    }

    private fun book(text: Boolean = true, audio: Boolean = false, music: Any? = null): JSONObject {
        val json = JSONObject().put("chapters", JSONArray().put(chapter(text, audio)))
        if (music != null) json.put("music", music)
        return json
    }

    private fun packaged() = JSONObject().put("tracks", JSONObject()).put("chapters", JSONObject())

    @Test
    fun a_text_book_with_no_music_of_its_own_follows_the_scenes_unless_the_listener_chose_something_else() {
        val text = book()
        // Chưa chọn gì ("Để máy chọn"): mặc định là theo cảnh khi "Tự chọn nhạc nền" còn bật, không nhạc khi tắt.
        assertTrue(Playlists.sceneMode(text, "", auto = true))
        assertFalse(Playlists.sceneMode(text, "", auto = false))
        // Đã chọn "Theo cảnh": theo cảnh dù công tắc tự chọn tắt (người nghe đã chọn tay).
        assertTrue(Playlists.sceneMode(text, Playlists.SCENE, auto = true))
        assertTrue(Playlists.sceneMode(text, Playlists.SCENE, auto = false))
        // Danh sách của danh mục, "Nhạc của tôi", tắt: luật cũ, không theo cảnh.
        for (choice in listOf("fantasy_adventure", Playlists.MINE, Playlists.OFF)) {
            assertFalse(choice, Playlists.sceneMode(text, choice, auto = true))
            assertFalse(choice, Playlists.sceneMode(text, choice, auto = false))
        }
    }

    @Test
    fun a_book_with_packaged_music_or_with_audio_never_follows_the_scenes() {
        for (choice in listOf("", Playlists.SCENE)) {
            assertFalse("nhạc của người làm sách thắng", Playlists.sceneMode(book(music = packaged()), choice, auto = true))
            assertFalse("sách có audio không phải sách chữ", Playlists.sceneMode(book(text = true, audio = true), choice, auto = true))
            assertFalse("sách audio", Playlists.sceneMode(book(text = false, audio = true), choice, auto = true))
            assertFalse("không chương nào", Playlists.sceneMode(JSONObject(), choice, auto = true))
        }
        // `music` rỗng / false trong book.json: như không có (BookEdits.truthy, như `book.get("music")` của Python).
        assertTrue(Playlists.sceneMode(book(music = JSONObject.NULL), "", auto = true))
        assertTrue(Playlists.sceneMode(book(music = false), "", auto = true))
    }

    // ---- mốc thô -> mốc của trình phát ---------------------------------------------------------------------------------------------------------

    private val a = "https://x/a.mp3"
    private val b = "https://x/b.mp3"
    private val c = "https://x/c.mp3"

    private fun raw() = listOf(
        SceneAnchor.Cue(0.0, 100.0, a, "1:0", firstSegment = 0),
        SceneAnchor.Cue(100.0, 170.0, b, "1:1", steps = listOf(MusicCues.Step(135.0, -3.0)), firstSegment = 2),
        SceneAnchor.Cue(170.0, 250.0, c, "1:1", sibling = true),
        SceneAnchor.Cue(250.0, 300.0, a, "1:2", tail = true, firstSegment = 4),
    )

    private fun info(lufs: Double, speechBand: Double, s95: Double? = null, audible: Pair<Double, Double>? = null): JSONObject =
        JSONObject().put("lufs", lufs).put("speechBand", speechBand).also { json ->
            s95?.let { json.put("s95", it) }
            audible?.let { json.put("audibleStart", it.first).put("audibleEnd", it.second) }
        }

    private fun arrival(levelDb: Double = -20.0, cues: List<SceneAnchor.Cue> = raw()) = SceneBed.Arrival(
        cues, 300.0, levelDb, mapOf(a to info(-14.0, 0.5, audible = 1.5 to 120.0), b to info(-18.0, 0.1, s95 = -20.0)),
    )

    private fun timing(vararg starts: Double, total: Double) = SceneAnchor.Timing(starts, total)

    @Test
    fun cues_become_player_cues_with_the_gain_of_the_catalogue_measurements() {
        val clock = timing(0.0, 5.0, 12.0, 20.0, 31.0, total = 40.0)
        val bed = SceneBed { clock }
        assertTrue(bed.arrive(arrival(), 0.0))
        assertEquals(listOf(a, b, c, a), bed.cues.map { it.track })
        assertEquals(listOf(0.0, 12.0, 20.87, 31.0), bed.cues.map { Math.round(it.start * 100) / 100.0 })
        assertEquals(40.0, bed.cues.last().end, 1e-9)
        assertEquals(MusicGain.cueGainDb(-20.0, -14.0, 0.5, null), bed.cues[0].gainDb!!, 0.0)
        assertEquals(MusicGain.cueGainDb(-20.0, -18.0, 0.1, -20.0), bed.cues[1].gainDb!!, 0.0)
        assertEquals("bài không có số đo trong danh mục: mức mặc định của công thức", MusicGain.cueGainDb(-20.0, null, null, null), bed.cues[2].gainDb!!, 0.0)
        assertEquals(1.5, bed.cues[0].audibleStart!!, 0.0)
        assertEquals(120.0, bed.cues[0].audibleEnd!!, 0.0)
        assertNull(bed.cues[1].audibleStart)
        assertTrue(bed.cues[2].sibling)
        assertTrue(bed.cues[3].tail)
        assertEquals(1, bed.cues[1].steps.size)
        assertTrue("bước âm lượng co theo: sau đầu cảnh của nó", bed.cues[1].steps[0].at > bed.cues[1].start)
        // Mức nhạc của cuốn (lớp sửa) đổi gain.
        val louder = SceneBed { clock }
        louder.arrive(arrival(levelDb = -14.0), 0.0)
        assertTrue(louder.cues[0].gainDb!! > bed.cues[0].gainDb!!)
    }

    @Test
    fun the_bed_finds_the_cue_of_a_second_and_a_sibling_follows_exactly_where_the_cue_before_ends() {
        val bed = SceneBed { timing(0.0, 5.0, 12.0, 20.0, 31.0, total = 40.0) }
        bed.arrive(arrival(), 0.0)
        val failures = MusicFailures { 0L }
        assertEquals(a, MusicCues.at(bed.cues, 11.99, failures)?.track)
        assertEquals(b, MusicCues.at(bed.cues, 12.0, failures)?.track)
        assertEquals(c, MusicCues.at(bed.cues, 25.0, failures)?.track)
        assertNull(MusicCues.at(bed.cues, 40.0, failures))
        // Bài kết sớm hơn mốc thì mốc kế vào ngay: `nextAfter` so bằng nhau từng bit, nên giây đã co phải bằng nhau.
        assertEquals(c, MusicCues.nextAfter(bed.cues, bed.cues[1])?.track)
    }

    @Test
    fun a_chapter_without_music_sets_no_cues_and_ticks_do_nothing() {
        val bed = SceneBed { timing(0.0, 5.0, total = 9.0) }
        assertTrue(bed.arrive(arrival(), 0.0))
        assertTrue(bed.cues.isNotEmpty())
        assertTrue("chương không nhạc: mốc rỗng đặt thẳng", bed.arrive(arrival(cues = emptyList()), 0.0))
        assertTrue(bed.cues.isEmpty())
        assertFalse(bed.tick(1.0, seeked = true))
    }

    // ---- đặt lại khi đồng hồ đọc đổi ----------------------------------------------------------------------------------------------------------

    @Test
    fun cues_are_placed_again_only_when_the_reading_clock_has_new_seconds() {
        var clock: SceneAnchor.Timing? = timing(0.0, 4.0, 9.0, 15.0, 22.0, total = 30.0) // đồng hồ ước
        val bed = SceneBed { clock }
        bed.arrive(arrival(), 0.0)
        val first = bed.cues.map { it.start }
        assertEquals(9.0, first[1], 1e-9)
        // Nhịp kế, đồng hồ y nguyên (mảng mới nhưng cùng số): không đặt lại.
        clock = timing(0.0, 4.0, 9.0, 15.0, 22.0, total = 30.0)
        assertFalse(bed.tick(2.0, seeked = false))
        assertEquals(first, bed.cues.map { it.start })
        // Clip về: đoạn 0..1 dài hơn ước, mọi đoạn sau dịch theo - mốc co theo, bài đổi vẫn đúng đầu đoạn đầu cảnh.
        clock = timing(0.0, 6.5, 11.5, 17.5, 24.5, total = 32.5)
        assertTrue(bed.tick(3.0, seeked = false))
        assertEquals(11.5, bed.cues[1].start, 1e-9)
        assertEquals(24.5, bed.cues[3].start, 1e-9)
        assertEquals(32.5, bed.cues[3].end, 1e-9)
        // Cùng đồng hồ rồi: yên.
        assertFalse(bed.tick(4.0, seeked = false))
    }

    @Test
    fun cues_arriving_while_the_voice_is_mid_chapter_start_at_the_next_paragraph_and_a_seek_back_brings_the_scene_of_that_place() {
        val clock = timing(0.0, 5.0, 12.0, 20.0, 31.0, total = 40.0)
        val bed = SceneBed { clock }
        bed.arrive(arrival(), 14.0) // giọng đang ở đoạn 2 (12..20): nhạc vào ở đoạn 3 (giây 20)
        assertEquals(20.0, bed.cues.first().start, 1e-9)
        assertEquals("cảnh B đang dở (12..20,87): chỉ còn phần sau đầu đoạn kế", b, bed.cues.first().track)
        assertFalse("nhảy tiếp về phía sau: vẫn chờ", bed.tick(30.0, seeked = true))
        assertTrue("tua về trước chỗ nhạc được phép vào: cảnh chứa chỗ mới", bed.tick(6.0, seeked = true))
        assertEquals(0.0, bed.cues.first().start, 1e-9)
        assertEquals(a, bed.cues.first().track)
    }

    @Test
    fun cues_that_arrive_before_the_chapter_has_a_clock_are_placed_when_it_appears() {
        var clock: SceneAnchor.Timing? = null
        val bed = SceneBed { clock }
        assertFalse(bed.arrive(arrival(), 0.0))
        assertTrue(bed.cues.isEmpty())
        assertFalse("vẫn chưa có đồng hồ", bed.tick(1.0, seeked = false))
        clock = timing(0.0, 5.0, 12.0, 20.0, 31.0, total = 40.0)
        assertTrue(bed.tick(2.0, seeked = false))
        assertEquals(4, bed.cues.size)
        assertNotNull(bed.cues[1])
        // Chương khác: quên hết.
        bed.reset()
        assertTrue(bed.cues.isEmpty())
        assertFalse(bed.tick(3.0, seeked = false))
    }

    @Test
    fun the_response_of_the_engine_reads_back_into_raw_cues() {
        val response = JSONObject().put(
            "cues",
            JSONArray()
                .put(JSONObject().put("start", 0.0).put("end", 50.0).put("link", a).put("key", "1:0").put("firstSegment", 0))
                .put(JSONObject().put("start", 50.0).put("end", 80.0).put("link", b).put("key", "1:0").put("sibling", true).put("tail", true)
                    .put("steps", JSONArray().put(JSONObject().put("at", 60.0).put("db", -2.0)).put(JSONObject().put("at", "x").put("db", 1))))
                .put(JSONObject().put("start", 80.0).put("end", 90.0).put("key", "1:1")) // không link: bỏ
        )
        val cues = SceneAnchor.cuesOf(response)
        assertEquals(2, cues.size)
        assertEquals(0, cues[0].firstSegment)
        assertNull(cues[1].firstSegment)
        assertTrue(cues[1].sibling && cues[1].tail)
        assertEquals(listOf(60.0), cues[1].steps.map { it.at })
        assertTrue(SceneAnchor.cuesOf(JSONObject()).isEmpty())
    }
}
