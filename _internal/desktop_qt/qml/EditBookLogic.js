.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size

// Phần thuần của "Sửa sách" và "Tìm bìa" (EditBook.tsx, CoverSearch.tsx, shared/capabilities.ts, musicLevels.ts, studio/musicLocal.ts): chữ và quy tắc
// chép nguyên từ bản web để hai nền tảng nói cùng một câu.

// Chữ người gõ như máy chủ làm sạch: khoảng trắng gộp một dấu cách, bỏ đầu cuối.
function tidy(text) { return String(text || "").trim().replace(/\s+/g, " ") }

// Ô "Tác giả" lưu được không: chữ gõ khác tác giả đang hiện (trống cũng là một thay đổi nếu sách đang có tác giả).
function authorSaveable(typed, shown) { return tidy(typed) !== tidy(shown || "") }

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
