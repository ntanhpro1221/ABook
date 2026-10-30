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
    start: "dùng khi bắt đầu làm sách",
    cast: "chờ phân vai xong",
    running: "áp từ chương sau",
    done: "bấm “Áp dụng thay đổi” ở đầu trang để áp",
    paused: "chờ áp dụng khi sách chạy tiếp"
}
function pendingNote(book) { return PENDING_NOTE[applyWhen(book)] }

// 15 giây: đủ để đọc thông báo rồi mới nhận ra bấm nhầm
var UNDO_MS = 15000

// Thông báo sau khi hoàn tác: nói đúng điều đã xảy ra. `sent`: lần bấm đã gửi sang máy giữ sách - chỉ còn lời nhờ máy ấy rút lại.
function undoToast(restored, sent, message) {
    if (sent) return ["Đã nhờ máy giữ sách rút lại", "Nếu máy ấy đã đưa vào sách, bạn sẽ thấy báo ở đây và cần chọn lại ở máy đó."]
    return [restored ? "Đã hoàn tác - máy đọc lại theo cách cũ" : message ? "Đã hoàn tác. " + message : "Đã hoàn tác"]
}
function undoText(restored, sent, message) { return undoToast(restored, sent, message).join("\n") }

// ---- elsewhere.ts ----
function elsewhereNote(count, was) {
    return {
        title: count > 1 ? count + " câu vừa được sửa ở máy hay cửa sổ khác" : "Chỗ này vừa được sửa ở máy hay cửa sổ khác",
        description: (was ? "Trước đó đang là " + was : "Trước đó chưa ai quyết khác") + " - lần ghi của bạn đã thay nó."
    }
}
// `seen` gửi kèm lần ghi: điều thẻ / màn này đang thấy cho từng câu (câu không có thì "")
function seenFor(lines, known) {
    const out = {}
    for (const line of lines || []) out[line.stableId] = known && known[line.stableId] !== undefined ? known[line.stableId] : ""
    return out
}
function verdictWord(verdict) { return verdict === "ok" ? "“Ổn”" : verdict === "redo" ? "“Cần thu lại”" : "" }

// ---- workText.ts ----
function sentence(text) { return text.charAt(0).toUpperCase() + text.slice(1) }
// Nhãn nút ("Vai phụ không tên", "Người kể") đứng GIỮA câu thì viết thường chữ đầu. Tên người giữ nguyên.
function midSentence(label) {
    const text = label === null || label === undefined ? "" : String(label)
    return text === "Vai phụ không tên" || text === "Người kể" ? text.charAt(0).toLowerCase() + text.slice(1) : text
}
