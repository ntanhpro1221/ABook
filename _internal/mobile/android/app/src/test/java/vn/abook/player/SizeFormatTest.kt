package vn.abook.player

import java.io.File
import org.junit.Assert.*
import org.junit.Test

class SizeFormatTest {
    @Test fun matchesAllSeventeenQtAndWebValues() {
        val m = 1024L * 1024; val g = 1024 * m
        val cases = listOf(0L to "1\u00a0KB", 500L to "1\u00a0KB", 51200L to "50\u00a0KB", 104857L to "102\u00a0KB", 104858L to "0,1\u00a0MB",
            5000000L to "4,8\u00a0MB", 10443817L to "10\u00a0MB", 10*m to "10\u00a0MB", 12000000L to "11\u00a0MB", 820*m to "820\u00a0MB",
            Math.round(999.6*m) to "1.000\u00a0MB", g-1 to "1.024\u00a0MB", g to "1\u00a0GB", 1116691497L to "1\u00a0GB",
            3435973837L to "3,2\u00a0GB", 5200000000L to "4,8\u00a0GB", 1500*g to "1.500\u00a0GB")
        assertEquals(17, cases.size)
        for ((bytes, text) in cases) assertEquals("$bytes bytes", text, formatSize(bytes))
    }

    @Test fun everyUserFacingSizeUsesTheSharedFormatter() {
        val root = File("src/main/java/vn/abook/player")
        assertTrue(root.isDirectory)
        val other = root.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name != "SizeFormat.kt" }.filter {
            val source = it.readText()
            Regex("fun\\s+(?:size|megabytes|gigabytes)\\(bytes:").containsMatchIn(source) ||
                Regex("\\$\\{[^\\n]*} (?:KB|MB|GB)\"").containsMatchIn(source) ||
                Regex("%[.0-9]*f (?:MB|GB)").containsMatchIn(source)
        }.map { it.relativeTo(root).path }.toList()
        assertEquals("Separate size formatter found", emptyList<String>(), other)
    }
}
