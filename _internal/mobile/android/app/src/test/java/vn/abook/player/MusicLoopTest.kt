package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

/**
 * Điểm vòng của bài có đoạn kết (Corpus/research/music/PLAN_loop.md §10) trên điện thoại: [MusicCues.loopBounds], [MusicCues.loopPosition],
 * [MusicCues.loopSchedule] ra cùng số với Python (`music_mix`, nguồn sự thật) và máy tính (musicBed.test.ts) trên đúng các fixture
 * `tests/fixtures/music_loop` (scripts/music_loop_fixtures.py), lệch <= 1 ms. Bài không có điểm vòng (hay không hợp lệ): trùng từng số với 0.4.89.
 */
class MusicLoopTest {
    private val mixFile = File("../../../abook/webui/assets/music_mix.json")
    private val fixtures = File("../../../tests/fixtures/music_loop")
    private val ms = 1e-3

    @Before
    fun loadMix() {
        MusicCues.mix = MusicMix.parse(mixFile.readText())
    }

    private fun number(json: JSONObject, key: String): Double? = if (json.has(key) && !json.isNull(key)) json.getDouble(key) else null

    private fun doubles(array: JSONArray): List<Double> = List(array.length()) { array.getDouble(it) }

    private fun cue(track: JSONObject): MusicCues.Cue = MusicCues.Cue(
        0.0, 0.0, "", null, audibleStart = number(track, "audibleStart"), audibleEnd = number(track, "audibleEnd"),
        loopStart = number(track, "loopStart"), loopEnd = number(track, "loopEnd"),
    )

    private fun near(label: String, want: List<Double>, got: List<Double>) {
        assertEquals("$label: số phần tử", want.size, got.size)
        want.indices.forEach { assertEquals("$label #$it", want[it], got[it], ms) }
    }

    @Test
    fun every_loop_fixture_matches_the_python_reference() {
        val names = fixtures.listFiles { file -> file.extension == "json" }!!.map { it.nameWithoutExtension }.sorted()
        assertEquals(listOf("invalid_points", "with_points", "without_points"), names)
        for (name in names) {
            val case = JSONObject(File(fixtures, "$name.json").readText())
            val track = case.getJSONObject("track")
            val bounds = MusicCues.loopBounds(cue(track), track.getDouble("seconds"))
            val want = case.getJSONObject("bounds")
            assertEquals(name, MusicCues.Loop(want.getDouble("start"), want.getDouble("end"), want.getDouble("period"), want.getBoolean("crossfade"),
                want.getDouble("loopStart"), want.getDouble("loopEnd")), bounds)
            case.optJSONArray("invalidVariants")?.let { variants ->
                val plain = MusicCues.loopBounds(cue(track).copy(loopStart = null, loopEnd = null), track.getDouble("seconds"))
                for (index in 0 until variants.length()) {
                    val variant = variants.getJSONObject(index)
                    val odd = cue(track).copy(loopStart = number(variant, "loopStart"), loopEnd = number(variant, "loopEnd"))
                    assertEquals("$name: $variant như không có điểm vòng", plain, MusicCues.loopBounds(odd, track.getDouble("seconds")))
                }
            }
            val ts = doubles(case.getJSONArray("ts"))
            val positions = ts.map { MusicCues.loopPosition(bounds, it) }
            near("$name: vị trí", doubles(case.getJSONArray("positions")), positions)
            val cues = case.getJSONArray("cues")
            for (index in 0 until cues.length()) {
                val item = cues.getJSONObject(index)
                val length = item.getDouble("seconds")
                near("$name $length: mở phần tử", doubles(item.getJSONArray("opens")), MusicCues.loopSchedule(bounds, length).opens)
                val tail = MusicCues.loopSchedule(bounds, length, tail = true)
                near("$name $length tail: mở phần tử", doubles(item.getJSONObject("tail").getJSONArray("opens")), tail.opens)
                assertEquals("$name $length: hết vòng cuối", item.getJSONObject("tail").getDouble("seconds"), tail.end, ms)
            }
            case.optJSONObject("legacy")?.let { legacy ->
                assertEquals("$name: vị trí trùng từng số với 0.4.89", doubles(legacy.getJSONArray("positions")), positions)
                val old = legacy.getJSONArray("cues")
                for (index in 0 until old.length()) {
                    val item = old.getJSONObject(index)
                    val length = item.getDouble("seconds")
                    near("$name $length: như 0.4.89", doubles(item.getJSONArray("opens")), MusicCues.loopSchedule(bounds, length).opens)
                    val tail = MusicCues.loopSchedule(bounds, length, tail = true)
                    near("$name $length tail: như 0.4.89", doubles(item.getJSONObject("tail").getJSONArray("opens")), tail.opens)
                    assertEquals(item.getJSONObject("tail").getDouble("seconds"), tail.end, ms)
                }
            }
        }
    }

    @Test
    fun the_loop_element_opens_at_loop_end_less_x_from_loop_start() {
        val track = JSONObject(File(fixtures, "with_points.json").readText()).getJSONObject("track")
        val cue = cue(track).copy(start = 100.0, end = 700.0)
        val bounds = MusicCues.loopBounds(cue, track.getDouble("seconds"))
        val x = MusicCues.mix.loopCrossfadeSeconds
        assertTrue("tới loopEnd - X thì mở", MusicCues.loopDue(bounds, bounds.loopEnd - x))
        assertTrue("chưa tới thì chưa", !MusicCues.loopDue(bounds, bounds.loopEnd - x - 0.05))
        assertEquals("tua vòng đầu: A + t", 1.5 + 100.0, MusicCues.alignedPosition(cue, 200.0, bounds), 1e-9)
        assertEquals("tua vòng sau", 12.5 + (200.0 - 11.0) % 146.25, MusicCues.alignedPosition(cue, 300.0, bounds), 1e-9)
        assertEquals((12.5 * 1000).toLong(), MusicCues.offsetMs(cue, 100.0 + 157.25, 200_000))
    }

    @Test
    fun the_loop_points_come_from_the_book_package_and_the_catalog() {
        val name = "music/" + "a".repeat(40) + ".mp3"
        val music = JSONObject("""{"tracks": {"$name": {"file": "$name"}}, "chapters": {"1": [
            {"start": 0, "end": 300, "track": "$name", "gainDb": -9, "audibleStart": 1.5, "audibleEnd": 190.25, "loopStart": 12.5, "loopEnd": 160.75},
            {"start": 300, "end": 400, "track": "$name", "gainDb": -9}]}}""")
        val (fresh, old) = MusicCues.of(music, 1)
        assertEquals(12.5, fresh.loopStart!!, 0.0)
        assertEquals(160.75, fresh.loopEnd!!, 0.0)
        assertEquals(null, old.loopStart)
        val track = SceneTrack.of(JSONObject("""{"link": "https://x/a.mp3", "valence": 0.1, "arousal": 0.2, "loopStart": 12.5, "loopEnd": 160.75}"""))!!
        assertEquals(12.5 to 160.75, track.loopStart to track.loopEnd)
    }
}
