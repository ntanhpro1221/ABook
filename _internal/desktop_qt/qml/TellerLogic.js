.import "UiStrings.js" as S
.pragma library
.import "CastLogic.js" as Cast

// Công tắc B "Nhân vật tự kể" (studio/tellerMode.ts, TellerModeSwitch.tsx, NarratorNote của ProjectScreen.tsx; webui/teller_mode.py): chữ và phép tính cái giá, chép từng chữ.

var TITLE = S.s_nhan_vat_tu_ke_b75121e9
// Câu thay cho nút đổi ở nơi không đổi được (điện thoại mở file dự án)
var ELSEWHERE = S.s_doi_o_may_tinh_co_studio_can_thu_lai_d1f81a52
// Sách đang chạy: Tạm dừng chưa đủ (máy vẫn giữ sách), phải “Dừng”
var BUSY_NOTE = S.s_dung_sau_phan_tich_de_doi_roi_tiep_tuc_tam_2623587f

function hint(on) {
    return on ? S.s_nhan_vat_xung_toi_doc_ca_loi_ke_bang_giong_b51f6c3e : S.s_giong_dan_doc_loi_ke_nhan_vat_chi_doc_loi_51b22986
}
// Có cần hỏi lại trước khi đổi không: chỉ khi đã có câu thu sẽ bị bỏ
function needsConfirm(view) { return Boolean(view && view.castLocked && view.plan && view.plan.recorded > 0) }
// Cái giá của lần đổi, nói như người nghe thấy
function costText(plan, turningOn) {
    if (!plan || !plan.lines) return turningOn ? S.s_chua_co_cau_loi_ke_nao_can_doi_giong_1713d093 : S.s_khong_con_cau_nao_de_tra_lai_giong_dan_b32638ee
    const who = plan.tellers && plan.tellers.length ? plan.tellers.join(", ") : S.s_nguoi_ke_50063a62
    const what = turningOn
        ? Cast.formatNumber(plan.lines) + S.s_cau_loi_ke_se_doc_bang_giong_cua_1f5895da + who
        : Cast.formatNumber(plan.lines) + S.s_cau_loi_ke_se_tro_ve_giong_dan_88b035b1
    if (!plan.recorded) return what + S.s_chua_cau_nao_trong_so_do_duoc_thu_nen_khon_6eef4a17
    return what + ". " + Cast.formatNumber(plan.recorded) + S.s_ban_thu_hien_co_cua_nhung_cau_ay_se_bi_bo_b6216517 + Cast.estimateText(plan.seconds, plan.measured) + S.s_ban_thu_cu_khong_lay_lai_duoc_e8505f7b
}
function confirmTitle(asking) { return asking === "teller" ? S.s_bat_giong_tu_ke_ef32d59a : S.s_dung_giong_dan_c9aaaec4 }
function confirmAction(asking) { return asking === "teller" ? S.s_bat_va_thu_lai_16adc647 : S.s_tat_va_thu_lai_dc0f8e21 }
// Lời báo sau khi đổi xong: chỉ nhắc thu lại khi có bản thu bị bỏ
function savedNote(view, recorded) {
    if (!(view.castLocked && view.mode === "teller" && view.applied)) return ""
    return recorded > 0 ? S.s_da_doi_bam_tiep_tuc_de_thu_lai_nhung_cau_d_273ea241 : S.s_da_doi_nhung_cau_doi_giong_se_duoc_thu_ban_1a29ee0b
}

// NarratorNote: dưới hàng "Người kể chuyện" của tab Nhân vật. Cuốn chưa chạy: đổi qua "Sửa thiết lập"; đã phân vai: nút ở hàng ấy; đang phân tích: nói khi nào đổi được.
function narratorNote(book) {
    if (book.phase === "idle") return {text: S.s_giong_ke_chon_luc_tao_sach_doi_duoc_vi_cuo_7293eb77, link: S.s_doi_giong_ke_bbebd2a5}
    if (book.castLocked) return {text: S.s_doi_giong_ke_khong_phai_tao_lai_sach_cau_k_bee3443c, link: ""}
    return {text: S.s_doi_duoc_giong_ke_khi_may_phan_vai_xong_ng_d2298cde, link: ""}
}
