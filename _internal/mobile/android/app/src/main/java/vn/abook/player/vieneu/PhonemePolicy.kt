package vn.abook.player.vieneu

import java.util.Locale
import vn.abook.player.BuildConfig
import vn.abook.player.readaloud.EnglishPolicy
import vn.abook.player.readaloud.EnglishWords
import vn.abook.player.readaloud.Names

/** Corrections after sea-g2p normalization, shared with readaloud/phoneme_policy.py. */
object PhonemePolicy {
    private val gi = Regex("(?<![\\p{L}\\p{N}_])gi(?![\\p{L}\\p{N}_])", RegexOption.IGNORE_CASE)
    private val bareZ = Regex("(?<!\\S)z(?=[.,!?;:…]*(?:\\s|$))")
    private const val VOWELS = "aeiouyæɐɑɒɔəɘɛɜɤɯɵøœʉʊʌɪɨɚɝᵻᵿ"
    private val interjection = Regex("(?<![\\p{L}\\p{N}_'-])([A-Za-z]+(?:['’][A-Za-z]+)*)[!?]")
    private val nuclei = Regex("[$VOWELS]+")
    private val stressedDiphthong = Regex("^(wˈ)(e(?=ɪ)|o(?=ʊ)|a(?=[ɪʊ])|ɔ(?=ɪ))")
    private val syllabicO = Regex("o[.,!?;:…]*")
    private val letterO = Regex("ˈo([.,!?;:…]*)")

    /** A standalone Vietnamese gi has a vowel; sea-g2p currently drops its /i/. */
    fun repairSyllabicGi(text: String, phonemes: String): String {
        val count = gi.findAll(text).count()
        if (count == 0 || count != bareZ.findAll(phonemes).count()) return phonemes
        return bareZ.replace(phonemes, "zˈi")
    }

    fun repairSyllabicO(text: String, phonemes: String): String {
        val words = text.split(Regex("\\s+")).filter { it.isNotEmpty() }
        val phones = phonemes.split(Regex("\\s+")).filter { it.isNotEmpty() }
        if (words.size != phones.size) return phonemes
        var changed = false
        val out = words.indices.map { i ->
            if (syllabicO.matches(words[i]) && letterO.matches(phones[i])) {
                changed = true
                "ˈɔ" + phones[i].substring(2)
            } else phones[i]
        }
        return if (changed) out.joinToString(" ") else phonemes
    }

    /** Preserve short English cries at code switches without splitting or changing words. */
    fun emphasizeEnglishInterjections(text: String, phonemes: String, g2p: (String) -> String): String {
        var out = phonemes
        val extra = BuildConfig.DIRECT_ENGLISH_WORDS.split(" ")
        for (match in interjection.findAll(text)) {
            val word = match.groupValues[1].lowercase(Locale.ROOT)
            if ((word !in EnglishWords.ALL && word !in extra) || EnglishPolicy.vietnamese(word) || word in Names.JAPANESE_COMMON) continue
            val original = g2p(word).trim()
            if (original.isEmpty() || nuclei.findAll(original.replace("ː", "")).count() > 2) continue
            var strong = original.replace('ˌ', 'ˈ')
            val vowel = stressedDiphthong.find(strong)
            if (vowel != null) strong = strong.replaceRange(vowel.range, vowel.value + "ː")
            if (strong != original) out = Regex("(?<!\\S)" + Regex.escape(original) + "(?=[!?])").replace(out) { strong }
        }
        return out
    }
}
