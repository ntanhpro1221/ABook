package vn.abook.player.ui

/**
 * Máy dò chuyển cảnh chỉ có alpha trong mã nguồn giao diện native (docs/NATIVE_PHONE_UI.md §4: "loại fade là tôi ghét nhất").
 * Quét chữ, không biên dịch: bắt `fadeIn(` / `fadeOut(` không đi cùng slide / scale / expand / shrink trong CÙNG MỘT biểu thức (nối bằng `+`,
 * `togetherWith`, `with`, hay `.`), mọi `Crossfade(`, `AnimatedContent(` không có `transitionSpec` (mặc định là mờ chéo), và alpha chạy một mình
 * (`.alpha(giá trị động)`, `graphicsLayer { alpha = ... }` không kèm translation / scale / rotation, biến alpha lấy từ `animate*AsState`).
 */
object MotionScan {
    data class Finding(val file: String, val line: Int, val why: String)

    private val geometry = Regex("""\b(slideIn|slideOut|scaleIn|scaleOut|expand|shrink)\w*\s*[({]""")
    private val fadeCall = Regex("""\bfade(In|Out)\s*\(""")
    private val alphaModifier = Regex("""\.alpha\(\s*(?![0-9.]+f?\s*\))""")
    private val animatedAlpha = Regex("""\bval\s+\w*(alpha|fade|opacity)\w*\s*(by|=)\s*(animate\w*AsState|Animatable|updateTransition)""", RegexOption.IGNORE_CASE)

    /** Thay chú thích bằng khoảng trắng (giữ nguyên số dòng). */
    fun stripComments(source: String): String {
        val out = StringBuilder(source.length)
        var i = 0
        while (i < source.length) {
            when {
                source.startsWith("//", i) -> while (i < source.length && source[i] != '\n') { out.append(' '); i++ }
                source.startsWith("/*", i) -> {
                    val end = source.indexOf("*/", i + 2).let { if (it < 0) source.length else it + 2 }
                    while (i < end) { out.append(if (source[i] == '\n') '\n' else ' '); i++ }
                }
                else -> { out.append(source[i]); i++ }
            }
        }
        return out.toString()
    }

    private fun matchForward(text: String, open: Int, up: Char, down: Char): Int {
        var depth = 0
        var i = open
        while (i < text.length) {
            if (text[i] == up) depth++ else if (text[i] == down && --depth == 0) return i + 1
            i++
        }
        return text.length
    }

    private fun matchBackward(text: String, close: Int, up: Char, down: Char): Int {
        var depth = 0
        var i = close
        while (i >= 0) {
            if (text[i] == down) depth++ else if (text[i] == up && --depth == 0) return i
            i--
        }
        return 0
    }

    private fun isIdent(c: Char) = c.isLetterOrDigit() || c == '_'

    /** Hết một toán hạng bắt đầu ở `from`: chuỗi tên (a.b.c), rồi tuỳ chọn (...) và { ... }. */
    private fun operandEnd(text: String, from: Int): Int {
        var i = from
        while (i < text.length && (isIdent(text[i]) || text[i] == '.')) i++
        while (i < text.length) {
            var j = i
            while (j < text.length && text[j] == ' ') j++
            i = when {
                j < text.length && text[j] == '(' -> matchForward(text, j, '(', ')')
                j < text.length && text[j] == '{' -> matchForward(text, j, '{', '}')
                else -> return i
            }
        }
        return i
    }

    /** Biểu thức chứa lời gọi bắt đầu ở `at` (`fadeIn(`...): kéo dài sang hai phía qua `+`, `togetherWith`, `with` và `.`. */
    fun expressionAround(text: String, at: Int): String {
        var start = at
        var end = operandEnd(text, at)
        // Sang phải.
        while (true) {
            var i = end
            while (i < text.length && text[i].isWhitespace()) i++
            val next = when {
                text.startsWith("togetherWith", i) -> i + "togetherWith".length
                text.startsWith("with", i) && (i + 4 >= text.length || !isIdent(text[i + 4])) -> i + 4
                text.startsWith("+", i) && !text.startsWith("++", i) -> i + 1
                text.startsWith(".", i) -> i + 1
                else -> break
            }
            var j = next
            while (j < text.length && text[j].isWhitespace()) j++
            end = operandEnd(text, j)
        }
        // Sang trái.
        while (true) {
            var i = start - 1
            while (i >= 0 && text[i].isWhitespace()) i--
            if (i < 0) break
            val operatorStart = when {
                text[i] == '+' && (i == 0 || text[i - 1] != '+') -> i
                text[i] == '.' -> i
                i >= 11 && text.startsWith("togetherWith", i - 11) -> i - 11
                i >= 3 && text.startsWith("with", i - 3) && (i < 4 || !isIdent(text[i - 4])) -> i - 3
                else -> break
            }
            var k = operatorStart - 1
            while (k >= 0 && text[k].isWhitespace()) k--
            if (k < 0) break
            var from = k
            while (from >= 0 && (text[from] == ')' || text[from] == '}')) {
                from = if (text[from] == ')') matchBackward(text, from, '(', ')') else matchBackward(text, from, '{', '}')
                from--
                while (from >= 0 && text[from] == ' ') from--
            }
            while (from >= 0 && (isIdent(text[from]) || text[from] == '.')) from--
            start = from + 1
        }
        return text.substring(start, end)
    }

    private fun lineOf(text: String, at: Int) = text.substring(0, at).count { it == '\n' } + 1

    fun scan(file: String, source: String): List<Finding> {
        val text = stripComments(source)
        val found = ArrayList<Finding>()
        for (m in fadeCall.findAll(text)) {
            if (m.range.first > 0 && (isIdent(text[m.range.first - 1]))) continue
            if (!geometry.containsMatchIn(expressionAround(text, m.range.first))) {
                found += Finding(file, lineOf(text, m.range.first), "${m.value.trim()} đứng một mình: ghép với slide / scale / expand / shrink")
            }
        }
        for (m in Regex("""\bCrossfade\s*\(""").findAll(text)) found += Finding(file, lineOf(text, m.range.first), "Crossfade là mờ chéo")
        for (m in Regex("""\bAnimatedContent\s*\(""").findAll(text)) {
            val open = text.indexOf('(', m.range.first)
            if (!text.substring(open, matchForward(text, open, '(', ')')).contains("transitionSpec")) {
                found += Finding(file, lineOf(text, m.range.first), "AnimatedContent không có transitionSpec: mặc định là mờ chéo")
            }
        }
        for (m in alphaModifier.findAll(text)) found += Finding(file, lineOf(text, m.range.first), "Modifier.alpha với giá trị động")
        for (m in Regex("""\bgraphicsLayer\s*\{""").findAll(text)) {
            val open = text.indexOf('{', m.range.first)
            val block = text.substring(open, matchForward(text, open, '{', '}'))
            val alphaSet = Regex("""\balpha\s*=\s*(?![0-9.]+f?\s*(;|\n|\}))""").containsMatchIn(block)
            if (alphaSet && !Regex("""\b(translation[XYZ]|scale[XY]|rotation[XYZ])\b""").containsMatchIn(block)) {
                found += Finding(file, lineOf(text, m.range.first), "graphicsLayer chỉ đổi alpha")
            }
        }
        for (m in animatedAlpha.findAll(text)) found += Finding(file, lineOf(text, m.range.first), "biến alpha chạy từ animate*AsState")
        return found
    }
}
