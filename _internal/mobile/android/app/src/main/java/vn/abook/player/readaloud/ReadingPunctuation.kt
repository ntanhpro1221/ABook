package vn.abook.player.readaloud

/** Voice text only; keep shown tokens/source offsets. Mirrors studio_tn.reading_punctuation. */
object ReadingPunctuation {
    // Explicit Python whitespace set: Android ICU does not support Java's (?U).
    private val lexical = listOf(
        Regex("""(?i:https?://|ftp://|www\.)[^\u0009-\u000D\u001C-\u0020\u0085\u00A0\u1680\u2000-\u200A\u2028\u2029\u202F\u205F\u3000<>"“”]+"""),
        Regex("""[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+(?:\.[\p{L}\p{N}_-]+)+"""),
        Regex("""(?<![\p{L}\p{N}_])(?:[A-Za-z]\.){2,}(?:[A-Za-z](?![\p{L}\p{N}_]))?"""),
        Regex("""(?<![\p{L}\p{N}_.])[vV]\.v\.?(?![\p{L}\p{N}_.])"""),
        Regex("""(?<![\p{L}\p{N}_])[A-Z]+(?:\.[A-Z]+)+\.?(?![\p{L}\p{N}_.])"""),
        Regex("""(?<![\p{L}\p{N}_.])(?:[A-Za-z0-9_-]+\.)+[A-Za-z0-9_-]*\p{Nd}[A-Za-z0-9_-]*(?![\p{L}\p{N}_.])"""),
        Regex("""(?<![\p{L}\p{N}_.])(?:[A-Za-z0-9-]+\.)+[a-z]{2,63}(?![\p{L}\p{N}_])"""),
        Regex("""(?<![\p{L}\p{N}_.])(?:[A-Za-z0-9-]+\.)+(?i:com|org|net|edu|gov|io|co|vn|jp|uk|ai|dev|app|info|me|tv)(?![\p{L}\p{N}_])"""),
        Regex("""(?<=\p{Nd})[.,:](?=\p{Nd})"""),
        Regex("""(?<![\p{L}\p{N}_.])Th\.S(?![\p{L}\p{N}_])"""),
    )
    private val joined = Regex("""[.!?,:;…]+["'”’»\])]*([“‘«\[]*)(?=[\p{L}\p{Nl}\p{No}])""")

    private fun isAlphanumeric(cp: Int): Boolean = Character.isLetterOrDigit(cp) ||
        Character.getType(cp) in listOf(Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt())

    fun separate(text: String): String {
        val protected = lexical.asSequence().flatMap { it.findAll(text) }.map { it.range }.toList()
        val insertions = mutableSetOf<Int>()
        for (match in joined.findAll(text)) {
            val start = match.range.first
            val at = match.groups[1]!!.range.first
            if (start == 0 || !isAlphanumeric(text.codePointBefore(start))) continue
            if (protected.any { start <= it.last && at > it.first }) continue
            val punctuation = match.value.trimEnd { it in "\"'”’»])“‘«[" }
            val following = text.getOrNull(start + punctuation.length)
            if (punctuation.lastOrNull() in listOf(':', ',', ';') && following in listOf('"', '\'')) continue
            if (("…" in punctuation || ".." in punctuation) && match.value.none { it in "\"”’»])" }) continue
            insertions.add(at)
        }
        if (insertions.isEmpty()) return text
        return buildString {
            for (index in 0..text.length) {
                if (index in insertions) append(' ')
                if (index < text.length) append(text[index])
            }
        }
    }
}
