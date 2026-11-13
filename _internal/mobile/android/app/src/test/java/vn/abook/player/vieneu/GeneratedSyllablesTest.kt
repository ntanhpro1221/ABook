package vn.abook.player.vieneu

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import vn.abook.player.readaloud.BookReadings

/** Always-run requirements; no JNI, dictionary, model or assumeTrue. */
class GeneratedSyllablesTest {
    private val phones = mapOf("tâu" to "t̪ˈə1w", "tấu" to "t̪ˈəɜw", "cai" to "kˈaːj", "cái" to "kˌaːɜj",
        "ten" to "tˈɛn", "tén" to "t̪ˈɛɜn")
    private val fake: (String) -> String = { phones[it] ?: error("Unexpected probe: $it") }

    @Test fun nativeLevelAndStressSurviveTheProbe() {
        assertEquals("t̪ˈə1w", PhonemePolicy.levelProbe("tâu", fake))
        assertEquals("kˈaːj", PhonemePolicy.levelProbe("cai", fake))
    }

    @Test fun levelToneStopSyllablesAreNeverProbed() {
        // dat/bach/cap/Cat: Vietnamese p/t/c/ch codas carry only sac or nang tone.
        for (word in listOf("dat", "bach", "cap", "Cat")) assertEquals(null, PhonemePolicy.levelProbe(word, fake))
    }

    @Test fun generatedRestorationPreservesExactNativeLevel() {
        assertEquals("t̪ˈə1w.", PhonemePolicy.restoreGeneratedSyllables("tâu", "tâu.", "t̪ˈə1w.", fake, "Tou"))
    }

    @Test fun rulingsIdentifyOccurrencesRatherThanSharedSpellings() {
        assertEquals(setOf(0), PhonemePolicy.ruledVietnameseWords("An nói: I want an apple.",
            rulings = PhonemePolicy.Rulings(names = setOf("an"))))
        assertEquals(setOf(5), PhonemePolicy.ruledVietnameseWords("I can not do it, Can.",
            rulings = PhonemePolicy.Rulings(names = setOf("can"))))
    }

    @Test fun phoneTextRoutingUsesTransportedRulings() {
        val text = "I can not do it, Can."
        val readings = BookReadings(emptyMap(), PhonemePolicy.Rulings(names = setOf("can")))
        val spoken = VieneuUnits.spokenTokens(text.split(" "), readings = readings, directEnglish = true).joinToString(" ")
        assertTrue(spoken, "<en>can</en>" in spoken)
        assertTrue(spoken, spoken.endsWith("Can."))
    }

    @Test fun oldEthAndCombiningVowelsUseModernVietnameseLetters() {
        for ((old, modern) in listOf("Ði" to "Đi", "Ðang" to "Đang", "Ðan" to "Đan", "Ðo\u0302ng" to "Đông")) {
            assertEquals(listOf(modern), VieneuUnits.spokenTokens(listOf(old), directEnglish = true))
        }
    }
}
