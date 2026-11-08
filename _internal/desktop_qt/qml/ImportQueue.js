.import "UiStrings.js" as S
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
        return {name: name, error: S.s_chua_ho_tro_bf077876 + last.toLowerCase() + S.s_chon_epub_docx_pdf_co_chu_txt_hoac_abook_26d1adb6}
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
        if (item.opened) return {id: id, name: item.name, state: "opened", note: S.s_da_mo_617b34d1}
        number += 1
        return {id: id, name: item.name, path: item.path, state: "waiting", number: number}
    })
}

function queueTotal(items) { return items.filter(item => item.number !== undefined).length }

function queueLabel(items, id) {
    const item = items.find(entry => entry.id === id)
    return !item || item.number === undefined ? "" : S.s_sach_cf2dd275 + item.number + "/" + queueTotal(items)
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
        summary.added ? S.s_da_them_14852134 + summary.added + S.s_sach_c41b3bde : "",
        summary.opened ? S.s_da_mo_2e7c79a1 + summary.opened + S.s_file_sach_679b88e4 : "",
        summary.existing ? summary.existing + S.s_cuon_da_co_trong_thu_vien_c132fc69 : "",
        summary.skipped ? S.s_bo_qua_cea5e01e + summary.skipped + S.s_cuon_421f8494 : "",
        summary.failed ? summary.failed + S.s_file_chua_doc_duoc_a21a3450 : ""
    ].filter(part => part !== "")
    const text = parts.join("\u00a0·\u00a0")
    return text ? text[0].toUpperCase() + text.slice(1) : S.s_khong_them_cuon_nao_0fb1d747
}

// Cuốn mà dòng "Đang …" ở: đang thêm cả lô thì cuốn ĐANG THÊM (khớp tên), không thì cuốn đang xem.
function queueFocus(items, currentId, working) {
    if (!working) return {id: currentId, adding: false}
    const match = items.find(item => item.state === "waiting" && item.name === working)
    return {id: match ? match.id : currentId, adding: true}
}

var STATE_TEXT = {added: S.s_da_them_e26b2fcb, existing: S.s_da_co_trong_thu_vien_3bb6eeb4, skipped: S.s_bo_qua_c67ba288, opened: S.s_da_mo_617b34d1, error: S.s_chua_doc_duoc_ad95887c}

// Dòng nói tình trạng của một hàng trong danh sách file.
function rowSaid(item, focus) {
    if (item.state === "waiting") return item.id === focus.id ? (focus.adding ? S.s_dang_them_457edcc3 : S.s_dang_xem_42cc3b08) : S.s_cho_8de7e9a5
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
    const base = S.s_tach_theo_5f3e6530 + formatNumber(headings) + S.s_dong_chuong_n_cc00807e
    return offer > headings ? base + S.s_them_phan_mo_dau_dccbd9ba + formatNumber(offer) + S.s_chuong_be1b3067 : base
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

function where(chapters) { return chapters.length === 1 ? S.s_chuong_f4f8b331 + chapters[0] : chapters.length + S.s_chuong_9e6a01dc }

// ---- Chú thích ------------------------------------------------------------------------------------------------------------
var NO_FOOTNOTES = {hideMarks: false, notes: ""}

// Lựa chọn gửi đi; undefined khi chưa tích gì.
function footnotesToSend(choice) { return choice.hideMarks || choice.notes ? {hideMarks: choice.hideMarks, notes: choice.notes} : undefined }

function footnoteSummary(offer) {
    const first = offer.examples && offer.examples.length ? offer.examples[0] : null
    return {
        title: S.s_tim_thay_52e7add3 + formatNumber(offer.found) + S.s_chu_thich_trong_sach_26cae6a5,
        example: first ? S.s_vi_du_364d1ccf + first.mark + S.s_co_loi_chu_68675904 + first.note + "”" : ""
    }
}

// ---- Mở file sách (.abook / .abookproj) -----------------------------------------------------------------------------------
// Lời báo sau khi máy chủ mở một file sách (useOpenedBook của desktop/App.tsx + shared/editsKept.ts). Toast của bản web là Api.notice ở đây: tiêu đề, nếu có
// lời phụ thì nối sau " - ".
var OPENED_SAID = {
    "new": S.s_da_them_e26b2fcb, existing: S.s_sach_da_co_24cc49e2, updated: S.s_da_cap_nhat_9ca1e681, older: S.s_file_nay_cu_hon_ban_dang_co_afc4d520, conflict: S.s_file_nay_co_ban_thu_khac_6036a451,
    repaired: S.s_da_khoi_phuc_file_037a8437, project: S.s_sach_cua_studio_b54d45e2, studio: S.s_da_mo_du_an_ef7db505
}

function said(title, note) { return note ? title + " - " + note : title }

function workshopMergeNote(merge) {
    if (!merge || (!merge.merged && !merge.kept)) return null
    const taken = merge.merged ? S.s_da_gop_c3d15783 + merge.merged + S.s_sua_tu_file_681b4e09 : ""
    const kept = merge.kept ? merge.kept + S.s_sua_giu_ban_cua_may_nay_vi_moi_hon_7dd147cc : ""
    return [taken, kept].filter(part => part !== "").join(", ") + "."
}

function brokenMusicNote(broken) {
    if (!broken || broken <= 0) return null
    return broken === 1 ? S.s_1_bai_nhac_nen_trong_sach_bi_hong_doan_ay_0a679d5d
                        : broken + S.s_bai_nhac_nen_trong_sach_bi_hong_nhung_doan_1864261a
}

// {ok, notice, id, studio}: `ok` false = không mở được (lỗi / thiếu mã); `studio` mở Studio thay vì trang sách; không có `id` = chỉ báo, không chuyển trang.
function openedOutcome(result) {
    if (!result) return {ok: false, notice: ""}
    if (result.error) return {ok: false, notice: said(S.s_chua_mo_duoc_file_sach_2cdc21ae, result.file ? result.file + ": " + result.error : result.error)}
    if (!result.id) return {ok: false, notice: ""}
    const how = result.how || "new"
    if (how === "older" || how === "conflict")
        return {ok: true, notice: said(OPENED_SAID[how], S.s_chinh_sua_va_cho_nghe_cua_ban_van_duoc_giu_287783a6)}
    if (how === "studio") {
        const lost = result.missingSources || 0
        return {ok: true, id: result.id, studio: true,
                notice: said(OPENED_SAID.studio, lost ? S.s_thieu_8f1e7ea0 + lost + S.s_file_nguon_chuong_thu_lai_chuong_ay_thi_ca_c813f633 : "")}
    }
    const kept = result.merge && result.merge.kept > 0 ? S.s_da_cap_nhat_sach_giu_nguyen_578dc3b4 + result.merge.kept + S.s_chinh_sua_cua_ban_ab7109a7 : null
    const adopted = result.merge && result.merge.adopted ? S.s_da_lay_7e7e7a15 + result.merge.adopted + S.s_thay_doi_tu_file_5db945f8 : null
    const title = workshopMergeNote(result.workshop) || kept || adopted || OPENED_SAID[how] || OPENED_SAID["new"]
    const note = [result.otherTitle ? S.s_ten_trong_file_la_c98d30b4 + result.otherTitle + S.s_khac_ten_dang_dung_a0b3b466 : "", brokenMusicNote(result.brokenMusic) || ""]
        .filter(part => part !== "").join(" ")
    // Cuốn mới: AddBook hỏi tên sách để nói “Đã thêm “tên”” (`named`); tên chưa đọc được thì còn “Đã thêm”.
    if (how === "new" && title === OPENED_SAID["new"]) return {ok: true, id: result.id, notice: said(title, note), named: {title: title, note: note}}
    return {ok: true, id: result.id, notice: said(title, note)}
}
