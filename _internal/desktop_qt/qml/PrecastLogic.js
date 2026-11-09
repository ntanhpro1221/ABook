.import "UiStrings.js" as S
.pragma library
.import "WorkLogic.js" as W
.import "CastLogic.js" as Cast

// "Duyệt trước khi thu" (studio/precast.ts, PrecastReview.tsx; webui/precast.py, docs/STUDIO_REVIEW.md): phân tích xong, trước khi thu những chương đầu - lúc sửa còn miễn phí.
// Phần này chỉ chọn, đếm và nói chữ - không gì ở đây sửa chữ truyện. Chữ chép từng chữ của bản web.

var STEPS = ["cast", "names", "lines", "done"]
// Những người nói nhiều nhất: giọng của họ nghe suốt cuốn
var TOP_PEOPLE = 6
var CAST_KINDS = ["gender", "alias", "shared-voice"]
var LINE_KINDS = ["speaker", "caller", "turn", "vocative", "bracket", "unnamed"]
var TITLE = {cast: S.s_nhan_vat_va_giong_52dfc919, names: S.s_cach_doc_ten_1c46e75d, lines: S.s_ai_noi_cau_nay_0e00a5c7, done: S.s_xong_a6f4543a}
var ICON = {cast: "users", names: "spell-check", lines: "message-square-quote", done: "clipboard-check"}

function stepOf(value) { return STEPS.indexOf(value) >= 0 ? value : "cast" }

function openItems(items) { return (items || []).filter(W.isOpenWork) }
// (a) Việc về người và giọng: nam hay nữ, một người hai tên, hai người chung giọng. Giữ thứ tự lợi / lần bấm của hộp việc.
function castItems(items) { return openItems(items).filter(function(item) { return CAST_KINDS.indexOf(item.kind) >= 0 }) }
// (b) Cách đọc tên máy tự đoán - tên máy kém chắc nhất trước, cùng mức thì tên gặp nhiều câu hơn trước
function nameItems(items) {
    return openItems(items).filter(function(item) { return item.kind === "pronunciation" })
        .sort(function(a, b) { return (b.doubt - a.doubt) || (b.affected - a.affected) })
}
// (c) "Ai nói câu này" kém chắc ở các chương sắp thu - thu xong chương ấy thì sửa phải thu lại
function lineItems(items, upcoming) {
    return openItems(items).filter(function(item) {
        return LINE_KINDS.indexOf(item.kind) >= 0 && (item.chapters || []).some(function(id) { return upcoming.indexOf(id) >= 0 })
    })
}
function upcomingIds(view) { return view && view.upcoming ? view.upcoming.map(function(chapter) { return chapter.id }) : [] }
// Khoá các thẻ việc nằm trong màn duyệt: {khoá: true}. Tab "Duyệt trước khi thu" đếm chúng, "Việc cần duyệt" đếm phần còn lại.
function keys(items, upcoming) {
    const out = {}
    for (const list of [castItems(items), nameItems(items), lineItems(items, upcoming)]) for (const item of list) out[item.key] = true
    return out
}
function keyCount(map) { return map ? Object.keys(map).length : 0 }
function lineCount(items) { return items.reduce(function(total, item) { return total + item.affected }, 0) }

// Chapter range uses the same arrow as the web; app fonts supply the glyph.
function chapterRange(chapters) {
    if (!chapters || !chapters.length) return ""
    const first = chapters[0].title, last = chapters[chapters.length - 1].title
    return chapters.length === 1 ? first : first + " → " + last
}
// Sửa tới đâu thì miễn phí
function freeNote(view) {
    return view && view.recordedThrough
        ? S.s_da_thu_toi_1742ddd2 + view.recordedThrough.title + S.s_sua_o_chuong_sau_do_khong_phai_thu_lai_sua_fabeab60
        : S.s_chua_thu_chuong_nao_sua_bay_gio_khong_phai_e0dc8283
}

// ---- chữ của màn ----
function stepCounts(castCards, nameCards, lineCards, people) {
    return {
        cast: castCards.length ? castCards.length + S.s_viec_1c50ca93 : people + S.s_nguoi_dfc3c5c7,
        names: nameCards.length ? nameCards.length + S.s_ten_0fd957e9 : S.s_on_01d34073,
        lines: lineCards.length ? lineCount(lineCards) + S.s_cau_b07e1008 : S.s_on_01d34073,
        done: ""
    }
}
function castIntro(people) { return S.s_nghe_va_chinh_giong_cho_b5f5cadd + people + S.s_nhan_vat_noi_nhieu_nhat_a302caa8 }
function doubtLine(count) { return count + S.s_viec_ve_nguoi_va_giong_681679b6 }   // mảnh sau "Máy chưa chắc" (FlowDetail thêm dấu ngăn)
function namesIntro(count) {
    return count ? S.s_nghe_va_sua_aea8d99f + count + S.s_cach_doc_ten_ten_kem_chac_o_tren_8ab646a0 : S.s_xem_va_sua_cach_doc_tung_ten_o_danh_sach_d_efbb8f8e
}
function linesIntro(lineCards, view, range) {
    const head = lineCards.length
        ? Cast.formatNumber(lineCount(lineCards)) + S.s_cau_may_chua_chac_ai_noi_o_79bf2e57 + (range || S.s_nhung_chuong_sap_thu_969d3947) + S.s_cac_chuong_thu_dau_tien_236b3489
        : (view.upcoming || []).length ? S.s_khong_co_cau_nghi_ngo_o_c53551ac + range : S.s_da_thu_moi_chuong_52c1b8d5
    return head + S.s_cac_chuong_sau_xem_o_viec_can_duyet_9a7b13dc
}
function doneText(book) {
    return book.precast && book.precast.held ? S.s_da_ghi_lai_bam_thu_am_de_lam_tiep_0f63f737
        : book.running ? S.s_sua_nao_cung_da_ghi_lai_may_ap_o_chuong_ke_7b639271
        : S.s_sua_nao_cung_da_ghi_lai_may_ap_khi_sach_ch_eb78b798
}
var HELD_NOTE = S.s_sach_dang_cho_ban_duyet_duyet_xong_bam_thu_f9900395
var INTRO = S.s_duyet_nhanh_truoc_khi_thu_co_the_bo_qua_tu_d3a2f0a0
var TWIN_NOTE = S.s_cung_ten_voi_nguoi_khac_trong_sach_mot_ngu_e99f281d
var NOT_READY = S.s_man_duyet_mo_duoc_khi_may_da_phan_tich_xon_1220ed63

// Công tắc "Duyệt trước khi thu"
function waitHint(book) {
    const precast = book.precast || {}
    return precast.announcedAt ? S.s_phan_tich_da_xong_muon_dung_thi_bam_tam_du_73416c6b
        : precast.wait ? S.s_dung_sau_phan_tich_de_ban_duyet_roi_bam_th_0ca451d3
        : S.s_phan_tich_xong_thi_thu_luon_duyet_luc_nao_1f91e9f9
}

// Dải mời trên trang dự án
function bannerTitle(held) { return held ? S.s_phan_tich_xong_sach_dang_cho_ban_duyet_4df5357f : S.s_phan_tich_xong_duyet_truoc_khi_thu_86b704d6 }
var BANNER_TEXT = S.s_duyet_giong_ten_va_nguoi_noi_truoc_de_tran_fcbf5c99
// Dải mời hiện khi: phân tích xong, đang không ở màn duyệt, và sách đang chờ duyệt hay chưa thu xong chương nào
// Lời mời "Phân tích xong - duyệt trước khi thu?" (usePrecastInvites của PrecastReview.tsx, precastInvites của precast.ts): một lần cho mỗi mốc Studio báo
// (`announcedAt`), chỉ khi còn đúng lúc - sách đang được giữ chờ duyệt, hay chưa thu xong chương nào. `seen(id)`: mốc đã mời của cuốn ấy.
function canReview(book) { return Boolean(book.precast && book.precast.ready) && book.phase !== "done" }
function invites(books, seen) {
    return (books || []).filter(function(book) {
        const at = book.precast ? book.precast.announcedAt : 0
        if (!at || !canReview(book)) return false
        if (!book.precast.held && book.chapters.completed > 0) return false
        return seen(book.id) !== String(at)
    })
}
function inviteText(book) { return book.precast && book.precast.held ? "“" + book.title + S.s_dang_cho_ban_duyet_ef81de57 : "“" + book.title + S.s_da_phan_tich_xong_4edb6015 }
function bannerShown(book, tab) {
    return Boolean(book.precast && book.precast.ready) && book.phase !== "done" && tab !== "precast"
        && (Boolean(book.precast.held) || book.chapters.completed === 0)
}
