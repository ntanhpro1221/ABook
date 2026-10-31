.pragma library

// Hàm thuần của "Thêm sách" (listen/importQueue.ts + listen/textImport.ts + ReadingSuggestions.tsx của bản web): hàng nhiều file, chương đã tích,
// tên đã đổi, gợi ý bỏ dòng. AddBook.qml giữ trạng thái; ở đây không có gì dính tới giao diện. Chữ giữ đúng từng chữ của bản web.

// ---- Định dạng ------------------------------------------------------------------------------------------------------------
// Intl.NumberFormat("vi-VN"): ngăn nhóm nghìn bằng dấu chấm.
function formatNumber(value) {
    const rounded = Math.round(Number(value) || 0)
    return String(Math.abs(rounded)).replace(/\B(?=(\d{3})+(?!\d))/g, ".") .replace(/^/, rounded < 0 ? "-" : "")
}

function fileName(path) {
    const clean = String(path).trim()
    const parts = clean.split(/[\\/]/).filter(p => p !== "")
    return parts.length ? parts[parts.length - 1] : clean
}

function cleanPath(value) {
    return String(value).trim().replace(/^["']+|["']+$/g, "").trim()
}

// ---- File sách ------------------------------------------------------------------------------------------------------------
function isBookFile(path) { return /\.abook(proj)?$/i.test(String(path).trim()) }

var BOOK_TYPES = /\.(epub|docx|pdf|txt|abook|abookproj)$/i

// Một đường dẫn trên máy (hộp chọn file, hay file kéo thả vào cửa sổ app) thành thứ đã chọn. Không có đuôi = có thể là thư mục TXT.
function itemFromPath(path) {
    const clean = String(path).trim()
    const name = fileName(clean)
    const dot = name.lastIndexOf(".")
    const last = name.indexOf(".") >= 0 ? name.slice(dot) : ""
    if (last && !BOOK_TYPES.test(name))
        return {name: name, error: "Chưa hỗ trợ " + last.toLowerCase() + ". Chọn EPUB, DOCX, PDF có chữ, TXT hoặc .abook."}
    return {name: name, path: clean}
}

// ---- Hàng nhiều file ------------------------------------------------------------------------------------------------------
// File sách .abook / .abookproj xếp CUỐI (mở chúng đưa app sang trang sách, nên làm sau khi xong các cuốn cần xem trước).
function buildQueue(picked) {
    const entries = picked.map((item, index) => ({item: item, index: index}))
    const book = item => item.path !== undefined && isBookFile(item.path)
    entries.sort((a, b) => (book(a.item) ? 1 : 0) - (book(b.item) ? 1 : 0) || a.index - b.index)
    let number = 0
    return entries.map((entry, id) => {
        const item = entry.item
        if (item.error !== undefined) return {id: id, name: item.name, state: "error", note: item.error}
        if (item.opened) return {id: id, name: item.name, state: "opened", note: "Đã mở"}
        number += 1
        return {id: id, name: item.name, path: item.path, state: "waiting", number: number}
    })
}

function queueTotal(items) { return items.filter(item => item.number !== undefined).length }

function queueLabel(items, id) {
    const item = items.find(entry => entry.id === id)
    return !item || item.number === undefined ? "" : "Sách " + item.number + "/" + queueTotal(items)
}

function nextWaiting(items) { return items.find(item => item.state === "waiting") }

function waitingAfter(items, id) { return items.filter(item => item.state === "waiting" && item.id !== id) }

function settle(items, id, patch) {
    return items.map(item => item.id === id ? Object.assign({}, item, {note: undefined}, patch) : item)
}

// Cuốn còn chờ mà bỏ đi thì không được thêm (không tính file sách .abook: chúng không cần xem trước).
function unfinished(items) {
    return items ? items.filter(item => item.state === "waiting" && item.path !== undefined && !isBookFile(item.path)).length : 0
}

function summarize(items) {
    const count = state => items.filter(item => item.state === state).length
    return {added: count("added"), existing: count("existing"), skipped: count("skipped"), failed: count("error"), opened: count("opened")}
}

// "Đã thêm 3 sách · 1 cuốn đã có trong thư viện · 1 file chưa đọc được"
function summaryText(summary) {
    const parts = [
        summary.added ? "Đã thêm " + summary.added + " sách" : "",
        summary.opened ? "đã mở " + summary.opened + " file sách" : "",
        summary.existing ? summary.existing + " cuốn đã có trong thư viện" : "",
        summary.skipped ? "bỏ qua " + summary.skipped + " cuốn" : "",
        summary.failed ? summary.failed + " file chưa đọc được" : ""
    ].filter(part => part !== "")
    const text = parts.join(" · ")
    return text ? text[0].toUpperCase() + text.slice(1) : "Không thêm cuốn nào"
}

// Cuốn mà dòng "Đang …" ở: đang thêm cả lô thì cuốn ĐANG THÊM (khớp tên), không thì cuốn đang xem.
function queueFocus(items, currentId, working) {
    if (!working) return {id: currentId, adding: false}
    const match = items.find(item => item.state === "waiting" && item.name === working)
    return {id: match ? match.id : currentId, adding: true}
}

var STATE_TEXT = {added: "Đã thêm", existing: "Đã có trong thư viện", skipped: "Bỏ qua", opened: "Đã mở", error: "Chưa đọc được"}

// Dòng nói tình trạng của một hàng trong danh sách file.
function rowSaid(item, focus) {
    if (item.state === "waiting") return item.id === focus.id ? (focus.adding ? "Đang thêm" : "Đang xem") : "Chờ"
    return item.note !== undefined && item.note !== "" ? item.note : STATE_TEXT[item.state]
}

// ---- Chương xem trước -----------------------------------------------------------------------------------------------------
var SURE_SPLIT_HEADINGS = 3

function splitIsSure(preview) {
    return Boolean(preview.splitOffer) && (preview.splitHeadings !== undefined && preview.splitHeadings !== null ? preview.splitHeadings : preview.splitOffer) >= SURE_SPLIT_HEADINGS
}

function splitLabel(preview) {
    const offer = preview.splitOffer || 0
    const headings = preview.splitHeadings !== undefined && preview.splitHeadings !== null ? preview.splitHeadings : offer
    const base = "Tách theo " + formatNumber(headings) + " dòng “Chương N”"
    return offer > headings ? base + " (thêm phần Mở đầu - " + formatNumber(offer) + " chương)" : base
}

// Các hàng tích sẵn: mọi hàng trừ mục rất ngắn và phần có vẻ không phải truyện (máy gửi `included: false`).
function defaultPicked(chapters) { return chapters.filter(c => c.included !== false).map(c => c.index) }

function sameSet(a, b) {
    if (a.length !== b.length) return false
    const keys = {}
    for (const n of a) keys[n] = true
    return b.every(n => keys[n])
}

function isDefaultPick(chapters, picked) { return sameSet(defaultPicked(chapters), picked) }

function sameRows(a, b) {
    return a.length === b.length && a.every((row, at) => row.title === b[at].title && row.included === b[at].included)
}

// Người dùng gõ `value` làm tên mới cho hàng: rỗng hay đúng tên cũ là giữ tên cũ (bỏ đổi tên).
function renameChapter(names, chapter, value) {
    const next = Object.assign({}, names)
    const clean = String(value).trim().replace(/\s+/g, " ")
    if (!clean || clean === chapter.title) delete next[chapter.index]
    else next[chapter.index] = clean
    return next
}

function pickedTotals(chapters, picked) {
    const rows = chapters.filter(c => picked.indexOf(c.index) >= 0)
    return {chapters: rows.length, words: rows.reduce((sum, c) => sum + (c.words || 0), 0)}
}

// Lúc thêm LUÔN gửi danh sách tường minh các hàng đang tích (kể cả khi đúng mặc định), kèm tên mới nếu có.
function chapterPicks(chapters, picked, names) {
    return chapters.filter(c => picked.indexOf(c.index) >= 0).map(c => {
        const title = names[c.index] ? String(names[c.index]).trim() : ""
        return title && title !== c.title ? {index: c.index, title: title} : {index: c.index}
    })
}

// ---- Gợi ý bỏ dòng ghi công -----------------------------------------------------------------------------------------------
// Gợi ý chỉ của các hàng đang tích, đánh số lại thành MÃ CHƯƠNG trong sách sẽ thêm (hàng thứ k trong số hàng tích = chương k), gộp theo dòng.
function groupSuggestions(suggestions, chapters, picked) {
    const ids = {}
    let count = 0
    for (const chapter of chapters) if (picked.indexOf(chapter.index) >= 0) ids[chapter.index] = ++count
    const groups = []
    for (const item of suggestions || []) {
        const id = ids[item.chapter]
        if (id === undefined) continue
        let group = groups.find(g => g.line === item.line)
        if (!group) { group = {line: item.line, chapters: []}; groups.push(group) }
        group.chapters.push(id)
    }
    return groups
}

function where(chapters) { return chapters.length === 1 ? "chương " + chapters[0] : chapters.length + " chương" }

// ---- Chú thích ------------------------------------------------------------------------------------------------------------
var NO_FOOTNOTES = {hideMarks: false, notes: ""}

// Lựa chọn gửi đi; undefined khi chưa tích gì.
function footnotesToSend(choice) { return choice.hideMarks || choice.notes ? {hideMarks: choice.hideMarks, notes: choice.notes} : undefined }

function footnoteSummary(offer) {
    const first = offer.examples && offer.examples.length ? offer.examples[0] : null
    return {
        title: "Tìm thấy " + formatNumber(offer.found) + " chú thích trong sách",
        example: first ? "Ví dụ: “" + first.mark + "” có lời chú “" + first.note + "”" : ""
    }
}

// ---- Mở file sách (.abook / .abookproj) -----------------------------------------------------------------------------------
// Lời báo sau khi máy chủ mở một file sách (useOpenedBook của desktop/App.tsx + shared/editsKept.ts). Toast của bản web là Api.notice ở đây: tiêu đề, nếu có
// lời phụ thì nối sau " - ".
var OPENED_SAID = {
    "new": "Đã thêm", existing: "Sách đã có", updated: "Đã cập nhật", older: "File này cũ hơn bản đang có", conflict: "File này có bản thu khác",
    repaired: "Đã khôi phục file", project: "Sách của Studio", studio: "Đã mở dự án"
}

function said(title, note) { return note ? title + " - " + note : title }

function workshopMergeNote(merge) {
    if (!merge || (!merge.merged && !merge.kept)) return null
    const taken = merge.merged ? "Đã gộp " + merge.merged + " sửa từ file" : ""
    const kept = merge.kept ? merge.kept + " sửa giữ bản của máy này vì mới hơn" : ""
    return [taken, kept].filter(part => part !== "").join(", ") + "."
}

function brokenMusicNote(broken) {
    if (!broken || broken <= 0) return null
    return broken === 1 ? "1 bài nhạc nền trong sách bị hỏng - đoạn ấy sẽ không có nhạc."
                        : broken + " bài nhạc nền trong sách bị hỏng - những đoạn ấy sẽ không có nhạc."
}

// {ok, notice, id, studio}: `ok` false = không mở được (lỗi / thiếu mã); `studio` mở Studio thay vì trang sách; không có `id` = chỉ báo, không chuyển trang.
function openedOutcome(result) {
    if (!result) return {ok: false, notice: ""}
    if (result.error) return {ok: false, notice: said("Chưa mở được file sách", result.file ? result.file + ": " + result.error : result.error)}
    if (!result.id) return {ok: false, notice: ""}
    const how = result.how || "new"
    if (how === "older" || how === "conflict")
        return {ok: true, notice: said(OPENED_SAID[how], "Chỉnh sửa và chỗ nghe của bạn vẫn được giữ.")}
    if (how === "studio") {
        const lost = result.missingSources || 0
        return {ok: true, id: result.id, studio: true,
                notice: said(OPENED_SAID.studio, lost ? "Thiếu " + lost + " file nguồn chương - thu lại chương ấy thì cần chép nguồn vào." : "")}
    }
    const kept = result.merge && result.merge.kept > 0 ? "Đã cập nhật sách - giữ nguyên " + result.merge.kept + " chỉnh sửa của bạn" : null
    const adopted = result.merge && result.merge.adopted ? "Đã lấy " + result.merge.adopted + " thay đổi từ file" : null
    const title = workshopMergeNote(result.workshop) || kept || adopted || OPENED_SAID[how] || OPENED_SAID["new"]
    const note = [result.otherTitle ? "Tên trong file là “" + result.otherTitle + "”, khác tên đang dùng." : "", brokenMusicNote(result.brokenMusic) || ""]
        .filter(part => part !== "").join(" ")
    // Cuốn mới: AddBook hỏi tên sách để nói “Đã thêm “tên”” (`named`); tên chưa đọc được thì còn “Đã thêm”.
    if (how === "new" && title === OPENED_SAID["new"]) return {ok: true, id: result.id, notice: said(title, note), named: {title: title, note: note}}
    return {ok: true, id: result.id, notice: said(title, note)}
}
