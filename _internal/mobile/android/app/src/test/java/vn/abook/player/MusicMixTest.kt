package vn.abook.player

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * Lặp mờ chéo trong đoạn nghe được (lô 2 mix-loop, MIX_QA 3.2, 3.4, 3.5, 9) trên điện thoại - cùng mô hình với
 * abook/webui/music_mix.py và ui/src/listen/musicBed.ts: hằng số đọc từ MỘT file `abook/webui/assets/music_mix.json` (app đọc qua
 * `context.assets`, test đọc đúng file ấy), hàm thuần của [MusicCues] chạy qua cùng các fixture `tests/fixtures/music_timeline`.
 */
class MusicMixTest {
    private val mixFile = File("../../../abook/webui/assets/music_mix.json")
    private val fixtures = File("../../../tests/fixtures/music_timeline")
    private val track = "music/" + "a".repeat(40) + ".mp3"

    @Before
    fun loadMix() {
        MusicCues.mix = MusicMix.parse(mixFile.readText())
    }

    @Test
    fun the_values_in_use_are_the_values_in_the_file() {
        val file = JSONObject(mixFile.readText())
        val mix = MusicCues.mix
        assertEquals(file.getDouble("fadeSeconds") * 1000, mix.fadeMs.toDouble(), 0.0)
        assertEquals(file.getDouble("siblingFadeSeconds") * 1000, mix.siblingFadeMs.toDouble(), 0.0)
        assertEquals(file.getDouble("stepRampSeconds") * 1000, mix.stepRampMs.toDouble(), 0.0)
        assertEquals(file.getDouble("loopCrossfadeSeconds"), mix.loopCrossfadeSeconds, 0.0)
        assertEquals(file.getDouble("loopMinPeriodSeconds"), mix.loopMinPeriodSeconds, 0.0)
        // Công thức gain (MusicGain, dùng cả khi chưa có Context: sửa sách, hàng danh sách phát) giữ số chép tay - phải trùng file.
        assertEquals(file.getDouble("voicePlayedLufs"), MusicGain.VOICE_PLAYED_LUFS, 1e-12)
        assertEquals(file.getDouble("shortTermFloorLu"), MusicGain.SHORT_TERM_FLOOR_LU, 0.0)
    }

    @Test
    fun the_gain_keeps_the_loudest_part_of_a_track_ten_lu_under_the_voice() {
        assertEquals(-10.99, MusicGain.cueGainDb(-14.0, -20.0, 0.30), 0.0)
        assertEquals(-14.99, MusicGain.cueGainDb(-14.0, -20.0, 0.30, -12.0), 0.0)
        assertEquals("mức mặc định: sàn không chặn", -16.99, MusicGain.cueGainDb(-20.0, -20.0, 0.30, -18.0), 0.0)
        assertEquals("chưa đo p95: như cũ", -16.99, MusicGain.cueGainDb(-20.0, -20.0, 0.30, null), 0.0)
    }

    @Test
    fun cues_carry_the_audible_part_and_old_books_fall_back_to_the_whole_file() {
        val music = JSONObject(
            """{"tracks": {"$track": {}}, "chapters": {"1": [
                {"start": 0, "end": 300, "track": "$track", "gainDb": -9, "audibleStart": 1.5, "audibleEnd": 190.25},
                {"start": 300, "end": 400, "track": "$track", "gainDb": -9}
            ]}}""",
        )
        val (fresh, old) = MusicCues.of(music, 1)
        assertEquals(1.5, fresh.audibleStart!!, 0.0)
        assertEquals(190.25, fresh.audibleEnd!!, 0.0)
        assertNull(old.audibleStart)
        assertEquals(MusicCues.Loop(1.5, 190.25, 186.75, true), MusicCues.loopBounds(fresh, 200.0))
        assertEquals("thiếu A/E: 0 và độ dài thật", MusicCues.Loop(0.0, 200.0, 198.0, true), MusicCues.loopBounds(old, 200.0))
    }

    @Test
    fun the_loop_bounds_match_the_server() {
        fun cue(start: Double?, end: Double?) = MusicCues.Cue(0.0, 600.0, track, -9.0, audibleStart = start, audibleEnd = end)
        assertEquals(MusicCues.Loop(1.5, 190.0, 186.5, true), MusicCues.loopBounds(cue(1.5, 190.0), 200.0))
        assertEquals("E không vượt độ dài thật", MusicCues.Loop(1.5, 200.0, 196.5, true), MusicCues.loopBounds(cue(1.5, 250.0), 200.0))
        assertEquals("quá ngắn: lặp thường cả file", MusicCues.Loop(0.0, 10.0, 10.0, false), MusicCues.loopBounds(cue(2.0, 7.0), 10.0))
        val unknown = MusicCues.loopBounds(cue(null, null), Double.NaN)
        assertFalse(unknown.crossfade)
        assertTrue(unknown.end.isInfinite())
    }

    @Test
    fun a_seek_lands_at_a_plus_the_offset_modulo_the_period() {
        val cue = MusicCues.Cue(100.0, 600.0, track, -9.0, audibleStart = 10.0, audibleEnd = 200.0)
        val bounds = MusicCues.loopBounds(cue, 210.0) // P = 200 - 10 - 2 = 188
        assertEquals(10.0 + 95.0, MusicCues.alignedPosition(cue, 195.0, bounds), 1e-9)
        assertEquals(10.0 + 250.0 - 188.0, MusicCues.alignedPosition(cue, 350.0, bounds), 1e-9)
        assertEquals(10.0, MusicCues.alignedPosition(cue, 90.0, bounds), 0.0)
        assertEquals(72_000L, MusicCues.offsetMs(cue, 350.0, 210_000L))
        assertNull(MusicCues.offsetMs(cue, 350.0, -1L))
    }

    @Test
    fun a_new_element_opens_at_e_minus_x_and_the_final_loop_of_a_tail_cue_opens_none() {
        val tail = MusicCues.Cue(0.0, 400.0, track, -9.0, tail = true, audibleStart = 1.0, audibleEnd = 191.0)
        val bounds = MusicCues.loopBounds(tail, 200.0) // P = 188
        assertFalse(MusicCues.loopDue(bounds, 188.9))
        assertTrue(MusicCues.loopDue(bounds, 189.0))
        assertFalse("bài ngắn lặp thường", MusicCues.loopDue(MusicCues.loopBounds(tail, 5.0), 4.9))
        // Vòng 1 (0-188): còn 400 - 188 = 212 giây mốc, vòng sau vẫn trọn -> lặp. Vòng 2 (188-376): còn 24 < P/2 -> vòng cuối.
        assertFalse(MusicCues.finalLoop(tail, 188.0, 189.0, bounds))
        assertTrue(MusicCues.finalLoop(tail, 376.0, 189.0, bounds))
        assertFalse("mốc thường", MusicCues.finalLoop(tail.copy(tail = false), 376.0, 189.0, bounds))
        // Vào sớm mốc kế: bài tới E (hay `ended`) là hết.
        assertFalse(MusicCues.finished(bounds, 190.9, false))
        assertTrue(MusicCues.finished(bounds, 191.0, false))
        assertTrue(MusicCues.finished(bounds, 10.0, true))
    }

    @Test
    fun the_old_sibling_fades_within_what_is_left_of_it() {
        val cue = MusicCues.Cue(0.0, 300.0, track, -9.0, audibleStart = 0.0, audibleEnd = 190.0)
        val bounds = MusicCues.loopBounds(cue, 200.0)
        assertEquals(6.0, MusicCues.siblingFadeSeconds(bounds, 100.0), 0.0)
        assertEquals(2.5, MusicCues.siblingFadeSeconds(bounds, 187.5), 1e-9)
        assertEquals("đã quá E: một nhịp", MusicCues.TICK_MS / 1000.0, MusicCues.siblingFadeSeconds(bounds, 195.0), 0.0)
    }

    @Test
    fun a_new_level_keeps_the_loud_part_under_the_voice_and_a_pinned_track_drops_the_old_audible_part() {
        val music = JSONObject(
            """{"levelDb": -14, "tracks": {"$track": {"lufs": -20.0, "speechBand": 0.3, "s95": -12.0}}, "chapters": {"1": [
                {"start": 0, "end": 300, "track": "$track", "gainDb": -14.99, "audibleStart": 1.5, "audibleEnd": 190.25}
            ]}}""",
        )
        val louder = BookEdits.applyMusic(music, JSONObject("""{"music": {"levelDb": -10.0}}""")) as JSONObject
        assertEquals(-14.99, louder.getJSONObject("chapters").getJSONArray("1").getJSONObject(0).getDouble("gainDb"), 0.0)
        val sha = "c".repeat(40)
        val pinned = BookEdits.applyMusic(music, JSONObject(
            """{"music": {"pins": {"1:0": "local:$sha"}, "tracks": {"$sha": {"ext": "mp3", "title": "Bài", "lufs": -20.0}}}}""",
        )) as JSONObject
        val cue = pinned.getJSONObject("chapters").getJSONArray("1").getJSONObject(0)
        assertEquals("music/$sha.mp3", cue.getString("track"))
        assertFalse("bài ghim: trình phát dùng 0 và độ dài thật", cue.has("audibleStart") || cue.has("audibleEnd"))
    }

    @Test
    fun a_pinned_track_does_not_inherit_the_old_tracks_tail_flag() {
        val music = JSONObject(
            """{"levelDb": -14, "tracks": {"$track": {"lufs": -20.0}}, "chapters": {"1": [
                {"start": 0, "end": 300, "track": "$track", "gainDb": -14.99, "tail": true, "loopStart": 2.0, "loopEnd": 30.0}
            ]}}""",
        )
        val sha = "c".repeat(40)
        val pinned = BookEdits.applyMusic(music, JSONObject(
            """{"music": {"pins": {"1:0": "local:$sha"}, "tracks": {"$sha": {"ext": "mp3", "title": "Bài", "lufs": -20.0}}}}""",
        )) as JSONObject
        val cue = pinned.getJSONObject("chapters").getJSONArray("1").getJSONObject(0)
        assertEquals("music/$sha.mp3", cue.getString("track"))
        assertFalse("bài ghim không phải bài đuôi của bài cũ", cue.has("tail"))
        assertFalse(cue.has("loopStart") || cue.has("loopEnd"))
    }

    @Test
    fun a_new_chapter_reopens_the_track_even_when_its_first_cue_uses_the_same_one() {
        val cue = MusicCues.Cue(0.0, 120.0, track, -9.0)
        assertTrue("cùng chương, cùng bài: chơi tiếp", MusicCues.continues(track, cue, newChapter = false))
        // Như web (player.tsx xoá mốc cũ khi đổi chương): bài cũ mờ ra, mốc đầu chương mới mở lại bài, không tua bài cũ về đầu.
        assertFalse(MusicCues.continues(track, cue, newChapter = true))
        assertFalse("khác bài", MusicCues.continues("music/" + "d".repeat(40) + ".mp3", cue, newChapter = false))
        assertFalse("hết mốc", MusicCues.continues(track, null, newChapter = false))
        assertFalse("chưa có bài nào kêu", MusicCues.continues(null, cue, newChapter = false))
    }

    // ---- fixture dòng thời gian chung (tests/fixtures/music_timeline, như musicBed.test.ts) ----

    private class Element(json: JSONObject) {
        val track: String = json.getString("track")
        val cue = json.getInt("cue")
        val enter: String = json.getString("enter")
        val from = json.getDouble("from")
        val to = json.getDouble("to")
        val position = json.getDouble("position")
        val loop = json.optBoolean("loop", false)

        fun at(seconds: Double) = position + seconds - from
    }

    /** Mốc như trình phát nhận (máy chủ đã kẹp cuối chương - music_plan.clamp_to_chapter). */
    private fun playerCues(case: JSONObject, mix: JSONObject): List<MusicCues.Cue> {
        val limit = case.getDouble("chapterSeconds") - mix.getDouble("chapterEndFadeSeconds")
        val tracks = case.getJSONObject("tracks")
        val cues = case.getJSONArray("cues")
        return (0 until cues.length()).map { cues.getJSONObject(it) }.mapNotNull { cue ->
            val end = minOf(cue.getDouble("end"), limit)
            val info = tracks.getJSONObject(cue.getString("track"))
            MusicCues.Cue(
                cue.getDouble("start"), end, cue.getString("track"), cue.getDouble("gainDb"),
                sibling = cue.optBoolean("sibling", false),
                tail = cue.optBoolean("tail", false) && cue.getDouble("end") <= limit,
                audibleStart = info.optDouble("audibleStart").takeIf { it.isFinite() },
                audibleEnd = info.optDouble("audibleEnd").takeIf { it.isFinite() },
                loopStart = info.optDouble("loopStart").takeIf { it.isFinite() },
                loopEnd = info.optDouble("loopEnd").takeIf { it.isFinite() },
            ).takeIf { it.end > it.start }
        }
    }

    @Test
    fun the_pure_functions_agree_with_every_timeline_fixture() {
        val mix = JSONObject(mixFile.readText())
        val x = MusicCues.mix.loopCrossfadeSeconds
        val names = fixtures.listFiles { file -> file.extension == "json" }!!.map { it.nameWithoutExtension }.sorted()
        assertTrue(names.containsAll(listOf("loop_crossfade", "sibling_tail", "stop_at", "chapter_end", "short_track", "loop_points")))
        for (name in names) {
            val case = JSONObject(File(fixtures, "$name.json").readText())
            val cues = playerCues(case, mix)
            val tracks = case.getJSONObject("tracks")
            val timeline = case.getJSONArray("timeline").let { list -> (0 until list.length()).map { Element(list.getJSONObject(it)) } }
            timeline.forEachIndexed { index, element ->
                val label = "$name #$index"
                val cue = cues[element.cue]
                val bounds = MusicCues.loopBounds(cue, tracks.getJSONObject(element.track).getDouble("seconds"))
                assertEquals("$label: lặp thường hay mờ chéo", !bounds.crossfade, element.loop)
                if (element.enter != "early") {
                    assertEquals("$label: vị trí căn", element.position, MusicCues.alignedPosition(cue, element.from, bounds), 1e-6)
                }
                val before = timeline.getOrNull(index - 1)
                if (element.enter == "loop") {
                    val position = before!!.at(element.from)
                    assertTrue("$label: mở phần tử lặp ở loopEnd - X", MusicCues.loopDue(bounds, position))
                    assertFalse(MusicCues.loopDue(bounds, position - 0.05))
                    assertFalse("$label: chưa phải vòng cuối", MusicCues.finalLoop(cue, element.from, position, bounds))
                    assertEquals(bounds.loopStart, element.position, 0.0)
                }
                if (element.enter == "early") {
                    val previous = MusicCues.loopBounds(cues[before!!.cue], tracks.getJSONObject(before.track).getDouble("seconds"))
                    assertTrue("$label: vào sớm khi bài trước tới E", MusicCues.finished(previous, before.at(element.from), false))
                    assertFalse(MusicCues.finished(previous, before.at(element.from) - 0.05, false))
                    assertEquals(cue.start, cues[before.cue].end, 0.0)
                    assertTrue(element.from < cue.start)
                    assertEquals(bounds.start, element.position, 0.0)
                }
                val looped = timeline.drop(index + 1).any { it.cue == element.cue && it.enter == "loop" }
                if (cue.tail && bounds.crossfade) {
                    val position = bounds.loopEnd - x
                    val seconds = element.from + position - element.position
                    assertEquals("$label: vòng cuối = không có phần tử lặp sau", !looped, MusicCues.finalLoop(cue, seconds, position, bounds))
                }
                if (cue.tail && !bounds.crossfade) {
                    assertTrue("$label: vòng cuối của lặp thường", MusicCues.finalLoop(cue, element.to - bounds.period, 0.0, bounds))
                    assertFalse(MusicCues.finalLoop(cue, element.to - 2 * bounds.period, 0.0, bounds))
                }
                val following = cues.getOrNull(element.cue + 1)
                if (following != null && following.sibling && following.start == cue.end && element.to > cue.end && !looped) {
                    assertEquals("$label: anh em cũ mờ trong phần còn lại",
                        MusicCues.siblingFadeSeconds(bounds, element.at(cue.end)), element.to - cue.end, 1e-6)
                }
                if (following?.sibling != true && element.to > cue.end + 1e-9 && !looped) {
                    assertEquals("$label: mờ ra cuối mốc", MusicCues.mix.fadeMs / 1000.0, element.to - cue.end, 1e-6)
                }
                assertTrue("$label: nhạc mờ xong trước khi giọng hết", element.to <= case.getDouble("chapterSeconds") - 0.5)
            }
        }
    }
}
