.import "UiStrings.js" as S
.pragma library
.import "StudioLogic.js" as Studio

// Tab Nhân vật, mục "Cách đọc tên" (studio/NameReadings.tsx, readingReach.ts, sharedReadings.tsx) và hộp thư thay đổi từ điện thoại (PhoneEdits.tsx): tìm tên, sửa lạc quan,
// lời của dòng, câu "chữ ấy chạm tới bao nhiêu câu", cách đọc chung, lời kể lần gửi gần đây. Chữ chép từng chữ của bản web.

var PAGE = 30
// So tên không phân biệt hoa thường, dấu, gạch nối hay khoảng trắng: "hen" thấy "Hên-cơ", "dac lat" thấy "Đác-lát"
function fold(text) {
    return String(text).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/đ/g, "d").replace(/[\s\-‐-―]/g, "")
}
// Danh sách sau khi lưu `spokenForm` cho `item` - đúng điều máy chủ sẽ trả: cách đọc mới là "chờ áp dụng"; trùng cách đang đọc là "giữ". Tên CHƯA có trong danh sách thì chờ máy chủ nhận.
function withReading(data, item, spokenForm) {
    const keep = spokenForm === item.spoken
    const updated = Object.assign({}, item, {requested: keep ? null : spokenForm, byListener: item.byListener || keep})
    if (!data.items.some(function(entry) { return entry.surface === item.surface })) return data
    return Object.assign({}, data, {items: data.items.map(function(entry) { return entry.surface === item.surface ? updated : entry })})
}
function found(items, typed) {
    const needle = fold(typed)
    if (!needle) return items
    return items.filter(function(item) { return fold(item.surface).indexOf(needle) >= 0 || fold(item.requested !== null && item.requested !== undefined ? item.requested : item.spoken).indexOf(needle) >= 0 })
}
// Gõ đúng một chữ liền nhau mà KHÔNG khớp tên nào thì mời thêm cách đọc cho nó
function single(typed) { return /^\S{1,80}$/.test(typed) }
function freshItem(surface) { return {surface: surface, spoken: "", byListener: false, lines: 0, requested: null, example: null} }
function countedNames(items) { return items.filter(function(item) { return item.lines > 0 }).length }
function heading(analyzed, counted) {
    return (analyzed ? Studio.formatNumber(counted) + S.s_ten_trong_phan_nay_d7a30000 : S.s_chua_phan_tich_ten_hien_ra_sau_buoc_ay_32656b4c)
}
var INTRO = S.s_nghe_va_sua_cach_doc_ten_cau_da_thu_co_ten_957bce51
function noMatch(typed) { return S.s_khong_khop_be597abb + typed + S.s_dung_them_cach_doc_cho_mot_tu_khac_a96aa798 }
function moreNames(count) { return S.s_xem_them_58c3f515 + Studio.formatNumber(count) + S.s_ten_0fd957e9 }
function unseenLine(count) { return Studio.formatNumber(count) + S.s_ten_khac_cua_cuon_khong_co_cau_nao_trong_p_f3b0713b }

// Dòng nhỏ dưới tên: "12 câu · đã chọn" / "chưa phân tích tới" / cách đọc đang chờ áp
function rowStatus(item, analyzed, fresh, reach, shared) {
    let base
    if (fresh) base = reach ? reachSummary(reach) : S.s_khong_co_trong_danh_sach_may_doc_theo_chu_935ca799
    else if (!analyzed && !item.lines) base = S.s_chua_phan_tich_toi_34530fdc
    else base = Studio.formatNumber(item.lines) + S.s_cau_u00a0_u00a0_fbf05e92 + (item.never ? S.s_may_khong_dung_duoc_cach_doc_nay_ky_hieu_2038583b : item.byListener ? S.s_da_chon_a0788df6 : item.spoken ? S.s_may_doan_7217169e : S.s_chua_co_trong_sach_5fecd5a8)
    return base + (shared ? S.s_u00a0_u00a0dung_chung_7982c97c : "")
}
function waitingPart(item) { return item.requested ? S.s_u00a0_u00a0cho_ap_dung_3abf3f09 + item.requested + "”" : "" }
function editLabel(item, fresh) { return (fresh ? S.s_them_dd92626f : S.s_sua_d4e07603) + S.s_cach_doc_90952f06 + item.surface }
function sampleLabel(item) { return S.s_nghe_cau_co_fff39f88 + item.surface + ": " + item.example.text }
function addLabel(item, fresh) { return fresh ? S.s_doc_3edddc37 + item.surface + "”" : S.s_sua_d4e07603 }

// ---- readingReach.ts ----
function where(reach) {
    const named = reach.chapters.slice(0, 3).map(function(chapter) { return chapter.title || S.s_chuong_f4f8b331 + chapter.chapterId })
    const more = reach.chapters.length - named.length
    return named.length ? S.s_u00a0_u00a0o_0f268159 + named.join(", ") + (more > 0 ? S.s_va_79e3d3b1 + more + S.s_chuong_nua_21d52b35 : "") : ""
}
function neverText(surface) {
    return S.s_may_doc_ky_hieu_trong_a13b0999 + surface + S.s_thanh_mot_cho_ngung_truoc_khi_tra_cach_doc_eca2ddab
}
function reachSummary(reach, later) {
    if (reach.never) return (reach.lines ? S.s_co_41db9112 + reach.lines + S.s_cau_co_chu_nay_nhung_m_719f5bcd : "M") + S.s_ay_khong_dung_duoc_cach_doc_cho_chu_co_ky_760f06cc
    if (!reach.lines) return S.s_chua_co_cau_nao_co_chu_nay_cach_doc_se_duo_2d730bc4
    const cost = reach.recorded ? reach.recorded + S.s_cau_da_thu_se_duoc_thu_lai_5fe9480b + (later ? " " + later : "") : S.s_chua_thu_cau_nao_nen_khong_phai_thu_lai_79ed2712
    const blocked = reach.blocked ? " (" + reach.blocked + S.s_cau_khac_khong_dung_duoc_vi_ky_hieu_15e1f699 : ""
    return reach.reached + S.s_cau_co_chu_nay_u00a0_u00a0_a6c879d7 + cost + where(reach) + blocked
}

// ---- Lưu một cách đọc (EditReading) ----
// Cách đọc đang lưu nếu chỉ khác hoa thường (không thành một thay đổi bắt thu lại các câu)
function asStored(item, text) {
    const lower = text.toLocaleLowerCase("vi")
    for (const saved of [item.requested, item.spoken]) if (saved && saved.toLocaleLowerCase("vi") === lower) return saved
    return text
}
function seenSpoken(item) { return item.requested !== null && item.requested !== undefined ? item.requested : (item.byListener ? item.spoken : "") }
function savedBack(item, everywhere) {
    return (item.requested ? S.s_tro_lai_cach_doc_cho_ap_truoc_do_11658168 + Studio.shownReading(item.requested) + "”."
        : item.spoken ? "“" + item.surface + S.s_lai_doc_la_fbb29ef1 + Studio.shownReading(item.spoken) + "”."
        : S.s_da_bo_cach_doc_vua_them_cho_2b673caf + item.surface + "”.") + (everywhere ? S.s_da_bo_khoi_cach_doc_chung_76683f71 : "")
}
function savedToast(item, spokenForm) {
    return spokenForm === item.spoken ? S.s_giu_cach_doc_fac907c0 + Studio.shownReading(spokenForm) + "”" : S.s_da_ghi_a2accbdb + item.surface + S.s_doc_la_4c516fb0 + spokenForm + "”"
}

// ---- Cách đọc chung (sharedReadings.tsx) ----
function sharedEntry(entries, surface, reading) {
    const key = String(surface).toLocaleLowerCase("vi")
    return (entries || []).find(function(entry) { return entry.surface.toLocaleLowerCase("vi") === key && (reading === undefined || reading === null || entry.spokenForm === reading) })
}
function offerLine(entries) {
    const shown = entries.slice(0, 3).map(function(entry) {
        return entry.current ? entry.surface + ": “" + Studio.shownReading(entry.current) + "” → “" + Studio.shownReading(entry.spokenForm) + "”" : entry.surface + " → “" + Studio.shownReading(entry.spokenForm) + "”"
    }).join(", ")
    return S.s_cach_doc_chung_khac_cach_cuon_nay_dang_doc_82c45e55 + shown + (entries.length > 3 ? S.s_va_231e8fb6 + (entries.length - 3) + S.s_ten_khac_53211f28 : "")
}

// ---- PhoneEdits.tsx ----
function describePush(push) {
    const parts = []
    if (push.applied) parts.push(push.applied + S.s_thay_doi_da_ap_2527227c)
    if (push.requests) parts.push(push.requests + S.s_viec_da_thanh_yeu_cau_e5e4d971)
    if (push.waiting) parts.push(push.waiting + S.s_viec_dang_cho_duyet_041191e2)
    if (push.skipped) parts.push(push.skipped + S.s_khong_con_cho_trong_sach_bo_qua_61910675)
    return push.name + "\u00a0·\u00a0" + Studio.formatWhen(push.at) + ": " + (parts.join(", ") || S.s_khong_co_gi_moi_40f1e53d)
}
function applyNote(skipped, held, dropped) {
    const names = dropped || []
    const which = names.length ? ": " + names.slice(0, 3).join("; ") + (names.length > 3 ? S.s_va_d2f4f022 + (names.length - 3) + S.s_viec_nua_4f452578 : "") : ""
    return [
        skipped ? skipped + S.s_viec_khong_con_khop_voi_sach_nen_bi_bo_qua_ce62428f + which + "." : "",
        held ? held + S.s_viec_may_nay_da_doi_khac_sau_do_van_cho_ba_58fe603c : ""
    ].filter(Boolean).join(" ")
}
function inboxHeading(waiting) { return S.s_yeu_cau_thiet_bi_26f11a4f + (waiting ? " (" + waiting + S.s_viec_cho_duyet_ba42de47 : "") }
function skippedCount(devices) { return (devices || []).reduce(function(sum, device) { return sum + device.items.length }, 0) }
// Biểu tượng của một việc từ điện thoại (KIND_ICON của ApplyChanges.tsx; "alias" = nối hai tên)
var KIND_ICON = {pronunciation: "book-open-check", speaker: "user-round", line: "audio-lines", voice: "mic-vocal", retake: "refresh-cw", alias: "link-2"}
function kindIcon(kind) { return KIND_ICON[kind] || "check" }
