package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.readaloud.WordTokens

/** Paragraph -> clip with a fake engine: one take per unit, seeded from voice + text, the desktop's pauses, one word timing per shown word. */
class VieneuSpeakerTest {
    private class FakeTier : VieneuTier {
        override val rate = 24_000
        val calls = ArrayList<Pair<String, Long>>()
        override fun infer(phonemes: String, preset: VieneuPreset, seed: Long): FloatArray {
            calls.add(phonemes to seed)
            // 50 ms of silence, then "speech" as long as the phonemes, then 50 ms of silence
            val speech = phonemes.length * 240
            return FloatArray(1200 + speech + 1200) { if (it in 1200 until 1200 + speech) 0.3f else 0f }
        }
        override fun close() = Unit
    }

    private val preset = VieneuPreset("Adam", "male", FloatArray(192), null, FloatArray(50 * 256))

    @Test
    fun aParagraphBecomesOneClipWithAWordTimingPerShownWord() {
        val tier = FakeTier()
        val text = "Trời hôm nay đẹp quá. Cô gái đứng bên cửa sổ,  lặng lẽ nhìn mưa rơi suốt buổi chiều hôm ấy, rồi cô đứng dậy đi ra phía cửa sau của ngôi nhà nhỏ."
        val spoken = VieneuSpeaker { pieces -> pieces.joinToString(" ").lowercase() }.speak("nano", tier, "Adam", preset, text)
        val (_, units) = VieneuUnits.units(text, 140)
        assertEquals(units.size, tier.calls.size)
        assertEquals(units.map { VieneuSpeaker.seedOf("nano", "Adam", it.pieces.joinToString(" ")) }, tier.calls.map { it.second })
        assertEquals(WordTokens.count(text), spoken.words.size)
        assertEquals(spoken.samples.size * 1000L / 24_000, spoken.durationMs)
        var previous = 0L
        for (word in spoken.words) {
            assertTrue(word.start >= previous && word.end >= word.start && word.end <= spoken.durationMs)
            previous = word.start
        }
        // each unit's words lie inside its own span of the clip
        var index = 0
        for ((unit, span) in units.zip(spoken.spans)) {
            for (k in unit.first..unit.last) {
                val word = spoken.words[index++]
                assertTrue("$k", word.start >= span[0] * 1000L / 24_000 && word.end <= span[1] * 1000L / 24_000 + 1)
            }
        }
    }

    @Test
    fun aUnitEndingOnACommaGetsTheShortPauseAndASentenceTheLongOne() {
        val tier = FakeTier()
        val speaker = VieneuSpeaker { pieces -> pieces.joinToString(" ") }
        val first = "Một hai ba bốn năm sáu bảy tám chín mười mười một mười hai mười ba mười bốn mười lăm mười sáu mười bảy mười tám"
        val second = "hai chín ba mươi ba mốt ba hai ba ba ba bốn ba lăm ba sáu ba bảy."
        val comma = speaker.speak("nano", tier, "Adam", preset, "$first, $second")
        val sentence = speaker.speak("nano", FakeTier(), "Adam", preset, "$first. ${second.replaceFirstChar { it.uppercase() }}")
        fun gap(spoken: VieneuSpeaker.Spoken) = spoken.spans[1][0] - spoken.spans[0][1] + 1200 + 1200 // inserted + silent edges
        assertEquals(2, comma.spans.size)
        assertEquals((0.30 * 24_000).toInt(), gap(comma))
        assertEquals((0.50 * 24_000).toInt(), gap(sentence))
    }

    @Test
    fun aUnitWithNothingToReadKeepsItsWordsInPlace() {
        val tier = FakeTier()
        val text = "*** *** *** *** *** *** ***. Đoạn này có chữ thật để đọc, khá dài để thành một khúc riêng biệt, vì cả đoạn vượt quá giới hạn của giọng Nano, thêm vài chữ."
        val spoken = VieneuSpeaker { pieces -> if (pieces.joinToString(" ").startsWith("***")) "" else "ʔa1 ʔa1." }.speak("nano", tier, "Adam", preset, text)
        assertEquals(2, spoken.spans.size)
        assertEquals(WordTokens.count(text), spoken.words.size)
        assertTrue("the silent unit's words sit at its place", spoken.words.take(7).all { it.start == 0L && it.end == 0L })
        assertEquals("only the unit with words is synthesized", 1, tier.calls.size)
    }
}
