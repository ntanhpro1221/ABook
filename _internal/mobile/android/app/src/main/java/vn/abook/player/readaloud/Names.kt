package vn.abook.player.readaloud

import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import vn.abook.player.VietnameseReading

/**
 * Tên Nhật / Hàn trong "Nghe ngay": đọc bằng luật phiên âm ([Romanization]) thay vì âm tiếng Anh của sea-g2p - bản Kotlin y hệt `abook/readaloud/names.py`
 * (cùng đọc tests/fixtures/vieneu/android/text.json: các khúc `units` có `origin`, và `origins`). Từ tiếng Anh thật ([EnglishWords]) và âm tiết tiếng Việt viết sẵn
 * ("Hoa", "Nam") để nguyên; viết tắt, tiếng reo ("Aaaa") và chữ luật không chắc cũng vậy. Gốc của cuốn tự đoán từ chính tên trong cuốn ([bookOrigin]).
 */
object Names {
    val ORIGINS = setOf("ja", "ko")
    const val SAMPLE_CHAPTERS = 40
    const val MIN_NAMES = 10
    const val MIN_OCCURRENCES = 60
    const val JA_SHARE = 0.70
    const val HON_MIN = 20
    const val HON_NAMES = 3
    const val HON_JA_SHARE = 0.3
    const val KO_SHARE = 0.70
    const val KO_ONLY_SHARE = 0.5
    /** Đổi khi đổi cách đoán: gốc đã lưu của cuốn được đoán lại. */
    const val RULE_VERSION = 3
    private const val ALLOWED_MARKS = "āīūēōâîûêôĀĪŪĒŌÂÎÛÊÔ"

    /** (dấu câu đầu, lõi từ chữ cái đầu tới chữ cái cuối, dấu câu cuối). */
    fun splitToken(token: String): Triple<String, String, String> {
        var start = 0
        var end = token.length
        while (start < end) {
            val cp = token.codePointAt(start)
            if (Character.isLetter(cp)) break
            start += Character.charCount(cp)
        }
        while (end > start) {
            val cp = token.codePointBefore(end)
            if (Character.isLetter(cp)) break
            end -= Character.charCount(cp)
        }
        return Triple(token.substring(0, start), token.substring(start, end), token.substring(end))
    }

    private fun lower(text: String) = text.lowercase(Locale.ROOT)

    /** Lõi bỏ hậu tố gọi (Haruto-kun -> Haruto) nếu có dáng một tên Latin; null nếu không (không viết hoa, toàn HOA, tiếng reo, chữ lạ). */
    private fun head(core: String): String? {
        val segments = core.split("-").toMutableList()
        while (segments.size > 1 && lower(segments.last()) in Romanization.JA_SUFFIXES) segments.removeAt(segments.size - 1)
        val head = segments.joinToString("-")
        val first = segments[0]
        if (head.length < 2 || first.isEmpty() || !first[0].isUpperCase() || first.substring(1) != lower(first.substring(1))) return null
        if (!segments.all { it.isNotEmpty() && Character.isLetter(it.codePointAt(0)) }) return null
        if (!head.all { it.code < 128 || it in ALLOWED_MARKS }) return null
        val lowered = lower(head)
        for (i in 0 until lowered.length - 2) if (lowered[i] == lowered[i + 1] && lowered[i] == lowered[i + 2]) return null // "Aaaa", "Haaa": tiếng reo
        if (lowered.none { it in 'a'..'z' && it !in "aeiou" }) return null // chỉ nguyên âm ("Aa", "Ooo")
        if (lowered.none { it in "aeiouy" || it.code >= 128 }) return null // không nguyên âm ("Hm", "Nn", "Shh"): tiếng reo
        return head
    }

    /** Từ tiếng Anh thật, hay âm tiết tiếng Việt đã viết sẵn: để nguyên cho sea-g2p. */
    private fun knownWord(head: String): Boolean {
        val plain = lower(head.replace("-", ""))
        return plain in EnglishWords.ALL || ("-" !in head && VietnameseReading.isSyllable(plain))
    }

    private val readings = ConcurrentHashMap<String, String>()

    /** "O-xu-ki-xan" -> "o-xu-ki-xan": một chữ HOA đứng riêng đầu âm tiết của tên nối gạch là âm tiết, không phải viết tắt (sea-g2p đánh vần nó) - `lone_syllable`. */
    fun loneSyllable(reading: String?): String? =
        if (reading != null && reading.length >= 2 && reading[1] == '-' && reading[0].isUpperCase()) reading[0].lowercaseChar() + reading.substring(1) else reading

    /** Cách đọc nối gạch của `core` (đã bỏ dấu câu quanh) khi nó là tên theo luật của `origin`, null khi để nguyên. */
    fun nameReading(core: String, origin: String?): String? {
        if (origin == null || origin !in ORIGINS) return null
        val key = "$origin|$core"
        val hit = readings[key]
        if (hit != null) return hit.ifEmpty { null }
        val head = head(core)
        val found = if (head == null || knownWord(head)) null else loneSyllable(Romanization.reading(core, origin))
        if (readings.size > 8192) readings.clear()
        readings[key] = found ?: ""
        return found
    }

    /** Thay tại chỗ, trong `out`, token (chưa bị đổi so với `toks`) là tên bằng cách đọc của nó, giữ dấu câu quanh; số chữ không đổi. */
    fun readNames(toks: List<String>, out: MutableList<String>, origin: String?) {
        if (origin == null || origin !in ORIGINS) return
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = splitToken(token)
            val reading = if (core.isEmpty()) null else nameReading(core, origin)
            if (reading != null) out[index] = before + reading + after
        }
    }

    /** Hậu tố gọi Nhật nối gạch (JA_SUFFIXES còn "tan", "nee", "nii": dễ lẫn với chữ thường nên chỉ đi theo tên đã nhận) - `HONORIFICS` của names.py. */
    private val HONORIFICS = setOf("san", "kun", "chan", "sama", "senpai", "sensei", "dono")
    /** Tiếng gọi Hàn cố định (bộ thử TN) - `KOREAN_TERMS`. */
    private val KOREAN_TERMS = mapOf("oppa" to "óp-pa", "unnie" to "un-ni", "noona" to "nu-na", "hyung" to "hi-ung", "ssi" to "xi", "nim" to "nim")
    private val KOREAN_ALONE = setOf("oppa", "unnie", "noona", "hyung")
    /** Từ đã vào từ điển tiếng Việt: đọc như từ Việt với mọi cuốn - `DICTIONARY_WORDS`. */
    private val DICTIONARY_WORDS = mapOf("sofa" to "xô-pha", "logic" to "lô-gích", "video" to "vi-đê-ô", "violin" to "vi-ô-lông", "piano" to "pi-a-nô", "sandal" to "xăng-đan",
        "vali" to "va-li", "robot" to "rô-bốt", "gorilla" to "gô-ri-la")
    /** Từ Nhật rất quen: đọc theo luật phiên âm với mọi cuốn, dù có trong danh sách từ Anh - `JAPANESE_COMMON`. */
    private val JAPANESE_COMMON = setOf("anime", "manga", "ninja", "samurai", "bento", "kimono", "sake", "miso", "dango", "takoyaki", "okonomiyaki", "senpai", "sensei",
        "onii", "onee", "otaku", "eroge", "tsukkomi", "ara", "umu")
    /** Tiền / cân của truyện Hàn - Nhật, chỉ khi liền sau một số - `CURRENCY`. */
    private val CURRENCY = mapOf("won" to "guôn", "yen" to "yên", "kwan" to "quan")
    private val NUMBER_WORDS = setOf("nghìn", "ngàn", "triệu", "tỷ", "tỉ", "trăm", "vạn", "chục", "mươi", "mười", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")

    /**
     * Dấu câu sau chữ, đổi cho vừa với cách đọc: sea-g2p đọc nháy đơn đóng sau MỘT chữ cái ("a’", "nha… a'") là "phẩy", nên khi cách đọc kết thúc bằng một chữ cái đứng riêng
     * thì ’ và ' thành dấu ngoặc kép đóng ” (bỏ qua khi đọc) - `closing`.
     */
    fun closing(after: String, reading: String): String {
        val lone = reading.isNotEmpty() && reading.last().isLetter() && !(reading.length >= 2 && reading[reading.length - 2].isLetter())
        return if (lone) after.replace("’", "”").replace("'", "”") else after
    }

    private fun isSuffix(segment: String) = lower(segment) in HONORIFICS || lower(segment) in KOREAN_TERMS

    private fun suffixOk(segment: String) = isSuffix(segment) && !(segment.length > 1 && segment.any { it.isUpperCase() } && segment.none { it.isLowerCase() })

    private fun term(segment: String): String {
        val lowered = lower(segment)
        return KOREAN_TERMS[lowered] ?: Romanization.reading(lowered, "ja") ?: lowered
    }

    /**
     * Cách đọc nối gạch của [core] (đã bỏ dấu câu quanh) khi nó mang hậu tố gọi nối gạch ("Sora-sama", "hiệp sĩ-sama", "Mary-san", "Lane-ssi") hay là tiếng gọi Hàn đứng riêng ("oppa"),
     * null khi để nguyên. Hậu tố đọc theo bảng của nó với MỌI cuốn; phần tên đứng trước đọc theo luật romaji khi nó là tên Nhật rõ (cuốn gốc Hàn thì để [readNames]), còn lại (tên Âu,
     * từ Việt, từ Anh) giữ nguyên chữ - `honorific_reading`.
     */
    fun honorificReading(core: String, origin: String?): String? {
        val segments = core.split("-").toMutableList()
        if (!segments.all { segment -> segment.replace("'", "").let { it.isNotEmpty() && it.all(Char::isLetter) } }) return null
        val popped = ArrayList<String>()
        while (segments.isNotEmpty() && suffixOk(segments.last())) popped.add(0, segments.removeAt(segments.size - 1))
        if (popped.isEmpty() || (segments.isEmpty() && lower(popped[0]) !in KOREAN_ALONE)) return null
        val terms = popped.joinToString("-") { term(it) }
        val head = segments.joinToString("-")
        if (head.isEmpty()) return loneSyllable(terms)
        if (origin != "ko" && popped.all { lower(it) in HONORIFICS }) {
            val whole = if (head[0].isUpperCase()) nameReading(core, "ja")
            else if (head.all { it.code < 128 } && head == lower(head) && !knownWord(head)) Romanization.reading(core, "ja") else null
            if (whole != null) return loneSyllable(whole)
        }
        return "$head-$terms"
    }

    /** Cách đọc của từ đã vào từ điển tiếng Việt hay từ Nhật rất quen, null khi không phải - `loanword_reading`. */
    fun loanwordReading(core: String): String? {
        val lowered = lower(core)
        DICTIONARY_WORDS[lowered]?.let { return it }
        return if (lowered in JAPANESE_COMMON) Romanization.reading(lowered, "ja") else null
    }

    private fun afterNumber(toks: List<String>, index: Int): Boolean {
        val before = if (index > 0) toks[index - 1].trim { it in ".,;:!?…\"'“”‘’()[]" } else ""
        return before.isNotEmpty() && (before.last().isDigit() || lower(before) in NUMBER_WORDS)
    }

    /** Thay tại chỗ, trong `out`, token (chưa bị đổi) là từ mượn quen bằng cách đọc của nó, và "won" / "yen" / "kwan" liền sau một số bằng tên đơn vị đọc Việt - `read_loanwords`. */
    fun readLoanwords(toks: List<String>, out: MutableList<String>) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = splitToken(token)
            if (core.isEmpty()) continue
            var reading = loanwordReading(core)
            if (reading == null && lower(core) in CURRENCY && core.all { it.isLetter() } && afterNumber(toks, index)) reading = CURRENCY[lower(core)]
            if (reading != null) out[index] = before + reading + after
        }
    }

    /** Thay tại chỗ, trong `out`, token (chưa bị đổi) mang hậu tố gọi bằng cách đọc của nó ([honorificReading]), giữ dấu câu quanh; số chữ không đổi. */
    fun readHonorifics(toks: List<String>, out: MutableList<String>, origin: String?) {
        for ((index, token) in toks.withIndex()) {
            if (out[index] != token) continue
            val (before, core, after) = splitToken(token)
            val reading = if (core.isEmpty()) null else honorificReading(core, origin)
            if (reading != null) out[index] = before + reading + after
        }
    }

    // ---- gốc của cuốn ---------------------------------------------------------------------------------------------------------

    /** (mỗi tên đã bỏ hậu tố gọi và số lần nó xuất hiện, riêng những lần nó đi kèm hậu tố gọi kiểu Nhật). `scan_names` của names.py. */
    fun scanNames(texts: Sequence<String>): Pair<Map<String, Int>, Map<String, Int>> {
        val found = LinkedHashMap<String, Int>()
        val suffixed = LinkedHashMap<String, Int>()
        for (text in texts) {
            for (range in WordTokens.tokens(text)) {
                val (_, core, _) = splitToken(text.substring(range.first, range.last + 1))
                if (core.length < 2 || !core[0].isUpperCase()) continue
                val head = head(core)
                if (head != null && !knownWord(head)) {
                    found[head] = (found[head] ?: 0) + 1
                    if (head != core) suffixed[head] = (suffixed[head] ?: 0) + 1
                }
            }
        }
        return found to suffixed
    }

    fun nameCounts(texts: Sequence<String>): Map<String, Int> = scanNames(texts).first

    class Shares(
        val total: Int, val names: Int, val ja: Double, val ko: Double, val koOnly: Double, val jaNames: Int, val koNames: Int,
        val honorific: Int = 0, val honorificNames: Int = 0,
    )

    fun originShares(counts: Map<String, Int>, suffixed: Map<String, Int> = emptyMap()): Shares {
        val total = counts.values.sum()
        var ja = 0
        var ko = 0
        var koOnly = 0
        var jaNames = 0
        var koNames = 0
        for ((name, times) in counts) {
            val byJa = Romanization.reading(name, "ja") != null
            val byKo = Romanization.reading(name, "ko") != null
            if (byJa) ja += times
            if (byKo) ko += times
            if (byKo && !byJa) koOnly += times
            if (byJa) jaNames++
            if (byKo) koNames++
        }
        fun share(value: Int) = if (total == 0) 0.0 else value.toDouble() / total
        val honorific = suffixed.filterKeys { Romanization.reading(it, "ja") != null }
        return Shares(total, counts.size, share(ja), share(ko), share(koOnly), jaNames, koNames, honorific.values.sum(), honorific.size)
    }

    fun decide(shares: Shares): String? {
        if (shares.total < MIN_OCCURRENCES) return null
        if (shares.jaNames >= MIN_NAMES && shares.ja >= JA_SHARE) return "ja"
        if (shares.honorific >= HON_MIN && shares.honorificNames >= HON_NAMES && shares.jaNames >= MIN_NAMES && shares.ja >= HON_JA_SHARE) return "ja"
        if (shares.koNames >= MIN_NAMES && shares.ko >= KO_SHARE && shares.koOnly >= KO_ONLY_SHARE) return "ko"
        return null
    }

    /** "ja" / "ko" khi tên trong cuốn gần như toàn là romaji Nhật / RR Hàn, null khi không chắc. Chỉ `sample` chương đầu được xét (null = hết). */
    fun bookOrigin(texts: Sequence<String>, sample: Int? = SAMPLE_CHAPTERS): String? =
        scanNames(if (sample == null) texts else texts.take(sample)).let { (counts, suffixed) -> decide(originShares(counts, suffixed)) }
}
