.pragma library
.import "SizeFormat.js" as Size
.import "StudioLogic.js" as Studio
.import "TemplateLogic.js" as Templates

// Phần thuần của trình tạo sách (ui/src/studio/NewProjectScreen.tsx và các file nó dùng: scanState, scanView, credits, narratorChoice, tellerMode, chapterNumbers,
// splitOffer, sourceRef, samePath, volumes, timeEstimate, AnalysisModelPicker): chữ và quy tắc chép từng chữ để hai nền tảng nói cùng một câu.

var PROFILES = [
    {value: "fast", title: "Nhanh", pace: "Nhanh nhất", summary: "Nghe thử một truyện mới, hoặc cần gấp.",
     points: ["Máy hiểu truyện theo từng đoạn dài một lần - nhanh hơn", "Soát cơ bản sau khi đọc", "Đọc lại tối đa 1 lần nếu câu bị đọc sai"]},
    {value: "balanced", title: "Cân bằng", pace: "Vừa phải", summary: "Nghe hằng ngày, chấp nhận vài câu chưa hoàn hảo.",
     points: ["Phân tích truyện đầy đủ", "Soát cơ bản sau khi đọc", "Đọc lại tối đa 2 lần nếu câu bị đọc sai"]},
    {value: "high_quality", title: "Chất lượng cao", pace: "Chậm nhất, kỹ nhất", summary: "Sách nghe lại nhiều lần hoặc để chia sẻ.",
     points: ["Rà lại cảm xúc từng câu một lần nữa", "Nghe lại mọi câu, soát kỹ từng chữ", "Đọc lại tới 5 lần nếu câu bị đọc sai"]}
]
var PROFILE_VALUES = ["fast", "balanced", "high_quality"]
// Chọn nhanh số chương cho một đợt - chỉ hiện khi nguồn có nhiều hơn mức nhỏ nhất.
var CHAPTER_LIMITS = [20, 50, 100]
var DEFAULT_LABEL = Templates.DEFAULT_LABEL

/** Chữ của người dùng đưa vào Text.StyledText (tên sách, đường dẫn): thoát <, > và &. */
function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
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
    return {disabled: reading || !String(title).trim() || unfit, reading: reading, label: reading ? "Đang đọc nguồn…" : ""}
}

/** Lỗi quét: nguồn không đọc được -> {text, subfolders}. */
function scanProblem(result) {
    if (result.errors && result.errors.length) return {text: "Không mở được " + result.errors[0], subfolders: []}
    if (result.missing && result.missing.length) {
        const first = result.missing[0]
        return {text: isSourceRef(first) ? "Không tìm thấy “" + sourceName(first) + "” trên máy tính. Gửi lại rồi thử lần nữa." : "Không tìm thấy “" + first + "”. Kiểm tra lại đường dẫn.", subfolders: []}
    }
    return {text: "Thư mục này không có file .txt (hay .epub, .docx, .pdf) nằm ngay bên trong.", subfolders: result.subfolders || []}
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
        .concat(tails.map(function(line) { return "“" + line + "” (cuối chương)" })).slice(0, 3)
    return {lines: head + tail, head: head, tail: tail, chapters: chapters, examples: examples}
}
function creditKind(credits) {
    if (!credits.tail) return "dòng ghi công"
    if (!credits.head) return "dòng xin ủng hộ, quảng cáo"
    return "dòng ghi công, xin ủng hộ, quảng cáo"
}
function creditWhere(credits) {
    if (!credits.tail) return "dòng ghi công người dịch ở đầu chương"
    if (!credits.head) return "dòng xin ủng hộ, quảng cáo hay nguồn ở cuối chương"
    return "dòng ghi công ở đầu chương hay dòng xin ủng hộ, quảng cáo ở cuối chương"
}
function droppedLines(credits, drop) { return (drop.head ? credits.head : 0) + (drop.tail ? credits.tail : 0) }
/** Loại dòng đang được bỏ (để nói "Sẽ bỏ N dòng ghi công khỏi phần đọc"). */
function droppedKind(credits, drop) { return creditKind({head: drop.head ? credits.head : 0, tail: drop.tail ? credits.tail : 0}) }
function creditRows(files, label) {
    return files.filter(function(file) { return ((file.credits || []).length + (file.tailCredits || []).length) > 0 })
        .map(function(file) { return {chapter: label(file), head: file.credits || [], tail: file.tailCredits || []} })
}
function creditLine(line, place, drop) {
    const where = place === "head" ? "đầu chương" : "cuối chương"
    if (!drop.head && !drop.tail) return {text: "“" + line + "” (" + where + ")", dropped: false}
    return drop[place] ? {text: "“" + line + "” (" + where + ", bỏ)", dropped: true} : {text: "“" + line + "” (" + where + ", vẫn đọc)", dropped: false}
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
    const wanted = gender === "male" ? "Nam" : "Nữ"
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
var TELLER_TITLE = "Nhân vật tự kể"
function tellerHint(on) {
    return on ? "Nhân vật xưng “tôi” đọc cả lời kể bằng giọng mình." : "Giọng dẫn đọc lời kể; nhân vật chỉ đọc lời thoại."
}
function firstPersonGuess(hint) {
    if (!hint) return ""
    if (hint.firstPerson) {
        return hint.chaptersSampled && hint.chaptersWithI
            ? hint.chaptersWithI + "/" + hint.chaptersSampled + " chương đầu có lời kể xưng “tôi”."
            : Math.round(hint.rate * 100) + "% đoạn lời kể có “tôi”."
    }
    return "Chọn nhân vật xưng “tôi” trong lời kể."
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
        issues.push("Chương " + number + " có " + names.length + " file (" + names.slice(0, 3).join(", ") + ") - giữ một, bỏ các file kia.")
    }
    if (duplicates.length > 3) issues.push("và " + (duplicates.length - 3) + " số chương trùng khác.")
    const backwards = [], gaps = []
    for (let index = 1; index < known.length; ++index) {
        const before = known[index - 1].number, here = known[index].number
        if (here < before) backwards.push("chương " + here + " đứng sau chương " + before)
        else if (here > before + 1) gaps.push(here === before + 2 ? "chương " + (before + 1) : "chương " + (before + 1) + "–" + (here - 1))
    }
    if (backwards.length) issues.push("Thứ tự lệch: " + backwards.slice(0, 3).join("; ") + (backwards.length > 3 ? "; và " + (backwards.length - 3) + " chỗ khác" : "") + " - tên file xếp khác số chương.")
    if (gaps.length) issues.push("Có vẻ thiếu " + gaps.slice(0, 4).join(", ") + (gaps.length > 4 ? " và " + (gaps.length - 4) + " khoảng khác" : "") + ".")
    const last = previousLast ? chapterNumber(previousLast, previousLast) : null
    const first = known[0].number
    if (last !== null && first !== last + 1) {
        issues.push(first <= last
            ? "Phần trước đã làm tới chương " + last + ", phần này lại bắt đầu từ chương " + first + " - làm lại các chương đã có?"
            : "Phần trước dừng ở chương " + last + ", phần này bắt đầu từ chương " + first + " - thiếu chương " + (last + 1) + (first > last + 2 ? "–" + (first - 1) : "") + ".")
    }
    return issues
}
/** Lời nhắc số chương cho cả trang: khi chia tập thì soát riêng từng tập (mỗi tập đánh số lại từ 1). */
function numberIssues(files, splitting, starts, previousLast) {
    if (splitting && starts) {
        const out = []
        ranges(starts, files.length).forEach(function(part, index) {
            chapterNumberIssues(files.slice(part.start - 1, part.end), index === 0 ? previousLast : undefined).forEach(function(issue) { out.push("Phần " + (index + 1) + ": " + issue) })
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
var SOURCE_TEXT = {folders: "mỗi thư mục là một tập", epubs: "mỗi file EPUB là một tập", headings: "các tiêu đề chương gọi tên tập"}
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
    for (let i = 0; i < count; ++i) out.push(i === 0 ? String(title).trim() : base + " · Phần " + (i + 1))
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
    return exact ? "Số tham khảo, đo trên máy cùng card " + MEASURED_ON
                 : "Số tham khảo, đo trên máy " + MEASURED_ON + "; máy của bạn có thể nhanh hơn hay chậm hơn nên đây là khoảng rộng"
}
function lengthRange(low, high) {
    const a = Studio.formatLength(low), b = Studio.formatLength(high)
    return a === b ? "khoảng " + a : a + " - " + b
}

// ---- AnalysisModelPicker.tsx ----
function modelLabel(name) { return String(name).replace(/:latest$/, "") }
function modelHint(model, defaultSize) {
    const parts = []
    const billions = Number.parseFloat(model.parameters)
    if (isFinite(billions) && /b$/i.test(String(model.parameters).trim())) parts.push(String(Math.round(billions * 10) / 10).replace(".", ",") + " tỉ tham số")
    else if (model.parameters) parts.push(model.parameters)
    if (model.size) {
        parts.push("khoảng " + Size.formatSize(model.size) + " bộ nhớ card")
        if (defaultSize > 0) {
            if (model.size > defaultSize * 1.3) parts.push("nặng và chậm hơn mặc định")
            else if (model.size < defaultSize * 0.75) parts.push("nhẹ và nhanh hơn mặc định")
        }
    }
    return parts.join(" · ")
}
function experimentalLabel(model, defaultSize) {
    const hint = modelHint(model, defaultSize)
    return "Bản thử nghiệm" + (hint ? " · " + hint : "")
}
function analysisChoiceLabel(chosen, seedModel) {
    return chosen ? "Bản thử nghiệm (" + (seedModel === chosen ? "như phần trước" : "chỉ cuốn này") + ")" : "Mặc định của ABook"
}
/** Tên các model dùng được cho một cuốn (mặc định + Ollama đang có), hay null khi chưa biết (chưa tải xong, Ollama tắt). */
function availableModelNames(data) { return data && data.reachable ? [data.default].concat(data.models.map(function(model) { return model.name })) : null }
/** Các lựa chọn của ô "Bộ phân tích truyện": mặc định + các bản khác. Trả {options, others, defaultSize}. */
function modelOptions(data) {
    if (!data || !Array.isArray(data.models)) return {others: [], options: []}
    const others = data.models.filter(function(model) { return modelLabel(model.name) !== modelLabel(data.default) })
    let defaultSize = 0
    for (const model of data.models) if (modelLabel(model.name) === modelLabel(data.default)) defaultSize = model.size || 0
    const options = [{value: "", label: "Mặc định của ABook (khuyên dùng)"}]
    if (others.length) options.push({header: "Bản khác (thử nghiệm)"})
    others.forEach(function(model, index) { options.push({value: model.name, label: (index + 1) + ". " + experimentalLabel(model, defaultSize)}) })
    return {others: others, options: options, defaultSize: defaultSize}
}

// ---- nối tiếp ----
function carriedText(carries) {
    const n = Studio.formatNumber
    const parts = [
        carries.voices ? "giọng " + n(carries.voices) + " nhân vật" : "",
        carries.pronunciations ? n(carries.pronunciations) + " cách đọc tên" : "",
        carries.pins ? "giới / tuổi đã sửa tay của " + n(carries.pins) + " nhân vật" : "",
        carries.aliases ? n(carries.aliases) + " bí danh" : "",
        carries.names ? n(carries.names) + " tên nhân vật đã đổi" : "",
        carries.bracket ? "quy ước lời trong 『』" : ""
    ].filter(Boolean)
    return parts.length ? parts.join(" · ") : "những gì phần trước đã có"
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
    const queued = draft.startNow && !noStudio && result.queued ? " - vào hàng chờ (thứ " + result.queued + ")" : ""
    const head = result.unchanged ? "Không có thiết lập nào thay đổi - giữ nguyên sách cũ"
        : volumes > 1 ? "Đã tạo " + volumes + " phần"
        : draft.replaces && draft.replaces.restart ? "Đã làm lại sách từ đầu"
        : draft.replaces ? "Đã tạo lại sách với thiết lập mới" : "Đã tạo sách"
    return [head + queued, noStudio ? "Dự án chờ tới khi Studio cài xong, rồi bấm “Bắt đầu tạo sách nói” ở trang dự án." : ""]
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
    const rows = [["Chương", scan.files.length + " chương · " + approx(scan.totals.words, scan.totals.estimated) + " chữ"]]
    if (a.volumes) {
        const names = volumeTitles(a.title, a.volumes.length).map(function(name, index) { return "“" + name + "” (" + n(a.volumes[index].chapters) + " chương)" })
        rows.push(["Chia thành", a.volumes.length + " phần: " + names.join(", ")])
        rows.push(["Các phần sau", a.startNow ? "Tự chạy sau phần trước, giữ giọng và cách đọc tên" : "Xếp hàng sau phần 1, giữ giọng và cách đọc tên"])
    }
    const dropped = droppedLines(a.credits, a.dropCredits)
    if (dropped) rows.push([droppedKind(a.credits, a.dropCredits).replace(/^d/, "D"), "bỏ " + n(dropped) + " dòng khỏi phần đọc"])
    rows.push(["Độ dài audio", "khoảng " + Studio.formatLength(scan.totals.audioSeconds)])
    rows.push(["Giọng kể", a.narratorAuto ? "máy chọn, cùng giới với người kể “tôi” (đang là " + a.narrator + ")" : a.narrator])
    if (a.firstPerson) rows.push(["Người kể “tôi”", a.firstPersonGender ? a.firstPerson + " (" + (a.firstPersonGender === "female" ? "nữ" : "nam") + ")" : a.firstPerson])
    if (a.tellerMode) rows.push(["Lời kể", "đọc bằng giọng của người kể “tôi”"])
    const pov = Object.keys(a.povChapters)
    if (pov.length) rows.push(["Chương đổi người kể", pov.map(function(chapter) { return "chương " + chapter + ": " + a.povChapters[chapter] }).join(", ")])
    // "Nối tiếp: phần 2 của …" đọc như nối SAU phần 2 hay LÀ phần 2 đều được - nói thẳng là phần mấy, sau phần nào, và dải chương.
    if (a.seed) {
        rows.push(["Là", "phần " + a.seed.part + " của “" + a.seed.title + "”, nối sau phần " + (a.seed.part - 1) +
            (scan.files.length ? " · " + chapterLabel(scan.files[0]) + " → " + chapterLabel(scan.files[scan.files.length - 1]) : "")])
    }
    rows.push(["Nhân vật", a.seed ? "Giữ " + carriedText(a.seed.carries) + "; người mới được phân vai sau khi phân tích" : "Tự động phân vai sau khi phân tích"])
    rows.push(["Chất lượng", option.title])
    // Luôn nói bộ phân tích nào sẽ đọc hiểu truyện - cả khi là mặc định - vì phân tích là bước dài nhất và không ngắt được.
    if (a.analysisModel || a.modelsDefault) rows.push(["Bộ phân tích truyện", analysisChoiceLabel(a.analysisModel, a.seed ? a.seed.analysisModel : undefined)])
    if (a.unfit) rows.push(["Thời gian làm", "máy này không làm sách nói được"])
    else if (a.noStudio) rows.push(["Thời gian làm", "tính được khi Studio đã cài - dự án chờ tới lúc đó"])
    else if (measured) {
        rows.push(["Thời gian làm (tham khảo)", lengthRange(guess.totalLow, guess.totalHigh)])
        rows.push(["Chương đầu nghe được sau (tham khảo)", (exact ? "khoảng" : "tối đa khoảng") + " " + Studio.formatLength(guess.firstChapter)])
        rows.push(["Số tham khảo từ đâu", timeBasis(exact)])
    } else {
        // "Nhanh" chưa có số đo trên máy này - vẫn nói được trần trên thay vì im lặng.
        rows.push(["Thời gian làm", "chưa đo cho chế độ này - ngắn hơn “Chất lượng cao” (dưới " + Studio.formatLength(guess.totalHigh) + ", số tham khảo)"])
    }
    return rows
}
function startNowHint(startNow, noStudio, unfit) {
    if (unfit) return "Tắt vì máy này không làm sách nói được (lý do ở đầu trang)."
    if (noStudio) return "Chưa có Studio: sách được tạo và chờ cài xong."
    return startNow ? "Chạy nền; nghe được ngay từng chương đã xong." : "Tạo nhưng chưa chạy; bắt đầu ở trang dự án khi sẵn sàng."
}
function precastHint(on) { return on ? "Dừng sau phân tích để bạn duyệt, rồi bấm “Thu âm”." : "Phân tích xong thì thu luôn; duyệt lúc nào cũng được." }
function qualityDetail(noStudio, profile, chapters, guess, exact) {
    if (noStudio) return "Cài Studio để ước tính thời gian."
    if (profile === "high_quality") return "Tham khảo: " + lengthRange(guess.totalLow, guess.totalHigh) + " cho " + chapters + " chương. " + timeBasis(exact) + "."
    return "Nhanh hơn Chất lượng cao; chưa có số đo."
}
var PAUSE_NOTE = "Đang phân tích mà cần nghỉ, hãy dùng Tạm dừng."
function pauseWhy(noStudio, analysis) {
    return "Đừng tắt máy, cho máy ngủ hoặc bấm Dừng trong lúc phân tích. Dừng hoặc nạp lại model có thể đổi phân vai và audio; bản cũ cần tạo dự án mới nếu bị ngắt. Tạm dừng quá 30 phút cũng có thể dỡ model. Sau phân tích, bạn có thể dừng và tiếp tục." +
        (!noStudio && analysis ? " Thời gian tham khảo: " + analysis + "." : "")
}
function optionsSummary(auto, narrator, profile, startNow, noStudio) {
    return [auto ? "Giọng kể máy chọn" : "Giọng kể " + narrator, profileTitle(profile), startNow && !noStudio ? "bắt đầu ngay" : "chưa chạy"].filter(Boolean).join(" · ")
}
