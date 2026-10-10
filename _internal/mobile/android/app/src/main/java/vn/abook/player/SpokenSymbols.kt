package vn.abook.player

import vn.abook.player.readaloud.Symbols

/**
 * Chữ máy thu sẽ đọc sau khi ký hiệu không nói được đổi thành chữ hay quãng nghỉ - bản Kotlin của `text_processing.spoken_symbols_to_words` (Studio): "Mở/đóng"
 * thành "Mở, đóng", "(1)" thành ", 1", "A + B" thành "A cộng B"; "km/h" giữ nguyên. Điện thoại không thu giọng nên chỉ dùng để biết một cách đọc có chạm tới
 * câu hay chữ ấy đã biến mất trước khi tra cách đọc (`LocalStudio.readingReach`, trường `blocked`). Cùng luật, cùng ca: tests/fixtures/book_edits/spoken_symbols.json.
 *
 * Khác `readaloud.Symbols` (Nghe ngay đọc ký hiệu theo ngữ cảnh): đây là luật phẳng của Studio; chỗ chung duy nhất là "/" giữa hai đơn vị đo
 * ([Symbols.unitSlash]), như bên Python (`readaloud.symbols.unit_slash`).
 */
object SpokenSymbols {
    /** `\s` của Python (Unicode): thêm khoảng trắng Z*, NEL và bốn dấu điều khiển \x1c-\x1f. */
    private const val SPACE = "[\\s\\p{Z}\\u0085\\u001c-\\u001f]"
    /** `[^\W\d_]` của Python: chữ (cả số La Mã / số mũ dạng chữ), không phải chữ số thập phân hay gạch dưới. ICU của Android không có (?U). */
    private const val LETTER = "[\\p{L}\\p{Nl}\\p{No}]"

    private val SYMBOL_WORDS = mapOf('↓' to "giảm", '↑' to "tăng", '+' to "cộng", '=' to "bằng", '≥' to "lớn hơn hoặc bằng", '≤' to "nhỏ hơn hoặc bằng",
        '^' to "mũ", '×' to "nhân", '÷' to "chia")
    private const val SEPARATORS = "»«›‹→⇒▸▶►([{)]}|"
    private const val DROPPED = "•▪◦*"
    private val BOUNDARY_TRIM = (SEPARATORS + DROPPED + " \t\r\n").toSet()

    private val VOCAL_CUE = Regex("\\[(cười|chuckle|thở$SPACE+dài|sigh|hắng$SPACE+giọng|clear$SPACE+throat)\\]",RegexOption.IGNORE_CASE)
    private val CENSOR_RUN = Regex("[#&@\\$%*!?]{3,}")
    private const val CENSOR_MARKS = "#&@$"
    private val HAS_LETTER = Regex(LETTER)
    private val WORD_SLASH = Regex("(?<=$LETTER)$SPACE*/$SPACE*(?=$LETTER)")
    private val SPACE_BEFORE_PUNCT = Regex("$SPACE+([,.!?;:…])")
    private val COMMA_RUN = Regex("(?:$SPACE*,)+(?=$SPACE*,)")
    private val TRAILING_COMMA = Regex(",($SPACE*[.!?…:;])")
    private val SPACE_RUN = Regex("[ \\t]{2,}")

    /** Chữ bị che bằng ký hiệu ("Cái #&!@!") là một quãng ngừng, không phải tên ký hiệu (`_censored_words_as_pauses`). */
    private fun censoredAsPauses(text: String): String {
        if (!HAS_LETTER.containsMatchIn(text)) return text
        return CENSOR_RUN.replace(text) { match ->
            val run = match.value
            if (run.any { it in CENSOR_MARKS } || run.count { it == '*' } >= 3) "…" else run
        }
    }

    private fun inSpan(text: String): String {
        val out = StringBuilder()
        for (character in text) {
            val word = SYMBOL_WORDS[character]
            when {
                word != null -> out.append(' ').append(word).append(' ')
                character in SEPARATORS -> out.append(", ")
                character in DROPPED -> Unit
                else -> out.append(character)
            }
        }
        return out.toString()
    }

    fun toWords(text: String): String {
        val source = censoredAsPauses(text.replace("=>", "→"))
        val spans = ArrayList<Pair<String, Boolean>>() // (đoạn, là dấu hiệu giọng "[thở dài]" - để nguyên)
        var position = 0
        for (match in VOCAL_CUE.findAll(source)) {
            spans.add(source.substring(position, match.range.first) to false)
            spans.add(match.value to true)
            position = match.range.last + 1
        }
        spans.add(source.substring(position) to false)
        if (!spans.first().second) spans[0] = spans.first().first.trimStart { it in BOUNDARY_TRIM } to false
        if (!spans.last().second) spans[spans.size - 1] = spans.last().first.trimEnd { it in BOUNDARY_TRIM } to false
        var out = spans.joinToString("") { (span, isCue) -> if (isCue) span else inSpan(span) }
        out = WORD_SLASH.replace(out) { match ->
            if (Symbols.unitSlash(out.substring(0, match.range.first), out.substring(match.range.last + 1))) match.value else ", "
        }
        out = SPACE_BEFORE_PUNCT.replace(out) { it.groupValues[1] }
        out = COMMA_RUN.replace(out, "")
        out = TRAILING_COMMA.replace(out) { it.groupValues[1] }
        out = SPACE_RUN.replace(out, " ")
        return BookEdits.pyStrip(out)
    }
}
