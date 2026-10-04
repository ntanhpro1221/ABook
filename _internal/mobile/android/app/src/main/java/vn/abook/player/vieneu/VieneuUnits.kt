package vn.abook.player.vieneu

import vn.abook.player.readaloud.Abbreviations
import vn.abook.player.readaloud.Names
import vn.abook.player.readaloud.Shouts
import vn.abook.player.readaloud.WordTokens
import java.text.Normalizer
import java.util.Locale

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
    /** Khung của bảng trạng thái / lời thoại kiểu Nhật: chữ La Mã sát trong khung vẫn là số. */
    private const val FRAMES_OPEN = "【〔「『{"
    private const val FRAMES_CLOSE = "】〕」』}"
    /** Khung hệ thống: sea-g2p bỏ khung mà không ngắt, người nghe cần một nhịp ở hai đầu. */
    private const val SYSTEM_OPEN = "【〔[{"
    private const val SYSTEM_CLOSE = "】〕]}"
    private const val DASHES = "—–―"
    /** Dấu câu CJK: sea-g2p bỏ qua, người nghe mất nhịp. */
    private val FULLWIDTH = mapOf('，' to ',', '：' to ':', '；' to ';', '。' to '.', '！' to '!', '？' to '?', '、' to ',')
    private const val ANGLE_OPEN = "<《〈"
    private const val ANGLE_CLOSE = ">》〉"
    /** The opening and the closing angle bracket are at most this many shown words apart. */
    private const val ANGLE_REACH = 24
    private const val PUNCT_MARKS = ".,;:!?…"
    private val TILDES = Regex("~+")
    private const val W = """\p{L}\p{N}_"""
    /** 1/3, 3/5: một phần ba (sea-g2p đọc "một trên ba"); 180/300 là thanh chỉ số: để "trên". */
    private val FRACTION = Regex("""(?<![$W/.,-])([1-9])/([2-9])(?![$W/-]|[.,][0-9])""")
    /** 3-4000, 1-1, 1-3-1. */
    private val RANGE = Regex("""(?<![$W/.,-])([0-9]{1,4})((?:-[0-9]{1,4})+)(?![$W/-]|[.,][0-9])""")
    private val TIMES = Regex("""(?<![$W])[x×]([0-9]+)(?![$W])""")
    private val DOLLARS = Regex("""[$]\s?([0-9]+(?:[.,][0-9]+)*)""")
    private val EMOTICON = Regex("""(?:[:;=]['\-^o]?[()dDpP3vV/\\|*]+|>[:;=]['\-^o]?[()]+|<3+|-_-|\^_*\^|[Tt]_[Tt]|>_<|orz|OTZ)""")
    private val STUTTER_ONSETS = listOf("ngh", "ng", "nh", "kh", "ch", "gh", "gi", "th", "tr", "ph", "qu")
    private val STUTTER_SOUND = mapOf("k" to "c", "w" to "v", "z" to "d", "j" to "gi", "f" to "ph")
    private val STUTTER = Regex("""([^$W]*)(\p{L}{1,3})-+(\p{L}.*)""", RegexOption.DOT_MATCHES_ALL)
    private val STUTTER_ALONE = Regex("""([^$W]*)(\p{L}{1,3})-+([^$W]*)""")
    private val CENSORED = Regex("""([^$W]*)(\p{L})\*+([^$W]*)""")
    /** "->", "-->", "=>", "→": sea-g2p reads "sang" / "đến" / "suy ra"; "<->" (both ways) stays. */
    private val ARROW_FORWARD = Regex("""(?<![<=-])(?:-+|=+)>|[→⇒➜➡➔⟶⟹]""")
    /** "<-", "<--", "←": no way to say it aloud (sea-g2p reads "nhỏ hơn"), so it goes; "<=" is a comparison and stays. */
    private val ARROW_BACK = Regex("""<(?:-+|={2,})(?!>)|[←⇐⟵⟸]""")
    /** Chỗ dính liền hai từ trong một chữ hiện (tách để đọc từng từ, mảnh dấu giữ nguyên). */
    private val GLUED = Regex("""(?:\.{2,}|[…—–])+""")
    /** English thousands: 1,500 is "một nghìn năm trăm"; Vietnamese decimals ("1,5") do not match. */
    private val THOUSANDS = Regex("(?<![0-9.,])[0-9]{1,3}(?:,[0-9]{3})+(?![0-9]|[.,][0-9])")
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

    private fun digit(char: Char?): Boolean = char != null && char in '0'..'9'

    private fun tilde(token: String): String = TILDES.replace(token) { match ->
        val left = token.getOrNull(match.range.first - 1)
        val right = token.getOrNull(match.range.last + 1)
        when {
            digit(left) && digit(right) -> " đến "
            digit(right) && !(left != null && left.isLetterOrDigit()) -> match.value // "~50 người": sea-g2p reads "khoảng"
            left != null && left.isLetter() && right != null && right.isLetter() -> " " // "Har~kun"
            else -> "" // "Hmm~"
        }
    }

    /** "~" stretching a voice ("Hmm~") goes, between numbers ("3~5", "10,000 ~ 15,000") it is "đến", before a number ("~50") sea-g2p reads "khoảng" - `_tildes` of vieneu.py. */
    private fun tildes(out: MutableList<String>) {
        for (index in out.indices) {
            val token = out[index]
            if ('~' !in token) continue
            if (token.trim { it in OPENERS || it in CLOSERS || it in PUNCT_MARKS }.trim('~').isNotEmpty()) { // other text in the word: look inside it
                out[index] = tilde(token)
                continue
            }
            val before = if (index > 0) out[index - 1].trimEnd { it in CLOSERS } else ""
            val after = if (index + 1 < out.size) out[index + 1].trimStart { it in OPENERS } else "" // a lone "~": look at the neighbours
            val numberAfter = digit(after.firstOrNull())
            var said = TILDES.replace(token, if (numberAfter && digit(before.lastOrNull())) "đến" else if (numberAfter) "~" else "")
            if (index > 0 && said.trim { it in CLOSERS || it in PUNCT_MARKS }.isEmpty()) { // "Ô ~," -> "Ô,"
                out[index - 1] = out[index - 1] + said
                said = ""
            }
            out[index] = said
        }
    }

    private fun arrow(original: String, atStart: Boolean): String {
        var token = original
        fun replace(match: MatchResult, wordIn: String): String {
            val left = token.getOrNull(match.range.first - 1)
            val right = token.getOrNull(match.range.last + 1)
            val word = if (left == null && atStart) "" else wordIn // "-> Bước tiếp": an arrow opening a line is only a bullet
            if (word.isNotEmpty()) return (if (left != null && left.isLetterOrDigit()) " " else "") + word + (if (right != null && right.isLetterOrDigit()) " " else "")
            return if (left != null && left.isLetterOrDigit() && right != null && right.isLetterOrDigit()) " " else ""
        }
        token = ARROW_FORWARD.replace(token) { replace(it, "thành") }
        return ARROW_BACK.replace(token) { replace(it, "") }
    }

    /**
     * Text arrows: "1780 --> 1940", "A -> B", "=>", "→" are "thành" (sea-g2p reads "sang" / "đến" / "suy ra"); a backward arrow "<-", "←" has nothing to say so it goes; an arrow opening
     * a paragraph or a sentence is a bullet, it goes too - `_arrows`.
     */
    private fun arrows(out: MutableList<String>) {
        for (index in out.indices) {
            val token = out[index]
            if (token.none { it in "<>=→⇒➜➡➔⟶⟹←⇐⟵⟸" }) continue
            val before = if (index > 0) out[index - 1].trimEnd { it in CLOSERS } else ""
            out[index] = arrow(token, before.isEmpty() || before.last() in SENTENCE_END)
        }
    }

    /**
     * <Skill name> -> Skill name (sea-g2p reads "nhỏ hơn ... lớn hơn"): the angle brackets around words go; a name of two or more words gets a comma
     * on both sides for the pause. "<" is a bracket only right before a letter and with a ">" within [ANGLE_REACH] words; "3 < 5", "<3", ">:)" stay - `_angle`.
     */
    private fun angle(out: MutableList<String>) {
        var index = 0
        while (index < out.size) {
            val body = out[index].trimStart { it in OPENERS }
            val start = out[index].length - body.length
            val next = if (index + 1 < out.size) out[index + 1].trimStart { it in OPENERS } else ""
            val bracket = body.getOrNull(1)?.isLetter() == true || (body == "<" && next.firstOrNull()?.isLetter() == true) ||
                (body.getOrNull(1)?.isDigit() == true && '>' in body.drop(2)) // "<50/50>": số trong ngoặc phải đóng ngay trong chữ này ("<3" là trái tim)
            if (body.isEmpty() || body[0] !in ANGLE_OPEN || (body[0] == '<' && !bracket)) {
                index++
                continue
            }
            val run = body.length - body.trimStart { it in ANGLE_OPEN }.length
            var endToken = -1
            var endAt = -1
            var last = index
            while (last < minOf(out.size, index + ANGLE_REACH) && endToken < 0) {
                val text = out[last]
                for (at in (if (last == index) start + run else 0) until text.length) {
                    if (text[at] in ANGLE_CLOSE && !(text[at] == '>' && at > 0 && text[at - 1] in "-=")) {
                        endToken = last
                        endAt = at
                        break
                    }
                }
                last++
            }
            if (endToken < 0) {
                if (body[0] == '<' && (body.getOrNull(1)?.isLetter() == true || next.firstOrNull()?.isUpperCase() == true)) { // "< Thật Tuyệt vời" không có ngoặc đóng: dấu mở chỉ là trang trí
                    out[index] = out[index].substring(0, start) + out[index].substring(start + run)
                }
                index++
                continue
            }
            val tail = out[endToken].substring(endAt)
            val size = tail.length - tail.trimStart { it in ANGLE_CLOSE }.length
            out[endToken] = out[endToken].substring(0, endAt) + out[endToken].substring(endAt + size)
            out[index] = out[index].substring(0, start) + out[index].substring(start + run)
            if (endToken > index) { // a name of several words: commas before and after
                val rest = out[endToken].substring(endAt) // what is left of the word after the closing bracket ("Star〉[Cầu" -> "[Cầu")
                if (endAt > 0 && out[endToken][endAt - 1].isLetterOrDigit() && rest.firstOrNull()?.let { it !in PUNCT_MARKS } != false &&
                    (rest.trimStart { it in CLOSERS }.isNotEmpty() || endToken + 1 < out.size)) out[endToken] = out[endToken].substring(0, endAt) + "," + rest
                val core = if (index > 0) out[index - 1].trimEnd { it in CLOSERS } else ""
                if (core.isNotEmpty() && core.last().isLetterOrDigit()) out[index - 1] = core + "," + out[index - 1].substring(core.length)
            }
            index = endToken + 1
        }
    }

    /** "Đóng băng / yếu": a lone slash between two words is a comma on the word before (sea-g2p reads "trên"); between numbers it stays - `_slashes`. */
    private fun slashes(out: MutableList<String>) {
        for (index in 1 until out.size - 1) {
            val after = out[index + 1].trimStart { it in OPENERS }
            if (out[index] == "/" && out[index - 1].lastOrNull()?.isLetter() == true && after.firstOrNull()?.isLetter() == true) {
                out[index - 1] = out[index - 1] + ","
                out[index] = ""
            }
        }
    }

    private fun range(match: MatchResult): String {
        val parts = listOf(match.groupValues[1]) + match.groupValues[2].split("-").drop(1)
        if (parts.size == 2) {
            val (first, second) = parts
            if (first.toInt() < second.toInt()) return "$first đến $second" // sea-g2p drops "đến" in "3-4000"
            return if (first == second || (first.length == 1 && second.length == 1)) "$first $second" else match.value // "1-1" (class), "3-1" (score): two numbers in a row
        }
        if (parts.all { it.length <= 2 && !it.startsWith("0") }) return parts.joinToString(" ") // "1-3-1": a row of numbers, not a range
        return match.value // a date "01-10-2026", a phone number "090-123-4567"
    }

    /** Numbers sea-g2p reads differently from the listener's ear: small fractions "1/3" are "một phần ba", "3-4000" has its "đến", "1-1" / "1-3-1" are numbers in a row, "x2" is "nhân hai", "$5" is "năm đô la" - `_numbers`. */
    private fun numbers(out: MutableList<String>) {
        for ((index, original) in out.withIndex()) {
            if (original.none { it.isDigit() }) continue
            var token = FRACTION.replace(original) { m -> if (m.groupValues[1].toInt() < m.groupValues[2].toInt()) "${m.groupValues[1]} phần ${m.groupValues[2]}" else m.value }
            token = RANGE.replace(token) { m -> range(m) }
            token = TIMES.replace(token) { m -> "nhân ${m.groupValues[1]}" }
            out[index] = DOLLARS.replace(token) { m -> "${m.groupValues[1]} đô la" }
        }
    }

    /** Text smileys (":3", ":))", ">:)", "<3", "-_-", "orz") cannot be read: they go, the punctuation after them stays - `_emoticons`. */
    private fun emoticons(out: MutableList<String>) {
        for ((index, token) in out.withIndex()) {
            val body = token.trimEnd { it in "!?.,\"”’…" }
            if (body.isNotEmpty() && EMOTICON.matches(body.trimStart { it in "\"“‘" })) out[index] = token.substring(body.length)
        }
    }

    /** The sound of a stuttered [frag] at the start of [rest] ("C" before "chuyện" is "chờ", "E" before "em" is "e") - `stutter_sound`. */
    private fun stutterSound(frag: String, rest: String): String {
        val lowered = frag.lowercase(Locale.ROOT)
        val word = Normalizer.normalize(rest, Normalizer.Form.NFC).lowercase(Locale.ROOT)
        if (Normalizer.normalize(lowered, Normalizer.Form.NFD)[0] in "aeiouy") return lowered
        val onset = STUTTER_ONSETS.firstOrNull { it.startsWith(lowered) && word.startsWith(it) } ?: lowered
        return (STUTTER_SOUND[onset] ?: onset) + "ờ"
    }

    /** "*" is decoration ("*từ*", "(*)"): it goes; a letter before a censoring star ("đ*") is read like a stutter ("đờ…") - `_stars`. */
    private fun stars(out: MutableList<String>) {
        for ((index, token) in out.withIndex()) {
            if ('*' !in token) continue
            val censored = CENSORED.matchEntire(token)
            out[index] = if (censored != null) censored.groupValues[1] + stutterSound(censored.groupValues[2], censored.groupValues[2]) + "…" + censored.groupValues[3] else token.replace("*", "")
        }
    }

    /** Stuttering "T-tôi", "C-Chuyện", "E-em", "[Kh- Không": the stutter is read as a sound ("tờ… tôi", "chờ… chuyện", "e… em"), the rest of the word as usual - `_stutters`. */
    private fun stutters(toks: List<String>, out: MutableList<String>, origin: String?) {
        for ((index, token) in toks.withIndex()) {
            var match = STUTTER.matchEntire(token)
            val alone = match == null
            var tail = ""
            val rest: String
            if (match != null) {
                rest = match.groupValues[3]
            } else {
                match = STUTTER_ALONE.matchEntire(token)
                if (match == null || index + 1 >= toks.size) continue
                rest = toks[index + 1].trimStart { it in OPENERS }
                tail = match.groupValues[3]
            }
            val before = match.groupValues[1]
            val frag = match.groupValues[2]
            if (!Normalizer.normalize(rest, Normalizer.Form.NFC).lowercase(Locale.ROOT).startsWith(frag.lowercase(Locale.ROOT))) continue
            if (frag.length > 1 && Normalizer.normalize(frag.lowercase(Locale.ROOT), Normalizer.Form.NFD).any { it in "aeiouy" }) continue
            val sound = stutterSound(frag, rest)
            out[index] = if (alone) {
                val next = tail.trimStart { it in CLOSERS }.firstOrNull()
                before + sound + (if (next != null && next in PUNCT_MARKS) "" else "…") + tail
            } else {
                before + sound + "… " + spokenTokens(listOf(rest), origin)[0]
            }
        }
    }

    /** CJK punctuation ("đi，nhà ta", "734：Chúng ta") becomes the ordinary mark; glued to the next word it gets a space - `_fullwidth`. */
    private fun fullwidth(out: MutableList<String>) {
        for ((index, token) in out.withIndex()) {
            if (token.none { it in FULLWIDTH }) continue
            val said = StringBuilder()
            for ((at, char) in token.withIndex()) {
                said.append(FULLWIDTH[char] ?: char)
                if (char in FULLWIDTH && token.getOrNull(at + 1)?.isLetterOrDigit() == true) said.append(' ')
            }
            out[index] = said.toString()
        }
    }

    /** A dash glued to words ("Babi—người", "nên— Cảm ơn") is a pause sea-g2p loses (it only pauses at a spaced dash): a comma - `_dashes`. */
    private fun dashes(out: MutableList<String>) {
        for ((index, token) in out.withIndex()) {
            if (token.none { it in DASHES }) continue
            val said = StringBuilder()
            var at = 0
            while (at < token.length) {
                var end = at
                while (end < token.length && token[end] in DASHES) end++
                if (end == at) {
                    said.append(token[at])
                    at++
                    continue
                }
                val after = token.getOrNull(end)
                val glued = at > 0 && token[at - 1].isLetterOrDigit()
                if (glued && after != null && after.isLetterOrDigit()) said.append(", ")
                else if (glued && after == null && index + 1 < out.size) said.append(",")
                else said.append(token, at, end)
                at = end
            }
            out[index] = said.toString()
        }
    }

    /** 【Name】, [Notice], 〔..〕 glued to words get a comma at both ends (a pause, like parentheses); a frame holding only a number ("[1]") is a footnote mark and stays - `_frames`. */
    private fun frames(out: MutableList<String>) {
        val quotes = "\"'“‘«("
        for (index in out.indices) {
            var token = out[index]
            if (token.none { it in SYSTEM_OPEN || it in SYSTEM_CLOSE }) continue
            val bare = token.trim { it in SYSTEM_OPEN || it in SYSTEM_CLOSE || it in quotes || it in CLOSERS || it in PUNCT_MARKS }
            if (bare.isNotEmpty() && bare.all { it.isDigit() }) continue
            val said = StringBuilder()
            for ((at, char) in token.withIndex()) {
                if (char in SYSTEM_OPEN && at > 0 && token[at - 1].isLetterOrDigit()) said.append(',')
                said.append(char)
                if (char in SYSTEM_CLOSE && token.getOrNull(at + 1)?.isLetterOrDigit() == true) said.append(',')
            }
            token = said.toString()
            if (token.trimStart { it in quotes }.firstOrNull()?.let { it in SYSTEM_OPEN } == true && index > 0) { // an opening frame at the start of the word: the comma goes on the word before
                val previous = out[index - 1]
                val core = previous.trimEnd { it in CLOSERS && it != ']' }
                if (core.lastOrNull()?.isLetterOrDigit() == true) out[index - 1] = core + "," + previous.substring(core.length)
            }
            val core = token.trimEnd { it in "\"'”’»)" }
            if (core.lastOrNull()?.let { it in SYSTEM_CLOSE } == true && index + 1 < out.size &&
                out[index + 1].trimStart { it in quotes.replace("(", "") || it in "【〔[{" }.firstOrNull()?.isLetterOrDigit() == true) token = core + "," + token.substring(core.length)
            out[index] = token
        }
    }

    /** Roman numerals standing right become Vietnamese numbers, in place in [out] - see [spokenTokens]. */
    private fun romanNumbers(toks: List<String>, out: MutableList<String>) {
        for ((index, token) in toks.withIndex()) {
            val core = token.trimStart { it in OPENERS || it in FRAMES_OPEN }.trimEnd { it in CLOSERS || it in FRAMES_CLOSE || it in ".,;:!?…" }
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
    }

    private fun splitGlued(token: String): List<String> {
        val parts = ArrayList<String>()
        var last = 0
        for (m in GLUED.findAll(token)) {
            parts.add(token.substring(last, m.range.first))
            parts.add(m.value)
            last = m.range.last + 1
        }
        parts.add(token.substring(last))
        return parts
    }

    /**
     * The per-word steps (Roman numerals, level, abbreviations, names, loanwords). A word glued to the next through "…" or "—" ("rồi…Senpai", "Babi—người", "DP?”…Tốn") is split
     * apart for a moment so each word is judged alone, then put back; a word an earlier step changed stays as it is - `_read_words`.
     */
    private fun readWords(toks: List<String>, out: MutableList<String>, origin: String?) {
        val pieces = ArrayList<String>()
        val said = ArrayList<String>()
        val owner = ArrayList<Int>()
        for ((index, token) in toks.withIndex()) {
            val unchanged = out[index] == token
            for (part in if (unchanged) splitGlued(token) else listOf(token)) {
                pieces.add(part)
                said.add(if (unchanged) part else out[index])
                owner.add(index)
                if (!unchanged) break
            }
        }
        romanNumbers(pieces, said)
        Abbreviations.readLevels(pieces, said)
        Abbreviations.readTitles(pieces, said)
        Abbreviations.readShoutedHonorifics(pieces, said, origin)
        Abbreviations.spellAbbreviations(pieces, said)
        Names.readNames(pieces, said, origin)
        Names.readHonorifics(pieces, said, origin)
        Names.readLoanwords(pieces, said)
        val rebuilt = Array(toks.size) { "" }
        for (k in pieces.indices) rebuilt[owner[k]] += said[k]
        for (index in toks.indices) out[index] = rebuilt[index]
    }

    /** Marks sea-g2p reads wrongly as words ("~" is "khoảng", "500,000" is "năm trăm"), fixed in place without changing the word count - `reading_marks`. */
    fun readingMarks(out: MutableList<String>) {
        fullwidth(out)
        emoticons(out)
        arrows(out)
        tildes(out)
        for (index in out.indices) out[index] = THOUSANDS.replace(out[index]) { it.value.replace(",", "") }
        numbers(out)
        angle(out)
        slashes(out)
        dashes(out)
        frames(out)
        stars(out)
        for (index in out.indices) out[index] = out[index].filterNot { it in ANGLE_OPEN.drop(1) || it in ANGLE_CLOSE.drop(1) } // leftover 《》〈〉 without a pair are only a frame
    }

    /**
     * Shown words -> words to read (a reading-only change, the shown text stays): an upper-case Roman numeral I..XXXIX standing alone after a word
     * with a lower-case letter ("Phổ thông II", "Chương IV"), after a numeral just read ("Mục II, III"), or as a heading at the start of the
     * paragraph ("I. Mở đầu") is read as a Vietnamese number - sea-g2p only knows "Benedict III" and reads "thông II" as "i i". "I am" at the
     * start, an "I" after punctuation and abbreviations (CV, MC, VIP) never become numbers. In a book with a Japanese / Korean [origin] ("ja" / "ko") romaji / RR names are read by the
     * romanization rules ("Haruto" -> "Ha-ru-tô", [Names.readNames]); real English words are left to sea-g2p. In every book: stretched sounds ("Aaaa" -> "a… a", [Shouts]),
     * capital abbreviations by their letter names ("HP" -> "hát pê", [Abbreviations]) and hyphenated honorifics ("Ariel-sama" -> "Ariel-xa-ma", [Names.readHonorifics]). Last `readingMarks` fixes "~", English thousands,
     * <angle brackets> and " / ". `spoken_tokens` of vieneu.py.
     */
    fun spokenTokens(toks: List<String>, origin: String? = null): List<String> {
        val out = toks.toMutableList()
        stutters(toks, out, origin)
        Shouts.readShouts(toks, out)
        readWords(toks, out, origin)
        readingMarks(out)
        return out
    }

    /** `VieneuProvider.reading_tag`: the [origin] when it makes this paragraph sound different (some name read by the rules), else "" - part of the clip cache key. */
    fun readingTag(text: String, origin: String?): String {
        if (origin == null || origin !in Names.ORIGINS) return ""
        val toks = tokens(text)
        return if (spokenTokens(toks, origin) != spokenTokens(toks)) origin else ""
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

    /** The paragraph's shown words and its units (every shown word in exactly one unit, in order). [origin]: the book's origin, see [spokenTokens]. */
    fun units(text: String, maxChars: Int, origin: String? = null): Pair<List<String>, List<Unit>> {
        val toks = tokens(text)
        if (toks.isEmpty()) return toks to emptyList()
        val said = spokenTokens(toks, origin)
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
            val words = said.subList(piece[0], piece[1] + 1).filter { it.isNotEmpty() }.joinToString(" ")
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
