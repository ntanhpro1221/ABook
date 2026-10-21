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
        val live = LocalLive(target, out, tokens, units, 1.0, { now })
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
    fun aListenerWithNoSoundLeftHearsTheFirstUnitAtOnceAndTheClipStaysTheSame() {
        val (plain, _) = read("plain.wav", null)
        var now = 0L
        val target = Target()
        val out = File(dir, "dry.wav")
        val (tokens, units) = VieneuUnits.units(text, 140)
        val live = LocalLive(target, out, tokens, units, 1.0, { now }, reach = 0L) { _, _ -> error("nothing to wait for") }
        val tier = FakeTier()
        val waves = ArrayList<FloatArray>()
        for ((index, unit) in units.withIndex()) {
            val wave = tier.infer(phonemize(unit.pieces), preset, 0).also { waves += it }
            now += (2.5 * wave.size / 24_000 * 1e9).toLong() // 2.5 times slower than real time: the old rule would hold everything
            live.unit(wave, 24_000, phonemize(unit.pieces))
            if (index == 0) assertEquals("holding it back only makes the silence longer", listOf("format", "grew"), target.events)
        }
        val (joined, _) = VieneuAudio.join(waves, 24_000, units.dropLast(1).map { VieneuAudio.gapAfter(phonemize(it.pieces)) })
        live.finish(joined, 24_000)
        assertArrayEquals("the final file does not change by one byte", plain.readBytes(), out.readBytes())
    }

    @Test
    fun theHeldUnitsGoOutWhenTheListenerRunsOutOfSoundBetweenTwoUnits() {
        var now = 0L
        val target = Target()
        val (tokens, units) = VieneuUnits.units(text, 140)
        val waits = ArrayList<Pair<Long, () -> Unit>>()
        val live = LocalLive(target, File(dir, "reach.wav"), tokens, units, 1.0, { now }, reach = 30_000_000_000L) { ms, task -> waits += ms to task }
        val tier = FakeTier()
        val first = tier.infer(phonemize(units[0].pieces), preset, 0)
        now = 10_000_000_000L // read slowly: the old rule holds it
        live.unit(first, 24_000, phonemize(units[0].pieces))
        assertTrue("the listener still has sound", target.events.isEmpty())
        assertEquals("one wake-up, at the moment the sound runs out", listOf(20_000L), waits.map { it.first })
        now = 30_000_000_000L
        waits.single().second()
        assertEquals(listOf("format", "grew"), target.events)
        live.failed(VoiceException("x"))
        waits.single().second()
        assertEquals("nothing after the read is over", listOf("format", "grew", "failed"), target.events)
    }

    @Test
    fun aLateWakeUpAfterTheClipIsDoneSendsNothing() {
        val target = Target()
        val (tokens, units) = VieneuUnits.units(text, 140)
        val waits = ArrayList<() -> Unit>()
        var now = 0L
        val live = LocalLive(target, File(dir, "late.wav"), tokens, units, 1.0, { now }, reach = 50_000_000_000L) { _, task -> waits += task }
        val tier = FakeTier()
        val waves = units.map { tier.infer(phonemize(it.pieces), preset, 0) }
        for ((index, wave) in waves.withIndex()) {
            now += (2.5 * wave.size / 24_000 * 1e9).toLong()
            live.unit(wave, 24_000, phonemize(units[index].pieces))
        }
        val (joined, _) = VieneuAudio.join(waves, 24_000, units.dropLast(1).map { VieneuAudio.gapAfter(phonemize(it.pieces)) })
        live.finish(joined, 24_000)
        waits.forEach { it() }
        assertEquals("read before the sound ran out: held to the last unit as before, nothing after the end", listOf("format", "grew", "done"), target.events)
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
            assertEquals("its first unit IS the clip: no sooner sound", null, LocalLive.here(out) { VieneuUnits.units("Trời hôm nay đẹp quá.", 140) })
            assertTrue(LocalLive.here(out) { VieneuUnits.units(text, 140) } != null)
        }
        assertEquals("no listener waiting", null, LocalLive.here(out) { VieneuUnits.units(text, 140) })
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

    @Test
    fun theOpeningHoldWaitsForTheStreamToStartNotForTheWholeParagraph() {
        // Nano a65: 310 ký tự cắt 140 + 140 + 30, máy làm 0,0132 s mỗi ký tự: khúc đầu là đủ để bắt đầu luồng.
        assertEquals(140, LocalLive.charsBeforeStart(listOf(140, 140, 30), 0.0132))
        // máy chậm (làm bằng thời gian tiếng, r = 1): một khúc chưa đủ để theo kịp, hai khúc thì đủ.
        assertEquals(200, LocalLive.charsBeforeStart(listOf(100, 100, 100), LocalLive.AUDIO_PER_CHAR))
        assertEquals("một khúc: không có luồng, đọc cả đoạn", 293, LocalLive.charsBeforeStart(listOf(293), 0.0132))
        assertEquals("không bao giờ theo kịp: tới khúc cuối", 410, LocalLive.charsBeforeStart(listOf(10, 400), LocalLive.AUDIO_PER_CHAR))
        assertTrue("nghe nhanh hơn thì phải đọc nhiều hơn mới bắt đầu", LocalLive.charsBeforeStart(listOf(100, 100, 100), 0.04, speed = 2.0) > LocalLive.charsBeforeStart(listOf(100, 100, 100), 0.04))
        assertEquals("Supertonic: khúc đầu được cắt ngắn", SupertonicText.units(this.text, null, null).second.map { it.first to it.last }, LocalLive.unitsOf("supertonic:F1#fast5", this.text, null, null)!!.second.map { it.first to it.last })
        assertEquals(VieneuUnits.units(this.text, 140).second.size, LocalLive.unitsOf("vieneu:nano/Đức Trí", this.text, null, null)!!.second.size)
        assertEquals(VieneuUnits.units(this.text, 256).second.size, LocalLive.unitsOf("vieneu:turbo/x", this.text, null, null)!!.second.size)
        assertEquals(null, LocalLive.unitsOf("edge:vi-VN-HoaiMyNeural", this.text, null, null))
        val sentence = "Một hai ba bốn năm sáu bảy tám chín mười mười một mười hai mười ba mười bốn mười lăm mười sáu mười bảy."
        val text = "$sentence $sentence"
        val start = LocalLive.charsBeforeStreamStarts("vieneu:nano/x", text, null, null, 0.0132)
        assertTrue("đoạn nhiều khúc: giữ tới khúc đầu", start in 1 until text.length)
        assertEquals("tốc độ giọng chưa đo: cả đoạn", text.length, LocalLive.charsBeforeStreamStarts("vieneu:nano/x", text, null, null, null))
        assertEquals("giọng không đọc theo khúc: cả đoạn", text.length, LocalLive.charsBeforeStreamStarts("edge:x", text, null, null, 0.0132))
        assertTrue("Supertonic: khúc đầu cắt ngắn nên đoạn 212 ký tự cũng có luồng", LocalLive.charsBeforeStreamStarts("supertonic:F1", text, null, null, 0.0132) in 1 until text.length)
    }
}
