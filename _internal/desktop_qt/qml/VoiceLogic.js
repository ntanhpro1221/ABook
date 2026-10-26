.pragma library

// Phần thuần (không giao diện) của Cài đặt › Giọng đọc, chép từng chữ từ bản web: listen/voiceGroups.ts, readAloudVoice.ts (chọn giọng mặc định,
// lời báo chữ đi đâu), vieneuModule.ts (lời của thẻ giọng trên máy), voiceSpeed.ts (Hiệu năng), studio/musicLocal.ts (formatSize, hai câu chung).
// Chỗ web viết "khóa" thì đây viết "khoá" (chủ app 26-10: một cách viết duy nhất).

var SAMPLE_TEXT = "Xin chào, tôi sẽ đọc sách cho bạn nghe. Bạn thấy giọng này thế nào?"
var ONLINE_NOTICE = "Giọng Edge gửi chữ của sách tới máy chủ Microsoft để đọc."
var DEVICE_HINT = "Cài giọng tiếng Việt tại Cài đặt Windows › Thời gian và ngôn ngữ › Giọng nói."
var LOAD_ERROR = "Bạn hãy kiểm tra kết nối rồi tải lại giọng đọc."
var DEFAULT_VOICE_ERROR = "Chưa lưu được giọng mặc định. Bạn hãy chọn lại để thử lại."
var CANCELLED_NOTE = "Đã huỷ - lần tải sau làm tiếp từ chỗ dừng."
var RETRYING_NOTE = "Mạng chập chờn - đang thử lại…"
var ONLINE_VOICE = "edge:vi-VN-HoaiMyNeural"

// Tên nhà cung cấp giọng dùng khoá riêng
var KEYED = {azure: "Azure Speech", google: "Google Cloud", fpt: "FPT.AI", viettel: "Viettel AI"}

// Cách lấy khoá, theo những gì người dùng thấy trên trang của nhà cung cấp
var KEY_HELP = {
    azure: "Azure: tạo Speech (F0 miễn phí) › Keys and Endpoint. Chép Key 1 và Location/Region (ví dụ southeastasia).",
    google: "Google Cloud: bật Cloud Text-to-Speech API. Vào APIs & Services › Credentials › Create credentials › API key.",
    fpt: "Trên console.fpt.ai: đăng nhập, mở mục “Text to Speech” (Chuyển văn bản thành giọng nói), chép “API key” (khoá API).",
    viettel: "Trên viettelai.vn: đăng nhập, mở Tài khoản › Token, chép token."
}

// Các nhóm giọng theo nhà cung cấp, đúng thứ tự và tên ở Cài đặt › Giọng đọc
var GROUPS = [
    {provider: "edge", title: "Edge", detail: "trực tuyến, miễn phí"},
    {provider: "azure", title: KEYED.azure, detail: "dùng khoá của bạn"},
    {provider: "google", title: KEYED.google, detail: "dùng khoá của bạn"},
    {provider: "fpt", title: KEYED.fpt, detail: "dùng khoá của bạn"},
    {provider: "viettel", title: KEYED.viettel, detail: "dùng khoá của bạn"},
    {provider: "vieneu", title: "VieNeu", detail: "trên máy này, không cần mạng"},
    {provider: "supertonic", title: "Supertonic", detail: "trên máy này, không cần mạng"},
    {provider: "device", title: "Giọng của máy", detail: "không cần mạng"}
]

function groupLabel(group) { return group.detail ? group.title + " · " + group.detail : group.title }

function genderLabel(gender) { return gender === "female" ? "Nữ" : gender === "male" ? "Nam" : "" }

// "Hoài My (Edge)" -> "Hoài My"
function spokenVoiceName(name) {
    const spoken = String(name).replace(/\s*\([^)]*\)\s*$/, "").trim()
    return spoken || name
}

// Tách "Nhẹ (VieNeu Nano)" thành tên giọng + tên mô-đun
function splitVoiceName(name) {
    const found = /^(.*\S)\s+\(([^()]+)\)$/.exec(name)
    return found ? {shown: found[1], module: found[2]} : {shown: name, module: null}
}

// Chia các giọng của một nhóm theo mô-đun (giữ thứ tự); tiêu đề phụ chỉ khi từ hai mô-đun trở lên
function voiceSections(list) {
    const parts = list.map(voice => { const s = splitVoiceName(voice.name); return {voice: voice, shown: s.shown, module: s.module} })
    const counts = {}
    const order = []
    for (const part of parts) if (part.module !== null) {
        if (counts[part.module] === undefined) { counts[part.module] = 0; order.push(part.module) }
        counts[part.module]++
    }
    const shared = order.filter(m => counts[m] >= 2)
    const sections = []
    const loose = parts.filter(p => p.module === null || shared.indexOf(p.module) < 0)
    if (loose.length) sections.push({label: null, voices: loose.map(p => ({voice: p.voice, shown: p.voice.name}))})
    for (const module of shared)
        sections.push({label: shared.length > 1 ? module : null, voices: parts.filter(p => p.module === module).map(p => ({voice: p.voice, shown: p.shown}))})
    return sections
}

// Mã giọng theo thứ tự hiển thị của một nhóm (mũi tên đổi chọn)
function orderedIds(list) {
    const ids = []
    for (const section of voiceSections(list)) for (const item of section.voices) ids.push(item.voice.id)
    return ids
}

// Câu nói rõ chữ của sách đi đâu khi chọn giọng này
function onlineNotice(voice) {
    const keyed = KEYED[voice.provider]
    if (keyed) return "Giọng " + keyed + " gửi chữ của sách tới " + keyed + " bằng khoá của bạn - có thể bị tính tiền vào tài khoản của bạn."
    return voice.online ? ONLINE_NOTICE : ""
}

// Giọng VieNeu kể chuyện trung tính của từng bản, theo thứ tự ưu tiên (readAloudVoice.ts NARRATOR_VOICES)
var NARRATOR = {
    turbo: ["Phạm Tuyên", "Ngọc Linh", "Thanh Bình"],
    nano: ["Ái Hân", "Mỹ Duyên", "Đức Trí"]
}

function nfc(text) { return text.normalize ? text.normalize("NFC") : text }

function narratorVoice(voices, gender) {
    const local = voices.filter(v => v.provider === "vieneu")
    const tierOf = v => v.id.slice(v.id.indexOf(":") + 1, v.id.indexOf("/"))
    const nameOf = v => nfc(v.id.slice(v.id.indexOf("/") + 1))
    let ranks = 0
    for (const key in NARRATOR) ranks = Math.max(ranks, NARRATOR[key].length)
    for (let rank = 0; rank < ranks; rank++) {
        const found = local.find(v => { const list = NARRATOR[tierOf(v)]; return list && list[rank] !== undefined && nfc(list[rank]) === nameOf(v) })
        if (found) return found
    }
    return local.find(v => gender && v.gender === gender) || local[0]
}

// Giọng dùng thật: giọng đã chọn nếu còn trong danh sách; chưa chọn mà máy có giọng VieNeu thì giọng kể chuyện của VieNeu; không thì giọng mặc định / đầu tiên
function resolveVoice(voices, chosen) {
    const exact = voices.find(v => v.id === chosen)
    if (exact) return exact
    const fallback = voices.find(v => v.default) || voices[0]
    const local = chosen ? undefined : narratorVoice(voices, fallback ? fallback.gender : undefined)
    return local || fallback
}

// ---- Mô-đun giọng trên máy (VieNeu, Supertonic) ----

var VIENEU = {
    key: "vieneu", name: "Giọng VieNeu", title: "Giọng VieNeu", path: "/api/readaloud/vieneu",
    invite: "Giọng hay, đọc ngay trên máy, không cần mạng. Chữ của sách không rời máy.",
    tiers: ["turbo", "nano"]
}
var SUPERTONIC = {
    key: "supertonic", name: "Giọng Supertonic", title: "Giọng Supertonic", path: "/api/readaloud/supertonic",
    invite: "Mười giọng nam nữ, nhẹ máy, không cần mạng. Chữ của sách không rời máy.",
    tiers: ["supertonic"]
}
var TIER_NAME = {turbo: "Giọng VieNeu", nano: "Giọng VieNeu Nano", supertonic: "Giọng Supertonic"}
var LIVE_RTF = 0.8

function lowerFirst(text) { return text.charAt(0).toLowerCase() + text.slice(1) }

function tierVoicePrefix(tier) { return tier === "supertonic" ? "supertonic:" : "vieneu:" + tier + "/" }

function formatSize(bytes) {
    if (bytes >= 1e9) return (bytes / 1e9).toFixed(2).replace(".", ",") + " GB"
    const megabytes = bytes / 1e6
    if (megabytes < 1) return Math.max(1, Math.round(bytes / 1e3)) + " KB"
    return (megabytes < 10 ? megabytes.toFixed(1).replace(".", ",") : String(Math.round(megabytes))) + " MB"
}

function percent(status) {
    return status.total > 0 ? Math.min(100, Math.floor((status.done / status.total) * 100)) : 0
}

function seconds(value) { return value.toFixed(1).replace(".", ",") }

function working(status) { return Boolean(status) && (status.state === "downloading" || Boolean(status.benchmarking)) }

// Dòng tóm tắt của mục "Bộ giọng"
function moduleActivity(vieneu, supertonic) {
    const out = []
    const pairs = [["VieNeu", vieneu], ["Supertonic", supertonic]]
    for (const pair of pairs) {
        const status = pair[1]
        if (status && status.state === "downloading") out.push(pair[0] + " · " + percent(status) + "%")
        else if (status && status.benchmarking) out.push(pair[0] + " · đang đo")
    }
    return out.join(" · ") || "Tải, đo và quản lý"
}

function hasInstalled(status) { return Boolean(status) && (status.choices || []).some(c => c.installed) }

// Một dòng khuyên tải bộ nào; Supertonic chỉ đánh dấu sẵn khi máy không chạy được VieNeu
function moduleAdvice(vieneu, supertonic) {
    if (!vieneu || !vieneu.state) return {advice: "", preselectSupertonic: false}
    if (vieneu.state === "unsupported") return {advice: "", preselectSupertonic: true}
    if (hasInstalled(vieneu) || hasInstalled(supertonic)) return {advice: "", preselectSupertonic: false}
    const name = lowerFirst(TIER_NAME[vieneu.recommended === "nano" ? "nano" : "turbo"])
    return {advice: "Nên dùng " + name + "; chỉ cần tải một bộ giọng.", preselectSupertonic: false}
}

// Lựa chọn đánh dấu sẵn: cái đã tải + cái mô-đun đánh dấu sẵn cho máy này
function initialChoices(status, preselect) {
    return (status.choices || []).filter(c => c.installed || (preselect && c.default)).map(c => c.id)
}

// Byte phải tải cho các lựa chọn đang đánh dấu: hợp các phần còn thiếu, phần dùng chung tính một lần
function selectionBytes(status, chosen) {
    const parts = {}
    for (const part of status.parts || []) parts[part.id] = part
    const wanted = {}
    for (const choice of status.choices || []) if (chosen.indexOf(choice.id) >= 0) for (const id of choice.needs || []) wanted[id] = true
    let total = 0
    for (const id in wanted) { const part = parts[id]; if (part && part.state !== "current") total += part.bytes }
    return total
}

// Đánh dấu cái cần cái khác thì đánh dấu cả hai; bỏ cái được cần thì bỏ luôn cái cần nó
function toggleChoice(status, picked, id, on) {
    const choices = status.choices || []
    if (on) {
        const found = choices.find(c => c.id === id)
        const needed = found && found.requires ? found.requires : []
        const out = picked.slice()
        for (const item of [id].concat(needed)) if (out.indexOf(item) < 0) out.push(item)
        return out
    }
    const dependants = choices.filter(c => c.requires && c.requires.indexOf(id) >= 0).map(c => c.id)
    return picked.filter(item => item !== id && dependants.indexOf(item) < 0)
}

function meteredNotice(status, bytes) {
    if (!status.metered || bytes <= 0) return ""
    return "Điện thoại đang dùng dữ liệu di động - tải " + formatSize(bytes) + " có thể tốn tiền mạng. Nên chờ có Wi-Fi."
}

function fastUnsupportedNote(status) {
    return status.fastUnsupported ? "Bản tăng tốc: máy này không chạy được (" + status.fastUnsupported + ")." : ""
}

function acceleratedNote(state) {
    if (!state.on) return "Đang đọc bằng bản thường."
    if (state.problem) return "Máy này chưa chạy được bản tăng tốc, đang đọc bản thường."
    return state.active ? "Đang đọc bằng bản tăng tốc." : "Bản tăng tốc sẽ dùng từ lần đọc kế."
}

function benchmarkLabel(tier, result, live) {
    const limit = live === undefined ? LIVE_RTF : live
    const name = TIER_NAME[tier]
    if (result.rtf >= limit) {
        const hour = Math.max(1, Math.round(result.rtf * 60))
        return name + ": máy này không kịp đọc trực tiếp (" + seconds(result.rtf) + " giây cho mỗi giây nghe). Dùng “Làm trước”: mỗi giờ nghe cần ~" + hour + " phút."
    }
    const speed = result.rtf > 0 ? 1 / result.rtf : 0
    return name + ": đọc trực tiếp được - máy này đọc nhanh gấp " + seconds(speed) + " lần tốc độ nghe; đoạn đầu chương có tiếng sau khoảng " + seconds(result.firstAudioMs / 1000) + " giây."
}

// Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút
function suggestionText(suggestion) {
    const slow = TIER_NAME[suggestion.tier]
    const lead = slow + " đọc chậm trên máy này (" + seconds(suggestion.rtf) + " giây cho mỗi giây nghe). Giữ giọng này thì dùng “Làm trước”."
    if (suggestion.switchTo === "nano") {
        return suggestion.installed
            ? {message: lead + " Giọng VieNeu Nano nhẹ hơn, đã có sẵn.", action: "Dùng giọng VieNeu Nano"}
            : {message: lead + " Giọng VieNeu Nano nhẹ hơn, hợp máy này.", action: "Tải giọng VieNeu Nano"}
    }
    return {message: lead + " Giọng trực tuyến nhẹ máy (cần mạng).", action: "Dùng giọng trực tuyến"}
}

// Câu chính của thẻ theo trạng thái
function moduleLabel(status, copy) {
    const mid = lowerFirst(copy.name)
    if (status.state === "error") return status.error
    if (status.state === "downloading")
        return status.retrying ? RETRYING_NOTE + " (" + mid + ", " + percent(status) + "%)" : "Đang tải " + mid + " (" + formatSize(status.total) + ") " + percent(status) + "%"
    if (status.benchmarking) return Object.keys(status.benchmark || {}).length === 0 ? "Đang thử giọng vừa tải trên máy này (vài giây)…" : "Đang đo lại tốc độ trên máy này (vài giây)…"
    if (status.state === "unsupported") return status.reason ? "Máy này chưa dùng được " + mid + ": " + status.reason + "." : "Máy này chưa dùng được " + mid + "."
    if (status.restart) return copy.name + " đã cập nhật - mở lại ABook để dùng bản mới."
    const cancelled = status.cancelled ? CANCELLED_NOTE + " " : ""
    if (status.state === "outdated") return cancelled + copy.name + " có bản mới - " + formatSize(status.outdatedBytes) + ". Bản đang dùng vẫn đọc bình thường."
    if (status.state === "ready") return copy.name + " đã có trên máy: chọn trong nút Giọng đọc khi nghe sách chỉ có chữ."
    return cancelled + copy.invite
}

// Lời hỏi trước khi gỡ một giọng khỏi máy, nói từ phía người nghe
function removeAsk(use) {
    if (!use) return "Giọng sẽ không còn trên máy này cho tới khi bạn tải lại."
    if (!use.bookCount) return "Chưa cuốn nào dùng giọng này. Bạn tải lại được bất cứ lúc nào."
    const titles = use.books.slice(0, 3).map(book => "“" + book.title + "”").join(", ")
    const more = use.bookCount > 3 ? " và " + (use.bookCount - 3) + " cuốn khác" : ""
    const who = use.bookCount + " cuốn đang dùng giọng này (" + titles + more + "), " + use.peopleCount + " nhân vật."
    const rest = use.left
        ? use.left + " câu chưa thu sẽ im tới khi bạn tải lại giọng hay đổi giọng khác; câu đã thu vẫn nghe được."
        : "Các câu đã thu vẫn nghe được."
    return who + " " + rest
}

// ---- Hiệu năng (voiceSpeed.ts) ----

var SPEED_TITLE = "Tốc độ đọc"
var SPEED_OPTIONS = [
    {value: "auto", label: "Tự động"},
    {value: "quality", label: "Chất lượng cao nhất"},
    {value: "fast", label: "Nhanh hơn"}
]
var SPEED_DESCRIPTION = {
    auto: "Máy kịp thì đọc bản hay nhất.",
    quality: "Luôn đọc bản hay nhất; máy chậm có thể phải chờ.",
    fast: "Nhanh hơn, tiếng kém hơn chút - hợp máy yếu."
}
var SPEED_TIER = {quality: "Chất lượng cao nhất", fast: "Nhanh hơn"}

function speedLabel(choice) {
    const found = SPEED_OPTIONS.find(o => o.value === choice)
    return found ? found.label : ""
}

function speedDescription(choice) {
    return (SPEED_DESCRIPTION[choice] || "") + " Chỉ áp cho giọng Supertonic; sách xuất ra luôn dùng bản hay nhất."
}

function speedWhy(voice, choice) {
    if (choice !== "auto") return "bạn đã chọn"
    if (voice.rtf === null || voice.rtf === undefined) return "chưa đo được tốc độ máy này"
    return voice.tier === "fast" ? "máy này đọc chậm hơn tốc độ nghe" : "máy này đọc kịp tốc độ nghe"
}

function speedLine(voice, choice) {
    const lead = voice.name + " - Đang dùng: " + SPEED_TIER[voice.using] + " (" + speedWhy(voice, choice) + ")"
    if (voice.tier === "fast" && voice.using !== "fast")
        return voice.name + " - Đang dùng: " + SPEED_TIER.quality + ". Bản nhanh hơn cần tải thêm " + formatSize(voice.fastBytes) + "."
    return lead + "."
}

function needsFastDownload(voice) {
    return voice.tier === "fast" && voice.using !== "fast" && voice.fastBytes > 0
}
