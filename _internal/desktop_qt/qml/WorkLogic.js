.pragma library
.import "DecisionLogic.js" as D
.import "StudioLogic.js" as Studio

// Hộp "Việc cần duyệt" (studio/WorkInbox.tsx, workText.ts, workFocus.ts, minorGroups.ts, precast.isOpenWork): loại thẻ, tiêu đề thẻ đã quyết, lời mở đầu, chia thẻ thành
// nhóm, bộ lọc, phân trang, "Giữ cả nhóm", tiêu điểm sau khi quyết. Chữ chép từng chữ của bản web; ở đây không có gì dính tới giao diện.

// Thứ tự loại việc = thứ tự khoá của KIND_LABEL bản web (thanh lọc liệt kê theo thứ tự này)
var KINDS = ["speaker", "turn", "pronunciation", "gender", "vocative", "alias", "bracket", "shared-voice", "unnamed", "audio", "narrator", "voice-wish", "snap", "teller-voice", "teller-thought", "refused"]
var KIND_LABEL = {
    "speaker": "Ai nói câu này",
    "turn": "Lượt đối đáp",
    "pronunciation": "Cách đọc tên",
    "gender": "Nam hay nữ",
    "vocative": "Gọi hay nói",
    "alias": "Một người hai tên",
    "bracket": "Lời trong 『』",
    "shared-voice": "Chung giọng",
    "unnamed": "Vai phụ không tên",
    "audio": "Bản thu lỗi",
    "narrator": "Người kể của đoạn",
    "voice-wish": "Giọng chưa đổi được",
    "snap": "Tên viết khác",
    "teller-voice": "Giọng lời dẫn",
    "teller-thought": "Nội tâm người kể",
    "refused": "Yêu cầu chưa được"
}
function kindLabel(kind) { return KIND_LABEL[kind] || kind }
var PAGE = 40
// Nhiều hơn ngần này lựa chọn thì phần còn lại gom vào “Người khác…”
var MAX_CHIPS = 6
var GENERIC_PEOPLE = ["Người kể", "Người kể đọc tất cả", "Vai phụ không tên"]
// Thẻ vai phụ cả cuốn hiện ngần này câu đầu; "Xem cả N câu" mở hết để bỏ chọn - nhóm lớn thì từng trang PICK_PAGE câu
var PICK_PREVIEW = 3
var PICK_PAGE = 100
// "Giữ như máy đang làm" cho cả loại thẻ đang lọc chỉ có ở các loại này
var BULK_KINDS = ["pronunciation", "speaker", "turn", "vocative", "unnamed"]

// Việc còn chờ người duyệt: chưa quyết, và quyết thì có tác dụng ngay (precast.isOpenWork, cùng phép đếm với work_items.open_count)
function isOpenWork(item) { return !item.requested && !item.redoOnly }

// ---- workText.ts ----
function narratorDecidedTitle(current, answer) {
    if (answer === "Giữ nguyên") return current ? "Đoạn này vẫn do " + current + " kể" : "Đoạn này vẫn kể ở ngôi thứ ba"
    if (answer === "Đổi người kể") return "Đoạn này không phải " + current + " kể"
    const name = answer.replace(/^Người kể:\s*/, "").trim()
    return "Đoạn này do " + (name || answer) + " kể"
}
function narratorButtons(current, heading) {
    const keep = current ? "Giữ " + current + " là người kể" : "Giữ nguyên ngôi thứ ba"
    if (!heading) return {accept: "Không phải " + current + " kể - đoạn kể ngôi thứ ba", keep: keep, accepted: "Đổi người kể"}
    return heading.label
        ? {accept: "Nhận: " + heading.label + " kể đoạn này", keep: keep, accepted: "Người kể: " + heading.label}
        : {accept: "Nhận: đoạn kể ngôi thứ ba", keep: keep, accepted: "Đổi người kể"}
}
// Thẻ đã quyết nói KẾT QUẢ thay vì lặp câu hỏi; null = giữ tiêu đề
function decidedTitle(item) {
    const answer = item.requested
    if (!answer) return null
    if (item.kind === "pronunciation" && item.surface) {
        return answer === item.current ? "Giữ: “" + item.surface + "” đọc là “" + answer + "”" : "“" + item.surface + "” sẽ đọc là “" + answer + "”"
    }
    if (item.voiceChoices && item.voiceChoices.length) {
        const found = item.voiceChoices.find(function(choice) { return choice.label === answer || choice.done === answer })
        return found && found.done !== undefined ? found.done : null
    }
    if (item.kind === "alias") return "“" + (item.subject !== undefined && item.subject !== null ? item.subject : item.current) + "” là " + D.midSentence(answer)
    if (item.kind === "narrator") return narratorDecidedTitle(item.current, answer)
    if (item.lines && item.lines.length) return (item.lines.length > 1 ? item.lines.length + " câu này" : "Câu này") + " của " + D.midSentence(answer)
    return null
}
function cardTitle(item) { const decided = decidedTitle(item); return decided !== null ? decided : item.title }
function inboxLead(book) {
    const first = book.running && book.paused ? "Sách đang tạm dừng; sửa áp khi làm tiếp."
        : book.running ? "Máy đang chạy tiếp; sửa áp ở chương sau."
        : book.phase === "done" ? "Sửa xong, bấm “Áp dụng thay đổi”."
        : "Sách đang dừng; sửa áp khi làm tiếp."
    return "Ưu tiên việc trên. " + first
}
// Chữ ký tự: chữ cái có hoa / thường (kể cả tiếng Việt), chữ số, hay chữ Nhật - Hàn - Trung
function isWordChar(ch) {
    if (!ch) return false
    return ch.toLowerCase() !== ch.toUpperCase() || (ch >= "0" && ch <= "9") || ch.charCodeAt(0) >= 0x3040
}
// Câu lời kể chia thành mảnh thường / mảnh tô (`mark`) ở mỗi chỗ có một trong `names`: nguyên chữ, không phân biệt hoa thường, tên dài trước
function markNames(text, names) {
    const seen = {}
    const forms = []
    for (const name of names || []) {
        const form = String(name).trim()
        if (form && !seen[form]) { seen[form] = true; forms.push(form.toLowerCase()) }
    }
    forms.sort(function(a, b) { return b.length - a.length })
    const lower = text.toLowerCase()
    if (!forms.length || lower.length !== text.length) return [{text: text, mark: false}]
    const parts = []
    let last = 0
    let i = 0
    while (i < text.length) {
        let hit = 0
        if (!isWordChar(text.charAt(i - 1))) {
            for (const form of forms) {
                if (lower.startsWith(form, i) && !isWordChar(text.charAt(i + form.length))) { hit = form.length; break }
            }
        }
        if (hit) {
            if (i > last) parts.push({text: text.slice(last, i), mark: false})
            parts.push({text: text.slice(i, i + hit), mark: true})
            i += hit
            last = i
        } else i++
    }
    if (last < text.length || !parts.length) parts.push({text: text.slice(last), mark: false})
    return parts
}
// Màu của Theme thành chữ cho CSS của Text.RichText (Qt đọc rgba(), không đọc #aarrggbb)
function cssColor(color) {
    const rgb = Math.round(color.r * 255) + "," + Math.round(color.g * 255) + "," + Math.round(color.b * 255)
    return color.a >= 1 ? "rgb(" + rgb + ")" : "rgba(" + rgb + "," + Math.round(color.a * 1000) / 1000 + ")"
}
function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
// Câu ví dụ của thẻ thành HTML ngắn cho Text.RichText: tên ứng viên tô nền nhạt, đậm, màu nhấn
function exampleHtml(example, markBg, markInk) {
    if (!example.names || !example.names.length) return esc(example.text)
    return markNames(example.text, example.names).map(function(part) {
        return part.mark ? "<span style=\"background-color:" + markBg + "; color:" + markInk + "; font-weight:600\">" + esc(part.text) + "</span>" : esc(part.text)
    }).join("")
}
// Dòng nhỏ trên câu: "Chương 1 · câu 3 · máy gán: X · lời kể · sẽ đổi · chưa thu". `html`: ra HTML cho Text.RichText ("sẽ đổi" đậm màu `ink`).
function exampleMeta(example, willChange, html, ink) {
    const head = example.chapterTitle + " · " + (example.seq === 0 ? "tiêu đề chương" : "câu " + example.seq)
        + (example.speaker ? " · máy gán: " + example.speaker : "")
        + (example.narration ? " · lời kể" : "")
    const change = willChange ? (html ? "<span style=\"color:" + ink + "; font-weight:600\"> · sẽ đổi</span>" : " · sẽ đổi") : ""
    return (html ? esc(head) : head) + change + (!example.hasAudio ? " · chưa thu" : "")
}

// ---- minorGroups.ts ----
// Câu bỏ chọn là tập `dropped` dạng {stableId: true}
function pickedLines(lines, dropped) { return lines.filter(function(line) { return !dropped[line.stableId] }) }
function toggleLine(dropped, stableId) {
    const next = Object.assign({}, dropped)
    if (next[stableId]) delete next[stableId]; else next[stableId] = true
    return next
}
function keepRequests(item) {
    if (item.keepGroups && item.keepGroups.length) return item.keepGroups.filter(function(group) { return group.lines.length > 0 })
    if (item.lines && item.lines.length && item.currentValue) return [{lines: item.lines, speaker: item.currentValue}]
    return []
}
function pickNote(picked, total) {
    if (picked === total) return "Đang chọn cả " + total + " câu"
    if (picked === 0) return "Chưa chọn câu nào trong " + total + " câu"
    return "Đang chọn " + picked + "/" + total + " câu"
}
// Thẻ nhóm lớn chỉ mang vài câu đầu (`examplesTotal` là tổng); "Xem thêm" lấy từng trang (GET /work/examples). Trả câu đã có, tổng, và đường hỏi trang kế ("" = đã đủ).
function examplesPage(bookId, key, first, more, total, page) {
    const loaded = more.length > 0 ? first.concat(more) : first
    const all = Math.max(total || 0, loaded.length)
    const next = loaded.length < all ? "/api/books/" + bookId + "/work/examples?key=" + encodeURIComponent(key) + "&offset=" + loaded.length + "&limit=" + page : ""
    return {loaded: loaded, total: all, next: next}
}
function moreText(shown, total) { return "Xem thêm (đang hiện " + Studio.formatNumber(shown) + "/" + Studio.formatNumber(total) + " câu)" }

// ---- Chọn người nói trên thẻ ----
// Chip hiện thẳng / chip gom vào “Người khác…”: chừa MAX_CHIPS đầu, lựa chọn đã ghi và người chung chung
function isAnswer(item, choice) { return !!item.requested && (choice.name === item.requested || choice.label === item.requested) }
function shownChoices(item) {
    return (item.choices || []).filter(function(choice, index) { return index < MAX_CHIPS || isAnswer(item, choice) || GENERIC_PEOPLE.indexOf(choice.label) >= 0 })
}
function moreChoices(item) {
    const shown = shownChoices(item)
    return (item.choices || []).filter(function(choice) { return shown.indexOf(choice) < 0 })
}
// Gợi ý tên bằng chính tên trong sách
function sampleName(item) {
    for (const choice of item.choices || []) {
        const text = choice.name !== undefined && choice.name !== null ? choice.name : choice.label
        if (text && GENERIC_PEOPLE.indexOf(text) < 0 && !/^(Tất cả là|Giữ) /.test(text)) return text
    }
    return ""
}
// Chip được gạch chân (lựa chọn đã ghi, hay máy đề xuất ở chip đầu)
function chipMarked(item, choice, index) {
    if (item.requested) return isAnswer(item, choice)
    return index === 0 && item.kind !== "unnamed" && item.suggested !== false
}
function keepButtonLabel(item) { return item.keepLabel || (item.kind === "unnamed" ? "Đúng là vai phụ" : "Giữ " + item.current) }
// Tên người từ mã của họ, theo các lựa chọn của thẻ (báo "trước đó đang là …")
function personOf(item, value) {
    if (value === item.currentValue) return item.current
    const choice = (item.choices || []).find(function(option) { return option.value === value })
    return choice ? (choice.name !== undefined && choice.name !== null ? choice.name : choice.label) : value
}
function speakerBack(item, which) {
    if (item.requested) return "Trở lại quyết định trước: " + which + " của " + D.midSentence(item.requested) + "."
    if (item.pick) return D.sentence(which) + " trở lại chờ duyệt."
    return D.sentence(which) + " lại là của " + D.midSentence(item.current) + "."
}
function speakerToast(item, recorded, speaker) {
    const which = recorded > 1 ? recorded + " câu này" : "câu này"
    if (speaker === item.currentValue) return item.keepLabel ? "Đã ghi: " + item.keepLabel : "Giữ nguyên: " + which + " của " + D.midSentence(item.current)
    const choice = (item.choices || []).find(function(option) { return option.value === speaker })
    const label = choice ? (choice.name !== undefined && choice.name !== null ? choice.name : choice.label) : speaker
    return "Đã ghi: " + which + " của " + D.midSentence(label)
}
function speakerAppliedLine(item, pending) {
    if (item.kind === "alias") return "Đã ghi: “" + (item.subject !== undefined && item.subject !== null ? item.subject : item.current) + "” là " + D.midSentence(item.requested) + " - cả cuốn và các phần sau."
    const n = item.lines ? item.lines.length : 1
    return "Đã ghi: " + (n > 1 ? n + " câu này" : "câu này") + " của " + D.midSentence(item.requested) + " - " + pending + "."
}
function scopeNote(item) {
    return item.scopeLabels
        ? item.scopeLabels[0] + " theo chương; " + item.scopeLabels[1] + " theo cả sách và các phần sau."
        : "Câu xen kẽ chỉ đổi câu đánh dấu; cả chuỗi đổi toàn bộ người nói."
}

// ---- Thẻ giọng / giới ----
function voiceHeard(item) { return item.current === "Giọng nam" || item.current === "Giọng nữ" ? item.current.toLowerCase() : "giọng đang có" }
function voiceBack(item) {
    if (item.kind === "gender" && item.subject) {
        return item.requested ? "Trở lại quyết định trước: " + item.subject + " là " + item.requested.toLowerCase() + "."
            : item.subject + " lại để máy quyết - vẫn đọc bằng " + voiceHeard(item) + "."
    }
    if (item.requested) return "Trở lại quyết định trước: " + item.requested + "."
    return item.kind === "shared-voice" ? "Hai người lại dùng chung giọng như trước." : "Thẻ hỏi lại như trước khi bấm."
}
function voiceChoiceMarked(item, choice) { return item.requested ? (choice.done === item.requested || choice.label === item.requested) : !!choice.recommended }

// ---- Thẻ cách đọc tên ----
function pronunciationBack(item) {
    return item.requested ? "Trở lại quyết định trước: “" + item.surface + "” đọc là “" + item.requested + "”." : "“" + item.surface + "” lại đọc là “" + item.current + "”."
}
function pronunciationAppliedLine(item, pending) {
    return item.requested === item.current ? "Giữ “" + item.requested + "” - không cần áp dụng." : "Đã ghi “" + item.requested + "” - " + pending + "."
}

// ---- Nhóm thẻ của hộp ----
// Số thay đổi đang chờ áp dụng trong các thẻ đã quyết: hai thẻ cùng quyết một câu là MỘT thay đổi; “Giữ” cách đang đọc là đã quyết mà không có gì chờ áp dụng.
function waitingChanges(decided) {
    const changes = {}
    for (const item of decided) {
        if (item.requested === item.current) continue
        const ids = item.lines ? item.lines.map(function(line) { return line.stableId }).sort() : []
        changes[ids.length ? "lines:" + ids.join(",") : "key:" + item.key] = true
    }
    return Object.keys(changes).length
}
// Chia việc của máy chủ thành các nhóm hộp hiển thị. `inPrecast`: {khoá: true} của thẻ đang nằm ở "Duyệt trước khi thu" (không hiện lại ở đây).
function groups(items, inPrecast, kind) {
    const precast = inPrecast || {}
    const undecided = items.filter(isOpenWork)
    const later = items.filter(function(item) { return !item.requested && item.redoOnly })
    const open = undecided.filter(function(item) { return !precast[item.key] })
    const answered = items.filter(function(item) { return item.requested })
    const redo = answered.filter(function(item) { return item.redoOnly })
    const decided = answered.filter(function(item) { return !item.redoOnly })
    const counts = {}
    for (const item of open) counts[item.kind] = (counts[item.kind] || 0) + 1
    const kinds = KINDS.filter(function(value) { return counts[value] })
    const active = kind !== "all" && !counts[kind] ? "all" : kind
    return {
        open: open, atReview: undecided.length - open.length, later: later, redo: redo, decided: decided, waiting: waitingChanges(decided),
        counts: counts, kinds: kinds, active: active,
        filtered: open.filter(function(item) { return active === "all" || item.kind === active })
    }
}
function decidedSummary(decided, waiting) {
    return waiting === decided.length ? "Đã quyết, chờ áp dụng · " + decided.length + " việc" : "Đã quyết · " + decided.length + " việc (" + waiting + " thay đổi chờ áp dụng)"
}
function endLine(group, hint) {
    return group.later.length > 0
        ? "Không còn việc nào sửa được ngay - những việc bên dưới chỉ có tác dụng khi làm lại phân tích từ đầu."
        : "Mọi việc đã có quyết định" + (group.decided.length > 0 ? " - " + hint : "") + "."
}
function precastLine(count) { return count + " việc của các chương đầu đang chờ ở “Duyệt trước khi thu”." }
function filterOptions(group) {
    const options = [{value: "all", label: "Tất cả · " + group.open.length}]
    for (const value of group.kinds) options.push({value: value, label: KIND_LABEL[value] + " · " + group.counts[value]})
    return options
}
function bulkKeepable(kind, items) {
    return items.filter(function(item) { return kind === "pronunciation" ? !!item.surface : keepRequests(item).length > 0 })
}
function bulkTitle(kind, count) { return "Giữ cả " + count + " thẻ “" + KIND_LABEL[kind] + "”?" }
function bulkDescription(kind) { return kind === "pronunciation" ? "Giữ cách đọc tên, không thu lại; có thể hoàn tác." : "Giữ người nói, không thu lại; có thể hoàn tác." }

// ---- workFocus.ts ----
// Thẻ nhận tiêu điểm sau khi danh sách đổi và tiêu điểm vừa mất. before / after: {open: [khoá], decided: [khoá]}; focused: khoá thẻ chứa tiêu điểm lần gần nhất (null = ở nút "Hoàn tác" của thông báo).
// Trả khoá thẻ, "end" (hết thẻ) hay null (không làm gì).
function focusAfterChange(before, after, focused) {
    if (focused === null) {
        const back = after.open.filter(function(key) { return before.open.indexOf(key) < 0 })
        const returned = back.find(function(key) { return before.decided.indexOf(key) >= 0 })
        if (returned !== undefined) return returned
        if (after.decided.length < before.decided.length && back.length) return back[0]
        return null
    }
    const list = before.open.indexOf(focused) >= 0 ? "open" : before.decided.indexOf(focused) >= 0 ? "decided" : null
    if (!list) return null
    const now = after[list]
    if (now.indexOf(focused) >= 0) return focused
    if (now.length) return now[Math.min(before[list].indexOf(focused), now.length - 1)]
    return list === "decided" && after.open.indexOf(focused) >= 0 ? focused : "end"
}
