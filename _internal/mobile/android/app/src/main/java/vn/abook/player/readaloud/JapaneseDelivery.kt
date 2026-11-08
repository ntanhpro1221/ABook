package vn.abook.player.readaloud

/** Private VieNeu input; stored readings and ASR text retain their ordinary spelling. */
object JapaneseDelivery {
    private val word = Regex("""\p{L}+_?(?:-\p{L}+_?)+""")
    private val marked = Regex("<en>([^<>\\s]+)</en>")
    private val delivery get() = JapanesePolicy.data.getJSONObject("delivery")
    private val joiner get() = delivery.getString("joiner")

    fun groups(tokens: List<String>, origin: String?, readings: Map<String, String>? = null): Set<String> {
        if (Readings.applicable(tokens.joinToString(" "), readings).isNotEmpty()) return emptySet()
        val contextual = JapanesePolicy.contextualNames(tokens, origin)
        return tokens.flatMapIndexed { index, token ->
            val (_, core, _) = Names.splitToken(token)
            val said = JapanesePolicy.reading(core, origin, index in contextual) ?: ""
            word.findAll(said).map { it.value.lowercase(java.util.Locale.ROOT) }.toList()
        }.toSet()
    }

    fun mark(text: String, words: Set<String>): String = word.replace(text) {
        if (it.value.lowercase(java.util.Locale.ROOT) in words)
            "<en>" + it.value.replace("-", joiner) + "</en>" else it.value
    }

    /** Verify the entire unjoined stream before changing any marked word's spaces. */
    fun phonemes(text: String, final: Boolean, plain: (String, Boolean) -> String): String {
        val matches = marked.findAll(text).filter {
            joiner in it.groupValues[1] && word.matches(it.groupValues[1].replace(joiner, "-"))
        }.toList()
        if (matches.isEmpty()) return plain(text, final)
        val source = StringBuilder()
        val spans = ArrayList<Pair<Int, Int>>()
        var cursor = 0
        for (match in matches) {
            source.append(text.substring(cursor, match.range.first))
            val start = source.length
            source.append(match.groupValues[1].replace(joiner, "-"))
            spans.add(start to source.length)
            cursor = match.range.last + 1
        }
        source.append(text.substring(cursor))
        val ordinary = source.toString()
        var baseline = plain(ordinary, final)
        val context = delivery.getString("context_word")
        val contextPhones = plain(context, false)
        fun prefixPhones(end: Int): String? {
            val value = plain(ordinary.substring(0, end) + " " + context, false)
            if (value == contextPhones) return ""
            val suffix = " " + contextPhones
            return if (contextPhones.isNotEmpty() && value.endsWith(suffix)) value.dropLast(suffix.length) else null
        }
        val replacements = ArrayList<Triple<Int, Int, String>>()
        for ((start, end) in spans) {
            val left = prefixPhones(start) ?: continue
            val right = prefixPhones(end) ?: continue
            if (!baseline.startsWith(left) || !baseline.startsWith(right) || !right.startsWith(left)) continue
            var first = left.length
            val last = right.length
            if (baseline.getOrNull(first) == ' ') first++
            if (first >= last) continue
            if (last < baseline.length && baseline[last] !in " .,!?;:…)]}\"'’”") continue
            val phones = baseline.substring(first, last)
            if (phones.isEmpty() || phones.any { it in ".,!?;:…<>" }) continue
            var compact = phones.filterNot(Char::isWhitespace)
            if (delivery.getString("stress") in listOf("first", "secondary")) {
                var seen = false
                compact = compact.mapNotNull { char ->
                    if (char !in "ˈˌ") char else if (seen) {
                        if (delivery.getString("stress") == "secondary") 'ˌ' else null
                    } else { seen = true; char }
                }.joinToString("")
            }
            replacements.add(Triple(first, last, compact))
        }
        for ((first, last, compact) in replacements.asReversed())
            baseline = baseline.substring(0, first) + compact + baseline.substring(last)
        return baseline
    }
}
