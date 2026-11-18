.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size

// Phần thuần của "Sửa sách" và "Tìm bìa" (EditBook.tsx, CoverSearch.tsx, shared/capabilities.ts, musicLevels.ts, studio/musicLocal.ts): chữ và quy tắc
// chép nguyên từ bản web để hai nền tảng nói cùng một câu.

// Phần thông tin của form "Sửa sách" (BookMetadata.tsx metadataOf): tác giả cùng các ô mô tả, lưu một lần bằng "Lưu thông tin".
function metadataOf(book) {
    return {author: book.author || "", illustrator: book.illustrator || "", altTitles: book.altTitles || [], genres: book.genres || [],
            summary: book.summary || "", source: book.source || {url: "", site: ""}}
}
// Bản nháp như máy chủ sẽ giữ (BookMetadata.tsx cleanMetadata, `book_metadata.clean`): tác giả một dòng (ký tự điều khiển / định dạng thành dấu
// cách, khoảng trắng gộp một dấu cách, trần 160), mục rỗng của danh sách bị bỏ. Ca dùng chung: tests/fixtures/book_metadata/saveable.json.
// Lớp ký tự là \p{C} của web viết ra (Cc + Cf thường gặp): V4 của Qt chưa chắc có \p{...}.
var AUTHOR_MAX = 160
var CONTROL = /[\u0000-\u001f\u007f-\u009f\u00ad\u0600-\u0605\u061c\u06dd\u070f\u180e\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u206f\ufeff\ufff9-\ufffb]/g
function cleanMetadata(draft) {
    const value = metadataOf(draft || {})
    const words = String(value.author).normalize("NFC").replace(CONTROL, " ").split(/\s+/).filter(function(word) { return word !== "" })
    const author = Array.from(words.join(" ")).slice(0, AUTHOR_MAX).join("").trim()
    const kept = function(list) { return list.filter(function(item) { return String(item).trim() !== "" }) }
    return {author: author, illustrator: value.illustrator, altTitles: kept(value.altTitles), genres: kept(value.genres), summary: value.summary, source: value.source}
}
// Nút "Lưu thông tin" bấm được khi bản nháp ĐÃ làm sạch khác thông tin đang có (EditBook.tsx metadataSaveable): thêm khoảng trắng hay Enter cuối
// danh sách không phải một thay đổi, và lưu xong (sách nạp lại) nút tắt.
function metadataSaveable(draft, book) { return JSON.stringify(cleanMetadata(draft)) !== JSON.stringify(cleanMetadata(book || {})) }

// ---- capabilities.ts ----
var LINK_BOOK = S.s_sach_nay_lay_tu_may_tinh_khac_muon_sua_thi_d2a5136b
function canEditLayer(caps) { return !!caps && (!!caps.workshop || !caps.link) }
function studioNeed(caps) {
    if (!caps || caps.link) return null
    if (caps.workshop && caps.toolchain) return null
    if (!caps.toolchain) return S.s_can_cai_studio_7de0b351
    return S.s_cuon_nay_chua_co_du_an_studio_b175061f
}
function syncsToComputer(caps) { return !!(caps && caps.sync) && !(caps && caps.workshop) }
function editBlockedNote(caps) { return caps && caps.link && !caps.workshop ? LINK_BOOK : null }
function holderName(remote) { return remote && typeof remote === "object" && remote.computer ? remote.computer : S.s_may_tinh_8eafc226 }

// Lời mô tả dưới tên hộp "Sửa sách"
function editDescription(book, computer) {
    if (computer) return S.s_doi_co_hieu_luc_ngay_tren_may_tinh_2c86999e + computer + S.s_audio_va_chu_cua_nguoi_lam_sach_giu_nguyen_23fc70c2
    if (syncsToComputer(book.capabilities))
        return S.s_doi_co_hieu_luc_ngay_tren_may_nay_va_duoc_6f67ffbd + holderName(book.remote) + S.s_khi_ket_noi_audio_va_chu_cua_nguoi_lam_sac_100e8418
    return S.s_doi_co_hieu_luc_ngay_va_chi_tren_may_nay_a_a2fe1444
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
var PROVIDER_NAMES = {itunes: "iTunes", open_library: S.s_open_library_11e9037f, google_books: S.s_google_books_8a341a41}
function failedSourcesNote(failed) {
    return S.s_chua_noi_duoc_21cf7b4e + failed.map(function(name) { return PROVIDER_NAMES[name] || String(name).replace("_", " ") }).join(", ") + S.s_thu_lai_hoac_chon_anh_tren_may_576777e9
}
function coverTitle(found) { return found.title + (found.author ? " - " + found.author : "") + " (" + found.provider + ")" }

// ---- readings.ts ----
function cleanSpoken(value) { return String(value || "").normalize("NFC").trim().replace(/\s+/gu, " ") }

// Tên chương đang hiện trên dòng chương (nhãn + tên phụ nếu có)
function chapterShownName(chapter) { return chapter ? (chapter.fullTitle || chapter.title || "") : "" }

// Toast lỗi của web (tiêu đề + mô tả) thành MỘT câu thông báo: hai dòng
function toastText(title, description) { return description ? title + "\n" + description : title }
