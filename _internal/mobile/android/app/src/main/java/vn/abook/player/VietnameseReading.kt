package vn.abook.player

import java.text.Normalizer
import java.util.Locale

/**
 * Phép kiểm "cách đọc một cái tên" - bản Kotlin của `listener_overrides.pronunciation_problem` (qua
 * `analysis._valid_vietnamese_spoken_form` + `is_vietnamese_syllable`) và của `webui/spelling.py` (lời mời sửa chính tả). Người
 * nghe gõ cách đọc theo tai ("Hên-kơ"); chỉ nhận âm tiết viết đúng chính tả tiếng Việt, và khi sai ở phụ âm đầu thì chỉ ra chỗ
 * sửa. Điện thoại không có Studio để kiểm lại, nên phép kiểm phải y hệt máy tính (bộ ví dụ hợp đồng
 * tests/fixtures/book_edits/contract/wishes_pronunciation.json phát lại từng ca).
 */
object VietnameseReading {
    const val MULTI_WORD = "multi_word"
    const val NOT_VIETNAMESE = "not_vietnamese"

    // analysis.VIETNAMESE_SPOKEN_FORM_PATTERN: `À-ỹ` là dải điểm mã U+00C0..U+1EF9 (đã gồm Đ, đ).
    private val SPOKEN_FORM = Regex("[A-Za-zÀ-ỹ]+(?:[ -][A-Za-zÀ-ỹ]+)*")
    private val NON_VIETNAMESE_CODA = Regex("[fjlrsvwz]$", RegexOption.IGNORE_CASE)
    private val ONSETS = setOf(
        "", "b", "c", "ch", "d", "đ", "g", "gh", "gi", "h", "k", "kh", "l", "m", "n",
        "ng", "ngh", "nh", "p", "ph", "q", "qu", "r", "s", "t", "th", "tr", "v", "x",
    )
    private val NUCLEI = listOf(
        "uyê", "uya", "uyu", "oai", "oay", "oeo", "uôi", "ươi", "ươu", "iêu", "yêu", "uây",
        "iê", "yê", "uô", "ươ", "uơ", "uâ", "uê", "uy", "ua", "ưa", "ia", "ya", "oa", "oă", "oe", "oo",
        "ai", "ao", "au", "ay", "âu", "ây", "eo", "êu", "iu", "oi", "ôi", "ơi", "ui", "ưi", "ưu", "ôô",
        "a", "ă", "â", "e", "ê", "i", "o", "ô", "ơ", "u", "ư", "y",
    )
    private val CODAS = listOf("ngh", "ng", "nh", "ch", "c", "m", "n", "p", "t", "i", "o", "u", "y")
    private val FRONT_WRITTEN = setOf("i", "e", "ê", "y")
    private val FRONT_SIMPLE = setOf('i', 'ê')
    private const val GLIDE_LETTERS = "iouy"
    private val TONE_MARKS = setOf('̣', '̀', '́', '̃', '̉')

    // Ba nhóm: phụ âm đầu, nhân, phụ âm cuối - dài trước ngắn như bản Python.
    private val SYLLABLE = Regex(
        "(" + ONSETS.filter { it.isNotEmpty() }.sortedByDescending { it.length }.joinToString("|") + ")?" +
            "(" + NUCLEI.sortedByDescending { it.length }.joinToString("|") + ")" +
            "(" + CODAS.sortedByDescending { it.length }.joinToString("|") + ")?",
    )

    private fun words(text: String): List<String> = text.split(Regex("[\\p{Z}\\s\\u001c-\\u001f\\u0085]+")).filter { it.isNotEmpty() }

    /** `str.casefold()` cho chữ Latin: hạ -> hoa -> hạ (ß thành ss, như Python). */
    fun casefold(text: String): String = text.lowercase(Locale.ROOT).uppercase(Locale.ROOT).lowercase(Locale.ROOT)

    /** listener_overrides.surface_key: khoá một từ - bỏ khoảng trắng đầu cuối, hạ chữ, gộp khoảng trắng. */
    fun surfaceKey(surface: String): String = words(casefold(BookEdits.pyStrip(surface))).joinToString(" ")

    private fun withoutTone(word: String): String {
        val decomposed = Normalizer.normalize(casefold(word), Normalizer.Form.NFD)
        return Normalizer.normalize(decomposed.filter { it !in TONE_MARKS }, Normalizer.Form.NFC)
    }

    /** analysis.is_vietnamese_syllable: từ đã viết như một âm tiết tiếng Việt chưa. */
    fun isSyllable(word: String): Boolean {
        val bare = withoutTone(word)
        val match = SYLLABLE.matchEntire(bare) ?: return false
        val onset = match.groupValues[1]
        val nucleus = match.groupValues[2]
        val coda = match.groupValues[3]
        if ((nucleus == "ă" || nucleus == "â") && coda.isEmpty()) return false
        if (coda.isNotEmpty() && coda.length == 1 && coda[0] in GLIDE_LETTERS && nucleus.last() in GLIDE_LETTERS) return false
        if (onset.isNotEmpty() && nucleus.take(1) in FRONT_WRITTEN) {
            if (onset == "c" || onset == "ng") return false
        } else if (onset == "k" || onset == "ngh") {
            return false
        }
        for (ending in listOf("ng", "c")) {
            if (bare.endsWith(ending)) {
                val stem = bare.dropLast(ending.length)
                val before = if (stem.length >= 2) stem[stem.length - 2].toString() else ""
                if (stem.isNotEmpty() && stem.last() in FRONT_SIMPLE && before != "i" && before != "y") return false
            }
        }
        return true
    }

    /** analysis._name_candidate_key: hạ chữ và bỏ dấu. */
    private fun nameKey(value: String): String {
        val lowered = casefold(value.replace("’", "'")).replace("đ", "d")
        return Normalizer.normalize(lowered, Normalizer.Form.NFD).filter { Character.getType(it) != Character.NON_SPACING_MARK.toInt() }
    }

    internal fun validSpokenForm(surface: String, spokenForm: String): Boolean {
        val value = words(BookEdits.pyStrip(spokenForm)).joinToString(" ")
        if (value.isEmpty() || nameKey(value) == nameKey(surface)) return false
        if (!SPOKEN_FORM.matches(value)) return false
        val syllables = value.split(' ', '-')
        if (syllables.any { NON_VIETNAMESE_CODA.containsMatchIn(it) }) return false
        for (syllable in syllables) {
            val normalized = Normalizer.normalize(casefold(syllable).replace("đ", "d"), Normalizer.Form.NFD)
                .filter { Character.getType(it) != Character.NON_SPACING_MARK.toInt() }
            val firstVowel = normalized.indexOfFirst { it in "aeiouy" }
            if (firstVowel < 0) return false
            if (normalized.substring(0, firstVowel) !in ONSETS) return false
            if (!isSyllable(syllable)) return false
        }
        return true
    }

    /** listener_overrides.pronunciation_problem: mã lý do không nhận một cách đọc, hay null. */
    fun problem(surface: String, spokenForm: String): String? {
        if (words(surface).size != 1) return MULTI_WORD
        // Đọc đúng như viết: máy không được lười phiên âm, người nghe thì được chọn.
        if (surfaceKey(spokenForm) == surfaceKey(surface)) return null
        return if (validSpokenForm(surface, spokenForm)) null else NOT_VIETNAMESE
    }

    // ---- spelling.py: phụ âm đầu theo chính tả -------------------------------------------------------------------------

    private val TONES = setOf('̀', '́', '̉', '̃', '̣')
    private val BACK = "aăâoôơuư".toSet()

    private class Rule(val initial: String, val fixed: String, val before: Set<Char>)

    private val RULES = listOf(
        Rule("ngh", "ng", BACK), Rule("ng", "ngh", setOf('i', 'e', 'ê')), Rule("gh", "g", BACK), Rule("gi", "gi", emptySet()),
        Rule("g", "gh", setOf('e', 'ê')), Rule("kh", "kh", emptySet()), Rule("k", "c", BACK), Rule("ch", "ch", emptySet()),
        Rule("c", "k", setOf('i', 'e', 'ê', 'y')),
    )

    private fun base(letter: String): String =
        Normalizer.normalize(Normalizer.normalize(letter.lowercase(Locale.ROOT), Normalizer.Form.NFD).filter { it !in TONES }, Normalizer.Form.NFC)

    private fun respell(syllable: String): String {
        val lower = syllable.lowercase(Locale.ROOT)
        for (rule in RULES) {
            if (!lower.startsWith(rule.initial)) continue
            val rest = syllable.substring(rule.initial.length)
            if (rest.isEmpty() || base(rest.substring(0, 1)).singleOrNull().let { it == null || it !in rule.before }) return syllable
            val fixed = if (syllable.isNotEmpty() && Character.isUpperCase(syllable[0])) rule.fixed.replaceFirstChar { it.uppercaseChar() } else rule.fixed
            return fixed + rest
        }
        return syllable
    }

    private val SYLLABLE_TOKEN = Regex("[^\\s-]+")

    /** spelling.respelled: "Hên-kơ" -> "Hên-cơ", "Ngê-ra" -> "Nghê-ra"; không có gì để sửa thì trả nguyên chuỗi. */
    fun respelled(spokenForm: String): String {
        val text = Normalizer.normalize(spokenForm, Normalizer.Form.NFC)
        val fixed = SYLLABLE_TOKEN.replace(text) { respell(it.value) }
        return if (fixed != text) fixed else spokenForm
    }

    /** spelling.respelling_note: 'Tiếng Việt viết “cơ”, không viết “kơ”.' */
    fun respellingNote(spokenForm: String, fixed: String): String {
        val before = SYLLABLE_TOKEN.findAll(Normalizer.normalize(spokenForm, Normalizer.Form.NFC)).map { it.value }.toList()
        val after = SYLLABLE_TOKEN.findAll(fixed).map { it.value }.toList()
        val pairs = before.zip(after).filter { (old, new) -> old != new }
        if (pairs.isEmpty()) return ""
        val right = pairs.joinToString(", ") { "“${it.second}”" }
        val wrong = pairs.joinToString(", ") { "“${it.first}”" }
        return "Tiếng Việt viết $right, không viết $wrong."
    }
}
