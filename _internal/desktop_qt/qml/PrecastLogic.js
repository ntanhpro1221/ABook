.pragma library
.import "WorkLogic.js" as W
.import "CastLogic.js" as Cast

// "Duyệt trước khi thu" (studio/precast.ts, PrecastReview.tsx; webui/precast.py, docs/STUDIO_REVIEW.md): phân tích xong, trước khi thu những chương đầu - lúc sửa còn miễn phí.
// Phần này chỉ chọn, đếm và nói chữ - không gì ở đây sửa chữ truyện. Chữ chép từng chữ của bản web.

var STEPS = ["cast", "names", "lines", "done"]
// Những người nói nhiều nhất: giọng của họ nghe suốt cuốn
var TOP_PEOPLE = 6
var CAST_KINDS = ["gender", "alias", "shared-voice"]
var LINE_KINDS = ["speaker", "turn", "vocative", "bracket", "unnamed"]
var TITLE = {cast: "Nhân vật và giọng", names: "Cách đọc tên", lines: "Ai nói câu này", done: "Xong"}
var ICON = {cast: "users", names: "spell-check", lines: "message-square-quote", done: "clipboard-check"}

function stepOf(value) { return STEPS.indexOf(value) >= 0 ? value : "cast" }

function openItems(items) { return (items || []).filter(W.isOpenWork) }
// (a) Việc về người và giọng: nam hay nữ, một người hai tên, hai người chung giọng. Giữ thứ tự lợi / lần bấm của hộp việc.
function castItems(items) { return openItems(items).filter(function(item) { return CAST_KINDS.indexOf(item.kind) >= 0 }) }
// (b) Cách đọc tên máy tự đoán - tên máy kém chắc nhất trước, cùng mức thì tên gặp nhiều câu hơn trước
function nameItems(items) {
    return openItems(items).filter(function(item) { return item.kind === "pronunciation" })
        .sort(function(a, b) { return (b.doubt - a.doubt) || (b.affected - a.affected) })
}
// (c) "Ai nói câu này" kém chắc ở các chương sắp thu - thu xong chương ấy thì sửa phải thu lại
function lineItems(items, upcoming) {
    return openItems(items).filter(function(item) {
        return LINE_KINDS.indexOf(item.kind) >= 0 && (item.chapters || []).some(function(id) { return upcoming.indexOf(id) >= 0 })
    })
}
function upcomingIds(view) { return view && view.upcoming ? view.upcoming.map(function(chapter) { return chapter.id }) : [] }
// Khoá các thẻ việc nằm trong màn duyệt: {khoá: true}. Tab "Duyệt trước khi thu" đếm chúng, "Việc cần duyệt" đếm phần còn lại.
function keys(items, upcoming) {
    const out = {}
    for (const list of [castItems(items), nameItems(items), lineItems(items, upcoming)]) for (const item of list) out[item.key] = true
    return out
}
function keyCount(map) { return map ? Object.keys(map).length : 0 }
function lineCount(items) { return items.reduce(function(total, item) { return total + item.affected }, 0) }

// Chapter range uses the same arrow as the web; app fonts supply the glyph.
function chapterRange(chapters) {
    if (!chapters || !chapters.length) return ""
    const first = chapters[0].title, last = chapters[chapters.length - 1].title
    return chapters.length === 1 ? first : first + " → " + last
}
// Sửa tới đâu thì miễn phí
function freeNote(view) {
    return view && view.recordedThrough
        ? "Đã thu tới " + view.recordedThrough.title + " - sửa ở chương sau đó không phải thu lại; sửa chỗ đã thu thì máy thu lại đúng các câu ấy."
        : "Chưa thu chương nào - sửa bây giờ không phải thu lại câu nào."
}

// ---- chữ của màn ----
function stepCounts(castCards, nameCards, lineCards, people) {
    return {
        cast: castCards.length ? castCards.length + " việc" : people + " người",
        names: nameCards.length ? nameCards.length + " tên" : "ổn",
        lines: lineCards.length ? lineCount(lineCards) + " câu" : "ổn",
        done: ""
    }
}
function castIntro(people) { return "Nghe và chỉnh giọng cho " + people + " nhân vật nói nhiều nhất." }
function doubtLine(count) { return "· " + count + " việc về người và giọng" }
function namesIntro(count) {
    return count ? "Nghe và sửa " + count + " cách đọc tên, tên kém chắc ở trên." : "Xem và sửa cách đọc từng tên ở danh sách dưới."
}
function linesIntro(lineCards, view, range) {
    const head = lineCards.length
        ? Cast.formatNumber(lineCount(lineCards)) + " câu máy chưa chắc ai nói ở " + (range || "những chương sắp thu") + " - các chương thu đầu tiên;"
        : view.upcoming.length ? "Không có câu nghi ngờ ở " + range : "Đã thu mọi chương"
    return head + " các chương sau xem ở Việc cần duyệt."
}
function doneText(book) {
    return book.precast && book.precast.held ? "Đã ghi lại. Bấm “Thu âm” để làm tiếp."
        : book.running ? "Sửa nào cũng đã ghi lại; máy áp ở chương kế tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."
        : "Sửa nào cũng đã ghi lại; máy áp khi sách chạy tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."
}
var HELD_NOTE = "Sách đang chờ bạn duyệt - duyệt xong bấm “Thu âm” ở đầu trang."
var INTRO = "Duyệt nhanh trước khi thu; có thể bỏ qua từng bước."
var TWIN_NOTE = "Cùng tên với người khác trong sách - một người?"
var NOT_READY = "Màn duyệt mở được khi máy đã phân tích xong và phân vai."

// Công tắc "Duyệt trước khi thu"
function waitHint(book) {
    const precast = book.precast || {}
    return precast.announcedAt ? "Phân tích đã xong. Muốn dừng thì bấm “Tạm dừng”."
        : precast.wait ? "Dừng sau phân tích để bạn duyệt, rồi bấm “Thu âm”."
        : "Phân tích xong thì thu luôn; duyệt lúc nào cũng được."
}

// Dải mời trên trang dự án
function bannerTitle(held) { return held ? "Phân tích xong - sách đang chờ bạn duyệt" : "Phân tích xong - duyệt trước khi thu?" }
var BANNER_TEXT = "Duyệt giọng, tên và người nói trước để tránh thu lại."
// Dải mời hiện khi: phân tích xong, đang không ở màn duyệt, và sách đang chờ duyệt hay chưa thu xong chương nào
function bannerShown(book, tab) {
    return Boolean(book.precast && book.precast.ready) && book.phase !== "done" && tab !== "precast"
        && (Boolean(book.precast.held) || book.chapters.completed === 0)
}
