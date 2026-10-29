.pragma library

// Phần thuần của việc cài Studio (ui/src/studio/StudioSetup.tsx, studioFit.ts, errorText.ts friendlySetupError, setupLeftover.ts):
// chữ chép từng chữ để thẻ "Cài Studio" ở màn Dự án, Cài đặt › Studio và khối nhắc ở trình tạo sách nói cùng một câu.

var STUDIO_WHAT = "Studio biến truyện chữ thành sách nói."
// Thời gian một chương: số đo của dây chuyền trên card 8 GB của máy thử (docs/ANALYSIS_RESEARCH.md)
var STUDIO_NEEDS = "NVIDIA từ 8 GB · tải ~25 GB · trống 35 GB · ~7–10 phút/chương."
var TESTED_GB = 8
var MIN_GB = 6

// ---- studio/studioFit.ts: máy này có đủ để làm sách nói không (NVIDIA từ 8 GB đủ, 6-8 GB chưa thử, dưới 6 GB hay không có card là không) ----
function studioFit(gpu) {
    if (!gpu) {
        const reason = "không có card đồ hoạ NVIDIA, hay driver NVIDIA chưa cài"
        return {level: "no", line: "Máy này " + reason + ".", reason: reason}
    }
    if (!(gpu.memory > 0)) return {level: "maybe", line: "Card " + gpu.name + ": chưa đọc được bộ nhớ của card, chưa biết có đủ không."}
    const gb = gpu.memory / Math.pow(2, 30)
    const shown = gpu.name + " (" + Math.round(gb) + " GB)"
    if (gb >= TESTED_GB - 0.5) return {level: "ok", line: "Card " + shown + ": đủ để làm sách nói (đã thử trên card " + TESTED_GB + " GB)."}
    if (gb >= MIN_GB - 0.5) return {level: "maybe", line: "Card " + shown + ": có thể chạy được nhưng chưa thử trên card dưới " + TESTED_GB + " GB, có thể chậm."}
    const reason = "card " + shown + " ít bộ nhớ hơn mức tối thiểu " + MIN_GB + " GB"
    return {level: "no", line: "Card " + shown + ": ít bộ nhớ hơn mức tối thiểu " + MIN_GB + " GB.", reason: reason}
}
/** Câu nói thật khi máy không làm sách nói được - MỘT câu cho trình tạo sách, bước cuối và thẻ Cài Studio. */
function noStudioLine(reason) { return "Máy này không làm sách nói được (" + reason + "). Bạn vẫn nghe ngay mọi sách." }

// ---- tình trạng từ /api/app ----
/** `info.studio` -> {missing, update, repair, action}: tên nút dẫn tới thẻ Studio ở màn Dự án (useStudioMissing). */
function studioMissing(studio) {
    const update = Boolean(studio && studio.installed && studio.outdated)
    const repair = Boolean(update && studio.damaged)
    return {
        missing: Boolean(studio && (!studio.installed || studio.outdated)),
        update: update, repair: repair,
        action: repair ? "Sửa Studio" : update ? "Cập nhật Studio" : "Cài Studio"
    }
}

// ---- tình trạng từ /api/studio/setup ----
/** Thẻ ở màn Dự án: hiện khi app đóng gói thiếu / cũ Studio (StudioSetupCard `needed`). */
function cardNeeded(info) { return Boolean(info && info.studio && (!info.studio.installed || info.studio.outdated)) }
function damagedOf(status) { return (status && status.damaged) || [] }
function isRepair(status) { return Boolean(status.installed) && damagedOf(status).length > 0 }
function isUpdate(status) { return Boolean(status.installed) && (status.outdated || []).length > 0 }
function staleOf(status) {
    const damaged = damagedOf(status)
    return (status.outdated || []).filter(function(label) { return damaged.indexOf(label) < 0 })
}
function started(status) { return (status.steps || []).some(function(step) { return step.done }) }
function currentStep(status) {
    const steps = status.steps || []
    for (let i = 0; i < steps.length; ++i) if (steps[i].id === status.step) return steps[i]
    return null
}
function progressOf(status) { return status.progress && status.progress.total > 0 ? status.progress.done / status.progress.total : -1 }
function cardTitle(status) { return isRepair(status) ? "Sửa Studio" : isUpdate(status) ? "Cập nhật Studio" : "Cài Studio" }
function cardLine(status) {
    if (isRepair(status)) return "Tải lại " + damagedOf(status).concat(staleOf(status)).join(", ") + "; sách giữ nguyên."
    if (isUpdate(status)) return "Cập nhật " + status.outdated.join(", ") + "; sách giữ nguyên."
    return STUDIO_NEEDS
}
/** Nút chính của thẻ theo tình trạng: {kind: "cancel" | "cancelOld" | "wait" | "unfit" | "go", text}. */
function cardButton(status, fit) {
    if (status.running) return {kind: "cancel", text: "Dừng"}
    if (status.leftover) return status.leftover.orphan ? {kind: "cancelOld", text: "Dừng lượt cũ"} : {kind: "wait", text: "Cài tiếp"}
    if (fit && fit.level === "no") return {kind: "unfit", text: "Vẫn cài"}
    return {kind: "go", text: isRepair(status) ? "Sửa Studio" : isUpdate(status) ? "Cập nhật Studio" : started(status) ? "Cài tiếp" : "Cài Studio"}
}

var OFFLINE = /getaddrinfo failed|\[Errno 11001\]|WinError 11001|WinError 10051|WinError 10060|Network is unreachable|Temporary failure in name resolution|Name or service not known|timed out|Connection (?:aborted|reset)|RemoteDisconnected|IncompleteRead/i
/** Lỗi dừng dở của bước "Cài Studio": mất mạng nói bằng lời người nghe và chỉ việc làm tiếp; nguyên văn ở `detail` cho "Chi tiết". */
function friendlySetupError(raw) {
    const detail = String(raw).trim()
    if (OFFLINE.test(detail)) return {summary: "Mất mạng giữa chừng - bấm Cài tiếp để làm tiếp.", detail: detail}
    return {summary: detail, detail: ""}
}
function clock(seconds) {
    if (!seconds) return "trước"
    const date = new Date(seconds * 1000)
    return (date.getHours() < 10 ? "0" : "") + date.getHours() + ":" + (date.getMinutes() < 10 ? "0" : "") + date.getMinutes()
}
function leftoverLine(leftover) {
    const when = clock(leftover.since)
    return leftover.orphan
        ? "Lượt cài lúc " + when + " (lần mở app trước) vẫn còn chạy ngầm. Bạn chờ nó xong rồi bấm Cài tiếp, hoặc bấm “Dừng lượt cũ” để cài lại từ chỗ dở."
        : "Một cửa sổ ABook khác đang cài Studio từ " + when + ". Bạn đóng nó hoặc chờ nó xong rồi bấm Cài tiếp."
}
