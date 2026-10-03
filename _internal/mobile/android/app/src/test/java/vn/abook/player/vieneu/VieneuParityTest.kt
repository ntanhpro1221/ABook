package vn.abook.player.vieneu

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest
import java.util.Base64

/**
 * The phone's VieNeu pieces against what the DESKTOP gives for the same input (tests/fixtures/vieneu/android, written by
 * scripts/vieneu_android_fixtures.py from abook/readaloud/vieneu.py + vieneu_engine.py): units, frame caps, syllables, seeds, Turbo token
 * ids, numpy's random streams, edge trimming / joins / babble check / WAV bytes. Everything here must be bit-identical.
 */
class VieneuParityTest {
    private val dir = File("../../../tests/fixtures/vieneu/android")

    private fun json(name: String) = JSONObject(File(dir, name).readText(Charsets.UTF_8))

    private fun strings(array: JSONArray) = (0 until array.length()).map { array.getString(it) }

    private fun sha(floats: FloatArray): String {
        val bytes = ByteBuffer.allocate(floats.size * 4).order(ByteOrder.LITTLE_ENDIAN).also { buffer -> floats.forEach { buffer.putFloat(it) } }.array()
        return sha(bytes)
    }

    private fun sha(bytes: ByteArray) = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    @Test
    fun paragraphsAreCutIntoTheDesktopsUnits() {
        val cases = json("text.json").getJSONArray("units")
        assertTrue(cases.length() >= 30)
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val (tokens, units) = VieneuUnits.units(case.getString("text"), case.getInt("max"), case.optString("origin").ifEmpty { null })
            val label = "${case.getString("text").take(40)} / ${case.getInt("max")}"
            assertEquals(label, case.getInt("tokens"), tokens.size)
            val want = case.getJSONArray("units")
            assertEquals(label, want.length(), units.size)
            for (i in units.indices) {
                val row = want.getJSONObject(i)
                assertEquals(label, row.getInt("first"), units[i].first)
                assertEquals(label, row.getInt("last"), units[i].last)
                assertEquals(label, strings(row.getJSONArray("pieces")), units[i].pieces)
            }
        }
    }

    @Test
    fun frameCapsAndSyllablesMatch() {
        val cases = json("text.json").getJSONArray("frames")
        assertTrue(cases.length() >= 200)
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val phonemes = case.getString("phonemes")
            assertEquals(phonemes, case.getInt("syllables"), VieneuAudio.phonemeSyllables(phonemes))
            assertEquals(phonemes, case.getInt("cap"), VieneuAudio.maxExpectedFrames(phonemes))
        }
    }

    @Test
    fun seedsAreTheDesktopsSeeds() {
        val cases = json("text.json").getJSONArray("seeds")
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            assertEquals(case.getLong("seed"), VieneuSpeaker.seedOf(*strings(case.getJSONArray("parts")).toTypedArray()))
        }
    }

    @Test
    fun turboTokenIdsMatchTheDesktopTokenizer() {
        val bpe = ByteBpe(File(dir, "turbo_tokenizer.json"))
        val cases = json("tokens.json").getJSONArray("cases")
        assertTrue(cases.length() >= 200)
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val ids = case.getJSONArray("ids").let { array -> IntArray(array.length()) { array.getInt(it) } }
            assertArrayEquals(case.getString("text"), ids, bpe.encode(case.getString("text")))
        }
    }

    @Test
    fun randomStateDrawsTheSameUniforms() {
        val cases = json("rng.json").getJSONArray("randomState")
        for (n in 0 until cases.length()) {
            val case = cases.getJSONObject(n)
            val random = NumpyRandomState(case.getLong("seed"))
            val values = case.getJSONArray("values")
            for (i in 0 until values.length()) assertEquals("seed ${case.getLong("seed")} #$i", values.getDouble(i), random.randomSample(), 0.0)
        }
    }

    @Test
    fun defaultRngDrawsTheSameNormals() {
        val rng = json("rng.json")
        val uniform = rng.getJSONArray("uniform")
        for (n in 0 until uniform.length()) {
            val case = uniform.getJSONObject(n)
            val generator = NumpyGenerator(case.getLong("seed"))
            val values = case.getJSONArray("values")
            for (i in 0 until values.length()) assertEquals(values.getDouble(i), generator.nextDouble(), 0.0)
        }
        val normals = rng.getJSONArray("standardNormal")
        for (n in 0 until normals.length()) {
            val case = normals.getJSONObject(n)
            val first = case.getJSONArray("first")
            val generator = NumpyGenerator(case.getLong("seed"))
            for (i in 0 until first.length()) assertEquals("seed ${case.getLong("seed")} #$i", first.getDouble(i), generator.standardNormal(), 0.0)
            val all = NumpyGenerator(case.getLong("seed")).standardNormalFloats(case.getInt("count"))
            assertEquals("seed ${case.getLong("seed")}: Nano start noise", case.getString("float32Sha256"), sha(all))
        }
    }

    private fun pcm(text: String): FloatArray {
        val bytes = Base64.getDecoder().decode(text)
        val shorts = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        return FloatArray(shorts.remaining()) { shorts.get(it) / 32768f }
    }

    @Test
    fun edgesTrimsJoinsBurstsAndWavBytesMatch() {
        val audio = json("audio.json")
        val rate = audio.getInt("rate")
        val signals = audio.getJSONObject("signals")
        val decoded = signals.keys().asSequence().associateWith { pcm(signals.getJSONObject(it).getString("pcm")) }
        for ((name, wav) in decoded) {
            val case = signals.getJSONObject(name)
            val edge = case.getJSONArray("edge")
            assertArrayEquals(name, intArrayOf(edge.getInt(0), edge.getInt(1)), VieneuAudio.edgeSilence(wav, rate))
            val trimmed = VieneuAudio.trimAndFade(wav, rate)
            assertEquals(name, case.getInt("trimmedLength"), trimmed.size)
            assertEquals("$name: trim + fade", case.getString("trimmedSha256"), sha(trimmed))
            assertEquals("$name: bursts", case.getInt("bursts"), VieneuAudio.countSpeechBursts(wav, rate))
            assertEquals("$name: wav", case.getString("wavSha256"), sha(VieneuAudio.wavBytes(wav, rate)))
        }
        val joins = audio.getJSONArray("joins")
        for (n in 0 until joins.length()) {
            val case = joins.getJSONObject(n)
            val chunks = strings(case.getJSONArray("chunks")).map { decoded.getValue(it) }
            val pauses = case.getJSONArray("pauses").let { array -> (0 until array.length()).map { array.getDouble(it) } }
            val (joined, spans) = VieneuAudio.join(chunks, rate, pauses)
            assertEquals(case.getInt("length"), joined.size)
            val want = case.getJSONArray("spans")
            for (i in spans.indices) assertArrayEquals(intArrayOf(want.getJSONArray(i).getInt(0), want.getJSONArray(i).getInt(1)), spans[i])
            assertEquals(case.getString("sha256"), sha(joined))
        }
        val babble = audio.getJSONArray("babble")
        for (n in 0 until babble.length()) {
            val case = babble.getJSONObject(n)
            val got = VieneuAudio.babbleSuspect(decoded.getValue(case.getString("signal")), rate, case.getString("phonemes"), case.getInt("cap"), case.getInt("frames"))
            val want = case.getJSONArray("result")
            assertEquals(case.toString(), listOf(want.getBoolean(0), want.getInt(1), want.getInt(2), want.getInt(3)), listOf(got.suspect, got.syllables, got.bursts, got.frames))
        }
    }

    @Test
    fun npzArraysAreReadInPlace() {
        val npz = NpzFile(File(dir, "small.npz"))
        assertEquals(setOf("table", "eps", "wide"), npz.names)
        val table = npz.floats("table")
        assertArrayEquals(intArrayOf(3, 4), table.shape)
        assertArrayEquals(FloatArray(12) { it / 8f }, table.data, 0f)
        assertEquals(1e-5f, npz.floats("eps").data.single(), 0f)
        val refused = runCatching { npz.floats("wide") }.exceptionOrNull()
        assertTrue("float64 is refused, not misread: $refused", refused is IllegalArgumentException)
    }

    @Test
    fun presetsAreOrderedFeaturedFirstThenAsInTheFile() {
        val json = JSONObject().put("presets", JSONObject()
            .put("C", JSONObject().put("speaker_emb", JSONArray(listOf(0.5, 1.0))).put("gender", "female"))
            .put("B", JSONObject().put("featured", 2).put("speaker_emb", JSONArray(listOf(1.0))).put("codes", JSONArray(listOf(JSONArray(listOf(1, 2)), JSONArray(listOf(3, 4))))))
            .put("A", JSONObject().put("featured", 1).put("speaker_emb", JSONArray(listOf(1.0))).put("style", JSONArray(listOf(JSONArray(listOf(0.25, 0.5)))))))
        val presets = VieneuPresets.read(json)
        assertEquals(listOf("A", "B", "C"), presets.map { it.name })
        assertArrayEquals(intArrayOf(1, 2, 3, 4), presets[1].codes)
        assertArrayEquals(floatArrayOf(0.25f, 0.5f), presets[0].style, 0f)
        assertEquals("female", presets[2].gender)
    }

    @Test
    fun theDesktopClipsVoiceOrderIsTheFirstVoiceOfEachTier() {
        // the self-benchmark and the androidTest use the first voice of a tier: the same one the desktop lists first
        val clips = json("clips.json").getJSONArray("clips")
        for (n in 0 until clips.length()) {
            val clip = clips.getJSONObject(n)
            assertEquals("vieneu:${clip.getString("tier")}/${clip.getJSONArray("voiceOrder").getString(0)}", clip.getString("voice"))
        }
    }
}
