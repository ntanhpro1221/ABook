package vn.abook.player.readaloud

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.vieneu.NumpyRandomState
import vn.abook.player.vieneu.VieneuSpeaker
import vn.abook.player.vieneu.VieneuUnits

/** Paragraph -> clip with a fake engine: one take per unit of normalised text, seeded from voice + shown pieces, at the chunk's speed, raised
 *  4 dB, the desktop's pauses, one word timing per shown word. */
class SupertonicSpeakerTest {
    private class FakeEngine : SupertonicSynth {
        override val sampleRate = 44_100
        val calls = ArrayList<Triple<String, Double, Double>>()
        override fun infer(text: String, name: String, random: NumpyRandomState, speed: Double): FloatArray {
            calls.add(Triple(text, random.standardNormal(), speed))
            if (text.isBlank()) return FloatArray(0)
            // 50 ms of silence, then "speech" as long as the text, then 50 ms of silence
            val speech = text.length * 441
            return FloatArray(2205 + speech + 2205) { if (it in 2205 until 2205 + speech) 0.1f else 0f }
        }
    }

    @Test
    fun aParagraphBecomesOneLouderClipWithAWordTimingPerShownWord() {
        val engine = FakeEngine()
        val text = "Ngày 12/03, trời mưa. Cô gái đứng bên cửa sổ, lặng lẽ nhìn mưa rơi suốt buổi chiều hôm ấy."
        val spoken = SupertonicSpeaker { pieces -> pieces.joinToString(" ").lowercase() }.speak(engine, "F1", text)
        val (_, units) = VieneuUnits.units(text, SupertonicText.MAX_CHARS)
        assertEquals(units.size, engine.calls.size)
        for ((unit, call) in units.zip(engine.calls)) {
            val seed = VieneuSpeaker.seedOf("supertonic", "F1", unit.pieces.joinToString(" "))
            assertEquals(NumpyRandomState(seed).standardNormal(), call.second, 0.0)
            assertEquals(unit.pieces.joinToString(" ").lowercase(), call.first)
            assertEquals(SupertonicText.speedFor(call.first), call.third, 0.0)
        }
        assertEquals("raised 4 dB", 0.1f * Math.pow(10.0, 4.0 / 20).toFloat(), spoken.samples.max(), 1e-6f)
        assertEquals(WordTokens.count(text), spoken.words.size)
        assertEquals(spoken.samples.size * 1000L / 44_100, spoken.durationMs)
        var previous = 0L
        for (word in spoken.words) {
            assertTrue(word.start >= previous && word.end >= word.start && word.end <= spoken.durationMs)
            previous = word.start
        }
    }

    /** The book's own readings ([Readings]) come after the names, as on the computer (`test_the_books_own_readings_come_after_the_names`). */
    @Test
    fun theBooksOwnReadingsComeAfterTheNames() {
        val engine = FakeEngine()
        val text = "Haruto gặp Kyouko."
        val spoken = SupertonicSpeaker { pieces -> pieces.joinToString(" ").lowercase() }.speak(engine, "F1", text, "ja", mapOf("Haruto" to "Ha-ru-to"))
        assertEquals(listOf("ha-ru-to gặp ki-âu-cô."), engine.calls.map { it.first })
        assertEquals(WordTokens.count(text), spoken.words.size)
    }

    @Test
    fun aUnitEndingOnACommaGetsTheShortPauseAndASentenceTheLongOne() {
        val first = "Một hai ba bốn năm sáu bảy tám chín mười ".repeat(7).trim()
        val second = "hai chín ba mươi ba mốt ba hai ba ba ba bốn ba lăm ba sáu ba bảy."
        val speaker = SupertonicSpeaker { pieces -> pieces.joinToString(" ") }
        val comma = speaker.speak(FakeEngine(), "F1", "$first, $second")
        val sentence = speaker.speak(FakeEngine(), "F1", "$first. ${second.replaceFirstChar { it.uppercase() }}")
        fun gap(spoken: VieneuSpeaker.Spoken) = spoken.spans[1][0] - spoken.spans[0][1] + 2205 + 2205 // inserted + silent edges
        assertEquals(2, comma.spans.size)
        assertEquals((0.30 * 44_100).toInt(), gap(comma))
        assertEquals((0.50 * 44_100).toInt(), gap(sentence))
    }
}
