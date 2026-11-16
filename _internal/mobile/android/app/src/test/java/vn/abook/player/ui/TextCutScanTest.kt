package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật chủ sách: không bao giờ cắt chữ của người dùng (tên sách, tên chương, tác giả...) - không "…", không cắt im lặng bằng maxLines + Clip,
 * không mờ đuôi. Chữ dài thì xuống dòng (hoặc thu cỡ chữ khi là chữ vẽ trên bìa). Máy dò này quét mọi nguồn giao diện native; chỗ cắt có chủ ý thật
 * (không phải chữ người dùng) phải ghi `// cắt-có-chủ-ý: <lý do>` ngay trên dòng ấy.
 */
class TextCutScanTest {
    data class Finding(val file: String, val line: Int, val why: String)

    private val nameText = Regex("""\b(?:device|peer|target|remote|sharer|session|profile|computer|phone|preset|lib|voice)\??\.(?:name|displayName|label)\b|\b(?:deviceName|phoneName|profileName|machineName|displayName)\b|\bnames(?:\[|\.current)|\bfound\.shown\b""")

    /** Name-bearing text cannot use the generic exemption: a shortened mini label needs its own full-name surface. */
    fun scanNames(file: String, source: String): List<Finding> {
        val code = source.replace(Regex("""(?s)/\*.*?\*/|//[^\n]*""")) { match ->
            match.value.map { if (it == '\n' || it == '\r') it else ' ' }.joinToString("")
        }
        return Regex("""\b(?:BasicText|Text)\s*\(""").findAll(code).mapNotNull { start ->
            var depth = 1
            var index = start.range.last + 1
            var quoted = false
            var escaped = false
            while (index < code.length && depth > 0) {
                val ch = code[index++]
                if (quoted) {
                    if (escaped) escaped = false else if (ch == '\\') escaped = true else if (ch == '"') quoted = false
                } else when (ch) {
                    '"' -> quoted = true
                    '(' -> depth++
                    ')' -> depth--
                }
            }
            val call = code.substring(start.range.first, index)
            if (nameText.containsMatchIn(call) && Regex("""\bmaxLines\s*=|TextOverflow\.(?:Ellipsis|Clip|StartEllipsis|MiddleEllipsis)|\bsoftWrap\s*=\s*false|\.(?:take|takeLast|drop|dropLast|substring|slice)\s*\(""").containsMatchIn(call))
                Finding(file, source.take(start.range.first).count { it == '\n' } + 1, "tên thiết bị hoặc hồ sơ phải đọc trọn") else null
        }.toList()
    }

    private val rules = listOf(
        Regex("""\bmaxLines\s*=""") to "maxLines giới hạn số dòng - chữ dài sẽ bị cắt",
        Regex("""TextOverflow\.(Ellipsis|Clip|StartEllipsis|MiddleEllipsis)""") to "TextOverflow cắt chữ",
        Regex("…") to "dấu … trong mã",
        Regex("""\.endFade\b|horizontalGradient\(listOf\([^)]*Transparent\)[^)]*\)[^\n]*DstIn""") to "mờ đuôi chữ",
    )

    fun scan(file: String, source: String): List<Finding> {
        val lines = source.lines()
        return lines.flatMapIndexed { index, raw ->
            val code = raw.substringBefore("//").let { if (raw.trimStart().startsWith("*") || raw.trimStart().startsWith("/*")) "" else it }
            val exempt = raw.contains("cắt-có-chủ-ý:") || (index > 0 && lines[index - 1].contains("cắt-có-chủ-ý:"))
            if (exempt) emptyList() else rules.filter { (re, _) -> re.containsMatchIn(code) }.map { (_, why) -> Finding(file, index + 1, why) }
        }
    }

    @Test
    fun `native ui never cuts user text`() {
        val dir = File("src/main/java/vn/abook/player/ui")
        assertTrue("không thấy ${dir.absolutePath}", dir.isDirectory)
        val files = dir.walkTopDown().filter { it.extension == "kt" }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 8)
        val findings = files.flatMap { scan(it.name, it.readText()) }
        assertEquals(findings.joinToString("\n") { "${it.file}:${it.line} ${it.why}" }, emptyList<Finding>(), findings)
    }

    @Test
    fun `device and profile names cannot hide clipping behind a generic exemption`() {
        val dir = File("src/main/java/vn/abook/player")
        assertTrue("không thấy ${dir.absolutePath}", dir.isDirectory)
        val findings = dir.walkTopDown().filter { it.extension == "kt" }.flatMap { scanNames(it.relativeTo(dir).path, it.readText()) }.toList()
        assertEquals(findings.joinToString("\n") { "${it.file}:${it.line} ${it.why}" }, emptyList<Finding>(), findings)
    }

    @Test
    fun `name clipping is detected across multiline calls and exemptions`() {
        for (name in listOf("device.name", "peer.name", "target.name", "remote.name", "sharer.name", "session.name", "profile.label", "preset.name", "lib.name", "voice.name", "phoneName", "deviceName", "names[0]", "names.current", "found.shown")) {
            assertEquals(name, 1, scanNames("t.kt", "// cắt-có-chủ-ý: fixed strip\nBasicText(S.label($name),\n maxLines = 1)").size)
            assertEquals(name, 1, scanNames("t.kt", "BasicText($name, overflow = TextOverflow.Ellipsis)").size)
            assertEquals(name, 1, scanNames("t.kt", "BasicText($name, softWrap = false)").size)
            assertEquals(name, 1, scanNames("t.kt", "BasicText($name.take(20))").size)
            assertEquals(name, 0, scanNames("t.kt", "BasicText($name, autoSize = OneLineFit.of(style))").size)
        }
        assertEquals(0, scanNames("t.kt", "// BasicText(device.name, maxLines = 1)").size)
        assertEquals(4, scanNames("t.kt", "/* a\n b\n */\nBasicText(device.name, maxLines = 1)").single().line)
    }

    @Test
    fun `cuts are caught and the exemption works`() {
        assertEquals(1, scan("t.kt", """BasicText(title, maxLines = 1)""").size)
        assertEquals(1, scan("t.kt", """BasicText(title, overflow = TextOverflow.Ellipsis)""").size)
        assertEquals(1, scan("t.kt", "val s = title.take(20) + \"…\"").size)
        assertEquals(0, scan("t.kt", "// cắt-có-chủ-ý: số giờ cố định 5 ký tự\nBasicText(clock, maxLines = 1)").size)
        assertEquals(0, scan("t.kt", "// maxLines = 1 không dùng nữa").size)
        assertEquals(0, scan("t.kt", """BasicText(title, autoSize = TextAutoSize.StepBased())""").size)
    }
}
