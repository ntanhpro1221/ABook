package vn.abook.player.readaloud

import java.text.Normalizer

/** Mốc một chữ trong đoạn âm thanh: mili giây tính từ đầu đoạn. */
data class Span(val start: Long, val end: Long)

/**
 * Một mảnh do giọng đọc báo, theo thứ tự đọc: lúc nào (ms từ đầu đoạn) và chữ nào. `text` là mảnh chữ (Edge `WordBoundary`; với giọng của máy là đoạn chữ ở khoảng
 * ký tự mà `onRangeStart` báo). `char` (nếu có) là vị trí ký tự (code point, từ 0) của mảnh trong chữ đã đưa cho giọng - gợi ý để lấy lại nhịp khi lệch.
 */
data class Boundary(val startMs: Long, val endMs: Long, val text: String?, val char: Int = -1)

/**
 * Từ mốc của giọng đọc ra `words` của một đoạn - đúng hình mà ui/src/listen/words.ts đọc: mỗi chữ hiện (`\S+`) một cặp [bắt đầu, kết thúc] ms từ đầu đoạn, không
 * giảm, số cặp = số chữ, không quá `durationMs`. MỌI giọng đưa về hàm này (Edge: mảnh chữ; điện thoại: mảnh chữ + vị trí ký tự; không có mảnh: chia đều theo độ dài chữ).
 *
 * Đây là bản Kotlin của thuật toán trong `tests/fixtures/readaloud/README.md` (Python: `abook/readaloud/mapping.py`) - hai bên chạy CÙNG các file ví dụ
 * trong thư mục ấy (WordTokensTest) nên đổi một bên là phải đổi cả hai. Mọi phép toán là số nguyên, chia làm tròn xuống.
 */
object WordTokens {
    /** Mảnh phải BẮT ĐẦU trong chừng này chữ phía trước con trỏ (chữ t .. t + LOOKAHEAD). */
    const val LOOKAHEAD = 8
    private val TOKEN = Regex("[^${Paragraphs.JS_SPACE}]+")

    /** Các chữ hiện của đoạn: (vị trí đầu, vị trí cuối) trong chuỗi - `\S+` như `countTokens` của words.ts. */
    fun tokens(text: String): List<IntRange> = TOKEN.findAll(text).map { it.range }.toList()

    fun count(text: String): Int = tokens(text).size

    /** NFC, chữ thường, chỉ giữ chữ cái (L*) và chữ số (N*) - theo code point. */
    fun fold(piece: String): IntArray {
        val out = ArrayList<Int>()
        Normalizer.normalize(piece, Normalizer.Form.NFC).lowercase().codePoints().forEach { cp ->
            when (Character.getType(cp)) {
                Character.UPPERCASE_LETTER.toInt(), Character.LOWERCASE_LETTER.toInt(), Character.TITLECASE_LETTER.toInt(),
                Character.MODIFIER_LETTER.toInt(), Character.OTHER_LETTER.toInt(), Character.DECIMAL_DIGIT_NUMBER.toInt(),
                Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt() -> out.add(cp)
            }
        }
        return out.toIntArray()
    }

    /** Chỗ khớp của một mảnh: phủ chữ `first` (từ ký tự `offset`) tới chữ `last` (tới ký tự `stop`, không gồm). */
    private class Match(val first: Int, val offset: Int, val last: Int, val stop: Int)

    fun map(text: String, boundaries: List<Boundary>, durationMs: Long): List<Span> {
        val ranges = tokens(text)
        val n = ranges.size
        if (n == 0) return emptyList()
        val folds = Array(n) { fold(text.substring(ranges[it].first, ranges[it].last + 1)) }
        val lengths = IntArray(n) { text.codePointCount(ranges[it].first, ranges[it].last + 1) }
        val cpStart = IntArray(n) { text.codePointCount(0, ranges[it].first) }
        val total = durationMs.coerceAtLeast(0)
        val starts = LongArray(n) { -1 }
        val ends = LongArray(n) { -1 }

        /** Chữ chứa ký tự thứ `char`: rơi vào khoảng trắng thì chữ kế sau, quá cuối thì chữ cuối. */
        fun tokenAt(char: Int): Int {
            for (i in 0 until n) if (char < cpStart[i] + lengths[i]) return i
            return n - 1
        }

        /** Tìm `key` bắt đầu từ ký tự `c0` của chữ `t0`, trong LOOKAHEAD chữ đầu; chỗ khớp ở đầu chữ (hay đúng con trỏ) thắng chỗ khớp giữa chữ. */
        fun find(key: IntArray, t0: Int, c0: Int): Match? {
            if (t0 >= n) return null
            val limit = minOf(n - 1, t0 + LOOKAHEAD)
            val s = ArrayList<Int>()
            val owner = ArrayList<Int>()
            val offset = ArrayList<Int>()
            var windowEnd = -1
            var token = t0
            while (token < n) {
                if (token > limit && s.size >= windowEnd + key.size) break
                val from = if (token == t0) c0.coerceAtMost(folds[token].size) else 0
                for (k in from until folds[token].size) {
                    s.add(folds[token][k])
                    owner.add(token)
                    offset.add(k)
                }
                if (token == limit) windowEnd = s.size
                token += 1
            }
            var middle = -1
            for (pos in 0..(s.size - key.size)) {
                if (owner[pos] > limit) break
                var same = true
                for (k in key.indices) if (s[pos + k] != key[k]) { same = false; break }
                if (!same) continue
                if (pos == 0 || offset[pos] == 0) return Match(owner[pos], offset[pos], owner[pos + key.size - 1], offset[pos + key.size - 1] + 1)
                if (middle < 0) middle = pos
            }
            return if (middle >= 0) Match(owner[middle], offset[middle], owner[middle + key.size - 1], offset[middle + key.size - 1] + 1) else null
        }

        var t = 0
        var c = 0
        for (b in boundaries) {
            val key = fold(b.text.orEmpty())
            if (key.isEmpty()) continue
            var hit: Match? = null
            if (b.char >= 0) {
                val g = tokenAt(b.char)
                if (g > t) hit = find(key, g, 0)
            }
            if (hit == null) hit = find(key, t, c)
            if (hit == null) continue
            // Chia [start, end] cho các chữ phủ theo số ký tự mỗi chữ được phủ.
            val sizes = (hit.first..hit.last).map { k ->
                val from = if (k == hit.first) hit.offset else 0
                val to = if (k == hit.last) hit.stop else folds[k].size
                (to - from).coerceAtLeast(0)
            }
            val sum = sizes.sum().coerceAtLeast(1)
            var before = 0
            for ((i, k) in (hit.first..hit.last).withIndex()) {
                val lo = b.startMs + (b.endMs - b.startMs) * before / sum
                before += sizes[i]
                val hi = b.startMs + (b.endMs - b.startMs) * before / sum
                if (starts[k] < 0) starts[k] = lo
                ends[k] = hi
            }
            t = hit.last
            c = hit.stop
        }

        // Chữ chưa có mốc: mỗi cụm liền nhau nhận khoảng từ (kết thúc chữ có mốc trước) tới (bắt đầu chữ có mốc sau), chia theo độ dài chữ.
        var i = 0
        while (i < n) {
            if (starts[i] >= 0) {
                i += 1
                continue
            }
            var j = i
            while (j < n && starts[j] < 0) j += 1
            val left = if (i > 0) ends[i - 1] else 0L
            val right = (if (j < n) starts[j] else total).coerceAtLeast(left)
            val weight = (i until j).sumOf { lengths[it] }.coerceAtLeast(1)
            var before = 0
            for (k in i until j) {
                starts[k] = left + (right - left) * before / weight
                before += lengths[k]
                ends[k] = left + (right - left) * before / weight
            }
            i = j
        }

        // Làm sạch theo thứ tự chữ: không giảm, không quá độ dài; chữ không chồng sang chữ sau.
        var previous = 0L
        for (k in 0 until n) {
            starts[k] = minOf(maxOf(starts[k], previous), total)
            ends[k] = minOf(maxOf(ends[k], starts[k]), total)
            previous = starts[k]
        }
        return (0 until n).map { k -> Span(starts[k], if (k + 1 < n) minOf(ends[k], starts[k + 1]) else ends[k]) }
    }
}
