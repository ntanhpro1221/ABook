.pragma library
.import "ImportQueue.js" as Queue
.import "VoiceLogic.js" as Voice
.import "PeerStudio.js" as Peer

// Hàm thuần của "Nhân vật" ở trang sách (CastList / PersonRow của listen/BookScreen.tsx, MergeDialog / GenderDialog của studio/): tên đã làm sạch,
// chữ cái đầu và màu ô tròn, dòng giọng / chờ áp dụng / số câu, người của các chương sau, cuộc gọi chọn giọng. Chữ giữ đúng từng chữ của bản web.

// ---- Tên ------------------------------------------------------------------------------------------------------------------
// Tên hiển thị không lộ dữ liệu thô: gạch dưới thành dấu cách (cleanName)
function cleanName(name) { return String(name || "").replace(/_/g, " ").replace(/\s+/g, " ").trim() }

// Chữ cái đầu của hai từ đầu, bỏ số La Mã ("Lính gác II" -> "LG")
function initials(name) {
    return cleanName(name).split(/\s+/).filter(word => word !== "" && !/^[IVXLCDM]+$/.test(word)).slice(0, 2).map(word => word[0]).join("").toUpperCase()
}

// Tên giọng người nghe thấy: nhãn nếu có, không thì khoá
function voiceName(voice) { return voice ? (voice.label || voice.preset || "") : "" }

// "Chương 5" dính liền số, để dòng không bao giờ kết thúc ở "Chương" (labels.ts keepTogether)
function keepTogether(title) { return String(title || "").replace(/^(Chương|Tập|Phần|Hồi|Quyển)\s+(\S+)/i, "$1 $2") }

function formatNumber(value) { return Queue.formatNumber(value) }

// "3 phút", "1 giờ 5 phút" (shared/format.ts formatLength)
function formatLength(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return "0 phút"
    const minutes = Math.round(seconds / 60)
    if (minutes < 1) return "dưới 1 phút"
    const hours = Math.floor(minutes / 60), rest = minutes % 60
    if (!hours) return minutes + " phút"
    return rest ? hours + " giờ " + rest + " phút" : hours + " giờ"
}

// Nhãn âm sắc ("trầm hẳn") là SO VỚI GIỌNG GỐC mà máy chỉnh để hai người cùng giọng khác nhau (listen/voiceTone.ts)
const FROM_BASE = ["trầm hẳn", "hơi trầm", "sáng hẳn", "hơi sáng"]
function toneLabel(tone) {
    const text = String(tone || "").trim()
    return FROM_BASE.indexOf(text) >= 0 ? "chỉnh " + text + " so với giọng gốc" : text
}

// ---- Ô tròn chữ cái (.avatar của styles.css: oklch(L 0.03 hue) nền, oklch(L 0.085 hue) chữ) -----------------------------------
function hueOf(text) {
    let value = 0
    for (const char of String(text || "")) value = (value * 31 + char.charCodeAt(0)) % 360
    return value
}
function oklch(lightness, chroma, hue) {
    const a = chroma * Math.cos(hue * Math.PI / 180), b = chroma * Math.sin(hue * Math.PI / 180)
    const l = Math.pow(lightness + 0.3963377774 * a + 0.2158037573 * b, 3)
    const m = Math.pow(lightness - 0.1055613458 * a - 0.0638541728 * b, 3)
    const s = Math.pow(lightness - 0.0894841775 * a - 1.2914855480 * b, 3)
    const linear = [4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s,
                    -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s,
                    -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s]
    return "#" + linear.map(v => {
        const c = Math.max(0, Math.min(1, v))
        const g = c <= 0.0031308 ? 12.92 * c : 1.055 * Math.pow(c, 1 / 2.4) - 0.055
        return ("0" + Math.round(g * 255).toString(16)).slice(-2)
    }).join("")
}
// --avatar-bg-l / --avatar-fg-l của styles.css: sáng 0,93 / 0,43; tối 0,33 / 0,84
function avatarFill(hue, dark) { return oklch(dark ? 0.33 : 0.93, 0.03, hue) }
function avatarInk(hue, dark) { return oklch(dark ? 0.84 : 0.43, 0.085, hue) }

// ---- Dòng chữ của một người -------------------------------------------------------------------------------------------------
function voiceLine(person) {
    if (!person.voice) return "Chưa có giọng"
    return voiceName(person.voice) + (person.voice.tone ? " · " + toneLabel(person.voice.tone) : "")
}
// "Chờ áp dụng" (dự án) / "Đang chờ máy làm sách" (cuốn không có xưởng)
function waitPrefix(waiting) { return waiting ? "Đang chờ máy làm sách" : "Chờ áp dụng" }
function pendingVoiceLine(person, waiting) {
    const pending = person.pendingVoice
    if (!pending) return ""
    return waitPrefix(waiting) + ": " + [pending.preset && "giọng " + voiceName(pending), String(pending.gender || "").toLowerCase()].filter(Boolean).join(" · ")
}
function mergedLine(person, waiting) { return person.mergedInto ? waitPrefix(waiting) + ": gộp vào " + cleanName(person.mergedInto) : "" }
function countLine(person) {
    return formatNumber(person.lines) + " câu" + (person.seconds > 0 ? " · " + formatLength(person.seconds) : "")
        + (person.firstChapter ? " · từ " + keepTogether(person.firstChapter) : "")
}
function narratorLine(narrator) {
    return formatNumber(narrator.lines) + " câu dẫn truyện" + (narrator.seconds > 0 ? " · " + formatLength(narrator.seconds) : "")
        + (narrator.redo ? " · " + formatNumber(narrator.redo) + " câu chờ thu lại" : "")
}
function narratorPending(narrator) {
    return narrator.pendingVoice && narrator.pendingVoice.preset ? "Chờ áp dụng: giọng " + voiceName(narrator.pendingVoice) : ""
}

// ---- Nghe thử -----------------------------------------------------------------------------------------------------------------
function sampleId(bookId, person) { return "sample-" + bookId + "-" + person.sampleId }
function sampleUrl(bookId, person) { return "/media/books/" + bookId + "/samples/" + person.sampleId }
function voiceId(name) { return "voice-" + name }
function voiceUrl(name) { return "/media/voices/" + encodeURIComponent(name) }
// Studio của máy tính ghép: tệp nghe thử cũng lấy qua máy ấy (cùng cầu nối với mọi lời gọi khác)
function routed(url, peer) { return Peer.throughPeer(url, peer) }

// ---- Người của các chương sau ---------------------------------------------------------------------------------------------------
// Tên (ngắn và đầy đủ) của các chương từ đầu tới chương `until` (chưa nghe gì: tới chương đầu): {tên: true}
function reachedTitles(chapters, until) {
    const titles = {}
    const list = chapters || []
    const last = until === undefined || until === null ? (list.length ? list[0].id : undefined) : until
    for (const chapter of list) {
        titles[chapter.title] = true
        titles[chapter.fullTitle] = true
        if (chapter.id === last) break
    }
    return titles
}
// Người chỉ xuất hiện SAU chỗ đang nghe bị ẩn tới khi bấm "Hiện chương sau" (soát UX 29-09); reached null = hiện hết
function hidden(person, reached) { return Boolean(reached && person.firstChapter && !reached[person.firstChapter]) }
function ahead(people, reached) { return people.filter(person => hidden(person, reached)).length }

// ---- Gộp / giới -------------------------------------------------------------------------------------------------------------------
// Giọng người ấy SẼ đọc: giọng người nghe vừa chọn mà chưa áp, nếu có (voiceToUse)
function voiceToUse(member) { return member.pendingVoice && member.pendingVoice.preset ? voiceName(member.pendingVoice) : voiceName(member.voice) }

// Người có thể nhận phần gộp: không phải chính nó, có giọng, tên khớp ô tìm
function mergeTargets(people, person, query) {
    const words = String(query || "").trim().toLowerCase()
    return people.filter(other => (!person || other.name !== person.name) && other.voice)
        .filter(other => !words || cleanName(other.displayName).toLowerCase().indexOf(words) >= 0)
}
// Vai phụ trùng tên: tên (đã làm sạch, hạ chữ) xuất hiện hơn một lần (workText.sameNames)
function sameNames(people) {
    const seen = {}, twins = {}
    for (const person of people) {
        const key = cleanName(person.displayName).toLowerCase()
        if (seen[key]) twins[key] = true
        seen[key] = true
    }
    return twins
}
function mergeSummary(person, into) {
    return formatNumber(person.lines) + " câu của " + cleanName(person.displayName) + " thành của " + cleanName(into.displayName)
        + ", đọc bằng giọng " + voiceToUse(into) + (into.pendingVoice && into.pendingVoice.preset ? " (giọng vừa chọn, chờ áp dụng)" : "") + "."
}
// Giới người nghe đang thấy ở dòng nhân vật: giới chờ áp dụng nếu có, không thì giới trong sổ
function shownGender(person) {
    if (!person) return ""
    const label = (person.pendingVoice && person.pendingVoice.gender) || person.gender
    return label === "Nam" ? "male" : label === "Nữ" ? "female" : ""
}

// ---- Hộp "Giọng của …" (studio/VoicePicker.tsx, voiceEngines.ts, voiceTryText.ts) ---------------------------------------------------
// Lọc Nam / Nữ / Tất cả, giữ thứ tự máy chủ gửi
function byGender(voices, filter) { return filter === "all" ? voices.slice() : voices.filter(voice => voice.gender === filter) }

// Nhóm theo máy đọc, giữ thứ tự máy chủ gửi (VieNeu trước)
function groupByEngine(voices) {
    const groups = []
    for (const voice of voices) {
        let group = groups.filter(item => item.engine === voice.engine)[0]
        if (!group) { group = {engine: voice.engine, voices: []}; groups.push(group) }
        group.voices.push(voice)
    }
    return groups
}
// Máy đọc chính (VieNeu) là "Giọng chính", các máy khác "Giọng thêm" (đánh số khi có hai nhóm thêm trở lên)
function groupLabels(groups) {
    const extras = groups.filter(group => group.engine !== "vieneu").length
    let seen = 0
    return groups.map(group => group.engine === "vieneu" ? "Giọng chính" : extras > 1 ? "Giọng thêm " + (++seen) : "Giọng thêm")
}
function sharedText(voice, current) {
    const others = voice.otherUsers ? voice.otherUsers + " người khác dùng, không cùng chương" : ""
    const sharedWith = voice.sharedWith || []
    if (!sharedWith.length) return others || (current ? "Giọng đang đọc cho người này" : "Chưa ai dùng")
    const people = sharedWith.map(person => person.label + " (" + person.chapters + " chương)").join(", ")
    const after = voice.oneStep ? "hai người sẽ nghe giống hệt nhau" : "máy lấy bậc âm sắc khác"
    return "Cùng chương với " + people + " - " + after + (others ? " · " + others : "")
}
// Hộp của người kể: giọng nhân vật đang giữ không chọn được - nói của ai (tối đa ba tên)
function takenText(takenBy) {
    return "Đang là giọng của " + takenBy.slice(0, 3).join(", ") + (takenBy.length > 3 ? " và " + (takenBy.length - 3) + " người khác" : "") + " - người kể cần giọng riêng"
}
// Dòng phụ dưới tên giọng: miền + phong cách (hay chất giọng của máy khác) và ai đang dùng
function voiceMeta(voice, withGender) {
    const parts = voice.description ? [voice.description] : [voice.region ? "Miền " + voice.region : "", voice.style]
    const about = [withGender && !voice.description ? voice.genderLabel : ""].concat(parts).filter(Boolean).join(" · ")
    const alone = voice.current && !(voice.sharedWith || []).length && !voice.otherUsers
    const use = voice.takenNote || ((voice.takenBy || []).length ? takenText(voice.takenBy) : alone ? "" : sharedText(voice, voice.current))
    return [about, use].filter(Boolean).join(" · ")
}
// Chữ của nút cuối hàng
function voiceAction(voice) {
    return voice.current ? "Đang dùng" : voice.pending ? "Đã chọn" : voice.takenNote ? "Người kể dùng" : (voice.takenBy || []).length ? "Nhân vật dùng" : "Chọn"
}
function estimateText(seconds, measured) {
    const length = seconds < 60 ? "chưa tới 1 phút" : "khoảng " + formatLength(seconds)
    return measured === false ? length + " - ước chừng, vì cuốn chưa xong chương nào để đo" : length + " trên máy này"
}
// Một dòng trong hộp: đổi giọng tốn gì
function rerecordText(name, cost) {
    if (!cost.lines) return "Chưa câu nào của " + name + " được thu - đổi giọng không phải thu lại gì."
    return "Đổi giọng là thu lại " + formatNumber(cost.lines) + " câu đã thu của " + name + ", " + estimateText(cost.seconds, cost.measured) + "."
}
function genderWord(gender) { return gender === "female" ? "nữ" : "nam" }

// ---- "Nghe thử bằng câu của sách" (VoiceTry.tsx, previewText.ts, voiceTryText.ts) -----------------------------------------------
// Máy thu thử một câu của chính nhân vật bằng giọng đang cân nhắc - đúng giọng sẽ áp, không ghi gì vào sách. Bản đã nghe trong phiên (theo sách, người,
// giọng): bấm lại là phát lại, không hỏi máy chủ.
var heard = {}
function tryKey(bookId, request) { return [bookId, request.character, request.preset || "", request.gender || "", request.avoid || ""].join("\u0000") }
function tryId(preview) { return "voice-try-" + preview.url }
function tryLabel(voiceName, playing) { return playing ? "Dừng nghe thử" : "Nghe giọng " + voiceName + " đọc một câu của sách" }
function tryHint(name, hasLine) {
    return hasLine ? "Nút sách đọc câu của " + name + "; ▶ đọc mẫu chung." : name + " chưa có câu nào để đọc thử - nút ▶ là câu mẫu chung của giọng."
}
function tryAsking(voiceName) { return "Máy đang đọc thử giọng " + voiceName + " - lần đầu có thể mất vài chục giây" }
var NO_LINE = "Người này chưa có câu nào để đọc thử - đang phát câu mẫu chung của giọng"
// Lời từ chối của máy chủ: mã quen thì câu viết sẵn, không thì lời của máy chủ (đã là tiếng Việt)
var REFUSALS = {
    producing: "Máy đang làm sách; thử lại khi xong.",
    gpu: "Card đồ hoạ đang bận - thử lại sau ít phút",
    studio: "Cài Studio để nghe thử.",
    busy: "Đang nghe thử câu khác - bấm lại sau ít giây"
}
function refusalText(reason, fallback, named) {
    if (reason === "producing" && named) return fallback
    return (typeof reason === "string" && REFUSALS[reason]) || fallback
}
// Đầu một câu để nhắc lại: bỏ ngoặc thoại hai đầu, cắt ở ranh giới từ (shared/format.ts excerpt)
function excerpt(text, max) {
    max = max || 48
    const clean = String(text || "").replace(/\s+/g, " ").trim().replace(/^["“”'‘’«»『』「」—–\-\s]+|["“”'‘’«»『』「」\s]+$/g, "")
    if (clean.length <= max) return clean
    const cut = clean.slice(0, max)
    const space = cut.lastIndexOf(" ")
    return (space > max / 2 ? cut.slice(0, space) : cut).replace(/[\s,.;:!?…—–-]+$/, "") + "…"
}
function previewCaption(text, speaker) {
    return "Lúc thu thật sẽ nghe gần như vậy · câu “" + excerpt(text, 70) + "”" + (speaker ? " · giọng " + speaker : "")
}

// ---- Mô-đun giọng của máy đọc khác (voiceEngines.ts: EngineModuleStatus, moduleNote) --------------------------------------------------
// Dòng ghi chú dưới tên nhóm của một máy đọc chưa sẵn sàng trên máy này; "" khi đã dùng được
function moduleNote(status) {
    if (!status || status.state === "ready") return ""
    if (status.state === "downloading") return "Đang tải giọng (" + Voice.formatSize(status.total) + ") " + Voice.percent(status) + "%"
    if (status.state === "error") return status.error || "Chưa tải được giọng - thử lại."
    if (status.state === "unsupported") return "Máy này chưa dùng được những giọng này."
    const cancelled = status.cancelled ? Voice.CANCELLED_NOTE + " " : ""
    if (status.damaged) return cancelled + "Giọng này đã tải nhưng một phần bị mất hay hỏng - bấm Sửa giọng để tải lại đúng phần ấy."
    if (status.state === "outdated") return cancelled + "Có bản giọng mới (" + Voice.formatSize(status.bytes) + ") - tải để dùng tiếp."
    return cancelled + "Máy đọc khác: cần tải thêm " + Voice.formatSize(status.bytes) + ", một lần."
}
// Nút tải của nhóm: chỉ khi máy đọc chưa có / hỏng / cũ
function moduleAction(status) {
    if (!status || ["missing", "error", "outdated"].indexOf(status.state) < 0) return ""
    return status.state === "error" ? "Thử lại" : status.damaged ? "Sửa giọng" : "Tải giọng"
}
// Nhóm có đầu riêng (tên + nút tải) khi có hai nhóm trở lên hay không phải máy đọc chính (VieNeu)
function groupHasHeader(groups, group) { return groups.length > 1 || group.engine !== "vieneu" }
