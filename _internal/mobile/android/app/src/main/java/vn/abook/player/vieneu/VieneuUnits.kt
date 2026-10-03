package vn.abook.player.vieneu

import vn.abook.player.readaloud.WordTokens

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

    /** Shown words [first]..[last] (inclusive) of the paragraph, read as the sentences [pieces]. */
    class Unit(val first: Int, var last: Int, val pieces: MutableList<String>) {
        fun text(tokens: List<String>): String = tokens.subList(first, last + 1).joinToString(" ")
    }

    fun tokens(text: String): List<String> = WordTokens.tokens(text).map { text.substring(it.first, it.last + 1) }

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
            val words = toks.subList(piece[0], piece[1] + 1).joinToString(" ")
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
