package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * [MusicTimeline] khớp NGUYÊN phần `timeline` (Python `music_mix.music_timeline`, làm tròn như `_Element.shape`) của mọi fixture
 * `tests/fixtures/music_timeline` - cùng bộ ví dụ pytest và trình phát web kiểm. Hằng số đọc từ đúng `music_mix.json` của app.
 */
class MusicTimelineTest {
    private val mixFile = File("../../../abook/webui/assets/music_mix.json")
    private val fixtures = File("../../../tests/fixtures/music_timeline")

    @Before
    fun loadMix() {
        MusicCues.mix = MusicMix.parse(mixFile.readText())
    }

    private fun number(json: JSONObject, key: String): Double? = if (json.has(key) && !json.isNull(key)) json.getDouble(key) else null

    private fun cue(json: JSONObject): MusicCues.Cue {
        val steps = json.optJSONArray("steps") ?: JSONArray()
        return MusicCues.Cue(
            json.getDouble("start"), json.getDouble("end"), json.getString("track"), number(json, "gainDb"),
            List(steps.length()) { steps.getJSONObject(it).let { s -> MusicCues.Step(s.getDouble("at"), s.getDouble("db")) } },
            json.optBoolean("sibling", false), json.optBoolean("tail", false), number(json, "audibleStart"), number(json, "audibleEnd"),
        )
    }

    /** Phần tử như Python ghi ra JSON: số kép so bằng ==, dB null = câm. */
    private fun shown(shaped: MusicTimeline.Shaped): List<Any?> {
        val e = shaped.element
        return listOf(e.track, shaped.cue, shaped.enter, e.from, e.to, e.position, e.gainAt.indices.map { listOf(e.gainAt[it], e.gainDb[it]) }, e.loop)
    }

    private fun shown(json: JSONObject): List<Any?> {
        val gain = json.getJSONArray("gain")
        return listOf(json.getString("track"), json.getInt("cue"), json.getString("enter"), json.getDouble("from"), json.getDouble("to"),
            json.getDouble("position"), List(gain.length()) { gain.getJSONArray(it).let { p -> listOf(p.getDouble(0), if (p.isNull(1)) null else p.getDouble(1)) } },
            json.optBoolean("loop", false))
    }

    @Test
    fun every_timeline_fixture_matches_the_python_reference() {
        val files = fixtures.listFiles { f -> f.name.endsWith(".json") }!!.sortedBy { it.name }
        assertTrue("có fixture music_timeline", files.size >= 5)
        for (file in files) {
            val case = JSONObject(file.readText())
            val cues = case.getJSONArray("cues").let { a -> List(a.length()) { cue(a.getJSONObject(it)) } }
            val tracks = case.getJSONObject("tracks").let { t ->
                t.keys().asSequence().toList().associateWith { name ->
                    t.getJSONObject(name).let { MusicTimeline.TrackInfo(number(it, "seconds"), number(it, "audibleStart"), number(it, "audibleEnd")) }
                }
            }
            val got = MusicTimeline.build(cues, number(case, "chapterSeconds"), tracks).map(::shown)
            val want = case.getJSONArray("timeline").let { a -> List(a.length()) { shown(a.getJSONObject(it)) } }
            assertEquals(file.name, want, got)
        }
    }

    @Test
    fun the_last_cue_ends_before_the_chapter_does_and_loses_its_tail() {
        val cues = listOf(MusicCues.Cue(0.0, 100.0, "a", -10.0, tail = true), MusicCues.Cue(100.0, 120.0, "b", -10.0))
        val fade = MusicCues.mix.chapterEndFadeSeconds
        val clamped = MusicTimeline.clampToChapter(cues, 100.0)
        assertEquals(listOf(100.0 - fade), clamped.map { it.end })
        assertEquals(false, clamped.single().tail)
        assertEquals(cues, MusicTimeline.clampToChapter(cues, null))
    }

    @Test
    fun the_shaped_elements_render_like_the_python_reference_elements() {
        // Phần tử của dòng thời gian đưa thẳng vào bộ dựng (như Mixer.wrap của máy tính dựng từ shape()).
        val shaped = MusicTimeline.build(listOf(MusicCues.Cue(0.0, 30.0, "a", -12.0)), 40.0, mapOf("a" to MusicTimeline.TrackInfo(20.0)))
        val pcm = MusicRender.DoublePcm(DoubleArray(20 * 100) { 0.5 }, 1)
        val bus = MusicRender.renderBus(shaped.map { it.element }, 40 * 100, 100, 1, { pcm }).data
        assertEquals(0.0, bus[0], 0.0)
        assertTrue(bus[15 * 100] > 0.0)
    }
}
