package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Đặt mốc nhạc theo cảnh theo đồng hồ đọc (SceneAnchor) phải ra GIỐNG HỆT ui/src/listen/sceneCues.ts trên bộ ví dụ chung `tests/fixtures/music/anchor/` (các file .json)
 * (sinh bởi sceneCues.fixtures.test.ts, chữ và con số tự dựng): đoạn chỉ có giây ước, đoạn đã đọc một phần, mốc về giữa chương (fromSegment / nextSegment),
 * firstSegment ngoài khoảng, đoạn tiêu đề / ngăn cảnh, chương chưa có đoạn nào - và chuỗi arrive / refresh / seeked của SceneCues. Sai số 1e-9.
 */
class SceneAnchorTest {
    private val folder = File("../../../tests/fixtures/music/anchor")
    private val eps = 1e-9

    private fun fixtures(): List<Pair<String, JSONObject>> {
        val files = folder.listFiles { file -> file.name.endsWith(".json") }?.sortedBy { it.name }.orEmpty()
        assertTrue("bộ ví dụ ${folder.absolutePath} phải có file (sceneCues.fixtures.test.ts sinh ra)", files.size >= 6)
        return files.map { it.name to JSONObject(it.readText(Charsets.UTF_8)) }
    }

    private fun timingOf(json: JSONObject): SceneAnchor.Timing {
        val starts = json.getJSONArray("starts")
        return SceneAnchor.Timing(DoubleArray(starts.length()) { starts.getDouble(it) }, json.getDouble("total"))
    }

    private fun cuesOf(array: JSONArray): List<SceneAnchor.Cue> = SceneAnchor.cuesOf(JSONObject().put("cues", array))

    private fun assertCues(label: String, expected: JSONArray, actual: List<SceneAnchor.Cue>) {
        assertEquals("$label: số mốc", expected.length(), actual.size)
        for (index in actual.indices) {
            val want = expected.getJSONObject(index)
            val got = actual[index]
            val at = "$label[$index]"
            assertEquals("$at link", want.getString("link"), got.link)
            assertEquals("$at key", want.getString("key"), got.key)
            assertEquals("$at start", want.getDouble("start"), got.start, eps)
            assertEquals("$at end", want.getDouble("end"), got.end, eps)
            assertEquals("$at sibling", want.optBoolean("sibling", false), got.sibling)
            assertEquals("$at tail", want.optBoolean("tail", false), got.tail)
            assertEquals("$at firstSegment", if (want.has("firstSegment")) want.getInt("firstSegment") else null, got.firstSegment)
            val steps = want.optJSONArray("steps") ?: JSONArray()
            assertEquals("$at số bước", steps.length(), got.steps.size)
            for (step in got.steps.indices) {
                assertEquals("$at bước $step: giây", steps.getJSONObject(step).getDouble("at"), got.steps[step].at, eps)
                assertEquals("$at bước $step: dB", steps.getJSONObject(step).getDouble("db"), got.steps[step].db, eps)
            }
        }
    }

    @Test
    fun anchoring_equals_the_web_one_on_every_shared_case() {
        for ((name, fixture) in fixtures()) {
            val expected = fixture.getJSONObject("expected")
            val timing = timingOf(expected.getJSONObject("timing"))
            val raw = cuesOf(fixture.getJSONArray("cues"))
            val anchored = SceneAnchor.anchor(raw, fixture.getDouble("estSeconds"), timing)
            assertCues("$name anchored", expected.getJSONArray("anchored"), anchored)
        }
    }

    @Test
    fun from_segment_and_next_segment_equal_the_web_ones() {
        for ((name, fixture) in fixtures()) {
            val expected = fixture.getJSONObject("expected")
            val timing = timingOf(expected.getJSONObject("timing"))
            val anchored = SceneAnchor.anchor(cuesOf(fixture.getJSONArray("cues")), fixture.getDouble("estSeconds"), timing)
            val from = expected.getJSONObject("from")
            assertTrue("$name: có ca fromSegment", from.length() > 0)
            for (key in from.keys()) assertCues("$name fromSegment($key)", from.getJSONArray(key), SceneAnchor.fromSegment(anchored, timing, key.toInt()))
            val next = expected.getJSONObject("next")
            assertTrue("$name: có ca nextSegment", next.length() > 0)
            for (key in next.keys()) assertEquals("$name nextSegment($key)", next.getInt(key), SceneAnchor.nextSegment(timing, key.toDouble()))
        }
    }

    @Test
    fun the_feed_places_and_re_places_cues_like_scene_cues() {
        var steps = 0
        for ((name, fixture) in fixtures()) {
            val expected = fixture.getJSONObject("expected")
            val events = fixture.getJSONArray("events")
            val results = expected.getJSONArray("events")
            assertEquals(events.length(), results.length())
            val raw = cuesOf(fixture.getJSONArray("cues"))
            var timing: SceneAnchor.Timing? = null
            val feed = SceneAnchor.Feed { timing }
            for (index in 0 until events.length()) {
                val event = events.getJSONObject(index)
                val result = results.getJSONObject(index)
                timing = timingOf(result.getJSONObject("timing")) // đồng hồ đọc ngay trước bước (kịch bản có thể vừa đổi)
                val placed = when (val op = event.getString("op")) {
                    "arrive" -> feed.arrive(raw, fixture.getDouble("estSeconds"), event.getDouble("time"))
                    "refresh" -> feed.refresh()
                    "seeked" -> feed.seeked(event.getDouble("time"))
                    else -> throw AssertionError(op)
                }
                val label = "$name ${event.getString("op")}#$index"
                if (result.isNull("set")) assertNull("$label: không đặt gì", placed) else assertCues(label, result.getJSONArray("set"), placed ?: throw AssertionError("$label: phải đặt mốc"))
                steps++
            }
        }
        assertTrue(steps >= 12)
    }
}
