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
    private const val W = "\\p{L}\\p{N}_"
    private val spaces = Regex("\\s+")
    private val token = Regex("(<en>.*?</en>)|([$W]+(?:['’][$W]+)*)|([^$W\\s\\p{Z}])", RegexOption.IGNORE_CASE)
    private val capital = Regex("(?<![$W'’<>/])[A-Z][A-Za-z]*(?![$W'’])")
    private const val QUOTES = " \t\r\n\"'“”‘’«»()[]{}「」『』〈〉《》【】—–-*"
    private const val SENTENCE_END = ".!?…:;"
    private const val PHONEME_MARKS = ".,!?"
    private val readings = java.util.concurrent.ConcurrentHashMap<String, Pair<String, String>>()

    private class Shared {
        private val data = EnglishPolicy.sharedVietnamese
        private fun list(key: String): List<String> = data.getJSONArray(key).let { a -> (0 until a.length()).map(a::getString) }
        val words = list("words").toSet()
        val strong = list("strong").toSet()
        val beforeEnglish = list("before_english").toSet()
        val nouns = list("nouns").toSet()
        val echo = list("echo").toSet()
        val pairs = data.getJSONArray("pairs").let { a -> (0 until a.length()).map { a.getJSONArray(it).getString(0) to a.getJSONArray(it).getString(1) }.toSet() }
        val sentinels = list("sentinels")
        val listed = words + echo + pairs.flatMap { listOf(it.first, it.second) }
        val english = EnglishPolicy.context("only") + EnglishPolicy.context("function")
        val neverToneless = english + EnglishPolicy.context("weak") + EnglishPolicy.context("letters") + listed
        val find = Regex("(?<![$W'’])(?:" + listed.sorted().joinToString("|") + ")(?![$W'’])", RegexOption.IGNORE_CASE)
    }

    private val shared by lazy { Shared() }

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

    /** phoneme_policy.capitalised: ASCII words written with a capital inside a sentence, lower-cased - names, not prose. */
    fun capitalised(text: String): Set<String> {
        val found = mutableSetOf<String>()
        for (match in capital.findAll(text)) {
            val head = text.substring(0, match.range.first).trimEnd { it in QUOTES }
            if (head.isNotEmpty() && head.last() !in SENTENCE_END) found.add(match.value.lowercase(Locale.ROOT))
        }
        return found
    }

    private fun ascii(word: String) = word.all { it.code < 128 }

    /** phoneme_policy.vietnamese_shared: positions, among the listed shared words of normalized [text], of those the sentence proves Vietnamese. */
    fun vietnameseShared(text: String, capitals: Set<String> = emptySet()): List<Int> {
        val shared = shared
        val words = mutableListOf<String>()
        val joined = mutableListOf<Boolean>()  // no punctuation between this word and the one before
        val explicit = mutableListOf<Boolean>()
        var gap = true
        for (match in token.findAll(text)) {
            if (match.groups[3] != null) {
                gap = true
                continue
            }
            val tagged = match.groups[1]?.value
            words.add(if (tagged != null) "" else match.groups[2]!!.value.lowercase(Locale.ROOT))
            // Spelled letters ("<en>G M</en>") name something; only a tagged word proves an English phrase.
            explicit.add(tagged != null && tagged.substring(4, tagged.length - 5).split(spaces).any { it.length > 1 })
            joined.add(!gap)
            gap = false
        }
        val accented = words.any { !ascii(it) && EnglishPolicy.vietnamese(it) }
        val kinds = HashMap<Int, Char>()

        /** E explicit English, n a name, s listed, V Vietnamese, e certainly English, o anything else. */
        fun kind(index: Int): Char = kinds.getOrPut(index) {
            val word = words[index]
            when {
                explicit[index] -> 'E'
                word.isEmpty() || word in capitals -> 'n'
                word in shared.listed -> 's'
                !ascii(word) -> if (EnglishPolicy.vietnamese(word)) 'V' else 'o'
                accented && word.length > 1 && word !in shared.neverToneless && EnglishPolicy.vietnamese(word) -> 'V'  // "quay", "con", "ninh"
                word in shared.english || (word.all(Char::isLetter) && word in EnglishWords.ALL) -> 'e'
                else -> 'o'
            }
        }

        val listed = words.indices.filter { words[it] in shared.listed }
        val open = listed.filter { kind(it) == 's' }
        val proven = mutableSetOf<Int>()
        fun side(index: Int, step: Int): Int? {
            val other = index + step
            return if (other !in words.indices || !joined[maxOf(index, other)]) null else other
        }
        fun vietnameseAt(index: Int?) = index != null && (index in proven || kind(index) == 'V')

        var changed = true
        while (changed) {
            changed = false
            for (index in open) {
                if (index in proven) continue
                val word = words[index]
                val left = side(index, -1)
                val right = side(index, 1)
                val beside = listOf(left, right).map { if (it != null) kind(it) else ' ' }
                if ('E' in beside) continue
                var found = false
                if (word in shared.words) {
                    if (vietnameseAt(right)) found = !(word in shared.nouns && beside[0] == 'e')  // "Lost Day là", "Big Bang ấy"
                    else if (vietnameseAt(left)) found = beside[1] in " ns" || word in shared.beforeEnglish  // "leo rank", not "rất so cute"
                    // "Julius sang Emily", "do Kaori"; not "say goodbye", not a bare "So, ..."
                    else if (word in shared.strong && accented) found = 'e' !in beside && ('n' in beside || 'o' in beside)
                }
                if (!found && word in shared.echo) found = listOf(index - 1, index + 1).any { it in words.indices && words[it] == word }
                if (!found) found = (right != null && (word to words[right]) in shared.pairs) || (left != null && (words[left] to word) in shared.pairs)
                if (found) {
                    proven.add(index)
                    changed = true
                }
            }
        }
        return listed.indices.filter { listed[it] in proven }
    }

    /** (Vietnamese, English) phonemes of one shared word, from the dictionary that is loaded. */
    private fun reading(word: String, g2p: (String) -> String): Pair<String, String> = readings.getOrPut(word) {
        g2p("ạ $word ạ").trim().split(spaces)[1] to g2p("<en>$word</en>").trim()
    }

    /**
     * phoneme_policy.restore_vietnamese: the shared words [vietnameseShared] claims get their Vietnamese phonemes. [phonemes] is `g2p(source)`;
     * [text] is the chunk the decision is made on. The spoken text is not touched: each claimed word is swapped, in the phonemizer's input only,
     * for another shared word that is not in the sentence. sea-g2p resolves a run of shared words as one unit, so the swap changes no other
     * word's language, and the stand-in's phonemes mark the exact place. A result that differs anywhere else is thrown away.
     */
    fun restoreVietnamese(text: String, phonemes: String, source: String, g2p: (String) -> String, capitals: Set<String> = emptySet()): String {
        val shared = shared
        val present = shared.find.findAll(text).map { it.value.lowercase(Locale.ROOT) }.toSet()
        if (present.isEmpty() || present.none { reading(it, g2p).second in phonemes }) return phonemes  // nothing was read as English
        val proven = vietnameseShared(text, capitals)
        if (proven.isEmpty()) return phonemes
        fun listed(value: String): List<Pair<IntRange, String>> = token.findAll(value).mapNotNull { match ->
            match.groups[2]?.let { it.range to it.value.lowercase(Locale.ROOT) }?.takeIf { it.second in shared.listed }
        }.toList()
        val spans = listed(source)
        if (spans.map { it.second } != listed(text).map { it.second }) return phonemes  // the second normalization moved a shared word: do not guess
        val before = phonemes.split(spaces).filter { it.isNotEmpty() }
        val claimed = proven.map { spans[it] }
        val spoken = token.findAll(source).mapNotNull { it.groups[2]?.value?.lowercase(Locale.ROOT) }.toSet()
        sentinels@ for (sentinel in shared.sentinels) {
            if (sentinel in spoken) continue
            var marked = source
            for ((range, _) in claimed.asReversed()) marked = marked.replaceRange(range, sentinel)
            val after = g2p(marked).split(spaces).filter { it.isNotEmpty() }
            val places = (0 until minOf(after.size, before.size)).filter { after[it] != before[it] }
            if (after.size != before.size || places.size != claimed.size) continue
            val out = before.toMutableList()
            for ((index, claim) in places.zip(claimed)) {
                val (vietnamese, english) = reading(claim.second, g2p)
                val core = before[index].trimEnd { it in PHONEME_MARKS }
                if (after[index].trimEnd { it in PHONEME_MARKS } !in reading(sentinel, g2p).toList() || (core != vietnamese && core != english)) continue@sentinels
                out[index] = vietnamese + before[index].substring(core.length)
            }
            return out.joinToString(" ")
        }
        return phonemes
    }
}
