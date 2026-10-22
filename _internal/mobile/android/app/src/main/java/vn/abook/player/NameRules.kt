package vn.abook.player

import java.text.Normalizer

/**
 * Phép kiểm chữ người nghe gõ cho TÊN và CÁCH ĐỌC (soát a89 T1) - bản Kotlin của webui/name_rules.py + names.tidy, đáp chung bộ ví dụ
 * tests/fixtures/book_edits/name_rules.json. Chữ gõ được làm sạch TRƯỚC khi lưu (NFC, bỏ ký tự vô hình nhóm Cf và ký tự điều khiển, gộp
 * khoảng trắng); quá dài thì BÁO chứ không cắt lặng lẽ; chỉ có ký tự vô hình thì từ chối; tên người không trùng người khác hay tên dành
 * riêng của máy. Không chặn tên gần trùng ("Hà" / "Hạ"): tiếng Việt phân biệt người bằng dấu.
 */
object NameRules {
    const val NAME_MAX = 80
    const val SURFACE_MAX = 80
    const val SPOKEN_MAX = 120

    private val RESERVED = setOf("người kể", "người kể đọc tất cả", "vai phụ không tên", "narrator", "unknown", "unnamed", "anonymous")

    /** Lời báo cho người gõ (đã là tiếng Việt, hiện nguyên văn). */
    class Problem(message: String) : Exception(message)

    private fun isSpace(codePoint: Int): Boolean =
        Character.isWhitespace(codePoint) || Character.isSpaceChar(codePoint) || codePoint == 0x85

    /** `names.tidy`: NFC, bỏ ký tự Cf và điều khiển (trừ khoảng trắng), mọi khoảng trắng thành một dấu cách. */
    fun tidy(text: String): String {
        val kept = StringBuilder()
        Normalizer.normalize(text, Normalizer.Form.NFC).codePoints().forEach { codePoint ->
            val type = Character.getType(codePoint)
            when {
                type == Character.FORMAT.toInt() -> Unit
                type == Character.CONTROL.toInt() && !isSpace(codePoint) -> Unit
                isSpace(codePoint) -> kept.append(' ')
                else -> kept.appendCodePoint(codePoint)
            }
        }
        return kept.toString().split(' ').filter { it.isNotEmpty() }.joinToString(" ")
    }

    private fun length(text: String): Int = text.codePointCount(0, text.length)

    private fun typed(raw: String, what: String): String {
        val cleaned = tidy(raw)
        if (cleaned.isEmpty() && BookEdits.pyStrip(raw).isNotEmpty()) throw Problem("$what chỉ có ký tự không nhìn thấy - bạn gõ lại bằng chữ thường.")
        return cleaned
    }

    private fun tooLong(cleaned: String, limit: Int, what: String) {
        if (length(cleaned) > limit) throw Problem("$what dài tối đa $limit ký tự (bạn đang gõ ${length(cleaned)}) - bạn rút ngắn lại.")
    }

    fun isReserved(name: String): Boolean {
        val folded = VietnameseReading.casefold(name)
        return folded in RESERVED || folded.startsWith("anonymous_") || folded.startsWith("npc_local") || "::" in name
    }

    /** `name_rules.person`: tên một người (đổi tên, người mới). `others`: tên những người KHÁC. Rỗng chỉ khi `allowEmpty` (trở về tên gốc). */
    fun person(raw: String, others: List<String> = emptyList(), allowEmpty: Boolean = false): String {
        val name = typed(raw, "Tên")
        if (name.isEmpty()) {
            if (allowEmpty) return ""
            throw Problem("Bạn chưa gõ tên.")
        }
        tooLong(name, NAME_MAX, "Tên")
        if (isReserved(name)) throw Problem("“$name” là tên máy dùng cho người kể hay vai phụ không tên - bạn đặt tên khác.")
        val folded = VietnameseReading.casefold(name)
        for (other in others) {
            if (VietnameseReading.casefold(tidy(other)) == folded) {
                throw Problem("Trong sách đã có người tên “${tidy(other)}” - bạn đặt tên khác để khỏi nhầm hai người.")
            }
        }
        return name
    }

    /** `name_rules.surface`: chữ trong sách cần đổi cách đọc. */
    fun surface(raw: String): String {
        val word = typed(raw, "Từ cần đổi cách đọc")
        if (word.isEmpty()) throw Problem("Bạn chưa gõ từ cần đổi cách đọc.")
        tooLong(word, SURFACE_MAX, "Từ cần đổi cách đọc")
        return word
    }

    /** `name_rules.spoken`: cách đọc người gõ. */
    fun spoken(raw: String): String {
        val form = typed(raw, "Cách đọc")
        if (form.isEmpty()) throw Problem("Bạn chưa gõ cách đọc.")
        tooLong(form, SPOKEN_MAX, "Cách đọc")
        return form
    }

    /** Dùng trong LocalStudio: chữ có gõ (không chỉ khoảng trắng) mới qua phép kiểm; chưa gõ gì -> "" để nơi gọi tự nói "thiếu". */
    internal fun typedSurface(raw: String): String = if (BookEdits.pyStrip(raw).isEmpty()) "" else surface(raw)
}
