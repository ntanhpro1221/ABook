.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size
.import "StudioLogic.js" as Studio
.import "TemplateLogic.js" as Templates

// Phần thuần của trình tạo sách (ui/src/studio/NewProjectScreen.tsx và các file nó dùng: scanState, scanView, credits, narratorChoice, tellerMode, chapterNumbers,
// splitOffer, sourceRef, samePath, volumes, timeEstimate, AnalysisModelPicker): chữ và quy tắc chép từng chữ để hai nền tảng nói cùng một câu.

var PROFILES = [
    {value: "fast", title: S.s_nhanh_c2385879, pace: S.s_nhanh_nhat_3e80ad74, summary: S.s_nghe_thu_mot_truyen_moi_hoac_can_gap_7595a3d8,
     points: [S.s_may_hieu_truyen_theo_tung_doan_dai_mot_lan_e6cda2fb, S.s_soat_co_ban_sau_khi_doc_2e51d472, S.s_doc_lai_toi_da_1_lan_neu_cau_bi_doc_sai_82e58722]},
    {value: "balanced", title: S.s_can_bang_8b88211d, pace: S.s_vua_phai_8c671657, summary: S.s_nghe_hang_ngay_chap_nhan_vai_cau_chua_hoan_2bc0c77a,
     points: [S.s_phan_tich_truyen_day_du_7d2d439e, S.s_soat_co_ban_sau_khi_doc_2e51d472, S.s_doc_lai_toi_da_2_lan_neu_cau_bi_doc_sai_4d15b713]},
    {value: "high_quality", title: S.s_chat_luong_cao_dc7017a7, pace: S.s_cham_nhat_ky_nhat_ff0d4141, summary: S.s_sach_nghe_lai_nhieu_lan_hoac_de_chia_se_c35352d9,
     points: [S.s_ra_lai_cam_xuc_tung_cau_mot_lan_nua_5d40fd1d, S.s_nghe_lai_moi_cau_soat_ky_tung_chu_88b14719, S.s_doc_lai_toi_5_lan_neu_cau_bi_doc_sai_df336644]}
]
var PROFILE_VALUES = ["fast", "balanced", "high_quality"]
// Chọn nhanh số chương cho một đợt - chỉ hiện khi nguồn có nhiều hơn mức nhỏ nhất.
var CHAPTER_LIMITS = [20, 50, 100]
var DEFAULT_LABEL = Templates.DEFAULT_LABEL

/** Chữ của người dùng đưa vào Text.StyledText (tên sách, đường dẫn): thoát <, > và &. */
function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;") }
function profileOf(value) { return PROFILES[PROFILE_VALUES.indexOf(value)] }
function profileTitle(value) { const p = profileOf(value); return p ? p.title : "" }

// ---- nháp ----
function emptyDraft() {
    return {paths: [], excluded: [], title: "", titleEdited: false, narrator: "", firstPerson: "", profile: "high_quality", startNow: true}
}
function cleanPath(value) { return String(value).trim().replace(/^["']+|["']+$/g, "").trim() }
/** Giọng kể mặc định cho sách mới (Cài đặt > Studio): giọng người dùng đặt nếu còn trong danh sách giọng, không thì giọng máy đề xuất. */
function defaultNarrator(voices, preferred) {
    if (!voices || !voices.length) return ""
    for (const voice of voices) if (preferred && voice.name === preferred) return voice.name
    for (const voice of voices) if (voice.recommended) return voice.name
    return voices[0].name
}
function profileFor(preferred) { return PROFILE_VALUES.indexOf(preferred || "") >= 0 ? preferred : "high_quality" }

// ---- scanState.ts ----
function sourcesKey(paths) { return paths.join("\n") }
/** Kết quả đang giữ là của đúng danh sách nguồn hiện tại (hay chưa có nguồn nào thì không có gì để đợi). */
function scanIsCurrent(scanned, paths) { return paths.length === 0 ? true : Boolean(scanned) && scanned.key === sourcesKey(paths) }
/** Nút cuối trình tạo: chờ khi còn đọc nguồn (nói rõ), khoá khi thiếu tên sách hay máy không làm được. */
function createGate(title, reading, unfit) {
    return {disabled: reading || !String(title).trim() || unfit, reading: reading, label: reading ? S.s_dang_doc_nguon_9a3908c6 : ""}
}

/** Lỗi quét: nguồn không đọc được -> {text, subfolders}. */
function scanProblem(result) {
    if (result.errors && result.errors.length) return {text: S.s_chua_mo_duoc_273b1e54 + result.errors[0], subfolders: []}
    if (result.missing && result.missing.length) {
        const first = result.missing[0]
        return {text: isSourceRef(first) ? S.s_khong_tim_thay_6ffd6396 + sourceName(first) + S.s_tren_may_tinh_gui_lai_roi_thu_lan_nua_f28a369b : S.s_khong_tim_thay_6ffd6396 + first + S.s_kiem_tra_lai_duong_dan_10db1a21, subfolders: []}
    }
    return {text: S.s_thu_muc_nay_khong_co_file_txt_hay_epub_doc_9c5a2dff, subfolders: result.subfolders || []}
}

// ---- scanView.ts ----
function matterFiles(files) { return files.filter(function(file) { return Boolean(file.matter) }) }
function unpickedMatter(files, keep) {
    return files.filter(function(file) { return file.matter && keep.indexOf(file.path) < 0 }).map(function(file) { return file.path })
}
/** Mọi chương không vào sách: chương người dùng bỏ tay, và trang phụ chưa tích lại. */
function allExcluded(files, excluded, keep) {
    const seen = {}
    const out = []
    for (const path of excluded.concat(unpickedMatter(files, keep))) if (!seen[path]) { seen[path] = true; out.push(path) }
    return out
}
/** Tích / bỏ tích một trang phụ: tích thì ra khỏi danh sách bỏ tay luôn. Trả {keepMatter, excluded}. */
function keepMatterState(state, path, on) {
    const keep = (state.keepMatter || []).filter(function(item) { return item !== path })
    return on ? {keepMatter: keep.concat([path]), excluded: state.excluded.filter(function(item) { return item !== path })}
              : {keepMatter: keep, excluded: state.excluded}
}
/** Số ước tính của file dài (chỉ đọc phần đầu để đếm): đặt "~" trước số. */
function approx(value, estimated) { return (estimated ? "~" : "") + Studio.formatNumber(value) }

/** Kết quả quét sau khi lọc chương bỏ tay, giới hạn "N chương đầu" (không áp khi chia tập) và tính lại tổng. */
function viewOf(raw, ordered, excludedPaths, limit, splitting) {
    if (!raw) return null
    const skip = {}
    for (const path of excludedPaths) skip[path] = true
    const kept = ordered.filter(function(file) { return !skip[file.path] })
    const files = limit && !splitting ? kept.slice(0, limit) : kept
    let words = 0, audio = 0, estimated = false
    for (const file of files) { words += file.words; audio += file.audioSeconds || 0; if (file.estimated) estimated = true }
    const totals = {chapters: files.length, words: words, audioSeconds: audio}
    if (estimated) totals.estimated = true
    return Object.assign({}, raw, {files: files, totals: totals})
}

// ---- sourceRef.ts / samePath.ts ----
function isSourceRef(source) { return /^(?:up:|ref:)/.test(source) }
/** Tên file / thư mục cuối của nguồn: đường dẫn Windows, đường kiểu "/", hay tham chiếu. */
function sourceName(source) {
    const ref = /^ref:[^:]*:[^:]*:\d+:([\s\S]*)$/.exec(source)
    if (ref) {
        try { return decodeURIComponent(ref[1]) } catch (e) { return ref[1] }
    }
    const body = source.indexOf("up:") === 0 ? source.slice(3) : source
    const parts = body.split(/[\\/]/).filter(Boolean)
    return parts.length ? parts[parts.length - 1] : source
}
function pathKey(path) {
    const slashed = String(path).trim().replace(/\\/g, "/")
    const unc = slashed.indexOf("//") === 0
    const collapsed = slashed.replace(/\/{2,}/g, "/")
    const joined = unc ? "/" + collapsed : collapsed
    const trimmed = joined.length > 1 ? joined.replace(/\/+$/, "") : joined
    return /^[A-Za-z]:(\/|$)|^\/\//.test(trimmed) ? trimmed.toLowerCase() : trimmed
}
function samePath(a, b) { return pathKey(a) === pathKey(b) }

// ---- credits.ts ----
var KEEP_CREDITS = {head: false, tail: false}
/** Đếm trên các chương ĐANG CHỌN (bỏ chương hay giới hạn số chương thì đếm lại). */
function creditSummary(files) {
    const heads = [], tails = []
    let head = 0, tail = 0, chapters = 0
    for (const file of files) {
        const top = file.credits || [], end = file.tailCredits || []
        if (!top.length && !end.length) continue
        head += top.length; tail += end.length; chapters += 1
        for (const line of top) if (heads.length < 3 && heads.indexOf(line) < 0) heads.push(line)
        for (const line of end) if (tails.length < 3 && tails.indexOf(line) < 0) tails.push(line)
    }
    const examples = heads.slice(0, tails.length ? 2 : 3).map(function(line) { return "“" + line + "”" })
        .concat(tails.map(function(line) { return "“" + line + S.s_cuoi_chuong_097818de })).slice(0, 3)
    return {lines: head + tail, head: head, tail: tail, chapters: chapters, examples: examples}
}
function creditKind(credits) {
    if (!credits.tail) return S.s_dong_ghi_cong_acaae945
    if (!credits.head) return S.s_dong_xin_ung_ho_quang_cao_a4165e32
    return S.s_dong_ghi_cong_xin_ung_ho_quang_cao_ffb87b29
}
function creditWhere(credits) {
    if (!credits.tail) return S.s_dong_ghi_cong_nguoi_dich_o_dau_chuong_c94cc054
    if (!credits.head) return S.s_dong_xin_ung_ho_quang_cao_hay_nguon_o_cuoi_e826e333
    return S.s_dong_ghi_cong_o_dau_chuong_hay_dong_xin_un_a0d7e71e
}
function droppedLines(credits, drop) { return (drop.head ? credits.head : 0) + (drop.tail ? credits.tail : 0) }
/** Loại dòng đang được bỏ (để nói "Sẽ bỏ N dòng ghi công khỏi phần đọc"). */
function droppedKind(credits, drop) { return creditKind({head: drop.head ? credits.head : 0, tail: drop.tail ? credits.tail : 0}) }
function creditRows(files, label) {
    return files.filter(function(file) { return ((file.credits || []).length + (file.tailCredits || []).length) > 0 })
        .map(function(file) { return {chapter: label(file), head: file.credits || [], tail: file.tailCredits || []} })
}
function creditLine(line, place, drop) {
    const where = place === "head" ? S.s_dau_chuong_ef996d71 : S.s_cuoi_chuong_f95a0fda
    if (!drop.head && !drop.tail) return {text: "“" + line + "” (" + where + ")", dropped: false}
    return drop[place] ? {text: "“" + line + "” (" + where + S.s_bo_f7c2a1f4, dropped: true} : {text: "“" + line + "” (" + where + S.s_van_doc_48b294c1, dropped: false}
}
/** Dòng cuối chương: "Chương 768" từ dòng đầu file ("Chương 768 - Mô hình…"), không thì tên file - cho dải chương ở bước xác nhận. */
function chapterLabel(file) {
    const head = String(file.firstLine || "").split(/\s[-–—:]\s|[:：]/)[0].trim()
    return head && head.length <= 40 ? head : file.name
}

// ---- narratorChoice.ts ----
function narratorIsAuto(draft, preferred, voices) {
    if (!String(draft.firstPerson).trim() || draft.narratorPicked || draft.seed) return false
    return !(preferred && (voices || []).some(function(voice) { return voice.name === preferred }))
}
function recommendedFor(voices, gender) {
    if (!gender) return ""
    const wanted = gender === "male" ? S.s_nam_22dd59c8 : S.s_nu_e15bc11c
    for (const voice of voices || []) if (voice.recommended && voice.gender === wanted) return voice.name
    return ""
}
/** Chương đổi góc kể được giữ: gợi ý của máy, trừ chương mà tên ấy chính là người kể cả cuốn và chương người dùng bỏ chọn. */
function chosenPovChapters(hint, narrator, off) {
    const book = String(narrator).trim().toUpperCase()
    const out = {}
    for (const chapter of (hint && hint.chapters) || []) if (chapter.name !== book && off.indexOf(chapter.chapter) < 0) out[String(chapter.chapter)] = chapter.name
    return out
}
function povChaptersOf(hint, narrator) {
    const book = String(narrator).trim().toUpperCase()
    return ((hint && hint.chapters) || []).filter(function(chapter) { return chapter.name !== book })
}
/** "Sửa thiết lập": chương nào của gợi ý mà lúc tạo bạn không giữ thì tắt đi; chương giữ thì vẫn bật. */
function povOffFrom(hint, firstPerson, kept) {
    const book = String(firstPerson).trim().toUpperCase()
    return ((hint && hint.chapters) || []).filter(function(chapter) { return chapter.name !== book && !(String(chapter.chapter) in kept) }).map(function(chapter) { return chapter.chapter })
}

// ---- tellerMode.ts ----
var TELLER_TITLE = S.s_nhan_vat_tu_ke_b75121e9
function tellerHint(on) {
    return on ? S.s_nhan_vat_xung_toi_doc_ca_loi_ke_bang_giong_b51f6c3e : S.s_giong_dan_doc_loi_ke_nhan_vat_chi_doc_loi_51b22986
}
function firstPersonGuess(hint) {
    if (!hint) return ""
    if (hint.firstPerson) {
        return hint.chaptersSampled && hint.chaptersWithI
            ? hint.chaptersWithI + "/" + hint.chaptersSampled + S.s_chuong_dau_co_loi_ke_xung_toi_f95b0dc4
            : Math.round(hint.rate * 100) + S.s_doan_loi_ke_co_toi_608f94df
    }
    return S.s_chon_nhan_vat_xung_toi_trong_loi_ke_d47a6c20
}

// ---- chapterNumbers.ts ----
var NUMBER = /(?:chương|chuong|hồi|hoi|chapter|tiết|第)\s*0*(\d{1,5})/i
var BARE = /^0*(\d{1,5})(?!\d)/
function chapterNumber(firstLine, name) {
    const found = NUMBER.exec(firstLine) || NUMBER.exec(name) || BARE.exec(name)
    return found ? Number(found[1]) : null
}
function chapterNumberIssues(files, previousLast) {
    const known = []
    for (const file of files) { const number = chapterNumber(file.firstLine || "", file.name); if (number !== null) known.push({name: file.name, number: number}) }
    // Ít hơn một nửa số file có số chương: truyện không đánh số (EPUB theo tên chương) - không đoán.
    if (known.length < 2 || known.length * 2 < files.length) return []
    const issues = []
    const seen = {}, order = []
    for (const file of known) { if (!seen[file.number]) { seen[file.number] = []; order.push(file.number) } seen[file.number].push(file.name) }
    const duplicates = order.filter(function(number) { return seen[number].length > 1 })
    for (const number of duplicates.slice(0, 3)) {
        const names = seen[number]
        issues.push(S.s_chuong_aad5968e + number + S.s_co_d1231f10 + names.length + " file (" + names.slice(0, 3).join(", ") + S.s_giu_mot_bo_cac_file_kia_5cddf0c1)
    }
    if (duplicates.length > 3) issues.push(S.s_va_c04322b2 + (duplicates.length - 3) + S.s_so_chuong_trung_khac_a8627d97)
    const backwards = [], gaps = []
    for (let index = 1; index < known.length; ++index) {
        const before = known[index - 1].number, here = known[index].number
        if (here < before) backwards.push(S.s_chuong_f4f8b331 + here + S.s_dung_sau_chuong_5385c5b1 + before)
        else if (here > before + 1) gaps.push(here === before + 2 ? S.s_chuong_f4f8b331 + (before + 1) : S.s_chuong_f4f8b331 + (before + 1) + "–" + (here - 1))
    }
    if (backwards.length) issues.push(S.s_thu_tu_lech_603b1a0f + backwards.slice(0, 3).join("; ") + (backwards.length > 3 ? S.s_va_d2f4f022 + (backwards.length - 3) + S.s_cho_khac_e6f6ea90 : "") + S.s_ten_file_xep_khac_so_chuong_47bc7c9e)
    if (gaps.length) issues.push(S.s_co_ve_thieu_e1b304e8 + gaps.slice(0, 4).join(", ") + (gaps.length > 4 ? S.s_va_79e3d3b1 + (gaps.length - 4) + S.s_khoang_khac_9f3ff65c : "") + ".")
    const last = previousLast ? chapterNumber(previousLast, previousLast) : null
    const first = known[0].number
    if (last !== null && first !== last + 1) {
        issues.push(first <= last
            ? S.s_phan_truoc_da_lam_toi_chuong_8f92903c + last + S.s_phan_nay_lai_bat_dau_tu_chuong_2174ede5 + first + S.s_lam_lai_cac_chuong_da_co_1a0e5f5c
            : S.s_phan_truoc_dung_o_chuong_d995cb57 + last + S.s_phan_nay_bat_dau_tu_chuong_6a49a9cb + first + S.s_thieu_chuong_0f452f06 + (last + 1) + (first > last + 2 ? "–" + (first - 1) : "") + ".")
    }
    return issues
}
/** Lời nhắc số chương cho cả trang: khi chia tập thì soát riêng từng tập (mỗi tập đánh số lại từ 1). */
function numberIssues(files, splitting, starts, previousLast) {
    if (splitting && starts) {
        const out = []
        ranges(starts, files.length).forEach(function(part, index) {
            chapterNumberIssues(files.slice(part.start - 1, part.end), index === 0 ? previousLast : undefined).forEach(function(issue) { out.push(S.s_phan_a17569d5 + (index + 1) + ": " + issue) })
        })
        return out
    }
    return chapterNumberIssues(files, previousLast)
}

// ---- splitOffer.ts ----
function sameTitle(a, b) {
    function norm(text) { return String(text).normalize("NFC").toLowerCase().split(/\s+/).filter(Boolean).join(" ") }
    return norm(a) !== "" && norm(a) === norm(b)
}
function splitOutcome(plan, title) {
    const line = plan.titleLine || ""
    return {chapters: plan.chapters, titleAsName: Boolean(line) && sameTitle(line, title), titleStays: Boolean(line)}
}

// ---- volumes.ts ----
var MAX_VOLUMES = 99
var SOURCE_TEXT = {folders: S.s_moi_thu_muc_la_mot_tap_5f476863, epubs: S.s_moi_file_epub_la_mot_tap_42de53c4, headings: S.s_cac_tieu_de_chuong_goi_ten_tap_2ed33746}
function inOrder(files, order) {
    if (!order) return files
    const rank = {}
    order.forEach(function(path, index) { rank[path] = index })
    function of(file) { return rank[file.path] === undefined ? order.length : rank[file.path] }
    return files.map(function(file, at) { return {file: file, at: at} }).sort(function(a, b) { return (of(a.file) - of(b.file)) || (a.at - b.at) }).map(function(item) { return item.file })
}
/** Số chương đầu (từ 1, trong số chương còn chọn) của mỗi tập. */
function startNumbers(ordered, startPaths, excluded) {
    const skip = {}
    for (const path of excluded || []) skip[path] = true
    const number = {}
    let count = 0
    for (const file of ordered) if (!skip[file.path]) number[file.path] = ++count
    const found = {1: true}
    for (const path of startPaths || []) {
        let from = -1
        for (let i = 0; i < ordered.length; ++i) if (ordered[i].path === path) { from = i; break }
        for (let index = from; from >= 0 && index < ordered.length; ++index) {
            const kept = number[ordered[index].path]
            if (kept !== undefined) { found[kept] = true; break }
        }
    }
    return Object.keys(found).map(Number).sort(function(a, b) { return a - b })
}
function ranges(starts, total) {
    return starts.map(function(start, position) {
        const end = (starts[position + 1] !== undefined ? starts[position + 1] : total + 1) - 1
        return {start: start, end: end, chapters: end - start + 1}
    })
}
function moveStart(starts, position, number, total) {
    if (position < 1 || position >= starts.length || Math.floor(number) !== number) return null
    if (number <= starts[position - 1] || number >= (starts[position + 1] !== undefined ? starts[position + 1] : total + 1)) return null
    return starts.map(function(value, index) { return index === position ? number : value })
}
function addStart(starts, number, total) {
    if (Math.floor(number) !== number || number < 2 || number > total || starts.indexOf(number) >= 0 || starts.length >= MAX_VOLUMES) return null
    return starts.concat([number]).sort(function(a, b) { return a - b })
}
function removeStart(starts, position) { return position < 1 ? starts : starts.filter(function(value, index) { return index !== position }) }
function volumeTitles(title, count) {
    const base = String(title).replace(/\s*(?:\(phần\s*\d+\)|[·|:—–-]\s*phần\s*\d+)\s*$/i, "").trim() || String(title).trim()
    const out = []
    for (let i = 0; i < count; ++i) out.push(i === 0 ? String(title).trim() : base + S.s_u00a0_u00a0phan_1a9d9c8e + (i + 1))
    return out
}
/** Thư mục chứa file (cắt ở dấu gạch cuối): đếm số thư mục trong một tập. */
function foldersIn(files) {
    const seen = {}
    let count = 0
    for (const file of files) {
        const path = String(file.path)
        const folder = path.slice(0, Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\")))
        if (!seen[folder]) { seen[folder] = true; count++ }
    }
    return count
}

// ---- timeEstimate.ts ----
var MEASURED_ON = "RTX 5060 Laptop 8 GB"
var ANALYSIS_PER_KILOWORD = 2.1 * 60
var SYNTHESIS_PER_KILOWORD = [2.5 * 60, 3.8 * 60]
var WIDER = {low: 0.6, high: 3}
function matchesMeasured(gpu, analysisModel) { return !analysisModel && Boolean(gpu && /RTX\s*5060/i.test(gpu.name)) }
function estimate(words, chapters, exact) {
    const kilo = words / 1000
    const analysis = kilo * ANALYSIS_PER_KILOWORD
    const low = kilo * SYNTHESIS_PER_KILOWORD[0], high = kilo * SYNTHESIS_PER_KILOWORD[1]
    const scale = exact ? {low: 1, high: 1} : WIDER
    return {analysis: analysis, analysisLow: analysis * scale.low, analysisHigh: analysis * scale.high,
            totalLow: (analysis + low) * scale.low, totalHigh: (analysis + high) * scale.high,
            firstChapter: (analysis + high / Math.max(1, chapters)) * scale.high}
}
function timeBasis(exact) {
    return exact ? S.s_so_tham_khao_do_tren_may_cung_card_4a8c3aa5 + MEASURED_ON
                 : S.s_so_tham_khao_do_tren_may_fdcf624f + MEASURED_ON + S.s_may_cua_ban_co_the_nhanh_hon_hay_cham_hon_a3289a65
}
function lengthRange(low, high) {
    const a = Studio.formatLength(low), b = Studio.formatLength(high)
    return a === b ? S.s_khoang_934859d7 + a : a + " - " + b
}

// ---- AnalysisModelPicker.tsx ----
function modelLabel(name) { return String(name).replace(/:latest$/, "") }
function modelHint(model, defaultSize) {
    const parts = []
    const billions = Number.parseFloat(model.parameters)
    if (isFinite(billions) && /b$/i.test(String(model.parameters).trim())) parts.push(String(Math.round(billions * 10) / 10).replace(".", ",") + S.s_ti_tham_so_fa61447f)
    else if (model.parameters) parts.push(model.parameters)
    if (model.size) {
        parts.push(S.s_khoang_934859d7 + Size.formatSize(model.size) + S.s_bo_nho_card_f09d305c)
        if (defaultSize > 0) {
            if (model.size > defaultSize * 1.3) parts.push(S.s_nang_va_cham_hon_mac_dinh_91d5acea)
            else if (model.size < defaultSize * 0.75) parts.push(S.s_nhe_va_nhanh_hon_mac_dinh_dce4bb68)
        }
    }
    return parts.join("\u00a0·\u00a0")
}
function experimentalLabel(model, defaultSize) {
    const hint = modelHint(model, defaultSize)
    return S.s_ban_thu_nghiem_55f7ee8c + (hint ? "\u00a0·\u00a0" + hint : "")
}
function analysisChoiceLabel(chosen, seedModel) {
    return chosen ? S.s_ban_thu_nghiem_a7572b70 + (seedModel === chosen ? S.s_nhu_phan_truoc_74dc8ee9 : S.s_chi_cuon_nay_eaf5b949) + ")" : S.s_mac_dinh_cua_abook_2fc069a4
}
/** Tên các model dùng được cho một cuốn (mặc định + Ollama đang có), hay null khi chưa biết (chưa tải xong, Ollama tắt). */
function availableModelNames(data) { return data && data.reachable ? [data.default].concat(data.models.map(function(model) { return model.name })) : null }
/** Các lựa chọn của ô "Bộ phân tích truyện": mặc định + các bản khác. Trả {options, others, defaultSize}. */
function modelOptions(data) {
    if (!data || !Array.isArray(data.models)) return {others: [], options: []}
    const others = data.models.filter(function(model) { return modelLabel(model.name) !== modelLabel(data.default) })
    let defaultSize = 0
    for (const model of data.models) if (modelLabel(model.name) === modelLabel(data.default)) defaultSize = model.size || 0
    const options = [{value: "", label: S.s_mac_dinh_khuyen_dung_60a7ae4e}]
    if (others.length) options.push({header: S.s_ban_khac_thu_nghiem_73e6829a})
    others.forEach(function(model, index) { options.push({value: model.name, label: (index + 1) + ". " + experimentalLabel(model, defaultSize)}) })
    return {others: others, options: options, defaultSize: defaultSize}
}

// ---- nối tiếp ----
function carriedText(carries) {
    const n = Studio.formatNumber
    const parts = [
        carries.voices ? S.s_giong_c3af83b2 + n(carries.voices) + S.s_nhan_vat_5f244327 : "",
        carries.pronunciations ? n(carries.pronunciations) + S.s_cach_doc_ten_82e037cc : "",
        carries.pins ? S.s_gioi_tuoi_da_sua_tay_cua_9c51dd17 + n(carries.pins) + S.s_nhan_vat_5f244327 : "",
        carries.aliases ? n(carries.aliases) + S.s_bi_danh_c1f87079 : "",
        carries.names ? n(carries.names) + S.s_ten_nhan_vat_da_doi_2bd21e94 : "",
        carries.bracket ? S.s_quy_uoc_loi_trong_b4f1c558 : ""
    ].filter(Boolean)
    return parts.length ? parts.join("\u00a0·\u00a0") : S.s_nhung_gi_phan_truoc_da_co_84eb2fe7
}

// ---- nháp từ "Sửa thiết lập" / "Làm tiếp" ----
/** GET /api/books/<id>/redo -> nháp điền sẵn (hay null khi sách đã bắt đầu chạy). */
function draftFromRedo(redo, id) {
    const draft = Object.assign(emptyDraft(), {
        paths: redo.paths, title: redo.title, titleEdited: true, narrator: redo.narrator,
        // Giọng do máy chọn lúc tạo thì vẫn là máy chọn, không thành lựa chọn tay.
        narratorPicked: !redo.narratorAuto, firstPerson: redo.firstPerson,
        profile: profileFor(redo.profile),
        dropCredits: {head: Boolean(redo.dropCreditLines), tail: Boolean(redo.dropTailCreditLines)},
        replaces: {id: id, title: redo.title}
    })
    if (redo.firstPersonGender) draft.firstPersonGender = redo.firstPersonGender
    if (redo.tellerMode) draft.tellerMode = true
    if (redo.firstPersonChapters && Object.keys(redo.firstPersonChapters).length) draft.povKept = redo.firstPersonChapters
    if (redo.analysisModel) draft.analysisModel = redo.analysisModel
    if (redo.seedFrom) draft.replaces.seedFrom = redo.seedFrom
    if (redo.analysisInterrupted) draft.replaces.restart = true
    return draft
}
/** GET /api/books/<id>/continuation -> nháp điền sẵn từ phần trước. */
function draftFromContinuation(plan, id) {
    const draft = Object.assign(emptyDraft(), {
        paths: plan.paths, title: plan.title, titleEdited: true, narrator: plan.narrator, firstPerson: plan.firstPerson,
        profile: profileFor(plan.profile),
        seed: {
            id: plan.sourceId || id, title: plan.sourceTitle, clickedTitle: plan.clickedTitle, latestTitle: plan.latestTitle,
            analysisModel: plan.analysisModel, analysisModelMissing: plan.analysisModelMissing, part: plan.part, analyzed: plan.analyzed,
            empty: plan.paths.length === 0, carries: plan.carries, narrator: plan.narrator, folder: plan.folder, lastChapter: plan.lastChapter
        }
    })
    if (plan.analysisModel) draft.analysisModel = plan.analysisModel
    return draft
}

// ---- POST /api/books ----
/** Thân yêu cầu tạo sách - đúng các khoá của bản web. `args`: {draft, files, volumeStarts, povChapters, auto, remote, noStudio, credits}. */
function createBody(args) {
    const draft = args.draft
    const firstPerson = String(draft.firstPerson).trim()
    const body = {
        paths: args.files.map(function(file) { return file.path }),
        title: String(draft.title).trim(),
        profile: draft.profile,
        // Máy chọn giọng dẫn: gửi rỗng - máy chủ đặt giọng cùng giới người kể "tôi" và ghi nhớ đó là lựa chọn của máy.
        narrator: args.auto ? "" : draft.narrator,
        firstPerson: firstPerson
    }
    if (args.volumeStarts.length > 1) body.volumeStarts = args.volumeStarts
    if (firstPerson && draft.firstPersonGender) body.firstPersonGender = draft.firstPersonGender
    if (firstPerson && draft.tellerMode) body.tellerMode = true
    if (Object.keys(args.povChapters).length) body.firstPersonChapters = args.povChapters
    if (draft.seed) body.seedFrom = draft.seed.id
    else if (draft.replaces && draft.replaces.seedFrom) body.seedFrom = draft.replaces.seedFrom
    // Studio từ xa không nói tên đường dẫn nào: chương nguồn là `ref:...` của cuốn cũ, máy tính tự đổi ra file và tự thay cuốn cũ.
    if (draft.replaces) { if (args.remote) body.redoOf = draft.replaces.id; else body.replaces = draft.replaces.id }
    if (draft.analysisModel) body.analysisModel = draft.analysisModel
    // Chỉ khi người dùng đã đồng ý đề xuất - không gửi gì thì sách giữ nguyên nội dung.
    const credits = args.credits
    if (draft.dropCredits && draft.dropCredits.head && credits.head) body.dropCreditLines = true
    if (draft.dropCredits && draft.dropCredits.tail && credits.tail) body.dropTailCreditLines = true
    body.start = Boolean(draft.startNow) && !args.noStudio
    if (draft.precastWait) body.precastWait = true
    return body
}
/** Lời báo sau khi tạo: [tiêu đề, mô tả]. */
function createdText(result, draft, noStudio) {
    const volumes = result.parts ? result.parts.length : 0
    const queued = draft.startNow && !noStudio && result.queued ? S.s_vao_hang_cho_thu_643986c7 + result.queued + ")" : ""
    const head = result.unchanged ? S.s_khong_co_thiet_lap_nao_thay_doi_giu_nguyen_929846eb
        : volumes > 1 ? S.s_da_tao_4057a2eb + volumes + S.s_phan_20f71101
        : draft.replaces && draft.replaces.restart ? S.s_da_lam_lai_sach_tu_dau_6e51eb4c
        : draft.replaces ? S.s_da_tao_lai_sach_voi_thiet_lap_moi_cd546877 : S.s_da_tao_sach_15431889
    return [head + queued, noStudio ? S.s_du_an_cho_toi_khi_studio_cai_xong_roi_bam_9937b79b : ""]
}

// ---- bước xác nhận ----
/** Các hàng "Tóm tắt" (nhãn, giá trị) - chép từ ConfirmStep. */
function summaryRows(a) {
    const n = Studio.formatNumber
    const scan = a.scan
    const option = profileOf(a.profile)
    const exact = matchesMeasured(a.gpu, a.analysisModel)
    const guess = estimate(scan.totals.words, scan.files.length, exact)
    const measured = a.profile === "high_quality" && !a.noStudio
    const rows = [[S.s_chuong_2d157977, scan.files.length + S.s_chuong_u00a0_u00a0_08db5e1d + approx(scan.totals.words, scan.totals.estimated) + S.s_chu_6117d040]]
    if (a.volumes) {
        const names = volumeTitles(a.title, a.volumes.length).map(function(name, index) { return "“" + name + "” (" + n(a.volumes[index].chapters) + S.s_chuong_be1b3067 })
        rows.push([S.s_chia_thanh_b0af0247, a.volumes.length + S.s_phan_d5cacf53 + names.join(", ")])
        rows.push([S.s_cac_phan_sau_c2deb368, a.startNow ? S.s_tu_chay_sau_phan_truoc_giu_giong_va_cach_d_3418c1f0 : S.s_xep_hang_sau_phan_1_giu_giong_va_cach_doc_a149ce8b])
    }
    const dropped = droppedLines(a.credits, a.dropCredits)
    if (dropped) rows.push([droppedKind(a.credits, a.dropCredits).replace(/^d/, "D"), S.s_bo_00ebba58 + n(dropped) + S.s_dong_khoi_phan_doc_5306b53e])
    rows.push([S.s_do_dai_audio_cc51e366, S.s_khoang_934859d7 + Studio.formatLength(scan.totals.audioSeconds)])
    rows.push([S.s_giong_ke_b209f686, a.narratorAuto ? S.s_may_chon_cung_gioi_voi_nguoi_ke_toi_dang_l_6eeb72dc + a.narrator + ")" : a.narrator])
    if (a.firstPerson) rows.push([S.s_nguoi_ke_toi_e2ce42b1, a.firstPersonGender ? a.firstPerson + " (" + (a.firstPersonGender === "female" ? S.s_nu_316c30fd : "nam") + ")" : a.firstPerson])
    if (a.tellerMode) rows.push([S.s_loi_ke_eba0761e, S.s_doc_bang_giong_cua_nguoi_ke_toi_e1d42efd])
    const pov = Object.keys(a.povChapters)
    if (pov.length) rows.push([S.s_chuong_doi_nguoi_ke_88865076, pov.map(function(chapter) { return S.s_chuong_f4f8b331 + chapter + ": " + a.povChapters[chapter] }).join(", ")])
    // "Nối tiếp: phần 2 của …" đọc như nối SAU phần 2 hay LÀ phần 2 đều được - nói thẳng là phần mấy, sau phần nào, và dải chương.
    if (a.seed) {
        rows.push([S.s_la_9d0892e6, S.s_phan_c7559390 + a.seed.part + S.s_cua_285bec9f + a.seed.title + S.s_noi_sau_phan_d101f14b + (a.seed.part - 1) +
            (scan.files.length ? "\u00a0·\u00a0" + chapterLabel(scan.files[0]) + " → " + chapterLabel(scan.files[scan.files.length - 1]) : "")])
    }
    rows.push([S.s_nhan_vat_d4940c17, a.seed ? S.s_giu_d3777f80 + carriedText(a.seed.carries) + S.s_nguoi_moi_duoc_phan_vai_sau_khi_phan_tich_135b0bed : S.s_tu_dong_phan_vai_sau_khi_phan_tich_6530ecf1])
    rows.push([S.s_chat_luong_a12ed26c, option.title])
    // Luôn nói bộ phân tích nào sẽ đọc hiểu truyện - cả khi là mặc định - vì phân tích là bước dài nhất và không ngắt được.
    if (a.analysisModel || a.modelsDefault) rows.push([S.s_bo_phan_tich_truyen_9a52f60b, analysisChoiceLabel(a.analysisModel, a.seed ? a.seed.analysisModel : undefined)])
    if (a.unfit) rows.push([S.s_thoi_gian_lam_ba044b40, S.s_may_nay_khong_lam_sach_noi_duoc_a627fd2a])
    else if (a.noStudio) rows.push([S.s_thoi_gian_lam_ba044b40, S.s_tinh_duoc_khi_studio_da_cai_du_an_cho_toi_4387d301])
    else if (measured) {
        rows.push([S.s_thoi_gian_lam_tham_khao_95d55912, lengthRange(guess.totalLow, guess.totalHigh)])
        rows.push([S.s_chuong_dau_nghe_duoc_sau_tham_khao_2d0bf61e, (exact ? S.s_khoang_18209c07 : S.s_toi_da_khoang_1532dcc6) + " " + Studio.formatLength(guess.firstChapter)])
        rows.push([S.s_so_tham_khao_tu_dau_afcc409b, timeBasis(exact)])
    } else {
        // "Nhanh" chưa có số đo trên máy này - vẫn nói được trần trên thay vì im lặng.
        rows.push([S.s_thoi_gian_lam_ba044b40, S.s_chua_do_cho_che_do_nay_ngan_hon_chat_luong_954558a3 + Studio.formatLength(guess.totalHigh) + S.s_so_tham_khao_6bb184b8])
    }
    return rows
}
function startNowHint(startNow, noStudio, unfit) {
    if (unfit) return S.s_tat_vi_may_nay_khong_lam_sach_noi_duoc_ly_7f659322
    if (noStudio) return S.s_chua_co_studio_sach_duoc_tao_va_cho_cai_xo_5e5d9ecf
    return startNow ? S.s_chay_nen_nghe_duoc_ngay_tung_chuong_da_xon_5872a97a : S.s_tao_nhung_chua_chay_bat_dau_o_trang_du_an_3c708f92
}
function precastHint(on) { return on ? S.s_dung_sau_phan_tich_de_ban_duyet_roi_bam_th_0ca451d3 : S.s_phan_tich_xong_thi_thu_luon_duyet_luc_nao_1f91e9f9 }
function qualityDetail(noStudio, profile, chapters, guess, exact) {
    if (noStudio) return S.s_cai_studio_de_uoc_tinh_thoi_gian_0ac5ef9b
    if (profile === "high_quality") return S.s_tham_khao_e9bde754 + lengthRange(guess.totalLow, guess.totalHigh) + " cho " + chapters + S.s_chuong_2721c3eb + timeBasis(exact) + "."
    return S.s_nhanh_hon_chat_luong_cao_chua_co_so_do_d80ead73
}
var PAUSE_NOTE = S.s_dang_phan_tich_ma_can_nghi_hay_dung_tam_du_ddbf5b3d
function pauseWhy(noStudio, analysis) {
    return S.s_dung_tat_may_cho_may_ngu_hoac_bam_dung_tro_98270a3d +
        (!noStudio && analysis ? S.s_thoi_gian_tham_khao_5c7b5a20 + analysis + "." : "")
}
function optionsSummary(auto, narrator, profile, startNow, noStudio) {
    return [auto ? S.s_giong_ke_may_chon_bcf6a534 : S.s_giong_ke_255bd6e6 + narrator, profileTitle(profile), startNow && !noStudio ? S.s_bat_dau_ngay_83137873 : S.s_chua_chay_713224b6].filter(Boolean).join("\u00a0·\u00a0")
}
