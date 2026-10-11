package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.min
import kotlin.math.sin
import kotlin.math.sqrt

/**
 * [MusicRender] khớp bản tham chiếu Python `abook/webui/music_render.py` trên cùng fixture `tests/fixtures/music_render` (Python
 * sinh, mỗi bên tự dựng tín hiệu theo công thức trong fixture): int16 lệch <= 1 LSB, g lệch <= 1e-9, RMS 100 ms lệch <= 0,01 dB,
 * số liệu chặn + bài thiếu khớp đúng. Hằng số xuất đọc từ ĐÚNG file `abook/webui/assets/music_mix.json` mà app gói vào assets.
 */
class MusicRenderTest {
    private val mixFile = File("../../../abook/webui/assets/music_mix.json")
    private val fixtures = File("../../../tests/fixtures/music_render")

    private class Case(val name: String, val json: JSONObject) {
        val rate = json.getInt("rate")
        val n = MusicRender.samples(json.getDouble("seconds"), rate)
        val params = MusicRender.Params.parse(json.getJSONObject("mix"))
        val voice = signal(json.getJSONArray("voice"), n, rate)
        val tracks = json.getJSONObject("tracks").let { t -> t.keys().asSequence().toList().associateWith { MusicRender.DoublePcm(track(t.getJSONObject(it), rate), 1) } }
        val timeline = MusicRender.Element.parseAll(json.getJSONArray("timeline"))
        val expected: JSONObject = json.getJSONObject("expected")
    }

    private fun cases(): List<Case> {
        val files = fixtures.listFiles { f -> f.name.endsWith(".json") }!!.sortedBy { it.name }
        assertEquals("7 fixture music_render", 7, files.size)
        return files.map { Case(it.name.removeSuffix(".json"), JSONObject(it.readText())) }
    }

    private fun run(case: Case, block: Int? = null): Triple<DoubleArray, DoubleArray, List<String>> {
        val bus = MusicRender.renderBus(case.timeline, case.n, case.rate, 1, { case.tracks[it] })
        val (out, g) = MusicRender.guard(case.voice, bus.data, case.rate, 1, case.params, block)
        return Triple(out, g, bus.missing)
    }

    @Test
    fun the_export_constants_are_read_from_the_shared_file() {
        val file = MusicRender.Params.parse(JSONObject(mixFile.readText()))
        for (case in cases()) {
            assertEquals(case.params.ceilingDbtp, file.ceilingDbtp, 0.0)
            assertEquals(case.params.headroomDb, file.headroomDb, 0.0)
            assertEquals(case.params.attackMs, file.attackMs, 0.0)
            assertEquals(case.params.releaseMs, file.releaseMs, 0.0)
            for (p in 0 until MusicRender.FIR_PHASES) assertArrayEquals(case.params.fir[p], file.fir[p], 0.0)
        }
    }

    @Test
    fun every_fixture_matches_the_python_reference() {
        for (case in cases()) {
            val (out, g, missing) = run(case)
            assertEquals(case.name, case.n, out.size)
            assertEquals(case.name, case.n, g.size)
            var lsb = 0
            for ((k, want) in pairs(case.expected.getJSONArray("probes"))) {
                val got = MusicRender.toInt16(out[k.toInt()]).toInt()
                lsb = max(lsb, abs(got - want.toInt()))
            }
            var gain = 0.0
            for ((k, want) in pairs(case.expected.getJSONArray("gainProbes"))) gain = max(gain, abs(g[k.toInt()] - want))
            val rms = case.expected.getJSONArray("rmsDb")
            val win = case.rate / 10
            var db = 0.0
            for (w in 0 until rms.length()) {
                var sum = 0.0
                for (i in w * win until (w + 1) * win) sum += out[i] * out[i]
                val r = sqrt(sum / win)
                if (rms.isNull(w)) assertEquals("${case.name} rms[$w]", 0.0, r, 0.0)
                else db = max(db, abs(20 * log10(r) - rms.getDouble(w)))
            }
            println("music_render ${case.name}: lệch int16 lớn nhất $lsb LSB, g ${"%.2e".format(gain)}, RMS ${"%.4f".format(db)} dB")
            assertTrue("${case.name}: int16 lệch $lsb LSB", lsb <= 1)
            assertTrue("${case.name}: g lệch $gain", gain <= 1e-9)
            assertTrue("${case.name}: RMS lệch $db dB", db <= 0.01)
            val stats = MusicRender.guardStats(g, case.rate)
            val want = case.expected.getJSONObject("guard")
            assertEquals(case.name, want.getInt("spans"), stats.spans)
            assertEquals(case.name, want.getDouble("ms"), stats.ms, 0.0)
            assertEquals(case.name, want.getDouble("maxSpanMs"), stats.maxSpanMs, 0.0)
            if (want.isNull("minGainDb")) assertEquals(case.name, null, stats.minGainDb)
            else assertEquals(case.name, want.getDouble("minGainDb"), stats.minGainDb!!, 0.0)
            val wantMissing = case.expected.getJSONArray("missing").let { a -> List(a.length()) { a.getString(it) } }
            assertEquals(case.name, wantMissing, missing)
        }
    }

    @Test
    fun the_guard_is_bit_identical_for_every_block_size() {
        for (case in cases()) {
            val (whole, g) = run(case)
            for (block in intArrayOf(1, 7, 64, 1000, 4096)) {
                val (out, gb) = run(case, block)
                assertArrayEquals("${case.name} khối $block", whole, out, 0.0)
                assertArrayEquals("${case.name} khối $block", g, gb, 0.0)
            }
        }
    }

    @Test
    fun the_bus_rendered_in_blocks_equals_the_bus_rendered_at_once() {
        for (case in cases()) {
            val whole = MusicRender.renderBus(case.timeline, case.n, case.rate, 1, { case.tracks[it] }).data
            val pieces = DoubleArray(case.n)
            var start = 0
            while (start < case.n) {
                val size = min(997, case.n - start)
                MusicRender.renderBus(case.timeline, size, case.rate, 1, { case.tracks[it] }, start).data
                    .copyInto(pieces, start)
                start += size
            }
            assertArrayEquals(case.name, whole, pieces, 0.0)
        }
    }

    @Test
    fun an_open_ended_element_plays_to_the_end_of_the_chapter() {
        // music_timeline ghi `to` = math.inf thành `Infinity` (json của Python) - phần tử kêu tới hết chương như `to` hữu hạn ở cuối.
        val pcm = MusicRender.DoublePcm(DoubleArray(100) { 0.5 }, 1)
        fun bus(to: String) = MusicRender.renderBus(MusicRender.Element.parseAll(JSONArray(
            """[{"track": "a", "from": 0.01, "to": $to, "position": 0, "gain": [[0, -6]], "loop": true}]""")), 400, 8000, 1, { pcm }).data
        assertArrayEquals(bus("0.05"), bus("Infinity"), 0.0)
        assertEquals(0.0, bus("Infinity")[79], 0.0)
        assertEquals(0.5 * Math.pow(10.0, -6.0 / 20.0), bus("Infinity")[399], 0.0)
    }

    @Test
    fun the_guard_only_scales_the_music_and_never_the_voice() {
        for (case in cases()) {
            val bus = MusicRender.renderBus(case.timeline, case.n, case.rate, 1, { case.tracks[it] }).data
            val (out, g) = MusicRender.guard(case.voice, bus, case.rate, 1, case.params)
            for (k in out.indices) assertEquals(case.voice[k] + g[k] * bus[k], out[k], 0.0)
            assertTrue(g.all { it in 0.0..1.0 })
        }
    }

    @Test
    fun a_sixteen_bit_track_renders_like_the_same_samples_in_doubles() {
        // Bộ đệm bài trên đĩa của bản xuất là int16 (như `_Pcm` máy tính): mẫu = short / 32768, kết quả như bài double cùng giá trị.
        val shorts = ShortArray(2 * 300) { k -> ((k * 977) % 65536 - 32768).toShort() }
        val asShort = MusicRender.ShortPcm(java.nio.ShortBuffer.wrap(shorts), 2)
        val asDouble = MusicRender.DoublePcm(DoubleArray(shorts.size) { shorts[it] / 32768.0 }, 2)
        val timeline = MusicRender.Element.parseAll(JSONArray("""[
            {"track": "a", "from": 0, "to": 5, "position": 0.5, "gain": [[0, null], [1, -6]], "loop": true}
        ]"""))
        val one = MusicRender.renderBus(timeline, 500, 100, 2, { asShort }).data
        val two = MusicRender.renderBus(timeline, 500, 100, 2, { asDouble }).data
        assertTrue(one.contentEquals(two))
        assertEquals(300, asShort.frames)
    }

    /**
     * Thời gian trộn một chương 20 phút 48 kHz mono trên JVM theo khối 4096 khung (như xuất M4B sẽ gọi): bus 3 phần tử (lặp mờ chéo
     * + bài anh em) + chặn đỉnh + int16. Chỉ đo - in ra để báo, không đặt ngưỡng (máy CI khác nhau).
     */
    @Test
    fun timing_of_a_twenty_minute_chapter() {
        val rate = 48000
        val n = 20 * 60 * rate
        val params = MusicRender.Params.parse(JSONObject(mixFile.readText()))
        fun tone(seconds: Double, vararg parts: Pair<Double, Double>) = MusicRender.DoublePcm(
            DoubleArray(MusicRender.samples(seconds, rate)) { k -> parts.sumOf { (f, a) -> a * sin(2 * PI * f * k / rate) } }, 1)
        val tracks = mapOf("a" to tone(60.0, 440.0 to 0.5, 1250.0 to 0.2), "b" to tone(120.0, 660.0 to 0.6))
        val timeline = MusicRender.Element.parseAll(JSONArray("""[
            {"track": "a", "from": 0, "to": 58, "position": 0, "gain": [[0, null], [2, -9], [56, -9], [58, null]]},
            {"track": "a", "from": 56, "to": 600, "position": 0, "gain": [[56, null], [58, -9]], "loop": true},
            {"track": "b", "from": 594, "to": 1200, "position": 0, "gain": [[594, null], [600, -6], [1197.5, -6], [1200, null]], "loop": true}
        ]"""))
        // giọng: 220 Hz nhỏ, mỗi 30 s có 0,5 s gần trần để bộ chặn làm việc thật
        fun voice(k: Int): Double {
            val hot = (k / rate) % 30 == 0 && (k % rate) < rate / 2
            return (if (hot) 0.8 else 0.3) * sin(2 * PI * 220.0 * k / rate)
        }
        val block = 4096
        var spent = 0L
        var peak = 0
        var written = 0
        val stream = MusicRender.GuardStream(rate, 1, params)
        var start = 0
        while (start < n) {
            val size = min(block, n - start)
            val v = DoubleArray(size) { voice(start + it) }
            val t0 = System.nanoTime()
            val bus = MusicRender.renderBus(timeline, size, rate, 1, { tracks[it] }, start)
            val out = stream.feed(v, bus.data)
            for (x in out) peak = max(peak, abs(MusicRender.toInt16(x).toInt()))
            spent += System.nanoTime() - t0
            written += out.size
            start += size
        }
        val t0 = System.nanoTime()
        val tail = stream.finish()
        for (x in tail) peak = max(peak, abs(MusicRender.toInt16(x).toInt()))
        spent += System.nanoTime() - t0
        written += tail.size
        assertEquals(n, written)
        println("music_render timing: chương 20 phút 48 kHz mono (${n} mẫu) trộn + chặn + int16 = ${"%.2f".format(spent / 1e9)} s, đỉnh $peak")
    }

    companion object {
        private fun pairs(a: JSONArray): List<Pair<Long, Double>> =
            List(a.length()) { a.getJSONArray(it).let { p -> p.getLong(0) to p.getDouble(1) } }

        /** x[k] = sum amp * sin(2*pi*freq*k/rate + phase) trên [round(from*rate), round(to*rate)) - đúng thứ tự phép tính của Python. */
        fun signal(components: JSONArray, n: Int, rate: Int): DoubleArray {
            val x = DoubleArray(n)
            for (i in 0 until components.length()) {
                val c = components.getJSONObject(i)
                val a = MusicRender.samples(c.optDouble("from", 0.0), rate)
                val b = if (!c.has("to") || c.isNull("to")) n else min(n, MusicRender.samples(c.getDouble("to"), rate))
                val freq = c.getDouble("freq")
                val amp = c.getDouble("amp")
                val phase = c.optDouble("phase", 0.0)
                for (k in a until b) x[k] += amp * sin(2 * PI * freq * k.toDouble() / rate + phase)
            }
            return x
        }

        fun track(spec: JSONObject, rate: Int): DoubleArray {
            val n = MusicRender.samples(spec.getDouble("seconds"), rate)
            val x = signal(spec.getJSONArray("components"), n, rate)
            for (k in 0 until min(n, MusicRender.samples(spec.optDouble("lead", 0.0), rate))) x[k] = 0.0
            val tail = MusicRender.samples(spec.optDouble("trail", 0.0), rate)
            for (k in max(0, n - tail) until n) x[k] = 0.0
            return x
        }
    }
}
