.import "UiStrings.js" as S
.pragma library
.import "WorkLogic.js" as Work
.import "StudioLogic.js" as Studio

// Tab "Cần nghe lại" (studio/ReviewQueue.tsx, reviewText.ts) và nút "Nghe thử" một cách đọc (TryReading.tsx, previewText.ts): câu máy không chắc, phán quyết, chữ
// của hàng, đường nghe một câu, lời của nút nghe thử. Chữ chép từng chữ của bản web.

// Loại câu -> màu chữ của dòng lý do (mức nặng nói bằng màu, không bằng viên chữ riêng)
function reasonTone(kind) { return kind === "failed" ? "danger" : kind === "unverified" ? "warning" : "muted" }

// Câu đã có cách xử lý: phán quyết, hay chữ đem đọc mới đang chờ áp
function handled(item) { return !!item.verdict || (item.pendingSpoken !== null && item.pendingSpoken !== undefined) }
// Cùng chữ, bỏ qua dấu câu và hoa thường: “Tách tách tách.” và “Tách tách tách!” là một câu tượng thanh
function letters(text) {
    let out = ""
    for (const ch of String(text).toLowerCase()) out += Work.isWordChar(ch) ? ch : " "
    return out.replace(/\s+/g, " ").trim()
}
function sameText(left, right) { return letters(left) === letters(right) }
function twinsOf(items, item) {
    return items.filter(function(other) { return other.stableId !== item.stableId && other.textSha256 && sameText(other.text, item.text) })
}

// Đường nghe một câu: bản thu riêng, hay đúng đoạn ấy trong file chương; null = chưa có gì để nghe. `route(path)` = đường qua máy tính đã ghép (nếu có).
function clipOf(item, bookId, route) {
    if (item.playable) return {src: route("/media/books/" + bookId + "/samples/" + item.segmentId)}
    if (item.chapterClip) return {src: route("/media/books/" + bookId + "/chapters/" + item.chapterId), start: item.chapterClip.start, end: item.chapterClip.end}
    return null
}
function unplayableText(item) {
    return item.kind === "failed" ? S.s_cau_nay_chua_thu_duoc_chua_co_gi_de_nghe_3e5fa33a : S.s_ban_thu_rieng_cua_cau_nay_da_duoc_don_sau_552e64b0
}

// ---- reviewText.ts ----
function notRecordedYet(segments) { return !!segments && segments.recorded === 0 }
function matchPhrase(percent) { return S.s_may_nghe_lai_khop_979c637f + percent + S.s_voi_chu_cua_cau_dfe84142 }
function matchShort(percent) { return S.s_khop_4cfe8500 + percent }
function spokenEditLabel(twins) { return twins > 0 ? S.s_sua_d5f3503d + (twins + 1) + S.s_cau_b07e1008 : S.s_sua_cach_doc_d67b7a7b }
function shortcutHint(continuous) { return continuous ? S.s_dang_nghe_lien_bam_o_neu_on_r_neu_can_thu_4e3d0d8d : null }
function heardLine(item) {
    return S.s_may_nghe_ra_31219589 + item.heard + "”"
}
function showsHeard(item) { return !!item.heard && !sameText(item.heard, item.text) }
function similarityText(item) { return item.similarity === null || item.similarity === undefined ? "" : "\u00a0·\u00a0" + matchShort(Studio.formatPercent(item.similarity)) }
function pendingSpokenLine(item, note) {
    return (item.pendingSpoken ? S.s_se_doc_la_a0124031 + item.pendingSpoken + "”" : S.s_se_doc_lai_dung_chu_sach_32abc746) + " - " + note + "."
}
function leadLine(data, unrecorded) {
    if (data.pending) return {strong: data.pending + S.s_cau_b07e1008, rest: S.s_nghe_roi_chon_on_hoac_can_thu_lai_1f69221d}
    return {strong: "", rest: unrecorded ? S.s_chua_co_ban_thu_se_co_sau_khi_thu_am_c61d063f : S.s_da_xem_het_cac_cau_dang_lo_c91d08e4}
}
function emptyTitle(filter, unrecorded) { return filter === "todo" ? (unrecorded ? S.s_chua_co_ban_thu_9897618d : S.s_da_xem_het_75fa60d3) : S.s_chua_danh_dau_cau_nao_6b8e8be3 }
function emptyText(filter, unrecorded) {
    if (filter === "todo") return unrecorded ? S.s_may_kiem_tung_cau_ngay_khi_thu_xong_cau_na_3fe114af : S.s_moi_cau_dang_lo_deu_da_co_phan_quyet_7c2be09b
    return S.s_nghe_mot_cau_roi_bam_on_hoac_can_thu_lai_c3dfde28
}
function minorCount(counts) { return ((counts && counts.name) || 0) + ((counts && counts.text) || 0) }
function redoLine(count) { return count + S.s_chuong_cho_thu_lai_sua_chu_o_kich_ban_11e7f43e }
function loadMoreText(remaining, busy) { return busy ? S.s_dang_tai_465b1987 : S.s_tai_tiep_u00a0_u00a0con_0ebab88c + (remaining || 0) + S.s_cau_b07e1008 }
function spokenSaved(count) { return count > 1 ? S.s_da_ghi_cach_doc_cho_4566132d + count + S.s_cau_b07e1008 : S.s_da_ghi_cach_doc_cau_nay_0db96b25 }

// ---- previewText.ts ----
function tryNote(state) {
    if (state.pending) return S.s_may_dang_doc_thu_lan_dau_co_the_mat_vai_ch_51a539dc
    if (state.refusal) return state.refusal
    if (state.playing && state.caption) return S.s_dang_phat_u00a0_u00a0_6c88d17d + state.caption
    if (state.caption) return S.s_da_nghe_xong_bam_nghe_thu_de_nghe_lai_u00a_9e8cc7ab + state.caption
    if (state.bookBusy) return S.s_dang_lam_sach_ban_thu_lai_khi_xong_4414af8b
    return null
}
