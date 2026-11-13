.import "UiStrings.js" as S
.pragma library
.import "ImportQueue.js" as Queue

// Hàm thuần của "Tìm trong sách" (listen/findText.ts + findStatus của FindInBook.tsx): khớp không phân biệt hoa thường và dấu trên CHỮ GỐC của sách,
// đoạn trích quanh chỗ khớp để tô đậm, câu nói tình hình tìm. Chữ một chương chia đoạn như màn đọc (ChapterReader dùng chung `paragraphs`), nên chỉ số
// đoạn của kết quả là chỗ màn đọc mở tới. Việc đi qua các chương (nạp gộp, nhường luồng) nằm ở FindInBook.qml.

// Ít nhất chừng này ký tự mới tìm: một ký tự khớp gần như mọi câu.
var MIN_QUERY = 2
// Số kết quả giữ để hiện; số chương xin trong một lần nạp gộp (máy chủ cũng chặn ở 64 - server.py SEARCH_TEXT_CHAPTERS); số chương nạp cùng lúc khi nạp từng chương.
var RESULT_LIMIT = 200
var BULK = 64
var LOT = 4

// model.ts foldVietnamese: bỏ dấu (NFD, dấu kết hợp U+0300-U+036F), đ -> d, chữ thường.
function foldVietnamese(text) {
    return String(text).normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase()
}

// Chữ của một đoạn đã chuẩn hoá để so khớp: mọi kiểu khoảng trắng thành dấu cách - độ dài giữ nguyên từng ký tự, nên chỗ khớp dò lại về chữ gốc được.
function foldedText(text) { return foldVietnamese(text).replace(/\s/g, " ") }

// Từ khoá đã chuẩn hoá ("  Nguyễn   An " -> "nguyen an"); rỗng khi chưa đủ dài.
function foldedQuery(query) {
    const folded = foldedText(query).replace(/ +/g, " ").trim()
    return folded.length >= MIN_QUERY ? folded : ""
}

const charCache = {}
let charCacheSize = 0
// Chuẩn hoá một ký tự (có thể thành rỗng - dấu rời - hay vài ký tự), cùng kết quả với foldedText. Ký tự ASCII đi đường tắt.
function foldChar(character) {
    if (character < "\u0080") return /\s/.test(character) ? " " : character.toLowerCase()
    let folded = charCache[character]
    if (folded === undefined) {
        folded = foldedText(character)
        if (charCacheSize < 4096) { charCache[character] = folded; ++charCacheSize }
    }
    return folded
}

// Đoạn [start, end) của `text` (chữ gốc) ứng với chỗ khớp ở vị trí `at` dài `length` của foldedText(text); lệch độ dài (chữ lạ) thì null.
function originalSpan(text, foldedHaystack, at, length) {
    const starts = []
    let built = ""
    for (let i = 0; i < text.length; i += 1) {
        const folded = foldChar(text[i])
        for (let k = 0; k < folded.length; k += 1) starts.push(i)
        built += folded
    }
    if (built.length !== foldedHaystack.length) return null
    if (at < 0 || at + length > starts.length || length <= 0) return null
    const end = starts[at + length - 1] + 1
    // Dấu rời đứng ngay sau chữ cái cuối vẫn thuộc về chữ ấy.
    let stop = end
    while (stop < text.length && foldChar(text[stop]) === "") stop += 1
    return [starts[at], stop]
}

const BEFORE = 40
const AFTER = 70

// Cắt về ranh giới chữ (khoảng trắng) gần nhất để không bắt đầu / kết thúc giữa một chữ.
function trimLeft(text) {
    const space = text.search(/\s/)
    return space >= 0 && space < 12 ? text.slice(space + 1) : text
}
function trimRight(text) {
    const space = text.search(/\s\S*$/)
    return space >= text.length - 12 && space > 0 ? text.slice(0, space) : text
}

// Đoạn trích {before, match, after} quanh `span`; "…" ở đầu / cuối khi đã cắt. `span` null thì lấy đầu đoạn, không tô.
function snippetOf(text, span) {
    const flat = value => value.replace(/\s+/g, " ")
    if (!span) {
        const head = flat(text).trim()
        return {before: "", match: "", after: head.length > BEFORE + AFTER ? trimRight(head.slice(0, BEFORE + AFTER)) + "…" : head}
    }
    const start = span[0], end = span[1]
    let before = flat(text.slice(Math.max(0, start - BEFORE), start))
    let after = flat(text.slice(end, end + AFTER))
    if (start > BEFORE) before = "…" + trimLeft(before)
    if (end + AFTER < text.length) after = trimRight(after) + "…"
    return {before: before, match: flat(text.slice(start, end)), after: after}
}

// Kết quả đầu tiên của từ khoá trong từng đoạn: [{chapterId, sentence, snippet}]. Dòng ngăn cảnh không tính.
function findInSegments(chapterId, segments, folded, foldedSegments) {
    const hits = []
    segments.forEach(function(segment, sentence) {
        if (segment.sceneBreak) return
        const haystack = foldedSegments && foldedSegments[sentence] !== undefined ? foldedSegments[sentence] : foldedText(segment.text)
        const at = haystack.indexOf(folded)
        if (at < 0) return
        hits.push({chapterId: chapterId, sentence: sentence, snippet: snippetOf(segment.text, originalSpan(segment.text, haystack, at, folded.length))})
    })
    return hits
}

// Các đoạn của một chương như màn đọc chia: chương chỉ có chữ - chữ thô bỏ các dòng đã chọn bỏ (`skip`), tách theo dòng trống; chương có kịch bản - từng
// câu theo thứ tự (chỉ số câu giữ nguyên, câu rỗng vẫn chiếm chỗ để kết quả chỉ đúng câu).
function paragraphs(data, skip) {
    if (typeof data.text === "string") {
        const skipped = skip || []
        return data.text.split(/\r?\n/).filter(line => skipped.indexOf(line.trim()) < 0).join("\n").split(/\n\s*\n/).map(p => p.trim()).filter(Boolean)
            .map(text => ({text: text, sceneBreak: false}))
    }
    return (data.segments || []).map(s => ({text: s.text || "", sceneBreak: Boolean(s.sceneBreak), start: s.start}))
}

// Một chương đã chuẩn hoá (giữ giữa các lần gõ trong một lần mở hộp).
function prepare(segments) { return {segments: segments, folded: segments.map(s => foldedText(s.text))} }

// Cộng kết quả của một chương vào tình hình tìm; `text` null = chương không đọc được.
function scan(state, chapterId, text, needle, limit) {
    state.scanned += 1
    let hits = null
    try { hits = text ? findInSegments(chapterId, text.segments, needle, text.folded) : null } catch (error) { hits = null }
    if (!hits) { state.failed += 1; return }
    state.total += hits.length
    for (const hit of hits) if (state.hits.length < (limit || RESULT_LIMIT)) state.hits.push(hit)
}

function count(value) { return Queue.formatNumber(value) }

// Câu nói tình hình tìm kiếm (FindInBook.tsx findStatus). `progress`: {hits, total, scanned, chapters, failed, done} hay null khi chưa bắt đầu.
function findStatus(query, progress, shown) {
    if (!String(query).trim()) return S.s_go_chu_hay_cau_can_tim_khong_can_go_dau_ho_d1bb2734
    if (!foldedQuery(query)) return S.s_go_it_nhat_090904c8 + MIN_QUERY + S.s_ky_tu_3eb5266e
    if (!progress) return S.s_dang_tim_58376830
    const failed = progress.failed > 0 ? " " + count(progress.failed) + S.s_chuong_chua_doc_duoc_nen_chua_tim_trong_do_1040b0f3 : ""
    if (!progress.done) return S.s_dang_tim_da_xem_8f303989 + count(progress.scanned) + "/" + count(progress.chapters) + S.s_chuong_thay_c2cdfd57 + count(progress.total) + S.s_cho_72c89a7f
    if (progress.total === 0) return S.s_khong_thay_7dda2441 + String(query).trim() + S.s_trong_sach_cda74863 + failed
    const more = progress.total > shown ? S.s_dang_hien_1d87dc08 + count(shown) + S.s_ket_qua_dau_con_c726021c + count(progress.total - shown) + S.s_ket_qua_go_them_chu_de_thu_hep_d6894da8 : ""
    return count(progress.total) + S.s_ket_qua_94a063ce + more + failed
}

function escapeHtml(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;") }

// Đoạn trích dạng RichText, chỗ khớp nền nhấn nhạt + đậm (web <mark>).
function snippetHtml(snippet, soft, ink) {
    return escapeHtml(snippet.before)
        + (snippet.match ? "<span style=\"background-color:" + soft + ";color:" + ink + ";font-weight:600\">" + escapeHtml(snippet.match) + "</span>" : "")
        + escapeHtml(snippet.after)
}
