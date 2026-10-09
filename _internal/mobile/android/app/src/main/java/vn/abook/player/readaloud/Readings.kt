package vn.abook.player.readaloud

import java.security.MessageDigest
import java.text.Normalizer

/**
 * Cách đọc riêng của một cuốn chỉ có chữ ("Đọc từ này là…", lớp sửa `readings` - [vn.abook.player.BookEdits]): {khoá: chữ đọc}.
 * Bản Kotlin của abook/readaloud/readings.py - hai bên chạy cùng bộ ví dụ tests/fixtures/book_edits/readings/speech.json.
 *
 * Khoá là MỘT chữ ("Haruto") hay một CỤM 2..[KEY_WORDS_MAX] chữ liền nhau nối bằng một dấu cách ("Hạ Vy", "ông Tư"; [isKey]). Biến đổi để đọc, chữ hiện không
 * đổi. Duyệt theo TỪNG CHỮ HIỆN ([WordTokens.tokens]) từ trái sang phải, ở mỗi chỗ thử khoá DÀI NHẤT (theo số chữ) trước: các chữ hiện có lõi (bỏ dấu câu / ngoặc hai
 * đầu) trùng đúng từng chữ của khoá (phân biệt hoa thường, chỉ cả từ) và không có dấu câu chen GIỮA cụm ("Hạ, Vy" không khớp "Hạ Vy") thì phần lõi được thay bằng
 * chữ đọc, dấu câu đầu cụm và đuôi cụm giữ nguyên. Số chữ hiện không đổi nên mốc từng chữ vẫn khớp chữ hiện: chữ đọc tách theo khoảng trắng thành m từ, chia đều cho
 * k chữ hiện của cụm (nhóm đầu nhận phần dư), mỗi nhóm nối bằng [JOINER] thành MỘT chữ. m < k: các chữ hiện cuối không còn từ nào, chữ đọc của chúng là "" (dấu câu
 * đuôi cụm dính vào từ đọc cuối) - nơi tiêu thụ bỏ chữ rỗng.
 *
 * Giọng đọc trên máy (VieNeu, Supertonic) áp trong `VieneuUnits.spokenTokens` (sau bước đọc tên; `units` bỏ chữ rỗng khi ghép câu); giọng khác (Edge, giọng dùng khoá
 * riêng, giọng của máy) nhận [spokenLayout] - chữ đem đọc đã thay (chữ rỗng mất khỏi chuỗi, bảng chữ hiện -> chữ đem đọc; [expandWords] trả mốc về đủ chữ hiện). Khoá bộ đệm
 * clip thêm [tag]: chỉ những cách đọc có mặt trong đoạn, nên đổi một cách đọc chỉ đọc lại đoạn có cụm ấy.
 */
object Readings {
    /** Edge báo MỘT mốc cho cả "Ha-ru-tô" và không đọc dấu gạch (đo 06-10, xem readings.py). */
    const val JOINER = "-"

    /** Khoá dài nhất: 6 chữ liền nhau. */
    const val KEY_WORDS_MAX = 6

    private fun isCore(codePoint: Int): Boolean = when (Character.getType(codePoint)) {
        Character.UPPERCASE_LETTER.toInt(), Character.LOWERCASE_LETTER.toInt(), Character.TITLECASE_LETTER.toInt(),
        Character.MODIFIER_LETTER.toInt(), Character.OTHER_LETTER.toInt(), Character.NON_SPACING_MARK.toInt(),
        Character.ENCLOSING_MARK.toInt(), Character.COMBINING_SPACING_MARK.toInt(), Character.DECIMAL_DIGIT_NUMBER.toInt(),
        Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt() -> true
        else -> false
    }

    private fun isSpace(codePoint: Int) = Character.isWhitespace(codePoint) || Character.isSpaceChar(codePoint)

    /** [đầu, cuối) của lõi chữ (vị trí ký tự Java): bỏ mọi ký tự không phải chữ / dấu thanh / số ở hai đầu. */
    fun coreSpan(token: String): Pair<Int, Int> {
        var start = 0
        var end = token.length
        while (start < end && !isCore(token.codePointAt(start))) start += Character.charCount(token.codePointAt(start))
        while (end > start && !isCore(token.codePointBefore(end))) end -= Character.charCount(token.codePointBefore(end))
        return start to end
    }

    /** Một chữ (không khoảng trắng), đã là lõi của chính nó, dạng NFC. */
    fun isWord(text: String): Boolean =
        text.isNotEmpty() && coreSpan(text) == (0 to text.length) && text.codePoints().noneMatch { isSpace(it) } &&
            Normalizer.isNormalized(text, Normalizer.Form.NFC)

    /** Khoá hợp lệ của một cách đọc: 1..[KEY_WORDS_MAX] chữ ([isWord]) nối bằng MỘT dấu cách, dạng NFC. */
    fun isKey(text: String): Boolean {
        val words = text.split(" ")
        return words.size in 1..KEY_WORDS_MAX && words.all { isWord(it) } && Normalizer.isNormalized(text, Normalizer.Form.NFC)
    }

    private fun words(value: String): List<String> = value.split(Regex("[\\p{Z}\\s]+")).filter { it.isNotEmpty() }

    /** Chữ đọc thành MỘT chữ hiện: khoảng trắng giữa các từ thành [JOINER]. */
    fun spokenForm(value: String): String = words(value).joinToString(JOINER)

    /**
     * Khoá `count` chữ mà các chữ hiện `toks[at until at + count]` đang mang, null khi chúng không thể là một cụm: chữ nào không có lõi, hay có dấu câu CHEN GIỮA
     * (đuôi ngoài lõi của chữ không phải cuối cụm, đầu ngoài lõi của chữ không phải đầu cụm).
     */
    private fun phraseKey(toks: List<String>, at: Int, count: Int): String? {
        val parts = ArrayList<String>(count)
        for (offset in 0 until count) {
            val token = toks[at + offset]
            val (start, end) = coreSpan(token)
            if (start == end || (offset > 0 && start > 0) || (offset < count - 1 && end != token.length)) return null
            parts.add(Normalizer.normalize(token.substring(start, end), Normalizer.Form.NFC))
        }
        return parts.joinToString(" ")
    }

    /** Một cụm có cách đọc riêng: từ chữ hiện `at`, dài `count` chữ, khoá `key`. */
    private class Hit(val at: Int, val count: Int, val key: String)

    /** Các cụm có cách đọc riêng, trái sang phải, khoá dài nhất thắng, mỗi chữ hiện thuộc nhiều nhất một cụm. Khoá có chữ đọc không còn từ nào không tính. */
    private fun matches(toks: List<String>, readings: Map<String, String>): List<Hit> {
        val longest = minOf(KEY_WORDS_MAX, readings.entries.filter { words(it.value).isNotEmpty() }.maxOfOrNull { entry -> entry.key.count { it == ' ' } + 1 } ?: 0)
        val found = ArrayList<Hit>()
        var at = 0
        while (at < toks.size) {
            var hit: Hit? = null
            for (count in minOf(longest, toks.size - at) downTo 1) {
                val key = phraseKey(toks, at, count)
                if (key != null && readings[key]?.let { words(it).isNotEmpty() } == true) {
                    hit = Hit(at, count, key)
                    break
                }
            }
            if (hit != null) {
                found.add(hit)
                at += hit.count
            } else {
                at += 1
            }
        }
        return found
    }

    /** Chữ đọc chia cho `count` chữ hiện: m từ thành `count` nhóm liền nhau đều nhất (nhóm đầu nhận phần dư), mỗi nhóm nối bằng [JOINER]; m < count thì nhóm cuối rỗng. */
    private fun groups(value: String, count: Int): List<String> {
        val parts = words(value)
        val size = parts.size / count
        val extra = parts.size % count
        val out = ArrayList<String>(count)
        var at = 0
        for (index in 0 until count) {
            val take = size + if (index < extra) 1 else 0
            out.add(parts.subList(at, at + take).joinToString(JOINER))
            at += take
        }
        return out
    }

    /** Chữ đem đọc của từng chữ hiện (cùng số phần tử với `toks`; "" là chữ hiện không còn từ nào để đọc): chữ không thuộc cách đọc nào giữ nguyên. */
    private fun spoken(toks: List<String>, readings: Map<String, String>): MutableList<String> {
        val out = toks.toMutableList()
        for (hit in matches(toks, readings)) {
            val groups = groups(readings.getValue(hit.key), hit.count)
            val head = toks[hit.at]
            val tail = toks[hit.at + hit.count - 1]
            val pieces = groups.toMutableList()
            pieces[0] = head.substring(0, coreSpan(head).first) + groups[0]
            val said = groups.indexOfLast { it.isNotEmpty() } // nhóm cuối còn từ: dấu câu đuôi cụm dính vào nó
            pieces[said] = pieces[said] + tail.substring(coreSpan(tail).second)
            for (index in pieces.indices) out[hit.at + index] = pieces[index]
        }
        return out
    }

    /** Thay tại chỗ trong `out` (chữ đem đọc, cùng số phần tử với `toks`) mọi chữ hiện có cách đọc riêng; chữ hiện cuối cụm không còn từ nào thành "". */
    fun applyTokens(toks: List<String>, out: MutableList<String>, readings: Map<String, String>?) {
        if (readings.isNullOrEmpty()) return
        val said = spoken(toks, readings)
        for (index in toks.indices) if (said[index] != toks[index]) out[index] = said[index]
    }

    /**
     * (chữ đem đọc của cả đoạn, bảng) cho giọng nhận chữ thô. Khoảng trắng giữ nguyên; chữ hiện không còn từ nào (cụm đọc ngắn hơn số chữ) mất khỏi chuỗi cùng khoảng trắng
     * đứng trước nó. `bảng[i]` = số thứ tự trong chữ đem đọc của chữ hiện `i`, null cho chữ đã mất - xem [expandWords].
     */
    fun spokenLayout(text: String, readings: Map<String, String>?): Pair<String, List<Int?>> {
        val ranges = WordTokens.tokens(text)
        if (readings.isNullOrEmpty()) return text to ranges.indices.toList()
        val said = spoken(ranges.map { text.substring(it.first, it.last + 1) }, readings)
        val out = StringBuilder()
        val slots = ArrayList<Int?>()
        var kept = 0
        var at = 0
        for ((index, range) in ranges.withIndex()) {
            if (said[index].isNotEmpty()) {
                out.append(text, at, range.first).append(said[index])
                slots.add(kept++)
            } else {
                slots.add(null)
            }
            at = range.last + 1
        }
        return out.append(text, at, text.length).toString() to slots
    }

    /** Chữ đem đọc của cả đoạn cho giọng nhận chữ thô ([spokenLayout]). */
    fun spokenText(text: String, readings: Map<String, String>?): String = spokenLayout(text, readings).first

    /** Mốc từng chữ của chữ đem đọc -> mốc từng chữ HIỆN: chữ đã mất khỏi chuỗi đứng ở cuối mốc chữ trước nó (mốc rỗng). */
    fun expandWords(words: List<Span>, slots: List<Int?>): List<Span> {
        val out = ArrayList<Span>(slots.size)
        for (slot in slots) {
            if (slot != null && slot < words.size) {
                out.add(words[slot])
            } else {
                val end = out.lastOrNull()?.end ?: 0L
                out.add(Span(end, end))
            }
        }
        return out
    }

    /** Các cách đọc có mặt trong đoạn (khoá một chữ hay cụm), theo thứ tự xuất hiện lần đầu. */
    fun applicable(text: String, readings: Map<String, String>?): List<Pair<String, String>> {
        if (readings.isNullOrEmpty()) return emptyList()
        val seen = LinkedHashMap<String, String>()
        val toks = WordTokens.tokens(text).map { text.substring(it.first, it.last + 1) }
        for (hit in matches(toks, readings)) if (hit.key !in seen) seen[hit.key] = readings.getValue(hit.key)
        return seen.toList()
    }

    /** Dấu cho khoá bộ đệm clip: "" khi đoạn không có từ nào có cách đọc riêng, không thì "r" + 16 số hex của các cách đọc có mặt. */
    fun tag(text: String, readings: Map<String, String>?): String {
        val found = applicable(text, readings)
        if (found.isEmpty()) return ""
        val digest = MessageDigest.getInstance("SHA-256").digest(found.joinToString("\n") { "${it.first}\t${it.second}" }.toByteArray(Charsets.UTF_8))
        return "r" + digest.joinToString("") { "%02x".format(it) }.substring(0, 16)
    }
}
