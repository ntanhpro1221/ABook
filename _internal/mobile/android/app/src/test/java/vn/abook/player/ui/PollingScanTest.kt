package vn.abook.player.ui

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PollingScanTest {
    private data class AllowedTicker(val file: String, val loop: String, val reason: String)
    private val allowedTickers = listOf(AllowedTicker(
        "src/main/java/vn/abook/player/ui/data/ForegroundRefresh.kt",
        """while (isActive) {
                clock.delay(2_000)
                refresh()
                ticks++
                if (ticks % 4 == 0) syncStreamed()
            }""",
        "Snapshot-only peer APIs: 2 s player / 8 s library refresh, cancelled below STARTED or when no remote plays. " +
            "ForegroundWorkTest covers injected time, PiP, idle, stop, destroy and in-flight cancellation.",
    ))

    @Test fun `native sources have no unconditional or timer polling loops`() {
        val roots = listOf(File("src/main/java/vn/abook/player/ui"), File("src/nativeUi"))
        roots.forEach { assertTrue("Missing native source root: $it", it.isDirectory) }
        val files = roots.flatMap { root -> root.walkTopDown().filter { it.extension in setOf("kt", "java") }.toList() }
        assertTrue("Unexpectedly small native UI scan: ${files.size}", files.size > 100)
        // Allow only the exact reviewed loop, not the whole file or other loops in its function.
        val findings = files.flatMap { PollingScan.scan(it.path, it.readText()) }
        val allowed = allowedTickers.map { ticker ->
            assertTrue("Ticker exception needs a reason", ticker.reason.isNotBlank())
            val source = File(ticker.file).readText().replace("\r\n", "\n")
            val offset = source.indexOf(ticker.loop)
            assertTrue("Stale ticker exception: ${ticker.file}", offset >= 0)
            assertEquals("Ticker exception must match exactly once", offset, source.lastIndexOf(ticker.loop))
            val line = source.take(offset).count { it == '\n' } + 1
            findings.single { it.file.replace('\\', '/') == ticker.file && it.line == line }
        }
        val unexpected = findings - allowed.toSet()
        assertEquals(unexpected.joinToString("\n") { "${it.file}:${it.line}: ${it.why}" }, emptyList<PollingScan.Finding>(), unexpected)
    }

    @Test fun `catches unconditional loops and multiline polling bodies`() {
        val cases = listOf(
            "while (true) { refresh(); delay(8000) }",
            "while(true) refresh()",
            "while (isActive) { refresh(); delay(20) }",
            "while (ready && nested(check()))\n    delay(20)",
            "while (active) { if (test()) { work() }; delay(50) }",
            "repeat(Int.MAX_VALUE) { delay(20); refresh() }",
            "for (i in sequence) { Thread.sleep(20) }",
            "do { delay(20) } while (active)",
            "LaunchedEffect(Unit) { while (playing) { withFrameNanos { sample() } } }",
        )
        cases.forEach { assertTrue("Missed: $it", PollingScan.scan("test.kt", it).isNotEmpty()) }
    }

    @Test fun `ignores literals comments finite work and one shot deadlines`() {
        val cases = listOf(
            "// while (true) { delay(20) }\nval s = \"while (true)\"",
            "/* outer /* while(true) {} */ delay(20) */ val c = '{'",
            "val s = \"\"\"while (true) { delay(20) }\"\"\"",
            "while (cursor.moveToNext()) { read() }; delay(20)",
            "while (low <= high) { search() }",
            "repeat(3) { work() }; delay(20)",
            "for (tab in Tab.entries) { visit(tab); withFrameNanos { } }",
            "LaunchedEffect(key) { delay(450); save() }",
        )
        cases.forEach { assertEquals(it, emptyList<PollingScan.Finding>(), PollingScan.scan("test.kt", it)) }
    }

    @Test fun `reports original line after multiline comments`() {
        val source = "/* ignore\nwhile(true) {}\n*/\nwhile (isActive) {\n delay(20)\n}"
        assertEquals(4, PollingScan.scan("x.kt", source).single().line)
    }
}
