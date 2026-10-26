package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật bo góc (chủ sách 26-10, "từng cái bo góc"): chỉ ba vai của docs/DESIGN.md 5.5 (Dim.radiusControl / radiusCover / radiusSheet, sinh vào
 * theme/Tokens.kt) + tròn (CircleShape, hay nửa chiều cao) - cùng bộ với bản web (ui/src/shared/radiusRules.test.ts). Số dp viết tay trong
 * RoundedCornerShape / CornerRadius lệch bản web mà không ai thấy, nên bị chặn ở mọi file ngoài theme/.
 */
class RadiusRulesTest {
    private val root = File("src/main/java/vn/abook/player/ui")

    private fun sources() = root.walkTopDown().filter { it.isFile && it.extension == "kt" && !it.relativeTo(root).invariantSeparatorsPath.startsWith("theme/") }
        .map { it.relativeTo(root).invariantSeparatorsPath to it.readLines() }

    private val shapeCall = Regex("""RoundedCornerShape\(([^)]*)\)""")
    private val allowedArg = Regex("""\s+|,|=|\b(top|bottom)(Start|End)\b|\bDim\.radius(Control|Cover|Sheet)\b""")
    private val cornerCall = Regex("""\bCornerRadius\(([^)]*)\)""")
    private val radiusValue = Regex("""\b(corner|radius)\w*\s*=.*\d\s*\.dp""", RegexOption.IGNORE_CASE)

    /** Dòng vi phạm của một file (đã đọc thành dòng), dạng "dòng N: nội dung". */
    private fun offences(lines: List<String>): List<String> = lines.mapIndexedNotNull { index, line ->
        val bad = shapeCall.findAll(line).any { allowedArg.replace(it.groupValues[1], "").isNotEmpty() } ||
            cornerCall.findAll(line).any { it.groupValues[1].contains(".dp") } || radiusValue.containsMatchIn(line)
        if (bad) "dòng ${index + 1}: ${line.trim()}" else null
    }

    @Test
    fun cornersUseOnlyTheDesignRolesOrAPill() {
        val offenders = sources().flatMap { (path, lines) -> offences(lines).map { "$path $it" } }.toList()
        assertTrue("Bo góc viết tay ngoài theme/ (dùng Dim.radiusControl / radiusCover / radiusSheet hoặc CircleShape): $offenders", offenders.isEmpty())
    }

    @Test
    fun theRuleCatchesLiteralsAndLetsRolesThrough() {
        assertEquals(1, offences(listOf("Modifier.clip(RoundedCornerShape(4.dp))")).size)
        assertEquals(1, offences(listOf("Modifier.clip(RoundedCornerShape(topStart = 20.dp, topEnd = Dim.radiusSheet))")).size)
        assertEquals(1, offences(listOf("val corner = 18.dp.toPx()")).size)
        assertEquals(1, offences(listOf("drawRoundRect(c, cornerRadius = CornerRadius(8.dp.toPx()))")).size)
        assertEquals(1, offences(listOf("RoundedCornerShape(50)")).size)
        assertEquals(0, offences(listOf(
            "Modifier.clip(RoundedCornerShape(Dim.radiusControl))",
            "Modifier.clip(RoundedCornerShape(topStart = Dim.radiusSheet, topEnd = Dim.radiusSheet))",
            "drawRoundRect(c, cornerRadius = CornerRadius(size.height / 2))",
            "val corner = size.height / 2",
            "Modifier.clip(CircleShape)",
        )).size)
    }
}
