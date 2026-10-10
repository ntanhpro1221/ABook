package vn.abook.player.readaloud

import vn.abook.player.vieneu.VieneuUnits
import java.text.Normalizer
import java.util.concurrent.ConcurrentHashMap

/**
 * Ký hiệu trong "Nghe ngay" đọc theo NGỮ CẢNH (±3 chữ quanh ký hiệu, có khi cả câu) - bản Kotlin y hệt `abook/readaloud/symbols.py` (cùng luật, cùng fixture
 * tests/fixtures/vieneu/android/text.json): "/" là ngày, "mỗi", "phần" hay "trên"; "-" trước số là "âm", "trừ" hay "đến"; "x4" là "nhân bốn"...
 *
 * `readSymbols(toks, out)` sửa tại chỗ `out` (cách đọc từng chữ hiện), số chữ không đổi. Ngữ cảnh lấy từ `toks` (chữ hiện chưa đổi: "HP" chứ không phải "hát pê") khi có.
 * Một lời ("nhân", "mỗi") được thêm khoảng trắng hai bên khi dính chữ / số; im (rỗng) thì hai chữ dính hai bên được tách bằng một khoảng trắng; "im + ngắt" thêm dấu phẩy khi ký hiệu
 * nằm GIỮA hai chữ; không rõ nghĩa thì để nguyên cho sea-g2p. Mỗi hàm ở đây tên theo hàm Python cùng chỗ (`_slash` -> [slash]...).
 */
object Symbols {
    private const val OPEN = "\"'“‘([【「『《〈«{〔"
    private const val CLOSE = "\"'”’)]】」』》〉»}〕"
    private const val PUNCT_MARKS = ".,;:!?…"
    private const val W = """\p{L}\p{N}_"""
    private val FRACTION_HINTS = "bằng còn gấp hơn kém nửa chia".split(" ").toSet()
    val STAT_WORDS = ("hp mp sp exp xp lv lvl level cấp hạng rank điểm giá str agi vit int dex luk atk def máu mana tiền vàng tuổi sức mạnh nhanh nhẹn phòng thủ thể lực ma lực thiện cảm kinh nghiệm chỉ số tốc độ quyến " +
        "rũ cảm tính may mắn").split(" ").toSet()
    private val DATE_WORDS = "ngày mùng mồng hôm nhật lịch hạn sáng trưa chiều tối lễ tết niệm".split(" ").toSet()
    private val DATE_PREFIX = "ngày mùng mồng hôm".split(" ").toSet()
    private val WEEKDAY = Regex("thứ (?:hai|ba|tư|năm|sáu|bảy)|chủ nhật")
    private val TEMP_WORDS = "độ nhiệt °c oc f".split(" ").toSet()
    private val PER_PHYSICAL = "h s giờ phút giây min hr sec ms".split(" ").toSet()
    // "km/h", "50km/h", "kg/m2": "/" dính liền giữa HAI đơn vị đo là "trên" - để nguyên cả cặp cho sea-g2p (symbols.py UNIT_BEFORE / UNIT_AFTER).
    private val UNIT_BEFORE = Regex("""(?<!\p{L})(?:km|cm|dm|mm|m|kg|mg|g|ml|mL|l|L)$""")
    private val UNIT_AFTER = Regex("""^(?:h|ms|s|giờ|phút|giây|(?:km|cm|dm|mm|m)[23²³]?|kg|mg|g|ml|mL|l|L)(?![\p{L}\p{N}])""")
    private val PER_NOUNS = "ngày tuần tháng năm máy người lần cái chương tập".split(" ").toSet()
    private val RATIO_WORDS = "tỉ tỷ lệ chia cược kèo".split(" ").toSet()
    val DUEL_WORDS = "đấu đối trận đơn song solo đánh".split(" ").toSet()
    private val RATIO_SLASH = "tỉ tỷ lệ xác suất chia".split(" ").toSet()
    private val DIRECTION_WORDS = "tăng giảm lên xuống cao thấp up down".split(" ").toSet()
    private val KEY_WORDS = "ctrl alt shift tab esc enter".split(" ").toSet()
    private val NUMBER_WORDS = "không một hai ba bốn năm sáu bảy tám chín mười".split(" ").toSet()
    private val KEYS = mapOf('↑' to "lên", '↓' to "xuống", '←' to "trái", '→' to "phải", '↖' to "lên trái", '↗' to "lên phải", '↘' to "xuống phải", '↙' to "xuống trái")
    private val KEY_RUN = Regex("[" + KEYS.keys.joinToString("") + "]{2,}")
    private const val KAOMOJI = "´゜∀◕◡‿≧≦╯╰╭ω∇ಠ益ﾉﾟдДᴗヮ꒳˶˘ʕʔᴥ◠ヽ٩۶ᕕᕗ꒪ↀ͜͡ʖ￣ェ⑉﹏"
    private val KAOMOJI_SPAN = Regex("""[^\s$W?!.,…"“”]*[$KAOMOJI][^\s$W?!.,…"“”]*""")
    private val FACE_UNDERSCORE = Regex("""\([\^=;°]_+[\^=;°]\)""")
    private val GRAWLIX = Regex("""(?=[!@#$%^&*?]*[@#$%^&][!@#$%^&*?]*[@#$%^&])[!@#$%^&*?]{3,}""")
    private val POSTSCRIPT = Regex("""(?<![A-Za-z])[Pp]/[Ss](?![A-Za-z])""")
    private val URL = Regex("""(?:https?://|www\.)\S+|(?<![$W.])[$W-]+(?:\.[$W-]+)*\.(?:com|net|org|vn|jp|re|io|me|tv|info|co|app)/\S*""", RegexOption.IGNORE_CASE)
    private const val URL_TAIL = ".,;:!?)]}>”’\"'"
    private val ENTITIES = listOf("&gt;" to ">", "&lt;" to "<", "&amp;" to "&", "&quot;" to "\"")
    private const val STARS = "★☆✩✪✫✬✭✮✯✰⭐"
    private const val STAR_FULL = "★✪✮⭐"
    private const val STAR_MARKS = STARS + "︎️"
    private val SPECIAL = ("/／=#＃@＠^·<>+＋-–—―xX×$°&＆♀♂≠☎☏:↑↓▲▼△▽" + STARS).toSet()
    private val NUMBER = Regex("""[+-]?\d+(?:[.,]\d+)*%?""")
    private val NUMBERISH = Regex("""\d+[A-Za-z%°]*""")
    private val DIGIT_WORDS = listOf("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "mười")

    private val cache = ConcurrentHashMap<String, Regex>()
    private fun rx(pattern: String): Regex = cache.getOrPut(pattern) { Regex(pattern) }

    /** `re.search`. */
    private fun search(pattern: String, text: String): MatchResult? = rx(pattern).find(text)

    /** `re.match` (anchored at the start only). */
    private fun match(pattern: String, text: String): MatchResult? = rx("^(?:$pattern)").find(text)

    /** The word with punctuation and brackets trimmed off both ends ("[Cường" -> "Cường", "1940." -> "1940"). */
    fun core(word: String): String = word.trim { !it.isLetterOrDigit() }

    private fun numberish(word: String) = NUMBER.matches(word) || NUMBERISH.matches(word)

    /** `char` (one character, null at the end) is in [chars]. */
    private fun has(char: Char?, chars: String) = char != null && char in chars

    private fun single(word: String?) = word != null && word.length == 1 && (word[0] in 'A'..'Z' || word[0] in 'a'..'z')

    private fun String.letter0() = firstOrNull()?.isLetter() == true
    private fun String.upper0() = firstOrNull()?.isUpperCase() == true
    private fun String.isUpperStr() = any { it.isUpperCase() } && none { it.isLowerCase() }
    private fun String.nfc() = Normalizer.normalize(this, Normalizer.Form.NFC)
    private fun words(text: String) = text.split(Regex("\\s+")).filter { it.isNotEmpty() }
    private infix fun Set<String>.hit(other: Set<String>) = any { it in other }

    /** `Number.group` -> Long (at most 14 digits are ever read). */
    private fun long(text: String) = text.toLongOrNull() ?: Long.MAX_VALUE

    /** "0.15" is "0 phẩy mười lăm" (two fraction digits read as one number), "5,0" is "5 phẩy 0"; an integer stays - `_decimal`. */
    private fun decimal(number: String): String {
        val match = rx("""(\d+)[.,](\d+)""").matchEntire(number) ?: return number
        val whole = match.groupValues[1]
        var fraction = match.groupValues[2]
        if (fraction.length == 2 && fraction[0] != '0') fraction = VieneuUnits.vietnameseNumber(fraction.toInt())
        return "$whole phẩy $fraction"
    }

    private fun kind(char: Char?): String = when {
        char == null -> "edge"
        char.isWhitespace() -> "space"
        char.isDigit() -> "digit"
        char.isLetter() -> if (char.isUpperCase()) "upper" else if (char.isLowerCase()) "lower" else "alpha"
        char in OPEN -> "open"
        char in CLOSE -> "close"
        char in PUNCT_MARKS -> "punct"
        else -> "sym"
    }

    /** One symbol `sym` and the words around it: `left` / `right` are every shown word to the left / right on the same paragraph (a space apart, like the tokens). */
    private class Spot(leftIn: String, val sym: String, rightIn: String) {
        val left = leftIn.nfc()
        val right = rightIn.nfc()
        val lch: Char? = left.lastOrNull()
        val rch: Char? = right.firstOrNull()
        val ltype = kind(lch)
        val rtype = kind(rch)
        val gluedL = left.isNotEmpty() && !left.last().isWhitespace()
        val gluedR = right.isNotEmpty() && !right.first().isWhitespace()
        val l1: String
        val l2: String
        val l3: String
        val r1: String
        val r2: String
        val r3: String
        val lw1: String
        val rw1: String
        val left3: Set<String>
        val right3: Set<String>
        val lineStart = left.trim { it in " \t$OPEN-–—" }.isEmpty()
        val lineEnd = right.trim { it in " \t$CLOSE.,!?…" }.isEmpty()
        val colonBefore: Boolean
        val count: Int

        init {
            val before = words(left).takeLast(3).map { core(it) }.reversed().toMutableList()
            val after = words(right).take(3).map { core(it) }.toMutableList()
            while (before.size < 3) before.add("")
            while (after.size < 3) after.add("")
            l1 = before[0]; l2 = before[1]; l3 = before[2]
            r1 = after[0]; r2 = after[1]; r3 = after[2]
            lw1 = l1.lowercase()
            rw1 = r1.lowercase()
            left3 = before.map { it.lowercase() }.toSet()
            right3 = after.map { it.lowercase() }.toSet()
            val sentence = search("""[.!?…]\s+[^.!?…]*$""", left)
            colonBefore = ':' in (if (sentence != null) left.substring(sentence.range.first + 1) else left)
            count = Regex(Regex.escape(sym.take(1)) + "+").findAll(left + sym + right).count()
        }

        fun near(size: Int = 20) = left.takeLast(size) + sym + right.take(size)
    }

    /** Said text (null = leave it to sea-g2p, "" = silent) and whether to pause. */
    private class Said(val text: String?, val stop: Boolean = false, val back: Int = 0)
    private class Found(val end: Int, val said: Said, val back: Int = 0)

    private val KEEP = Said(null)
    private val SILENT = Said("")
    private val PAUSE = Said("", true)
    private fun say(text: String) = Said(text)

    // ---- one symbol: said / silent / keep, with a pause or not --------------------------------------------------------------------------------
    /** "/" giữa hai đơn vị đo ("km/h", "50km/h", "kg/m2"), như symbols.unit_slash (SpokenSymbols dùng chung cho Studio). */
    fun unitSlash(left: String, right: String): Boolean =
        UNIT_BEFORE.containsMatchIn(left.takeLast(8)) && UNIT_AFTER.containsMatchIn(right.take(8))

    private fun slash(c: Spot): Said {
        if (c.sym.length > 1) return SILENT
        if (unitSlash(c.left, c.right)) return KEEP  // "50km/h", "3 kg/m2": sea-g2p đọc cả cặp "ki lô mét trên giờ"
        val m = search("""(\d+)\s?$""", c.left.takeLast(14))
        val k = match("""\s?(\d+)""", c.right.take(14))
        if (m != null && k != null) {
            val a = long(m.groupValues[1])
            val b = long(k.groupValues[1])
            if (search("""\d\s?/\s?\d+\s?$""", c.left.takeLast(12)) != null || match("""\s?\d+\s?/\s?\d""", c.right.take(14)) != null) return KEEP
            val words = c.left3 + c.right3
            val valid = a in 1..31 && b in 1..12
            if (a <= 12 && b in 1900..2100) return say("năm")
            if (!(c.gluedL && c.gluedR)) return KEEP
            if ((c.left3 hit STAT_WORDS) && !(a < b && b <= 9 && (c.left3 hit FRACTION_HINTS))) return KEEP
            if (c.left3 hit RATIO_SLASH) return if (a < b) say("phần") else KEEP
            val signal = (words intersect DATE_WORDS) - (if (words hit setOf("đa", "thiểu", "ưu", "cao")) setOf("tối") else emptySet()) // "tối đa 3/5" không phải buổi tối
            if (valid && (signal.isNotEmpty() || WEEKDAY.containsMatchIn((c.left.takeLast(30) + " " + c.right.take(30)).lowercase()))) {
                if (c.l2.lowercase() in DATE_PREFIX) return say("tháng") // "ngày 5/3": đã có "ngày"
                return Said("ngày ${m.groupValues[1]} tháng", false, m.groupValues[1].length) // "sinh nhật 5/3"
            }
            if ((a == 24L && b == 7L) || (a == 1L && b == 1L) || (b in listOf(10L, 100L) && a <= b) || (a == b && match("""\d+\s?[)\]]""", c.right) != null)) return KEEP
            if ((a == 1L && b > 1) || (a < b && b <= 9)) return say("phần")
            return KEEP
        }
        if (c.lch == '?' && k != null) return say("trên")
        val rightWord = match("""\p{L}+""", c.right)?.value?.lowercase() ?: ""
        val digitNear = c.ltype == "digit" || search("""\d\s?\p{L}{1,4}$""", c.left.takeLast(8)) != null
        if (digitNear && c.rtype in listOf("lower", "upper", "digit")) return if (rightWord in PER_PHYSICAL) say("trên") else say("mỗi")
        val glued = c.gluedL && c.gluedR && c.ltype in listOf("lower", "upper") && c.rtype in listOf("lower", "upper")
        if (glued && rightWord in PER_NOUNS) return say("mỗi")
        if (glued && rightWord in PER_PHYSICAL) return KEEP
        if (c.lineEnd || c.right.isBlank() || c.rtype in listOf("close", "punct") || has(c.lch, "?!.")) return SILENT
        if (c.l1.letter0() && c.r1.letter0()) return PAUSE
        return SILENT
    }

    private fun equals(c: Spot): Said {
        if (c.sym.length >= 2) return SILENT
        if (has(c.lch, "<>!")) return KEEP
        val smile = has(c.rch, ")(]._[=") && !(has(c.rch, "([") && c.ltype in listOf("lower", "upper", "digit") && match(""".[$W(]""", c.right) != null)
        if (smile || has(c.lch, "#$%^&=°") || c.rch == '°' || (c.lch == '(' && c.rch != null && c.rch != ' ')) return SILENT
        if (search("""[?&][$W%.-]*$""", c.left.takeLast(14)) != null && match("""[$W%-]""", c.right) != null) return SILENT
        if (c.gluedL && c.gluedR && c.ltype in listOf("lower", "upper") && c.rtype in listOf("lower", "upper") && (c.l1.length >= 2 || c.r1.length >= 2)) return SILENT
        if (has(c.rch, "^%$#@")) return SILENT
        val near = c.near(24)
        if (match("""\d""", c.r1) != null || match("""\d""", c.l1.takeLast(1)) != null || '+' in near || '>' in near || "cộng" in near.lowercase() || single(c.l1) || single(c.r1)) return say("bằng")
        return say("là")
    }

    private fun plus(c: Spot): Said {
        if (c.sym.length >= 2) return if (c.gluedL && c.ltype in listOf("upper", "lower", "digit")) say(List(minOf(c.sym.length, 3)) { "cộng" }.joinToString(" ")) else SILENT
        if (c.lineStart && !c.gluedR) return SILENT
        if (c.gluedR && !c.gluedL && c.rtype in listOf("upper", "lower") && c.ltype in listOf("space", "open", "edge")) return SILENT
        if (c.ltype == "sym" || c.rtype == "sym") return SILENT
        if (c.gluedL && c.ltype in listOf("upper", "digit") && c.rtype !in listOf("lower", "upper", "digit")) return KEEP
        if (c.lineEnd || (c.lch == '(' && c.rch == ')') || c.lch == '_') return SILENT
        if (c.rtype == "digit" || c.ltype == "digit") return KEEP
        if (c.gluedL && c.gluedR && c.ltype != "sym" && c.rtype != "sym") return say("cộng")
        val words = c.l1.letter0() && c.r1.letter0()
        if (words && (c.lw1 in KEY_WORDS || c.rw1 in KEY_WORDS || c.l1.isUpperStr() || c.r1.isUpperStr())) return say("cộng")
        if (words && search("""=|(?<![$W])bằng(?![$W])""", c.near(40)) != null) return say("cộng")
        if (words && !((c.left3 + c.right3) hit STAT_WORDS) && (c.l1 + c.r1).none { it.isDigit() }) return say("và")
        return KEEP
    }

    private fun hash(c: Spot): Said {
        if (c.sym.length >= 2) return SILENT
        if (c.lw1 in listOf("số", "no") && !c.gluedL) return SILENT
        if (match("""\s?\d""", c.right) != null && (!c.lineStart || c.gluedR) && c.ltype != "sym") return say("số")
        return SILENT
    }

    private fun at(c: Spot): Said {
        if (c.sym.length >= 2) return SILENT
        val wordL = c.ltype in listOf("lower", "upper") && c.gluedL
        val wordR = c.rtype in listOf("lower", "upper") && c.gluedR
        val smiley = match("""[wεoO_.-]{1,2}@""", c.right) != null || has(c.lch, "wεoO_")
        if (wordL && wordR && !smiley) {
            if (match("""[$W-]+(?:\.[$W-]+)+""", c.right) != null) return KEEP
            val leftWord = search("""\p{L}+$""", c.left)?.value ?: ""
            val rightWord = match("""\p{L}+""", c.right)!!.value
            return if (minOf(leftWord.length, rightWord.length) <= 3) say("a") else say("a còng")
        }
        if ((c.left3 hit setOf("ngày", "tháng", "năm")) || (c.right3 hit setOf("ngày", "tháng", "năm"))) return SILENT
        if (wordR && !wordL && c.ltype != "digit" && !smiley) {
            val leet = match("""[a-zà-ỹ]{1,3}(?![$W])""", c.right)
            return if (leet != null) say("a") else say("a còng")
        }
        if (!c.gluedL && !c.gluedR && c.l1.letter0() && !c.lineEnd) return say("a còng")
        return SILENT
    }

    private fun caret(c: Spot): Said = if (c.sym.length == 1 && c.ltype == "digit" && c.rtype == "digit") say("mũ") else SILENT

    /** "<" / ">" left after `angle`: comparison, ranking, chain of steps, or silent - `_angle_mark`. */
    private fun angleMark(c: Spot): Said {
        if (c.rch == '=' && c.sym.length == 1) return KEEP
        if ((c.sym == "<" && match("""-+>""", c.right) != null) || (c.sym == ">" && search("""<-+$""", c.left) != null)) return KEEP
        if (c.ltype in listOf("open", "sym") || c.rtype in listOf("open", "sym")) return SILENT
        val spaced = !c.gluedL && !c.gluedR
        val words = c.l1.letter0() && c.r1.letter0() && !c.lineStart
        if (c.sym.length >= 2 && !(c.sym[0] == '>' && c.sym.length <= 3 && spaced && words)) return SILENT
        if ((numberish(c.l1) || single(c.l1)) && (numberish(c.r1) || single(c.r1)) && c.rtype != "sym") return KEEP
        if (!words) return SILENT
        fun stat(word: String) = word.lowercase().trimEnd { it in "0123456789." } in STAT_WORDS
        if (stat(c.l1) || stat(c.r1)) return say("thành")
        val word = if (c.sym[0] == '>') "hơn" else "nhỏ hơn"
        val chain = c.count >= 2
        val listing = ':' in c.left.takeLast(80) || has(c.left.trimEnd().lastOrNull(), "])】」") || has(c.right.trimStart().firstOrNull(), "[(【「")
        if (chain && listing) return say("rồi")
        if (chain) return say(word)
        if (c.colonBefore && c.sym == ">") return say("rồi")
        if (!spaced) return SILENT
        return if (c.r1.upper0()) say(word) else PAUSE
    }

    /** "-" right before a number - `_minus`. */
    private fun minus(c: Spot): Said {
        val after = c.right
        if (c.lineStart) {
            if (match("""\d[\d.,]*\s?%""", after) != null && (c.right3 hit STAT_WORDS)) return say("trừ")
            if (match("""\d[\d.,]*[A-Za-z]{1,3}(?![$W])""", after) != null) return say("trừ")
            if (match("""\d{1,3}(?:,\d{3})+(?![$W])""", after) != null) return say("âm")
            if (match("""\d[\d.,]*\s+(điểm|hp|mp)(?![$W])""", after.lowercase()) != null) return if (has(c.lch, "[【〔")) say("trừ") else say("âm")
            return SILENT
        }
        val follow = after.take(14).lowercase()
        if (search("""(→|⇒|➜|➡|-+>|=+>)\s?$""", c.left.takeLast(6)) != null || search("""[▲▼△▽↑↓]\($""", c.left.takeLast(3)) != null) return say("âm")
        if ((c.right3 hit TEMP_WORDS) || '°' in follow.take(8) || match("""\d[\d.,]*\s?(độ|mét|oc|of)""", follow) != null) return say("âm")
        if (c.lch == ')' && c.gluedL) return SILENT
        if (c.ltype == "space" && has(c.left.trimEnd().lastOrNull(), "”’\"")) return SILENT
        if (match("""\d+\s?[:：]""", after) != null) return SILENT
        val previous = if (c.ltype == "space") search("""(\d+)(?:st|nd|rd|th)?\s$""", c.left.takeLast(6)) else null
        if (previous != null) {
            val number = match("""\d+""", after)!!.value
            return if (number == previous.groupValues[1]) SILENT else say("đến")
        }
        if (search("""[:：]\s?$""", c.left) != null || search("""(?<![$W])(?:[Ll]v|lờ vê)\.?$""", c.left) != null) return say("âm")
        if (c.lw1 in setOf("là", "tới", "xuống", "đến", "mức", "khoảng", "dưới", "ở", "tầng", "thành", "hoặc", "đa", "âm", "bằng", "sang", "lên")) return say("âm")
        return say("trừ")
    }

    /** A lone dash between two numbers ("7 – 8cm", "5 - 8 giờ"): đến - `_dash_range`. */
    private fun dashRange(c: Spot): Said =
        if (search("""\d[$W]{0,3}\s$""", c.left.takeLast(6)) != null && match("""\s\d""", c.right.take(3)) != null) say("đến") else KEEP

    /** "A-" grade (one capital glued to "-" and then the word ends): trừ - `_grade_minus`. */
    private fun gradeMinus(c: Spot): Said =
        if (c.colonBefore && c.ltype == "upper" && c.gluedL && search("""\p{L}{2}$""", c.left) == null && c.rtype in listOf("space", "close", "edge")) say("trừ") else KEEP

    /** "x4", "×3" (before a number, not glued to a word): nhân; a capital "X" before "0..." / digits+letter is a variable / name: ích - `_times_pre`. */
    private fun timesPre(c: Spot, sym: Char): Said =
        if (sym == 'X' && (c.right.startsWith("0") || match("""\d+[A-Za-z]""", c.right) != null)) say("ích") else say("nhân")

    /** "3x", "100x", "0,5x", "1x Cuộn phép", "194X" - the symbol right after a number: (said, stop, how many characters of the number before go into it) - `_times_post`. */
    private fun timesPost(c: Spot, sym: Char): Pair<Said, Int> {
        val number = search("""\d+(?:[.,]\d+)?$""", c.left)!!.value
        val start = c.left.substring(0, c.left.length - number.length)
        if (sym == 'X' || (search("""\d{3}$""", number) != null && !c.gluedR && match("""\s?[a-zà-ỹ]|\s+[A-ZĐ]""", c.right) == null)) return say("ích") to 0
        if (search("""[A-Za-z]$""", start) != null || search("""[+=(]""", c.left.takeLast(4) + c.right.take(3)) != null) return say("ích") to 0
        if ((c.left3 hit setOf("tuổi", "thế", "hệ", "gen", "đời", "sinh")) || (c.right3 hit setOf("km", "km/h", "m"))) return say("ích") to 0
        if (c.rch == '[' || (search("""(?:^|[\s\[(–—-])$""", start) != null && match("""\s+[A-ZĐ]""", c.right) != null)) return say("") to 0
        if ('.' in number || ',' in number) return say(number.replace(".", ",") + " lần") to number.length
        if (number.length >= 2) return say("gấp $number lần") to number.length
        return say("gấp $number") to number.length
    }

    /** "×" outside a number: a couple between two names ("và"), a title between two phrases (pause), a blank "Ngày × tháng", decoration - `_times_sign`. */
    private fun timesSign(c: Spot): Said {
        if (c.sym == "××") return if (c.ltype != "digit") say("ích ích") else SILENT
        if (c.sym.length >= 2) return SILENT
        val around = c.left3 + c.right3
        if ((around hit setOf("ngày", "tháng", "năm")) || has(c.lch, "○◯□■+=") || has(c.rch, "○◯□■+=×:")) return SILENT
        if (has(c.lch, "“\"") && has(c.rch, "”\"")) return say("ích")
        if (numberish(c.l1) && (numberish(c.r1) || match("""\s?\d""", c.right) != null)) return say("nhân")
        if (c.ltype == "digit" || c.rtype == "digit" || match("""\s?\d""", c.right) != null || numberish(c.l1) || numberish(c.r1)) return KEEP
        if (c.gluedL && c.gluedR && c.ltype in listOf("lower", "upper") && c.rtype in listOf("lower", "upper")) return SILENT
        if (c.l1.upper0() && c.r1.upper0()) {
            val names = words(c.left).takeLast(2) + words(c.right).take(2)
            val phrase = names.count { it.upper0() } >= 3 || c.l2.upper0() || c.r2.upper0()
            if (!phrase && !c.left.trimEnd().endsWith(CLOSE) && c.lch != ')') return say("và")
            return PAUSE
        }
        return KEEP
    }

    /** A lone "$": the name of the sign ("dấu $") is "đô la", otherwise (cursing "$h*t", "$$$") silent - `_dollar`. */
    private fun dollar(c: Spot): Said =
        if ((c.left3 hit setOf("tự", "hình", "hiệu", "dấu")) || search("""(?<![$W])(dollar|usd)(?![$W])""", c.right.take(50).lowercase()) != null) say("đô la") else SILENT

    /** "&": two capital letters ("S&M") are read as letters with "en"; two words ("Trans & edit") are "và"; masked inside a word ("F&CK") or next to a symbol is silent - `_amp`. */
    private fun amp(c: Spot): Said {
        if (c.gluedL && c.gluedR && c.ltype in listOf("upper", "lower") && c.rtype in listOf("upper", "lower")) {
            val leftWord = search("""\p{L}+$""", c.left)!!.value
            val rightWord = match("""\p{L}+""", c.right)!!.value
            if (leftWord.length <= 2 && rightWord.length <= 2 && leftWord.isUpperStr() && rightWord.isUpperStr()) return if (leftWord != rightWord) say("en") else say("và")
            if (leftWord.isUpperStr() && rightWord.isUpperStr()) return SILENT
            return say("và")
        }
        if (c.ltype in listOf("sym", "punct") || c.rtype in listOf("sym", "punct") || c.ltype == "edge" || c.rtype == "edge") return SILENT
        if (c.l1.firstOrNull()?.isLetterOrDigit() == true && c.r1.firstOrNull()?.isLetterOrDigit() == true) return say("và")
        return SILENT
    }

    private fun gender(c: Spot): Said {
        if ((c.gluedL && c.ltype in listOf("lower", "upper")) || (c.gluedR && c.rtype in listOf("lower", "upper", "digit"))) return SILENT
        if (c.l1.letter0() || search("""[:：]\s?$""", c.left) != null) return say(if (c.sym == "♀") "nữ" else "nam")
        return SILENT
    }

    private fun updown(c: Spot, word: String): Said {
        if (((c.left3 + c.right3) hit DIRECTION_WORDS) || c.lineStart) return SILENT
        val afterNumber = numberish(c.l1) || search("""(→|⇒|-+>)\s?\S*\s?$""", c.left.takeLast(14)) != null
        val beforeNumber = match("""\(?\d""", c.right) != null
        val inFrame = c.sym in listOf("↑", "↓") && c.l1.letter0() && has(c.right.trimStart().firstOrNull(), "}])】")
        val labelled = c.gluedL && c.lw1 in STAT_WORDS
        return if (afterNumber || beforeNumber || inFrame || labelled) say(word) else SILENT
    }

    // ---- steps that need no context -----------------------------------------------------------------------------------------------------------
    /** `said` between `before` and `after` (the words around), with spaces when glued to words; silent separates two glued words - `_gap`. */
    private fun gap(before: String, after: String, said: String = ""): String {
        val spaceBefore = before.isNotEmpty() && (before.last().isLetterOrDigit() || before.last() in "%)]”’")
        val spaceAfter = after.isNotEmpty() && (after.first().isLetterOrDigit() || after.first() in "$([“‘")
        if (said.isNotEmpty()) return (if (spaceBefore) " " else "") + said + (if (spaceAfter) " " else "")
        return if (before.isNotEmpty() && before.last().isLetterOrDigit() && after.isNotEmpty() && after.first().isLetterOrDigit()) " " else ""
    }

    private fun replace(token: String, pattern: Regex, keepTail: String = "", said: (MatchResult) -> String): String {
        val pieces = StringBuilder()
        var last = 0
        for (match in pattern.findAll(token)) {
            val text = match.value
            var end = match.range.last + 1
            if (keepTail.isNotEmpty()) end -= text.length - text.trimEnd { it in keepTail }.length
            pieces.append(token, last, match.range.first)
            val word = said(match)
            pieces.append(gap(pieces.toString(), token.substring(end), word))
            last = end
        }
        pieces.append(token, last, token.length)
        return pieces.toString()
    }

    private fun keys(match: MatchResult): String {
        val run = match.value
        if (run.length < 3 && run.toSet().size < 2) return run
        return run.map { KEYS.getValue(it) }.joinToString(" ")
    }

    /** First step of `readingMarks`: HTML entities, "P/s", URLs, masked cursing "!@#$%", Japanese smileys and runs of arrow keys - need no context - `prepare`. */
    fun prepare(out: MutableList<String>) {
        for ((index, original) in out.withIndex()) {
            if (original.none { it in "&@#$%^*!?/_ωヽ´゜∀◕◡‿≧≦╯╰╭∇ಠ益ﾉﾟдДᴗヮ꒳˶˘ʕʔᴥ◠٩۶ᕕᕗ꒪ↀ͜͡ʖ￣ェ⑉﹏↑↓←→↖↗↘↙" } || original in listOf("!", "?", "!!", "??")) continue
            var token = original
            for ((entity, char) in ENTITIES) token = token.replace(entity, char)
            token = replace(token, POSTSCRIPT) { "pê ét" }
            token = replace(token, URL, URL_TAIL) { "đường dẫn" }
            token = replace(token, GRAWLIX) { "" }
            token = replace(token, KEY_RUN) { keys(it) }
            token = replace(token, FACE_UNDERSCORE) { "" }
            if (token.trim { it in PUNCT_MARKS + OPEN + CLOSE } != "ω") token = replace(token, KAOMOJI_SPAN) { "" }
            out[index] = token
        }
    }

    private fun run(token: String, pos: Int, chars: String): Int {
        var end = pos
        while (end < token.length && token[end] in chars) end++
        return end
    }

    private fun wordChar(char: Char?) = char != null && (char.isLetterOrDigit() || char == '_')

    private class Ratio(val said: String?, val back: Int)

    /** ":" between two glued numbers: "tỉ lệ 7:3" two numbers in a row, "đấu 1:1" is "một chọi một", "3.17:1" (betting) is "ba phẩy mười bảy ăn một", clock times stay - `_ratio`. */
    private fun ratio(c: Spot): Ratio {
        val number = search("""\d+(?:[.,]\d+)?$""", c.left)!!.value
        val right = match("""\d+""", c.right)!!.value
        val words = c.left3 + c.right3
        if (('.' in number || ',' in number) && right == "1") return Ratio(decimal(number) + " ăn", number.length)
        if (words hit RATIO_WORDS) return Ratio("", 0)
        if (number == "1" && right == "1" && (words hit DUEL_WORDS)) return Ratio("chọi", 0)
        return Ratio(null, 0)
    }

    /** A run of stars ("★★★☆☆", "★5,0", "★MAX", "5★"): a rating scale is "<n> sao", the rest is decoration, silent - `_star`. */
    private fun star(token: String, pos: Int, c: (Int) -> Spot): Found {
        val end = run(token, pos, STAR_MARKS)
        val spot = c(end)
        val stars = token.substring(pos, end).filter { it in STARS }
        val full = stars.count { it in STAR_FULL }
        val after = if (stars.length == 1 && full > 0) match("""(\d+(?:[.,]\d+)?)|(?:MAX|Max|max)(?![$W])""", token.substring(end)) else null
        if (after != null && after.groupValues[1].isNotEmpty()) return Found(end + after.range.last + 1, say(decimal(after.groupValues[1]) + " sao"))
        if (after != null) return Found(end + after.range.last + 1, say("sao tối đa"))
        val standing = spot.rtype !in listOf("lower", "upper", "digit")
        if (standing && search("""[★☆][★☆\s]*(?:→|⇒|➜|➡|-+>|=+>)\s*$""", spot.left) != null && full > 0) return Found(end, say(DIGIT_WORDS[full] + " sao"))
        if (stars.length == 1 && full > 0 && standing && (search("""(?:^|[\s(\[])\d+(?:[.,]\d+)?$""", spot.left) != null || (spot.lw1 in NUMBER_WORDS && spot.ltype == "space"))) return Found(end, say("sao"))
        if (stars.length in 3..10 && standing && !(spot.gluedL && spot.ltype in listOf("lower", "upper"))) {
            val mixed = full > 0 && full < stars.length
            if (mixed || spot.lch == '[' || ':' in spot.left.takeLast(30) || "để lại" in spot.left.takeLast(14)) return Found(end, say(DIGIT_WORDS[if (mixed) full else stars.length] + " sao"))
        }
        return Found(end, SILENT)
    }

    /** The symbol starting at `token[pos]`: where it ends and what it says, or null when it is not a symbol to look at - `_dispatch`. */
    private fun dispatch(token: String, pos: Int, spot: (Int) -> Spot): Found? {
        val char = token[pos]
        val before: Char? = if (pos > 0) token[pos - 1] else null
        val afterChar: Char? = token.getOrNull(pos + 1)
        if (char in "/／") {
            val end = run(token, pos, "/／")
            val said = slash(spot(end))
            return Found(end, said, said.back)
        }
        if (char == '=') {
            val end = run(token, pos, "=")
            return Found(end, equals(spot(end)))
        }
        if (char in "#＃") {
            val end = run(token, pos, "#＃")
            if (before == 'S' && match("""\.\d""", token.substring(end)) != null) return Found(end + 1, say("cảnh"), 1)
            return Found(end, hash(spot(end)))
        }
        if (char in "@＠") {
            val end = run(token, pos, "@＠")
            return Found(end, at(spot(end)))
        }
        if (char == '^') {
            val end = run(token, pos, "^")
            return Found(end, caret(spot(end)))
        }
        if (char == '·') return Found(pos + 1, PAUSE)
        if (char in "<>") {
            val end = run(token, pos, char.toString())
            return Found(end, angleMark(spot(end)))
        }
        if (char in "+＋") {
            val end = run(token, pos, "+＋")
            return Found(end, plus(spot(end)))
        }
        if (char == '-' && afterChar?.isDigit() == true && !wordChar(before)) return Found(pos + 1, minus(spot(pos + 1)))
        if (char == '-' && before?.isUpperCase() == true && !(afterChar?.isLetterOrDigit() == true) && (pos < 2 || !(token[pos - 2].isLetterOrDigit() || token[pos - 2] == '-'))) return Found(pos + 1, gradeMinus(spot(pos + 1)))
        if (char in "–—―-" && token.length == 1) return Found(pos + 1, dashRange(spot(pos + 1)))
        if (char == ':' && before?.isDigit() == true && afterChar?.isDigit() == true) {
            val ratio = ratio(spot(pos + 1))
            return if (ratio.said != null) Found(pos + 1, say(ratio.said), ratio.back) else null
        }
        if (char in "xX" && token.length == 1) {
            val around = spot(pos + 1)
            return Found(pos + 1, if (numberish(around.l1) && numberish(around.r1)) say("nhân") else KEEP)
        }
        if (char in "xX×" && before?.isDigit() == true && afterChar?.isDigit() == true) return Found(pos + 1, say("nhân"))
        if (char in "xX×") {
            if (char == '×' && before?.isDigit() != true && afterChar?.isDigit() != true) {
                val end = run(token, pos, "×")
                return Found(end, timesSign(spot(end)))
            }
            if (afterChar?.isDigit() == true && !wordChar(before)) return Found(pos + 1, timesPre(spot(pos + 1), char))
            if (before?.isDigit() == true && afterChar?.isDigit() != true && !(afterChar?.isLetter() == true || afterChar == '_')) {
                val (said, back) = timesPost(spot(pos + 1), char)
                return Found(pos + 1, said, back)
            }
            return null
        }
        if (char == '$') {
            val end = run(token, pos, "$")
            val number = if (end == pos + 1) match("""\d+(?:[.,]\d+)*""", token.substring(end)) else null
            if (number != null) return Found(end + number.value.length, say(number.value + " đô la"))
            if (before?.isDigit() == true && end == pos + 1) return Found(end, say("đô la"))
            return Found(end, dollar(spot(end)))
        }
        if (char == '°') {
            if (search("""\d\s?$""", spot(pos + 1).left.takeLast(3)) != null) return null
            return Found(pos + 1, SILENT)
        }
        if (char in "&＆") {
            val end = run(token, pos, "&＆")
            val qa = if (end == pos + 1 && before != null && before in "Qq" && !(pos >= 2 && token[pos - 2].isLetter())) match("""[Aa](?![$W])""", token.substring(end)) else null
            if (qa != null) return Found(end + 1, say("hỏi đáp"), 1)
            return Found(end, amp(spot(end)))
        }
        if (char in "♀♂") return Found(pos + 1, gender(spot(pos + 1)))
        if (char == '≠') {
            val around = spot(pos + 1)
            return Found(pos + 1, if (around.l1.isNotEmpty() && around.r1.isNotEmpty() && around.ltype != "sym" && around.rtype != "sym") say("không phải là") else SILENT)
        }
        if (char in "☎☏") return Found(pos + 1, if (match("""\s?[\d(]""", spot(pos + 1).right) != null) say("điện thoại") else SILENT)
        if (char in "↑▲△") return updownRun(token, pos, spot, "tăng")
        if (char in "↓▼▽") return updownRun(token, pos, spot, "giảm")
        if (char in STARS) return star(token, pos, spot)
        return null
    }

    private fun updownRun(token: String, pos: Int, spot: (Int) -> Spot, word: String): Found {
        val end = pos + 1
        val said = updown(spot(end), word)
        if (!said.text.isNullOrEmpty()) {
            val number = match("""\(?(\d+(?:[.,]\d+)?)\)?""", token.substring(end))
            if (number != null) {
                val parens = token.substring(end, end + number.range.last + 1)
                return Found(end + number.range.last + 1, say(word + " " + parens.replace(number.groupValues[1], decimal(number.groupValues[1]))))
            }
        }
        return Found(end, said)
    }

    /**
     * Reads the symbols left in each word of [out] by the context of ±3 words (see the top). [toks] are the shown words matching [out] (same count), used as context - `read_symbols`.
     */
    fun readSymbols(toks: List<String>?, out: MutableList<String>) {
        val plain = if (toks != null && toks.size == out.size) toks else out.toList()
        val starts = IntArray(plain.size)
        val lineBuilder = StringBuilder()
        for ((i, word) in plain.withIndex()) {
            starts[i] = lineBuilder.length
            lineBuilder.append(word).append(' ')
        }
        val line = lineBuilder.toString()
        for (index in out.indices) {
            val token = out[index]
            if (token.none { it in SPECIAL }) continue
            val base = starts[index]
            val afterLine = line.substring(base + plain[index].length)
            val head = line.substring(0, base)
            var pieces = StringBuilder()
            var leadComma = false
            var pos = 0
            while (pos < token.length) {
                val at = pos
                val found = if (token[at] in SPECIAL) dispatch(token, at) { end -> Spot(head + token.substring(0, at), token.substring(at, end), token.substring(end) + afterLine) } else null
                if (found == null) {
                    pieces.append(token[pos])
                    pos++
                    continue
                }
                val end = found.end
                if (found.back > 0) pieces = StringBuilder(pieces.toString().dropLast(found.back))
                val said = found.said.text
                if (said == null) {
                    pieces.append(token, pos, end)
                    pos = end
                    continue
                }
                val beforeText = pieces.toString()
                val leftChar = (head + beforeText).trimEnd().lastOrNull()
                val afterText = token.substring(end)
                val rightChar = (afterText + afterLine).trimStart().firstOrNull()
                var piece = gap(beforeText, afterText, said)
                if (found.said.stop && said.isEmpty() && leftChar?.isLetterOrDigit() == true && (rightChar == null || rightChar.isLetterOrDigit() || rightChar in OPEN)) {
                    if (beforeText.isNotEmpty()) piece = "," + (if (afterText.firstOrNull()?.isLetterOrDigit() == true) " " else "")
                    else leadComma = true
                }
                pieces.append(piece)
                pos = end
            }
            out[index] = pieces.toString()
            if (leadComma && index > 0 && out[index - 1].lastOrNull()?.isLetterOrDigit() == true) out[index - 1] = out[index - 1] + ","
        }
    }
}
