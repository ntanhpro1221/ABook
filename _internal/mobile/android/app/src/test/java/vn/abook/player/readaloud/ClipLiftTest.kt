package vn.abook.player.readaloud

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.MusicRender
import vn.abook.player.vieneu.VieneuAudio
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64

/** Bù theo clip cho giọng VieNeu và Supertonic ([ClipLift]) so với máy tính (loudness.py) trên cùng clip: tests/fixtures/vieneu/android/lift.json. */
class ClipLiftTest {
    private val fixture = JSONObject(File("../../../tests/fixtures/vieneu/android/lift.json").readText(Charsets.UTF_8))
    private val params = MusicRender.Params.parse(JSONObject(File("../../../abook/webui/assets/music_mix.json").readText()))
    private val rate = fixture.getInt("rate")
    private val cases = fixture.getJSONObject("cases")

    private fun pcm(b64: String): ShortArray {
        val bytes = Base64.getDecoder().decode(b64)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        return ShortArray(bytes.size / 2) { buffer.short }
    }

    private fun samples(name: String): FloatArray = pcm(cases.getJSONObject(name).getString("pcm")).let { p -> FloatArray(p.size) { p[it] / 32767f } }

    @Test
    fun meterAndPeakReadLikeTheComputer() {
        assertTrue(cases.length() >= 8)
        for (name in cases.keys()) {
            val case = cases.getJSONObject(name)
            val x = samples(name)
            val lufs = ClipLift.clipLufs(x, rate)
            if (case.isNull("lufs")) assertNull(name, lufs) else assertEquals(name, case.getDouble("lufs"), lufs!!, 0.02)
            assertEquals(name, case.getDouble("truePeak"), ClipLift.truePeakDbtp(x, params), 0.05)
        }
    }

    @Test
    fun liftsTheSameDbAndTheSameSamples() {
        for (name in cases.keys()) {
            val case = cases.getJSONObject(name)
            val voice = case.getString("voice")
            val x = samples(name)
            assertEquals(name, case.getDouble("liftDb"), ClipLift.liftDb(voice, x, rate, params), 0.0)
            val made = ClipLift.lifted(voice, x, rate, params)
            if (case.isNull("lifted")) {
                assertSame(name, x, made)
                continue
            }
            val want = pcm(case.getString("lifted"))
            val wav = VieneuAudio.wavBytes(made, rate)
            val buffer = ByteBuffer.wrap(wav, 44, wav.size - 44).order(ByteOrder.LITTLE_ENDIAN)
            val got = ShortArray(want.size) { buffer.short }
            assertEquals(name, want.size, (wav.size - 44) / 2)
            for (i in want.indices) assertTrue("$name[$i] ${want[i]} vs ${got[i]}", Math.abs(want[i] - got[i]) <= 1)
        }
    }

    @Test
    fun withoutThePeakTableNothingIsLifted() {
        val x = samples("very_quiet")
        assertEquals(0.0, ClipLift.liftDb(cases.getJSONObject("very_quiet").getString("voice"), x, rate, null), 0.0)
    }

    @Test
    fun onlyMeasuredVieneuAndSupertonicVoicesAreLiftedAndKeyedApart() {
        assertTrue(ClipLift.lifts("vieneu:turbo/Đức Trí"))
        assertTrue(!ClipLift.lifts("vieneu:turbo/Giọng chưa đo") && !ClipLift.lifts("edge:vi-VN-HoaiMyNeural") && !ClipLift.lifts("supertonic:X9"))
        assertTrue(ClipLift.lifts("supertonic:F1") && ClipLift.lifts("supertonic:M5"))
        // both Supertonic tiers lift by the one level of the bare id: the cache (and the reader) work on the id without its tier tag
        assertTrue(!ClipLift.lifts("supertonic:F1#fast5") && ClipLift.lifts(VoiceSpeed.split("supertonic:F1#fast5").first))
        assertEquals(ClipLift.TAG, ClipCache.reading("supertonic:F3", "Hả?", null))
        assertEquals("ld1", ClipLift.TAG)
        assertEquals(ClipCache.reading("vieneu:turbo/Đức Trí", "Ừ.", null), ClipLift.TAG)
        assertEquals("", ClipCache.reading("device:vi-vn-x-gft-local", "Ừ.", null))
    }

    @Test
    fun theVoiceGainTableStillGivesTheOldGains() {
        assertEquals(-1.7, VoiceGain.db("edge:vi-VN-HoaiMyNeural"), 0.0)
        assertEquals(-0.9, VoiceGain.db("vieneu:turbo/Adam bựa"), 0.0)
        assertEquals(-2.3, VoiceGain.db("vieneu:nano/Minh Quân"), 0.0)
        assertEquals(0.0, VoiceGain.db("vieneu:turbo/Mai Anh"), 0.0)
        assertEquals(0.0, VoiceGain.db("vieneu:turbo/Phạm Tuyên"), 0.0)
        assertEquals(0.0, VoiceGain.db("device:vi-vn-x-gft-local"), 0.0)
        for (voice in listOf("F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5")) assertEquals(voice, 0.0, VoiceGain.db("supertonic:$voice"), 0.0) // every level <= -20 LUFS: only the clip lift changes
    }
}
