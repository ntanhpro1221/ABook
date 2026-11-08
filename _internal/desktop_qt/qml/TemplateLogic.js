.import "UiStrings.js" as S
.pragma library

// "Mẫu thiết lập" có tên cho sách mới (ui/src/studio/bookTemplates.ts): phần thuần dùng chung cho Cài đặt (BookTemplates.qml: đổi tên, xoá) và trình tạo sách
// (NewProjectScreen: chọn, lưu, áp). Máy chủ kiểm lại cùng luật (webui/library.py clean_book_templates).
// Mẫu CHỈ mang lựa chọn thường: giọng kể, chất lượng, model đọc hiểu, "bắt đầu ngay", "chờ tôi duyệt trước khi thu" - không bao giờ mang nguồn truyện, tên
// sách, ngôi kể hay `dropCredits` (bỏ dòng ghi công là đồng ý riêng từng cuốn).

var MAX_TEMPLATES = 20
var NAME_MAX = 40
/** Nhãn của lựa chọn "không mẫu" (giá trị mặc định của app) - không đặt được làm tên mẫu. */
var DEFAULT_LABEL = S.s_mac_dinh_9a1af367
var PROFILE_LABEL = {high_quality: S.s_chat_luong_cao_dc7017a7, balanced: S.s_can_bang_8b88211d, fast: S.s_nhanh_c2385879}

function same(a, b) { return String(a).toLocaleLowerCase("vi") === String(b).toLocaleLowerCase("vi") }
function cleanName(value) { return String(value).split(/\s+/).filter(Boolean).join(" ") }
function modelKey(name) { return String(name).replace(/:latest$/, "") }

/** Danh sách mẫu trong tuỳ chọn - chịu được dữ liệu thiếu hay hỏng (không có thì rỗng). */
function templatesOf(value) {
    if (!Array.isArray(value)) return []
    const found = []
    for (const item of value) {
        if (!item || typeof item !== "object") continue
        if (typeof item.name !== "string" || !item.name || !PROFILE_LABEL[item.profile]) continue
        found.push({
            name: item.name,
            narrator: typeof item.narrator === "string" ? item.narrator : "",
            profile: item.profile,
            analysisModel: typeof item.analysisModel === "string" ? item.analysisModel : "",
            startNow: item.startNow !== false,
            precastWait: item.precastWait === true
        })
    }
    return found
}
function templateIndex(templates, name) {
    for (let i = 0; i < templates.length; ++i) if (same(templates[i].name, name)) return i
    return -1
}
function findTemplate(templates, name) {
    if (name === undefined || name === null) return undefined
    const index = templateIndex(templates, name)
    return index < 0 ? undefined : templates[index]
}
/** Lời báo cho một cái tên không dùng được, "" nếu được. `except`: tên đang được đổi (không tính là trùng với chính nó). */
function nameProblem(templates, raw, except) {
    const name = cleanName(raw)
    if (!name) return S.s_dat_cho_mau_mot_cai_ten_acc6e254
    if (name.length > NAME_MAX) return S.s_ten_mau_toi_da_c66079a1 + NAME_MAX + S.s_chu_6117d040
    if (same(name, DEFAULT_LABEL)) return "“" + DEFAULT_LABEL + S.s_la_mau_co_san_cua_app_chon_ten_khac_02696be5
    for (const item of templates) if (same(item.name, name) && !(except !== undefined && except !== "" && same(item.name, except))) return S.s_copy_69e49650d87d(name)
    return ""
}
function isFull(templates) { return templates.length >= MAX_TEMPLATES }
function summaryOf(t) {
    return [t.narrator || S.s_giong_may_de_xuat_35389626, PROFILE_LABEL[t.profile], t.startNow ? S.s_bat_dau_ngay_83137873 : S.s_cho_bam_bat_dau_5d760870]
        .concat(t.precastWait ? [S.s_cho_ban_duyet_truoc_khi_thu_35299b41] : []).join("\u00a0·\u00a0")
}

/** Model của mẫu mà máy không còn: tên model, "" nếu dùng được. `available` = tên các model đang có (chưa biết thì không kết luận). */
function missingModel(template, available) {
    const wanted = template ? template.analysisModel || "" : ""
    if (!wanted || !available || !available.length) return ""
    return available.some(function(name) { return modelKey(name) === modelKey(wanted) }) ? "" : wanted
}
/** Giọng kể của mẫu mà máy không còn: tên giọng, "" nếu dùng được. */
function missingVoice(template, available) {
    const wanted = template ? template.narrator || "" : ""
    if (!wanted || !available || !available.length) return ""
    return available.indexOf(wanted) >= 0 ? "" : wanted
}
function missingVoiceNote(voice) { return S.s_giong_7e6f9338 + voice + S.s_trong_mau_khong_con_tren_may_giu_giong_dan_28d28bcb }
function missingModelNote() { return S.s_bo_phan_tich_trong_mau_khong_con_tren_may_a85891ce }

/** Chụp các lựa chọn hiện tại của nháp thành một mẫu. `narratorAuto`: giọng kể do máy chọn - mẫu ghi "" để áp cho sách khác thì máy lại chọn theo sách ấy. */
function templateFromDraft(draft, name, narratorAuto) {
    return {
        name: cleanName(name),
        narrator: narratorAuto ? "" : draft.narrator,
        profile: draft.profile,
        analysisModel: draft.analysisModel || "",
        startNow: draft.startNow,
        precastWait: Boolean(draft.precastWait)
    }
}
/** Áp mẫu lên nháp: chỉ năm lựa chọn ấy + tên mẫu. Giọng của mẫu không còn trong danh sách (`voiceNames`) thì giữ giọng đang chọn; model cũng vậy.
 *  Mẫu ghi giọng "" (máy chọn) đưa giọng về `machineVoice`. */
function applyTemplate(draft, template, voiceNames, modelNames, machineVoice) {
    const usable = template.narrator && (!voiceNames || voiceNames.indexOf(template.narrator) >= 0)
    return Object.assign({}, draft, {
        narrator: usable ? template.narrator : (!template.narrator && machineVoice ? machineVoice : draft.narrator),
        profile: template.profile,
        analysisModel: missingModel(template, modelNames) ? (draft.analysisModel || "") : template.analysisModel,
        startNow: template.startNow,
        precastWait: template.precastWait,
        template: template.name
    })
}
/** Những lựa chọn mà áp mẫu có thể ghi đè (kèm `narratorPicked`): chụp trước khi áp để "Hoàn tác" trả lại đúng. */
function templateChoices(draft) {
    return {
        narrator: draft.narrator, narratorPicked: draft.narratorPicked, profile: draft.profile, analysisModel: draft.analysisModel || "",
        startNow: draft.startNow, precastWait: Boolean(draft.precastWait), template: draft.template
    }
}
var CHOICE_LABELS = [["narrator", S.s_giong_ke_cc1476e9], ["profile", S.s_chat_luong_7c01566d], ["analysisModel", S.s_model_doc_hieu_97027daf], ["startNow", S.s_bat_dau_ngay_83137873], ["precastWait", S.s_cho_ban_duyet_truoc_khi_thu_35299b41]]
/** Áp mẫu đã đổi những lựa chọn nào (nói như người dùng thấy). */
function changedChoices(before, after) {
    const a = templateChoices(before), b = templateChoices(after)
    return CHOICE_LABELS.filter(function(pair) { return a[pair[0]] !== b[pair[0]] }).map(function(pair) { return pair[1] })
}
/** Người dùng đã đổi lựa chọn nào đó sau khi áp mẫu. */
function isModified(draft, template, modelNames) {
    return (template.narrator !== "" && draft.narrator !== template.narrator)
        || draft.profile !== template.profile
        || (!missingModel(template, modelNames) && (draft.analysisModel || "") !== template.analysisModel)
        || draft.startNow !== template.startNow
        || Boolean(draft.precastWait) !== template.precastWait
}
