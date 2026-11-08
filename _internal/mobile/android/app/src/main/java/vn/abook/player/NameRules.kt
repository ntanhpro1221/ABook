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

    private val RESERVED = setOf(S.s_nguoi_ke_50063a62, S.s_nguoi_ke_doc_tat_ca_50e8a103, S.s_vai_phu_khong_ten_6a816c3e, "narrator", "unknown", "unnamed", "anonymous")

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
        if (cleaned.isEmpty() && BookEdits.pyStrip(raw).isNotEmpty()) throw Problem(S.s_0_chi_co_ky_tu_khong_nhin_thay_ban_go_lai_b9991811(what))
        return cleaned
    }

    private fun tooLong(cleaned: String, limit: Int, what: String) {
        if (length(cleaned) > limit) throw Problem(S.s_0_toi_da_1_ky_tu_hien_co_2_ban_rut_ngan_la_73afad5d(what, limit, length(cleaned)))
    }

    fun isReserved(name: String): Boolean {
        val folded = VietnameseReading.casefold(name)
        return folded in RESERVED || folded.startsWith("anonymous_") || folded.startsWith("npc_local") || "::" in name
    }

    /** `name_rules.person`: tên một người (đổi tên, người mới). `others`: tên những người KHÁC. Rỗng chỉ khi `allowEmpty` (trở về tên gốc). */
    fun person(raw: String, others: List<String> = emptyList(), allowEmpty: Boolean = false): String {
        val name = typed(raw, S.s_ten_c8b17259)
        if (name.isEmpty()) {
            if (allowEmpty) return ""
            throw Problem(S.s_ban_chua_go_ten_a420d6a9)
        }
        tooLong(name, NAME_MAX, S.s_ten_c8b17259)
        if (isReserved(name)) throw Problem(S.s_0_la_ten_may_dung_cho_nguoi_ke_hay_vai_phu_5c4ec8cb(name))
        val folded = VietnameseReading.casefold(name)
        for (other in others) {
            if (VietnameseReading.casefold(tidy(other)) == folded) {
                throw Problem(S.s_da_co_0_trong_sach_ban_dat_ten_khac_de_tra_1c5bd10d(tidy(other)))
            }
        }
        return name
    }

    /** `name_rules.surface`: chữ trong sách cần đổi cách đọc. */
    fun surface(raw: String): String {
        val word = typed(raw, S.s_tu_can_doi_cach_doc_f9aca636)
        if (word.isEmpty()) throw Problem(S.s_ban_chua_go_tu_can_doi_cach_doc_cfee5b4f)
        tooLong(word, SURFACE_MAX, S.s_tu_can_doi_cach_doc_f9aca636)
        return word
    }

    /** `name_rules.spoken`: cách đọc người gõ. */
    fun spoken(raw: String): String {
        val form = typed(raw, S.s_cach_doc_94265da7)
        if (form.isEmpty()) throw Problem(S.s_ban_chua_go_cach_doc_6f2d412a)
        tooLong(form, SPOKEN_MAX, S.s_cach_doc_94265da7)
        return form
    }

    /** Dùng trong LocalStudio: chữ có gõ (không chỉ khoảng trắng) mới qua phép kiểm; chưa gõ gì -> "" để nơi gọi tự nói "thiếu". */
    internal fun typedSurface(raw: String): String = if (BookEdits.pyStrip(raw).isEmpty()) "" else surface(raw)
}
