.pragma library
.import "StudioLogic.js" as Studio
.import "SizeFormat.js" as Size
.import "CastLogic.js" as Cast

// Phần thuần của hộp "Xuất" (ui/src/studio/ExportBook.tsx, exportText.ts, projectPacking.ts, bookFilePacking.ts, WordTimings.tsx và phần jobView / copy của
// desktop/bookFileExport.ts, listenExport.ts): chữ và quy tắc chép từng chữ để hai nền tảng nói cùng một câu; HTTP và giao diện nằm ở ExportBook.qml.

// ---- kiểu bản xuất ----
var KINDS = [
    {value: "mp3", title: "Thư mục MP3", detail: "Mỗi chương một file có tên và bìa.", icon: "folder-down"},
    {value: "abook", title: "File .abook", detail: "Một file chứa cả sách, mở bằng ABook.", icon: "file-audio"},
    {value: "m4b", title: "Sách nói M4B", detail: "Một file có mục lục chương, cho app sách nói.", icon: "book-audio"},
    {value: "abookproj", title: "Cả dự án (.abookproj)", detail: "Cả dự án và audio, để sao lưu hay làm tiếp ở máy khác.", icon: "folder-archive"}
]
// [tiêu đề hộp chọn thư mục, đang làm, lỗi]
var SAVING = {
    mp3: ["Chọn nơi lưu bản xuất", "Đang xuất MP3…", "Không xuất được MP3"],
    abook: ["Chọn nơi lưu file sách", "Đang đóng gói sách…", "Không xuất được"],
    m4b: ["Chọn nơi lưu file M4B", "Đang làm file M4B…", "Không xuất được M4B"],
    abookproj: ["Chọn nơi lưu file dự án", "Đang đóng gói dự án…", "Không gói được dự án"]
}
/** Thẻ nhớ / USB định dạng FAT32 không chứa nổi file lớn hơn 4 GiB. */
var FAT32_LIMIT = 4 * 1024 * 1024 * 1024
var MUSIC_MIX_HINT = "Nhạc được trộn thẳng vào file, không tắt riêng được khi nghe."
function scopeOptions(parts) { return [{value: "part", label: "Phần này"}, {value: "series", label: "Cả bộ (" + parts + " phần)"}] }
var LAYOUTS = [{value: "single", label: "Một file"}, {value: "perPart", label: "Mỗi phần một file"}]

/** Studio từ xa (máy khác) không gói dự án: file nằm ở máy tính, việc của người ngồi trước nó. */
function kindsFor(remote) { return remote ? KINDS.filter(function(item) { return item.value !== "abookproj" }) : KINDS }
function kindInfo(kind) { return KINDS.filter(function(item) { return item.value === kind })[0] || KINDS[0] }
/** Truy vấn chọn trạng thái tải nhạc / Huỷ của đúng kiểu xuất ở máy chủ (server.py `_music_key`); `.abook` không cần. */
function musicKind(kind) { return kind === "abookproj" ? "?kind=projectfile" : "" }

// ---- exportText.ts ----
/** Chương chờ thu lại theo sửa của người nghe: bản xuất mang bản thu CŨ của chúng. `null` khi không có chương nào chờ. */
function redoExportNote(redo, abook) {
    if (redo <= 0) return null
    const name = abook ? "; tên giọng ghi trong sách có thể đã là giọng mới" : ""
    return redo + " chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy" + name + "."
}

// ---- projectPacking.ts ----
var PACK_SPAN = {prepare: [0, 0.02], listen: [0.02, 0.38], views: [0.38, 0.42], hash: [0.42, 0.72], write: [0.72, 1]}
/** File sách `.abook` (bookfile.pack): gom chương là gần hết thời gian, rồi ghi gói. */
var BOOK_FILE_SPAN = {prepare: [0, 0.02], listen: [0.02, 0.85], views: [0.85, 0.85], hash: [0.85, 0.85], write: [0.85, 1]}
/** {title: "Đang đóng gói (12/400 chương)…", fraction: 0-1 hay null khi chưa có mẫu số} */
function packView(job, spans) {
    spans = spans || PACK_SPAN
    const base = "Đang đóng gói"
    if (!job || !job.phase || job.state !== "running") return {title: base + "…", fraction: null}
    const span = spans[job.phase]
    const total = job.total || 0
    const done = Math.min(job.done || 0, total)
    const inner = total > 0 ? done / total : 0
    const fraction = span[0] + (span[1] - span[0]) * inner
    if (job.phase === "listen" && total > 0) return {title: base + " (" + done + "/" + total + " chương)…", fraction: fraction}
    if ((job.phase === "hash" || job.phase === "write") && total > 0) return {title: base + " (" + Size.formatSize(done) + "/" + Size.formatSize(total) + ")…", fraction: fraction}
    return {title: base + "…", fraction: job.phase === "prepare" ? null : span[0]}
}
var PACK_KNOWN = [
    {pattern: /No space left|ENOSPC|disk full|WinError 112|not enough space|disk quota/i, summary: "Ổ đĩa hết chỗ trống. Giải phóng dung lượng hoặc chọn thư mục ở ổ khác rồi gói lại."},
    {pattern: /PermissionError|WinError 5\b|WinError 32|Access is denied|being used by another process|Errno 13/i,
     summary: "Không ghi được vào thư mục đã chọn (đang bị khoá hay không đủ quyền). Chọn thư mục khác rồi gói lại."}
]
/** Lỗi thô của máy chủ -> câu cho người nghe + nguyên văn cho "Chi tiết". Lỗi đã viết bằng tiếng Việt giữ nguyên, không có Chi tiết. */
function packError(raw) {
    const detail = String(raw).trim()
    for (const known of PACK_KNOWN) if (known.pattern.test(detail)) return {summary: known.summary, detail: detail}
    if (/[ạảãàáâấầẩẫậắằẳẵặẹẻẽèéêếềểễệỉĩịọỏõòóôốồổỗộớờởỡợụủũùúưứừửữựỳỷỹýđ]/i.test(detail)) return {summary: detail, detail: ""}
    return {summary: "Chưa gói được dự án.", detail: detail}
}
/** Gói bị huỷ (máy chủ trả "cancelled"): người dùng bấm Huỷ. */
var CANCELLED = "cancelled"

// ---- bookFilePacking.ts ----
/** Bắt đầu một việc xuất nền rồi theo nó; theo lại việc cũ (`attach`) thì không tạo lượt mới. `request(method, path, body, done(status, data))`
 *  là đường HTTP của Studio; `follow(done)` theo job tới khi xong. `done(error, result, data)`. */
function startJob(request, path, body, follow, attach, done) {
    if (attach) { follow(done); return }
    request("POST", path, body, function(status, data) {
        if (status < 200 || status >= 300) { done(data && (data.message || data.error) || "Không xuất được", null, data); return }
        follow(done)
    })
}
/** Xuất file sách `.abook` (bookFilePacking.ts): cùng đường với mọi kiểu xuất, đường là `bookfile-job`. */
function packBookFile(request, bookId, body, follow, attach, done) {
    startJob(request, "/api/books/" + bookId + "/bookfile-job", body, follow, attach, done)
}

// ---- định dạng chữ chung ----
function fileName(path) { const parts = String(path).replace(/[\\/]+$/, "").split(/[\\/]/); return parts[parts.length - 1] || String(path) }
/** Studio từ xa: file xuất nằm trên máy tính, không về máy đang xem. `detail`: phần còn lại của dòng ("5 MB", "6 file"). */
function exportedOnComputer(computer, name, detail) {
    const where = computer && computer !== "máy tính" ? "Đã xuất vào máy tính " + computer : "Đã xuất vào máy tính"
    return [name ? where + ": " + name : where, detail || ""].filter(Boolean).join(" · ")
}
function spokenDuration(seconds) {
    const minutes = Math.round(seconds / 60)
    if (minutes < 1) return "dưới 1 phút"
    if (minutes < 60) return "khoảng " + minutes + " phút"
    const hours = Math.floor(minutes / 60), rest = minutes % 60
    return "khoảng " + hours + " giờ" + (rest ? " " + rest + " phút" : "")
}
/** "Chỗ lưu" nói trước khi bấm "Xuất": có hộp chọn thư mục thì tự chọn, không thì vào thư mục "Đã xuất" của thư viện. */
function savePlace(opts) {
    if (opts.dialogs) return "Bấm nút bên dưới rồi chọn thư mục để lưu."
    if (opts.remote) return "Sẽ lưu vào thư mục “Đã xuất” trong thư viện của máy tính" + (opts.computer && opts.computer !== "máy tính" ? " " + opts.computer : "")
        + " - file nằm ở máy tính, không tải về máy này."
    const root = opts.libraryRoot || ""
    return root ? "Sẽ lưu vào thư mục “Đã xuất” trong thư viện: " + root + (root.indexOf("\\") >= 0 ? "\\" : "/") + "Đã xuất" : "Sẽ lưu vào thư mục “Đã xuất” trong thư viện."
}

// ---- cái hộp tính ra: bao nhiêu chương, cảnh báo gì, nút có bấm được không ----
/** Truyện nhiều phần: xuất riêng phần đang xem hay cả bộ. M4B: mỗi phần một file riêng, như menu Thư viện; dự án nằm trong MỘT file. */
function isWholeSeries(scope, parts, kind) { return scope === "series" && parts > 1 && kind !== "abookproj" && kind !== "m4b" }
/** Mọi con số và lời cảnh báo của hộp cho một cuốn. ctx: {kind, scope, layout, parts, changedOnly, changed: [id], bytes} */
function plan(book, ctx) {
    const chapters = book.chapters || {}
    const missing = chapters.missingAudio || 0
    const ready = Math.max(0, (chapters.completed || 0) - missing)
    const total = chapters.total || 0
    const wholeSeries = isWholeSeries(ctx.scope, ctx.parts, ctx.kind)
    const oneFile = ctx.kind === "abook" && (!wholeSeries || ctx.layout === "single")
    // Dự án chỉ có chữ: `.abook` vẫn xuất được (gói mang chữ các chương); MP3 / M4B thì cần audio.
    const textOnly = ctx.kind === "abook" && !wholeSeries && !ready && total > 0
    const changed = ctx.changed || []
    const selectedCount = ctx.kind === "mp3" && !wholeSeries && ctx.changedOnly && changed.length ? changed.length : ready
    const whole = ctx.kind === "abookproj"
    const countText = whole ? "" : wholeSeries ? ctx.parts + " phần" : selectedCount + " chương"
    const bytes = ctx.bytes || 0
    const warnings = (whole
        ? [book.running && "Dự án đang chạy - gói khi nó đã chạy xong hoặc đã dừng."]
        : [
            textOnly && "Chưa chương nào có audio: file .abook chỉ mang chữ của " + Studio.formatNumber(total) + " chương (đọc được, chưa nghe được). Có audio rồi thì xuất lại.",
            !wholeSeries && !textOnly && ready < total && Studio.formatNumber(total - ready) + "/" + Studio.formatNumber(total) + " chương chưa có audio" + (missing ? " (" + missing + " chương mất file)" : "") + " - không có trong bản xuất.",
            wholeSeries && "Phần nào chưa có chương xong sẽ bị bỏ qua; phần đang chạy chỉ có các chương đã xong tới lúc này.",
            !wholeSeries && book.running && "Sách đang chạy - bản xuất chỉ gồm các chương đã xong tới lúc này.",
            !wholeSeries && redoExportNote(chapters.redo || 0, ctx.kind === "abook"),
            oneFile && bytes > FAT32_LIMIT && "File này sẽ lớn hơn 4 GB - thẻ nhớ hay USB định dạng FAT32 không chứa nổi." + (wholeSeries ? " Chọn “Mỗi phần một file” nếu định chép vào đó." : "")
        ]).filter(Boolean)
    return {
        missing: missing, ready: ready, total: total, wholeSeries: wholeSeries, oneFile: oneFile, textOnly: textOnly, selectedCount: selectedCount, countText: countText,
        whole: whole, warnings: warnings,
        description: wholeSeries ? "Các chương nghe được của cả " + ctx.parts + " phần sẽ vào bản xuất." : Studio.formatNumber(selectedCount) + " chương sẽ vào bản xuất.",
        // Gói dự án chờ sách chạy xong; còn lại cần chương có audio (hoặc bản chỉ chữ / cả bộ)
        blocked: whole ? Boolean(book.running) : (!wholeSeries && !ready && !textOnly)
    }
}
/** Bản xuất đã cũ (export-history): những lần xuất mà chương đã đổi sau đó; và các chương MP3 đã đổi. */
function staleOf(history) { return (history || []).filter(function(item) { return item.changed && item.changed.length > 0 }) }
function changedChapters(stale) {
    const out = []
    for (const item of stale) if (item.kind === "mp3") for (const id of item.changed) if (out.indexOf(id) < 0) out.push(id)
    return out
}
function staleAction(item) { return item.kind === "m4b" ? "Xuất lại M4B" : item.kind === "mp3" ? "Xuất chương đổi" : "Xuất file sách" }
/** Ô "Kèm nhạc nền": theo công tắc Nhạc nền của cuốn cho tới khi người dùng tự tích / bỏ tích; cuốn không có kế hoạch nhạc: luôn tắt. */
function musicChecked(state, chosen, bookId) {
    if (!state || !state.available) return false
    return chosen && chosen.bookId === bookId ? chosen.on : Boolean(state.enabled)
}
function ffmpegPercent(status) { return status.total > 0 ? Math.min(100, Math.round(100 * status.done / status.total)) : 0 }

// ---- kết quả ----
/** Xong: {title, detail, folder, note}; `kind`: "abook" | "abookproj". Studio từ xa: máy chủ chỉ trả TÊN file / thư mục - nói file nằm ở máy tính nào. */
function finishedOf(kind, result, opts) {
    const lost = result.missingSources ? result.missingSources.length : 0
    const skippedNote = result.skipped && result.skipped.length ? "chưa có chương nào nên bỏ qua: " + result.skipped.map(function(part) { return "Phần " + part.part }).join(", ") : ""
    const skipped = skippedNote ? " · " + skippedNote : ""
    const lostNote = lost ? lost + " file nguồn chương đã bị dời hay xoá nên không có trong gói" : ""
    // `file` chỉ có khi cả bộ (hay một phần) nằm trong MỘT file; cả bộ mỗi phần một file thì có `parts` mà không có `file`.
    const single = typeof result.file === "string"
    const title = result.parts
        ? (single ? "Đã xuất cả bộ " + result.parts.length + " phần trong một file sách" : "Đã xuất " + result.parts.length + " file sách")
        : kind === "abook" ? "Đã xuất file sách" : "Đã gói dự án"
    const perPart = Boolean(result.parts && kind === "abook" && !single)
    const size = Size.formatSize(result.size || 0)
    const placeText = perPart ? result.folder + " · mỗi phần một file .abook riêng" : single ? result.file + " · " + size : result.folder
    const detail = (opts.remote
        ? exportedOnComputer(opts.computer, perPart ? "" : single ? fileName(result.file) : fileName(result.folder || ""),
                             [perPart ? "mỗi phần một file .abook riêng" : "", single ? size : ""].filter(Boolean).join(" · "))
        : placeText) + skipped + (lostNote ? " · " + lostNote : "")
    return {title: title, detail: detail, folder: result.folder || "", note: [skippedNote, lostNote].filter(Boolean).join(" · "), remoteTitle: exportedOnComputer(opts.computer, "")}
}

// ---- việc nền (MP3, M4B): bookFileExport.ts jobView ----
var MP3_COPY = {busy: "Đang xuất MP3…", done: "Đã xuất MP3", failed: "Không xuất được MP3", stopped: "Đã huỷ xuất", stoppedNote: "Các chương đã ghi dở được xoá.",
                stopping: "Dừng ngay sau bước đang làm - thư mục MP3 dở được xoá."}
var M4B_COPY = {busy: "Đang làm file M4B…", done: "Đã xuất M4B", failed: "Không xuất được M4B", stopped: "Đã huỷ xuất", stoppedNote: "Chưa có file M4B nào được ghi.",
                stopping: "Dừng ngay sau bước đang làm - không ghi file M4B nào."}
function copyOf(kind) { return kind === "m4b" ? M4B_COPY : MP3_COPY }

function packingText(chapters, elapsed) { return chapters + " chương · đã " + Studio.formatClock(elapsed) }
/** Việc tự báo tiến độ: chữ + phần trăm 0-1; không báo thì null. */
function reportedProgress(job) {
    if (job.phase === "music-fetch" && job.total) {
        const done = job.done || 0
        return {fraction: done / job.total, text: "Đang tải nhạc nền " + Math.min(done + 1, job.total) + "/" + job.total + " bài"}
    }
    if (job.phase === "peaks") return {fraction: 1, text: "Đang kiểm đỉnh âm…"}
    const again = job.peakOver ? "Mã hoá lại vì " + job.peakOver + " chương vượt đỉnh (lượt " + (job.peakRound || 1) + ")" : ""
    if (job.phase === "reencode") return {fraction: 1, text: again}
    if (job.chapter === undefined || !job.chapters) return null
    const where = "Chương " + job.chapter + "/" + job.chapters
    if (job.phase === "encode") return {fraction: 1, text: again ? again + " · " + where : "Đang ghép file âm thanh · " + where}
    if (job.phase === "chapters") return {fraction: (job.chapter - 1) / job.chapters, text: "Đang ghi chương " + job.chapter + "/" + job.chapters}
    if (job.phase === "music") {
        const text = "Đang trộn nhạc chương " + job.chapter + "/" + job.chapters
        return {fraction: job.percent !== undefined ? job.percent / 100 : (job.chapter - 1) / job.chapters, text: again ? again + " · " + text : text}
    }
    const parts = [where, (job.percent || 0) + "%"]
    if (job.waiting === "listening") parts.push("nhường cho chương đang nghe")
    else if (job.waiting === "network") parts.push("Đang chờ mạng…")
    else if (job.secondsLeft !== undefined && job.secondsLeft !== null) parts.push("còn " + spokenDuration(job.secondsLeft))
    return {fraction: (job.percent || 0) / 100, text: parts.join(" · ")}
}
function missingChaptersNote(result) {
    if (result.chapters === undefined || result.chaptersTotal === undefined || result.chapters >= result.chaptersTotal) return ""
    return result.chapters + "/" + result.chaptersTotal + " chương - chương chưa xong không có trong file"
}
function musicMissingNote(result) { return result.musicMissing ? result.musicMissing + " đoạn thiếu nhạc vì chưa tải được bài" : "" }
function skippedPartsNote(result) {
    return result.skipped && result.skipped.length ? "chưa có chương nào nên bỏ qua: " + result.skipped.map(function(part) { return "Phần " + part.part }).join(", ") : ""
}
/** Thông báo cho trạng thái hiện có của một việc nền MP3 / M4B: {kind: none|loading|success|error|info, title, description, note, progress}. */
function jobView(job, chapters, copy) {
    if (job.state === "running") {
        const elapsed = job.elapsed || 0
        const reported = reportedProgress(job)
        if (reported) return {kind: "loading", title: copy.busy, description: reported.text, progress: reported.fraction}
        return {kind: "loading", title: copy.busy, description: chapters ? packingText(chapters, elapsed) : "đã " + Studio.formatClock(elapsed)}
    }
    if (job.state === "cancelled") return copy.stopped ? {kind: "info", title: copy.stopped, description: copy.stoppedNote || ""} : {kind: "none"}
    if (job.state === "done" && job.result) {
        const file = job.result.file, folder = job.result.folder
        const count = job.result.files !== undefined ? job.result.files : (job.result.parts ? job.result.parts.length : undefined)
        const partsNote = !file && job.result.files !== undefined && job.result.parts ? job.result.parts.length + " phần" : ""
        const skipped = skippedPartsNote(job.result)
        const lacks = [missingChaptersNote(job.result), musicMissingNote(job.result), job.result.coverBroken ? "ảnh bìa của sách bị hỏng nên dùng bìa vẽ từ tên" : ""].filter(Boolean)
        const details = [partsNote, !file && count ? count + " file" : "", skipped, job.result.size ? Size.formatSize(job.result.size) : ""].concat(lacks).filter(Boolean)
        const place = file || folder || ""
        const view = {kind: "success", title: copy.done, description: [fileName(place)].concat(details).filter(Boolean).join(" · "), place: place, folder: folder || ""}
        if (skipped || lacks.length) view.note = [skipped].concat(lacks).filter(Boolean).join(" · ")
        return view
    }
    if (job.state === "error") return {kind: "error", title: copy.failed, description: job.error || ""}
    return {kind: "none"}
}

// ---- WordTimings.tsx ----
/** Dòng dưới "Chữ sáng": đang làm bao nhiêu %, đã xong chưa, đã có bao nhiêu câu. */
function wordTimingsNote(data) {
    const lines = data && data.lines || 0, aligned = data && data.words || 0
    const finished = Boolean(data && data.state === "done" && data.file)
    let note = "Thêm chữ sáng theo giọng đọc, chạy nền vài phút."
    if (data && data.state === "running") note = "Đang thêm chữ sáng… " + (data.total ? Math.round(((data.done || 0) / data.total) * 100) : 0) + "%"
    else if (data && data.state === "error") note = data.error || "Chưa thêm được chữ sáng."
    else if (finished) note = "Xong - file sách của dự án đã được làm lại kèm chữ sáng theo giọng đọc."
    else if (lines > 0) note = Studio.formatNumber(aligned) + "/" + Studio.formatNumber(lines) + " câu đã có chữ sáng theo giọng đọc."
    return note
}
/** Nút "Thêm chữ sáng" tắt khi sách đang chạy hay mọi câu đã có chữ sáng. */
function wordTimingsDisabled(data, running) {
    const lines = data && data.lines || 0, aligned = data && data.words || 0
    const finished = Boolean(data && data.state === "done" && data.file)
    return Boolean(running) || (lines > 0 && aligned === lines && !finished)
}

// ---- ApplyChanges.tsx ----
/** Nút bỏ một dòng nói rõ nó bỏ gì ("Bỏ cách đọc “Lucien”"): mọi nút cùng nhãn thì trình đọc màn hình không phân biệt được dòng nào. */
function dropLabel(item) {
    if (item.kind === "pronunciation") {
        const surface = /^“([^”]+)”/.exec(item.label || "")
        if (surface) return "Bỏ cách đọc “" + surface[1] + "”"
    }
    const verbs = {pronunciation: "Bỏ cách đọc", speaker: "Bỏ đổi người nói", line: "Bỏ sửa cách đọc câu", voice: "Bỏ đổi giọng", retake: "Bỏ thu lại"}
    return (verbs[item.kind] || "Bỏ") + ": " + item.label
}
function pendingKey(item) { return item.section + ":" + item.key }
function pendingLines(item) { return item.lines ? Studio.formatNumber(item.lines) + " câu thu lại" : "chưa thu - không tốn gì" }
/** Hộp "Áp dụng": đang chạy (`running` "busy" | "checkpoint") thì máy tự áp ở ranh giới chương kế nên không có nút "Áp dụng". */
function applyHeading(count, running) { return running ? count + " thay đổi đang chờ áp" : "Áp dụng " + count + " thay đổi?" }
function applyDescription(running) {
    return running ? "Tự áp ở chương kế tiếp; chỉ bỏ được việc chưa áp."
                   : "Máy chỉ thu lại những câu bị ảnh hưởng, rồi dựng lại các chương có câu ấy - không làm lại cả cuốn."
}
function applyClose(running) { return running ? "Đóng" : "Để sau" }
function shownChapters(chapters) { return chapters.slice(0, 4).join(", ") + (chapters.length > 4 ? ", và " + (chapters.length - 4) + " chương khác" : "") }
/** Dòng cuối hộp "Áp dụng": thu lại bao nhiêu câu ở chương nào, mất bao lâu (data = /pending-changes). */
function applySummary(data) {
    if (!data.lines) return "Chỉ ghi thay đổi, không thu lại câu nào."
    return "Thu lại " + Studio.formatNumber(data.lines) + " câu ở " + data.chapters.length + " chương (" + shownChapters(data.chapters) + ")"
        + (data.seconds > 0 ? " - " + Cast.estimateText(data.seconds, data.measured) : "") + "."
}

// ---- việc xuất nền: đường, nhịp hỏi, lời ----
var JOB_SEGMENT = {mp3: "mp3-job", m4b: "m4b-job", abook: "bookfile-job", abookproj: "projectfile-job"}
/** Đường của việc nền theo kiểu xuất của hộp (khớp `url` / `cancel` của ExportBookFileJob.tsx). */
function jobPath(kind, bookId) { return "/api/books/" + bookId + "/" + JOB_SEGMENT[kind] }
/** Kiểu của hộp theo khoá `/api/export-jobs` (bookfile -> abook, projectfile -> abookproj). */
function kindOfJob(name) { return {mp3: "mp3", m4b: "m4b", bookfile: "abook", projectfile: "abookproj"}[name] || "" }
/** Mã các kiểu đang chạy của một cuốn trong trả lời của GET /api/export-jobs: kiểu của hộp đầu tiên đang chạy, hay "". */
function runningKind(all, bookId) {
    for (const name of ["projectfile", "bookfile", "mp3", "m4b"]) {
        const hit = (all && all[name] || []).filter(function(job) { return job.bookId === bookId && job.state === "running" })
        if (hit.length) return kindOfJob(name)
    }
    return ""
}
/** Thân yêu cầu bắt đầu: MP3 / M4B mang `music`, `series`, `chapterIds`; `.abook` mang `series` và `single`; dự án chỉ cần `target`. */
function startBody(kind, ctx) {
    const body = {target: ctx.target || ""}
    if (kind === "mp3" || kind === "m4b") {
        if (ctx.mixes) body.music = true
        if (kind === "mp3" && ctx.wholeSeries) body.series = true
        if (kind === "mp3" && !ctx.wholeSeries && ctx.changedOnly && ctx.changedIds.length) body.chapterIds = ctx.changedIds
    } else if (kind === "abook") {
        body.series = Boolean(ctx.wholeSeries)
        if (ctx.wholeSeries) body.single = ctx.layout === "single"
    }
    return body
}
/** Một nhịp hỏi việc nền: {state: "running"} | {state: "done", result} | {state: "cancelled"} | {state: "error", error}. (followPackJob của projectPacking.ts) */
function followStep(job, failure) {
    if (job.state === "done" && job.result) return {state: "done", result: job.result}
    if (job.state === "cancelled") return {state: "cancelled"}
    if (job.state !== "running") return {state: "error", error: job.error || failure || "Chưa gói được dự án."}
    return {state: "running"}
}
/** Lời lúc đang xuất: {title, note, fraction (-1 = chưa có mẫu số)}. ctx: {chapters, countText, downloading: {done, total} hay null, cancelling} */
function busyView(kind, job, ctx) {
    let title = SAVING[kind][1], fraction = -1
    if (kind === "mp3" || kind === "m4b") {
        const view = jobView(job, ctx.chapters, copyOf(kind))
        if (view.kind === "loading") { title = view.description || view.title; if (view.progress !== undefined) fraction = view.progress }
    } else {
        const shown = packView(job, kind === "abook" ? BOOK_FILE_SPAN : PACK_SPAN)
        title = shown.title
        if (shown.fraction !== null) fraction = shown.fraction
    }
    const downloading = ctx.downloading && ctx.downloading.total > 0 ? ctx.downloading : null
    if (downloading) { title = "Đang tải nhạc nền (" + downloading.done + "/" + downloading.total + ")…"; fraction = -1 }
    if (ctx.cancelling) title = "Đang huỷ…"
    const lead = downloading ? "Tải nhạc còn thiếu; " : ctx.countText ? ctx.countText + "; " : ""
    return {title: title, note: lead + "đóng hộp vẫn xuất nền và báo khi xong.", fraction: fraction}
}
/** Bản xuất xong: {title, detail, folder, note} - `.abook` / dự án theo finishedOf, MP3 / M4B theo jobView. */
function finishedFor(kind, result, opts) {
    if (kind === "abook" || kind === "abookproj") return finishedOf(kind, result, opts)
    const view = jobView({state: "done", result: result}, opts.chapters || 0, copyOf(kind))
    return {title: opts.remote ? exportedOnComputer(opts.computer, "") : view.title, detail: view.description, folder: view.folder || "", note: view.note || ""}
}
/** Việc hỏng: {title, description}; dự án qua packError (câu cho người nghe + nguyên văn sau một dòng trống). */
function failureOf(kind, raw) {
    if (kind === "abookproj") {
        const shown = packError(raw)
        return {title: SAVING[kind][2], description: shown.detail ? shown.summary + "\n" + shown.detail : shown.summary}
    }
    return {title: SAVING[kind][2], description: String(raw)}
}
/** Sách đang chạy: "checkpoint" (đã tạm dừng ở checkpoint), "busy" (đang làm) hay "" (đứng yên). Như `running=` của ApplyChangesDialog ở ProjectScreen.tsx. */
function applyRunning(book) {
    if (!book || !book.running) return ""
    return book.paused && book.status === "paused" ? "checkpoint" : "busy"
}
