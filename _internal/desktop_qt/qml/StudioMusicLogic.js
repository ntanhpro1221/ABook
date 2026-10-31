.pragma library
.import "SizeFormat.js" as Size
.import "MyMusicText.js" as Music

// Phần thuần của tab "Nhạc nền" trong Studio (MusicTab.tsx + studio/musicScenes.ts + shared/musicLevels.ts + musicCreditText của shared/format.ts):
// chữ chép từng chữ của bản web, để thử riêng không cần dựng màn.

/** "Chọn lại nhạc" (và đổi thể loại) dựng lại nhạc cả cuốn - sách 43 chương mất cỡ nửa phút: nói ra để các nút mờ không có vẻ như bị treo. */
var REBUILDING = "Đang chọn lại nhạc, cỡ nửa phút."
/** Sửa một đoạn (chọn bài, ghim, im lặng, bỏ bài) chỉ mất chốc lát: chỉ báo bận nhẹ, không hứa nửa phút. */
var SAVING = "Đang lưu lựa chọn"
/** Mỗi lần "Nghe thử" ~20 giây từ đầu bài. */
var PREVIEW_SECONDS = 20
// Bản web viết "↳ tiếp bài của đoạn trên"; phông của app không có "↳" nên mũi tên là icon corner-down-right đứng trước chữ
var CONTINUED_NOTE = "tiếp bài của đoạn trên"
/** Lời "đã chỉnh sửa" đi kèm ghi công nhạc CC BY; cùng câu với bản xuất MP3 / M4B (`music_export.MODIFIED_NOTE`). */
var MODIFIED_NOTE = "Đã chỉnh sửa: các bài nhạc được cắt vòng, trộn nhỏ dưới giọng đọc và chỉnh âm lượng cho vừa sách."

var LEVELS = [[-14, "To"], [-17, "Hơi to"], [-20, "Vừa (mặc định)"], [-24, "Nhỏ"], [-28, "Rất nhỏ"]]
var LEVEL_NOTES = {"-28": "dễ nghe lời nhất"}
function levelText(value, name) { const note = LEVEL_NOTES[String(value)]; return note ? name + " (" + note + ")" : name }
/** Ô "Mức nhạc dưới giọng đọc" của Studio: đúng các mức có sẵn. */
function levelOptions() { return LEVELS.map(function(level) { return {value: level[0], label: levelText(level[0], level[1])} }) }
/** Ô "Thể loại truyện": "Chưa chọn" rồi các thể loại theo thứ tự danh mục gửi. */
function genreOptions(taxonomy) {
    const out = [{value: "", label: "Chưa chọn"}]
    const genres = (taxonomy && taxonomy.genres) || {}
    for (const key in genres) out.push({value: key, label: genres[key].vi})
    return out
}
function genreName(taxonomy, genre) {
    const genres = (taxonomy && taxonomy.genres) || {}
    return genre && genres[genre] ? genres[genre].vi : ""
}

/** Mảnh này chỉ chơi tiếp bài của đoạn trên (chưa bị ghim / để im lặng riêng) - hiện gọn, không đủ bộ nút. */
function isContinuation(scene) { return Boolean(scene.continued && scene.link && !scene.pinned && !scene.silenced) }
/** Lời nút "Đổi bài": ở mảnh nối tiếp, ghim bài mới vào đây nên đổi từ chỗ này trở đi (các mảnh sau nối theo bài mới). */
function swapButton(scene) {
    return isContinuation(scene)
        ? {text: "Đổi từ đây", title: "Đổi bài từ chỗ này trở đi - các đoạn nối tiếp sau đó chơi theo bài mới; phần trên giữ nguyên"}
        : {text: "Đổi bài", title: ""}
}

// Danh mục cũ chưa gửi tên: dùng bảng có sẵn (cùng bộ với build_catalog.EMOTION_VI).
var EMOTION_VI = {
    peacefulness: "bình yên", tenderness: "dịu dàng", nostalgia: "hoài niệm", sadness: "buồn", joy: "vui tươi",
    playful: "tinh nghịch", power: "hào hùng", wonder: "kỳ vĩ", tension: "căng thẳng", fear: "rùng rợn",
    anger: "giận dữ", mystery: "bí ẩn", moved: "xúc động"
}
var MOOD_SHOWN = 0.5
var MOOD_MAX = 2
var TENSE_FROM = 0.5
var SAD_TO = -0.4
var BRIGHT_FROM = 0.4
/** Không khí của đoạn: các cảm xúc mạnh nhất; không cảm xúc nào đủ mạnh thì gọi theo vui/buồn và căng thẳng máy đã dùng để chọn bài. */
function moodOf(scene, names) {
    const emotions = scene.emotions || {}
    const strong = Object.keys(emotions)
        .filter(function(key) { return emotions[key] >= MOOD_SHOWN })
        .sort(function(a, b) { return emotions[b] - emotions[a] })
        .slice(0, MOOD_MAX)
        .map(function(key) { return (names && names[key]) || EMOTION_VI[key] || key })
    if (strong.length) return strong.join(" · ")
    if ((scene.tension || 0) >= TENSE_FROM) return "căng thẳng"
    if (scene.valence <= SAD_TO) return "buồn"
    if (scene.valence >= BRIGHT_FROM) return "tươi vui"
    return "êm"
}
/** Nhãn "AI" cạnh không khí: chỉ khi AI đã đọc đoạn; lời giải thích là `title` của bản web. */
function aiNote(scene) {
    if (scene.moodSource === "student") return "AI đã đoán đoạn này vui hơn hay buồn hơn, căng hơn hay dịu hơn so với mức của cả chương"
    if (scene.moodSource === "chapter") return "AI đã đọc cả đoạn này để chấm không khí, rồi cân theo mức của cả chương"
    if (scene.moodSource === "llm") return "AI đã đọc cả đoạn này để chấm không khí"
    return ""
}

/** Dòng tiến độ: MB khi biết cỡ, không thì đếm bài. */
function downloadText(download) {
    const tracks = "bài " + Math.min(download.done + 1, download.total) + "/" + download.total
    if (!download.totalBytes) return "Đang tải sẵn nhạc nền: " + tracks
    return "Đang tải sẵn nhạc nền: " + Size.formatSize(download.doneBytes || 0) + " / " + Size.formatSize(download.totalBytes) + " (" + tracks + ")"
}
function downloadShare(download) {
    if (download.totalBytes) return (download.doneBytes || 0) / download.totalBytes
    return download.total ? download.done / download.total : 0
}
/** Trình đọc màn hình chỉ đọc mốc 25 % (spokenProgress của shared/progressSpeech.ts): "pha · 50%"; chưa qua mốc đầu thì chỉ nói pha. */
function spokenProgress(phase, share) {
    const at = share === null || share === undefined || !isFinite(share) ? null : Math.floor(Math.max(0, Math.min(1, share)) * 4) * 25
    return at === null || at === 0 ? phase : phase.replace(/…$/, "") + " · " + at + "%"
}

/** Tên một bài: "tên · tác giả" nếu còn biết bài ấy, không thì tên file trong liên kết. */
function trackLabel(link, info) {
    if (info && info.title) return [info.title, info.creator].filter(Boolean).join(" · ")
    const parts = String(link).split(/[?#]/)[0].split("/").filter(Boolean)
    const name = parts.length ? parts[parts.length - 1] : String(link)
    try { return decodeURIComponent(name) } catch (error) { return name }
}
/** Đường nghe thử một bài: bài của "Nhạc của tôi" đọc thẳng file, bài danh mục qua bộ đệm nhạc của máy. */
function previewPath(link) {
    const digest = Music.localDigest(link)
    return digest ? "/api/music/local/" + digest + "/file" : "/api/music/track?link=" + encodeURIComponent(link)
}

/** Một dòng "Ghi công" (musicCreditText; nhạc của bạn thì nói rõ không có giấy phép). */
function creditLine(link, track) {
    if (track.source === "local") return [track.title, track.creator].filter(Boolean).join(" · ") + " - nhạc của bạn, không có thông tin giấy phép"
    const creator = String(track.creator || "").trim()
    const attribution = String(track.attribution || "").trim()
    if (attribution && creator) return attribution
    return [String(track.title || "").trim(), creator].filter(Boolean).join(" - ") || link
}
/** Giấy phép đòi ghi công (khác cc0) thì kèm lời "đã chỉnh sửa". */
function needsModifiedNote(license) {
    const code = String(license || "").trim().toLowerCase()
    return code !== "" && code !== "cc0"
}
function credits(plan) {
    const tracks = (plan && plan.tracks) || {}
    const lines = []
    let modified = false
    for (const link in tracks) {
        lines.push(creditLine(link, tracks[link]))
        if (needsModifiedNote(tracks[link].license)) modified = true
    }
    return {lines: lines, modified: modified}
}

/** Các đoạn theo chương, đúng thứ tự máy gửi. */
function chapterGroups(scenes) {
    const order = []
    const byChapter = {}
    for (const scene of scenes || []) {
        const key = String(scene.chapterId)
        if (!byChapter[key]) { byChapter[key] = []; order.push(scene.chapterId) }
        byChapter[key].push(scene)
    }
    return order.map(function(id) { return {chapterId: id, scenes: byChapter[String(id)]} })
}
/** Các đoạn nối liền: đoạn này hết ở đúng chỗ đoạn sau bắt đầu (cùng cách làm tròn). */
function sceneRange(scenes, index) {
    const next = scenes[index + 1]
    return Music.formatClock(scenes[index].start) + "–" + Music.formatClock(next ? next.start : scenes[index].end)
}
function chapterTitle(chapters, id) {
    for (const chapter of chapters || []) if (chapter.id === id) return chapter.displayTitle || chapter.title
    return "Chương " + id
}
/** Số đoạn đang dùng một bài (đếm trước khi bỏ bài ấy). */
function usedBy(plan, link) { return ((plan && plan.scenes) || []).filter(function(scene) { return scene.link === link }).length }

/** Bảng "…" của một đoạn: im lặng / có nhạc, bỏ ghim (khi đã ghim), không dùng bài này cho cả cuốn. */
function sceneMenu(scene) {
    const items = [{key: "silence", icon: "volume-x", text: scene.silenced ? "Bật nhạc đoạn này" : "Tắt nhạc đoạn này"}]
    if (scene.pinned) items.push({key: "unpin", icon: "pin-off", text: "Bỏ ghim"})
    if (scene.link) { items.push({sep: true}); items.push({key: "ban", icon: "ban", text: "Loại khỏi cuốn", danger: true}) }
    return items
}

/** Dòng trạng thái của "Nhạc theo ngữ cảnh" (MoodsPanel). */
function moodsState(model, remote) {
    if (!model) return "none"
    if (model.installed) return "installed"
    if (model.downloading) return "downloading"
    if (model.downloadable && !remote) return "offer"
    return "elsewhere"
}
function moodsPercent(model) {
    return model && model.progress && model.progress.total > 0 ? Math.round(model.progress.done * 100 / model.progress.total) : null
}
