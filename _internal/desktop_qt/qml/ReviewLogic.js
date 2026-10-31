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
    return item.kind === "failed" ? "Câu này chưa thu được, chưa có gì để nghe" : "Bản thu riêng của câu này đã được dọn sau khi ghép chương - nghe câu này trong chương"
}

// ---- reviewText.ts ----
function notRecordedYet(segments) { return !!segments && segments.recorded === 0 }
function matchPhrase(percent) { return "máy nghe lại khớp " + percent + " với chữ của câu" }
function matchShort(percent) { return "khớp " + percent }
function spokenEditLabel(twins) { return twins > 0 ? "Sửa " + (twins + 1) + " câu" : "Sửa cách đọc" }
function shortcutHint(continuous) { return continuous ? "Đang nghe liền: bấm O nếu ổn, R nếu cần thu lại - rồi sang câu kế" : null }
function heardLine(item) {
    return "Máy nghe ra: “" + item.heard + "”"
}
function showsHeard(item) { return !!item.heard && !sameText(item.heard, item.text) }
function similarityText(item) { return item.similarity === null || item.similarity === undefined ? "" : " · " + matchShort(Studio.formatPercent(item.similarity)) }
function pendingSpokenLine(item, note) {
    return (item.pendingSpoken ? "Sẽ đọc là “" + item.pendingSpoken + "”" : "Sẽ đọc lại đúng chữ sách") + " - " + note + "."
}
function leadLine(data, unrecorded) {
    if (data.pending) return {strong: data.pending + " câu", rest: ": nghe rồi chọn Ổn hoặc Cần thu lại."}
    return {strong: "", rest: unrecorded ? "Chưa có bản thu - sẽ có sau khi thu âm." : "Đã xem hết các câu đáng lo."}
}
function emptyTitle(filter, unrecorded) { return filter === "todo" ? (unrecorded ? "Chưa có bản thu" : "Đã xem hết") : "Chưa đánh dấu câu nào" }
function emptyText(filter, unrecorded) {
    if (filter === "todo") return unrecorded ? "Máy kiểm từng câu ngay khi thu xong; câu nào đáng lo sẽ hiện ở đây." : "Mọi câu đáng lo đều đã có phán quyết."
    return "Nghe một câu rồi bấm Ổn hoặc Cần thu lại."
}
function minorCount(counts) { return ((counts && counts.name) || 0) + ((counts && counts.text) || 0) }
function redoLine(count) { return count + " chương chờ thu lại; sửa chữ ở Kịch bản." }
function loadMoreText(remaining, busy) { return busy ? "Đang tải…" : "Tải tiếp · còn " + (remaining || 0) + " câu" }
function spokenSaved(count) { return count > 1 ? "Đã ghi cách đọc cho " + count + " câu" : "Đã ghi cách đọc câu này" }

// ---- previewText.ts ----
function tryNote(state) {
    if (state.pending) return "Máy đang đọc thử - lần đầu có thể mất vài chục giây"
    if (state.refusal) return state.refusal
    if (state.playing && state.caption) return "Đang phát · " + state.caption
    if (state.caption) return "Đã nghe xong - bấm “Nghe thử” để nghe lại · " + state.caption
    if (state.bookBusy) return "Đang làm sách; bạn thử lại khi xong."
    return null
}
