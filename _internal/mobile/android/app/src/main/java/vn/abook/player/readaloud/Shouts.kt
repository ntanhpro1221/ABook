package vn.abook.player.readaloud

import java.text.Normalizer
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import vn.abook.player.VietnameseReading
import vn.abook.player.VietnameseSyllable
import vn.abook.player.BuildConfig
import org.json.JSONObject

/**
 * Tiếng kêu trong "Nghe ngay": thán từ Latin ("Umm", "Oh") và thán từ kéo dài ("Aaaa", "Hmmm", "rồiiii") đọc thành âm tiếng Việt - bản Kotlin y hệt
 * `abook/readaloud/shouts.py` (cùng đọc tests/fixtures/vieneu/android/text.json: các khúc `units`). Biến đổi để đọc, chữ hiện không đổi.
 *
 * Quy ước: thán từ gốc MỘT lần bằng âm tiết Việt, rồi "…", rồi - chỉ khi chữ bị kéo là nguyên âm đứng riêng được thành một âm tiết (a, e, ê, i, o, ô, ơ, u, ư) -
 * nguyên âm ấy một lần, mang thanh của âm tiết gốc ("rồi… ì", "tớ… ớ"). Chữ kéo là phụ âm hay "y" thì chỉ "<gốc>…". Toàn hoa cùng luật; "ー" sau nguyên âm là kéo.
 * Nhận ra bằng một chữ lặp từ ba lần liền; chỉ đọc khi tách được gốc (thán từ trong bảng, âm tiết Việt, tiếng kêu kiểu Nhật đọc được bằng luật romaji).
 */
object Shouts {
    val POLICY = JSONObject(BuildConfig.SOUND_POLICY)
    private val NOTE = Regex(POLICY.getString("note_pattern"), RegexOption.IGNORE_CASE)

    /** A generated syllable that spells an English word ("he", "hi", "I") is said in English by sea-g2p: respell it as the same Vietnamese sound - `distinct_from_english`. */
    fun distinctFromEnglish(reading: String): String =
        POLICY.getJSONObject("english_collisions").optString(reading.lowercase(Locale.ROOT), reading)

    /** Presentation is removed from voice text only; owners retain displayed word positions. */
    fun presentationTokens(toks: List<String>): Pair<List<String>, List<Int>> {
        val prepared = ArrayList<String>()
        val owners = ArrayList<Int>()
        for ((index, token) in toks.withIndex()) {
            val parts = NOTE.replace(token, " ").split(Regex("\\s+")).filter { it.isNotEmpty() }.ifEmpty { listOf("") }
            for (raw in parts) {
                val (before, core, after) = Names.splitToken(raw)
                val part = if (core.isNotEmpty() && (before + after).none { it.isLetterOrDigit() }) before.replace("_", "") + core + after.replace("_", "") else raw
                prepared.add(part)
                owners.add(index)
            }
        }
        return prepared to owners
    }

    fun honorificStretch(core: String, origin: String?): String? {
        val parts = core.split(Regex("[-‐‑‒–]"))
        if (parts.size < 2) return null
        val suffix = dedupe(parts.last().lowercase(Locale.ROOT))
        if (suffix !in Names.HONORIFICS || suffix == parts.last().lowercase(Locale.ROOT)) return null
        val canonical = (parts.dropLast(1) + suffix).joinToString("-")
        return (JapanesePolicy.reading(canonical, origin) ?: Names.honorificReading(canonical, origin))?.plus("…")
    }

    private fun expandedReading(core: String): String? {
        val word = core.lowercase(Locale.ROOT)
        if (word.isEmpty() || word.any { it !in 'a'..'z' }) return null
        if (upper(core) && (word.all { it in ROMAN_LETTERS } || word in SHORT_CASED || (word.toSet().size == 1 && word[0] !in VOWELS))) return null
        val vowels = POLICY.getString("vowels")
        val atoms = if (Regex(POLICY.getString("laugh_pattern")).matches(word)) Regex(POLICY.getString("laugh_atom")).findAll(word).map { it.value }.toList() else emptyList()
        // "FIFA", "Fifi", "Ahifa", "HIFI": a laugh in "f" is "fu" / "fw" ("Fufu", "Fuhaha", "Fwahaha"); a bare "fa", "fi", "fo" needs three beats ("Fahaha", "Fofofo")
        if (atoms.isNotEmpty() && (atoms.size >= 3 || atoms.all { it[0] == 'h' || it[1] in "uw" })) {
            val sounds = atoms.take(POLICY.getInt("max_laugh_syllables")).map { atom ->
                val vowel = atom.first { ch -> ch in vowels }
                if (atom[0] == 'f') "phu" else POLICY.getJSONObject("laugh_vowels").getString(vowel.toString())
            }.toList()
            // The opening vowel tells "Ehehe" from "Hehe"; it does not count toward the ceiling.
            val lead = POLICY.getJSONObject("laugh_leads").optString(word.take(1), "")
            return (if (lead.isNotEmpty()) listOf(lead) + sounds else sounds).joinToString(" ")
        }
        if (Regex(POLICY.getString("nasal_pattern")).matches(word)) return Romanization.reading(dedupe(word), "ja")
        val run = Regex("(.)\\1{" + (POLICY.getInt("min_run") - 1) + ",}")
        val stretched = run.containsMatchIn(word)
        val base = run.replace(word) { it.groupValues[1] }
        // "AK", "KO", "IG", "EK": two capitals are an abbreviation unless listed ("AH", "OH"); "EEG", "UGG": a doubled letter closed by "g" is one too ("EEK", "AHH", "EGGG" are cries)
        val soundCase = !(core.any(Char::isUpperCase) && core.none(Char::isLowerCase)) || (Regex("(.)\\1").containsMatchIn(word) && (stretched || !word.endsWith("g")))
        val patterned = soundCase && word !in EnglishWords.ALL && !VietnameseReading.isSyllable(word) && word.all { it in vowels + "hkgwy" }
        val reading = when {
            stretched && Regex(POLICY.getString("growl_pattern")).matches(base) -> base.dropLast(1)
            stretched && Regex(POLICY.getString("hiss_pattern")).matches(base) -> base.replace(Regex("[zs]+$"), "") + "… xì"
            patterned && (Regex(POLICY.getString("breath_pattern")).matches(word) || Regex(POLICY.getString("palatal_pattern")).matches(word)) -> {
                val plain = base.replace(Regex("[hkg]+$"), "")
                if (plain.isEmpty()) null else Romanization.reading(plain, "ja")
            }
            stretched -> {
                val title = core.first().isUpperCase() && core.drop(1).all { it.isLowerCase() }
                val runs = runs(word.toList())
                if (title && runs.size == 1 && runs[0].second == word.length && word.last() !in vowels) return null
                if (VietnameseReading.isSyllable(base)) base else Romanization.reading(base, "ja") ?: base.takeIf { it in EnglishWords.ALL }
            }
            else -> null
        }?.let(::distinctFromEnglish) ?: return null
        return if ("…" in reading || !stretched) reading else "$reading…"
    }
    private val INTERJECTIONS = mapOf("umm" to "ừm", "ugh" to "ức", "boom" to "bùm", "oh" to "ô", "hmm" to "hừm", "shh" to "suỵt", "ah" to "a", "eh" to "ê",
        "hm" to "hừm", "huh" to "hả", "ooh" to "ô", "hic" to "hích", "urgh" to "ức",
        // "Um", "Uh", "Mm" (sea-g2p reads "mm" as "mi li mét"); repeated consonants: "grrr", "pfffft", "kkkk", "hhhh", "ssss" ("mmm" is "mm" above)
        "um" to "ừm", "uhm" to "ừm", "uh" to "ờ", "mm" to "ừm", "grr" to "gừ", "pff" to "phụt", "pfft" to "phụt", "kkk" to "khà khà", "hhh" to "ha ha", "sss" to "xì",
        "hmph" to "hừm", "hmpf" to "hừm", "tsk" to "chậc", "tch" to "chậc")
    /** Short words that are abbreviations or a rank when written all in capitals ("UH-60", "MM", "SSS"), not a cry. */
    private val SHORT_CASED = setOf("um", "uhm", "uh", "mm")
    /** A last letter written TWICE is a stretch too ("Ahh", "Haizz", "Hừmm") - three times any letter, twice only these (Boss, Class, Jess are real words). */
    private const val PAIR_LETTERS = "hzm"
    /** Besides the number words: "vài mm". */
    private val COUNT_WORDS = setOf("nghìn", "ngàn", "triệu", "tỷ", "tỉ", "trăm", "vạn", "chục", "mươi", "mười", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín", "vài", "mấy")
    /** Tiếng cười lặp ("Haha" -> "ha ha", "Hehe" -> "hê hê", "fufu" -> "phu phu"). */
    private val LAUGH_SYLLABLES = mapOf("ha" to "ha", "he" to "hê", "hi" to POLICY.getJSONObject("laugh_vowels").getString("i"), "ho" to "hô", "fu" to "phu")
    private val LAUGH = Regex("(?:ha|he|hi|ho|fu){2,}", RegexOption.IGNORE_CASE)
    private const val TONE_MARKS = "̣̀́̃̉"
    private val STANDALONE = "aeêioôơuư".toSet()
    private val VOWELS = "aăâeêioôơuưy".toSet()
    private val MIN_RUN = POLICY.getInt("min_run")
    private val ROMAN_LETTERS = "ivx".toSet()
    private val RANK_NOUNS = setOf("hạng", "cấp", "rank", "class", "loại", "bậc")
    private val CRY_MARK = Regex("[!?！？…~～—–―─]|\\.\\.") // the mark of a cry right after the letters
    private val CONSONANT_CRIES = setOf("mph", "tsk") // cries with no vowel outside the interjection table, also in capitals ("MMMMPH!", "TSSSK!")
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
        if (VietnameseSyllable.validSyllable(chars.joinToString(""))) return emptyList()
        val bases = chars.map { vowelFamily(it) }
        val marked = chars.any { it.code >= 128 && plain(it).singleOrNull() in VOWELS }
        val longRun = RUN.findAll(bases.joinToString("")).any { it.value.length >= MIN_RUN }
        val out = ArrayList<Pair<Int, Int>>()
        var start = 0
        for (index in 1..bases.size) {
            if (index == bases.size || bases[index] != bases[start]) {
                val same = chars.subList(start, index).map(::plain).toSet().size == 1
                val minimum = if (bases[start] in listOf("a", "e", "i", "o", "u", "y", "ư") &&
                    (marked || longRun) && (same || index - start >= MIN_RUN)) 2 else MIN_RUN
                if (index - start >= minimum) out.add(start to index)
                start = index
            }
        }
        return out
    }

    /** A stretched vowel keeps its quality and tone, including a marked trailing letter. */
    private fun vowelFamily(char: Char): String = if (plain(char) == "ư") "ư" else
        Normalizer.normalize(char.toString(), Normalizer.Form.NFD)
            .firstOrNull { Character.getType(it) != Character.NON_SPACING_MARK.toInt() }?.toString() ?: char.toString()

    private fun runChar(chars: List<Char>): String {
        val letter = chars.firstOrNull { plain(it) != vowelFamily(it) }?.let { plain(it) } ?: plain(chars.first())
        return Normalizer.normalize(Normalizer.normalize(letter, Normalizer.Form.NFD) + tone(chars.joinToString("")), Normalizer.Form.NFC)
    }

    private fun upper(text: String) = text.any { it.isUpperCase() } && text.none { it.isLowerCase() }

    /**
     * Chữ có NHIỀU chỗ kéo ("Cccchhhhàaaaaaoooo" -> "chào… ò"): gộp mỗi chỗ kéo thành một chữ (giữ dấu thanh ở chữ đầu của chỗ ấy); chỉ đọc khi gộp ra đúng một âm tiết tiếng Việt.
     * Chỗ kéo cuối là nguyên âm đứng riêng thì nhắc lại nó một lần sau "…", mang thanh của âm tiết - `_collapsed`.
     */
    private fun collapsed(chars: List<Char>, runs: List<Pair<Int, Int>>): String? {
        if (runs.size < 2) return null
        val pieces = ArrayList<String>()
        var cursor = 0
        for ((start, end) in runs) {
            pieces.add(chars.subList(cursor, start).joinToString(""))
            pieces.add(runChar(chars.subList(start, end)))
            cursor = end
        }
        pieces.add(chars.subList(cursor, chars.size).joinToString(""))
        val base = pieces.joinToString("")
        if (!VietnameseReading.isSyllable(base)) return null
        val letter = plain(runChar(chars.subList(runs.last().first, runs.last().second)).single())
        val append = if (runs.last().second == chars.size && letter.singleOrNull() in STANDALONE)
            Normalizer.normalize(Normalizer.normalize(letter, Normalizer.Form.NFD) + tone(base), Normalizer.Form.NFC) else ""
        return "$base…" + if (append.isNotEmpty()) " ${Names.loneSyllable(append)}" else ""
    }

    private val readings = ConcurrentHashMap<String, String>()

    /** Cách đọc của `core` (chữ cái đầu tới cuối, không dấu câu) khi nó là thán từ Latin hay tiếng kêu kéo dài; null khi để nguyên. */
    fun stretchReading(core: String): String? {
        val hit = readings[core]
        if (hit != null) return hit.ifEmpty { null }
        val lower = core.lowercase(Locale.ROOT)
        // "CCCD", "CMND": a listed abbreviation is never a cry. With no vowel, capitals are a cry only when listed ("HMMM", "GRRR", "MMMMPH"; not "SSSR", "PCCC"),
        // and small letters are one unless they spell a listed abbreviation ("cccd"; "Mmmph", "Ssst", "drrr" stay sounds)
        val found = if (upper(core) && lower in Abbreviations.LISTED) null
            else (compute(core) ?: expandedReading(core))?.takeIf {
                lower.any { c -> plain(c).singleOrNull() in VOWELS } || dedupe(lower) in DEDUPED ||
                    (if (upper(core)) dedupe(lower) in CONSONANT_CRIES else lower !in Abbreviations.LISTED)
            }
        if (readings.size > 4096) readings.clear()
        readings[core] = found ?: ""
        return found
    }

    private fun compute(core: String): String? {
        val chars = letters(core)
        if (chars == null || chars.isEmpty() || (upper(core) && chars.all { it in ROMAN_LETTERS } && chars.size >= MIN_RUN)) return null
        val word = chars.joinToString("")
        // "UH-60", "MMM", "SSS": abbreviations, not cries
        if (upper(core) && (word in SHORT_CASED || (chars.toSet().size == 1 && plain(chars[0]).singleOrNull() !in VOWELS))) return null
        // "um" is usually a Vietnamese word ("xanh um tùm"); capital "Um" is the cry
        if (Regex("(?:e|ừ)m{2,}", RegexOption.IGNORE_CASE).matches(core)) return "ừm"
        if (!(word == "um" && core.none { it.isUpperCase() })) INTERJECTIONS[word]?.let { return it }
        if (LAUGH.matches(word) && (0 until word.length step 2).all { word.substring(it, it + 2) == word.substring(0, 2) }) {
            return (0 until minOf(word.length, 2 * POLICY.getInt("max_laugh_syllables")) step 2).joinToString(" ") { LAUGH_SYLLABLES.getValue(word.substring(it, it + 2)) }
        }
        var runs = runs(chars)
        val pair = runs.isEmpty() && chars.size >= 3 && chars[chars.size - 1] == chars[chars.size - 2] && chars.last() in PAIR_LETTERS &&
            (chars.last() != 'z' || chars.size >= 4 && chars.subList(chars.size - 4, chars.size - 2).map { plain(it) } == listOf("a", "i")) // "Ahh", "Haizz", "Hừmm": the last letter twice
        if (pair) runs = listOf(chars.size - 2 to chars.size)
        if (runs.size != 1) return collapsed(chars, runs)
        val (start, end) = runs[0]
        var stretched = runChar(chars.subList(start, end))
        var letter = plain(stretched.single())
        if (start == 0 && end == chars.size && letter in listOf("ă", "â", "y")) {
            letter = mapOf("ă" to "a", "â" to "ơ", "y" to "i").getValue(letter)
            stretched = Normalizer.normalize(Normalizer.normalize(letter, Normalizer.Form.NFD) + tone(stretched), Normalizer.Form.NFC)
        }
        val one = chars.subList(0, start).joinToString("") + stretched + chars.subList(end, chars.size).joinToString("")
        if (one.length > 1 && one.all { plain(it).singleOrNull() in STANDALONE } && !VietnameseSyllable.validSyllable(one)) {
            return one.map { Names.loneSyllable(it.toString()) }.joinToString("… ")
        }
        var base = DEDUPED[dedupe(one)]
        var append = if (base == "a" || base == "ô" || base == "ê") base else ""
        if (base == null) {
            val asciiWord = one.all { it.code < 128 }
            if (pair && chars.last() == 'm' && asciiWord) return null // "Tamm", "Grimm", "Flamm" are names; only table cries or "Hừmm", "Ưmm" (with a mark) are stretches
            var japanese = if (asciiWord) Romanization.reading(one, "ja") else null
            val consonant = (chars.subList(0, start) + chars.subList(end, chars.size)).joinToString("")
            if (japanese == null && asciiWord && letter == "h" && JAPANESE_CRY.containsMatchIn(consonant)) japanese = Romanization.reading(consonant, "ja") // "Wahhh", "Uwahhh": the stretched letter is a breath "h"
            base = when {
                asciiWord && JAPANESE_CRY.containsMatchIn(one) && japanese != null -> japanese
                VietnameseReading.isSyllable(one) -> one
                letter.singleOrNull() !in VOWELS && consonant.isNotEmpty() && VietnameseReading.isSyllable(consonant) -> consonant
                japanese != null -> japanese
                else -> {
                    val trimmed = word.trimEnd('h') // "Haaah" -> "Haaa": the last "h" is a breath
                    return if (letter.singleOrNull() in VOWELS && trimmed != word && trimmed.length >= MIN_RUN) stretchReading(trimmed) else null
                }
            }
            if (letter.singleOrNull() in STANDALONE) append = Normalizer.normalize(Normalizer.normalize(letter, Normalizer.Form.NFD) + tone(base), Normalizer.Form.NFC)
        }
        return "$base…" + if (append.isNotEmpty() && letter.singleOrNull() in STANDALONE) " ${Names.loneSyllable(append)}" else ""
    }

    /** The word before is a quantity ("127", "một", "vài"): a "mm" after it is the unit. */
    private fun counted(word: String): Boolean {
        val trimmed = word.trim { it in CLOSING }.lowercase(Locale.ROOT)
        return trimmed.lastOrNull()?.isDigit() == true || trimmed in COUNT_WORDS
    }

    /** Reads [segment] (a token, or the part of a token after a glued mark) as [readShouts] does; not a cry -> returned as is. A cry first -> the part after the glue is looked at too ("Um....Umm…"). */
    private fun readSegment(segment: String, toks: List<String>, index: Int, first: Boolean, origin: String?): String {
        val face = segment.trim { it in POLICY.getString("frames") }
        val emoticons = POLICY.getJSONObject("emoticons")
        if (emoticons.has(face.lowercase(Locale.ROOT))) {
            val at = segment.indexOf(face)
            return segment.take(at) + emoticons.getString(face.lowercase(Locale.ROOT)) + segment.drop(at + face.length)
        }
        val glued = GLUE.find(segment, Names.splitToken(segment).first.length)
        val head = if (glued != null) segment.substring(0, glued.range.first) else segment
        var rest = if (glued != null) segment.substring(glued.range.first) else ""
        val (before, core, after) = Names.splitToken(head)
        val previous = if (first && index > 0) toks[index - 1] else ""
        if (core.isEmpty() || (before + after).any { it.isDigit() } ||
            (upper(core) && (after.startsWith("+") || previous.lowercase(Locale.ROOT).trim { it in CLOSING } in RANK_NOUNS))) return segment // a word glued to a number ("55mm", "ss1") is no cry
        // "Kỳ tích: AAA", "Kamen Rider OOO", "tài khoản YYY": three equal capitals are a rank / name / blank; only a cry mark ("AAA!") makes them a cry
        if (upper(core) && core.all { it.code < 128 } && core.length == MIN_RUN && core.toSet().size == 1 && !CRY_MARK.containsMatchIn(after + rest)) return segment
        var reading = honorificStretch(core, origin) ?: stretchReading(core) ?: return segment
        if (core.lowercase(Locale.ROOT) == "mm" && counted(previous)) return segment // "127 mm", "vài mm" is a unit, "Mm…" is a cry
        if (rest.isNotEmpty()) {
            val joint = GLUE.find(rest)!!.range.last + 1
            rest = rest.substring(0, joint) + readSegment(rest.substring(joint), toks, index, false, origin)
        }
        if (reading.endsWith("…")) rest = rest.trimStart('~')
        if (reading.endsWith("…") && (rest.startsWith("…") || rest.startsWith("."))) reading = reading.dropLast(1)
        return before + reading + Names.closing(if ("…" in reading) after.replace("-", "") else after, reading) + rest
    }

    /**
     * Thay tại chỗ, trong [out], token (chưa bị đổi so với [toks]) là thán từ / tiếng kêu kéo dài bằng cách đọc của nó, giữ dấu câu quanh (dấu "-" đuôi của "Xoạttt-" bỏ);
     * số chữ không đổi. Chữ dính liền vào phần sau qua "…", "..", "~" hay "—" ("Ummm…Ý", "màaaa—nếu", "Um....Umm") thì mỗi phần được xét riêng. Chữ hoa cả là hạng ("hạng AAA", "AAA+++")
     * thì để viết tắt đọc.
     */
    fun readShouts(toks: List<String>, out: MutableList<String>, origin: String? = null) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] == token) out[index] = readSegment(token, toks, index, true, origin)
        }
    }
}
