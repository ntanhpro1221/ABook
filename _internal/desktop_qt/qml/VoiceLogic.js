.import "UiStrings.js" as S
.pragma library
.import "SizeFormat.js" as Size

// Phần thuần (không giao diện) của Cài đặt › Giọng đọc, chép từng chữ từ bản web: listen/voiceGroups.ts, readAloudVoice.ts (chọn giọng mặc định,
// lời báo chữ đi đâu), vieneuModule.ts (lời của thẻ giọng trên máy), voiceSpeed.ts (Hiệu năng), studio/musicLocal.ts (hai câu chung).
// Chỗ web viết S.s_copy_998bbb22cf19 thì đây viết S.s_copy_91f4af3123f0 (chủ app 26-10: một cách viết duy nhất).

var SAMPLE_TEXT = S.s_xin_chao_toi_se_doc_sach_cho_ban_nghe_ban_885b35e2
var ONLINE_NOTICE = S.s_giong_edge_gui_chu_cua_sach_toi_may_chu_mi_7aefebec
var DEVICE_HINT = S.s_cai_giong_tieng_viet_tai_cai_dat_windows_t_a66056d9
var LOAD_ERROR = S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_giong_46330dab
var DEFAULT_VOICE_ERROR = S.s_chua_luu_duoc_giong_mac_dinh_ban_hay_chon_a2d2c7af
var CANCELLED_NOTE = S.s_da_huy_lan_tai_sau_lam_tiep_tu_cho_dung_a3bd5f77
var RETRYING_NOTE = S.s_mang_chap_chon_dang_thu_lai_e0ce6cbb
var ONLINE_VOICE = "edge:vi-VN-HoaiMyNeural"

// Tên nhà cung cấp giọng dùng khoá riêng
var KEYED = {azure: S.s_azure_speech_8bd84d93, google: S.s_google_cloud_69bd2211, fpt: "FPT.AI", viettel: S.s_viettel_ai_9094e708}

// Cách lấy khoá, theo những gì người dùng thấy trên trang của nhà cung cấp
var KEY_HELP = {
    azure: S.s_azure_tao_speech_f0_mien_phi_keys_and_endp_13c271d5,
    google: S.s_google_cloud_bat_cloud_text_to_speech_api_6c11e0dc,
    fpt: S.s_tren_console_fpt_ai_dang_nhap_mo_muc_text_4010b0be,
    viettel: S.s_tren_viettelai_vn_dang_nhap_mo_tai_khoan_t_0f2b04ac
}

// Các nhóm giọng theo nhà cung cấp, đúng thứ tự và tên ở Cài đặt › Giọng đọc
var GROUPS = [
    {provider: "edge", title: S.s_edge_0f82fe72, detail: S.s_truc_tuyen_mien_phi_0282fe41},
    {provider: "azure", title: KEYED.azure, detail: S.s_dung_khoa_cua_ban_36c096a0},
    {provider: "google", title: KEYED.google, detail: S.s_dung_khoa_cua_ban_36c096a0},
    {provider: "fpt", title: KEYED.fpt, detail: S.s_dung_khoa_cua_ban_36c096a0},
    {provider: "viettel", title: KEYED.viettel, detail: S.s_dung_khoa_cua_ban_36c096a0},
    {provider: "vieneu", title: S.s_vieneu_338b8a9f, detail: S.s_tren_may_nay_khong_can_mang_c8ad4ea8},
    {provider: "supertonic", title: S.s_supertonic_b426cb32, detail: S.s_tren_may_nay_khong_can_mang_c8ad4ea8},
    {provider: "device", title: S.s_giong_cua_may_2404d649, detail: S.s_khong_can_mang_1c7dfe7f}
]

function groupLabel(group) { return group.detail ? group.title + "\u00a0·\u00a0" + group.detail : group.title }

function genderLabel(gender) { return gender === "female" ? S.s_nu_e15bc11c : gender === "male" ? S.s_nam_22dd59c8 : "" }

// S.s_hoai_my_edge_65e287a0 -> S.s_copy_7d21bf1340d9
function spokenVoiceName(name) {
    const spoken = String(name).replace(/\s*\([^)]*\)\s*$/, "").trim()
    return spoken || name
}

// Tách S.s_copy_9ac1ef13c8d5 thành tên giọng + tên mô-đun
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
    if (keyed) return S.s_giong_7e6f9338 + keyed + S.s_gui_chu_cua_sach_toi_7aecc941 + keyed + S.s_bang_khoa_cua_ban_co_the_bi_tinh_tien_vao_1cae8fbf
    return voice.online ? ONLINE_NOTICE : ""
}

// Giọng VieNeu kể chuyện trung tính của từng bản, theo thứ tự ưu tiên (readAloudVoice.ts NARRATOR_VOICES)
var NARRATOR = {
    turbo: [S.s_duc_tri_c0417aaf, S.s_copy_9ce4f6d91ba0, "Kim Thanh", S.s_doan_trang_61fdcaa5, S.s_my_duyen_ad56a239, S.s_copy_3d89e39b9ae7, S.s_copy_8f79b50d9ab1, S.s_thanh_binh_6455e387],
    nano: [S.s_ai_han_a1f0d04f, S.s_my_duyen_ad56a239, S.s_duc_tri_c0417aaf]
}
// Checked against assets/voice_rank.json by the shared web/Qt test.
var NEVER_AUTO = [S.s_copy_520e2e7d18eb, S.s_copy_4d4dd0d13c5f, S.s_copy_51a4599e02f8]

function autoAllowed(voice) {
    return NEVER_AUTO.indexOf(nfc(voice.id.slice(voice.id.indexOf("/") + 1))) < 0
}

function nfc(text) { return text.normalize ? text.normalize("NFC") : text }

function narratorVoice(voices, gender) {
    const local = voices.filter(v => v.provider === "vieneu" && autoAllowed(v))
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
    const available = voices.filter(autoAllowed)
    const fallback = available.find(v => v.default) || available[0]
    const local = chosen ? undefined : narratorVoice(voices, fallback ? fallback.gender : undefined)
    return local || fallback
}

// ---- Mô-đun giọng trên máy (VieNeu, Supertonic) ----

var VIENEU = {
    key: "vieneu", name: S.s_giong_vieneu_371ad9fb, title: S.s_giong_vieneu_371ad9fb, path: "/api/readaloud/vieneu",
    invite: S.s_giong_hay_doc_ngay_tren_may_khong_can_mang_69bed8de,
    tiers: ["turbo", "nano"]
}
var SUPERTONIC = {
    key: "supertonic", name: S.s_giong_supertonic_9922ded4, title: S.s_giong_supertonic_9922ded4, path: "/api/readaloud/supertonic",
    invite: S.s_muoi_giong_nam_nu_nhe_may_khong_can_mang_c_4e018b39,
    tiers: ["supertonic"]
}
var TIER_NAME = {turbo: S.s_giong_vieneu_371ad9fb, nano: S.s_giong_vieneu_nano_dc5fdeb6, supertonic: S.s_giong_supertonic_9922ded4}
var LIVE_RTF = 0.8

function lowerFirst(text) { return text.charAt(0).toLowerCase() + text.slice(1) }

function tierVoicePrefix(tier) { return tier === "supertonic" ? "supertonic:" : "vieneu:" + tier + "/" }

function percent(status) {
    return status.total > 0 ? Math.min(100, Math.floor((status.done / status.total) * 100)) : 0
}

function seconds(value) { return value.toFixed(1).replace(".", ",") }

function working(status) { return Boolean(status) && (status.state === "downloading" || Boolean(status.benchmarking)) }

// Dòng tóm tắt của mục S.s_bo_giong_75b79178
function moduleActivity(vieneu, supertonic) {
    const out = []
    const pairs = [[S.s_vieneu_338b8a9f, vieneu], [S.s_supertonic_b426cb32, supertonic]]
    for (const pair of pairs) {
        const status = pair[1]
        if (status && status.state === "downloading") out.push(pair[0] + "\u00a0·\u00a0" + percent(status) + "%")
        else if (status && status.benchmarking) out.push(pair[0] + S.s_u00a0_u00a0dang_do_0bd36fdc)
    }
    return out.join("\u00a0·\u00a0") || S.s_tai_do_va_quan_ly_5d6c8c8d
}

function hasInstalled(status) { return Boolean(status) && (status.choices || []).some(c => c.installed) }

// Một dòng khuyên tải bộ nào; Supertonic chỉ đánh dấu sẵn khi máy không chạy được VieNeu
function moduleAdvice(vieneu, supertonic) {
    if (!vieneu || !vieneu.state) return {advice: "", preselectSupertonic: false}
    if (vieneu.state === "unsupported") return {advice: "", preselectSupertonic: true}
    if (hasInstalled(vieneu) || hasInstalled(supertonic)) return {advice: "", preselectSupertonic: false}
    const name = lowerFirst(TIER_NAME[vieneu.recommended === "nano" ? "nano" : "turbo"])
    return {advice: S.s_nen_dung_0670a68c + name + S.s_chi_can_tai_mot_bo_giong_e4b2c8c2, preselectSupertonic: false}
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
    return S.s_dien_thoai_dang_dung_du_lieu_di_dong_tai_23a80377 + Size.formatSize(bytes) + S.s_co_the_ton_tien_mang_nen_cho_co_wi_fi_0c02fc1c
}

function fastUnsupportedNote(status) {
    return status.fastUnsupported ? S.s_ban_tang_toc_may_nay_khong_chay_duoc_e5d9f595 + status.fastUnsupported + ")." : ""
}

function acceleratedNote(state) {
    if (!state.on) return S.s_dang_doc_bang_ban_thuong_1621d77e
    if (state.problem) return S.s_may_nay_chua_chay_duoc_ban_tang_toc_dang_d_b34f3faf
    return state.active ? S.s_dang_doc_bang_ban_tang_toc_c2dce725 : S.s_ban_tang_toc_se_dung_tu_lan_doc_ke_12b359e4
}

function benchmarkLabel(tier, result, live) {
    const limit = live === undefined ? LIVE_RTF : live
    const name = TIER_NAME[tier]
    if (result.rtf >= limit) {
        const hour = Math.max(1, Math.round(result.rtf * 60))
        return name + S.s_may_nay_khong_kip_doc_truc_tiep_0a50a380 + seconds(result.rtf) + S.s_giay_cho_moi_giay_nghe_dung_lam_truoc_moi_45e9decc + hour + S.s_phut_dd766870
    }
    const speed = result.rtf > 0 ? 1 / result.rtf : 0
    return name + S.s_doc_truc_tiep_duoc_may_nay_doc_nhanh_gap_6c53f9d8 + seconds(speed) + S.s_lan_toc_do_nghe_doan_dau_chuong_co_tieng_s_80a96d66 + seconds(result.firstAudioMs / 1000) + S.s_giay_e95d4212
}

// Lời đề nghị đổi giọng (không bao giờ tự đổi) và chữ trên nút
function suggestionText(suggestion) {
    const slow = TIER_NAME[suggestion.tier]
    const lead = slow + S.s_doc_cham_tren_may_nay_955dc130 + seconds(suggestion.rtf) + S.s_giay_cho_moi_giay_nghe_giu_giong_nay_thi_d_ac1058c1
    if (suggestion.switchTo === "nano") {
        return suggestion.installed
            ? {message: lead + S.s_giong_vieneu_nano_nhe_hon_da_co_san_f7b999a6, action: S.s_dung_giong_vieneu_nano_b84996dd}
            : {message: lead + S.s_giong_vieneu_nano_nhe_hon_hop_may_nay_1d0f6d48, action: S.s_tai_giong_vieneu_nano_e24acf37}
    }
    return {message: lead + S.s_giong_truc_tuyen_nhe_may_can_mang_e63eaf7a, action: S.s_dung_giong_truc_tuyen_a5bae2dc}
}

// Câu chính của thẻ theo trạng thái
function moduleLabel(status, copy) {
    const mid = lowerFirst(copy.name)
    if (status.state === "error") return status.error
    if (status.state === "downloading")
        return status.retrying ? RETRYING_NOTE + " (" + mid + ", " + percent(status) + "%)" : S.s_dang_tai_4568372a + mid + " (" + Size.formatSize(status.total) + ") " + percent(status) + "%"
    if (status.benchmarking) return Object.keys(status.benchmark || {}).length === 0 ? S.s_dang_thu_giong_vua_tai_tren_may_nay_vai_gi_2bdb3c97 : S.s_dang_do_lai_toc_do_tren_may_nay_vai_giay_c82d10d7
    if (status.state === "unsupported") return status.reason ? S.s_may_nay_chua_dung_duoc_7b938f54 + mid + ": " + status.reason + "." : S.s_may_nay_chua_dung_duoc_7b938f54 + mid + "."
    if (status.restart) return copy.name + S.s_da_cap_nhat_mo_lai_abook_de_dung_ban_moi_f196ad36
    const cancelled = status.cancelled ? CANCELLED_NOTE + " " : ""
    if (status.state === "outdated") return cancelled + copy.name + S.s_co_ban_moi_a04a8d79 + Size.formatSize(status.outdatedBytes) + S.s_ban_dang_dung_van_doc_binh_thuong_fc2d4305
    if (status.state === "ready") return copy.name + S.s_da_co_tren_may_chon_trong_nut_giong_doc_kh_6edd0dda
    return cancelled + copy.invite
}

// Lời hỏi trước khi gỡ một giọng khỏi máy, nói từ phía người nghe
function removeAsk(use) {
    if (!use) return S.s_giong_se_khong_con_tren_may_nay_cho_toi_kh_cb683781
    if (!use.bookCount) return S.s_chua_cuon_nao_dung_giong_nay_ban_tai_lai_d_7cef0995
    const titles = use.books.slice(0, 3).map(book => "“" + book.title + "”").join(", ")
    const more = use.bookCount > 3 ? S.s_va_79e3d3b1 + (use.bookCount - 3) + S.s_cuon_khac_d0f2513f : ""
    const who = use.bookCount + S.s_cuon_dang_dung_giong_nay_cc894228 + titles + more + "), " + use.peopleCount + S.s_nhan_vat_3c43b4c4
    const rest = use.left
        ? use.left + S.s_cau_chua_thu_se_im_toi_khi_ban_tai_lai_gio_961a2c5b
        : S.s_cac_cau_da_thu_van_nghe_duoc_a3a367c7
    return who + " " + rest
}

// ---- Hiệu năng (voiceSpeed.ts) ----

var SPEED_TITLE = S.s_toc_do_doc_3657e59d
var SPEED_OPTIONS = [
    {value: "auto", label: S.s_tu_dong_a25c8028},
    {value: "quality", label: S.s_chat_luong_cao_nhat_74af310a},
    {value: "fast", label: S.s_nhanh_hon_ecd73c9a}
]
var SPEED_DESCRIPTION = {
    auto: S.s_may_kip_thi_doc_ban_hay_nhat_afe3d688,
    quality: S.s_luon_doc_ban_hay_nhat_may_cham_co_the_phai_2de7d693,
    fast: S.s_nhanh_hon_tieng_kem_hon_chut_hop_may_yeu_d7e135a1
}
var SPEED_TIER = {quality: S.s_chat_luong_cao_nhat_74af310a, fast: S.s_nhanh_hon_ecd73c9a}

function speedLabel(choice) {
    const found = SPEED_OPTIONS.find(o => o.value === choice)
    return found ? found.label : ""
}

function speedDescription(choice) {
    return (SPEED_DESCRIPTION[choice] || "") + S.s_chi_ap_cho_giong_supertonic_sach_xuat_ra_l_0dfceae5
}

function speedWhy(voice, choice) {
    if (choice !== "auto") return S.s_ban_da_chon_f4117fe4
    if (voice.rtf === null || voice.rtf === undefined) return S.s_chua_do_duoc_toc_do_may_nay_6a6f6928
    return voice.tier === "fast" ? S.s_may_nay_doc_cham_hon_toc_do_nghe_1766f852 : S.s_may_nay_doc_kip_toc_do_nghe_aa82c4ab
}

function speedLine(voice, choice) {
    const lead = voice.name + S.s_dang_dung_fdd1225c + SPEED_TIER[voice.using] + " (" + speedWhy(voice, choice) + ")"
    if (voice.tier === "fast" && voice.using !== "fast")
        return voice.name + S.s_dang_dung_fdd1225c + SPEED_TIER.quality + S.s_ban_nhanh_hon_can_tai_them_bff4358e + Size.formatSize(voice.fastBytes) + "."
    return lead + "."
}

function needsFastDownload(voice) {
    return voice.tier === "fast" && voice.using !== "fast" && voice.fastBytes > 0
}
