package vn.abook.player.readaloud

import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import vn.abook.player.VietnameseReading

/**
 * Tiếng kêu trong "Nghe ngay": thán từ Latin ("Umm", "Oh") và thán từ kéo dài ("Aaaa", "Hmmm", "rồiiii") đọc thành âm tiếng Việt - bản Kotlin y hệt
 * `abook/readaloud/shouts.py` (cùng đọc tests/fixtures/vieneu/android/text.json: các khúc `units`). Biến đổi để đọc, chữ hiện không đổi.
 *
 * Quy ước: thán từ gốc MỘT lần bằng âm tiết Việt, rồi "…", rồi - chỉ khi chữ bị kéo là nguyên âm đứng riêng được thành một âm tiết (a, e, ê, i, o, ô, ơ, u, ư) -
 * nguyên âm ấy một lần, mang thanh của âm tiết gốc ("rồi… ì", "tớ… ớ"). Chữ kéo là phụ âm hay "y" thì chỉ "<gốc>…". Toàn hoa cùng luật; "ー" sau nguyên âm là kéo.
 * Nhận ra bằng một chữ lặp từ ba lần liền; chỉ đọc khi tách được gốc (thán từ trong bảng, âm tiết Việt, tiếng kêu kiểu Nhật đọc được bằng luật romaji).
 */
object Shouts {
    private val INTERJECTIONS = mapOf("umm" to "ừm", "ugh" to "ức", "boom" to "bùm", "oh" to "ô", "hmm" to "hừm", "shh" to "suỵt", "ah" to "a", "eh" to "ê",
        "hm" to "hừm", "huh" to "hả", "ooh" to "ô", "hic" to "hích", "urgh" to "ức")
    /** Tiếng cười lặp ("Haha" -> "ha ha", "Hehe" -> "hê hê", "fufu" -> "phu phu"). */
    private val LAUGH_SYLLABLES = mapOf("ha" to "ha", "he" to "hê", "hi" to "hi", "ho" to "hô", "fu" to "phu")
    private val LAUGH = Regex("(?:ha|he|hi|ho|fu){2,}", RegexOption.IGNORE_CASE)
    private const val TONE_MARKS = "̣̀́̃̉"
    private val STANDALONE = "aeêioôơuư".toSet()
    private val VOWELS = "aăâeêioôơuưy".toSet()
    private const val MIN_RUN = 3
    private val ROMAN_LETTERS = "ivx".toSet()
    private val RANK_NOUNS = setOf("hạng", "cấp", "rank", "class", "loại", "bậc")
    private val GLUE = Regex("(?:\\.{2,}|[…~—–])+")
    private const val CLOSING = "\"'“”‘’()[]«»"
    private val JAPANESE_CRY = Regex("(?:^|[bcdfghjklmnpqrstvxz])y|w")
    private val RUN = Regex("(.)\\1+")

    private fun dedupe(text: String) = RUN.replace(text) { it.groupValues[1] }

    private val DEDUPED = INTERJECTIONS.mapKeys { dedupe(it.key) }

    private fun plain(char: Char): String =
        Normalizer.normalize(Normalizer.normalize(char.toString(), Normalizer.Form.NFD).filter { it !in TONE_MARKS }, Normalizer.Form.NFC)

    private fun tone(word: String): String = Normalizer.normalize(word, Normalizer.Form.NFD).firstOrNull { it in TONE_MARKS }?.toString() ?: ""

    private fun latin(char: Char) = char.isLetter() && (char.code < 0x250 || char.code in 0x1E00..0x1EFF)

    /** Các chữ của `core` (NFC, chữ thường) với "ー" thay bằng chữ nguyên âm đứng trước nhắc lại hai lần; null khi có chữ ngoài Latin. */
    private fun letters(core: String): List<Char>? {
        val chars = ArrayList<Char>()
        for (char in Normalizer.normalize(core, Normalizer.Form.NFC).lowercase(Locale.ROOT)) {
            if (char == 'ー') {
                if (chars.isEmpty() || plain(chars.last()).singleOrNull() !in VOWELS) return null
                chars.add(chars.last())
                chars.add(chars.last())
            } else if (latin(char)) {
                chars.add(char)
            } else {
                return null
            }
        }
        return chars
    }

    private fun runs(chars: List<Char>): List<Pair<Int, Int>> {
        val bases = chars.map { plain(it) }
        val out = ArrayList<Pair<Int, Int>>()
        var start = 0
        for (index in 1..bases.size) {
            if (index == bases.size || bases[index] != bases[start]) {
                if (index - start >= MIN_RUN) out.add(start to index)
                start = index
            }
        }
        return out
    }

    private fun upper(text: String) = text.any { it.isUpperCase() } && text.none { it.isLowerCase() }

    /**
     * Chữ có NHIỀU chỗ kéo ("Cccchhhhàaaaaaoooo" -> "chào… ò"): gộp mỗi chỗ kéo thành một chữ (giữ dấu thanh ở chữ đầu của chỗ ấy); chỉ đọc khi gộp ra đúng một âm tiết tiếng Việt.
     * Chỗ kéo cuối là nguyên âm đứng riêng thì nhắc lại nó một lần sau "…", mang thanh của âm tiết - `_collapsed`.
     */
    private fun collapsed(chars: List<Char>, runs: List<Pair<Int, Int>>): String? {
        if (runs.size < 2) return null
        val keep = BooleanArray(chars.size) { true }
        for ((start, end) in runs) for (index in start + 1 until end) keep[index] = false
        val base = chars.indices.filter { keep[it] }.joinToString("") { chars[it].toString() }
        if (!VietnameseReading.isSyllable(base)) return null
        val letter = plain(chars[runs.last().first])
        val append = if (runs.last().second == chars.size && letter.singleOrNull() in STANDALONE)
            Normalizer.normalize(Normalizer.normalize(letter, Normalizer.Form.NFD) + tone(base), Normalizer.Form.NFC) else ""
        return "$base…" + if (append.isNotEmpty()) " $append" else ""
    }

    private val readings = ConcurrentHashMap<String, String>()

    /** Cách đọc của `core` (chữ cái đầu tới cuối, không dấu câu) khi nó là thán từ Latin hay tiếng kêu kéo dài; null khi để nguyên. */
    fun stretchReading(core: String): String? {
        val hit = readings[core]
        if (hit != null) return hit.ifEmpty { null }
        val found = compute(core)
        if (readings.size > 4096) readings.clear()
        readings[core] = found ?: ""
        return found
    }

    private fun compute(core: String): String? {
        val chars = letters(core)
        if (chars == null || chars.isEmpty() || (upper(core) && chars.all { it in ROMAN_LETTERS } && chars.size >= MIN_RUN)) return null
        val word = chars.joinToString("")
        INTERJECTIONS[word]?.let { return it }
        if (LAUGH.matches(word) && (0 until word.length step 2).all { word.substring(it, it + 2) == word.substring(0, 2) }) {
            return (0 until word.length step 2).joinToString(" ") { LAUGH_SYLLABLES.getValue(word.substring(it, it + 2)) }
        }
        val runs = runs(chars)
        if (runs.size != 1) return collapsed(chars, runs)
        val (start, end) = runs[0]
        val letter = plain(chars[start])
        val one = (chars.subList(0, start) + chars[start] + chars.subList(end, chars.size)).joinToString("")
        var base = DEDUPED[dedupe(one)]
        var append = if (base == "a" || base == "ô" || base == "ê") base else ""
        if (base == null) {
            val asciiWord = one.all { it.code < 128 }
            val japanese = if (asciiWord) Romanization.reading(one, "ja") else null
            val consonant = (chars.subList(0, start) + chars.subList(end, chars.size)).joinToString("")
            base = when {
                asciiWord && JAPANESE_CRY.containsMatchIn(one) && japanese != null -> japanese
                VietnameseReading.isSyllable(one) -> one
                letter.singleOrNull() !in VOWELS && consonant.isNotEmpty() && VietnameseReading.isSyllable(consonant) -> consonant
                japanese != null -> japanese
                else -> return null
            }
            if (letter.singleOrNull() in STANDALONE) append = Normalizer.normalize(Normalizer.normalize(letter, Normalizer.Form.NFD) + tone(base), Normalizer.Form.NFC)
        }
        return "$base…" + if (append.isNotEmpty() && letter.singleOrNull() in STANDALONE) " $append" else ""
    }

    /**
     * Thay tại chỗ, trong [out], token (chưa bị đổi so với [toks]) là thán từ / tiếng kêu kéo dài bằng cách đọc của nó, giữ dấu câu quanh (dấu "-" đuôi của "Xoạttt-" bỏ);
     * số chữ không đổi. Chữ dính liền vào phần sau qua "…", "..", "~" hay "—" ("Ummm…Ý", "màaaa—nếu") thì chỉ xét phần trước. Chữ hoa cả là hạng ("hạng AAA", "AAA+++")
     * thì để viết tắt đọc.
     */
    fun readShouts(toks: List<String>, out: MutableList<String>) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val glued = GLUE.find(token, Names.splitToken(token).first.length)
            val head = if (glued != null) token.substring(0, glued.range.first) else token
            var rest = if (glued != null) token.substring(glued.range.first) else ""
            val (before, core, after) = Names.splitToken(head)
            if (core.isEmpty() || (upper(core) && (after.startsWith("+") || (index > 0 && toks[index - 1].lowercase(Locale.ROOT).trim { it in CLOSING } in RANK_NOUNS)))) continue
            var reading = stretchReading(core) ?: continue
            if (reading.endsWith("…")) rest = rest.trimStart('~')
            if (reading.endsWith("…") && (rest.startsWith("…") || rest.startsWith("."))) reading = reading.dropLast(1)
            out[index] = before + reading + Names.closing(if ("…" in reading) after.replace("-", "") else after, reading) + rest
        }
    }
}
