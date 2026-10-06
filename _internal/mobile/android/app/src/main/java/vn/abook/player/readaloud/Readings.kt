package vn.abook.player.readaloud

import java.security.MessageDigest
import java.text.Normalizer

/**
 * Cách đọc riêng của một cuốn chỉ có chữ ("Đọc từ này là…", lớp sửa `readings` - [vn.abook.player.BookEdits]): {chữ hiện: chữ đọc}.
 * Bản Kotlin của abook/readaloud/readings.py - hai bên chạy cùng bộ ví dụ tests/fixtures/book_edits/readings/speech.json.
 *
 * Biến đổi để đọc, chữ hiện không đổi. Áp theo TỪNG CHỮ HIỆN ([WordTokens.tokens]): chữ hiện có lõi (bỏ dấu câu / ngoặc hai đầu) trùng
 * đúng một khoá (phân biệt hoa thường, chỉ cả từ) thì lõi ấy được thay bằng chữ đọc, dấu câu hai đầu giữ nguyên. Chữ đọc nhiều từ nối
 * bằng [JOINER] để vẫn là MỘT chữ: số chữ hiện không đổi nên mốc từng chữ vẫn khớp chữ hiện (một vùng sáng cho cả cụm).
 *
 * Giọng VieNeu áp trong `VieneuUnits.spokenTokens` (sau bước đọc tên); giọng khác (Edge, giọng dùng khoá riêng, giọng của máy) nhận
 * [spokenText]. Khoá bộ đệm clip thêm [tag]: chỉ những cách đọc có mặt trong đoạn, nên đổi một cách đọc chỉ đọc lại đoạn có từ ấy.
 */
object Readings {
    /** Edge báo MỘT mốc cho cả "Ha-ru-tô" và không đọc dấu gạch (đo 06-10, xem readings.py). */
    const val JOINER = "-"

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

    /** Khoá hợp lệ của một cách đọc: một chữ (không khoảng trắng), đã là lõi của chính nó, dạng NFC. */
    fun isWord(text: String): Boolean =
        text.isNotEmpty() && coreSpan(text) == (0 to text.length) && text.codePoints().noneMatch { isSpace(it) } &&
            Normalizer.isNormalized(text, Normalizer.Form.NFC)

    /** Chữ đọc thành MỘT chữ hiện: khoảng trắng giữa các từ thành [JOINER]. */
    fun spokenForm(value: String): String = value.split(Regex("[\\p{Z}\\s]+")).filter { it.isNotEmpty() }.joinToString(JOINER)

    private fun key(token: String): String? {
        val (start, end) = coreSpan(token)
        return if (start == end) null else Normalizer.normalize(token.substring(start, end), Normalizer.Form.NFC)
    }

    private fun read(token: String, readings: Map<String, String>): String? {
        val (start, end) = coreSpan(token)
        if (start == end) return null
        val value = readings[Normalizer.normalize(token.substring(start, end), Normalizer.Form.NFC)] ?: return null
        return token.substring(0, start) + spokenForm(value) + token.substring(end)
    }

    /** Thay tại chỗ trong `out` (chữ đem đọc, cùng số phần tử với `toks`) mọi chữ hiện có cách đọc riêng. */
    fun applyTokens(toks: List<String>, out: MutableList<String>, readings: Map<String, String>?) {
        if (readings.isNullOrEmpty()) return
        for ((index, token) in toks.withIndex()) read(token, readings)?.let { out[index] = it }
    }

    /** Chữ đem đọc của cả đoạn cho giọng nhận chữ thô: khoảng trắng giữ nguyên, số chữ hiện không đổi. */
    fun spokenText(text: String, readings: Map<String, String>?): String {
        if (readings.isNullOrEmpty()) return text
        val out = StringBuilder()
        var at = 0
        for (range in WordTokens.tokens(text)) {
            val token = text.substring(range.first, range.last + 1)
            out.append(text, at, range.first).append(read(token, readings) ?: token)
            at = range.last + 1
        }
        return out.append(text, at, text.length).toString()
    }

    /** Các cách đọc có mặt trong đoạn, theo thứ tự xuất hiện lần đầu. */
    fun applicable(text: String, readings: Map<String, String>?): List<Pair<String, String>> {
        if (readings.isNullOrEmpty()) return emptyList()
        val seen = LinkedHashMap<String, String>()
        for (range in WordTokens.tokens(text)) {
            val found = key(text.substring(range.first, range.last + 1)) ?: continue
            val value = readings[found] ?: continue
            if (found !in seen) seen[found] = value
        }
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
