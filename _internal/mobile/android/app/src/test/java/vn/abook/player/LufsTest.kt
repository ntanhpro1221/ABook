package vn.abook.player

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.File
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin

/**
 * [Lufs] so với `ebur128` của ffmpeg (máy tính, `music_export._lufs`) trên fixture `tests/fixtures/lufs/lufs.json` (sinh bằng
 * LLM_Train/music/mixqa/make_lufs_fixture.py): bài hai kênh, bản gộp một kênh (dualmono) và số bù gộp. ffmpeg in 0,1 LU và đo sau khi
 * tự đổi về 48 kHz - lệch tới 0,1 là cùng bậc.
 */
class LufsTest {
    private val cases = JSONArray(File("../../../tests/fixtures/lufs/lufs.json").readText())

    private fun channel(parts: JSONArray, n: Int, rate: Int): ShortArray {
        val x = DoubleArray(n)
        for (i in 0 until parts.length()) {
            val p = parts.getJSONObject(i)
            val a = Math.round(p.optDouble("from", 0.0) * rate).toInt()
            val b = if (p.has("to")) Math.round(p.getDouble("to") * rate).toInt() else n
            val freq = p.getDouble("freq")
            val amp = p.getDouble("amp")
            val phase = p.optDouble("phase", 0.0)
            for (k in a until b) x[k] += amp * sin(2 * PI * freq * k / rate + phase)
        }
        return ShortArray(n) { Math.rint(x[it] * 32768).coerceIn(-32768.0, 32767.0).toInt().toShort() }
    }

    @Test
    fun loudness_and_the_mono_fold_offset_match_ffmpeg() {
        assertEquals(10, cases.length())
        for (i in 0 until cases.length()) {
            val case: JSONObject = cases.getJSONObject(i)
            val rate = case.getInt("rate")
            val n = case.getInt("seconds") * rate
            val left = channel(case.getJSONArray("left"), n, rate)
            val right = channel(case.getJSONArray("right"), n, rate)
            val stereo = ShortArray(2 * n) { if (it % 2 == 0) left[it / 2] else right[it / 2] }
            val mono = ShortArray(n) { Math.round((left[it] + right[it]) / 2f).toShort() } // như PcmConverter
            val s = Lufs(rate, 2).apply { feed(stereo) }.integrated()!!
            val f = Lufs(rate, 1, dualMono = true).apply { feed(mono) }.integrated()!!
            val name = "${case.getString("name")}@$rate"
            assertEquals("$name hai kênh", case.getDouble("stereoLufs"), s, 0.1 + 1e-9)
            assertEquals("$name gộp", case.getDouble("foldedLufs"), f, 0.1 + 1e-9)
            assertEquals("$name bù", case.getDouble("offsetDb"), Lufs.monoOffsetDb(s, f), 0.2 + 1e-9)
        }
    }

    @Test
    fun feeding_in_pieces_is_the_same_and_silence_or_a_short_clip_is_not_measured() {
        val rate = 24000
        val tone = ShortArray(5 * rate) { k -> Math.rint(32768 * 0.2 * sin(2 * PI * 440.0 * k / rate)).toInt().toShort() }
        val whole = Lufs(rate, 1).apply { feed(tone) }.integrated()
        val pieces = Lufs(rate, 1)
        var at = 0
        while (at < tone.size) {
            val n = minOf(1237, tone.size - at)
            pieces.feed(tone.copyOfRange(at, at + n))
            at += n
        }
        assertEquals(whole, pieces.integrated())
        // sin 440 Hz biên độ 0,2 một kênh: -0,691 + 10 log10(0,02 * lọc K ~1) ~ -17,7 LUFS
        assertEquals(-17.7, whole!!, 0.15)
        assertNull(Lufs(rate, 1).apply { feed(ShortArray(3 * rate)) }.integrated())
        assertNull(Lufs(rate, 1).apply { feed(tone.copyOfRange(0, rate / 4)) }.integrated())
        assertEquals(0.0, Lufs.monoOffsetDb(null, -20.0), 0.0)
        assertEquals(Lufs.MONO_MAX_DB, Lufs.monoOffsetDb(-10.0, -30.0), 0.0)
        assertEquals(abs(Lufs.monoOffsetDb(-10.0, -10.004)), 0.0, 0.0)
    }
}
