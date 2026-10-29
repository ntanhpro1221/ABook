.pragma library
.import "StudioLogic.js" as Studio

// Tab Nhân vật, mục "Cách đọc tên" (studio/NameReadings.tsx, readingReach.ts, sharedReadings.tsx) và hộp thư thay đổi từ điện thoại (PhoneEdits.tsx): tìm tên, sửa lạc quan,
// lời của dòng, câu "chữ ấy chạm tới bao nhiêu câu", cách đọc chung, lời kể lần gửi gần đây. Chữ chép từng chữ của bản web.

var PAGE = 30
// So tên không phân biệt hoa thường, dấu, gạch nối hay khoảng trắng: "hen" thấy "Hên-cơ", "dac lat" thấy "Đác-lát"
function fold(text) {
    return String(text).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/đ/g, "d").replace(/[\s\-‐-―]/g, "")
}
// Danh sách sau khi lưu `spokenForm` cho `item` - đúng điều máy chủ sẽ trả: cách đọc mới là "chờ áp dụng"; trùng cách đang đọc là "giữ". Tên CHƯA có trong danh sách thì chờ máy chủ nhận.
function withReading(data, item, spokenForm) {
    const keep = spokenForm === item.spoken
    const updated = Object.assign({}, item, {requested: keep ? null : spokenForm, byListener: item.byListener || keep})
    if (!data.items.some(function(entry) { return entry.surface === item.surface })) return data
    return Object.assign({}, data, {items: data.items.map(function(entry) { return entry.surface === item.surface ? updated : entry })})
}
function found(items, typed) {
    const needle = fold(typed)
    if (!needle) return items
    return items.filter(function(item) { return fold(item.surface).indexOf(needle) >= 0 || fold(item.requested !== null && item.requested !== undefined ? item.requested : item.spoken).indexOf(needle) >= 0 })
}
// Gõ đúng một chữ liền nhau mà KHÔNG khớp tên nào thì mời thêm cách đọc cho nó
function single(typed) { return /^\S{1,80}$/.test(typed) }
function freshItem(surface) { return {surface: surface, spoken: "", byListener: false, lines: 0, requested: null, example: null} }
function countedNames(items) { return items.filter(function(item) { return item.lines > 0 }).length }
function heading(analyzed, counted) {
    return "· " + (analyzed ? Studio.formatNumber(counted) + " tên trong phần này" : "chưa phân tích - tên hiện ra sau bước ấy")
}
var INTRO = "Nghe và sửa cách đọc tên; câu đã thu có tên ấy sẽ thu lại."
function noMatch(typed) { return "Không khớp “" + typed + "”; dùng “Thêm cách đọc” cho một từ khác." }
function moreNames(count) { return "Xem thêm " + Studio.formatNumber(count) + " tên" }
function unseenLine(count) { return Studio.formatNumber(count) + " tên khác của cuốn không có câu nào trong phần này." }

// Dòng nhỏ dưới tên: "12 câu · đã chọn" / "chưa phân tích tới" / cách đọc đang chờ áp
function rowStatus(item, analyzed, fresh, reach, shared) {
    let base
    if (fresh) base = reach ? reachSummary(reach) : "Không có trong danh sách - máy đọc theo chữ"
    else if (!analyzed && !item.lines) base = "chưa phân tích tới"
    else base = Studio.formatNumber(item.lines) + " câu · " + (item.never ? "máy không dùng được cách đọc này (ký hiệu)" : item.byListener ? "đã chọn" : item.spoken ? "máy đoán" : "chưa có trong sách")
    return base + (shared ? " · dùng chung" : "")
}
function waitingPart(item) { return item.requested ? " · chờ áp dụng: “" + item.requested + "”" : "" }
function editLabel(item, fresh) { return (fresh ? "Thêm" : "Sửa") + " cách đọc " + item.surface }
function sampleLabel(item) { return "Nghe câu có " + item.surface + ": " + item.example.text }
function addLabel(item, fresh) { return fresh ? "Đọc “" + item.surface + "”" : "Sửa" }

// ---- readingReach.ts ----
function where(reach) {
    const named = reach.chapters.slice(0, 3).map(function(chapter) { return chapter.title || "chương " + chapter.chapterId })
    const more = reach.chapters.length - named.length
    return named.length ? " · ở " + named.join(", ") + (more > 0 ? " và " + more + " chương nữa" : "") : ""
}
function neverText(surface) {
    return "Máy đọc ký hiệu trong “" + surface + "” thành một chỗ ngừng trước khi tra cách đọc, nên cách đọc cho chữ này không bao giờ được dùng. Muốn đọc khác, sửa “Chữ đem đọc” của từng câu có chữ ấy."
}
function reachSummary(reach, later) {
    if (reach.never) return (reach.lines ? "Có " + reach.lines + " câu có chữ này, nhưng m" : "M") + "áy không dùng được cách đọc cho chữ có ký hiệu này."
    if (!reach.lines) return "Chưa có câu nào có chữ này - cách đọc sẽ được dùng khi chữ xuất hiện."
    const cost = reach.recorded ? reach.recorded + " câu đã thu sẽ được thu lại" + (later ? " " + later : "") : "chưa thu câu nào nên không phải thu lại"
    const blocked = reach.blocked ? " (" + reach.blocked + " câu khác không dùng được vì ký hiệu)" : ""
    return reach.reached + " câu có chữ này · " + cost + where(reach) + blocked
}

// ---- Lưu một cách đọc (EditReading) ----
// Cách đọc đang lưu nếu chỉ khác hoa thường (không thành một thay đổi bắt thu lại các câu)
function asStored(item, text) {
    const lower = text.toLocaleLowerCase("vi")
    for (const saved of [item.requested, item.spoken]) if (saved && saved.toLocaleLowerCase("vi") === lower) return saved
    return text
}
function seenSpoken(item) { return item.requested !== null && item.requested !== undefined ? item.requested : (item.byListener ? item.spoken : "") }
function savedBack(item, everywhere) {
    return (item.requested ? "Trở lại cách đọc chờ áp trước đó: “" + Studio.shownReading(item.requested) + "”."
        : item.spoken ? "“" + item.surface + "” lại đọc là “" + Studio.shownReading(item.spoken) + "”."
        : "Đã bỏ cách đọc vừa thêm cho “" + item.surface + "”.") + (everywhere ? " Đã bỏ khỏi cách đọc chung." : "")
}
function savedToast(item, spokenForm) {
    return spokenForm === item.spoken ? "Giữ cách đọc “" + Studio.shownReading(spokenForm) + "”" : "Đã ghi: “" + item.surface + "” đọc là “" + spokenForm + "”"
}

// ---- Cách đọc chung (sharedReadings.tsx) ----
function sharedEntry(entries, surface, reading) {
    const key = String(surface).toLocaleLowerCase("vi")
    return (entries || []).find(function(entry) { return entry.surface.toLocaleLowerCase("vi") === key && (reading === undefined || reading === null || entry.spokenForm === reading) })
}
function offerLine(entries) {
    const shown = entries.slice(0, 3).map(function(entry) {
        return entry.current ? entry.surface + ": “" + Studio.shownReading(entry.current) + "” → “" + Studio.shownReading(entry.spokenForm) + "”" : entry.surface + " → “" + Studio.shownReading(entry.spokenForm) + "”"
    }).join(", ")
    return "Cách đọc chung khác cách cuốn này đang đọc: " + shown + (entries.length > 3 ? ", và " + (entries.length - 3) + " tên khác" : "")
}

// ---- PhoneEdits.tsx ----
function describePush(push) {
    const parts = []
    if (push.applied) parts.push(push.applied + " thay đổi đã áp")
    if (push.requests) parts.push(push.requests + " việc đã thành yêu cầu")
    if (push.waiting) parts.push(push.waiting + " việc đang chờ duyệt")
    if (push.skipped) parts.push(push.skipped + " không còn chỗ trong sách (bỏ qua)")
    return push.name + " · " + Studio.formatWhen(push.at) + ": " + (parts.join(", ") || "không có gì mới")
}
function applyNote(skipped, held, dropped) {
    const names = dropped || []
    const which = names.length ? ": " + names.slice(0, 3).join("; ") + (names.length > 3 ? "; và " + (names.length - 3) + " việc nữa" : "") : ""
    return [
        skipped ? skipped + " việc không còn khớp với sách nên bị bỏ qua" + which + "." : "",
        held ? held + " việc máy này đã đổi khác sau đó vẫn chờ bạn chọn từng việc." : ""
    ].filter(Boolean).join(" ")
}
function inboxHeading(waiting) { return "Yêu cầu thiết bị" + (waiting ? " (" + waiting + " việc chờ duyệt)" : "") }
function skippedCount(devices) { return (devices || []).reduce(function(sum, device) { return sum + device.items.length }, 0) }
// Biểu tượng của một việc từ điện thoại (KIND_ICON của ApplyChanges.tsx; "alias" = nối hai tên)
var KIND_ICON = {pronunciation: "book-open-check", speaker: "user-round", line: "audio-lines", voice: "mic-vocal", retake: "refresh-cw", alias: "link-2"}
function kindIcon(kind) { return KIND_ICON[kind] || "check" }
