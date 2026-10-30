.pragma library
.import "SizeFormat.js" as Size

// Chữ và phép tính thuần của "Nhạc của tôi" (studio/musicLocal.ts, studio/musicImport.ts, shared/format.ts, listen/prepareAhead.ts của bản web), giữ nguyên lời.

var LOCAL_PREFIX = "local:"
var MY_MUSIC_INTRO = "Thêm nhạc làm nền; bài đã chọn đi cùng file sách."
var MY_MUSIC_HELP = "Nhạc được chép vào kho máy này; dùng Đổi bài để chọn cho từng đoạn. Hỗ trợ mp3, m4a, ogg, opus, flac, wav. Bài đã chọn đi cùng .abook / .abookproj, vẫn nghe được trên máy khác, không ai khác tải được. Tên bài và nghệ sĩ lấy từ file; ABook không xác nhận giấy phép."
var CANCELLED_NOTE = "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng."
var RETRYING_NOTE = "Mạng chập chờn - đang thử lại…"

// "m:ss" hay "h:mm:ss" (formatClock của shared/format.ts)
function formatClock(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0
    var whole = Math.floor(seconds)
    var hours = Math.floor(whole / 3600)
    var minutes = Math.floor((whole % 3600) / 60)
    var secs = whole % 60
    var mm = hours ? String(minutes).padStart(2, "0") : String(minutes)
    return (hours ? hours + ":" : "") + mm + ":" + String(secs).padStart(2, "0")
}

function modulePercent(module) {
    return module.total > 0 ? Math.min(100, Math.floor((module.done / module.total) * 100)) : 0
}

// Câu báo về mô-đun "Phân tích nhạc", nói bằng điều người nghe cần biết.
function moduleLabel(module) {
    if (module.state === "error") return module.error
    if (module.state === "downloading") return module.retrying ? RETRYING_NOTE + " (Phân tích nhạc, " + modulePercent(module) + "%)" : "Đang tải Phân tích nhạc (" + Size.formatSize(module.total) + ", một lần) " + modulePercent(module) + "%"
    if (module.analysing) return "Đang phân tích nhạc đã thêm"
    if (module.state === "unsupported") return module.reason ? "Máy này chưa phân tích được nhạc: " + module.reason + "." : "Máy này chưa phân tích được nhạc."
    if (module.state === "outdated" && module.stopped)
        return "Phân tích nhạc đang tắt; tải lại " + Size.formatSize(module.outdatedBytes !== undefined ? module.outdatedBytes : module.total) + ". Vẫn ghim tay được."
    if (module.state === "outdated") return (module.cancelled ? CANCELLED_NOTE + " " : "") + "Có bản mới - " + Size.formatSize(module.outdatedBytes !== undefined ? module.outdatedBytes : module.total) + "; bản hiện tại vẫn dùng được."
    if (module.state === "ready") {
        if (module.restart) return "Phân tích nhạc đã cập nhật - mở lại ABook để dùng thư viện mới."
        if ((module.stale || 0) > 0) return module.stale + " bài dùng phân tích cũ; có thể phân tích lại."
        return ""
    }
    return (module.cancelled ? CANCELLED_NOTE + " " : "") + "Tải " + Size.formatSize(module.total) + " để tự chọn nhạc phù hợp trên máy."
}

// Có mời bật "Đo cảm xúc nhạc chính xác hơn" không: máy đủ sức, và đã có bộ phân tích nhạc.
function preciseOffered(module) {
    return Boolean(module && module.precise && module.precise.state !== "unavailable" && module.ready)
}
function preciseBusy(precise) {
    return Boolean(precise && (precise.state === "downloading" || precise.working))
}
function preciseLabel(precise) {
    var size = Size.formatSize(precise.bytes)
    if (precise.state === "downloading") {
        var percent = precise.total > 0 ? Math.min(100, Math.floor((precise.done / precise.total) * 100)) : 0
        return "Đang tải bộ đo cảm xúc chính xác hơn (" + size + ", một lần) " + percent + "%"
    }
    if (precise.state === "error") return precise.error
    if (precise.state === "missing") return "Đã bật nhưng chưa tải xong - bài mới thêm tạm dùng số cũ."
    if (precise.state === "ready") {
        if (precise.working) {
            return precise.pending > 0
                ? "Đang nghe kỹ " + precise.pending + " bài bạn đã thêm - bài chưa tới lượt vẫn dùng số cũ."
                : "Đang nghe kỹ bài vừa thêm"
        }
        return "Đang bật - bài mới thêm sẽ được nghe kỹ ngầm vài giây."
    }
    var how = precise.present ? "Chạy" : "Tải thêm " + size + " một lần, sau đó chạy"
    return (precise.cancelled ? CANCELLED_NOTE + " " : "") + "Máy nghe kỹ hơn từng bài bạn thêm để chọn nhạc nền hợp không khí truyện hơn. " + how + " ngầm vài giây mỗi bài, không cần mạng."
}

function localDigest(link) {
    var digest = String(link).indexOf(LOCAL_PREFIX) === 0 ? String(link).slice(LOCAL_PREFIX.length) : ""
    return /^[0-9a-f]{40}$/.test(digest) ? digest : null
}

function hasVocals(track) { return track.analysed && track.vocalsLikely === true }

// Nhãn khi máy không tự chọn bài này (có vẻ có lời hát, hay bạn đã tắt); bài bình thường thì không có nhãn.
function autoLabel(track) {
    if (track.auto === "off") return "Máy không tự chọn bài này"
    if (!hasVocals(track)) return null
    return track.auto === "on" ? "Có vẻ có lời - bạn cho máy tự chọn" : "Có vẻ có lời - máy không tự chọn bài này"
}

// Nút đổi công tắc tự chọn của bài: chữ trên nút và giá trị `auto` gửi đi (null = về mặc định).
function autoSwitch(track) {
    if (track.auto === "off") return {text: "Tự chọn lại", next: null}
    if (track.auto === "on") return {text: "Theo mặc định", next: null}
    return hasVocals(track) ? {text: "Cho tự chọn", next: "on"} : {text: "Tắt tự chọn", next: "off"}
}

function analysisLabel(track) {
    return track.analysed ? "Đã phân tích - máy có thể tự chọn" : "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được"
}

// Gộp kết quả của nhiều lượt nhập (mỗi file một lượt): danh sách bài và mô-đun lấy của lượt cuối.
function mergeImports(results) {
    var last = results[results.length - 1]
    var merged = {tracks: last ? last.tracks : [], analyzer: last ? last.analyzer : false, added: [], existing: [], failed: []}
    if (last && last.module) merged.module = last.module
    for (var i = 0; i < results.length; ++i) {
        merged.added = merged.added.concat(results[i].added || [])
        merged.existing = merged.existing.concat(results[i].existing || [])
        merged.failed = merged.failed.concat(results[i].failed || [])
    }
    return merged
}

// Câu báo sau khi nhập: bao nhiêu bài đã vào, bao nhiêu đã có sẵn, file nào không nhập được. Trả {kind, title, description}.
function importSummary(result) {
    var added = result.added || [], existing = result.existing || [], failed = result.failed || []
    var parts = []
    if (added.length) parts.push(added.length + " bài mới")
    if (existing.length) parts.push(existing.length + " bài đã có từ trước")
    if (!added.length && !existing.length)
        return {kind: "error", title: failed.length > 1 ? "Không thêm được file nào" : "Không thêm được file này", description: failed.join("\n")}
    var unanalysed = added.filter(function(track) { return !track.analysed }).length
    var notes = []
    if (failed.length) notes.push(failed.join("\n"))
    if (unanalysed) notes.push(unanalysed + " bài chưa phân tích - máy chưa tự chọn, bạn ghim được ở “Đổi bài”.")
    return {kind: failed.length ? "warning" : "success", title: "Đã thêm: " + parts.join(", "), description: notes.join("\n")}
}

// Lời báo của web (toast(title, {description})) thành một chuỗi của Api.notice: tên ở dòng đầu, lý do ở dòng sau.
function toast(title, description) {
    return description ? title + "\n" + description : title
}

// ---- Bộ nhớ (listen/prepareAhead.ts) ----
function storageLabel(usage) {
    return usage.total > 0 ? "Bản đọc đã làm chiếm " + Size.formatSize(usage.total) + " trên máy này." : "Chưa có bản đọc đã lưu."
}
function clearStorageQuestion(usage) {
    return "Dọn " + Size.formatSize(usage.total) + " bản đọc đã làm của mọi cuốn? Máy sẽ đọc lại khi nghe. Sách và chỗ đang nghe giữ nguyên."
}

// ---- Cập nhật (desktop/updateCheck.ts) ----
var UPDATE_CHECK_WAIT_MS = 45000
// Lời hiện dưới nút kiểm tra; `found` không cần lời (mục "bản mới đã có" hiện thay); vỏ im là lỗi mạng. Trả {tone, text} hay null.
function checkLine(detail, current) {
    if (detail && detail.state === "found") return null
    if (detail && detail.state === "latest") return {tone: "ok", text: "ABook" + (current ? " " + current : "") + " là bản mới nhất."}
    return {tone: "error", text: (detail && detail.message) || "Chưa thấy trả lời từ trang phát hành - bạn kiểm tra mạng rồi thử lại."}
}

// ---- Thành phần bên thứ ba (shared/thirdParty.ts) ----
var MAINTAINER_SECTION = "Ghi chú cho người bảo trì"
// Tách Markdown của THIRD_PARTY.md thành các mục theo tiêu đề `##`; phần mở đầu là mục không tên; mục của người bảo trì bị bỏ.
function parseThirdParty(markdown) {
    var sections = [{title: "", items: []}]
    var open = null
    var lines = String(markdown).replace(/\r/g, "").split("\n")
    for (var i = 0; i < lines.length; ++i) {
        var line = lines[i].trim()
        if (!line) { open = null; continue }
        if (line.indexOf("# ") === 0) continue
        if (line.indexOf("## ") === 0) { sections.push({title: line.slice(3).trim(), items: []}); open = null; continue }
        var section = sections[sections.length - 1]
        var bullet = /^[-*] /.test(line)
        if (bullet || !open) {
            open = {text: bullet ? line.slice(2) : line, bullet: bullet}
            section.items.push(open)
        } else {
            open.text += " " + line
        }
    }
    return sections.filter(function(s) { return s.items.length && s.title.indexOf(MAINTAINER_SECTION) !== 0 })
}
function escapeHtml(text) {
    return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
}
// Chữ đậm `**...**` và mã `...` của Markdown thành HTML của Text (RichText); còn lại để nguyên. `strong`: màu chữ đậm; `codeBack`: nền mã.
function inlineHtml(text, strong, codeBack) {
    var parts = String(text).split(/(\*\*[^*]+\*\*|`[^`]+`)/)
    var out = ""
    for (var i = 0; i < parts.length; ++i) {
        var part = parts[i]
        if (part.indexOf("**") === 0 && part.slice(-2) === "**" && part.length > 4)
            out += "<span style=\"font-weight:600; color:" + strong + "\">" + escapeHtml(part.slice(2, -2)) + "</span>"
        else if (part.charAt(0) === "`" && part.slice(-1) === "`" && part.length > 2)
            out += "<span style=\"font-family:monospace; background-color:" + codeBack + "\">&nbsp;" + escapeHtml(part.slice(1, -1)) + "&nbsp;</span>"
        else
            out += escapeHtml(part)
    }
    return out
}
