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
        val blocks = if (BLANK_LINE.containsMatchIn(clean)) clean.split(BLANK_LINE) else clean.split("\n")
        return blocks.map(::squeeze).filter { it.isNotEmpty() }
    }
}
