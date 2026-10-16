package vn.abook.player

import java.math.BigDecimal
import java.math.RoundingMode
import java.util.regex.Pattern

/**
 * Những chỗ Python và Java/ICU hiểu khác nhau mà bản Kotlin của đường N0 (nhạc theo cảnh không học sinh: SceneCues, SceneScenes,
 * SceneChoose, SceneSegmenter) phải làm đúng Python: khoảng trắng, `\w`, `\b`, `$`, làm tròn, `str.split()`... Mọi regex của đường này viết
 * lại từ Python qua [rx] với lớp ký tự VIẾT RA RÕ - không dựa vào `\s` / `\w` / `\b` / cờ Unicode của máy (Android ICU không nhận
 * `UNICODE_CHARACTER_CLASS`, JVM mặc định `\s` / `\w` chỉ ASCII: bài thử JVM không bắt được lỗi loại ấy).
 */
internal object Py {
    /** Thân lớp ký tự của `\s` trong Python (`str.isspace`): ASCII, 0x1C-0x1F, 0x85, NBSP, U+1680, U+2000-200A, U+2028/9, U+202F, U+205F, U+3000. */
    const val SPACE = "\\t\\n\\u000B\\f\\r\\u001C-\\u001F \\u0085\\u00A0\\u1680\\u2000-\\u200A\\u2028\\u2029\\u202F\\u205F\\u3000"
    /** Thân lớp ký tự của `\w` trong Python: chữ, số, gạch dưới. */
    const val WORD = "\\p{L}\\p{N}_"
    private const val BOUNDARY = "(?:(?<=[$WORD])(?![$WORD])|(?<![$WORD])(?=[$WORD]))"
    private const val NOT_BOUNDARY = "(?:(?<=[$WORD])(?=[$WORD])|(?<![$WORD])(?![$WORD]))"

    /**
     * Regex Python (chép nguyên chuỗi gốc) -> [Pattern] cùng nghĩa trên JVM và Android. Dịch `\s \S \d \w \W \b \B $` (Unicode như Python);
     * `$` Python khớp cả TRƯỚC dấu xuống dòng cuối. Không dịch được `\S` / `\W` trong ngoặc vuông (viết lại cho khỏi cần).
     * `ignoreCase`: Python `re.IGNORECASE` = so không phân biệt hoa thường theo Unicode. `dotAll`: `re.DOTALL`.
     */
    fun rx(python: String, ignoreCase: Boolean = false, dotAll: Boolean = false): Pattern {
        val out = StringBuilder()
        var inClass = false
        var at = 0
        while (at < python.length) {
            val c = python[at]
            when {
                c == '\\' && at + 1 < python.length -> {
                    val next = python[at + 1]
                    at += 2
                    when (next) {
                        's' -> out.append(if (inClass) SPACE else "[$SPACE]")
                        'S' -> if (inClass) throw IllegalArgumentException("\\S trong ngoặc vuông") else out.append("[^$SPACE]")
                        'd' -> out.append("\\p{Nd}")
                        'D' -> if (inClass) throw IllegalArgumentException("\\D trong ngoặc vuông") else out.append("\\P{Nd}")
                        'w' -> out.append(if (inClass) WORD else "[$WORD]")
                        'W' -> if (inClass) throw IllegalArgumentException("\\W trong ngoặc vuông") else out.append("[^$WORD]")
                        'b' -> if (inClass) throw IllegalArgumentException("\\b trong ngoặc vuông") else out.append(BOUNDARY)
                        'B' -> if (inClass) throw IllegalArgumentException("\\B trong ngoặc vuông") else out.append(NOT_BOUNDARY)
                        else -> out.append('\\').append(next)
                    }
                    continue
                }
                inClass -> {
                    when (c) {
                        ']' -> { inClass = false; out.append(c) }
                        // Trong ngoặc vuông của Python `[` và `&` là chữ; Java/ICU hiểu `[` là lớp lồng, `&&` là giao.
                        '[', '&' -> out.append('\\').append(c)
                        else -> out.append(c)
                    }
                }
                c == '[' -> {
                    inClass = true
                    out.append(c)
                    // `[^]...]` / `[]...]`: dấu ] đầu tiên là chữ. Các regex của đường này không dùng, nhưng giữ cho đúng.
                    if (at + 1 < python.length && python[at + 1] == '^') { out.append('^'); at++ }
                    if (at + 1 < python.length && python[at + 1] == ']') { out.append("\\]"); at++ }
                }
                c == '$' -> out.append("(?=\\n?\\z)")
                else -> out.append(c)
            }
            at++
        }
        var flags = 0
        if (ignoreCase) flags = flags or Pattern.CASE_INSENSITIVE or Pattern.UNICODE_CASE
        if (dotAll) flags = flags or Pattern.DOTALL
        return Pattern.compile(out.toString(), flags)
    }

    /** `pattern.match(text)` của Python: khớp ở ĐẦU chuỗi (không cần hết chuỗi). */
    fun match(pattern: Pattern, text: CharSequence): Boolean = pattern.matcher(text).lookingAt()

    /** `pattern.search(text)`. */
    fun search(pattern: Pattern, text: CharSequence): Boolean = pattern.matcher(text).find()

    /** `pattern.fullmatch(text)`. */
    fun fullMatch(pattern: Pattern, text: CharSequence): Boolean = pattern.matcher(text).matches()

    /** `str.isspace()` của một code point. */
    fun isSpace(cp: Int): Boolean = when (cp) {
        in 0x09..0x0D, in 0x1C..0x20, 0x85, 0xA0, 0x1680, in 0x2000..0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000 -> true
        else -> false
    }

    /** `str.isalnum()` của một code point: chữ (Lu Ll Lt Lm Lo) hoặc số (Nd Nl No). */
    fun isAlnum(cp: Int): Boolean = Character.isLetter(cp) || when (Character.getType(cp)) {
        Character.DECIMAL_DIGIT_NUMBER.toInt(), Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt() -> true
        else -> false
    }

    /** `any(char.isalnum() for char in text)` (text_processing.has_spoken_content). */
    fun hasAlnum(text: String): Boolean {
        var at = 0
        while (at < text.length) {
            val cp = text.codePointAt(at)
            if (isAlnum(cp)) return true
            at += Character.charCount(cp)
        }
        return false
    }

    /** `str.isupper()` của ký tự ĐẦU (code point) của `text`; chuỗi rỗng: false. */
    fun firstIsUpper(text: String): Boolean = text.isNotEmpty() && Character.isUpperCase(text.codePointAt(0))

    /** `str.strip()`. */
    fun strip(text: String): String {
        var start = 0
        var end = text.length
        while (start < end && isSpace(text.codePointAt(start))) start += Character.charCount(text.codePointAt(start))
        while (end > start && isSpace(text.codePointBefore(end))) end -= Character.charCount(text.codePointBefore(end))
        return text.substring(start, end)
    }

    /** `str.rstrip()`. */
    fun rstrip(text: String): String {
        var end = text.length
        while (end > 0 && isSpace(text.codePointBefore(end))) end -= Character.charCount(text.codePointBefore(end))
        return text.substring(0, end)
    }

    /** `str.lstrip()`. */
    fun lstrip(text: String): String {
        var start = 0
        while (start < text.length && isSpace(text.codePointAt(start))) start += Character.charCount(text.codePointAt(start))
        return text.substring(start)
    }

    /** `str.split()` không đối số: tách theo chuỗi khoảng trắng Python, bỏ mảnh rỗng. */
    fun split(text: String): List<String> {
        val out = ArrayList<String>()
        var from = -1
        var at = 0
        while (at < text.length) {
            val cp = text.codePointAt(at)
            val width = Character.charCount(cp)
            if (isSpace(cp)) {
                if (from >= 0) { out.add(text.substring(from, at)); from = -1 }
            } else if (from < 0) {
                from = at
            }
            at += width
        }
        if (from >= 0) out.add(text.substring(from))
        return out
    }

    /** `str.splitlines()`: \n \r \r\n \v \f \x1c \x1d \x1e \x85     là ngắt dòng; không giữ dấu ngắt. */
    fun splitLines(text: String): List<String> {
        val out = ArrayList<String>()
        var from = 0
        var at = 0
        while (at < text.length) {
            val c = text[at]
            val breaks = c == '\n' || c == '\r' || c == '\u000B' || c == '\u000C' || c == '\u001C' || c == '\u001D' || c == '\u001E' ||
                c == '\u0085' || c == '\u2028' || c == '\u2029'
            if (breaks) {
                out.add(text.substring(from, at))
                if (c == '\r' && at + 1 < text.length && text[at + 1] == '\n') at++
                from = at + 1
            }
            at++
        }
        if (from < text.length) out.add(text.substring(from))
        return out
    }

    /** `len(text)` của Python: số code point. */
    fun len(text: String): Int = text.codePointCount(0, text.length)

    /** `round(value, digits)` của Python: làm tròn chẵn-gần-nhất trên GIÁ TRỊ NHỊ PHÂN CHÍNH XÁC của số. */
    fun round(value: Double, digits: Int): Double =
        if (value.isNaN() || value.isInfinite()) value else BigDecimal(value).setScale(digits, RoundingMode.HALF_EVEN).toDouble()
}
