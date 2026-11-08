.import "UiStrings.js" as S
.pragma library

// Phần thuần của việc cài Studio (ui/src/studio/StudioSetup.tsx, studioFit.ts, errorText.ts friendlySetupError, setupLeftover.ts):
// chữ chép từng chữ để thẻ "Cài Studio" ở màn Dự án, Cài đặt › Studio và khối nhắc ở trình tạo sách nói cùng một câu.

var STUDIO_WHAT = S.s_studio_bien_truyen_chu_thanh_sach_noi_59542b09
// Thời gian một chương: số đo của dây chuyền trên card 8 GB của máy thử (docs/ANALYSIS_RESEARCH.md)
var STUDIO_NEEDS = S.s_nvidia_tu_8_gb_u00a0_u00a0tai_25_gb_u00a0_7eecc929
var TESTED_GB = 8
var MIN_GB = 6

// ---- studio/studioFit.ts: máy này có đủ để làm sách nói không (NVIDIA từ 8 GB đủ, 6-8 GB chưa thử, dưới 6 GB hay không có card là không) ----
function studioFit(gpu) {
    if (!gpu) {
        const reason = S.s_khong_co_card_do_hoa_nvidia_hay_driver_nvi_a6c48055
        return {level: "no", line: S.s_may_nay_ee46aadd + reason + ".", reason: reason}
    }
    if (!(gpu.memory > 0)) return {level: "maybe", line: "Card " + gpu.name + S.s_chua_doc_duoc_bo_nho_cua_card_chua_biet_co_6aad987d}
    const gb = gpu.memory / Math.pow(2, 30)
    const shown = gpu.name + " (" + Math.round(gb) + " GB)"
    if (gb >= TESTED_GB - 0.5) return {level: "ok", line: "Card " + shown + S.s_du_de_lam_sach_noi_da_thu_tren_card_da727240 + TESTED_GB + " GB)."}
    if (gb >= MIN_GB - 0.5) return {level: "maybe", line: "Card " + shown + S.s_co_the_chay_duoc_nhung_chua_thu_tren_card_68d4fe61 + TESTED_GB + S.s_gb_co_the_cham_cd510682}
    const reason = "card " + shown + S.s_it_bo_nho_hon_muc_toi_thieu_f038c1c3 + MIN_GB + " GB"
    return {level: "no", line: "Card " + shown + S.s_it_bo_nho_hon_muc_toi_thieu_d079c3f4 + MIN_GB + " GB.", reason: reason}
}
/** Câu nói thật khi máy không làm sách nói được - MỘT câu cho trình tạo sách, bước cuối và thẻ Cài Studio. */
function noStudioLine(reason) { return S.s_may_nay_khong_lam_sach_noi_duoc_d4aa86af + reason + S.s_ban_van_nghe_ngay_moi_sach_8376f422 }

// ---- tình trạng từ /api/app ----
/** `info.studio` -> {missing, update, repair, action}: tên nút dẫn tới thẻ Studio ở màn Dự án (useStudioMissing). */
function studioMissing(studio) {
    const update = Boolean(studio && studio.installed && studio.outdated)
    const repair = Boolean(update && studio.damaged)
    return {
        missing: Boolean(studio && (!studio.installed || studio.outdated)),
        update: update, repair: repair,
        action: repair ? S.s_sua_studio_2f99394d : update ? S.s_cap_nhat_studio_b3acc7e7 : S.s_cai_studio_5fdd3bd9
    }
}

// ---- tình trạng từ /api/studio/setup ----
/** Thẻ ở màn Dự án: hiện khi app đóng gói thiếu / cũ Studio (StudioSetupCard `needed`). */
function cardNeeded(info) { return Boolean(info && info.studio && (!info.studio.installed || info.studio.outdated)) }
function damagedOf(status) { return (status && status.damaged) || [] }
function isRepair(status) { return Boolean(status.installed) && damagedOf(status).length > 0 }
function isUpdate(status) { return Boolean(status.installed) && (status.outdated || []).length > 0 }
function staleOf(status) {
    const damaged = damagedOf(status)
    return (status.outdated || []).filter(function(label) { return damaged.indexOf(label) < 0 })
}
function started(status) { return (status.steps || []).some(function(step) { return step.done }) }
function currentStep(status) {
    const steps = status.steps || []
    for (let i = 0; i < steps.length; ++i) if (steps[i].id === status.step) return steps[i]
    return null
}
function progressOf(status) { return status.progress && status.progress.total > 0 ? status.progress.done / status.progress.total : -1 }
function cardTitle(status) { return isRepair(status) ? S.s_sua_studio_2f99394d : isUpdate(status) ? S.s_cap_nhat_studio_b3acc7e7 : S.s_cai_studio_5fdd3bd9 }
function cardLine(status) {
    if (isRepair(status)) return S.s_tai_lai_eb29b90a + damagedOf(status).concat(staleOf(status)).join(", ") + S.s_sach_giu_nguyen_4f087c0c
    if (isUpdate(status)) return S.s_can_cap_nhat_1655056f + status.outdated.join(", ") + S.s_sach_giu_nguyen_4f087c0c
    return STUDIO_NEEDS
}
/** Nút chính của thẻ theo tình trạng: {kind: "cancel" | "cancelOld" | "wait" | "unfit" | "go", text}. */
function cardButton(status, fit) {
    if (status.running) return {kind: "cancel", text: S.s_dung_11554138}
    if (status.leftover) return status.leftover.orphan ? {kind: "cancelOld", text: S.s_dung_luot_cu_98c3e5d1} : {kind: "wait", text: S.s_cai_tiep_f4243054}
    if (fit && fit.level === "no") return {kind: "unfit", text: S.s_van_cai_ef098464}
    return {kind: "go", text: isRepair(status) ? S.s_sua_studio_2f99394d : isUpdate(status) ? S.s_cap_nhat_studio_b3acc7e7 : started(status) ? S.s_cai_tiep_f4243054 : S.s_cai_studio_5fdd3bd9}
}

var OFFLINE = /getaddrinfo failed|\[Errno 11001\]|WinError 11001|WinError 10051|WinError 10060|Network is unreachable|Temporary failure in name resolution|Name or service not known|timed out|Connection (?:aborted|reset)|RemoteDisconnected|IncompleteRead/i
/** Lỗi dừng dở của bước "Cài Studio": mất mạng nói bằng lời người nghe và chỉ việc làm tiếp; nguyên văn ở `detail` cho "Chi tiết". */
function friendlySetupError(raw) {
    const detail = String(raw).trim()
    if (OFFLINE.test(detail)) return {summary: S.s_mat_mang_giua_chung_bam_cai_tiep_de_lam_ti_c7e5dddf, detail: detail}
    return {summary: detail, detail: ""}
}
function clock(seconds) {
    if (!seconds) return S.s_truoc_22e6f96e
    const date = new Date(seconds * 1000)
    return (date.getHours() < 10 ? "0" : "") + date.getHours() + ":" + (date.getMinutes() < 10 ? "0" : "") + date.getMinutes()
}
function leftoverLine(leftover) {
    const when = clock(leftover.since)
    return leftover.orphan
        ? S.s_luot_cai_luc_f7b49d0c + when + S.s_lan_mo_app_truoc_van_con_chay_ngam_ban_cho_0515b464
        : S.s_mot_cua_so_abook_khac_dang_cai_studio_tu_d0368be3 + when + S.s_ban_dong_no_hoac_cho_no_xong_roi_bam_cai_t_8a3284aa
}
