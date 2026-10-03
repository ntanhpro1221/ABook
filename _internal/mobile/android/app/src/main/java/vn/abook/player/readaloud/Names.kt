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
    const val SAMPLE_CHAPTERS = 12
    const val MIN_NAMES = 10
    const val MIN_OCCURRENCES = 100
    const val JA_SHARE = 0.75
    const val KO_SHARE = 0.85
    const val KO_ONLY_SHARE = 0.5
    /** Đổi khi đổi cách đoán: gốc đã lưu của cuốn được đoán lại. */
    const val RULE_VERSION = 1
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
        return head
    }

    /** Từ tiếng Anh thật, hay âm tiết tiếng Việt đã viết sẵn: để nguyên cho sea-g2p. */
    private fun knownWord(head: String): Boolean {
        val plain = lower(head.replace("-", ""))
        return plain in EnglishWords.ALL || ("-" !in head && VietnameseReading.isSyllable(plain))
    }

    private val readings = ConcurrentHashMap<String, String>()

    /** Cách đọc nối gạch của `core` (đã bỏ dấu câu quanh) khi nó là tên theo luật của `origin`, null khi để nguyên. */
    fun nameReading(core: String, origin: String?): String? {
        if (origin == null || origin !in ORIGINS) return null
        val key = "$origin|$core"
        val hit = readings[key]
        if (hit != null) return hit.ifEmpty { null }
        val head = head(core)
        val found = if (head == null || knownWord(head)) null else Romanization.reading(core, origin)
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

    // ---- gốc của cuốn ---------------------------------------------------------------------------------------------------------

    /** Mỗi tên (đã bỏ hậu tố gọi) và số lần nó xuất hiện. */
    fun nameCounts(texts: Sequence<String>): Map<String, Int> {
        val found = LinkedHashMap<String, Int>()
        for (text in texts) {
            for (range in WordTokens.tokens(text)) {
                val (_, core, _) = splitToken(text.substring(range.first, range.last + 1))
                if (core.length < 2 || !core[0].isUpperCase()) continue
                val head = head(core)
                if (head != null && !knownWord(head)) found[head] = (found[head] ?: 0) + 1
            }
        }
        return found
    }

    class Shares(val total: Int, val names: Int, val ja: Double, val ko: Double, val koOnly: Double, val jaNames: Int, val koNames: Int)

    fun originShares(counts: Map<String, Int>): Shares {
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
        return Shares(total, counts.size, share(ja), share(ko), share(koOnly), jaNames, koNames)
    }

    fun decide(shares: Shares): String? {
        if (shares.total < MIN_OCCURRENCES) return null
        if (shares.jaNames >= MIN_NAMES && shares.ja >= JA_SHARE) return "ja"
        if (shares.koNames >= MIN_NAMES && shares.ko >= KO_SHARE && shares.koOnly >= KO_ONLY_SHARE) return "ko"
        return null
    }

    /** "ja" / "ko" khi tên trong cuốn gần như toàn là romaji Nhật / RR Hàn, null khi không chắc. Chỉ `sample` chương đầu được xét (null = hết). */
    fun bookOrigin(texts: Sequence<String>, sample: Int? = SAMPLE_CHAPTERS): String? =
        decide(originShares(nameCounts(if (sample == null) texts else texts.take(sample))))
}
