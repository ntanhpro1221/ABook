package vn.abook.player.ui

import java.io.File
import org.junit.Assert.*
import org.junit.Test

/** Source guard for self-updating text. Add new display formatters here when introducing a counter. */
class TickingValuePolicyTest {
    private val formatters = listOf(
        "PlayerLabels.time", "PlayerLabels.sleep", "PlayerText.percent", "PlayerText.bookProgress",
        "Fmt.clock", "Fmt.length", "Fmt.lengthUp", "Fmt.number", "formatSize",
        "BookPage.progressLine", "ListenLogic.progressText", "ProductionText.upcoming",
        "ExportText.progress", "ExportText.spokenDuration", "ExportText.menuHint",
        "PrepareText.spokenDuration", "PrepareText.label", "BookPage.percent", "BookPage.statusLine",
        "BookSearch.status", "DeviceText.clock", "DeviceText.seen",
    )
    private val moving = Regex("\\b(RollingLabel|AnimatedContent|Crossfade|MovingTextAction|SheetPages|animate\\w*AsState)\\s*\\(")
    private val formatter = Regex("\\b(?:" + formatters.joinToString("|") { Regex.escape(it) } + ")\\s*\\(")

    // Keep string templates (where counters live), discard comments so examples cannot trigger the scan.
    private fun clean(text: String) = text.replace(Regex("/\\*[\\s\\S]*?\\*/|//[^\\n]*")) { " ".repeat(it.value.length) }

    /** Read one argument/initializer, balancing nested calls and templates; commas/newlines inside them are safe. */
    private fun expression(text: String, start: Int, initializer: Boolean = false): String {
        var depth = 0
        var quoted = false
        var escaped = false
        var end = start
        while (end < text.length) {
            val c = text[end]
            if (quoted) {
                if (!escaped && c == '"') quoted = false
                escaped = !escaped && c == '\\'
            } else {
                if (depth == 0 && (c == ',' || c == ')' || (initializer && c == '\n'))) break
                when (c) {
                    '"' -> quoted = true
                    '(', '[', '{' -> depth++
                    ')', ']', '}' -> { if (depth == 0) break; depth-- }
                }
            }
            end++
        }
        return text.substring(start, end)
    }

    internal fun violations(source: String): List<Int> {
        val text = clean(source)
        val definitions = Regex("\\b(?:val|var)\\s+(\\w+)(?:\\s*:[^=\\n]+)?\\s*(?:=|by)\\s*").findAll(text).toList()
        fun ticking(value: String, before: Int, seen: Set<String> = emptySet()): Boolean {
            if (formatter.containsMatchIn(value)) return true
            if (Regex("\\$\\{?[^\"\\n]*(?:percent|secondsLeft|elapsed|remaining|done|total|count)[^\"\\n]*", RegexOption.IGNORE_CASE).containsMatchIn(value)) return true
            return Regex("\\b[A-Za-z_]\\w*\\b").findAll(value).any { token ->
                val name = token.value
                if (name in seen) false else {
                    val definition = definitions.lastOrNull { it.range.first < before && it.groupValues[1] == name }
                    definition != null && ticking(expression(text, definition.range.last + 1, true), definition.range.first, seen + name)
                }
            }
        }
        return moving.findAll(text).filter { call ->
            var start = call.range.last + 1
            var position = 0
            var found = false
            while (start < text.length) {
                val argument = expression(text, start)
                val named = Regex("^\\s*(\\w+)\\s*=\\s*(?!=)").find(argument)?.groupValues?.get(1)
                if ((named in listOf("text", "label", "targetState", "value") || (position == 0 && named == null)) && ticking(argument, call.range.first)) found = true
                start += argument.length
                if (start >= text.length || text[start] != ',') break
                start++
                position++
            }
            found
        }.map { text.take(it.range.first).count { c -> c == '\n' } + 1 }.toList()
    }

    @Test fun mainSourcesNeverAnimateTickingText() {
        val root = File("src/main/java")
        assertTrue("Run from Android app project: $root", root.isDirectory)
        val offenders = root.walkTopDown().filter { it.extension == "kt" }.flatMap { file ->
            violations(file.readText()).map { "${file.path}:$it" }
        }.toList()
        assertEquals("Ticking values must use ClockLabel or a tnum TextStyle, never a content animation", emptyList<String>(), offenders)
    }

    @Test fun catchesMultilineAliasesTemplatesAndEachMotionApi() {
        for (api in listOf("RollingLabel", "AnimatedContent", "Crossfade", "MovingTextAction")) {
            assertEquals(api, 1, violations("val clock =\n PlayerLabels.time(123)\nval label = clock\n$api(\n label,\n)").size)
        }
        assertEquals(1, violations("RollingLabel(\"\${'$'}{state.percent}%\")").size)
        assertEquals(1, violations("AnimatedContent(modifier = Modifier, targetState = Fmt.clock(time)) { Text(it) }").size)
        assertEquals(1, violations("MovingTextAction(onClick = {}, label = ExportText.progress(event), tag = \"export\")").size)
        assertTrue(violations("RollingLabel(PlayerLabels.rate(rate))\nClockLabel(PlayerLabels.time(ms))").isEmpty())
    }
}
