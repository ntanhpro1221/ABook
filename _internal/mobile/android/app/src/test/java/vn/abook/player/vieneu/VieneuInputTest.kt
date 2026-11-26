package vn.abook.player.vieneu

import org.json.JSONArray
import org.junit.Assert.*
import org.junit.Test
import java.io.File

class VieneuInputTest {
    @Test fun syntheticInputsMatchDesktopChunksAndKeepDisplayOwnership() {
        val cases = JSONArray(File("../../../tests/fixtures/vieneu/android/readcap.json").readText(Charsets.UTF_8))
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val text = case.getString("repeat").repeat(case.getInt("count")).take(case.getInt("chars"))
            val limit = case.getInt("limit")
            val (tokens, units) = VieneuUnits.units(text, limit, directEnglish = true)
            assertEquals((tokens.indices).toList(), units.flatMap { (it.first..it.last).toList() })
            val actual = units.map { VieneuInput.boundedPieces(it.pieces, limit) }
            assertEquals(case.getJSONArray("chunks").toString(), JSONArray(actual).toString())
            assertTrue(actual.flatten().all { it.joinToString(" ").codePointCount(0, it.joinToString(" ").length) <= limit })
        }
    }

    @Test fun refusesThenHalvesAndStreamsOneCompleteDisplayUnit() {
        val accepted = ArrayList<String>()
        val calls = ArrayList<Long>()
        val tier = object : VieneuTier {
            override val rate = 24000
            override fun close() {}
            override fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray {
                calls.add(seed)
                if (phonemes.length > 20) throw IllegalArgumentException("does not fit a cache")
                accepted.addAll(phonemes.split(" "))
                return FloatArray(100) { .2f }
            }
        }
        val text = "Một hai ba bốn năm sáu bảy tám chín mười."
        val preset = VieneuPreset("test", "", floatArrayOf(0f), null, floatArrayOf(0f))
        val spoken = VieneuSpeaker { pieces, _, _ -> pieces.joinToString(" ") }.speak("nano", tier, "test", preset, text)
        assertEquals(text.split(" "), accepted)
        assertEquals(1, calls.distinct().size)
        assertEquals(1, spoken.spans.size)
        assertTrue(spoken.samples.isNotEmpty())
    }

    @Test fun ordinaryInputKeepsPiecesAndPcmExactly() {
        val pieces = listOf("Xin chào, đây là một câu thử.", "Câu thứ hai.")
        assertEquals(listOf(pieces), VieneuInput.boundedPieces(pieces, 256))
        val expected = FloatArray(300) { (it % 50) / 100f }
        var calls = 0
        val (audio, _) = VieneuInput.readUnit(pieces, pieces.joinToString(" "), 256, 24000,
            { group, _ -> assertEquals(pieces, group); group.joinToString(" ") }, { calls++; expected })
        assertArrayEquals(expected, audio, 0f)
        assertEquals(1, calls)
    }

    @Test fun shortOomAndUnrelatedFailureDoNotRetryAndCacheFailureHasABottom() {
        for (error in listOf(IllegalStateException("broken model"), OutOfMemoryError("out of memory"))) {
            var calls = 0
            try {
                VieneuInput.readUnit(listOf("Xin chào."), "", 140, 24000, { p, _ -> p.joinToString(" ") }, { calls++; throw error })
                fail("must propagate")
            } catch (got: Throwable) { assertSame(error, got) }
            assertEquals(1, calls)
        }
        var calls = 0
        try {
            VieneuInput.readUnit(listOf("ab".repeat(1000)), "", 256, 24000, { p, _ -> p.joinToString(" ") }, {
                calls++; throw IllegalArgumentException("does not fit a cache")
            })
            fail("must stop")
        } catch (_: IllegalArgumentException) {}
        assertTrue(calls <= VieneuInput.HALVING_DEPTH + 1)
    }
}
