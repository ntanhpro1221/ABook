.import "UiStrings.js" as S
.pragma library

// Tab "Kịch bản" (studio/ScriptTab.tsx + scriptFind.ts của bản web): đọc cả chương như kịch bản - câu nào của ai - và đổi người nói, cách đọc
// của bất kỳ câu nói nào. Ở đây chỉ phần không dính giao diện: bộ lọc câu, ô tìm chữ, chữ trên nhãn; chữ chép từng chữ của bản web.

var NARRATOR = "NARRATOR"
var UNNAMED = "UNNAMED"
var FIXED = [
    {value: NARRATOR, label: S.s_nguoi_ke_fd36cd15, lines: 0},
    {value: UNNAMED, label: S.s_vai_phu_khong_ten_6395f0d2, lines: 0}
]
// Gán nhanh bằng phím số: người nói nhiều nhất của chương đứng trước.
var HOTKEYS = 9
// Nhịp hỏi nhẹ xem cửa sổ khác có sửa gì không (ms).
var STAMP_MS = 6000
var FILTERS = ["all", "speech", "doubt"]
// Bộ cảm xúc của khâu phân tích (analysis.ALLOWED_EMOTIONS) và bốn mức cường độ.
var EMOTIONS = [
    ["neutral", S.s_binh_thuong_23c1bd43],
    ["happy", S.s_vui_2e2beffc],
    ["sad", S.s_buon_a1dc5853],
    ["angry", S.s_gian_19da03ba],
    ["afraid", S.s_so_485ed077],
    ["surprised", S.s_ngac_nhien_8b160295],
    ["tender", S.s_diu_dang_0d05b980],
    ["sarcastic", S.s_mia_mai_729f7055],
    ["excited", S.s_hao_hung_b8003bdb],
    ["tired", S.s_met_moi_304a36cf],
    ["whispering", S.s_thi_tham_ed2d29dd]
]
var LEVELS = [S.s_nhe_52e76ce9, S.s_vua_8af1c03b, S.s_manh_52416a97, S.s_rat_manh_bef32ca9]
var KINDS = [
    {value: "narration", label: S.s_loi_ke_eba0761e},
    {value: "dialogue", label: S.s_loi_thoai_4ed83728},
    {value: "thought", label: S.s_noi_tam_885fce10}
]
var GENDERS = [{value: "male", label: S.s_nam_22dd59c8}, {value: "female", label: S.s_nu_e15bc11c}, {value: "unknown", label: S.s_khong_ro_8af7da78}]

function emotionLabel(emotion) {
    for (const pair of EMOTIONS) if (pair[0] === emotion) return pair[1]
    return emotion
}
function kindLabel(kind) {
    for (const item of KINDS) if (item.value === kind) return item.label
    return kind
}
function deliveryText(emotion, intensity) {
    const label = emotionLabel(emotion)
    return intensity ? label + "\u00a0·\u00a0" + (LEVELS[intensity] !== undefined ? LEVELS[intensity].toLowerCase() : intensity) : label
}
// Cách đọc một câu nói bằng lời ("loại câu: nội tâm, cảm xúc: buồn"); "" khi không đặt gì.
function deliveryWords(delivery) {
    const spoken = delivery.spoken
    return [
        delivery.kind ? S.s_loai_cau_7d36723e + kindLabel(delivery.kind).toLowerCase() : "",
        delivery.emotion ? S.s_cam_xuc_fd4a891d + deliveryText(delivery.emotion, delivery.intensity).toLowerCase() : "",
        spoken !== undefined && spoken !== null ? (spoken ? S.s_doc_la_61eaf179 + spoken + "”" : S.s_tra_ve_chu_cua_sach_0451f8ec) : ""
    ].filter(Boolean).join(", ")
}
// `seen` của lần sửa cách đọc một câu (elsewhere.ts seenDelivery): cách đọc màn này đang thấy, null = chưa ai sửa câu này.
function seenDelivery(wish) {
    if (!wish) return null
    const out = {kind: wish.kind, emotion: wish.emotion, intensity: wish.intensity}
    if (wish.spoken !== undefined && wish.spoken !== null) out.spoken = wish.spoken
    return out
}
// "Lấy của máy kia" cho cách đọc một câu (theirDelivery): ghi lại đúng những gì máy kia đã đặt; null = máy kia không đặt gì.
function theirDelivery(theirs) {
    if (!theirs) return null
    const change = {}
    if (theirs.kind) change.kind = theirs.kind
    if (theirs.emotion) change.emotion = theirs.emotion
    if (theirs.intensity !== undefined && theirs.intensity !== null) change.intensity = theirs.intensity
    if (theirs.spoken !== undefined && theirs.spoken !== null) change.spoken = theirs.spoken
    return Object.keys(change).length ? change : null
}

function isSpeech(line) { return line.kind === "dialogue" || line.kind === "thought" }
// Người nói của câu như màn đang thấy: đang chờ đổi người thì tính theo người mới.
function speakerNow(line) { return line.wish && line.wish.state === "pending" ? line.wish.value : line.current }

// Câu hiện ra theo bộ lọc; "Máy nghi" giữ câu nói liền trước mỗi chỗ nghi làm ngữ cảnh (mờ). Chip người nói (`who`) LỌC: chỉ câu nói của người
// ấy (đang chờ đổi người thì tính theo người mới), kể cả khi lọc "Máy nghi".
function visibleLines(lines, filter, who) {
    const out = []
    if (who) {
        for (const line of lines) {
            if (!isSpeech(line) || speakerNow(line) !== who) continue
            if (filter !== "doubt" || line.hint) out.push({line: line, context: false})
        }
        return out
    }
    if (filter !== "doubt") {
        for (const line of lines) if (filter === "all" || isSpeech(line)) out.push({line: line, context: false})
        return out
    }
    let previous = null
    for (const line of lines) {
        if (!isSpeech(line)) continue
        if (line.hint) {
            if (previous && !out.some(function(entry) { return entry.line.stableId === previous.stableId })) out.push({line: previous, context: true})
            out.push({line: line, context: false})
        }
        previous = line
    }
    return out
}
// Khoảng trống trên một hàng: sang đoạn mới (cả chương) hay sang chỗ nghi khác (Máy nghi)
function gapBefore(shown, index, filter) {
    if (index <= 0) return false
    const entry = shown[index], before = shown[index - 1]
    if (filter === "doubt") return !entry.context && !before.context && before.line.seq !== entry.line.seq - 1
    return entry.line.paragraph !== before.line.paragraph
}

// Chỉ ghi điều KHÁC giữa các chương: chỉ chương không có câu nói nào mới ghi "chỉ lời kể", rồi tới chỗ nghi và việc đã quyết.
function chapterExtras(chapter) {
    return [
        chapter.speech ? "" : S.s_chi_loi_ke_6ec7b2cb,
        chapter.hints ? chapter.hints + S.s_cho_nghi_b59d77e4 : "",
        chapter.decided ? chapter.decided + S.s_da_quyet_3f663a9a : ""
    ].filter(Boolean).join("\u00a0·\u00a0")
}
function chapterLabel(chapter) { return chapter.title || S.s_chuong_aad5968e + chapter.index }
// Mở đầu ở chương đầu tiên có chỗ máy nghi - nơi người nghe sửa được nhiều nhất.
function startChapter(chapters, asked) {
    if (asked && chapters.some(function(chapter) { return chapter.chapterId === asked })) return asked
    const fallback = chapters.find(function(chapter) { return chapter.hints > 0 }) || chapters.find(function(chapter) { return chapter.speech > 0 }) || chapters[0]
    return fallback ? fallback.chapterId : 0
}

function nameOf(script, value) {
    const everyone = (script ? script.cast.concat(script.others) : []).concat(FIXED)
    const person = everyone.find(function(item) { return item.value === value })
    return person ? person.label : value
}
// Số câu nói của một người trong chương (tính theo người mới khi đang chờ đổi)
function said(lines, value) {
    return lines.filter(function(line) { return isSpeech(line) && speakerNow(line) === value }).length
}
// Chú giải người nói: người của chương rồi người vừa gán qua ô tìm (số kế tiếp), mỗi người kèm số câu
function people(script, added) {
    if (!script) return []
    const out = script.cast.slice()
    for (const person of added) {
        if (script.cast.some(function(item) { return item.value === person.value })) continue
        out.push({value: person.value, label: person.label, lines: said(script.lines, person.value), newGender: person.newGender})
    }
    return out
}
// Hàng chip: người theo số (1-9) rồi "Chưa rõ" (nhóm vô danh, không có số phím) nếu chương có câu ấy
function legend(list, unnamed) {
    const out = list.map(function(person, index) { return {person: person, badge: index < HOTKEYS ? String(index + 1) : ""} })
    if (unnamed > 0) out.push({person: {value: UNNAMED, label: S.s_chua_ro_be464a5a, lines: unnamed}, badge: "?"})
    return out
}
function whoLabel(list, who) {
    const person = list.find(function(item) { return item.value === who })
    return person ? person.label : who === UNNAMED ? S.s_chua_ro_be464a5a : ""
}
function emptyTitle(who, label, filter) {
    return who ? S.s_khong_co_cau_nao_cua_40cffaf6 + label + S.s_o_muc_nay_1eed1ee9 : filter === "doubt" ? S.s_may_khong_nghi_cau_nao_trong_chuong_nay_89a0a346 : S.s_chuong_nay_chi_co_loi_ke_39589983
}
function emptyText(who, filter) {
    return who ? S.s_bam_lai_ten_o_tren_de_xem_moi_nguoi_noi_1edb333f : filter === "doubt" ? S.s_chon_ca_chuong_de_doc_lai_toan_bo_940e0db5 : S.s_khong_co_cau_noi_nao_de_gan_nguoi_48cf1ced
}

// Cách đọc mặc định ("Bình thường · vừa", không có yêu cầu đang chờ): không phải thông tin, chỉ là lối vào sửa - hiện khi rê / chọn câu.
function plainDelivery(line) {
    return !(line.lineWish && line.lineWish.state === "pending") && line.emotion === "neutral" && (!line.intensity || line.intensity === 1)
}
function deliveryChip(line) {
    const waiting = line.lineWish && line.lineWish.state === "pending" ? line.lineWish : null
    return waiting ? deliveryText(waiting.emotion || line.emotion, waiting.intensity !== undefined && waiting.intensity !== null ? waiting.intensity : line.intensity)
                   : deliveryText(line.emotion, line.intensity)
}
function lineWishText(wish, pendingNote) {
    const what = wish.kind ? S.s_da_doi_loai_cau_2ec1aef5 + kindLabel(wish.kind).toLowerCase() : S.s_da_ghi_cach_doc_cau_ce5474e2
    const spoken = wish.spoken !== undefined ? (wish.spoken ? S.s_doc_la_16104c6f + wish.spoken + "\"" : S.s_tra_ve_chu_cua_sach_b10a6f5a) : ""
    return what + spoken + " - " + pendingNote + "."
}

// Bảng sửa cách đọc: điều bảng sẽ gửi (Delivery) từ những gì đang chọn; {} = không đổi gì.
function deliveryChange(line, kind, emotion, level, picked, words) {
    const change = {}
    const needsSpeaker = line.kind === "narration" && kind !== "narration"
    const speaker = picked ? picked.value : ""
    if (kind !== line.kind) change.kind = kind
    if (line.emotion !== null && emotion !== line.emotion) change.emotion = emotion
    if (line.intensity !== null && level !== line.intensity) change.intensity = level
    if (needsSpeaker && speaker) {
        change.speaker = speaker
        if (picked.newGender) change.newGender = picked.newGender
    }
    const reading = line.spoken !== null && line.spoken !== undefined ? line.spoken : line.text
    const cleaned = String(words).replace(/\s+/g, " ").trim()
    if (cleaned !== String(reading).replace(/\s+/g, " ").trim()) {
        if (!cleaned) {
            if (line.spoken) change.spoken = ""
        } else change.spoken = cleaned === line.text.trim() ? "" : cleaned
    }
    return change
}
function deliveryReady(line, kind, change) {
    const needsSpeaker = line.kind === "narration" && kind !== "narration"
    return Object.keys(change).length > 0 && (!needsSpeaker || Boolean(change.speaker))
}

// ---- ô tìm chữ (scriptFind.ts): gõ "tuan" thấy "Tuấn", trả VỊ TRÍ trong chữ gốc để tô đúng chỗ ----
var MARKS = /[̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯]/
var MARKS_ALL = /[̀-ͯ᪰-᫿᷀-᷿⃐-⃿︠-︯]/g
function foldChar(character) { return character.normalize("NFD").replace(MARKS_ALL, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase() }
// Bỏ dấu để gõ "tuan" tìm được "Tuấn" (ô tìm người).
function fold(text) { return String(text).normalize("NFD").replace(MARKS_ALL, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase() }
function folded(text) {
    let out = ""
    const origin = []
    let index = 0
    for (const character of text) {
        const piece = foldChar(character)
        for (const unused of piece) origin.push(index)
        out += piece
        index += character.length
    }
    return {text: out, origin: origin}
}
// Mọi chỗ `query` xuất hiện trong `text` (không phân biệt hoa thường và dấu), dạng [đầu, cuối) theo chữ gốc. Rỗng nếu `query` rỗng.
function findRanges(text, query) {
    const needle = folded(String(query).trim()).text
    if (!needle) return []
    const hay = folded(text)
    const ranges = []
    for (let at = hay.text.indexOf(needle); at >= 0; at = hay.text.indexOf(needle, at + needle.length)) {
        const start = hay.origin[at]
        let end = hay.origin[at + needle.length - 1] + 1
        // Dấu rời (chữ NFD) đi sau ký tự cuối thuộc về nó.
        while (end < text.length && MARKS.test(text[end])) end += 1
        ranges.push([start, end])
    }
    return ranges
}
// Cắt `text` thành các đoạn theo `ranges` (đã sắp, không chồng): [chữ, có tô không].
function splitByRanges(text, ranges) {
    const parts = []
    let at = 0
    for (const range of ranges) {
        if (range[0] > at) parts.push([text.slice(at, range[0]), false])
        parts.push([text.slice(range[0], range[1]), true])
        at = range[1]
    }
    if (at < text.length) parts.push([text.slice(at), false])
    return parts
}
// Chuyển vòng: Enter qua hết câu khớp cuối thì về câu đầu (và ngược lại).
function wrapIndex(at, count) { return count ? ((at % count) + count) % count : 0 }
function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;") }
// Chữ của câu với chỗ khớp tô nền (StyledText)
function markedHtml(text, ranges, mark) {
    return splitByRanges(text, ranges).map(function(part) {
        return part[1] ? "<span style=\"background-color:" + mark + "\">" + esc(part[0]) + "</span>" : esc(part[0])
    }).join("")
}
// Ô đếm: "k/n" hay "Không có"; "" khi ô trống
function findCount(text, at, found) {
    if (!String(text).trim()) return ""
    return found ? (wrapIndex(at, found) + 1) + "/" + found : S.s_khong_co_af48b64f
}

// Ô chọn người (SpeakerMenu): tìm theo tên bỏ dấu, tối đa 8 người
function findPeople(script, query) {
    const q = fold(String(query).trim())
    if (!q) return []
    return script.cast.concat(script.others).filter(function(person) { return fold(person.label).indexOf(q) >= 0 }).slice(0, 8)
}
function suggestedOf(script, line) {
    if (!line.hint || !line.hint.suggest) return null
    return script.cast.concat(script.others).find(function(person) { return person.value === line.hint.suggest }) || null
}

// ---- lời báo (chép từng chữ) ----
function assignedText(recorded, label, line, keep) {
    if (keep) return recorded > 1 ? S.s_da_xac_nhan_c0b382d5 + recorded + S.s_cau_cua_35c4143d + label : S.s_da_xac_nhan_cau_nay_cua_8f9da842 + line.label
    return recorded > 1 ? S.s_da_ghi_85094402 + recorded + S.s_cau_cua_35c4143d + label : S.s_da_ghi_cau_nay_cua_e43b7ee7 + label
}
function assignBack(lines) {
    const line = lines[0]
    return lines.length > 1 ? lines.length + S.s_cau_tro_lai_nhu_truoc_fab5b735
        : line.wish && line.wish.state === "pending" ? S.s_tro_lai_quyet_dinh_truoc_cau_nay_cua_5fa780cc + line.wish.label + "." : S.s_cau_nay_lai_la_cua_ed2f5b8d + line.label + "."
}
function retakeNone(group) {
    return group.some(function(item) { return item.hasAudio }) ? S.s_cau_nay_da_xin_thu_lai_may_thu_khi_ap_dung_f84d9f60
        : S.s_chua_thu_cau_nay_nen_chua_co_gi_de_thu_lai_d2bc2550
}
function footerNote(script, open, doubtful) {
    if (!script.castReady) return ""
    if (open > 0) return S.s_coi_nguoi_noi_cua_cac_cau_chua_ai_quyet_la_08ff324b + (doubtful ? S.s_tru_7a3a6ada + doubtful + S.s_cau_may_con_nghi_157474e3 : "") + S.s_may_thoi_hoi_ctrl_z_de_hoan_tac_a01ae5fa
    return doubtful ? S.s_con_71d0e2b2 + doubtful + S.s_cau_may_nghi_chua_ai_quyet_xem_cac_cau_co_a900151f : S.s_moi_cau_noi_trong_chuong_da_co_nguoi_quyet_fea38465
}
// Những câu "Duyệt N câu" xác nhận, chia theo người nói hiện tại (mỗi nhóm một yêu cầu, như web)
function confirmGroups(lines) {
    const groups = []
    for (const line of lines) {
        let group = groups.find(function(entry) { return entry.speaker === line.current })
        if (!group) { group = {speaker: line.current, lines: []}; groups.push(group) }
        group.lines.push(line)
    }
    return groups
}
function ref(line) { return {stableId: line.stableId, textSha256: line.textSha256} }

// Tên riêng có trong câu (useNamesInLine): khớp cả từ, không phân biệt hoa thường; mỗi tên một lần, theo thứ tự danh sách cách đọc
function isWordChar(character) { return character !== undefined && (character.toLowerCase() !== character.toUpperCase() || /[0-9_\u0300-\u036f]/.test(character) || character.charCodeAt(0) > 0x2e7f) }
function namesInLine(items, text) {
    const hay = String(text).normalize("NFC").toLowerCase()
    return (items || []).filter(function(item) {
        const needle = String(item.surface).normalize("NFC").toLowerCase()
        if (!needle) return false
        for (let at = hay.indexOf(needle); at >= 0; at = hay.indexOf(needle, at + 1)) {
            if (!isWordChar(hay[at - 1]) && !isWordChar(hay[at + needle.length])) return true
        }
        return false
    })
}
