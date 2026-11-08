.import "UiStrings.js" as S
.pragma library

// Quyết định của người nghe vào sách (studio/decisions.ts, elsewhere.ts, workText.ts): khi nào thay đổi có hiệu lực, lời báo "Hoàn tác", lời báo hai máy
// cùng sửa một chỗ. Chữ chép từng chữ của bản web; WorkStore dựng việc, ở đây không có gì dính tới giao diện.

// ---- decisions.ts ----
// Thay đổi vào sách lúc nào: "start" chưa bắt đầu, "cast" trước khi phân vai khoá, "running" áp ở ranh giới chương kế, "done" phải bấm "Áp dụng thay đổi", "paused" chờ làm tiếp.
function applyWhen(book) {
    if (!book) return "paused"
    if (book.phase === "idle" && !book.running && !book.starting) return "start"
    if (book.phase === "analysis" || (book.phase === "casting" && !book.castLocked)) return "cast"
    if (book.paused) return "paused"
    if (book.running || book.starting) return "running"
    return book.phase === "done" ? "done" : "paused"
}
var PENDING_NOTE = {
    start: S.s_dung_khi_bat_dau_lam_sach_a665a71d,
    cast: S.s_cho_phan_vai_xong_51f41859,
    running: S.s_ap_tu_chuong_sau_8f2706c5,
    done: S.s_bam_ap_dung_thay_doi_o_dau_trang_de_ap_fd47948b,
    paused: S.s_cho_ap_dung_khi_sach_chay_tiep_6f0a3bc6
}
function pendingNote(book) { return PENDING_NOTE[applyWhen(book)] }

// 15 giây: đủ để đọc thông báo rồi mới nhận ra bấm nhầm
var UNDO_MS = 15000

// Thông báo sau khi hoàn tác: nói đúng điều đã xảy ra. `sent`: lần bấm đã gửi sang máy giữ sách - chỉ còn lời nhờ máy ấy rút lại.
function undoToast(restored, sent, message) {
    if (sent) return [S.s_da_nho_may_giu_sach_rut_lai_e7afaa0b, S.s_neu_may_ay_da_dua_vao_sach_ban_se_thay_bao_8fd1a2d0]
    return [restored ? S.s_da_hoan_tac_may_doc_lai_theo_cach_cu_15e82a15 : message ? S.s_da_hoan_tac_fd822d19 + message : S.s_da_hoan_tac_2ef55fca]
}
function undoText(restored, sent, message) { return undoToast(restored, sent, message).join("\n") }

// ---- elsewhere.ts ----
function elsewhereNote(count, was) {
    return {
        title: count > 1 ? count + S.s_cau_vua_duoc_sua_o_may_hay_cua_so_khac_19a69ce5 : S.s_cho_nay_vua_duoc_sua_o_may_hay_cua_so_khac_66af9a6c,
        description: (was ? S.s_truoc_do_dang_la_7c770fd7 + was : S.s_truoc_do_chua_ai_quyet_khac_1f656a59) + S.s_lan_ghi_cua_ban_da_thay_no_40de447d
    }
}
// `seen` gửi kèm lần ghi: điều thẻ / màn này đang thấy cho từng câu (câu không có thì "")
function seenFor(lines, known) {
    const out = {}
    for (const line of lines || []) out[line.stableId] = known && known[line.stableId] !== undefined ? known[line.stableId] : ""
    return out
}
function verdictWord(verdict) { return verdict === "ok" ? S.s_on_742e24ad : verdict === "redo" ? S.s_can_thu_lai_9d482626 : "" }

// ---- workText.ts ----
function sentence(text) { return text.charAt(0).toUpperCase() + text.slice(1) }
// Nhãn nút ("Vai phụ không tên", "Người kể") đứng GIỮA câu thì viết thường chữ đầu. Tên người giữ nguyên.
function midSentence(label) {
    const text = label === null || label === undefined ? "" : String(label)
    return text === S.s_vai_phu_khong_ten_6395f0d2 || text === S.s_nguoi_ke_fd36cd15 ? text.charAt(0).toLowerCase() + text.slice(1) : text
}
