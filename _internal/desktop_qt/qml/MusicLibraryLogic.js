.pragma library
// Kho nhạc (màn Nhạc) của app máy tính: lọc / tìm chạy ở máy chủ (abook/webui/music_library.py, GET /api/music/library) như bản web
// (ui/src/music/library.ts) - file này dựng chuỗi truy vấn từ bộ lọc và các phép tính nhỏ của dòng / sheet chi tiết. Bảng ca chung:
// tests/fixtures/music_library/cases.json (tests/test_musiclibrary.cpp kiểm mọi bộ lọc của bảng đi qua chuỗi truy vấn nguyên vẹn).

var TEMPOS = ["slow", "mid", "fast"]
var LENGTHS = ["short", "mid", "long"]
var KEYS = ["q", "playlist", "style", "emotion", "tempo", "length"]
var PREVIEW_SECONDS = 30

function noFilters() {
    return { q: "", playlist: "", style: "", emotion: "", tempo: "", length: "", downloaded: false }
}

// Chuỗi truy vấn của GET /api/music/library (rỗng khi không lọc gì); `saved`: phần "Đã lưu".
function libraryQuery(filters, saved) {
    var parts = []
    for (var i = 0; i < KEYS.length; i++) {
        var raw = filters[KEYS[i]]
        var value = typeof raw === "string" ? raw.trim() : ""
        if (value !== "") parts.push(KEYS[i] + "=" + encodeURIComponent(value))
    }
    if (filters.downloaded) parts.push("downloaded=1")
    if (saved) parts.push("saved=1")
    return parts.length ? "?" + parts.join("&") : ""
}

// Đọc lại chuỗi truy vấn (test, và mở màn với ?q= từ "Xem trong kho").
function parseQuery(query) {
    var out = {}
    var text = String(query || "").replace(/^\?/, "")
    if (text === "") return out
    var pairs = text.split("&")
    for (var i = 0; i < pairs.length; i++) {
        var at = pairs[i].indexOf("=")
        var key = at < 0 ? pairs[i] : pairs[i].slice(0, at)
        var value = at < 0 ? "" : decodeURIComponent(pairs[i].slice(at + 1).replace(/\+/g, " "))
        if (key === "downloaded") { if (value === "1") out.downloaded = true }
        else if (KEYS.indexOf(key) >= 0) out[key] = value
    }
    return out
}

// Có chip nào đang bật (chữ tìm không tính) - hiện "Bỏ lọc".
function filtering(filters) {
    return !!(filters.playlist || filters.style || filters.emotion || filters.tempo || filters.length || filters.downloaded)
}

// Trạng thái tải của một dòng: {kind: "loading", percent (tới 99, null khi chưa biết cỡ)} / "failed" / "done" / "none".
function loadOf(track, downloads) {
    var active = downloads && downloads.active ? downloads.active[track.link] : null
    if (active) return { kind: "loading", percent: active.total ? Math.min(99, Math.floor(active.done * 100 / active.total)) : null }
    if (downloads && downloads.failed && downloads.failed[track.link] !== undefined) return { kind: "failed" }
    return { kind: track.downloaded ? "done" : "none" }
}

// Năng lượng (arousal -1..1) thành 0-100 %; không có thì null.
function energyPercent(arousal) {
    if (typeof arousal !== "number" || isNaN(arousal)) return null
    return Math.round(Math.max(0, Math.min(1, (arousal + 1) / 2)) * 100)
}

function percent(score) {
    return Math.round(Math.max(0, Math.min(1, Number(score) || 0)) * 100)
}

// Nhãn tiếng Việt của một mã (phong cách / cảm xúc) trong danh sách {id, label} của /api/music/library/meta.
function labelOf(list, id) {
    var items = list || []
    for (var i = 0; i < items.length; i++) if (items[i].id === id) return items[i].label
    return id || ""
}

// "3:07" của thời lượng giây.
function clock(seconds) {
    var total = Math.max(0, Math.round(Number(seconds) || 0))
    var minutes = Math.floor(total / 60)
    var rest = total % 60
    return minutes + ":" + (rest < 10 ? "0" : "") + rest
}

// Đường nghe thử của một bài (cùng đường "Nghe thử" của Studio › Nhạc nền: bài tải về máy chủ rồi phát).
function previewPath(link) {
    return "/api/music/track?link=" + encodeURIComponent(link)
}
