.pragma library

// Luật thuần của màn đọc "Đọc chương này": chép ui/src/listen/labels.ts (readerHint, chapterOpenProblem), listen/readingPosition.ts
// (phiên bản chỗ đọc, chỗ đọc mới hơn, bản dự phòng trên máy) và listen/follow.ts (chapterToFollow). Chữ y như bản web.

var SIZES = [16, 18, 20, 22, 24];
var LEADINGS = [1.5, 1.7, 1.9];
var MAX_LISTENING_COUNTER = Math.pow(2, 40);
/** Chỗ đang đọc theo hồ sơ trên máy này: `<mã sách>#<mã hồ sơ>` (BOOK_STORAGE.reading). */
var READING_PREFIX = "abook-reading-";

/** "1,5" như toLocaleString("vi-VN"). */
function leadingLabel(value) { return String(value).replace(".", ",") }

/** Lời nhắc ở đầu màn đọc (null: không nhắc). Bản máy tính Qt chưa có giọng đọc to (canSpeak luôn false) và chưa sửa câu / cách đọc. */
function readerHint(state) {
    var verb = state.coarse ? "Chạm" : "Bấm";
    if (state.textOnly) {
        if (!state.canSpeak) return "Máy này chưa có giọng đọc.";
        var readingText = state.readings ? " " + (state.coarse ? "Giữ chữ" : "Bấm chuột phải vào chữ") + " để sửa cách đọc." : "";
        return state.tapped ? "Nghe bằng giọng đọc." + readingText : verb + " chữ để nghe từ đó." + readingText;
    }
    if (!state.timed) return "Chưa có audio; bạn vẫn đọc được chữ.";
    if (state.tapped) return null;
    var reading = state.readings ? " " + (state.coarse ? "Giữ chữ" : "Bấm chuột phải vào chữ") + " để sửa cách đọc." : "";
    return verb + " chữ để nghe từ đó." + (state.wish ? " “Sửa câu này”: đổi người nói, cách đọc hoặc thu lại." : "") + reading;
}

/** Lời dưới "Không mở được chương này": máy giữ sách không trả lời (503 có lời) thì nói đúng lời ấy. */
function chapterOpenProblem(status, message) {
    return status === 503 && message ? message.replace(/\.$/, "") + "." : "Chương có thể không còn trong sách.";
}

/** Giọng vừa sang chương `after`: màn đọc đang mở đúng chương `before` thì đi theo sang `after`; mở chương khác thì để yên (null). */
function chapterToFollow(before, after, shown) {
    return before !== null && after !== null && before !== after && before === shown ? after : null;
}

// ---- phiên bản chỗ đọc (readingPosition.ts) ----

function validEpoch(value) { return typeof value === "string" && /^1*$/.test(value) }

function validClock(value) {
    return typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= MAX_LISTENING_COUNTER ? value : 0;
}

function validRevision(value) {
    if (!value || typeof value !== "object") return false;
    return Number.isInteger(value.counter) && value.counter > 0 && value.counter <= MAX_LISTENING_COUNTER
        && typeof value.node === "string" && /^[A-Za-z0-9_-]{1,64}$/.test(value.node)
        && (value.epoch === undefined || validEpoch(value.epoch));
}

function newerReading(a, b) {
    var left = validRevision(a.rev) ? a.rev : { counter: 0, node: "" };
    var right = validRevision(b.rev) ? b.rev : { counter: 0, node: "" };
    if (left.counter || right.counter) {
        var le = left.epoch || "", re = right.epoch || "";
        return le > re || le === re && (left.counter > right.counter || left.counter === right.counter && left.node > right.node);
    }
    return a.at > b.at;
}

/** Mã máy cho phiên bản chỗ đọc: một lần mỗi phiên (crypto.randomUUID không gạch của web). */
var readingNode = "";
function node() {
    if (!readingNode) {
        var hex = "0123456789abcdef";
        for (var i = 0; i < 32; ++i) readingNode += hex[Math.floor(Math.random() * 16)];
    }
    return readingNode;
}

function nextReadingRevision(book, local) {
    var state = book && book.state || {};
    var revisions = [state.reading && state.reading.rev, state.last && state.last.rev, local && local.rev].filter(validRevision);
    var epochs = [state._epoch].concat(revisions.map(function(rev) { return rev.epoch || "" })).filter(validEpoch).sort();
    var epoch = epochs.length ? epochs[epochs.length - 1] : "";
    var counts = revisions.filter(function(rev) { return (rev.epoch || "") === epoch }).map(function(rev) { return rev.counter });
    var counter = Math.max.apply(null, [epoch === (state._epoch || "") ? validClock(state._clock) : 0].concat(counts, [0])) + 1;
    if (counter > MAX_LISTENING_COUNTER) { epoch += "1"; counter = 1 }
    var rev = { counter: counter, node: node() };
    if (epoch) rev.epoch = epoch;
    return rev;
}

/** Hồ sơ nghe đang dùng ("default" khi cuốn không có hồ sơ). */
function readingRecord(book) {
    var records = book && book.records || [];
    for (var i = 0; i < records.length; ++i) if (records[i].active) return records[i].id;
    return "default";
}

function readingKey(bookId, record) { return READING_PREFIX + bookId + "#" + record }

/** Bản dự phòng trên máy (chuỗi JSON đã lưu) nếu hợp lệ. */
function parseLocal(raw) {
    try {
        var value = JSON.parse(raw || "null");
        if (value && Number.isInteger(value.chapterId) && Number.isInteger(value.index) && value.index >= 0 && isFinite(value.at)) {
            if (!validRevision(value.rev)) delete value.rev;
            return value;
        }
    } catch (error) { /* hỏng thì như không có */ }
    return undefined;
}

/** Chỗ đọc mới nhất giữa bản trên máy và bản của hồ sơ; chỉ khi chương ấy còn trong sách. */
function latestReading(book, local) {
    if (!book) return undefined;
    var saved = book.state && book.state.reading;
    if (local && local.pending && !local.rev) local.rev = nextReadingRevision(book, local);
    var latest = local && (!saved || newerReading(local, saved)) ? local : saved;
    var chapters = book.chapters || [];
    for (var i = 0; latest && i < chapters.length; ++i) if (chapters[i].id === latest.chapterId) return latest;
    return undefined;
}

/** Bản trên máy khớp đúng phiên bản vừa lưu (ACK chỉ xác nhận đúng phiên bản, không xoá chỗ mới vừa cuộn tới). */
function sameVersion(local, place) {
    if (!local) return false;
    if (place.rev) return Boolean(local.rev) && local.rev.counter === place.rev.counter && local.rev.node === place.rev.node
        && (local.rev.epoch || "") === (place.rev.epoch || "");
    return local.at === place.at;
}
