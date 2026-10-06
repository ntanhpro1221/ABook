package vn.abook.player.readaloud

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import vn.abook.player.vieneu.NumpyRandomState
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuUnits
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.security.MessageDigest

/**
 * The phone's Supertonic inputs against what the DESKTOP gives for the same text (tests/fixtures/readaloud/supertonic/supertonic.json, written by
 * scripts/supertonic_android_fixtures.py from abook/readaloud/supertonic.py): cleaned text, character ids, chunk speed, units + seeds + pauses of a
 * paragraph, the start noise, the loudness raise. The voice styles and one chunk of audio are checked where the model is (SupertonicBenchTest#parity
 * on the emulator; here too when ABOOK_SUPERTONIC_MODEL points at the model folder).
 */
class SupertonicParityTest {
    private val fixture = JSONObject(File("../../../tests/fixtures/readaloud/supertonic/supertonic.json").readText(Charsets.UTF_8))

    private fun objects(name: String): List<JSONObject> = fixture.getJSONArray(name).let { array -> List(array.length()) { array.getJSONObject(it) } }

    private fun floats(array: JSONArray) = FloatArray(array.length()) { array.getDouble(it).toFloat() }

    private fun longs(array: JSONArray) = LongArray(array.length()) { array.getLong(it) }

    private fun strings(array: JSONArray) = List(array.length()) { array.getString(it) }

    /** The model's indexer for the characters the fixture uses (all others unknown). */
    private val indexer = IntArray(65_536) { -1 }.also { table ->
        val slice = fixture.getJSONObject("indexer")
        slice.keys().forEach { table[it.toInt()] = slice.getInt(it) }
    }

    private fun sha256(values: FloatArray): String {
        val buffer = ByteBuffer.allocate(values.size * 4).order(ByteOrder.LITTLE_ENDIAN)
        buffer.asFloatBuffer().put(values)
        return MessageDigest.getInstance("SHA-256").digest(buffer.array()).joinToString("") { "%02x".format(it) }
    }

    @Test
    fun cleaningIsTheDesktops() {
        for (case in objects("clean")) assertEquals(case.getString("text"), case.getString("cleaned"), SupertonicText.clean(case.getString("text")))
    }

    @Test
    fun theSpeedOfAChunkIsTheDesktops() {
        for (case in objects("speed")) assertEquals(case.getString("text"), case.getDouble("speed"), SupertonicText.speedFor(case.getString("text")), 0.0)
    }

    @Test
    fun characterIdsAreTheDesktops() {
        for (case in objects("ids")) assertArrayEquals(case.getString("cleaned"), longs(case.getJSONArray("ids")), SupertonicText.ids(case.getString("cleaned"), indexer))
    }

    @Test
    fun aParagraphIsCutSeededAndPausedLikeTheDesktop() {
        for (paragraph in objects("paragraphs")) {
            val text = paragraph.getString("text")
            val origin = paragraph.optString("origin").takeIf { !paragraph.isNull("origin") }
            val (_, units) = VieneuUnits.units(text, SupertonicText.MAX_CHARS, origin)
            val wanted = paragraph.getJSONArray("units").let { array -> List(array.length()) { array.getJSONObject(it) } }
            assertEquals(text, wanted.size, units.size)
            for ((unit, want) in units.zip(wanted)) {
                assertEquals(text, want.getInt("first"), unit.first)
                assertEquals(text, want.getInt("last"), unit.last)
                assertEquals(text, strings(want.getJSONArray("pieces")), unit.pieces)
                assertEquals(want.getLong("seed"), VieneuSpeaker.seedOf(SupertonicVoices.PREFIX, paragraph.getString("voice"), unit.pieces.joinToString(" ")))
                // the normalised text is sea-g2p's (SeaG2pParityTest checks that reader); from it on, the phone's own steps
                val spoken = want.getString("normalized")
                assertEquals(spoken, want.getDouble("speed"), SupertonicText.speedFor(spoken), 0.0)
                assertEquals(spoken, want.getString("cleaned"), SupertonicText.clean(spoken))
            }
        }
    }

    @Test
    fun theStartNoiseIsNumpysLegacyStream() {
        for (case in objects("rng")) {
            val noise = NumpyRandomState(case.getLong("seed")).standardNormalFloats(case.getInt("count"))
            assertArrayEquals(floats(case.getJSONArray("head")), noise.copyOf(16), 0f)
            assertEquals(case.getString("sha256"), sha256(noise))
        }
    }

    @Test
    fun theLoudnessRaiseIsTheDesktops() {
        for (case in objects("louder")) assertArrayEquals(floats(case.getJSONArray("out")), SupertonicText.louder(floats(case.getJSONArray("wave"))), 0f)
    }

    @Test
    fun voiceStylesAreReadAsTheDesktopReadsThem() {
        val model = System.getenv("ABOOK_SUPERTONIC_MODEL")?.let(::File)
        assumeTrue("ABOOK_SUPERTONIC_MODEL not set (the emulator checks this in SupertonicBenchTest#parity)", model != null && model.isDirectory)
        val styles = fixture.getJSONObject("styles")
        for (name in SupertonicVoices.NAMES) {
            val style = SupertonicEngine.readStyle(File(model, "voice_styles/$name.json"))
            val want = styles.getJSONObject(name)
            assertArrayEquals(longs(want.getJSONObject("style_ttl").getJSONArray("dims")), style.ttlShape)
            assertArrayEquals(longs(want.getJSONObject("style_dp").getJSONArray("dims")), style.dpShape)
            assertEquals(name, want.getJSONObject("style_ttl").getString("sha256"), sha256(style.ttl))
            assertEquals(name, want.getJSONObject("style_dp").getString("sha256"), sha256(style.dp))
        }
        assertTrue(styles.length() == SupertonicVoices.NAMES.size)
    }
}
