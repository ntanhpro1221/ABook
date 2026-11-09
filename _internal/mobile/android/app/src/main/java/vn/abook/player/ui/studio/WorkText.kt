package vn.abook.player.ui.studio

import vn.abook.player.S

import vn.abook.player.ui.data.dotJoin

/**
 * Chữ của ba tab nội dung Studio (Việc cần duyệt, Cần nghe lại, Nhân vật) và bảng giọng, ở MỘT nơi. Chữ của chính các thẻ (tiêu đề, nút trả lời, lời đã ghi)
 * lấy từ máy tính hay từ [WorkLogic] / [ReviewLogic] / [VoiceLogic] để hai nền tảng nói cùng một câu; ở đây chỉ là chữ riêng của điện thoại. Nhãn nút 1-4 chữ.
 */
object WorkText {
    // ---- chung ----

    /** Máy từ chối vì câu đã đổi từ lúc bạn mở thẻ (409 hay 400): thẻ nạp lại, không tự gửi lại. */
    const val STALE = S.s_cau_nay_da_doi_ban_xem_lai_692a26c3
    const val UNDO = S.s_hoan_tac_e72ff675
    const val CLOSE = S.s_dong_5d54c2a1
    const val SKIP = S.s_bo_qua_c67ba288
    const val MORE = S.s_chon_khac_a5d76e8e
    const val PLAY = S.s_nghe_a43aafef
    const val STOP = S.s_dung_11554138
    const val DONE = S.s_xong_a6f4543a
    const val LOADING = S.s_dang_mo_98235c77
    const val PLAY_FAILED_OFFLINE = S.s_chua_tai_duoc_doan_nay_kiem_tra_ket_noi_to_2d50f8f2
    const val PLAY_FAILED_MISSING = S.s_may_tinh_khong_con_doan_nay_a27c20db

    // ---- Việc cần duyệt ----

    const val WORK_LOADING = S.s_dang_mo_danh_sach_viec_a2832e95
    const val WORK_EMPTY_TITLE = S.s_da_duyet_het_d28b4c37
    const val WORK_EMPTY = S.s_may_chac_chan_ve_moi_thu_da_lam_toi_gio_15f0b56b
    const val WORK_EMPTY_LIVE = S.s_may_dang_lam_sach_viec_moi_se_hien_o_day_b2752696

    fun left(count: Int): String = S.s_con_0_viec_acd4365c(count)

    fun affected(count: Int): String = S.s_anh_huong_0_cau_9364fe83(count)

    fun using(text: String): String = S.s_may_dang_dung_0_f5344986(text)

    fun waiting(count: Int): String = if (count == 1) S.s_1_thay_doi_dang_cho_ap_dung_a9a3602a else S.s_0_thay_doi_dang_cho_ap_dung_ff5686a0(count)

    const val SCOPE_LEAD = S.s_doi_nguoi_noi_cho_214fb622
    const val OTHER_PERSON = S.s_nguoi_khac_36be042b
    const val OTHER_SHEET_TITLE = S.s_chon_nguoi_noi_f64cfd5e
    const val NEW_PERSON_HINT = S.s_hay_dat_ten_mot_nguoi_moi_b6a6bc49
    const val NEW_PERSON_FIELD = S.s_ten_nguoi_noi_d3caf277
    const val NEW_GENDER_LEAD = S.s_gioi_bam_de_luu_a6788bb3
    const val GENDER_MALE = S.s_nam_22dd59c8
    const val GENDER_FEMALE = S.s_nu_e15bc11c
    const val GENDER_UNKNOWN = S.s_khong_ro_8af7da78
    const val NARRATOR_OTHER = S.s_nguoi_ke_khac_7291e079
    const val NARRATOR_FIELD = S.s_ten_nguoi_ke_d492ccfb
    const val NARRATOR_SET = S.s_dat_nguoi_ke_d4ae9aa6
    const val PICK_LINES = S.s_chon_cau_75ca91ac
    const val PICK_ALL = S.s_chon_het_9e8a7c2c
    const val PICK_NONE = S.s_bo_het_502895ca

    fun scope(scope: WorkScope, labels: Pair<String, String>?, alternate: Int, all: Int): String = when (scope) {
        WorkScope.Alternate -> dotJoin(labels?.first ?: S.s_cau_xen_ke_a9442401, "$alternate")
        WorkScope.All -> dotJoin(labels?.second ?: S.s_ca_chuoi_2a2c3bbf, "$all")
    }

    fun scopeNote(labels: Pair<String, String>?): String =
        if (labels != null) S.s_0_theo_chuong_1_theo_ca_sach_va_cac_phan_s_1dd980b1(labels.first, labels.second)
        else S.s_cau_xen_ke_chi_doi_cau_danh_dau_ca_chuoi_d_8b814b90

    fun keepName(item: WorkItem): String = item.keepLabel ?: if (item.kind == WorkKind.Unnamed) S.s_dung_la_vai_phu_7f821afe else S.s_giu_0_b8c06ffa(item.current)

    // thẻ cách đọc tên
    const val READING_OR = S.s_hoac_doc_la_376990a8
    const val READING_SAVE = S.s_doc_the_nay_b9d202fe
    const val READING_TRY = S.s_nghe_thu_fa024065
    const val READING_TRYING = S.s_may_dang_doc_thu_12078d9b
    const val READING_HINT = S.s_go_cach_doc_bam_nghe_thu_de_nghe_truoc_khi_be4a153a

    fun readingKeep(current: String): String = S.s_dung_roi_giu_0_f1a41d1a(current)

    fun readingField(surface: String): String = S.s_cach_doc_moi_cho_0_d68a75c3(surface)

    fun readingUse(suggestion: String): String = S.s_dung_0_b8f33061(suggestion)

    // thẻ giọng
    const val VOICE_OTHER = S.s_chon_giong_khac_d31cfe89

    // thẻ bản thu lỗi
    const val LISTEN_LINE = S.s_nhung_cau_nay_nghe_lai_o_tab_can_nghe_lai_8b18c59a
    const val LISTEN_OPEN = S.s_mo_can_nghe_lai_710a440d

    // thẻ yêu cầu chưa được
    const val REFUSED_DROP = S.s_bo_yeu_cau_nay_670ce121

    // thẻ chưa trả lời được trên điện thoại
    const val PLAIN_LINE = S.s_viec_nay_ban_xem_tren_may_tinh_3b37d4d5

    // ---- Cần nghe lại ----

    const val REVIEW_LOADING = S.s_dang_mo_danh_sach_cau_ee65cafc
    const val REVIEW_EMPTY_TITLE = S.s_khong_con_cau_nao_can_xem_895b4a0c
    const val REVIEW_EMPTY = S.s_may_nghe_lai_nhung_cau_da_thu_va_chung_deu_a6d9fb47
    const val REVIEW_NOT_RECORDED_TITLE = S.s_chua_co_cau_nao_de_nghe_lai_0cc858a9
    const val REVIEW_NOT_RECORDED = S.s_may_se_kiem_cac_cau_sau_khi_thu_am_a79a0bf3
    const val REVIEW_DONE_EMPTY = S.s_ban_chua_xem_cau_nao_28daaec6
    const val OK = S.s_on_cec6d53a
    const val REDO = S.s_can_thu_lai_540b83e3
    const val PLAY_ALL_STOP = S.s_dung_nghe_lien_fff6a5f1
    const val PLAY_FINISHED = S.s_da_nghe_het_cac_cau_trong_danh_sach_8a9ddd98
    const val MORE_ITEMS = S.s_xem_them_e0ac1b1e
    const val HEARD = S.s_may_nghe_ra_ccc64fac
    const val HEARD_NOTHING = S.s_may_khong_nghe_ra_chu_nao_63c10adb
    const val NO_AUDIO = S.s_chua_co_ban_thu_de_nghe_75060b8a
    const val MINOR_SHOW = S.s_hien_ca_cau_lech_nhe_0379133b
    const val MINOR_HIDE = S.s_chi_cau_lech_nhieu_b3763bc7
    const val TAKE_THEIRS = S.s_lay_cua_may_kia_37d97780
    const val KEEP_MINE = S.s_giu_cua_toi_f7014d45

    fun playAll(count: Int): String = S.s_nghe_lien_0_cau_0b468c33(count)

    fun reviewPending(count: Int): String = S.s_con_0_cau_chua_xem_b2a11445(count)

    /** Lời gập dưới dòng "chương chờ thu lại" (web: MoreInfo của ReviewQueue.tsx). */
    const val REDO_MORE = S.s_chay_tiep_hoac_ap_dung_thay_doi_de_thu_lai_7f582c5b

    fun redoChapters(chapters: List<Int>): String =
        if (chapters.size == 1) S.s_chuong_0_se_duoc_thu_lai_khi_ban_ap_dung_t_28ace420(chapters[0])
        else S.s_0_chuong_se_duoc_thu_lai_khi_ban_ap_dung_t_8ea9b2e0(chapters.size)

    fun matched(percent: String): String = ReviewLogic.matchShort(percent)

    fun elsewhere(theirs: String): String {
        val was = WorkLogic.verdictWord(theirs.ifEmpty { null })
        return if (was.isEmpty()) S.s_may_hay_cua_so_khac_vua_bo_phan_quyet_cua_85952428 else S.s_may_hay_cua_so_khac_vua_chon_0_cho_cau_nay_a85b8d97(was)
    }

    fun kind(kind: ReviewKind): String = when (kind) {
        ReviewKind.Failed -> S.s_ban_thu_hong_0b08bea2
        ReviewKind.Unverified -> S.s_chua_kiem_duoc_d292aa64
        ReviewKind.NameLow -> S.s_ten_doc_lech_nhieu_67f22a5b
        ReviewKind.TextLow -> S.s_chu_lech_nhieu_06623d45
        ReviewKind.Name -> S.s_ten_doc_lech_nhe_7acc69fa
        ReviewKind.Text -> S.s_chu_lech_nhe_2bfc36c8
    }

    // ---- Nhân vật ----

    const val CAST_LOADING = S.s_dang_mo_dan_nhan_vat_c53d78db
    const val CAST_EMPTY = S.s_chua_co_dan_nhan_vat_6f7729cd
    const val CAST_EMPTY_HINT = S.s_nhan_vat_hien_ra_khi_may_doc_xong_phan_pha_4c7330d3
    const val CAST_NARRATOR = S.s_nguoi_ke_fd36cd15
    const val CAST_MAIN = S.s_nhan_vat_chinh_3071119c
    const val CAST_EXTRAS = S.s_vai_phu_6e7c6bce
    const val CAST_CARRIED = S.s_tu_phan_truoc_aaf26cfe
    const val CAST_NO_VOICE = S.s_chua_co_giong_7ce5f4b4
    const val CAST_PLAY = S.s_nghe_mot_cau_3d65a4ae

    fun castLines(count: Int): String = S.s_0_cau_2a1e6590(count)

    fun pendingVoice(label: String): String = S.s_da_chon_giong_0_cho_ap_dung_7d89890e(label)

    fun mergedInto(name: String): String = S.s_cho_gop_vao_0_dcce4394(name)

    fun renamed(original: String): String = S.s_ten_goc_0_b27cd007(original)

    // ---- Bảng giọng ----

    fun voiceTitle(name: String): String = S.s_giong_cua_0_96e5ead4(name)

    const val VOICE_LOADING = S.s_dang_mo_danh_sach_giong_a0cdaa14
    const val VOICE_PENDING_TITLE = S.s_ban_da_chon_mot_giong_chua_vao_sach_9a336ea9
    const val VOICE_KEEP_CURRENT = S.s_giu_giong_dang_dung_c47b18da
    const val VOICE_CHOOSE = S.s_chon_1171ca97
    const val VOICE_IN_USE = S.s_dang_dung_275ca289
    const val VOICE_CHOSEN = S.s_da_chon_7f7e38b3
    const val VOICE_TRY = S.s_nghe_thu_bang_cau_sach_55425c55
    const val VOICE_TRYING = S.s_may_dang_doc_thu_12078d9b
    const val VOICE_CROSS_YES = S.s_doi_giong_va_gioi_21985f64
    const val VOICE_CROSS_NO = S.s_thoi_e68f9e88
    const val VOICE_NO_VOICES = S.s_gioi_nay_chua_co_giong_nao_8b563453
    const val VOICE_NOT_INSTALLED = S.s_giong_nay_can_cai_them_tren_may_tinh_c80df79b
    /** Lời gập cuối bảng giọng (web: MoreInfo của VoicePicker.tsx): người kể, và nhân vật thường. */
    const val VOICE_NARRATOR_MORE = S.s_nguoi_ke_can_giong_rieng_nen_khong_chon_gi_c145ea51
    const val VOICE_SHARED_MORE = S.s_giong_them_co_the_khien_hai_nhan_vat_nghe_ec79eba6

    fun voicePending(name: String): String = if (name.isEmpty()) S.s_giong_ban_chon_dang_cho_vao_sach_7858aedb else S.s_giong_0_dang_cho_vao_sach_f889d85c(name)

    fun voiceCross(person: String, gender: String, voice: String): String =
        S.s_0_la_giong_1_chon_no_thi_2_cung_thanh_nhan_bd9c02fc(voice, if (gender == "female") S.s_nu_316c30fd else "nam", person, if (gender == "female") S.s_nu_316c30fd else "nam")
}
