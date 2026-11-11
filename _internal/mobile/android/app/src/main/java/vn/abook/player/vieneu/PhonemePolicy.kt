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
    private val letterRun = Regex("\\p{L}+")
    private val sentence = Regex("[^.!?…;:\\n\"“”«»「」『』]+")  // a quoted shout is a sentence of its own
    private const val QUOTES = " \t\r\n\"'“”‘’«»()[]{}「」『』〈〉《》【】—–-*"
    private const val SENTENCE_END = ".!?…:;"
    private const val PHONEME_MARKS = ".,!?"
    private const val STRONG = ".!?;:…"  // a neighbour beyond one of these is no neighbour
    private const val IDENTITY = "Vahs"  // word classes whose very word is evidence, not only its kind
    private const val FOREIGN = "efnX"
    private val letters = Regex("[a-z]+")
    private val lowerWord = Regex("(?<![$W'’<>/])[a-z]+(?![$W'’])")
    private val writtenName = Regex("(?<![$W'’<>/])[A-Z][A-Za-z]*(?![$W]|['’][$W])")  // as capital, and a closing quote may follow ("‘Giant Leo’")
    private val tone = Regex("[2-6ɜ]")  // sea-g2p's tone marks: a Vietnamese reading has one unless its tone is level
    private const val WORD_EDGE = ".,!?;:…\"'“”‘’()[]{}«»-–—"

    /** name_sounds.json (the build hands it over): what a romanized name may hold that the VieNeu road cannot say as written (docs/NAME_SOUNDS.md). */
    private class Sounds {
        private val data = org.json.JSONObject(BuildConfig.NAME_SOUNDS)
        val rimes: Map<String, String> = data.getJSONObject("rimes").let { all -> all.keys().asSequence().associateWith(all::getString) }
        val level: Set<String> = data.getJSONArray("level").let { a -> (0 until a.length()).map(a::getString).toSet() }
        val unread: Map<String, String> = data.getJSONObject("unread").let { all -> all.keys().asSequence().associateWith(all::getString) }
        val rime = Regex("(?<!\\p{L})([bcdđghklmnpqrstvx]{0,3})(" + rimes.keys.sorted().joinToString("|") + ")(?!\\p{L})")
    }

    private val sounds by lazy { Sounds() }

    /**
     * phoneme_policy.respell_rare_rimes: a rime Vietnamese hardly has ("ưn": Korean eun) is given to the phonemizer as the nearest one the
     * voice can say ("ân", Sino-Vietnamese for 은/恩) - VieNeu drags "ưn" to "ưng" and hesitates before it. [text] is normalized (lower
     * case); "ưm" (eum) is not respelled (the owner hears "rưm" right); the spoken text is not touched.
     */
    fun respellRareRimes(text: String): String =
        sounds.rime.replace(text) { it.groupValues[1] + sounds.rimes.getValue(it.groupValues[2]) }

    /**
     * phoneme_policy.repair_level_tone: sea-g2p gives a few syllables written without a tone mark a tone ("un" /ˈu2n/, "gin" /zˈi2n/, "pa"
     * /pˈaː2/); a name's syllable written without a mark has the level tone. Words of normalized [text] and of [phonemes] are aligned one to
     * one, or nothing is touched.
     */
    fun repairLevelTone(text: String, phonemes: String): String {
        val words = text.split(spaces).filter { it.isNotEmpty() }
        val phones = phonemes.split(spaces).filter { it.isNotEmpty() }.toMutableList()
        if (words.size != phones.size) return phonemes
        var changed = false
        for ((index, word) in words.withIndex()) {
            if (word.trim { it in WORD_EDGE } in sounds.level && tone.containsMatchIn(phones[index])) {
                phones[index] = tone.replace(phones[index], "")
                changed = true
            }
        }
        return if (changed) phones.joinToString(" ") else phonemes
    }

    private val unreadReadings = java.util.concurrent.ConcurrentHashMap<String, String>()

    /**
     * phoneme_policy.restore_unread_words: a Vietnamese word sea-g2p has no Vietnamese sound for - "pin" /pˈɪn/, "veo" /vˈiːəʊ/, "boa", the name
     * syllable "min" (English dictionary only), "qui" /kwj/, "gim" /zm/ (no vowel at all) - gets sea-g2p's own reading of the same syllable
     * written with a tone mark ("pìn"), less the tone. It keeps its English sound where the word right before or right after it, with no
     * punctuation between, is certainly English ("pin it", an <en> span). Words of normalized [text] and of [phonemes] are aligned one to one,
     * or nothing is touched.
     */
    fun restoreUnreadWords(text: String, phonemes: String, g2p: (String) -> String): String {
        val tokens = text.split(spaces).filter { it.isNotEmpty() }
        val phones = phonemes.split(spaces).filter { it.isNotEmpty() }.toMutableList()
        if (tokens.size != phones.size) return phonemes
        val words = ArrayList<String>(tokens.size)
        val english = BooleanArray(tokens.size)
        val opens = BooleanArray(tokens.size)  // punctuation before / after the word: the word beyond it is no neighbour
        val closes = BooleanArray(tokens.size)
        var inside = false
        for ((index, token) in tokens.withIndex()) {
            inside = inside || "<en>" in token
            val bare = token.replace("<en>", "").replace("</en>", "")
            val word = bare.trim { it in WORD_EDGE }.lowercase(Locale.ROOT)
            words.add(word)
            english[index] = inside || wordClass(word) == 'e'
            opens[index] = bare.trimStart { it in WORD_EDGE } != bare
            closes[index] = bare.trimEnd { it in WORD_EDGE } != bare
            inside = inside && "</en>" !in token
        }
        var changed = false
        for ((index, word) in words.withIndex()) {
            val marked = sounds.unread[word]
            if (marked == null || english[index]) continue
            val before = index > 0 && !opens[index] && !closes[index - 1] && english[index - 1]
            val after = index + 1 < words.size && !closes[index] && !opens[index + 1] && english[index + 1]
            if (before || after) continue
            val reading = unreadReadings.getOrPut(word) { tone.replace(g2p("ạ $marked ạ").trim().split(spaces)[1], "") }
            val core = phones[index].trimEnd { it in PHONEME_MARKS }
            if (core != reading) {
                phones[index] = reading + phones[index].substring(core.length)
                changed = true
            }
        }
        return if (changed) phones.joinToString(" ") else phonemes
    }
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
        // Tier 1 is sure outside [doubtFrom, doubtTo); a word written as a name is Vietnamese from nameThreshold, in doubt from nameDoubt.
        val doubtFrom = data.getJSONArray("doubt").getInt(0)
        val doubtTo = data.getJSONArray("doubt").getInt(1)
        val nameThreshold = data.getInt("name_threshold")
        val nameDoubt = data.getInt("name_doubt")
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

    /**
     * phoneme_policy.capitalised: ASCII words written as a name, lower-cased - a capital inside a sentence, or shouting ("admin BAN nick"). Read
     * from the spoken [text] and from [source], the text as it was WRITTEN (the text layer lower-cases a shouted word before it is spoken). A
     * sentence shouted from end to end ("BAY ĐI!") is prose.
     */
    fun capitalised(text: String, source: String? = null): Set<String> {
        val found = mutableSetOf<String>()
        for (value in listOf(text, source)) {
            if (value.isNullOrEmpty()) continue
            for (match in capital.findAll(value)) {
                val word = match.value
                if (word.length > 1 && word.all { it in 'A'..'Z' }) {
                    if (!source.isNullOrEmpty() && value !== source) continue  // only the written text can tell a shouted sentence
                    val around = sentence.findAll(value).first { match.range.first in it.range }.value
                    if (letterRun.findAll(around).any { it.value != it.value.uppercase(Locale.ROOT) }) found.add(word.lowercase(Locale.ROOT))
                    continue
                }
                val head = value.substring(0, match.range.first).trimEnd { it in QUOTES }
                if (head.isNotEmpty() && head.last() !in SENTENCE_END) found.add(word.lowercase(Locale.ROOT))
            }
        }
        return found
    }

    /**
     * phoneme_policy.Rulings: what a book already knows about its shared words (the second tier ran in Studio; `sharedWords` of book.json) -
     * answers by context ([sharedWordContexts] key -> Vietnamese?), the roster's Vietnamese names and its foreign names that are spelled
     * like a Vietnamese syllable ("dan", "tom": [englishNames]), lower-case.
     */
    class Rulings(val contexts: Map<String, Boolean> = emptyMap(), val names: Set<String> = emptySet(), val foreign: Set<String> = emptySet()) {
        val empty get() = contexts.isEmpty() && names.isEmpty() && foreign.isEmpty()

        /** One mark for a clip key: every ruling of the book (they come with the book and do not change). */
        val mark: String by lazy {
            val lines = contexts.entries.sortedBy { it.key }.map { "${it.key}\t${if (it.value) 1 else 0}" } + names.sorted().map { "name\t$it" } +
                foreign.sorted().map { "foreign\t$it" }
            java.security.MessageDigest.getInstance("SHA-256").digest(lines.joinToString("\n").toByteArray(Charsets.UTF_8)).take(8).joinToString("") { "%02x".format(it) }
        }

        companion object {
            /** The `sharedWords` entry of book.json (shared_rulings.shared), null when absent, of another version or with nothing in it. */
            fun of(found: org.json.JSONObject?): Rulings? {
                if (found == null || found.optInt("version") != 2) return null
                val contexts = found.optJSONObject("contexts") ?: return null
                val names = found.optJSONArray("names") ?: return null
                val foreign = found.optJSONArray("foreign") ?: return null
                val answers = HashMap<String, Boolean>()
                for (key in contexts.keys()) when (contexts.optString(key)) {
                    "v" -> answers[key] = true
                    "e" -> answers[key] = false
                    else -> return null
                }
                val rulings = Rulings(answers, (0 until names.length()).map { names.optString(it) }.toSet(),
                    (0 until foreign.length()).map { foreign.optString(it) }.toSet())
                return if (rulings.empty) null else rulings
            }
        }
    }

    /** "w" + the book's mark when [text] holds a word of the table and the book has rulings, else "" (ClipCache.reading). */
    fun rulingsTag(text: String, rulings: Rulings?): String =
        if (rulings == null || rulings.empty || !(shared.find.containsMatchIn(text) ||
                (rulings.foreign.isNotEmpty() && letters.findAll(text.lowercase(Locale.ROOT)).any { it.value in rulings.foreign }))) "" else "w" + rulings.mark

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

    class Scored(val word: String, val score: Int, val name: Boolean)

    class Verdict(val word: String, val vietnamese: Boolean, val sure: Boolean, val who: String)

    /**
     * phoneme_policy.shared_word_scores: every table word of normalized [text], in order, with its learned score (docs/SHARED_WORDS.md): the
     * word's own corpus behaviour, each neighbour's class and identity, the two neighbours together, the word one further out, the chunk's
     * share of certain English and certain Vietnamese, a tag, a doubled word. `name`: the word is one of [capitals] (its score is the one it
     * would have as prose).
     */
    fun sharedWordScores(text: String, capitals: Set<String> = emptySet()): List<Scored> {
        val shared = shared
        val tokens = sharedTokens(text, capitals)
        val english = tokens.count { it.kind == 'e' || it.kind == 'X' }
        val accented = tokens.count { it.kind == 'V' }
        val others = tokens.size - 1
        val out = ArrayList<Scored>()
        for ((index, target) in tokens.withIndex()) {
            val entry = shared.words[target.word] ?: continue
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
            out.add(Scored(target.word, score, target.kind == 'n'))
        }
        return out
    }

    /**
     * phoneme_policy.shared_word_contexts: the key of every table word of normalized [text], in order - two words each side as the phonemizer
     * sees them; "^" is the edge of the chunk or a `. ! ? ; : …`, a comma is kept as ",". A second-tier ruling is stored under this key.
     */
    fun sharedWordContexts(text: String): List<String> {
        val tokens = sharedTokens(text, emptySet())
        fun side(index: Int, step: Int): List<String> {
            val found = ArrayList<String>()
            var at = index
            while (found.size < 2) {
                val other = at + step
                if (other !in tokens.indices) {
                    found.add("^")
                    break
                }
                val gap = tokens[maxOf(at, other)].gap
                if (gap.any { it in STRONG }) {
                    found.add("^")
                    break
                }
                val comma = if (gap.isEmpty()) "" else ","
                found.add(if (step < 0) comma + tokens[other].word else tokens[other].word + comma)
                at = other
            }
            return found
        }
        return tokens.indices.filter { tokens[it].word in shared.words }
            .map { side(it, -1).reversed().joinToString(" ") + "|" + tokens[it].word + "|" + side(it, 1).joinToString(" ") }
    }

    /**
     * phoneme_policy.shared_word_verdicts: tier 1 is the score - prose is Vietnamese from the threshold up and sure outside the doubt band, a
     * word written as a name is only in doubt from `name_doubt` up, and a word that opens a sentence before an English word and an accented
     * Vietnamese one ("Do trans sắp thi") is in doubt whatever its score. Then what the book knows ([rulings]): a ruling for this very context, the
     * roster's Vietnamese names (every occurrence written as a name, and a doubtful one in prose), else tier 1's own best guess.
     */
    fun sharedWordVerdicts(text: String, capitals: Set<String> = emptySet(), rulings: Rulings? = null): List<Verdict> {
        val shared = shared
        val keys = if (rulings != null) sharedWordContexts(text) else emptyList()
        val tokens = sharedTokens(text, capitals)
        val listed = tokens.indices.filter { tokens[it].word in shared.words }
        fun opens(index: Int) = tokens[index].gap.let { gap -> '^' in gap || gap.any { it in STRONG } }
        fun english(index: Int) = index + 1 < tokens.size && tokens[index + 1].gap.isEmpty() && tokens[index + 1].kind in "eX"
        // a roster name that opens a sentence, unless an English word follows it directly ("An nói." but "An apple")
        val heads = listed.map { opens(it) && !english(it) }
        // opens a sentence, then an English word, then an accented Vietnamese one: a borrowed noun in a Vietnamese sentence
        val borrowed = listed.map { opens(it) && english(it) && it + 2 < tokens.size && tokens[it + 2].gap.isEmpty() && tokens[it + 2].kind == 'V' }
        return sharedWordScores(text, capitals).mapIndexed { position, scored ->
            var claimed = scored.score >= (if (scored.name) shared.nameThreshold else shared.threshold)
            var sure = if (scored.name) !(scored.score >= shared.nameDoubt && scored.score < shared.nameThreshold)
                else !((scored.score >= shared.doubtFrom && scored.score < shared.doubtTo) || (borrowed[position] && !claimed))
            var who = "table"
            if (rulings != null) {
                val ruled = rulings.contexts[keys[position]]
                if (ruled != null) {
                    claimed = ruled; sure = true; who = "ruling"
                } else if (scored.word in rulings.names && (scored.name || !sure || heads[position])) {
                    claimed = true; sure = true; who = "roster"
                } else if (scored.word in rulings.foreign && (scored.name || heads[position])) {
                    claimed = false; sure = true; who = "roster"
                }
            }
            Verdict(scored.word, claimed, sure, who)
        }
    }

    /** phoneme_policy.vietnamese_shared: positions, among the table's words of normalized [text], of those that are Vietnamese ([sharedWordVerdicts]). */
    fun vietnameseShared(text: String, capitals: Set<String> = emptySet(), rulings: Rulings? = null): List<Int> =
        sharedWordVerdicts(text, capitals, rulings).withIndex().filter { it.value.vietnamese }.map { it.index }

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
    fun writtenNames(text: String, source: String? = null): Set<String> {
        val upper = HashSet<String>()
        val lower = HashSet<String>()
        for (value in listOf(text, source)) {
            if (value.isNullOrEmpty()) continue
            writtenName.findAll(value).forEach { upper.add(it.value.lowercase(Locale.ROOT)) }
            lowerWord.findAll(value).forEach { lower.add(it.value) }
        }
        return upper - lower
    }

    /**
     * phoneme_policy.english_names: a foreign roster name that is spelled like a Vietnamese syllable gets its English sound ("Dan" /zaːn/ ->
     * /dæn/). sea-g2p has no English entry for such a word, not even inside an <en> tag; it does read the possessive in English ("dan's" ->
     * /dˈænz/), so each of [words] is swapped for its possessive in the phonemizer's input only ([given]; [raw] is its output) and the closing
     * /z/ or /s/ is dropped. A swap that moves any other word, or that does not come back as one English word, is thrown away.
     */
    fun englishNames(given: String, raw: String, phonemes: String, g2p: (String) -> String, words: Set<String>): String {
        if (words.isEmpty()) return phonemes
        val tokens = given.split(spaces).filter { it.isNotEmpty() }
        val before = raw.split(spaces).filter { it.isNotEmpty() }
        val out = phonemes.split(spaces).filter { it.isNotEmpty() }.toMutableList()
        if (tokens.size != before.size || tokens.size != out.size) return phonemes
        var changed = false
        for ((index, token) in tokens.withIndex()) {
            val match = letterRun.find(token) ?: continue
            if (match.value !in words || letterRun.find(token, match.range.last + 1) != null) continue
            val marked = tokens.toMutableList()
            marked[index] = token.substring(0, match.range.last + 1) + "'s" + token.substring(match.range.last + 1)
            val after = g2p(marked.joinToString(" ")).split(spaces).filter { it.isNotEmpty() }
            if (after.size != before.size || after.indices.any { it != index && after[it] != before[it] }) continue
            val said = after[index].trimEnd { it in PHONEME_MARKS }
            if (said.length < 3 || said.last() !in "zs" || tone.containsMatchIn(said)) continue
            out[index] = said.dropLast(1) + out[index].substring(out[index].trimEnd { it in PHONEME_MARKS }.length)
            changed = true
        }
        return if (changed) out.joinToString(" ") else phonemes
    }

    fun restoreVietnamese(text: String, phonemes: String, source: String, g2p: (String) -> String, capitals: Set<String> = emptySet(),
                          rulings: Rulings? = null): String {
        val shared = shared
        val present = shared.find.findAll(text).map { it.value.lowercase(Locale.ROOT) }.toSet()
        if (present.isEmpty() || present.none { reading(it, g2p).second in phonemes }) return phonemes  // nothing was read as English
        val proven = vietnameseShared(text, capitals, rulings)
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
