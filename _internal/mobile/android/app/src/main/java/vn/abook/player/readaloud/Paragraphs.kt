package vn.abook.player.readaloud

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
    fun of(text: String): List<String> {
        val clean = text.replace(NEWLINES, "\n")
        if (!BLANK_LINE.containsMatchIn(clean)) return clean.split("\n").map(::squeeze).filter { it.isNotEmpty() }
        return clean.split(BLANK_LINE).flatMap(::blockParagraphs)
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
            val shown = squeeze(line)
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
     * Các dòng của một khối giữa hai dòng trống (`blockParagraphs` của textScript.ts): bị bẻ giữa câu thì nối thành một đoạn; còn nếu đa số
     * dòng (trừ dòng cuối) kết thúc bằng dấu kết câu, hay có dòng dài hơn mọi khổ dòng, thì mỗi dòng một đoạn - file mỗi dòng một đoạn
     * chỉ có vài dòng trống không dồn cả chương thành một đoạn âm thanh khổng lồ.
     */
    private fun blockParagraphs(block: String): List<String> {
        val lines = block.split("\n").map(::squeeze).filter { it.isNotEmpty() }
        if (lines.size < 2) return lines
        val ended = lines.dropLast(1).count { it.last() in SENTENCE_END }
        return if (ended * 2 > lines.size - 1 || lines.any { it.length > WHOLE_LINE }) lines else listOf(lines.joinToString(" "))
    }
}
