.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size
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
function keepTogether(title) { return String(title || "").replace(/^(Chương|Tập|Phần|Hồi|Quyển)\s+(\S+)/i, "$1\u00a0$2") }

function formatNumber(value) { return Queue.formatNumber(value) }

// "3 phút", "1 giờ 5 phút" (shared/format.ts formatLength)
function formatLength(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return S.s_0_phut_66a3b36a
    const minutes = Math.round(seconds / 60)
    if (minutes < 1) return S.s_duoi_1_phut_a1dd4f60
    const hours = Math.floor(minutes / 60), rest = minutes % 60
    if (!hours) return minutes + S.s_phut_cf728a6a
    return rest ? hours + S.s_gio_fbaccc8e + rest + S.s_phut_cf728a6a : hours + S.s_gio_9e4dcadb
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
    if (!person.voice) return S.s_chua_co_giong_7ce5f4b4
    return voiceName(person.voice)
}
// "Chờ áp dụng" (dự án) / "Đang chờ máy làm sách" (cuốn không có xưởng)
function waitPrefix(waiting) { return waiting ? S.s_dang_cho_may_lam_sach_bad9fc96 : S.s_cho_ap_dung_77a52853 }
function pendingVoiceLine(person, waiting) {
    const pending = person.pendingVoice
    if (!pending) return ""
    return waitPrefix(waiting) + ": " + [pending.preset && S.s_giong_c3af83b2 + voiceName(pending), String(pending.gender || "").toLowerCase()].filter(Boolean).join("\u00a0·\u00a0")
}
function mergedLine(person, waiting) { return person.mergedInto ? waitPrefix(waiting) + S.s_gop_vao_6f4014d0 + cleanName(person.mergedInto) : "" }
function countLine(person) {
    return formatNumber(person.lines) + S.s_cau_b07e1008 + (person.seconds > 0 ? "\u00a0·\u00a0" + formatLength(person.seconds) : "")
        + (person.firstChapter ? S.s_u00a0_u00a0tu_ce4ae8bc + keepTogether(person.firstChapter) : "")
}
function narratorLine(narrator) {
    return formatNumber(narrator.lines) + S.s_cau_dan_truyen_f0d4156b + (narrator.seconds > 0 ? "\u00a0·\u00a0" + formatLength(narrator.seconds) : "")
        + (narrator.redo ? "\u00a0·\u00a0" + formatNumber(narrator.redo) + S.s_cau_cho_thu_lai_98956e55 : "")
}
function narratorPending(narrator) {
    return narrator.pendingVoice && narrator.pendingVoice.preset ? S.s_cho_ap_dung_giong_82c96902 + voiceName(narrator.pendingVoice) : ""
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
    return formatNumber(person.lines) + S.s_cau_cua_35c4143d + cleanName(person.displayName) + S.s_thanh_cua_0e935c9b + cleanName(into.displayName)
        + S.s_doc_bang_giong_0e64b444 + voiceToUse(into) + (into.pendingVoice && into.pendingVoice.preset ? S.s_giong_vua_chon_cho_ap_dung_23afd9d2 : "") + "."
}
// Giới người nghe đang thấy ở dòng nhân vật: giới chờ áp dụng nếu có, không thì giới trong sổ
function shownGender(person) {
    if (!person) return ""
    const label = (person.pendingVoice && person.pendingVoice.gender) || person.gender
    return label === S.s_nam_22dd59c8 ? "male" : label === S.s_nu_e15bc11c ? "female" : ""
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
    return groups.map(group => group.engine === "vieneu" ? S.s_giong_chinh_4a3858e3 : extras > 1 ? S.s_giong_them_fb4ef110 + (++seen) : S.s_giong_them_f6d2cefe)
}
function sharedText(voice, current) {
    const others = voice.otherUsers ? voice.otherUsers + S.s_nguoi_khac_dung_khong_cung_chuong_a5a72d73 : ""
    const sharedWith = voice.sharedWith || []
    if (!sharedWith.length) return others || (current ? S.s_giong_dang_doc_cho_nguoi_nay_16983253 : S.s_chua_ai_dung_3ba5b001)
    const people = sharedWith.map(person => person.label + " (" + person.chapters + S.s_chuong_be1b3067).join(", ")
    const after = S.s_hai_nguoi_se_nghe_giong_het_nhau_958bdccc
    return S.s_cung_chuong_voi_453ab883 + people + " - " + after + (others ? "\u00a0·\u00a0" + others : "")
}
// Hộp của người kể: giọng nhân vật đang giữ không chọn được - nói của ai (tối đa ba tên)
function takenText(takenBy) {
    return S.s_dang_la_giong_cua_9c41f23f + takenBy.slice(0, 3).join(", ") + (takenBy.length > 3 ? S.s_va_79e3d3b1 + (takenBy.length - 3) + S.s_nguoi_khac_b94bd0d6 : "") + S.s_nguoi_ke_can_giong_rieng_49eceac6
}
// Dòng phụ dưới tên giọng: miền + phong cách (hay chất giọng của máy khác) và ai đang dùng
function voiceMeta(voice, withGender) {
    const parts = voice.description ? [voice.description] : [voice.region ? S.s_mien_030e1e49 + voice.region : "", voice.style]
    const about = [withGender && !voice.description ? voice.genderLabel : ""].concat(parts).filter(Boolean).join("\u00a0·\u00a0")
    const alone = voice.current && !(voice.sharedWith || []).length && !voice.otherUsers
    const use = voice.takenNote || ((voice.takenBy || []).length ? takenText(voice.takenBy) : alone ? "" : sharedText(voice, voice.current))
    return [about, use].filter(Boolean).join("\u00a0·\u00a0")
}
// Chữ của nút cuối hàng
function voiceAction(voice) {
    return voice.current ? S.s_dang_dung_275ca289 : voice.pending ? S.s_da_chon_7f7e38b3 : voice.takenNote ? S.s_nguoi_ke_dung_e9ddd95f : (voice.takenBy || []).length ? S.s_nhan_vat_dung_0b0df351 : S.s_chon_1171ca97
}
function estimateText(seconds, measured) {
    const length = seconds < 60 ? S.s_chua_toi_1_phut_e8b7904f : S.s_khoang_934859d7 + formatLength(seconds)
    return measured === false ? length + S.s_uoc_chung_vi_cuon_chua_xong_chuong_nao_de_ca55dab5 : length + S.s_tren_may_nay_4fcdc883
}
// Một dòng trong hộp: đổi giọng tốn gì
function rerecordText(name, cost) {
    if (!cost.lines) return S.s_chua_cau_nao_cua_e7ec8755 + name + S.s_duoc_thu_doi_giong_khong_phai_thu_lai_gi_de7215ae
    return S.s_doi_giong_la_thu_lai_9ff9f393 + formatNumber(cost.lines) + S.s_cau_da_thu_cua_4ad4cc36 + name + ", " + estimateText(cost.seconds, cost.measured) + "."
}
function genderWord(gender) { return gender === "female" ? S.s_nu_316c30fd : "nam" }

// ---- "Nghe thử bằng câu của sách" (VoiceTry.tsx, previewText.ts, voiceTryText.ts) -----------------------------------------------
// Máy thu thử một câu của chính nhân vật bằng giọng đang cân nhắc - đúng giọng sẽ áp, không ghi gì vào sách. Bản đã nghe trong phiên (theo sách, người,
// giọng): bấm lại là phát lại, không hỏi máy chủ.
var heard = {}
function tryKey(bookId, request) { return [bookId, request.character, request.preset || "", request.gender || "", request.avoid || ""].join("\u0000") }
function tryId(preview) { return "voice-try-" + preview.url }
function tryLabel(voiceName, playing) { return playing ? S.s_dung_nghe_thu_41a2925b : S.s_nghe_giong_c10b4bc4 + voiceName + S.s_doc_mot_cau_cua_sach_fa73252c }
function tryHint(name, hasLine) {
    return hasLine ? S.s_nut_sach_doc_cau_cua_d9dd6eec + name + S.s_doc_mau_chung_26751b7c : name + S.s_chua_co_cau_nao_de_doc_thu_nut_la_cau_mau_438fb5c2
}
function tryAsking(voiceName) { return S.s_may_dang_doc_thu_giong_c9983cdc + voiceName + S.s_lan_dau_co_the_mat_vai_chuc_giay_c3784e8d }
var NO_LINE = S.s_nguoi_nay_chua_co_cau_nao_de_doc_thu_dang_85cfd8f2
// Lời từ chối của máy chủ: mã quen thì câu viết sẵn, không thì lời của máy chủ (đã là tiếng Việt)
var REFUSALS = {
    producing: S.s_may_dang_lam_sach_thu_lai_khi_xong_eea5a664,
    gpu: S.s_card_do_hoa_dang_ban_thu_lai_sau_it_phut_f63229bf,
    studio: S.s_cai_studio_de_nghe_thu_60d07d86,
    busy: S.s_dang_nghe_thu_cau_khac_bam_lai_sau_it_giay_8047fd55
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
    return S.s_luc_thu_that_se_nghe_gan_nhu_vay_u00a0_u00_7dab492d + excerpt(text, 70) + "”" + (speaker ? S.s_u00a0_u00a0giong_d2949262 + speaker : "")
}

// ---- Mô-đun giọng của máy đọc khác (voiceEngines.ts: EngineModuleStatus, moduleNote) --------------------------------------------------
// Dòng ghi chú dưới tên nhóm của một máy đọc chưa sẵn sàng trên máy này; "" khi đã dùng được
function moduleNote(status) {
    if (!status || status.state === "ready") return ""
    if (status.state === "downloading") return S.s_dang_tai_giong_980a1411 + Size.formatSize(status.total) + ") " + Voice.percent(status) + "%"
    if (status.state === "error") return status.error || S.s_chua_tai_duoc_giong_thu_lai_b81aafc6
    if (status.state === "unsupported") return S.s_may_nay_chua_dung_duoc_nhung_giong_nay_89504253
    const cancelled = status.cancelled ? Voice.CANCELLED_NOTE + " " : ""
    if (status.damaged) return cancelled + S.s_giong_nay_da_tai_nhung_mot_phan_bi_mat_hay_08c142c0
    if (status.state === "outdated") return cancelled + S.s_co_ban_giong_moi_e935fe26 + Size.formatSize(status.bytes) + S.s_tai_de_dung_tiep_c5237f84
    return cancelled + S.s_may_doc_khac_can_tai_them_39c523da + Size.formatSize(status.bytes) + S.s_mot_lan_deca884d
}
// Nút tải của nhóm: chỉ khi máy đọc chưa có / hỏng / cũ
function moduleAction(status) {
    if (!status || ["missing", "error", "outdated"].indexOf(status.state) < 0) return ""
    return status.state === "error" ? S.s_thu_lai_c58d068c : status.damaged ? S.s_sua_giong_df27f611 : S.s_tai_giong_d6f57d0b
}
// Nhóm có đầu riêng (tên + nút tải) khi có hai nhóm trở lên hay không phải máy đọc chính (VieNeu)
function groupHasHeader(groups, group) { return groups.length > 1 || group.engine !== "vieneu" }
