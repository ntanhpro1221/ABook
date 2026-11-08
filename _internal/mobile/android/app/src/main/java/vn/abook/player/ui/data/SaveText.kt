package vn.abook.player.ui.data

import vn.abook.player.S

/**
 * Chữ của "Lưu thay đổi" / "Lưu thành" (web: listen/BookScreen.tsx `useSaveBook`, listen/EditBook.tsx `SaveAsDialog`). Hàm thuần - thử trên JVM (SaveTextTest).
 */
object SaveText {
    const val SAVED = S.s_da_luu_file_sach_baab68d2
    const val FAILED = S.s_chua_luu_duoc_file_sach_964ff92c
    const val NO_CHANGES = S.s_chua_co_thay_doi_nao_file_giong_ban_goc_f109003f

    /** Lời báo sau khi lưu xong; không có thay đổi nào vẫn lưu được, nhưng nói rõ file giống hệt bản gốc. */
    fun done(edits: Int): String = if (edits > 0) SAVED else "$SAVED. $NO_CHANGES"

    /** Lưu hỏng: tên việc, rồi lý do của lõi nếu có. */
    fun failed(message: String?): String = if (message.isNullOrBlank()) FAILED else "$FAILED. ${message.trim()}"

    /** Dòng giải thích dưới lựa chọn loại file của "Lưu thành". */
    fun kindNote(project: Boolean, workshop: String?, wishes: Int): String = when {
        project && workshop == "present" -> S.s_ca_du_an_kem_thay_doi_cua_ban_mo_bang_stud_f33ca39c
        project -> S.s_chi_co_phan_nghe_va_thay_doi_cua_ban_studi_09cd637e
        else -> S.s_sach_nghe_mo_duoc_bang_abook_tren_may_tinh_ef9eba65 +
            (if (wishes > 0) S.s_cung_0_viec_dang_cho_may_lam_sach_chua_lam_4b0db6d4(wishes) else "") + "."
    }
}
