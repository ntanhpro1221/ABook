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
var LEVEL_NOTES = {"-28": "rõ lời"}
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

// ---- readings.ts ----
function cleanSpoken(value) { return String(value || "").normalize("NFC").trim().replace(/\s+/gu, " ") }

// Tên chương đang hiện trên dòng chương (nhãn + tên phụ nếu có)
function chapterShownName(chapter) { return chapter ? (chapter.fullTitle || chapter.title || "") : "" }

// Toast lỗi của web (tiêu đề + mô tả) thành MỘT câu thông báo: hai dòng
function toastText(title, description) { return description ? title + "\n" + description : title }
