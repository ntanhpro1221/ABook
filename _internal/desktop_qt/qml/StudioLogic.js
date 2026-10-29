.pragma library
.import "LibraryLogic.js" as LibraryLogic
.import "PeerStudio.js" as Peer

// Phần thuần của Studio (danh sách dự án + trang dự án): chữ và quy tắc chép nguyên từ ui/src/studio (data.ts, stopText.ts, errorText.ts, polling.ts,
// projectGroups.ts, ProjectScreen.tsx, ProjectsScreen.tsx) và ui/src/shared/format.ts, để hai nền tảng nói cùng một câu.

// ---- shared/format.ts ----
function formatNumber(value) {
    const whole = String(Math.round(value))
    return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ".")
}
function formatPercent(fraction) {
    const value = Math.max(0, Math.min(1, fraction)) * 100
    if (value > 0 && value < 1) return "<1%"
    if (value < 100 && value > 99) return "99%"
    return Math.floor(value) + "%"
}
function formatLength(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return "0 phút"
    const minutes = Math.round(seconds / 60)
    if (minutes < 1) return "dưới 1 phút"
    const hours = Math.floor(minutes / 60)
    const rest = minutes % 60
    if (!hours) return minutes + " phút"
    return rest ? hours + " giờ " + rest + " phút" : hours + " giờ"
}
function formatEta(seconds, fraction) {
    if (seconds < 90) return fraction === undefined || fraction >= 0.85 ? "sắp xong" : "còn dưới 2 phút"
    return "còn khoảng " + formatLength(seconds)
}
// Thời gian còn lại của một cuốn đang chạy theo bước máy đang ước, hay null khi chưa có tốc độ. `short`: gọn cho cột hẹp của bảng.
function etaOf(book, short) {
    if (!book.eta) return null
    function say(step, left) { return short ? step + " " + left.replace(/^còn khoảng /, "còn ") : "pha " + step + " " + left }
    if (book.eta.phase === "speaker") {
        const pass = book.speakerPass
        return say(short ? "dò người nói" : "xác định người nói", formatEta(book.eta.seconds, pass && pass.total ? pass.done / pass.total : undefined))
    }
    const synthesis = book.eta.phase === "synthesis"
    const left = formatEta(book.eta.seconds, synthesis ? book.progress.synthesis : book.progress.analysis)
    return say(synthesis ? "thu âm" : "phân tích", left)
}
function formatDate(epochSeconds) {
    const date = new Date(epochSeconds * 1000)
    return date.getDate() + "/" + (date.getMonth() + 1) + "/" + date.getFullYear()
}
function two(value) { return value < 10 ? "0" + value : String(value) }
function formatTime(epochSeconds, nowMs) {
    const date = new Date(epochSeconds * 1000)
    const today = new Date(nowMs === undefined ? Date.now() : nowMs)
    const time = two(date.getHours()) + ":" + two(date.getMinutes())
    return date.toDateString() === today.toDateString() ? time : time + " · " + date.getDate() + "/" + (date.getMonth() + 1)
}
function formatRelative(epochSeconds, nowMs) {
    if (!epochSeconds) return ""
    const delta = (nowMs === undefined ? Date.now() : nowMs) / 1000 - epochSeconds
    if (delta < 60) return "vừa xong"
    if (delta < 3600) return Math.floor(delta / 60) + " phút trước"
    if (delta < 86400) return Math.floor(delta / 3600) + " giờ trước"
    const days = Math.floor(delta / 86400)
    if (days === 1) return "hôm qua"
    if (days < 7) return days + " ngày trước"
    return formatDate(epochSeconds)
}
// Mốc thời gian nói kiểu người: "hôm nay 14:02", "tối qua 23:41", "hôm qua 09:15", "3 ngày trước" (formatWhen của shared/format.ts)
function formatWhen(epochSeconds, nowMs) {
    if (!epochSeconds) return ""
    const date = new Date(epochSeconds * 1000)
    const now = nowMs === undefined ? Date.now() : nowMs
    const today = new Date(now)
    const days = Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate()).getTime() - new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()) / 86400000)
    const time = two(date.getHours()) + ":" + two(date.getMinutes())
    if (days <= 0) return now / 1000 - epochSeconds < 60 ? "vừa xong" : "hôm nay " + time
    if (days === 1) return date.getHours() >= 18 ? "tối qua " + time : "hôm qua " + time
    if (days < 7) return days + " ngày trước"
    return formatDate(epochSeconds)
}
// Cách đọc để HIỆN: chữ đầu mỗi từ viết hoa ("rên-ta-rô" -> "Rên-ta-rô"); dữ liệu giữ nguyên cách đọc đã lưu (shownReading của shared/format.ts)
function shownReading(spoken) {
    return String(spoken).replace(/(^|\s)(\S)/g, function(match, gap, letter) {
        return letter.toLowerCase() === letter && letter.toUpperCase() !== letter ? gap + letter.toUpperCase() : match
    })
}

// ---- data.ts: trạng thái ----
function phaseTone(phase, running) {
    if (phase === "done") return "success"
    if (phase === "error") return "danger"
    if (running) return "accent"
    if (phase === "analysis" || phase === "casting" || phase === "synthesis" || phase === "stopped") return "warning"
    return "muted"
}
function queueLabel(position) { return position <= 1 ? "Sắp tới lượt" : "Còn " + (position - 1) + " việc trước" }
// Nhãn + màu + "đang chạy" của trạng thái một dự án: MỘT nơi cho đầu trang dự án và bảng dự án.
function projectStatus(book) {
    const running = Boolean(book.running || book.starting)
    return {
        label: book.queuePosition ? queueLabel(book.queuePosition) : book.starting ? "Đang khởi động" : book.precast && book.precast.held ? "Chờ bạn duyệt" : book.statusLabel || "",
        tone: book.queuePosition || book.paused || book.stopping ? "warning" : phaseTone(book.phase, running),
        live: running && !book.paused && !book.stopping
    }
}
function isLive(book) { return Boolean(book.running || book.starting) }

// ---- polling.ts ----
var BACKOFF_CAP_MS = 120000
// Nhịp hỏi kế tiếp (ms), hay 0 = thôi hỏi: 404 / chỉ-nghe dừng hẳn; lỗi khác gấp đôi theo số lần lỗi liên tiếp tới trần.
function pollDelay(base, errorStatus, errorCount) {
    if (errorStatus === 404 || errorStatus === "listenOnly") return 0
    if (!errorCount || base === 0) return base
    return Math.min(base * Math.pow(2, Math.min(errorCount, 8)), BACKOFF_CAP_MS)
}
var LIVE_MS = 2000
var IDLE_MS = 15000
function libraryInterval(books) { return (books || []).some(isLive) ? 5000 : IDLE_MS }
function bookInterval(book) { return book && isLive(book) ? LIVE_MS * 1.5 : IDLE_MS }
function failureText(status, message) {
    if (status === 0) return "Mất kết nối tới ABook."
    return message || "Sách có thể đã bị chuyển hoặc xoá."
}
// Trang dự án khi lần hỏi gần nhất hỏng: sách đã mất -> "gone"; đã có bản cũ -> "stale"; chưa từng có -> "error"; không lỗi -> "".
function bookFailure(hasData, errorStatus) {
    if (errorStatus === 404) return "gone"
    if (hasData && errorStatus !== null && errorStatus !== undefined) return "stale"
    if (!hasData) return "error"
    return ""
}

// ---- projectGroups.ts: gom phần của một cuốn, đưa nhóm đang chạy lên đầu ----
function unitOfGroup(group) {
    if (group.key.indexOf("chain:") === 0) return "phần"
    for (const book of group.books) {
        const match = String(book.title).match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b/i)
        if (match) { const word = match[2].toLowerCase(); return word === "quyển" || word === "phần" ? word : "tập" }
    }
    return "tập"
}
function groupParts(books) {
    const groups = LibraryLogic.sections(books.map(function(b) { return Object.assign({}, b, {bookId: b.id}) }))
    return groups.map(function(group) {
        if (group.books.length < 2 || group.key.indexOf("book:") === 0) return {kind: "book", book: group.books[0]}
        return {kind: "series", name: group.title, unit: unitOfGroup(group), books: group.books}
    })
}
function entryBooks(entry) { return entry.kind === "book" ? [entry.book] : entry.books }
function splitLive(entries) {
    const live = entries.filter(function(entry) { return entryBooks(entry).some(isLive) })
    return {live: live, rest: entries.filter(function(entry) { return live.indexOf(entry) < 0 })}
}
// Hàng phẳng của bảng: dòng tên nhóm (cuốn nhiều phần) rồi các phần của nó, hay một dự án lẻ. `key` ổn định cho mô hình cập nhật tại chỗ.
function tableRows(books) {
    const split = splitLive(groupParts(books))
    const rows = []
    for (const entry of split.live.concat(split.rest)) {
        if (entry.kind === "book") rows.push({key: "book:" + entry.book.id, kind: "book", id: entry.book.id, book: entry.book, grouped: false})
        else {
            rows.push({key: "series:" + entry.name, kind: "group", name: entry.name, unit: entry.unit, count: entry.books.length,
                       label: entry.name + " · " + entry.books.length + " " + entry.unit})
            for (const book of entry.books) rows.push({key: "book:" + book.id, kind: "book", id: book.id, book: book, grouped: true})
        }
    }
    return rows
}

// Cột của bảng (COLUMNS của ProjectsScreen.tsx): `width` là bề ngang cả hàng, đã gồm đệm 12 hai bên. Khổ "wide": 40 · tên · 230 · 190 · 100;
// "mid": 40 · tên · 190 · 170 · 36 (chỗ "…"); "stacked": 40 · tên · 36, trạng thái và tiến độ xếp dưới tên.
function tableColumns(width, kind) {
    const pad = 12, gap = 16, inner = width - 2 * pad
    const wide = kind === "wide", stacked = kind === "stacked"
    const statusW = wide ? 230 : 190, progressW = wide ? 190 : 170, updatedW = wide ? 100 : 0, moreW = 36
    const nameX = pad + 40 + gap
    const nameW = Math.max(80, stacked ? inner - 40 - gap - moreW - 4
                                        : inner - 40 - statusW - progressW - (wide ? updatedW : moreW) - 4 * gap)
    const statusX = nameX + nameW + gap
    const progressX = statusX + statusW + gap
    return {nameX: nameX, nameW: nameW, statusX: statusX, statusW: statusW, progressX: progressX, progressW: progressW,
            updatedX: progressX + progressW + gap, updatedW: updatedW}
}
// Khổ của bảng theo bề ngang của khung chữ (màn hẹp: trạng thái và tiến độ dưới tên)
function tableKind(bodyWidth) { return bodyWidth >= 1000 ? "wide" : bodyWidth >= 700 ? "mid" : "stacked" }

// ---- ProjectsScreen.tsx: nội dung một hàng ----
function rowSubtitle(book) {
    const settings = book.settings || {}
    return [settings.narrator && "Giọng kể " + settings.narrator, settings.profile !== "balanced" && settings.profileLabel].filter(Boolean).join(" · ")
}
function rowDetail(book) {
    if (!book.chapters) return ""
    const live = isLive(book)
    return book.phase !== "done" && book.eta && live ? etaOf(book, true) : book.chapters.completed + "/" + book.chapters.total + " chương"
}
function rowNeeds(book) {
    if (!book.chapters) return []
    return [
        book.pendingChanges ? book.pendingChanges + " thay đổi chờ áp" : book.phase === "done" && book.chapters.redo ? book.chapters.redo + " chương chờ thu lại" : "",
        book.chapters.missingAudio ? book.chapters.missingAudio + " chương mất audio" : ""
    ].filter(Boolean)
}
// Cột trạng thái: xong là mặc định, không đeo nhãn trên mọi hàng; chỉ dự án chưa xong mới có viên trạng thái.
function rowShowsPill(book) { return !(book.phase === "done" && !book.queuePosition) }
function rowUpdated(book) { return isLive(book) ? "vừa xong" : formatRelative(book.updatedAt) }
function brokenLine(book) { return (book.brokenKind === "busy" ? "Chưa mở được: " : "Không đọc được: ") + book.broken }
function projectsSubtitle(count) { return count ? count + " dự án" : " " }

// ---- stopText.ts ----
var ANALYSIS_CUT_COST = "có thể ra một cuốn khác: người nói ở đoạn sau chỗ dừng có thể đổi, kéo theo nhân vật và giọng đọc"
var ANALYSIS_STOP_FACT = "Phần đã phân tích được giữ nguyên, nhưng làm tiếp từ chỗ dừng"
function stopAnalysisAdvice(book) {
    if (book.paused) return "Sách đang tạm dừng - đứng yên đúng chỗ, phần đã phân tích không mất. Cứ để tạm dừng tới khi muốn làm tiếp."
    if (book.canPause) return "Cần nghỉ thì bấm Tạm dừng: sách đứng yên rồi làm tiếp đúng chỗ, phần đã phân tích không mất."
    return ""
}
function pauseNotice(paused, book, onBattery) {
    if (paused) return {
        title: "Đang tạm dừng",
        description: "Sách đứng lại sau phần đang làm dở (lúc phân tích có thể mất vài phút) và giữ nguyên mọi thứ - bấm “Tiếp tục” là làm tiếp đúng chỗ ấy.",
        warn: false
    }
    if (book.paused) return {
        title: "Sách vẫn đang tạm dừng",
        description: book.paused === "battery" ? "Máy đang chạy pin nên Studio vẫn giữ sách. Cắm sạc là tự làm tiếp."
                                                : "Sách chưa làm tiếp được. Đợi vài giây rồi xem lại; nếu vẫn đứng, bấm “Tiếp tục” lần nữa.",
        warn: true
    }
    return {
        title: "Đang làm tiếp",
        description: onBattery ? "Sách làm tiếp ngay trên pin - chậm và hao pin hơn. Cắm sạc rồi rút lại thì sách sẽ tạm dừng lại."
                               : "Sách làm tiếp đúng chỗ đã tạm dừng.",
        warn: false
    }
}
function queueWaitNotice(waitsOn) {
    return waitsOn.paused === "battery"
        ? "“" + waitsOn.title + "” đang tạm dừng vì máy chạy pin nên cuốn này chưa tới lượt - cắm sạc là cuốn kia tự làm tiếp, hay bấm “Tiếp tục” ở cuốn kia để làm tiếp ngay trên pin."
        : "“" + waitsOn.title + "” đang tạm dừng nên cuốn này chưa tới lượt - bấm “Tiếp tục” ở cuốn kia để hàng chạy tiếp."
}
// "Tiếp tục" phải hỏi trước: pha phân tích đã bị ngắt giữa chừng (AGENTS.md: dừng giữa pha phân tích là đổi quyển sách).
function asksBeforeResume(book) { return book.phase !== "done" && Boolean(book.analysisInterrupted) }
function stopTitle(book) { return book.phase === "analysis" ? "Dừng phân tích?" : "Dừng thu âm?" }
function stopDescription(book) {
    if (book.phase === "analysis") return ""
    return book.paused ? "Tạm dừng vẫn giữ bộ nhớ card đồ hoạ. Dừng hẳn thì nhả ra; việc đã xong giữ nguyên."
                       : "Mọi chương và câu đã xong được giữ nguyên - làm tiếp lúc nào cũng được, từ đúng chỗ dừng."
}
// Hộp Dừng lúc phân tích: hai đoạn cảnh báo (câu thứ hai nói nên để chạy hết bước này).
function stopWarning(book) {
    if (book.phase !== "analysis") return null
    const eta = etaOf(book)
    const advice = stopAnalysisAdvice(book)
    return {fact: ANALYSIS_STOP_FACT + " - " + ANALYSIS_CUT_COST + ".",
            advice: "Nên để chạy hết bước này" + (eta ? " (" + eta + ")" : "") + ". " + advice}
}
function resumeWarning(book) {
    return {fact: "Phân tích của “" + book.title + "” đã dừng giữa chừng.", cost: " Làm tiếp từ chỗ ấy " + ANALYSIS_CUT_COST + " - khác với khi phân tích liền một mạch.",
            advice: "Muốn chắc như chạy liền mạch: làm lại phân tích từ đầu."}
}

// ---- errorText.ts ----
var KNOWN_ERRORS = [
    {pattern: /out of memory|CUBLAS_STATUS_ALLOC_FAILED|CUDA error: .*memory|OutOfMemoryError|bad allocation/i,
     summary: "Card đồ hoạ hết bộ nhớ.",
     hint: "Đóng các app khác đang dùng card đồ hoạ (trò chơi, trình duyệt có video...) rồi bấm Tiếp tục."},
    {pattern: /disk free (\d+(?:[.,]\d+)?) GB/i,
     summary: function(match) { return "Ổ đĩa chứa thư viện sách chỉ còn " + match[1].replace(",", ".") + " GB." },
     hint: "Giải phóng thêm dung lượng ở ổ đó (làm sách cần chừng 12 GB trống; dây chuyền tự làm tiếp khi đủ chỗ) rồi bấm Tiếp tục."},
    {pattern: /model .* không sẵn sàng/i,
     summary: "Chưa dùng được model phân tích truyện (Ollama chưa chạy hoặc chưa có model).",
     hint: "Bấm Tiếp tục để thử lại; nếu vẫn lỗi, mở Ollama (biểu tượng ở khay hệ thống) và kiểm model phân tích đã được tải chưa.",
     studioHint: "Studio tự bật Ollama riêng của nó: bấm Tiếp tục để thử lại; nếu vẫn lỗi, vào Dự án bấm Sửa Studio - nó bật Ollama, kiểm model và tải lại phần thiếu."},
    {pattern: /ollama|11434|actively refused|Connection refused|ConnectionError|Max retries exceeded/i,
     summary: "Chưa kết nối được Ollama (phần chạy mô hình phân tích).",
     hint: "Mở Ollama (biểu tượng ở khay hệ thống) rồi bấm Tiếp tục.",
     studioHint: "Studio tự bật Ollama riêng của nó nên không có gì để mở tay: bấm Tiếp tục để thử lại; nếu vẫn lỗi, vào Dự án bấm Sửa Studio."},
    {pattern: /No space left|ENOSPC|disk full|database or disk is full|WinError 112|not enough space|disk quota/i,
     summary: "Ổ đĩa hết chỗ trống.",
     hint: "Giải phóng dung lượng ở ổ chứa thư viện sách rồi bấm Tiếp tục."}
]
// Lỗi thô -> câu cho người nghe + việc nên làm + nguyên văn.
function friendlyError(raw, bundledStudio, redo, studioLostModel) {
    const detail = String(raw).trim()
    if (studioLostModel && /ollama|model|qwen/i.test(detail)) {
        return {summary: "Studio mất model phân tích truyện (file đã bị xoá hay hỏng).",
                hint: redo ? "Vào Dự án, bấm Sửa Studio để tải lại đúng phần ấy, rồi bấm Làm lại phân tích từ đầu."
                           : "Vào Dự án, bấm Sửa Studio để tải lại đúng phần ấy, rồi bấm Tiếp tục.", detail: detail}
    }
    function advice(hint) { return redo ? hint.replace(/([Bb])ấm Tiếp tục/g, "$1ấm Làm lại phân tích từ đầu") : hint }
    for (const known of KNOWN_ERRORS) {
        const match = detail.match(known.pattern)
        if (match) return {summary: typeof known.summary === "function" ? known.summary(match) : known.summary,
                           hint: advice((bundledStudio && known.studioHint) || known.hint), detail: detail}
    }
    return {summary: "Có lỗi khi làm sách.", hint: advice("Bấm Tiếp tục để thử lại; nếu vẫn lỗi, mở Chi tiết bên dưới để gửi cho người hỗ trợ."), detail: detail}
}
// RunEnd: lượt chạy gần nhất chết vì sự cố mà sổ không có lỗi nào để hiện
function runEndText(end, bundledStudio, redo, lostModel) {
    const detail = [end.detail, end.exitCode ? "mã thoát " + end.exitCode : ""].filter(Boolean).join(" - ")
    const shown = friendlyError(detail, bundledStudio, redo, lostModel)
    const summary = end.state === "lost" ? "Lần chạy trước bị ngắt đột ngột (tiến trình làm sách bị tắt, máy khởi động lại hay hết điện)."
        : shown.summary === "Có lỗi khi làm sách." ? "Lần chạy trước dừng vì sự cố." : shown.summary
    return {summary: summary, hint: shown.hint, detail: shown.detail}
}

// ---- ProjectScreen.tsx: nút chính ----
// MỘT nút chính theo trạng thái (DESIGN.md mục 7); null = lúc ấy không có việc gì để bấm. Mọi việc khác vào "…".
function primaryKind(book) {
    const listen = book.chapters.completed > 0 ? "listen" : null
    const redoWaiting = book.phase === "done" ? (book.chapters.redo || 0) : 0
    if (book.queuePosition) return listen
    if (book.starting) return "starting"
    if (book.running) {
        if (book.stopping) return "stopping"
        if (book.paused) return "unpause"
        return book.canPause ? "pause" : listen
    }
    if (book.phase === "idle") return "start"
    if (book.precast && book.precast.held && book.phase !== "done") return "record"
    if (asksBeforeResume(book)) return "reanalyze"
    if (book.phase !== "done") return "continue"
    if (book.pendingChanges) return "apply"
    if (redoWaiting > 0) return "continue"
    return "listen"
}
// Nhãn + biểu tượng + trạng thái bận của nút chính; `busy`: lệnh đang chạy ({pause, start}).
function primaryButton(book, busy) {
    const kind = primaryKind(book)
    if (!kind) return null
    busy = busy || {}
    const held = Boolean(book.precast && book.precast.held)
    const table = {
        starting: {label: "Đang khởi động", busy: true},
        stopping: {label: "Đang dừng…", busy: true},
        unpause: {label: held ? "Thu âm" : "Tiếp tục", icon: held ? "mic-vocal" : "play", busy: Boolean(busy.pause)},
        pause: {label: "Tạm dừng", icon: "pause", busy: Boolean(busy.pause)},
        start: {label: "Bắt đầu", icon: "wand-sparkles", busy: Boolean(busy.start)},
        record: {label: "Thu âm", icon: "mic-vocal", busy: Boolean(busy.start)},
        reanalyze: {label: "Phân tích lại", icon: "rotate-ccw", busy: false},
        "continue": {label: "Tiếp tục", icon: "play", busy: Boolean(busy.start)},
        apply: {label: "Áp dụng " + (book.pendingChanges || 0) + " thay đổi", icon: "refresh-cw", busy: Boolean(busy.start)},
        listen: {label: "Nghe trong Thư viện", icon: "headphones", busy: false}
    }
    return Object.assign({kind: kind, enabled: kind !== "starting" && kind !== "stopping"}, table[kind])
}
// Các dòng nói thêm dưới hàng nút (hàng chờ, đang dừng, phân tích bị ngắt, chương chờ thu lại, tạm dừng vì pin).
function actionNotes(book, remote) {
    const kind = primaryKind(book)
    const live = Boolean(book.running)
    const notes = []
    const redoWaiting = book.phase === "done" ? (book.chapters.redo || 0) : 0
    const pending = book.segments.pending !== undefined && book.segments.pending !== null ? book.segments.pending : book.segments.total - book.segments.analyzed
    if (book.queuePosition) {
        notes.push("Chờ lượt " + book.queuePosition + ", tự chạy khi cuốn trước xong" + (book.seedPending ? ", giữ giọng và cách đọc tên" : "") + "."
                   + (book.queueWaitsOn ? " " + queueWaitNotice(book.queueWaitsOn) : ""))
    } else if (live && book.stopping) {
        notes.push("Dừng ở checkpoint kế, giữ phần đã xong; có thể mất vài phút.")
    } else if (kind === "reanalyze") {
        notes.push("Phân tích đã dừng giữa chừng" + (book.segments.total ? " (còn " + formatNumber(pending) + "/" + formatNumber(book.segments.total) + " câu)" : "")
                   + "; phân tích lại để giữ kết quả liền mạch, tiếp tục thì " + ANALYSIS_CUT_COST + ".")
    } else if (redoWaiting > 0 && kind === "continue") {
        notes.push((redoWaiting === 1 ? "1 chương đang chờ thu lại" : redoWaiting + " chương đang chờ thu lại") + " theo sửa của bạn. Bản cũ vẫn nghe được cho tới khi thu xong.")
    }
    if (live && book.paused === "battery") {
        notes.push("Studio tạm dừng; cắm sạc để tiếp tục.")
        notes.push("Làm sách trên pin chậm và hao pin. Bấm “Tiếp tục” để làm ngay trên pin" + (remote ? "." : ", hoặc đổi ở Cài đặt › Studio."))
    }
    return notes
}
function studioMissingNote(studio, book, remote) {
    if (!studio || (studio.installed && !studio.outdated) || book.running) return ""
    const redoWaiting = book.phase === "done" ? (book.chapters.redo || 0) : 0
    if (!(book.phase !== "done" || Boolean(book.pendingChanges) || redoWaiting > 0)) return ""
    const repair = Boolean(studio.installed && studio.outdated && studio.damaged)
    const update = Boolean(studio.installed && studio.outdated)
    return "Máy này " + (repair ? "cần sửa" : update ? "cần cập nhật" : "chưa cài") + " Studio nên chưa làm tiếp được phần phân tích và thu âm (nghe, xem, sửa cách đọc, nhạc nền, bìa và xuất sách vẫn được)."
}
function studioMissing(studio) {
    const update = Boolean(studio && studio.installed && studio.outdated)
    const repair = Boolean(update && studio.damaged)
    return {missing: Boolean(studio && (!studio.installed || studio.outdated)), update: update, repair: repair,
            action: repair ? "Sửa Studio" : update ? "Cập nhật Studio" : "Cài Studio"}
}
function startRefusal(missing) {
    return {title: missing.repair ? "Cần sửa Studio" : missing.update ? "Cần cập nhật Studio" : "Cần cài Studio", description: "Phân tích và thu âm chạy bằng Studio."}
}

// ---- Menu "…" ----
function separator() { return {sep: true} }
function item(key, icon, text, extra) { return Object.assign({key: key, icon: icon, text: text}, extra || {}) }
// "Làm việc ở máy tính <tên>" (shared/peerStudio.ts onComputerLine)
function onComputerLine(verb, name) { return name && name !== "máy tính" ? verb + " ở máy tính " + name : verb + " ở máy tính" }
// Việc ít dùng của đầu trang dự án (đứng trên các mục đổi tên, làm tiếp, xoá).
function actionExtras(book, opts) {
    const kind = primaryKind(book)
    const live = Boolean(book.running)
    const out = []
    if (book.chapters.completed > 0 && kind !== "listen") out.push(item("listen", "headphones", "Nghe trong Thư viện"))
    if (asksBeforeResume(book) && !live && !book.starting && !book.queuePosition) out.push(item("resumeAnyway", "play", "Vẫn tiếp tục…"))
    if (live && !book.stopping) out.push(item("stop", "square", "Dừng…"))
    if (live && book.pendingChanges) out.push(item("apply", "refresh-cw", book.pendingChanges + " thay đổi chờ áp"))
    if (book.queuePosition) out.push(item("leaveQueue", "square", "Bỏ xếp hàng"))
    if (book.phase === "idle" && !live && !book.queuePosition) out.push(item("redo", "sliders-horizontal", "Sửa thiết lập"))
    if (book.chapters.completed > 0) out.push(item("export", "folder-down", "Xuất…"))
    if (opts.next > 0) out.push(item("addChapters", "book-plus", "Thêm " + opts.next + " chương"))
    if (!opts.remote) out.push(item("reveal", "folder-open", "Mở thư mục"))
    out.push(item("details", "info", "Chi tiết"))
    return out
}
// "…" của một dự án: `extras` (đứng trên) rồi đổi tên, làm tiếp, xoá. `rename: false` cho dự án hỏng.
function projectMenu(book, opts) {
    opts = opts || {}
    const out = []
    const extras = opts.extras || []
    if (extras.length) { for (const e of extras) out.push(e); out.push(separator()) }
    if (opts.rename !== false) out.push(item("rename", "text-cursor-input", "Đổi tên…"))
    if (!book.broken) {
        const analyzed = ((book.segments && book.segments.analyzed) || 0) > 0
        out.push(item("continueBook", "book-plus", "Làm tiếp cuốn này…", {disabled: !analyzed, hint: analyzed ? "" : "chạy phần này trước"}))
    }
    out.push(separator())
    if (opts.remote) out.push(item("onComputer", "monitor", onComputerLine("Xoá dự án", opts.computer || "máy tính"), {disabled: true}))
    else out.push(item("delete", "trash-2", "Xoá dự án…", {danger: true}))
    return out
}
function rowMenu(book, local, computer) {
    const extras = []
    if (book.broken) {
        if (book.backup) extras.push(item("restore", "history", "Khôi phục bản sao…"))
        extras.push(item("reveal", "folder-open", "Mở thư mục"))
        return projectMenu(book, {rename: false, extras: extras, remote: !local, computer: computer})
    }
    if (local) extras.push(item("reveal", "folder-open", "Mở thư mục"))
    return projectMenu(book, {extras: extras, remote: !local, computer: computer})
}
function projectDetails(book) {
    const s = book.settings || {}
    function clock(seconds) {
        const whole = Math.max(0, Math.floor(seconds)), h = Math.floor(whole / 3600), m = Math.floor((whole % 3600) / 60), sec = whole % 60
        return (h ? h + ":" : "") + (h ? two(m) : String(m)) + ":" + two(sec)
    }
    function analyzerLabel(model) {
        const own = /^abook-analyzer:v(\d+)$/.exec(String(model).replace(/:latest$/, ""))
        return own ? "Bộ phân tích bản " + own[1] : "Bộ phân tích tuỳ chọn"
    }
    return [
        s.narratorPending ? "Giọng kể " + s.narratorPending + " (chờ áp dụng)" : s.narrator ? "Giọng kể " + s.narrator : "",
        s.profileLabel || "",
        s.analyzer ? analyzerLabel(s.analyzer) : "",
        book.createdAt ? "Tạo " + formatDate(book.createdAt) : "",
        book.position ? "Nghe lần cuối " + formatRelative(book.position.at) + " ở " + clock(book.position.seconds) : ""
    ].filter(Boolean)
}

// ---- Tab của trang dự án ----
var TAB_LABEL = {chapters: "Chương", precast: "Duyệt trước khi thu", work: "Việc cần duyệt", script: "Kịch bản", review: "Cần nghe lại", cast: "Nhân vật", music: "Nhạc nền", activity: "Nhật ký"}
var MAIN_TABS = ["chapters", "work", "review", "cast", "music"]
var ALL_TABS = ["chapters", "precast", "work", "script", "review", "cast", "music", "activity"]
function canReview(book) { return Boolean(book.precast && book.precast.ready) && book.phase !== "done" }
function moreTabs(precast) { return (precast ? ["precast"] : []).concat(["script", "activity"]) }
function tabOf(value) { return ALL_TABS.indexOf(value) >= 0 ? value : "chapters" }
// Nhãn nút "Thêm": nằm trong "Thêm" thì mang tên tab đang chọn.
function moreLabel(tab, precast) { return moreTabs(precast).indexOf(tab) >= 0 ? TAB_LABEL[tab] : "Thêm" }
function moreCount(tab, precast, counts) {
    const more = moreTabs(precast)
    if (more.indexOf(tab) >= 0) return counts[tab] || 0
    return more.reduce(function(sum, key) { return sum + (counts[key] || 0) }, 0)
}
function tabPlaceholder(tab) { return "Mục này chưa mở trong bản này." }

// ---- Chương ----
// Dấu nhỏ trên một hàng chương, hay null (chương xong / chờ tới lượt là mặc định, không đeo nhãn).
function chapterMark(chapter) {
    if (chapter.statusLabel === "Mất file audio") return {label: chapter.statusLabel, tone: "warning"}
    if (chapter.status === "completed" && !chapter.redo) return null
    if (chapter.status === "pending" || chapter.status === "analyzed" || chapter.status === "synthesizing" || chapter.status === "verifying") return null
    return {label: chapter.statusLabel, tone: chapter.status === "failed" ? "danger" : chapter.status === "warning" ? "warning" : "muted"}
}
function chapterWorking(chapter) { return chapter.status === "synthesizing" || chapter.status === "verifying" }
function chapterRecorded(chapter) { return chapter.segments.total ? chapter.segments.finished / chapter.segments.total : 0 }
// Độ dài khi đã có audio, chưa thì số câu
function chapterLength(chapter) {
    return chapter.status === "completed" || chapter.redo ? formatLength(chapter.seconds) : chapter.segments.total ? formatNumber(chapter.segments.total) + " câu" : ""
}
function chapterDone(chapter) { return chapter.completedAt ? formatRelative(chapter.completedAt) : "" }
function chapterWorkingText(chapter, running) { return (running ? "" : "dừng ở ") + chapter.segments.finished + "/" + chapter.segments.total }

// ---- Nhật ký ----
function activityGroups(items) {
    const result = []
    for (const entry of items || []) {
        const day = formatDate(entry.at)
        const last = result[result.length - 1]
        if (last && last.day === day) last.items.push(entry)
        else result.push({day: day, items: [entry]})
    }
    return result
}
function activityTime(entry) { return formatTime(entry.at).split(" · ")[0] }

// ---- Đầu trang một dự án ----
// Dòng phụ dưới tên (DotJoin của ProjectScreen.tsx, sau viên trạng thái): số chương · độ dài · việc cần để ý. StyledText; `warn` là màu cảnh báo.
function metaLine(book, warn) {
    const parts = [(book.phase !== "done" && book.chapters.total ? book.chapters.completed + "/" + book.chapters.total : String(book.chapters.total)) + " chương"]
    if (book.audioSeconds > 0) parts.push(formatLength(book.audioSeconds))
    if (book.chapters.missingAudio) parts.push("<font color=\"" + warn + "\"><b>" + book.chapters.missingAudio + " chương mất file audio</b></font>")
    if (book.chapters.redo) parts.push(book.chapters.redo + " chương chờ thu lại")
    return parts.join(" · ")
}
// Dải báo khi lần hỏi gần nhất hỏng mà vẫn còn bản cũ của sách
function staleLine(status, text) {
    return status === 0 ? "Mất kết nối tới ABook, đang thử lại…" : "Chưa tải lại được sách: " + failureText(status, text) + " Đang thử lại…"
}
// Lỗi của lần làm sách cho người nghe: {summary, hint, detail} hay null. `studio`: máy này có Studio.
function bookProblem(book, studio, studioLostModel) {
    if (book.lastError && book.phase === "error") return friendlyError(book.lastError, studio, asksBeforeResume(book), studioLostModel)
    if (book.runEnd && !book.running && !book.starting) return runEndText(book.runEnd, studio, asksBeforeResume(book), studioLostModel)
    return null
}
var TAB_ICON = {precast: "headphones", script: "book-open-text", activity: "history"}
function moreItems(precast) {
    return moreTabs(precast).map(function(key) { return item(key, TAB_ICON[key], TAB_LABEL[key]) })
}
var LEVEL_TONE = {error: "danger", warning: "warning"}

// Tên thư mục cuối của một đường dẫn (folderName của shared/MissingLibrary.tsx)
function folderName(path) { return String(path).split(/[\\/]/).filter(Boolean).pop() || String(path) }

// ---- Chữ của hộp ----
function renameDescription() { return "Tên mới hiện ở thư viện, điện thoại và file xuất." }
function deleteDescription() { return "Cả thư mục dự án vào Thùng rác của Windows, khôi phục được. File truyện gốc và sách đã xuất giữ nguyên." }
function applyTitle(count) { return "Áp dụng " + count + " thay đổi?" }
function applyDescription() { return "Máy chỉ thu lại những câu bị ảnh hưởng, rồi dựng lại các chương có câu ấy - không làm lại cả cuốn." }
function peerPath(path, peer) { return Peer.throughPeer(path, peer) }
