.pragma library
.import "HistoryLogic.js" as History

// Phần thuần của "Hồ sơ nghe" ở trang sách (RecordPicker / singleRecordActions / MoveTarget của listen/BookScreen.tsx, records của desktop/httpSource.ts):
// việc có trong menu, chữ của hộp, lời gửi lên máy chủ, lời báo sau khi xong. Chữ giữ đúng từng chữ của bản web.

// Hộp "Nghe lại từ đầu (hồ sơ mới)" mở sẵn tên gợi ý
function newDialog(book) {
    return {kind: "create", name: "Lần nghe " + ((book.records || []).length + 1)}
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
        {key: "create", label: "Hồ sơ mới", icon: "plus", dialog: newDialog(book)},
        {key: "move", label: "Chuyển hồ sơ", icon: "arrow-right-left", dialog: {kind: "move", name: name}},
        {key: "rename", label: "Đổi tên hồ sơ…", icon: "text-cursor-input", dialog: {kind: "rename", name: name}},
        {key: "delete", label: "Xoá hồ sơ…", icon: "trash", dialog: {kind: "delete", name: name}, danger: true}
    ]
}

// Menu của nút "Hồ sơ nghe:" (nhiều hồ sơ): đầu menu một dòng giải thích, rồi mỗi hồ sơ, rồi bốn việc
var PICKER_NOTE = "Mỗi hồ sơ giữ chỗ nghe, lịch sử riêng."
function pickerActions(book) {
    const active = activeRecord(book)
    const name = active ? active.name : ""
    return [
        {key: "create", label: "Hồ sơ mới", icon: "plus", dialog: newDialog(book)},
        {key: "rename", label: "Đổi tên hồ sơ này…", icon: "text-cursor-input", dialog: {kind: "rename", name: name}},
        {key: "move", label: "Chuyển sang cuốn khác…", icon: "arrow-right-left", dialog: {kind: "move", name: name}},
        {key: "delete", label: "Xoá hồ sơ này…", icon: "trash", dialog: {kind: "delete", name: name}, danger: true}
    ]
}

// Dòng phụ dưới tên một hồ sơ: "Chương 3 · 12:04 · nghe gần nhất hôm qua" / "chưa nghe"
function recordLine(book, record, now) {
    let where = ""
    if (record.last) {
        const found = (book.chapters || []).filter(chapter => chapter.id === record.last.chapterId)[0]
        where = (found ? found.title : "Chương") + " · " + History.formatClock(record.last.seconds) + " · "
    }
    return where + (record.updatedAt ? "nghe gần nhất " + History.dayLabel(record.updatedAt, now).toLowerCase() : "chưa nghe")
}

// ---- hộp thoại ------------------------------------------------------------------------------------------------------------
function dialogTitle(dialog, active) {
    const name = active ? active.name : ""
    if (dialog.kind === "create") return "Nghe lại từ đầu"
    if (dialog.kind === "rename") return "Đổi tên hồ sơ"
    if (dialog.kind === "move") return "Chuyển hồ sơ “" + name + "” sang cuốn khác"
    return "Xoá hồ sơ “" + name + "”?"
}

function dialogDescription(dialog, recordCount) {
    if (dialog.kind === "create") return "Hồ sơ mới nghe từ đầu; hồ sơ cũ vẫn giữ nguyên."
    if (dialog.kind === "move")
        return "Chỗ nghe, lịch sử đi theo hồ sơ sang cuốn kia." + (recordCount > 1 ? " Cuốn này chuyển sang hồ sơ nghe gần nhất còn lại." : " Cuốn này sẽ như chưa nghe lần nào.")
    if (dialog.kind === "delete")
        return "Chỗ nghe, lịch sử của hồ sơ này mất hẳn trên mọi máy. Sách giữ nguyên"
            + (recordCount > 1 ? " - cuốn chuyển sang hồ sơ nghe gần nhất còn lại." : "; đây là hồ sơ duy nhất nên cuốn sẽ như chưa nghe lần nào.")
    return ""
}

function confirmLabel(kind) {
    return kind === "create" ? "Tạo và nghe từ đầu" : kind === "delete" ? "Xoá hồ sơ" : kind === "move" ? "Chuyển" : "Lưu"
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
    if (kind === "create") return "Hồ sơ mới “" + (String(dialog.name || "").trim() || "không tên") + "” - nghe từ chương đầu"
    if (kind === "activate") return "Đang dùng hồ sơ “" + record.name + "”"
    if (kind === "rename") return "Đã đổi tên hồ sơ"
    if (kind === "delete") return "Đã xoá hồ sơ “" + active.name + "”"
    return "Đã chuyển hồ sơ “" + active.name + "” sang “" + dialog.target.title + "”"
}

// Chương đầu nghe được (nghe lại từ đầu bằng hồ sơ mới)
function firstPlayable(chapters) {
    return (chapters || []).filter(chapter => chapter.available || chapter.speech === true)[0]
}
