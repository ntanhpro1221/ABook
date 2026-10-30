package vn.abook.player.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Luật chữ giao diện (chủ sách 26-10, "từng cái chữ"), cùng bộ với bản web (scripts/ui_parity.py, tests/test_ui_parity.py):
 * dấu thanh KIỂU CŨ (hoà, khoá, xoá, tuỳ, thuý - không hòa, khoá, xóa, tùy, thúy; "quý" giữ nguyên) và nhãn / trạng thái / nút không tận cùng `...`
 * (dấu `…` đã bị TextCutScanTest chặn ở mọi chỗ). Quét chuỗi trong mã giao diện VÀ trong lõi (các file .kt của vn/abook/player ngoài ui/: lỗi, thông báo người nghe đọc); chữ giả của
 * thư viện mẫu (có trích sách thật) và vài chuỗi không phải chữ giao diện (so khớp chữ trong truyện, mã giọng, câu gửi cho giọng đọc) thì bỏ qua.
 */
class CopyRulesTest {
    private val core = File("src/main/java/vn/abook/player")
    private val root = File(core, "ui")
    private val sampleText = setOf("data/DemoLibrary.kt", "data/DemoPlayback.kt", "nowplaying/FakeNowPlayingModel.kt")

    /** Lõi: file có chuỗi không phải chữ giao diện (đổi dấu thanh sẽ làm hỏng việc khớp truyện / mã giọng / lời gửi giọng đọc). */
    private val notUiText = setOf("readaloud/VoiceGain.kt", "vieneu/VieneuUnits.kt", "readaloud/FptTts.kt")
    /** Chiếm hữu (`++`, `*+`): dòng dài của lõi không làm tràn ngăn xếp của regex. */
    private val literal = Regex(""""(?:[^"\\\n]++|\\.)*+"""")
    private val newTone = Regex("[òóỏõọ][ae]|[ùúủũụ]y|[ÒÓỎÕỌ][AEae]|[ÙÚỦŨỤ][Yy]")
    private val dotsAtEnd = Regex("""[\p{L}\p{N}]\.\.\.$""")

    /** Chuỗi của một file (đã đọc thành dòng) vi phạm luật, dạng "dòng N: chuỗi". Dòng chú thích bị bỏ. */
    private fun offences(lines: List<String>): List<String> = lines.flatMapIndexed { index, raw ->
        val trimmed = raw.trimStart()
        if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*") || "SPECIAL_SECTION" in raw) emptyList()
        else literal.findAll(raw.substringBefore(" // ")).map { it.value.trim('"') }
            .filter { newTone.containsMatchIn(it) || dotsAtEnd.containsMatchIn(it) }
            .map { "dòng ${index + 1}: $it" }.toList()
    }

    @Test
    fun uiStringsUseTheOldToneMarksAndNoTrailingDots() {
        assertTrue("không thấy ${root.absolutePath}", root.isDirectory)
        val files = root.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .filter { it.relativeTo(root).invariantSeparatorsPath !in sampleText }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 20)
        val offenders = files.flatMap { file -> offences(file.readLines()).map { "${file.relativeTo(root).invariantSeparatorsPath} $it" } }
        assertTrue("Chữ giao diện sai luật (dấu thanh kiểu mới hoặc tận cùng ...): $offenders", offenders.isEmpty())
    }

    @Test
    fun coreStringsUseTheOldToneMarksAndNoTrailingDots() {
        assertTrue("không thấy ${core.absolutePath}", core.isDirectory)
        val files = core.walkTopDown().filter { it.isFile && it.extension == "kt" }
            .filter { !it.relativeTo(core).invariantSeparatorsPath.startsWith("ui/") && it.relativeTo(core).invariantSeparatorsPath !in notUiText }.toList()
        assertTrue("quét được quá ít file: ${files.size}", files.size >= 100)
        val offenders = files.flatMap { file -> offences(file.readLines()).map { "${file.relativeTo(core).invariantSeparatorsPath} $it" } }
        assertTrue("Chữ của lõi sai luật (dấu thanh kiểu mới hoặc tận cùng ...): $offenders", offenders.isEmpty())
    }

    @Test
    fun theRuleCatchesNewStyleAndLetsOldStyleThrough() {
        assertEquals(1, offences(listOf("""BasicText("Khóa giọng")""")).size)
        assertEquals(1, offences(listOf("""BasicText("Hòa âm")""")).size)
        assertEquals(1, offences(listOf("""BasicText("Thúy Kiều")""")).size)
        assertEquals(1, offences(listOf("""BasicText("Tùy chọn")""")).size)
        assertEquals(1, offences(listOf("""BasicText("Đang gửi...")""")).size)
        assertEquals(0, offences(listOf("""BasicText("Khoá giọng trực tuyến")""", """BasicText("Tuỳ chọn")""", """BasicText("Quý khách")""")).size)
        assertEquals(0, offences(listOf("""// "Khóa" kiểu mới trong chú thích""", """BasicText("Xong")""")).size)
    }

    // ---- "Không X được": câu cụt (soát 31-10) - nói "Chưa X được" kèm việc nên làm ----

    private val cutSentence = Regex("""Không [^"]{1,30} được""")

    private fun cutSentences(lines: List<String>): List<String> = lines.flatMapIndexed { index, raw ->
        val trimmed = raw.trimStart()
        if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*") || "AppLog." in raw) emptyList()
        else literal.findAll(raw.substringBefore(" // ")).map { it.value.trim('"') }.filter { cutSentence.containsMatchIn(it) }.map { "dòng ${index + 1}: $it" }.toList()
    }

    @Test
    fun noUiStringIsAClippedKhongXDuoc() {
        val offenders = (root.walkTopDown() + core.walkTopDown()).filter { it.isFile && it.extension == "kt" }
            .filter { it.relativeTo(root).invariantSeparatorsPath !in sampleText && it.relativeTo(core).invariantSeparatorsPath !in notUiText }
            .flatMap { file -> cutSentences(file.readLines()).map { "${file.name} $it" } }.toList()
        assertTrue("Câu cụt 'Không … được' (dùng 'Chưa … được' + việc nên làm): $offenders", offenders.isEmpty())
    }

    @Test
    fun theClippedSentenceRuleCatchesAndLetsThrough() {
        assertEquals(1, cutSentences(listOf("""BasicText("Không mở được sách")""")).size)
        assertEquals(0, cutSentences(listOf("""BasicText("Chưa mở được sách")""", """BasicText("Không có sách")""", """// "Không mở được" cũ""", """AppLog.w("Không mở được")""")).size)
    }
}
