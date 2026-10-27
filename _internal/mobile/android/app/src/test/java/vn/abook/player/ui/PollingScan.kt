package vn.abook.player.ui

/** Small lexical guard: balanced conditions/bodies, with comments and literals masked at their original offsets. */
internal object PollingScan {
    data class Finding(val file: String, val line: Int, val why: String)

    fun scan(file: String, source: String): List<Finding> {
        val code = mask(source)
        val findings = mutableListOf<Finding>()
        fun report(at: Int, why: String) {
            findings += Finding(file, source.take(at).count { it == '\n' } + 1, why)
        }
        for (match in Regex("""\b(while|repeat|for)\s*\(""").findAll(code)) {
            val start = code.indexOf('(', match.range.first)
            val end = close(code, start, '(', ')')
            val condition = code.substring(start + 1, end).trim()
            val body = body(code, end + 1)
            if (match.groupValues[1] == "while" && condition == "true") report(match.range.first, "unconditional loop")
            else if (waits(body, frames = match.groupValues[1] != "for")) report(match.range.first, "timer/frame wait inside a loop")
        }
        for (match in Regex("""\bdo\s*\{""").findAll(code)) {
            val start = code.indexOf('{', match.range.first)
            if (waits(code.substring(start, close(code, start, '{', '}') + 1))) report(match.range.first, "timer/frame wait inside do/while")
        }
        return findings.distinct()
    }

    private fun waits(body: String, frames: Boolean = true): Boolean {
        val calls = if (frames) "delay|sleep|withFrameNanos|withFrameMillis|awaitFrame" else "delay|sleep"
        return Regex("\\b($calls)\\s*[({]").containsMatchIn(body)
    }

    private fun body(code: String, after: Int): String {
        val start = (after until code.length).firstOrNull { !code[it].isWhitespace() } ?: return ""
        if (code[start] == '{') return code.substring(start, close(code, start, '{', '}') + 1)
        val end = (start until code.length).firstOrNull { code[it] == '\n' || code[it] == ';' } ?: code.length
        return code.substring(start, end)
    }

    private fun close(code: String, start: Int, left: Char, right: Char): Int {
        var depth = 0
        for (index in start until code.length) {
            if (code[index] == left) depth++
            if (code[index] == right) {
                depth--
                if (depth == 0) return index
            }
        }
        return code.lastIndex
    }

    private fun mask(source: String): String {
        val out = source.toCharArray()
        fun blank(from: Int, to: Int) { for (i in from until to) if (out[i] != '\n') out[i] = ' ' }
        var i = 0
        while (i < source.length) {
            val start = i
            when {
                source.startsWith("//", i) -> {
                    i = source.indexOf('\n', i).let { if (it < 0) source.length else it }
                    blank(start, i)
                }
                source.startsWith("/*", i) -> {
                    var depth = 1
                    i += 2
                    while (i < source.length && depth > 0) {
                        when {
                            source.startsWith("/*", i) -> { depth++; i += 2 }
                            source.startsWith("*/", i) -> { depth--; i += 2 }
                            else -> i++
                        }
                    }
                    blank(start, i)
                }
                source.startsWith("\"\"\"", i) -> {
                    i = source.indexOf("\"\"\"", i + 3).let { if (it < 0) source.length else it + 3 }
                    blank(start, i)
                }
                source[i] == '"' || source[i] == '\'' -> {
                    val quote = source[i++]
                    while (i < source.length) {
                        if (source[i] == '\\') i = (i + 2).coerceAtMost(source.length)
                        else if (source[i++] == quote) break
                    }
                    blank(start, i)
                }
                else -> i++
            }
        }
        return String(out)
    }
}
