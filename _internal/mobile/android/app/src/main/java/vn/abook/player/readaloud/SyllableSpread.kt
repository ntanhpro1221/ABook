package vn.abook.player.readaloud

import java.text.Normalizer
import java.util.Locale

/**
 * Mốc từng chữ cho giọng KHÔNG báo mốc (FPT.AI, Viettel AI): chia độ dài clip theo âm tiết, chừa chỗ ngắt ở dấu câu - bản Kotlin của `abook/readaloud/spread.py`
 * (+ `word_timing.syllable_count`). Hai bên chạy CÙNG bộ ví dụ `tests/fixtures/readaloud/spread/` (README.md ở đó viết thuật toán) nên đổi một bên là phải đổi
 * cả hai. Kết quả là các [Boundary] (một mảnh mỗi chữ có âm tiết, kèm vị trí ký tự) đi qua [WordTokens.map] như mọi giọng. Toàn số nguyên.
 */
object SyllableSpread {
    const val SYLLABLE = 4
    const val COMMA_PAUSE = 4
    const val SENTENCE_PAUSE = 8
    private const val STRIP = "\"'“”‘’()[]«»—–-…,.!?:;"
    private const val CLOSERS = "\"'”’)]»"
    private const val COMMA = ",;:—–"
    private const val SENTENCE = ".!?…"

    private fun isWordChar(cp: Int): Boolean = cp == '_'.code || when (Character.getType(cp)) {
        Character.UPPERCASE_LETTER.toInt(), Character.LOWERCASE_LETTER.toInt(), Character.TITLECASE_LETTER.toInt(), Character.MODIFIER_LETTER.toInt(),
        Character.OTHER_LETTER.toInt(), Character.DECIMAL_DIGIT_NUMBER.toInt(), Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt() -> true
        else -> false
    }

    private fun isDecimal(text: String) = text.isNotEmpty() && text.codePoints().allMatch { Character.getType(it) == Character.DECIMAL_DIGIT_NUMBER.toInt() }

    /** Python `\d+(\.\d{3})*`: chấm ngăn nhóm ba chữ số. */
    private fun isGroupedNumber(text: String): Boolean {
        val parts = text.split('.')
        return isDecimal(parts[0]) && parts.drop(1).all { it.codePointCount(0, it.length) == 3 && isDecimal(it) }
    }

    /** Số âm tiết của `đọc_ba(nhóm, đủ)` (word_timing._read_three). */
    private fun three(value: Int, full: Boolean): Int {
        val hundreds = value / 100
        val tens = (value / 10) % 10
        val units = value % 10
        var count = if (full || hundreds != 0) 2 else 0
        count += when (tens) {
            0 -> if (units != 0 && (full || hundreds != 0)) 2 else if (units != 0) 1 else 0
            1 -> 1 + if (units != 0) 1 else 0
            else -> 2 + if (units != 0) 1 else 0
        }
        return count
    }

    /** Số âm tiết khi đọc số `digits` (chỉ chữ số thập phân) thành lời (word_timing.read_number): "2500" = hai nghìn năm trăm = 4. */
    fun numberSyllables(digits: String): Int {
        val values = digits.codePoints().map { Character.digit(it, 10) }.toArray().dropWhile { it == 0 }
        if (values.isEmpty()) return 1
        val groups = ArrayList<Int>()
        var end = values.size
        while (end > 0) {
            val start = maxOf(0, end - 3)
            groups.add(values.subList(start, end).fold(0) { acc, d -> acc * 10 + d })
            end = start
        }
        var count = 0
        for (position in groups.indices.reversed()) {
            val group = groups[position]
            if (group == 0) continue
            count += three(group, full = position < groups.size - 1)
            if (position in 1..3) count += 1 // nghìn / triệu / tỷ
        }
        return count
    }

    /** word_timing.syllable_count trên chữ đã NFC. */
    fun syllables(token: String): Int {
        val core = Normalizer.normalize(token, Normalizer.Form.NFC).trim { it in STRIP }.lowercase(Locale.ROOT)
        if (core.isEmpty()) return 0
        if (isGroupedNumber(core)) return numberSyllables(core.replace(".", ""))
        val parts = ArrayList<String>()
        val current = StringBuilder()
        core.codePoints().forEach { cp ->
            if (isWordChar(cp) && cp != '_'.code) current.appendCodePoint(cp)
            else if (current.isNotEmpty()) { parts.add(current.toString()); current.setLength(0) }
        }
        if (current.isNotEmpty()) parts.add(current.toString())
        var count = 0
        for (part in parts) count += if (isDecimal(part)) numberSyllables(part) else 1
        if (count != 1) return count
        val only = parts.single()
        if (isDecimal(only) || !only.all { it in 'a'..'z' }) return 1
        return maxOf(1, Regex("[aeiouy]+").findAll(only).count())
    }

    fun pauseAfter(token: String): Int {
        val core = token.trimEnd { it in CLOSERS }
        if (core.isEmpty()) return 0
        return when (core.last()) {
            in SENTENCE -> SENTENCE_PAUSE
            in COMMA -> COMMA_PAUSE
            else -> 0
        }
    }

    fun boundaries(text: String, durationMs: Long): List<Boundary> {
        val ranges = WordTokens.tokens(text)
        val words = ranges.map { text.substring(it.first, it.last + 1) }
        val weights = words.map { SYLLABLE * syllables(it) }
        val pauses = words.mapIndexed { index, word -> if (index + 1 < words.size) pauseAfter(word) else 0 }
        val total = weights.sum() + pauses.sum()
        if (total == 0 || durationMs <= 0) return emptyList()
        val out = ArrayList<Boundary>()
        var before = 0L
        for (i in words.indices) {
            if (weights[i] > 0) {
                out.add(Boundary(durationMs * before / total, durationMs * (before + weights[i]) / total, words[i], text.codePointCount(0, ranges[i].first)))
            }
            before += weights[i] + pauses[i]
        }
        return out
    }
}
