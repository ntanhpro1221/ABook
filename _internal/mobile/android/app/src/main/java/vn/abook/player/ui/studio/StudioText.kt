package vn.abook.player.ui.studio

import vn.abook.player.S

import vn.abook.player.Pin
import vn.abook.player.StudioError
import vn.abook.player.StudioLink
import vn.abook.player.ui.data.Fmt

/**
 * Mọi chữ tiếng Việt của Studio từ xa ở MỘT nơi (NATIVE_REMOTE_STUDIO.md §3.3, §8): lời lỗi giữ y chữ của web (`polling.ts failureText`,
 * `stopText.ts`, `format.ts`) để hai nền tảng nói cùng một câu. Nhãn nút 1-4 chữ; nói với người dùng là "bạn".
 */
object StudioText {
    const val TITLE = S.s_studio_0aa91af2

    // ---- lỗi và quyền ----

    const val OFFLINE = S.s_mat_ket_noi_toi_abook_1d2b48ae
    const val GONE = S.s_sach_co_the_da_bi_chuyen_hoac_xoa_e69fbf8d
    const val UNPAIRED = S.s_may_tinh_da_bo_ghep_dien_thoai_nay_ban_ghe_30e3644b
    const val TOO_BIG = S.s_goi_gui_len_qua_lon_ed6234f1
    const val RETRY = S.s_thu_lai_c58d068c

    /** Lời cho người nghe của một lỗi Studio, theo loại: một nơi duy nhất. */
    fun failure(error: StudioError): String = when (error) {
        is StudioError.Offline -> OFFLINE
        is StudioError.Gone -> GONE
        is StudioError.Unauthorized -> UNPAIRED
        is StudioError.PinChanged -> Pin.CHANGED
        is StudioError.TooBig -> TOO_BIG
        is StudioError.ListenOnly -> PERMISSION_TITLE
        is StudioError.Busy -> error.message.orEmpty()
        is StudioError.Server -> error.message.orEmpty().ifBlank { GONE }
    }

    const val PERMISSION_TITLE = S.s_may_tinh_chua_cho_ban_sua_6a5d6567

    /** `name`: tên máy như bạn thấy ở Thiết bị. */
    fun permissionLine(name: String): String = S.s_bat_cho_phep_dieu_khien_san_xuat_tren_0_ro_eaf20ada(machine(name))

    /** "máy MayCuaNam-Laptop": giữa câu nên không viết hoa. */
    fun machine(name: String): String = StudioLink.called(name).replaceFirstChar { it.lowercase() }

    fun silent(name: String): String = StudioLink.silentLine(name)

    const val MISMATCH = S.s_may_tinh_can_cap_nhat_abook_o_cung_phien_b_aea800ed

    // ---- danh sách dự án ----

    const val NO_PROJECTS = S.s_chua_co_du_an_dd6cd3d2
    const val NO_PROJECTS_HINT = S.s_bam_sach_moi_de_lam_sach_noi_tu_mot_file_t_a05f06f6
    const val LOADING = S.s_dang_mo_studio_3b7f5836

    fun group(group: StudioGroup): String = when (group) {
        StudioGroup.Working -> S.s_dang_lam_ae875642
        StudioGroup.Review -> S.s_cho_ban_duyet_dd9175be
        StudioGroup.Rest -> S.s_con_lai_b3edb1ba
    }

    /** Chỗ trong hàng chờ nói bằng "còn mấy việc trước" ("thứ 6" đọc thành "thứ Sáu"); `position` đếm từ 1. */
    fun queue(position: Int): String = if (position <= 1) S.s_sap_toi_luot_4fcc9331 else S.s_con_0_viec_truoc_7f305d79(position - 1)

    // ---- dự án ----

    const val GONE_TITLE = S.s_du_an_nay_khong_con_94194a30
    const val BACK_TO_STUDIO = S.s_ve_studio_349a48c4
    const val MORE = S.s_them_dd92626f

    fun subLabel(kind: StudioSubKind): String = when (kind) {
        StudioSubKind.Precast -> PrecastText.TITLE
        StudioSubKind.Script -> ScriptText.TITLE
        StudioSubKind.Readings -> ReadingsText.TITLE
        StudioSubKind.Export -> StudioExportText.TITLE
        StudioSubKind.Activity -> StudioLogText.TITLE
        StudioSubKind.Cover -> StudioCoverText.TITLE
    }
    const val NO_CHAPTERS = S.s_chua_co_chuong_nao_35e56dd1

    fun label(kind: PrimaryKind, book: StudioBook): String = when (kind) {
        PrimaryKind.Starting -> S.s_dang_khoi_dong_e7a9b0e5
        PrimaryKind.Stopping -> S.s_dang_dung_9b35aeb5
        PrimaryKind.Unpause -> if (book.precastHeld) S.s_thu_am_db588c2e else S.s_tiep_tuc_87a7ae88
        PrimaryKind.Pause -> S.s_tam_dung_67635815
        PrimaryKind.Start -> S.s_bat_dau_b3cacc46
        PrimaryKind.Record -> S.s_thu_am_db588c2e
        PrimaryKind.Resume, PrimaryKind.Continue -> S.s_tiep_tuc_87a7ae88
        PrimaryKind.Apply -> S.s_ap_dung_0_thay_doi_fdb3a048(book.pendingChanges)
        PrimaryKind.Dequeue -> S.s_bo_xep_hang_e797cd68
        PrimaryKind.Listen -> S.s_nghe_trong_thu_vien_c0d6771a
    }

    /** Hai nút chính này chỉ báo trạng thái (đang khởi động / đang dừng), chưa bấm được. */
    fun inert(kind: PrimaryKind) = kind == PrimaryKind.Starting || kind == PrimaryKind.Stopping

    /** Dòng dưới nút chính (web `Actions`): vì sao đứng, hay việc đang chờ; "" khi không có gì để nói. */
    fun actionNote(book: StudioBook, kind: PrimaryKind?): String {
        val redoWaiting = if (book.phase == "done") book.chaptersRedo else 0
        return when {
            book.queuePosition != null ->
                S.s_cho_luot_0_tu_chay_khi_cuon_truoc_xong_1_32334b5f(book.queuePosition, if (book.seedPending) S.s_giu_giong_va_cach_doc_ten_993d1078 else "") +
                    (book.queueWaitsOn?.let { " " + queueWait(it) } ?: "")
            book.running && book.stopping -> S.s_dung_o_checkpoint_ke_giu_phan_da_xong_co_t_37dd2329
            kind == PrimaryKind.Resume -> {
                val pending = book.segmentsPending ?: (book.segmentsTotal - book.segmentsAnalyzed)
                S.s_phan_tich_da_dung_giua_chung_6971e0d3 + (if (book.segmentsTotal > 0) S.s_con_0_1_cau_3ea208e0(pending, book.segmentsTotal) else "") +
                    S.s_tiep_tuc_thi_0_d797f394(ANALYSIS_CUT_COST)
            }
            redoWaiting > 0 && kind == PrimaryKind.Continue ->
                (if (redoWaiting == 1) S.s_1_chuong_dang_cho_thu_lai_b9da1ca4 else S.s_0_chuong_dang_cho_thu_lai_c577313b(redoWaiting)) +
                    S.s_theo_sua_cua_ban_ban_cu_van_nghe_duoc_cho_6adf5ab2
            onBattery(book) -> S.s_studio_tam_dung_cam_sac_de_tiep_tuc_5704e36a
            else -> ""
        }
    }

    /** Đang tạm dừng vì máy chạy pin: [actionNote] nói một câu, [BATTERY_INFO] gập sau "Dùng pin" ngay dưới. */
    fun onBattery(book: StudioBook): Boolean = book.running && book.paused == StudioPause.Battery

    /** Vì sao tạm dừng khi máy chạy pin (web: MoreInfo của Actions ở ProjectScreen.tsx; điện thoại luôn là máy từ xa nên câu dừng ở "pin."). */
    const val BATTERY_INFO = S.s_lam_sach_tren_pin_cham_va_hao_pin_bam_tiep_7044fad1

    /** Cuốn xếp hàng đứng sau một cuốn đang tạm dừng: hàng không tự đi tiếp (stopText.ts `queueWaitNotice`). */
    fun queueWait(waits: StudioQueueWait): String =
        if (waits.paused == StudioPause.Battery) {
            S.s_0_dang_tam_dung_vi_may_chay_pin_nen_cuon_n_a3f87494(waits.title)
        } else {
            S.s_0_dang_tam_dung_nen_cuon_nay_chua_toi_luot_e8965d5e(waits.title)
        }

    // ---- xác nhận ----

    /** Hệ quả, đứng sau "… thì" / "… sẽ" (stopText.ts `ANALYSIS_CUT_COST`). */
    const val ANALYSIS_CUT_COST = S.s_co_the_ra_mot_cuon_khac_nguoi_noi_o_doan_s_4a2e8f6b
    const val ANALYSIS_STOP_FACT = S.s_phan_da_phan_tich_duoc_giu_nguyen_nhung_la_7b0b4096

    fun stopTitle(book: StudioBook) = if (book.phase == "analysis") S.s_dung_phan_tich_3fae0cc9 else S.s_dung_thu_am_c0b08972

    /** Các dòng của hộp Dừng: lúc phân tích nói thẳng giá phải trả; không thì nói việc đã xong được giữ. */
    fun stopLines(book: StudioBook): List<String> {
        if (book.phase != "analysis") {
            return listOf(
                if (book.paused != null) S.s_tam_dung_van_giu_bo_nho_card_do_hoa_dung_h_5c49cc06
                else S.s_moi_chuong_va_cau_da_xong_duoc_giu_nguyen_295ff27b,
            )
        }
        val eta = etaOf(book)
        return listOf("$ANALYSIS_STOP_FACT - $ANALYSIS_CUT_COST.", S.s_nen_de_chay_het_buoc_nay_0_1_5ea96c79(if (eta != null) " ($eta)" else "", stopAdvice(book)).trim())
    }

    /** Câu cuối hộp Dừng lúc phân tích: đang tạm dừng thì nói sách đang yên ở đâu, không mời "bấm Tạm dừng" - không có nút ấy. */
    fun stopAdvice(book: StudioBook): String = when {
        book.paused != null -> S.s_sach_dang_tam_dung_dung_yen_dung_cho_phan_7bfd81b4
        book.canPause -> S.s_can_nghi_thi_bam_tam_dung_sach_dung_yen_ro_0d5d0ddd
        else -> ""
    }

    fun stopKeep(book: StudioBook) = if (book.paused != null) S.s_de_nguyen_2f029b4a else S.s_de_chay_tiep_28b8b5b6
    fun stopConfirm(book: StudioBook) = if (book.phase == "analysis") S.s_van_dung_f9d19e87 else S.s_dung_11554138

    fun resumeTitle() = S.s_tiep_tuc_phan_tich_6d773a52
    fun resumeLines(book: StudioBook): List<String> = listOf(
        S.s_phan_tich_cua_0_da_dung_giua_chung_lam_tie_95ef0030(book.title, ANALYSIS_CUT_COST),
        S.s_muon_chac_nhu_chay_lien_mach_hay_lam_lai_p_2316ba25,
    )

    fun applyTitle(book: StudioBook) = S.s_ap_dung_0_thay_doi_b7955e0a(book.pendingChanges)
    const val APPLY_LINE = S.s_may_chi_thu_lai_nhung_cau_bi_anh_huong_roi_67af5454

    // ---- chữ có số đổi theo thời gian (đi qua ClockLabel; xem TickingValuePolicyTest) ----

    private fun clamp(fraction: Float): Float = if (fraction.isFinite()) fraction.coerceIn(0f, 1f) else if (fraction == Float.POSITIVE_INFINITY) 1f else 0f

    /** Phần trăm của thanh tiến độ, làm tròn XUỐNG: chưa xong thì không bao giờ 100% (format.ts `formatPercent`). */
    fun percent(fraction: Float): String {
        val value = clamp(fraction) * 100f
        if (value > 0f && value < 1f) return "<1%"
        if (value < 100f && value > 99f) return "99%"
        return "${value.toInt()}%"
    }

    /** Từ mức này của bước đang làm thì "còn dưới 2 phút" mới là "sắp xong". */
    private const val NEAR_DONE = 0.85f

    /** format.ts `formatEta`: còn ít giây mà bước chưa tới mức gần xong thì chỉ nói còn dưới 2 phút. */
    fun eta(seconds: Double, fraction: Float? = null): String =
        if (seconds < 90) { if (fraction == null || fraction >= NEAR_DONE) S.s_sap_xong_7d5cfa0f else S.s_con_duoi_2_phut_41c172a6 } else S.s_con_khoang_0_1186d7f6(Fmt.length(seconds))

    /**
     * Thời gian còn lại của bước máy đang làm, hay null khi chưa có tốc độ để ước (format.ts `etaOf`). Nói rõ là của bước nào: cạnh "N% tổng", "sắp xong"
     * trần đọc thành cả cuốn sắp xong trong khi còn các bước sau.
     */
    fun etaOf(book: StudioBook): String? {
        val estimate = book.eta ?: return null
        if (estimate.phase == "speaker") {
            val pass = book.speaker
            return S.s_pha_xac_dinh_nguoi_noi_0baa5e0c + eta(estimate.seconds, pass?.takeIf { it.total > 0 }?.let { it.done.toFloat() / it.total })
        }
        val synthesis = estimate.phase == "synthesis"
        return (if (synthesis) S.s_pha_thu_am_51533dd9 else S.s_pha_phan_tich_1da0f8f4) + eta(estimate.seconds, if (synthesis) book.synthesis else book.analysis)
    }

    /** Dòng nói còn bao lâu của cả lượt làm sách (hay vì sao đang đứng); "" khi không có gì để nói (web `progressNote`). */
    fun progressNote(book: StudioBook): String {
        val live = book.working
        return when {
            book.stopping -> S.s_dang_dung_cd5f369b
            book.paused != null -> if (book.precastHeld) S.s_cho_ban_duyet_roi_bam_thu_am_5f91fe4f else ""
            else -> etaOf(book) ?: if (live) S.s_dang_uoc_tinh_thoi_gian_6e128147 else ""
        }
    }

    /** "chương 12/48" của một dự án đang làm. */
    fun chapterLine(book: StudioBook): String =
        if (book.chaptersTotal > 0) S.s_0_1_chuong_8d58e1df(book.chaptersCompleted, book.chaptersTotal) else ""

    /** Dòng trạng thái ngắn của thẻ dự án: nhãn, rồi tiến độ chương khi đang làm. */
    fun statusLine(book: StudioBook): String {
        val status = StudioLogic.status(book)
        val line = chapterLine(book)
        return if (line.isNotEmpty() && book.phase != "idle") "${status.label} · $line" else status.label
    }

    /** Thời lượng một chương ("12 phút"). */
    fun length(seconds: Double): String = if (seconds > 0) Fmt.length(seconds) else ""
}
