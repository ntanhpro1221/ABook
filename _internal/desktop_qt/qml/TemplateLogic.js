.pragma library

// "Mẫu thiết lập" có tên cho sách mới (ui/src/studio/bookTemplates.ts): phần thuần dùng chung cho Cài đặt (BookTemplates.qml: đổi tên, xoá) và trình tạo sách
// (NewProjectScreen: chọn, lưu, áp). Máy chủ kiểm lại cùng luật (webui/library.py clean_book_templates).
// Mẫu CHỈ mang lựa chọn thường: giọng kể, chất lượng, model đọc hiểu, "bắt đầu ngay", "chờ tôi duyệt trước khi thu" - không bao giờ mang nguồn truyện, tên
// sách, ngôi kể hay `dropCredits` (bỏ dòng ghi công là đồng ý riêng từng cuốn).

var MAX_TEMPLATES = 20
var NAME_MAX = 40
/** Nhãn của lựa chọn "không mẫu" (giá trị mặc định của app) - không đặt được làm tên mẫu. */
var DEFAULT_LABEL = "Mặc định"
var PROFILE_LABEL = {high_quality: "Chất lượng cao", balanced: "Cân bằng", fast: "Nhanh"}

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
    if (!name) return "Đặt cho mẫu một cái tên"
    if (name.length > NAME_MAX) return "Tên mẫu tối đa " + NAME_MAX + " chữ"
    if (same(name, DEFAULT_LABEL)) return "“" + DEFAULT_LABEL + "” là mẫu có sẵn của app - chọn tên khác"
    for (const item of templates) if (same(item.name, name) && !(except !== undefined && except !== "" && same(item.name, except))) return "Đã có mẫu tên “" + name + "”"
    return ""
}
function isFull(templates) { return templates.length >= MAX_TEMPLATES }
function summaryOf(t) {
    return [t.narrator || "Giọng máy đề xuất", PROFILE_LABEL[t.profile], t.startNow ? "bắt đầu ngay" : "chờ bấm bắt đầu"]
        .concat(t.precastWait ? ["chờ bạn duyệt trước khi thu"] : []).join(" · ")
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
function missingVoiceNote(voice) { return "Giọng " + voice + " trong mẫu không còn trên máy - giữ giọng đang chọn." }
function missingModelNote() { return "Bộ phân tích trong mẫu không còn trên máy - giữ bộ đang chọn." }

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
var CHOICE_LABELS = [["narrator", "giọng kể"], ["profile", "chất lượng"], ["analysisModel", "model đọc hiểu"], ["startNow", "bắt đầu ngay"], ["precastWait", "chờ bạn duyệt trước khi thu"]]
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
