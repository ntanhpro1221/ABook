package vn.abook.player

import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * ICU của Android văng với `(?U)` / UNICODE_CHARACTER_CLASS, còn JVM của bài thử thì chạy êm - nên bài thử thường không bao giờ bắt được
 * (03-10 thêm sách văng; 26-10 bấm "Đọc theo" ở bản native văng trên OPPO). Quét mọi file Kotlin của app: không dòng mã nào dùng chúng,
 * trừ chỗ đã chặn theo máy ảo (BookImport: chỉ bật khi không phải Dalvik).
 */
class AndroidRegexRulesTest {
    private val root = File("src/main/java/vn/abook/player")
    private val guarded = setOf("BookImport.kt")

    @Test
    fun noUnicodeCharacterClassFlagInAppCode() {
        val bad = Regex("""\(\?[a-zA-Z]*U[a-zA-Z]*\)|UNICODE_CHARACTER_CLASS""")
        val offenders = root.walkTopDown().filter { it.isFile && it.extension == "kt" && it.name !in guarded }.flatMap { file ->
            file.readLines().withIndex().filter { (_, line) ->
                val code = line.substringBefore("//").trimStart()
                !code.startsWith("*") && !code.startsWith("/*") && bad.containsMatchIn(code)
            }.map { (index, line) -> "${file.relativeTo(root).invariantSeparatorsPath}:${index + 1}: ${line.trim()}" }
        }.toList()
        assertTrue("(?U) / UNICODE_CHARACTER_CLASS văng trên Android - viết rõ lớp ký tự:\n${offenders.joinToString("\n")}", offenders.isEmpty())
    }
}
