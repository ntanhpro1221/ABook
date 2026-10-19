package vn.abook.player.readaloud

import org.junit.After
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.vieneu.VieneuAudio
import vn.abook.player.vieneu.VieneuPreset
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuTier
import vn.abook.player.vieneu.VieneuUnits
import java.io.File

/** Local voices stream unit by unit ([LocalLive]; desktop tests/test_readaloud_local_stream.py): the final file is byte-identical to the one made without
 *  streaming, the stream is its samples, words per unit, play waits on a slow machine, a clip-wide lift ends with the final samples in place, and a one-unit
 *  paragraph does not stream. */
class LocalLiveTest {
    private val dir = java.nio.file.Files.createTempDirectory("local-live").toFile()

    @After
    fun cleanUp() {
        dir.deleteRecursively()
    }

    private class FakeTier : VieneuTier {
        override val rate = 24_000
        val calls = ArrayList<String>()
        override fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray {
            calls.add(phonemes)
            val speech = phonemes.length * 240
            return FloatArray(1200 + speech + 1200) { if (it in 1200 until 1200 + speech) 0.3f * kotlin.math.sin(it / 3f) else 0f }
        }
        override fun close() = Unit
    }

    /** [LiveClips.Target] that keeps what it was told; [snapshot] = the file's bytes at each [grew]. */
    private class Target(val speed: Float = 1f) : LiveClips.Target {
        val events = ArrayList<String>()
        val snapshots = ArrayList<ByteArray>()
        val words = ArrayList<Triple<List<Span>, Long, Long>>()
        var durationOf: ((Long) -> Long)? = null
        var failure: Exception? = null
        override fun accepting() = !events.contains("grew")
        override fun format(durationMs: (Long) -> Long) {
            durationOf = durationMs
            events += "format"
        }
        override fun speed() = speed
        override fun grew(file: File, total: Long) {
            snapshots += file.readBytes().copyOf(total.toInt())
            events += "grew"
        }
        override fun words(words: List<Span>, durationMs: Long, heardMs: Long) {
            this.words += Triple(words, durationMs, heardMs)
        }
        override fun done(total: Long) {
            events += "done"
        }
        override fun failed(error: Exception) {
            failure = error
            events += "failed"
        }
    }

    private val preset = VieneuPreset("Adam", "male", FloatArray(192), null, FloatArray(50 * 256))
    private val text = "Trời hôm nay đẹp quá. Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi suốt buổi chiều hôm ấy, rồi cô đứng dậy đi ra phía cửa sau của ngôi nhà nhỏ. " +
        "Ngoài vườn, mấy cây cau nghiêng mình trong gió, lá xào xạc như ai đang thì thầm kể chuyện ngày xưa cho nhau nghe."
    private val phonemize = { pieces: List<String> -> pieces.joinToString(" ").lowercase() }

    /** The voice's synthesize (VieneuVoices.synthesize) with or without a listener: the final file, the spoken clip. */
    private fun read(name: String, target: LiveClips.Target?, lift: (FloatArray, Int) -> FloatArray = { samples, _ -> samples }, clock: () -> Long = System::nanoTime):
        Pair<File, VieneuSpeaker.Spoken> {
        val out = File(dir, name)
        val live = target?.let {
            val (tokens, units) = VieneuUnits.units(text, 140)
            LocalLive(it, out, tokens, units, it.speed().toDouble(), clock)
        }
        val spoken = VieneuSpeaker(phonemize).speak("nano", FakeTier(), "Adam", preset, text, live = live)
        val final = lift(spoken.samples, spoken.rate)
        if (live != null) live.finish(final, spoken.rate) else VieneuAudio.writeWav(final, spoken.rate, out)
        return out to spoken
    }

    @Test
    fun theStreamedClipIsByteIdenticalAndTheStreamIsItsSamples() {
        val (plain, _) = read("plain.wav", null)
        val target = Target()
        val (streamed, spoken) = read("streamed.wav", target)
        assertArrayEquals("the final file does not change by one byte", plain.readBytes(), streamed.readBytes())
        val (_, units) = VieneuUnits.units(text, 140)
        assertTrue(units.size > 1)
        assertEquals(listOf("format") + List(units.size) { "grew" } + "done", target.events)
        val last = target.snapshots.last()
        assertArrayEquals("growing header: sizes unknown", VieneuAudio.wavHeader(24_000, null), last.copyOf(44))
        assertArrayEquals("the stream is exactly the clip's samples", plain.readBytes().copyOfRange(44, plain.length().toInt()), last.copyOfRange(44, last.size))
        assertEquals(spoken.durationMs, target.durationOf!!(last.size.toLong()))
        val (words, duration, heard) = target.words.last()
        assertEquals("the last unit's words are the final words", spoken.words, words)
        assertEquals(duration, heard)
        val (first, firstDuration, _) = target.words.first()
        assertEquals(WordTokens.count(text), first.size)
        assertTrue("words not reached yet wait at the end of what is there", first.all { it.end <= firstDuration })
    }

    @Test
    fun aSlowMachineHoldsTheUnitsUntilTheRestWillKeepUp() {
        var now = 0L
        val target = Target()
        val out = File(dir, "slow.wav")
        val (tokens, units) = VieneuUnits.units(text, 140)
        val live = LocalLive(target, out, tokens, units, 1.0) { now }
        val tier = FakeTier()
        for ((index, unit) in units.withIndex()) {
            val wave = tier.infer(phonemize(unit.pieces), preset, 0)
            now += (2.5 * wave.size / 24_000 * 1e9).toLong() // 2.5 times slower than real time
            live.unit(wave, 24_000, phonemize(unit.pieces))
            if (index < units.lastIndex) assertTrue("nothing plays yet: it would stop halfway", target.events.isEmpty())
        }
        assertEquals(listOf("format", "grew"), target.events)
    }

    @Test
    fun theStartRuleMatchesTheDesktop() {
        assertTrue(LocalLive.readyToPlay(3.0, 1.0, 30, listOf(30, 60)))
        assertTrue(LocalLive.readyToPlay(3.0, 9.0, 30, emptyList()))
        assertFalse(LocalLive.readyToPlay(3.0, 6.0, 30, listOf(30)))
        assertFalse(LocalLive.readyToPlay(3.0, 2.8, 30, listOf(30)))
        assertTrue(LocalLive.readyToPlay(3.0, 2.0, 30, listOf(30)))
        assertFalse(LocalLive.readyToPlay(3.0, 2.0, 30, listOf(30), speed = 1.5))
        assertFalse(LocalLive.readyToPlay(1.0, 0.5, 10, listOf(10, 200)))
        assertFalse(LocalLive.readyToPlay(0.0, 0.5, 10, listOf(10)))
    }

    @Test
    fun aClipLiftedAsAWholeEndsWithTheFinalSamplesInPlace() {
        val louder = { samples: FloatArray, _: Int -> FloatArray(samples.size) { samples[it] * 2f } }
        val (plain, _) = read("plain.wav", null, louder)
        val target = Target()
        val (streamed, _) = read("streamed.wav", target, louder)
        assertArrayEquals(plain.readBytes(), streamed.readBytes())
        val streamedPcm = target.snapshots.last().let { it.copyOfRange(44, it.size) }
        assertFalse("streamed before the lift was known", streamedPcm.contentEquals(plain.readBytes().copyOfRange(44, plain.length().toInt())))
    }

    @Test
    fun aOneUnitParagraphDoesNotStream() {
        val out = File(dir, "one.wav")
        LiveClips.receiving(Target()) {
            assertEquals("its first unit IS the clip: no sooner sound", null, LocalLive.here(out, "Trời hôm nay đẹp quá.", 140, null, null))
            assertTrue(LocalLive.here(out, text, 140, null, null) != null)
        }
        assertEquals("no listener waiting", null, LocalLive.here(out, text, 140, null, null))
    }

    @Test
    fun aFailureAfterTheStartIsToldAndBeforeItIsNot() {
        val target = Target()
        val (tokens, units) = VieneuUnits.units(text, 140)
        val live = LocalLive(target, File(dir, "f.wav"), tokens, units)
        live.failed(VoiceException("x"))
        assertTrue(target.events.isEmpty())
        live.unit(FakeTier().infer("abc.", preset, 0), 24_000, "abc.")
        live.failed(VoiceException("Đã bỏ đoạn này.", reason = "cancelled"))
        assertEquals("failed", target.events.last())
    }
}
