package vn.abook.player.readaloud

import java.text.Normalizer

/**
 * Các đoạn của một chương chỉ-có-chữ - bản Kotlin CỦA `paragraphsOf` trong ui/src/listen/textScript.ts: màn đọc (JS) và lõi đọc to (native) phải chia
 * chương ra CÙNG các đoạn, vì mỗi đoạn là một đoạn âm thanh và `script()` trả mốc thời gian theo thứ tự đoạn. Đổi một bên là đổi cả hai bên (cùng bộ ví dụ
 * trong ParagraphsTest = textScript.test.ts).
 *
 * `\s` của JS gồm cả U+00A0 và U+FEFF mà `\s` của Java không có; `\s` của Java (kiểu Unicode) lại có thêm U+0085 mà JS không có - nên viết rõ tập ký tự.
 */
object Paragraphs {
    /** Đúng tập của `\s` trong JavaScript. */
    internal const val JS_SPACE = "\\t\\n\\u000B\\f\\r \\u00A0\\u1680\\u2000-\\u200A\\u2028\\u2029\\u202F\\u205F\\u3000\\uFEFF"
    private val SPACES = Regex("[$JS_SPACE]+")
    private val NEWLINES = Regex("\r\n?")
    /** `\n[ \t<nbsp>]*\n` của textScript.ts (ký tự thứ ba trong ngoặc là U+00A0). */
    private val BLANK_LINE = Regex("\n[ \t ]*\n")

    private val NOTE_MARKER = Regex("\\[[$JS_SPACE]*note[0-9]+[$JS_SPACE]*]", RegexOption.IGNORE_CASE)

    /**
     * Bỏ mã chú thích của trang web chép lẫn vào chữ ("[note54360]") - không phải chữ truyện, đọc lên là đọc "note năm bốn ba sáu không". Đúng mẫu của máy tính
     * (`text_processing.INLINE_REFERENCE_MARKER_PATTERN`, bước chuẩn hoá trước khi tách câu) và của `withoutNoteMarkers` trong textScript.ts; "[Note]" không số, "[1]" giữ nguyên.
     */
    fun withoutNoteMarkers(text: String): String = text.replace(NOTE_MARKER, "")

    /** Gộp mọi khoảng trắng thành một dấu cách rồi cắt hai đầu (`squeeze` của textScript.ts; `trim()` của JS cắt đúng tập `\s`). */
    fun squeeze(text: String): String = text.replace(SPACES, " ").trim { it in JS_SPACE_CHARS }

    private val JS_SPACE_CHARS: Set<Char> = buildSet {
        "\t\n\u000B\u000C\r       　﻿".forEach { add(it) }
        for (c in ' '..' ') add(c)
    }

    /**
     * File có dòng trống ngăn đoạn: đoạn là phần giữa hai dòng trống, xuống dòng trong đoạn là dòng bị bẻ của máy dàn trang (nối bằng dấu cách).
     * File KHÔNG có dòng trống nào (TXT mỗi dòng một đoạn): mỗi dòng là một đoạn.
     */
    fun of(text: String): List<String> = split(text).map { it.text }

    /**
     * Như [of], kèm cờ dòng ngăn cảnh (`splitParagraphs` của textScript.ts). Luật "đứng riêng" của text_processing lấy đoạn = giữa hai dòng trống, nên file không có
     * dòng trống là MỘT đoạn: chỉ khi cả file có đúng một dòng thì dòng ấy mới đứng riêng.
     */
    fun split(text: String): List<Paragraph> {
        val clean = withoutNoteMarkers(text).replace(NEWLINES, "\n")
        if (BLANK_LINE.containsMatchIn(clean)) return clean.split(BLANK_LINE).flatMap(::blockParagraphs)
        val lines = clean.split("\n").map(::squeeze).filter { it.isNotEmpty() }
        return lines.map { Paragraph(it, isSceneBreakLine(it, lines.size == 1)) }
    }

    /** Số dòng có chữ đầu chương mà luật dòng ghi công xét (text_processing.CREDIT_WINDOW_LINES). */
    private const val CREDIT_WINDOW = 6

    /**
     * Chữ của chương trừ các dòng người nghe đã chọn bỏ khỏi phần đọc (lớp sửa `skip` - gợi ý dòng ghi công của bộ nhập sách) - bản Kotlin
     * của `withoutLines` (textScript.ts): chỉ xét 6 dòng có chữ đầu chương. Chữ của sách không đổi; lõi đọc to và màn đọc cùng bỏ.
     */
    fun withoutLines(text: String, skip: List<String>): String {
        if (skip.isEmpty()) return text
        var seen = 0
        return text.replace(NEWLINES, "\n").split("\n").filter { line ->
            val shown = squeeze(withoutNoteMarkers(line)) // `skip` ghi từ chữ đã bỏ mã chú thích (BookImport.creditLines)
            if (shown.isEmpty() || seen >= CREDIT_WINDOW) return@filter true
            seen++
            shown !in skip
        }.joinToString("\n")
    }

    /** Dấu kết câu ở cuối dòng (`SENTENCE_END` của textScript.ts): dòng như vậy là trọn một đoạn, không phải dòng bị bẻ giữa câu. */
    private const val SENTENCE_END = ".!?…\"”»’)」』】。！？~–—"
    /** Dài hơn mọi khổ dòng của máy dàn trang: chắc chắn là trọn một đoạn (`WHOLE_LINE`). */
    private const val WHOLE_LINE = 200

    /**
     * Một đoạn chữ thường (không có dòng ngăn cảnh) - các dòng của một khối giữa hai dòng trống, hay phần của khối giữa hai dòng ngăn cảnh (`textParagraphs` của
     * textScript.ts): bị bẻ giữa câu thì nối thành một đoạn; còn nếu đa số dòng (trừ dòng cuối) kết thúc bằng dấu kết câu, hay có dòng dài hơn mọi khổ dòng,
     * thì mỗi dòng một đoạn - file mỗi dòng một đoạn chỉ có vài dòng trống không dồn cả chương thành một đoạn âm thanh khổng lồ.
     */
    private fun textParagraphs(lines: List<String>): List<String> {
        if (lines.size < 2) return lines
        val ended = lines.dropLast(1).count { it.last() in SENTENCE_END }
        return if (ended * 2 > lines.size - 1 || lines.any { it.length > WHOLE_LINE }) lines else listOf(lines.joinToString(" "))
    }

    /** Một đoạn của chương: chữ, và có phải dòng ngăn cảnh không ([isSceneBreakLine], kể cả luật "đứng riêng một đoạn"). */
    class Paragraph(val text: String, val sceneBreak: Boolean)

    private fun plain(texts: List<String>): List<Paragraph> = texts.map { Paragraph(it, false) }

    /**
     * Các đoạn của một khối giữa hai dòng trống (`blockParagraphs` của textScript.ts): dòng ngăn cảnh ("***", "◆") luôn là một đoạn riêng - không nối vào câu trước /
     * sau; phần chữ ở hai bên nó chia như [textParagraphs]. Khối chỉ có MỘT dòng là dòng "đứng riêng".
     */
    private fun blockParagraphs(block: String): List<Paragraph> {
        val lines = block.split("\n").map(::squeeze).filter { it.isNotEmpty() }
        val out = ArrayList<Paragraph>()
        var run = ArrayList<String>()
        for (line in lines) {
            if (!isSceneBreakLine(line, lines.size == 1)) {
                run.add(line)
                continue
            }
            out.addAll(plain(textParagraphs(run)))
            out.add(Paragraph(line, true))
            run = ArrayList()
        }
        out.addAll(plain(textParagraphs(run)))
        return out
    }

    // ---- dòng ngăn cảnh -----------------------------------------------------------------------------------------------------------------
    // Bản Kotlin của text_processing.is_scene_break_line / textScript.ts (isSceneBreakLine, sceneBreakGaps); cả ba chạy cùng bộ ví dụ
    // tests/fixtures/scene_break/cases.json (SceneBreakTest). Dòng chỉ gồm ký hiệu ngăn cảnh không đọc lên: người nghe nghe một quãng lặng thay cho nó.

    /** Quãng lặng ở chỗ đổi cảnh (ms) - text_processing.SCENE_BREAK_MS. */
    const val SCENE_BREAK_MS = 1500
    /** Ký hiệu kiểu đường kẻ: một dấu đơn lẻ có thể là dấu câu / gạch thoại / tiêu đề markdown, nên cần từ [SCENE_BREAK_MIN_RULE_GLYPHS] dấu. */
    internal const val SCENE_BREAK_RULE_GLYPHS = "*~-=_#+·•‧・—–―‒─━═┄┈╌"
    internal const val SCENE_BREAK_MIN_RULE_GLYPHS = 3
    /** ... trừ khi dòng đứng riêng một đoạn: khi ấy một-hai dấu trong nhóm này cũng đủ. "—" / "–" không vào nhóm: một đoạn chỉ có "—" có thể là lời thoại im lặng. */
    internal const val SCENE_BREAK_ALONE_GLYPHS = "*~-=#"
    /** Ký hiệu trang trí: một dấu đã đủ. Không có dấu chấm, "…", ngoặc, nháy hay ?! - dòng "..." hay dòng chỉ có ngoặc kép không phải ngăn cảnh. */
    internal const val SCENE_BREAK_ORNAMENT_GLYPHS = "◆◇◈○●◎□■▪▫▲△▽▼★☆✦✧✱✲✶✷✻✽❖❀✿❁※⁂⁕⋆◦♦♢◊⸻§"
    internal const val SCENE_BREAK_MAX_GLYPHS = 40

    /**
     * Dòng chỉ có ký hiệu ngăn cảnh ("***", "* * *", "◆", "◇◇◇", "———", "~~~", "＊＊＊"), không chữ không số. `alone`: dòng đứng riêng một đoạn - khi ấy "*", "-", "--"
     * cũng là ngăn cảnh (text_processing.is_scene_break_line).
     */
    fun isSceneBreakLine(line: String, alone: Boolean = false): Boolean {
        val glyphs = Normalizer.normalize(line, Normalizer.Form.NFKC).filter { it !in JS_SPACE_CHARS }
        if (glyphs.isEmpty() || glyphs.length > SCENE_BREAK_MAX_GLYPHS) return false
        if (!glyphs.all { it in SCENE_BREAK_RULE_GLYPHS || it in SCENE_BREAK_ORNAMENT_GLYPHS }) return false
        if (glyphs.none { it in SCENE_BREAK_RULE_GLYPHS }) return true
        if (alone && glyphs.all { it in SCENE_BREAK_ALONE_GLYPHS }) return true
        return glyphs.length >= SCENE_BREAK_MIN_RULE_GLYPHS
    }

    /** Đoạn có chữ hay số để đọc lên (`isSpeakable` của textScript.ts: `[\p{L}\p{N}]`). */
    fun isSpeakable(text: String): Boolean {
        var at = 0
        while (at < text.length) {
            val point = text.codePointAt(at)
            if (Character.isLetter(point)) return true
            when (Character.getType(point)) {
                Character.DECIMAL_DIGIT_NUMBER.toInt(), Character.LETTER_NUMBER.toInt(), Character.OTHER_NUMBER.toInt() -> return true
            }
            at += Character.charCount(point)
        }
        return false
    }

    /**
     * Quãng lặng (ms) của từng đoạn (`sceneBreakGaps` của textScript.ts): chỉ dòng ngăn cảnh ĐẦU của một chuỗi dòng ngăn cảnh liền nhau có quãng lặng, và chỉ khi có
     * đoạn đọc được ở cả trước lẫn sau nó (đầu / cuối chương không có cảnh nào để ngăn; hai dòng "***" liền nhau lặng một lần) - đúng như segment_chapter_text đặt
     * `break_ms` lên câu trước dòng ngăn. Đoạn còn lại 0. Dòng "..." (không đọc được nhưng không phải ngăn cảnh) không cắt chuỗi.
     */
    fun sceneBreakGaps(paragraphs: List<Paragraph>): IntArray {
        val gaps = IntArray(paragraphs.size)
        var spoken = false
        var first = -1
        paragraphs.forEachIndexed { index, paragraph ->
            if (paragraph.sceneBreak) {
                if (spoken && first < 0) first = index
            } else if (isSpeakable(paragraph.text)) {
                if (first >= 0) gaps[first] = SCENE_BREAK_MS
                first = -1
                spoken = true
            }
        }
        return gaps
    }
}
