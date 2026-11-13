.import "UiStrings.js" as S
.pragma library
.import "HistoryLogic.js" as History

// Phần thuần của "Hồ sơ nghe" ở trang sách (RecordPicker / singleRecordActions / MoveTarget của listen/BookScreen.tsx, records của desktop/httpSource.ts):
// việc có trong menu, chữ của hộp, lời gửi lên máy chủ, lời báo sau khi xong. Chữ giữ đúng từng chữ của bản web.

// Hộp "Nghe lại từ đầu (hồ sơ mới)" mở sẵn tên gợi ý
function newDialog(book) {
    return {kind: "create", name: S.s_lan_nghe_c5f2dfe8 + ((book.records || []).length + 1)}
}

function activeRecord(book) { return (book.records || []).filter(record => record.active)[0] }

// Cuốn có nhiều hồ sơ: nút "Hồ sơ nghe: {tên}" (hiện khi có ít nhất 2 hồ sơ và một hồ sơ đang dùng)
function hasPicker(book) { return (book.records || []).length > 1 && activeRecord(book) !== undefined }

// Việc với hồ sơ nghe khi cuốn chỉ có MỘT hồ sơ (không có nút "Hồ sơ nghe:"): menu "Thêm" liệt kê các việc này.
// `danger`: nằm cuối menu, dưới vạch ngăn.
function singleActions(book) {
    const records = book.records || []
    if (records.length !== 1) return []
    const name = records[0].name
    return [
        {key: "create", label: S.s_ho_so_moi_5dfda9aa, icon: "plus", dialog: newDialog(book)},
        {key: "move", label: S.s_chuyen_ho_so_a1c66184, icon: "arrow-right-left", dialog: {kind: "move", name: name}},
        {key: "rename", label: S.s_doi_ten_ho_so_92440dab, icon: "text-cursor-input", dialog: {kind: "rename", name: name}},
        {key: "delete", label: S.s_xoa_ho_so_38a06d83, icon: "trash", dialog: {kind: "delete", name: name}, danger: true}
    ]
}

// Menu của nút "Hồ sơ nghe:" (nhiều hồ sơ): đầu menu một dòng giải thích, rồi mỗi hồ sơ, rồi bốn việc
var PICKER_NOTE = S.s_moi_ho_so_giu_cho_nghe_lich_su_rieng_c3195597
function pickerActions(book) {
    const active = activeRecord(book)
    const name = active ? active.name : ""
    return [
        {key: "create", label: S.s_ho_so_moi_5dfda9aa, icon: "plus", dialog: newDialog(book)},
        {key: "rename", label: S.s_doi_ten_ho_so_nay_30b6b56f, icon: "text-cursor-input", dialog: {kind: "rename", name: name}},
        {key: "move", label: S.s_chuyen_sang_cuon_khac_0ddcf455, icon: "arrow-right-left", dialog: {kind: "move", name: name}},
        {key: "delete", label: S.s_xoa_ho_so_nay_27fc6264, icon: "trash", dialog: {kind: "delete", name: name}, danger: true}
    ]
}

// Dòng phụ dưới tên một hồ sơ: "Chương 3 · 12:04 · nghe gần nhất hôm qua" / "chưa nghe"
function recordLine(book, record, now) {
    let where = ""
    if (record.last) {
        const found = (book.chapters || []).filter(chapter => chapter.id === record.last.chapterId)[0]
        where = (found ? found.title : S.s_chuong_2d157977) + "\u00a0·\u00a0" + History.formatClock(record.last.seconds) + "\u00a0·\u00a0"
    }
    return where + (record.updatedAt ? S.s_nghe_gan_nhat_a3ee466b + History.dayLabel(record.updatedAt, now).toLowerCase() : S.s_chua_nghe_2d5b1cbe)
}

// ---- hộp thoại ------------------------------------------------------------------------------------------------------------
function dialogTitle(dialog, active) {
    const name = active ? active.name : ""
    if (dialog.kind === "create") return S.s_nghe_lai_tu_dau_e251d632
    if (dialog.kind === "rename") return S.s_doi_ten_ho_so_92440dab
    if (dialog.kind === "move") return S.s_chuyen_ho_so_7c2f34e0 + name + S.s_sang_cuon_khac_741d5ffa
    return S.s_xoa_ho_so_6629c57a + name + "”?"
}

function dialogDescription(dialog, recordCount) {
    if (dialog.kind === "create") return S.s_ho_so_moi_nghe_tu_dau_ho_so_cu_van_giu_ngu_38f1a4a4
    if (dialog.kind === "move")
        return S.s_cho_nghe_lich_su_di_theo_ho_so_sang_cuon_k_f25e60d4 + (recordCount > 1 ? S.s_cuon_nay_chuyen_sang_ho_so_nghe_gan_nhat_c_93f8e93a : S.s_cuon_nay_se_nhu_chua_nghe_lan_nao_bae846d0)
    if (dialog.kind === "delete")
        return S.s_cho_nghe_lich_su_cua_ho_so_nay_mat_han_tre_d2b64d84
            + (recordCount > 1 ? S.s_cuon_chuyen_sang_ho_so_nghe_gan_nhat_con_l_8cdb3e30 : S.s_day_la_ho_so_duy_nhat_nen_cuon_se_nhu_chua_75e8b48a)
    return ""
}

function confirmLabel(kind) {
    return kind === "create" ? S.s_tao_va_nghe_ee442c79 : kind === "delete" ? S.s_xoa_ho_so_38a06d83 : kind === "move" ? S.s_chuyen_c35a0ca1 : S.s_luu_e91f26c0
}

// Nút chính của hộp dùng được chưa: đổi tên cần tên, chuyển cần chọn cuốn nhận
function canConfirm(dialog) {
    if (dialog.kind === "rename") return String(dialog.name || "").trim() !== ""
    if (dialog.kind === "move") return Boolean(dialog.target)
    return true
}

// Chọn cuốn nhận hồ sơ: mọi cuốn trong thư viện trừ cuốn này
function moveTargets(library, bookId) {
    return (library || []).filter(item => item.id !== bookId).map(item => ({value: item.id, label: item.title}))
}

// ---- gửi lên máy chủ (records của desktop/httpSource.ts) ------------------------------------------------------------------
function base(bookId) { return "/api/listen/books/" + bookId + "/records" }

// {method, path, body} cho việc của hộp (`dialog`) hay của một hồ sơ trong menu (kind "activate", `record`)
function request(bookId, kind, active, dialog, record) {
    if (kind === "create") return {method: "POST", path: base(bookId), body: {name: String(dialog.name || "").trim()}}
    if (kind === "activate") return {method: "POST", path: base(bookId) + "/" + record.id + "/activate", body: null}
    if (kind === "rename") return {method: "PUT", path: base(bookId) + "/" + active.id, body: {name: String(dialog.name || "").trim()}}
    if (kind === "delete") return {method: "DELETE", path: base(bookId) + "/" + active.id, body: null}
    return {method: "POST", path: base(bookId) + "/" + active.id + "/move", body: {book: dialog.target.id}}
}

// Lời báo khi xong
function doneMessage(kind, active, dialog, record) {
    if (kind === "create") return S.s_ho_so_moi_73f39686 + (String(dialog.name || "").trim() || S.s_khong_ten_7a5bff7f) + S.s_nghe_tu_chuong_dau_88eab044
    if (kind === "activate") return S.s_dang_dung_ho_so_179c4a9a + record.name + "”"
    if (kind === "rename") return S.s_da_doi_ten_ho_so_543ec6a6
    if (kind === "delete") return S.s_da_xoa_ho_so_25ce98d9 + active.name + "”"
    return S.s_da_chuyen_ho_so_2348b1db + active.name + "” sang “" + dialog.target.title + "”"
}

// Chương đầu nghe được (nghe lại từ đầu bằng hồ sơ mới)
function firstPlayable(chapters) {
    return (chapters || []).filter(chapter => chapter.available || chapter.speech === true)[0]
}
