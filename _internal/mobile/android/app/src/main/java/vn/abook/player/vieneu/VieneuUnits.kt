package vn.abook.player.vieneu

import vn.abook.player.readaloud.WordTokens
import java.text.Normalizer

/**
 * A paragraph cut into the "units" VieNeu reads one at a time - the phone's copy of `abook/readaloud/vieneu.py` `units` (shared fixture
 * tests/fixtures/vieneu/android/text.json): sentences packed up to [maxChars] characters like vieneu, a sentence that is too long cut at
 * commas then at spaces, a unit under [MIN_UNIT_CHARS] merged into its shorter neighbour (a 1-2 word unit on its own makes the model "say
 * more"). Never one comma phrase alone: sea-g2p's normaliser ends every phrase with a full stop, so each comma would sound like the end of
 * a sentence. Lengths count code points, like Python.
 */
object VieneuUnits {
    const val MIN_UNIT_CHARS = 20
    private const val SENTENCE_END = ".!?…"
    private const val PHRASE_END = ",;:"
    private const val CLOSERS = "\"'”’)]»"
    private const val OPENERS = "\"'“‘([«"
    /** I..XXXIX (the empty string matches too and is rejected apart). */
    private val ROMAN = Regex("X{0,3}(?:IX|IV|V?I{0,3})")
    private val ROMAN_VALUE = mapOf('I' to 1, 'V' to 5, 'X' to 10)
    /** One-letter numerals (I, V, X) are often just letters ("ông X", "tia X"): they count only after a numbered noun (`NUMBERED_NOUNS` of vieneu.py). */
    private val NUMBERED_NOUNS = setOf("chương", "phần", "tập", "quyển", "hồi", "mục", "khoá", "khóa", "lớp", "cấp", "hạng", "bậc", "đệ", "đời", "kỳ", "kì",
        "số", "bài", "điều", "khoản", "chặng", "vòng", "màn", "cảnh", "tầng").map { Normalizer.normalize(it, Normalizer.Form.NFC) }.toSet()
    private val NUMBERED_PAIRS = setOf("thế kỷ", "thế kỉ", "thế chiến").map { Normalizer.normalize(it, Normalizer.Form.NFC) }.toSet()
    private val DIGITS = listOf("", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")

    /** Shown words [first]..[last] (inclusive) of the paragraph, read as the sentences [pieces]. */
    class Unit(val first: Int, var last: Int, val pieces: MutableList<String>) {
        fun text(tokens: List<String>): String = tokens.subList(first, last + 1).joinToString(" ")
    }

    fun tokens(text: String): List<String> = WordTokens.tokens(text).map { text.substring(it.first, it.last + 1) }

    /** Value of an upper-case Roman numeral I..XXXIX (strict: no IIII, VX...), null when [core] is not one - `roman_value` of vieneu.py. */
    fun romanValue(core: String): Int? {
        if (core.isEmpty() || !ROMAN.matches(core)) return null
        var total = 0
        for ((index, letter) in core.withIndex()) {
            val value = ROMAN_VALUE.getValue(letter)
            total += if (index + 1 < core.length && ROMAN_VALUE.getValue(core[index + 1]) > value) -value else value
        }
        return total
    }

    /** 1..39 in words: mười bốn, mười lăm, hai mươi mốt, hai mươi lăm, ba mươi (`vietnamese_number`). */
    fun vietnameseNumber(value: Int): String {
        val tens = value / 10
        val ones = value % 10
        val head = when (tens) { 0 -> ""; 1 -> "mười"; else -> "${DIGITS[tens]} mươi" }
        val tail = when { ones == 0 -> ""; ones == 5 && tens > 0 -> "lăm"; ones == 1 && tens > 1 -> "mốt"; else -> DIGITS[ones] }
        return "$head $tail".trim()
    }

    private fun word(token: String): String = Normalizer.normalize(token.trimStart { it in OPENERS }.trimEnd { it in CLOSERS }, Normalizer.Form.NFC)

    private fun capitalised(word: String): Boolean = word.isNotEmpty() && word.all { it.isLetter() } && word[0].isUpperCase()

    /** Can the word before `toks[index]` be numbered: a numbered noun ("chương", "thế kỷ"...) or two capitalised names in a row ("Louis X") - `numbered_by`. */
    fun numberedBy(toks: List<String>, index: Int): Boolean {
        val before = if (index >= 1) word(toks[index - 1]) else ""
        if (before.lowercase() in NUMBERED_NOUNS) return true
        val earlier = if (index >= 2) word(toks[index - 2]) else ""
        if ("$earlier $before".lowercase() in NUMBERED_PAIRS) return true
        return capitalised(before) && capitalised(earlier)
    }

    /**
     * Shown words -> words to read (a reading-only change, the shown text stays): an upper-case Roman numeral I..XXXIX standing alone after a word
     * with a lower-case letter ("Phổ thông II", "Chương IV"), after a numeral just read ("Mục II, III"), or as a heading at the start of the
     * paragraph ("I. Mở đầu") is read as a Vietnamese number - sea-g2p only knows "Benedict III" and reads "thông II" as "i i". "I am" at the
     * start, an "I" after punctuation and abbreviations (CV, MC, VIP) stay. `spoken_tokens` of vieneu.py.
     */
    fun spokenTokens(toks: List<String>): List<String> {
        val out = toks.toMutableList()
        for ((index, token) in toks.withIndex()) {
            val core = token.trimStart { it in OPENERS }.trimEnd { it in CLOSERS || it in ".,;:!?…" }
            val value = romanValue(core) ?: continue
            if (index == 0) {
                if (toks.size < 2 || token.trimStart { it in OPENERS }.substring(core.length) !in listOf(".", ")")) continue
            } else {
                val before = toks[index - 1].trimStart { it in OPENERS }.trimEnd { it in CLOSERS }
                if (out[index - 1] == toks[index - 1] &&
                    (!(before.isNotEmpty() && before.all { it.isLetter() } && before.any { it.isLowerCase() }) || (core.length == 1 && !numberedBy(toks, index)))) continue
            }
            out[index] = token.replaceFirst(core, vietnameseNumber(value))
        }
        return out
    }

    private fun ends(token: String, marks: String): Boolean {
        val core = token.trimEnd { it in CLOSERS }
        return core.isNotEmpty() && core.last() in marks
    }

    private fun groups(toks: List<String>, first: Int, last: Int, marks: String): List<IntArray> {
        val out = ArrayList<IntArray>()
        var start = first
        for (index in first..last) {
            if (ends(toks[index], marks) || index == last) {
                out.add(intArrayOf(start, index))
                start = index + 1
            }
        }
        return out
    }

    private fun length(toks: List<String>, first: Int, last: Int): Int =
        (first..last).sumOf { toks[it].codePointCount(0, toks[it].length) } + (last - first)

    /** Merge neighbouring spans into the longest runs of at most [maxChars] characters. */
    private fun pack(toks: List<String>, spans: List<IntArray>, maxChars: Int): List<IntArray> {
        val out = ArrayList<IntArray>()
        for (span in spans) {
            if (out.isNotEmpty() && length(toks, out.last()[0], span[1]) <= maxChars) out[out.lastIndex] = intArrayOf(out.last()[0], span[1])
            else out.add(span)
        }
        return out
    }

    /** The paragraph's shown words and its units (every shown word in exactly one unit, in order). */
    fun units(text: String, maxChars: Int): Pair<List<String>, List<Unit>> {
        val toks = tokens(text)
        if (toks.isEmpty()) return toks to emptyList()
        val said = spokenTokens(toks)
        val pieces = ArrayList<IntArray>()
        for (sentence in groups(toks, 0, toks.size - 1, SENTENCE_END)) {
            if (length(toks, sentence[0], sentence[1]) <= maxChars) {
                pieces.add(sentence)
                continue
            }
            for (phrase in pack(toks, groups(toks, sentence[0], sentence[1], PHRASE_END), maxChars)) { // long sentence: commas, then spaces
                if (length(toks, phrase[0], phrase[1]) <= maxChars) pieces.add(phrase)
                else pieces.addAll(pack(toks, (phrase[0]..phrase[1]).map { intArrayOf(it, it) }, maxChars))
            }
        }
        val result = ArrayList<Unit>()
        for (piece in pieces) { // sentences into units, like vieneu's pack_sentences_into_chunks
            val words = said.subList(piece[0], piece[1] + 1).joinToString(" ")
            if (result.isNotEmpty() && length(toks, result.last().first, piece[1]) <= maxChars) {
                result.last().last = piece[1]
                result.last().pieces.add(words)
            } else {
                result.add(Unit(piece[0], piece[1], mutableListOf(words)))
            }
        }
        while (result.size > 1) { // a unit that is too short joins the shorter neighbour (a tie: the next one)
            val short = result.indices.filter { length(toks, result[it].first, result[it].last) < MIN_UNIT_CHARS }
            if (short.isEmpty()) break
            val i = short.minBy { length(toks, result[it].first, result[it].last) }
            var right = i + 1 < result.size
            if (right && i > 0) right = length(toks, result[i + 1].first, result[i + 1].last) <= length(toks, result[i - 1].first, result[i - 1].last)
            val (a, b) = if (right) i to i + 1 else i - 1 to i
            result[a] = Unit(result[a].first, result[b].last, (result[a].pieces + result[b].pieces).toMutableList())
            result.removeAt(b)
        }
        return toks to result
    }
}
