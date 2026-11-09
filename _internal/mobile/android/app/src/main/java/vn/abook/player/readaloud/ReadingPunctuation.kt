package vn.abook.player.readaloud

/** Voice text only; keep shown tokens/source offsets. Mirrors studio_tn.reading_punctuation. */
object ReadingPunctuation {
    private val lexical = Regex(
        """(?:https?://|ftp://|www\.)[^\s<>"“”]+|[\p{L}\p{N}_.+-]+@[\p{L}\p{N}_-]+(?:\.[\p{L}\p{N}_-]+)+|(?<![\p{L}\p{N}_.])(?:[A-Za-z]\.){2,}(?:[A-Za-z](?![\p{L}\p{N}_]))?|(?<![\p{L}\p{N}_.])[vV]\.v\.?(?![\p{L}\p{N}_.])|(?<![\p{L}\p{N}_.])(?:[A-Za-z0-9-]+\.)+[a-z]{2,63}(?![\p{L}\p{N}_])|(?<=\p{Nd})[.,:](?=\p{Nd})"""
    )
    private val joined = Regex("""[.!?,:;…]+["'”’»\])]*([“‘«\[]*)(?=[\p{L}\p{Nl}\p{No}])""")
    private val identifiers = Regex("""(?<![\p{L}\p{N}_.])(?:[A-Za-z0-9_-]+\.)+[A-Za-z0-9_-]*\p{Nd}[A-Za-z0-9_-]*(?![\p{L}\p{N}_.])""")
    private val initials = Regex("""(?<![\p{L}\p{N}_.])[A-Z]+(?:\.[A-Z]+)+\.?(?![\p{L}\p{N}_.])""")
    private val network = Regex("""(?i:https?://|ftp://|www\.)[^\s<>"“”]+|(?<![\p{L}\p{N}_.])(?:[A-Za-z0-9-]+\.)+(?i:com|org|net|edu|gov|io|co|vn|jp|uk|ai|dev|app|info|me|tv)(?![\p{L}\p{N}_])""")

    fun separate(text: String): String {
        val protected = (lexical.findAll(text) + identifiers.findAll(text) + initials.findAll(text) + network.findAll(text)).map { it.range }.toList()
        val insertions = mutableSetOf<Int>()
        for (match in joined.findAll(text)) {
            val start = match.range.first
            val at = match.groups[1]!!.range.first
            if (start == 0 || !Character.isLetterOrDigit(text.codePointBefore(start))) continue
            if (protected.any { start <= it.last && at > it.first }) continue
            val punctuation = match.value.trimEnd { it in "\"'”’»])“‘«[" }
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
