.pragma library
.import "SizeFormat.js" as Size

// Phần thuần của "Sửa sách" và "Tìm bìa" (EditBook.tsx, CoverSearch.tsx, shared/capabilities.ts, musicLevels.ts, studio/musicLocal.ts): chữ và quy tắc
// chép nguyên từ bản web để hai nền tảng nói cùng một câu.

// Chữ người gõ như máy chủ làm sạch: khoảng trắng gộp một dấu cách, bỏ đầu cuối.
function tidy(text) { return String(text || "").trim().replace(/\s+/g, " ") }

// Ô "Tác giả" lưu được không: chữ gõ khác tác giả đang hiện (trống cũng là một thay đổi nếu sách đang có tác giả).
function authorSaveable(typed, shown) { return tidy(typed) !== tidy(shown || "") }

// ---- capabilities.ts ----
var LINK_BOOK = "Sách này lấy từ máy tính khác - muốn sửa thì sửa ở máy ấy"
function canEditLayer(caps) { return !!caps && (!!caps.workshop || !caps.link) }
function studioNeed(caps) {
    if (!caps || caps.link) return null
    if (caps.workshop && caps.toolchain) return null
    if (!caps.toolchain) return "cần cài Studio"
    return "cuốn này chưa có dự án Studio"
}
function syncsToComputer(caps) { return !!(caps && caps.sync) && !(caps && caps.workshop) }
function editBlockedNote(caps) { return caps && caps.link && !caps.workshop ? LINK_BOOK : null }
function holderName(remote) { return remote && typeof remote === "object" && remote.computer ? remote.computer : "máy tính" }

// Lời mô tả dưới tên hộp "Sửa sách"
function editDescription(book, computer) {
    if (computer) return "Đổi có hiệu lực ngay trên máy tính " + computer + " - audio và chữ của người làm sách giữ nguyên."
    if (syncsToComputer(book.capabilities))
        return "Đổi có hiệu lực ngay trên máy này và được gửi về " + holderName(book.remote) + " khi kết nối - audio và chữ của người làm sách giữ nguyên."
    return "Đổi có hiệu lực ngay và chỉ trên máy này - audio và chữ của người làm sách giữ nguyên."
}

// ---- model.ts seriesOf: bộ truyện từ tên sách, làm ô tìm bìa mặc định ----
function seriesName(title) {
    const match = String(title || "").match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b/i)
    return match ? match[1].trim() : String(title || "").trim()
}

// ---- format.ts formatClock ----
function formatClock(seconds) {
    if (!isFinite(seconds) || seconds < 0) seconds = 0
    const whole = Math.floor(seconds), hours = Math.floor(whole / 3600), minutes = Math.floor((whole % 3600) / 60), secs = whole % 60
    const mm = hours ? String(minutes).padStart(2, "0") : String(minutes)
    return (hours ? hours + ":" : "") + mm + ":" + String(secs).padStart(2, "0")
}

// ---- musicLevels.ts ----
var MUSIC_LEVELS = [[-14, "To"], [-17, "Hơi to"], [-20, "Vừa (mặc định)"], [-24, "Nhỏ"], [-28, "Rất nhỏ"]]
var LEVEL_NOTES = {"-28": "dễ nghe lời nhất"}
function levelText(value, name) { const note = LEVEL_NOTES[String(value)]; return note ? name + " (" + note + ")" : name }
// [{value, label}] cho ô chọn: các mức có sẵn, thêm mức hiện tại của sách nếu nó không trùng mức nào
function levelOptions(current) {
    let list = MUSIC_LEVELS.slice()
    if (!list.some(function(item) { return item[0] === current }))
        list = list.concat([[current, String(current).replace(".", ",") + " dB (của sách)"]]).sort(function(a, b) { return b[0] - a[0] })
    return list.map(function(item) { return {value: item[0], label: levelText(item[0], item[1])} })
}

// ---- EditBook.tsx musicEditView: sách đóng gói giữ nguyên, dự án Studio đọc plan / overrides ----
function musicEditView(raw) {
    if (!raw) return null
    if ("hasMusic" in raw) return raw
    const level = (raw.overrides && raw.overrides.levelDb !== undefined) ? raw.overrides.levelDb : (raw.plan && raw.plan.levelDb !== undefined ? raw.plan.levelDb : -20)
    return {
        project: true,
        hasMusic: !!(raw.plan && raw.plan.scenes && raw.plan.scenes.length),
        enabled: !(raw.overrides && raw.overrides.enabled === false),
        levelDb: level,
        defaultLevelDb: -20,
        cues: [],
        error: raw.error
    }
}

// ---- CoverSearch.tsx ----
var PROVIDER_NAMES = {itunes: "iTunes", open_library: "Open Library", google_books: "Google Books"}
function failedSourcesNote(failed) {
    return "Chưa nối được " + failed.map(function(name) { return PROVIDER_NAMES[name] || String(name).replace("_", " ") }).join(", ") + ". Thử lại hoặc chọn ảnh trên máy."
}
function coverTitle(found) { return found.title + (found.author ? " - " + found.author : "") + " (" + found.provider + ")" }

// ---- studio/musicLocal.ts ----
var MY_MUSIC_INTRO = "Thêm nhạc làm nền; bài đã chọn đi cùng file sách."
var MY_MUSIC_HELP = "Nhạc được chép vào kho máy này; dùng Đổi bài để chọn cho từng đoạn. Hỗ trợ mp3, m4a, ogg, opus, flac, wav. Bài đã chọn đi cùng .abook / .abookproj, vẫn nghe được trên máy khác, không ai khác tải được. Tên bài và nghệ sĩ lấy từ file; ABook không xác nhận giấy phép."
var CANCELLED_NOTE = "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng."
var RETRYING_NOTE = "Mạng chập chờn - đang thử lại…"
function hasVocals(track) { return !!track.analysed && track.vocalsLikely === true }
function autoLabel(track) {
    if (track.auto === "off") return "Máy không tự chọn bài này"
    if (!hasVocals(track)) return null
    return track.auto === "on" ? "Có vẻ có lời - bạn cho máy tự chọn" : "Có vẻ có lời - máy không tự chọn bài này"
}
function autoSwitch(track) {
    if (track.auto === "off") return {text: "Tự chọn lại", next: null}
    if (track.auto === "on") return {text: "Theo mặc định", next: null}
    return hasVocals(track) ? {text: "Cho tự chọn", next: "on"} : {text: "Tắt tự chọn", next: "off"}
}
function analysisLabel(track) { return track.analysed ? "Đã phân tích - máy có thể tự chọn" : "Chưa phân tích - máy chưa tự chọn, bạn vẫn ghim được" }
function mineNote(item) {
    const notes = [autoLabel(item), item.analysed ? (item.fits ? "Hợp không khí đoạn này" : null) : analysisLabel(item)].filter(function(note) { return !!note })
    return notes.length ? notes.join(" · ") : ""
}
function localDigest(link) {
    const digest = String(link).indexOf("local:") === 0 ? String(link).slice(6) : ""
    return /^[0-9a-f]{40}$/.test(digest) ? digest : null
}
function modulePercent(module) { return module.total > 0 ? Math.min(100, Math.floor(module.done / module.total * 100)) : 0 }
function moduleLabel(module) {
    if (module.state === "error") return module.error
    if (module.state === "downloading") return module.retrying ? RETRYING_NOTE + " (Phân tích nhạc, " + modulePercent(module) + "%)" : "Đang tải Phân tích nhạc (" + Size.formatSize(module.total) + ", một lần) " + modulePercent(module) + "%"
    if (module.analysing) return "Đang phân tích nhạc đã thêm"
    if (module.state === "unsupported") return module.reason ? "Máy này chưa phân tích được nhạc: " + module.reason + "." : "Máy này chưa phân tích được nhạc."
    if (module.state === "outdated" && module.stopped) return "Phân tích nhạc đang tắt; tải lại " + Size.formatSize(module.outdatedBytes || module.total) + ". Vẫn ghim tay được."
    if (module.state === "outdated") return (module.cancelled ? CANCELLED_NOTE + " " : "") + "Có bản mới - " + Size.formatSize(module.outdatedBytes || module.total) + "; bản hiện tại vẫn dùng được."
    if (module.state === "ready") {
        if (module.restart) return "Phân tích nhạc đã cập nhật - mở lại ABook để dùng thư viện mới."
        if ((module.stale || 0) > 0) return module.stale + " bài dùng phân tích cũ; có thể phân tích lại."
        return ""
    }
    return (module.cancelled ? CANCELLED_NOTE + " " : "") + "Tải " + Size.formatSize(module.total) + " để tự chọn nhạc phù hợp trên máy."
}
// Tóm tắt nhập nhạc (importSummary): {title, description}
function importSummary(result) {
    const added = result.added || [], existing = result.existing || [], failed = result.failed || []
    const parts = []
    if (added.length) parts.push(added.length + " bài mới")
    if (existing.length) parts.push(existing.length + " bài đã có từ trước")
    if (!added.length && !existing.length)
        return {title: failed.length > 1 ? "Không thêm được file nào" : "Không thêm được file này", description: failed.join("\n")}
    const notes = []
    if (failed.length) notes.push(failed.join("\n"))
    const unanalysed = added.filter(function(track) { return !track.analysed }).length
    if (unanalysed) notes.push(unanalysed + " bài chưa phân tích - máy chưa tự chọn, bạn ghim được ở “Đổi bài”.")
    return {title: "Đã thêm: " + parts.join(", "), description: notes.join("\n")}
}

// ---- readings.ts ----
function cleanSpoken(value) { return String(value || "").normalize("NFC").trim().replace(/\s+/gu, " ") }

// Tên chương đang hiện trên dòng chương (nhãn + tên phụ nếu có)
function chapterShownName(chapter) { return chapter ? (chapter.fullTitle || chapter.title || "") : "" }

// Toast lỗi của web (tiêu đề + mô tả) thành MỘT câu thông báo: hai dòng
function toastText(title, description) { return description ? title + "\n" + description : title }
