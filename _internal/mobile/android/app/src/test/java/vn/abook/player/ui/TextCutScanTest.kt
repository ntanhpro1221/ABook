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

    /** Chữ của sách / người dùng làm đối số đầu của ô chữ (tên sách, tên chương, tác giả, "· chương" của nút chính...). */
    private val bookText = Regex("""\b(?:title|fullTitle|chapterTitle|bookTitle|author|subtitle|displayTitle|sub)\b""")
    private val cutArgs = Regex("""\bmaxLines\s*=|TextOverflow\.(?:Ellipsis|Clip|StartEllipsis|MiddleEllipsis)|\bsoftWrap\s*=\s*false|\.(?:take|takeLast|drop|dropLast|substring)\s*\(""")

    /**
     * Chỗ cắt chữ sách còn giữ, mỗi chỗ một lý do (left174 result.md). Khoá là "<file>:<đối số đầu>"; chỗ mới phải qua OneLineFit hay xuống dòng,
     * không được thêm vào đây chỉ để qua test.
     */
    private val keptBookCuts = mapOf(
        "LibraryScreen.kt:title" to "chủ sách 15-11: ô thư viện cùng hàng cao bằng nhau, tên đúng 2 dòng (web TileName line-clamp-2 cùng quyết định); tên đầy đủ ở trang sách",
        "LibraryScreen.kt:sub" to "dòng tình trạng do app ghép (tiến độ, số chương) - không phải chữ sách; tác giả ở dòng riêng qua OneLineFit",
        "TrackRow.kt:track.title.ifEmpty { track.link.substringAfterLast('/') }" to "chủ sách: tên bài nhạc tối đa 2 dòng trong danh sách nhạc; tấm chi tiết bài hiện trọn",
    )

    /** Ô chữ (BasicText/Text/ClockLabel/WrapText) có chữ sách ở đối số đầu mà cắt (maxLines, Ellipsis, softWrap=false, take...) - miễn trừ chung không che được. */
    fun scanBookText(file: String, source: String): List<Finding> {
        val code = source.replace(Regex("""(?s)/\*.*?\*/|//[^\n]*""")) { match ->
            match.value.map { if (it == '\n' || it == '\r') it else ' ' }.joinToString("")
        }
        return Regex("""\b(?:BasicText|Text|ClockLabel|WrapText)\s*\(""").findAll(code).mapNotNull { start ->
            var depth = 1
            var index = start.range.last + 1
            var quoted = false
            var escaped = false
            var firstEnd = -1
            while (index < code.length && depth > 0) {
                val ch = code[index++]
                if (quoted) {
                    if (escaped) escaped = false else if (ch == '\\') escaped = true else if (ch == '"') quoted = false
                } else when (ch) {
                    '"' -> quoted = true
                    '(', '{' -> depth++
                    ')', '}' -> { depth--; if (depth == 0 && firstEnd < 0) firstEnd = index - 1 }
                    ',' -> if (depth == 1 && firstEnd < 0) firstEnd = index - 1
                }
            }
            val call = code.substring(start.range.first, index)
            val first = code.substring(start.range.last + 1, if (firstEnd < 0) index else firstEnd).trim()
            if (bookText.containsMatchIn(first) && cutArgs.containsMatchIn(call) && "$file:$first" !in keptBookCuts)
                Finding(file, source.take(start.range.first).count { it == '\n' } + 1, "chữ sách bị cắt ($first): dùng OneLineFit hay xuống dòng") else null
        }.toList()
    }

    @Test
    fun `book and user text is never cut, even behind an exemption`() {
        val dir = File("src/main/java/vn/abook/player")
        assertTrue("không thấy ${dir.absolutePath}", dir.isDirectory)
        val files = dir.walkTopDown().filter { it.extension == "kt" }.toList()
        val findings = files.flatMap { scanBookText(it.name, it.readText()) }
        assertEquals(findings.joinToString("\n") { "${it.file}:${it.line} ${it.why}" }, emptyList<Finding>(), findings)
        // Mỗi chỗ giữ phải còn thật (chỗ đã sửa thì xoá khỏi danh sách)
        val sources = files.associate { it.name to it.readText() }
        for (key in keptBookCuts.keys) {
            val (file, expression) = key.split(":", limit = 2)
            assertTrue("chỗ giữ không còn: $key", sources[file]?.contains(expression) == true)
        }
    }

    @Test
    fun `book text cuts are caught, OneLineFit passes`() {
        // Lỗi 0.4.173: "Nghe tiếp · Chương 3: Một cái t…" - có miễn trừ chung ngay trên dòng
        val old = "// cắt-có-chủ-ý: nút một dòng\nBasicText(\"\\u00a0·\\u00a0\" + sub, Modifier.weight(1f), style = ink, maxLines = 1, overflow = TextOverflow.Ellipsis)"
        assertEquals(1, scanBookText("t.kt", old).size)
        assertEquals(1, scanBookText("t.kt", "BasicText(chapter.title,\n maxLines = 1)").size)
        assertEquals(1, scanBookText("t.kt", "BasicText(book.author, softWrap = false)").size)
        assertEquals(1, scanBookText("t.kt", "Text(fullTitle.take(30))").size)
        assertEquals(0, scanBookText("t.kt", "BasicText(\"\\u00a0·\\u00a0\" + sub, style = ink, autoSize = OneLineFit.of(ink))").size)
        assertEquals(0, scanBookText("t.kt", "BasicText(clock, maxLines = 1)").size)
        assertEquals(0, scanBookText("LibraryScreen.kt", "BasicText(title, maxLines = 2)").size)
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
