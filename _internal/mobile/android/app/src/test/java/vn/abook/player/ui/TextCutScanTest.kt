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
    fun `cuts are caught and the exemption works`() {
        assertEquals(1, scan("t.kt", """BasicText(title, maxLines = 1)""").size)
        assertEquals(1, scan("t.kt", """BasicText(title, overflow = TextOverflow.Ellipsis)""").size)
        assertEquals(1, scan("t.kt", "val s = title.take(20) + \"…\"").size)
        assertEquals(0, scan("t.kt", "// cắt-có-chủ-ý: số giờ cố định 5 ký tự\nBasicText(clock, maxLines = 1)").size)
        assertEquals(0, scan("t.kt", "// maxLines = 1 không dùng nữa").size)
        assertEquals(0, scan("t.kt", """BasicText(title, autoSize = TextAutoSize.StepBased())""").size)
    }
}
