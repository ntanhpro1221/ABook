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
    private const val STRONG = ".!?;:…"  // a neighbour beyond one of these is no neighbour
    private const val IDENTITY = "Vahs"  // word classes whose very word is evidence, not only its kind
    private const val FOREIGN = "efnX"
    private val letters = Regex("[a-z]+")
    private val readings = java.util.concurrent.ConcurrentHashMap<String, Pair<String, String>>()

    /** The learned table shared_words.json (scripts/build_shared_words.py writes the Kotlin copy; docs/SHARED_WORDS.md). */
    private class Entry(val prior: Int, val left: IntArray, val right: IntArray, val bothForeign: Int, val doubled: Int, val leftWords: Map<String, Int>, val rightWords: Map<String, Int>)

    private class Shared {
        private val data = org.json.JSONObject(SharedWords.JSON)
        private fun strings(key: String): List<String> = data.getJSONArray(key).let { a -> (0 until a.length()).map(a::getString) }
        private fun ints(a: org.json.JSONArray) = IntArray(a.length()) { a.getInt(it) }
        private fun weights(o: org.json.JSONObject): Map<String, Int> = HashMap<String, Int>().also { m -> o.keys().forEach { m[it] = o.getInt(it) } }
        val words: Map<String, Entry> = data.getJSONObject("words").let { all -> all.keys().asSequence().associateWith { word ->
            val e = all.getJSONObject(word)
            Entry(e.getInt("p"), ints(e.getJSONArray("l")), ints(e.getJSONArray("r")), e.getInt("f"), e.getInt("x"), weights(e.getJSONObject("L")), weights(e.getJSONObject("R")))
        } }
        val both = strings("shared").toSet()  // every word sea-g2p holds in both dictionaries with two sounds
        val classes = strings("classes").withIndex().associate { it.value to it.index }
        val foreign = FOREIGN.map { classes.getValue(it.toString()) }.toSet()
        val secondLeft = weights(data.getJSONObject("second").getJSONObject("L"))
        val secondRight = weights(data.getJSONObject("second").getJSONObject("R"))
        val coarse = ints(data.getJSONArray("coarse"))  // the two neighbours taken together, each as one of five kinds
        val pair = ints(data.getJSONArray("pair"))
        val noDiacritics = data.getInt("no_diacritics")
        val tagged = data.getInt("tagged")
        val englishShare = data.getInt("english_share")
        val vietnameseShare = data.getInt("vietnamese_share")
        val threshold = data.getInt("threshold")
        val sentinels = strings("sentinels")
        val english = EnglishPolicy.context("only") + EnglishPolicy.context("function")
        val find = Regex("(?<![$W'’])(?:" + words.keys.sorted().joinToString("|") + ")(?![$W'’])", RegexOption.IGNORE_CASE)
        val kinds = java.util.concurrent.ConcurrentHashMap<String, Char>()
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

    /**
     * phoneme_policy._word_class: V a Vietnamese syllable with a diacritic, o other non-ASCII, e certainly English, s in both sea-g2p dictionaries
     * with two sounds, h a toneless Vietnamese syllable that is also an English word, a a toneless syllable that is not, f any other ASCII word.
     */
    private fun wordClass(word: String): Char = shared.kinds.getOrPut(word) {
        when {
            !ascii(word) -> if (EnglishPolicy.vietnamese(word)) 'V' else 'o'
            word in shared.english -> 'e'
            word in shared.both -> 's'
            letters.matches(word) && EnglishPolicy.vietnamese(word) -> if (word in EnglishWords.ALL) 'h' else 'a'
            word in EnglishWords.ALL || word.split('\'', '’')[0] in EnglishWords.ALL -> 'e'
            else -> 'f'
        }
    }

    private class Word(val word: String, val kind: Char, val gap: String)

    /** phoneme_policy._shared_tokens: every sea-g2p word of [text] with its class and the punctuation before it; an <en> span is one token X. */
    private fun sharedTokens(text: String, capitals: Set<String>): List<Word> {
        val out = ArrayList<Word>()
        val gap = StringBuilder("^")
        for (match in token.findAll(text)) {
            val mark = match.groups[3]
            if (mark != null) {
                gap.append(mark.value)
                continue
            }
            val tagged = match.groups[1]?.value
            if (tagged != null) out.add(Word(tagged.substring(4, tagged.length - 5).trim().lowercase(Locale.ROOT), 'X', gap.toString()))
            else {
                val word = match.groups[2]!!.value.lowercase(Locale.ROOT)
                out.add(Word(word, if (word in capitals && ascii(word)) 'n' else wordClass(word), gap.toString()))
            }
            gap.setLength(0)
        }
        return out
    }

    /**
     * phoneme_policy.vietnamese_shared: positions, among the table's words of normalized [text], of those the sentence makes Vietnamese. A learned
     * score (docs/SHARED_WORDS.md): the word's own corpus behaviour, each neighbour's class and identity, the two neighbours together, the word one further out, the chunk's
     * share of certain English and certain Vietnamese, a tag, a doubled word. A capital mid-sentence is a name and is never claimed.
     */
    fun vietnameseShared(text: String, capitals: Set<String> = emptySet()): List<Int> {
        val shared = shared
        val tokens = sharedTokens(text, capitals)
        val english = tokens.count { it.kind == 'e' || it.kind == 'X' }
        val accented = tokens.count { it.kind == 'V' }
        val others = tokens.size - 1
        val proven = ArrayList<Int>()
        var position = -1
        for ((index, target) in tokens.withIndex()) {
            val entry = shared.words[target.word] ?: continue
            position++
            if (target.kind == 'n') continue
            var score = entry.prior
            var foreign = 0
            var pair = 0
            for (step in intArrayOf(-1, 1)) {
                val table = if (step < 0) entry.left else entry.right
                val other = index + step
                val beside = tokens.getOrNull(other)
                val gap = if (beside == null) "" else tokens[maxOf(index, other)].gap
                val found = shared.classes.getValue(
                    if (beside == null) "^" else if (gap.isEmpty()) beside.kind.toString() else if (gap.any { it in STRONG }) "^" else if (beside.kind in IDENTITY) ",v" else ",x"
                )
                score += table[found]
                pair = pair * 5 + shared.coarse[found]
                if (beside == null || gap.isNotEmpty()) continue
                if (found in shared.foreign) foreign++
                if (beside.kind in IDENTITY) score += (if (step < 0) entry.leftWords else entry.rightWords)[beside.word] ?: 0
                val further = other + step
                val second = if (further !in tokens.indices || tokens[maxOf(other, further)].gap.isNotEmpty()) "|"
                    else if (tokens[further].kind == 'V') "v" else if (tokens[further].kind in "ahs") "t" else "x"
                score += (if (step < 0) shared.secondLeft else shared.secondRight).getValue(second)
            }
            score += shared.pair[pair]
            if (foreign == 2) score += entry.bothForeign
            if (accented == 0) score += shared.noDiacritics
            if (others > 0) score += Math.floorDiv(shared.englishShare * (english - (if (target.kind == 'X') 1 else 0)), others) +
                Math.floorDiv(shared.vietnameseShare * accented, others)
            if (target.kind == 'X') score += shared.tagged
            if (listOf(index - 1, index + 1).any { it in tokens.indices && tokens[it].word == target.word }) score += entry.doubled
            if (score >= shared.threshold) proven.add(position)
        }
        return proven
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
            if (match.groups[3] != null) return@mapNotNull null
            val tagged = match.groups[1]?.value
            val word = (tagged?.let { it.substring(4, it.length - 5).trim() } ?: match.groups[2]!!.value).lowercase(Locale.ROOT)
            if (word in shared.words) match.range to word else null  // the stand-in takes the place of the whole <en> tag
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
