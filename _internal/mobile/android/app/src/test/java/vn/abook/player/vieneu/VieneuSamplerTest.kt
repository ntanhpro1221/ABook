package vn.abook.player.vieneu

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64

/**
 * The code sampler repeats the desktop's `_det_sample` (scripts/vieneu_phone_bench_export.py) on recorded cases
 * (tests/fixtures/vieneu/sampler_cases.json, rewritten with `--sampler-fixture`): same logits, same repetition history, same uniform -> same code.
 */
class VieneuSamplerTest {
    private val fixture = JSONObject(File("../../../tests/fixtures/vieneu/sampler_cases.json").readText())

    @Test
    fun everyRecordedDrawPicksTheDesktopCode() {
        val cases = fixture.getJSONArray("cases")
        assertTrue(cases.length() >= 20)
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val bytes = Base64.getDecoder().decode(case.getString("logits"))
            val logits = FloatArray(bytes.size / 4).also { ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asFloatBuffer().get(it) }
            val history = RepetitionWindow(128, logits.size)
            val codes = case.getJSONArray("history")
            for (k in 0 until codes.length()) history.add(codes.getInt(k))
            val picked = VieneuSampler.sample(logits, history, fixture.getDouble("repetition_penalty").toFloat(), fixture.getDouble("temperature").toFloat(),
                fixture.getInt("top_k"), fixture.getDouble("top_p"), case.getDouble("u"))
            assertEquals("case $n", case.getInt("code"), picked)
        }
    }

    @Test
    fun theRepetitionWindowForgetsOldCodesAndListsEachCodeOnce() {
        val window = RepetitionWindow(3, 10)
        for (code in intArrayOf(1, 2, 2, 3, 4)) window.add(code)
        val seen = ArrayList<Int>()
        window.forEachCode { seen.add(it) }
        assertEquals(listOf(2, 3, 4), seen.sorted())
    }

    @Test
    fun aRecordedStreamOfUniformsIsReplayedInOrder() {
        val source = UniformSource.recorded(doubleArrayOf(0.25, 0.75))
        assertEquals(0.25, source.next(), 0.0)
        assertEquals(0.75, source.next(), 0.0)
    }
}
