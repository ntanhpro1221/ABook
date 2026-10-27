.pragma library

// Bảng dự án Studio (studio/ProjectsScreen.tsx): chữ và cách tính của mỗi hàng, đúng từng chữ với bản web.
// Nguồn: studio/data.ts (phaseTone, queueLabel, projectStatus), shared/format.ts (formatLength, formatEta, etaOf, formatPercent,
// formatRelative), listen/model.ts (seriesOf, seriesIndex), studio/projectGroups.ts (groupParts, splitLive).

function phaseTone(phase, running) {
    if (phase === "done") return "success";
    if (phase === "error") return "danger";
    if (running) return "accent";
    // Làm dở mà không chạy: cần người dùng để ý (bấm Tiếp tục) - không phải trạng thái trung tính.
    if (phase === "analysis" || phase === "casting" || phase === "synthesis" || phase === "stopped") return "warning";
    return "muted";
}

/** Chỗ trong hàng chờ nói bằng "còn mấy việc trước". `position` đếm từ 1. */
function queueLabel(position) {
    return position <= 1 ? "Sắp tới lượt" : "Còn " + (position - 1) + " việc trước";
}

/** Nhãn + màu + "đang chạy" của trạng thái một dự án. */
function projectStatus(book) {
    var running = Boolean(book.running || book.starting);
    return {
        label: book.queuePosition ? queueLabel(book.queuePosition) : book.starting ? "Đang khởi động" : book.precast && book.precast.held ? "Chờ bạn duyệt" : (book.statusLabel || ""),
        tone: book.queuePosition || book.paused || book.stopping ? "warning" : phaseTone(book.phase, running),
        live: running && !book.paused && !book.stopping
    };
}

/** Thời lượng cho con người: "45 phút", "9 giờ 12 phút", "2 giờ". */
function formatLength(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return "0 phút";
    var minutes = Math.round(seconds / 60);
    if (minutes < 1) return "dưới 1 phút";
    var hours = Math.floor(minutes / 60), rest = minutes % 60;
    if (!hours) return minutes + " phút";
    return rest ? hours + " giờ " + rest + " phút" : hours + " giờ";
}

/** Từ mức này của bước đang làm thì "còn dưới 2 phút" mới là "sắp xong". */
var NEAR_DONE = 0.85;

function formatEta(seconds, fraction) {
    if (seconds < 90) return fraction === undefined || fraction >= NEAR_DONE ? "sắp xong" : "còn dưới 2 phút";
    return "còn khoảng " + formatLength(seconds);
}

/** Thời gian còn lại của một cuốn đang chạy, theo bước máy đang ước, hoặc null khi chưa có tốc độ để ước. */
function etaOf(book, short) {
    if (!book.eta) return null;
    function say(step, left) { return short ? step + " " + left.replace(/^còn khoảng /, "còn ") : "pha " + step + " " + left }
    if (book.eta.phase === "speaker") {
        var pass = book.speakerPass;
        return say(short ? "dò người nói" : "xác định người nói", formatEta(book.eta.seconds, pass && pass.total ? pass.done / pass.total : undefined));
    }
    var synthesis = book.eta.phase === "synthesis";
    var progress = book.progress || {};
    var left = formatEta(book.eta.seconds, synthesis ? progress.synthesis : progress.analysis);
    return say(synthesis ? "thu âm" : "phân tích", left);
}

function formatPercent(fraction) {
    var value = Math.max(0, Math.min(1, fraction || 0)) * 100;
    if (value > 0 && value < 1) return "<1%";
    if (value < 100 && value > 99) return "99%";
    return Math.floor(value) + "%";
}

/** Ngày kiểu vi-VN của toLocaleDateString (day numeric, month numeric, year numeric): "7/10/2026". */
function formatDate(epochSeconds) {
    var date = new Date(epochSeconds * 1000);
    return date.getDate() + "/" + (date.getMonth() + 1) + "/" + date.getFullYear();
}

function formatRelative(epochSeconds, nowMs) {
    if (!epochSeconds) return "";
    var delta = (nowMs === undefined ? Date.now() : nowMs) / 1000 - epochSeconds;
    if (delta < 60) return "vừa xong";
    if (delta < 3600) return Math.floor(delta / 60) + " phút trước";
    if (delta < 86400) return Math.floor(delta / 3600) + " giờ trước";
    var days = Math.floor(delta / 86400);
    if (days === 1) return "hôm qua";
    if (days < 7) return days + " ngày trước";
    return formatDate(epochSeconds);
}

/** Bộ và số tập từ tên sách. */
function seriesOf(title) {
    var match = String(title).match(/^(.*?)\s*[·|:—–-]\s*(Tập|Quyển|Phần|Vol\.?|Book)\s*(\d+)\b/i);
    if (!match) return {key: "title:" + String(title).trim(), series: String(title).trim(), volume: null, unit: "tập"};
    var word = match[2].toLowerCase();
    var series = match[1].trim();
    return {key: "title:" + series, series: series, volume: Number(match[3]), unit: word === "quyển" || word === "phần" ? word : "tập"};
}

/** Bộ và số tập của mọi cuốn (mã -> chỗ), như seriesIndex của listen/model.ts. */
function seriesIndex(books) {
    var titles = {}, places = {}, i, book, id;
    for (i = 0; i < books.length; ++i) titles[books[i].id] = books[i].title;
    for (i = 0; i < books.length; ++i) {
        book = books[i];
        if (!book.series) continue;
        var rootTitle = titles.hasOwnProperty(book.series.root) ? titles[book.series.root] : book.title;
        places[book.id] = {key: "chain:" + book.series.root, series: seriesOf(rootTitle).series, volume: book.series.part, unit: "phần"};
    }
    // Phần đầu không mang `series` (máy chủ chỉ gắn cho phần nối tiếp): nó là sách mà phần khác trỏ về.
    var roots = {};
    for (i = 0; i < books.length; ++i) if (books[i].series) roots[books[i].series.root] = true;
    for (i = 0; i < books.length; ++i) {
        book = books[i];
        if (!places.hasOwnProperty(book.id) && roots[book.id]) places[book.id] = {key: "chain:" + book.id, series: seriesOf(book.title).series, volume: 1, unit: "phần"};
    }
    var byTitle = [], units = {}, stages = {};
    for (i = 0; i < books.length; ++i) {
        stages[books[i].id] = books[i].stage;
        if (!places.hasOwnProperty(books[i].id)) byTitle.push({id: books[i].id, place: seriesOf(books[i].title)});
    }
    for (i = 0; i < byTitle.length; ++i) {
        var p = byTitle[i].place;
        if (p.volume !== null && !units.hasOwnProperty(p.key)) units[p.key] = p.unit;
    }
    // Ứng viên tập 1 của mỗi bộ: các cuốn không số mà bộ có tập đánh số; chọn trong số cuốn nghe được trước, chỉ-chữ sau.
    var candidates = {}, order = [];
    for (i = 0; i < byTitle.length; ++i) {
        var c = byTitle[i].place;
        if (c.volume === null && units.hasOwnProperty(c.key)) {
            if (!candidates.hasOwnProperty(c.key)) { candidates[c.key] = []; order.push(c.key) }
            candidates[c.key].push(byTitle[i].id);
        }
    }
    var first = {};
    for (i = 0; i < order.length; ++i) {
        var ids = candidates[order[i]];
        var heard = ids.filter(function(x) { return stages[x] !== "text" });
        var pool = heard.length ? heard : ids;
        if (pool.length === 1) first[pool[0]] = true;
    }
    for (i = 0; i < byTitle.length; ++i) {
        id = byTitle[i].id;
        var place = byTitle[i].place;
        places[id] = first[id] ? {key: place.key, series: place.series, volume: 1, unit: units[place.key]} : place;
    }
    return places;
}

/** Các phần của một cuốn đứng chung một nhóm, theo thứ tự phần, ở chỗ của phần mới nhất; dự án lẻ giữ nguyên thứ tự. */
function groupParts(books) {
    var places = seriesIndex(books), members = {}, i, book, place;
    for (i = 0; i < books.length; ++i) {
        place = places[books[i].id];
        if (place && place.volume !== null && place.volume !== undefined) (members[place.key] = members[place.key] || []).push(books[i]);
    }
    var entries = [], shown = {};
    for (i = 0; i < books.length; ++i) {
        book = books[i];
        place = places[book.id];
        var group = place && place.volume !== null && place.volume !== undefined ? members[place.key] : undefined;
        if (!place || !group || group.length < 2) { entries.push({kind: "book", book: book}); continue }
        if (shown[place.key]) continue;
        shown[place.key] = true;
        var ordered = group.slice().sort(function(a, b) { return (places[a.id].volume || 0) - (places[b.id].volume || 0) });
        entries.push({kind: "series", name: place.series, unit: place.unit, books: ordered});
    }
    return entries;
}

function entryBooks(entry) { return entry.kind === "book" ? [entry.book] : entry.books }
function isLive(book) { return Boolean(book.running || book.starting) }

/** Nhóm có cuốn đang chạy lên đầu (cả nhóm), rồi phần còn lại - thứ tự bảng của web. */
function ordered(books) {
    var entries = groupParts(books || []);
    var live = entries.filter(function(entry) { return entryBooks(entry).some(isLive) });
    return live.concat(entries.filter(function(entry) { return live.indexOf(entry) < 0 }));
}

function entryKey(entry) { return entry.kind === "book" ? entry.book.id : "series:" + entry.name }

/** Dòng phụ dưới tên (DotJoin): giọng kể, và chất lượng khi khác "Cân bằng". */
function subLine(book) {
    var settings = book.settings || {};
    return [settings.narrator ? "Giọng kể " + settings.narrator : "", settings.profile !== "balanced" ? settings.profileLabel : ""].filter(Boolean).join(" · ");
}

/** Chữ của ô tiến độ: thời gian còn lại khi đang chạy, không thì "xong/tổng chương". */
function detail(book) {
    var live = isLive(book), chapters = book.chapters || {};
    return book.phase !== "done" && book.eta && live ? etaOf(book, true) : (chapters.completed || 0) + "/" + (chapters.total || 0) + " chương";
}

/** Việc còn của mình ở sách "Hoàn tất". */
function needs(book) {
    var chapters = book.chapters || {};
    return [
        book.pendingChanges ? book.pendingChanges + " thay đổi chờ áp" : book.phase === "done" && chapters.redo ? chapters.redo + " chương chờ thu lại" : "",
        chapters.missingAudio ? chapters.missingAudio + " chương mất audio" : ""
    ].filter(Boolean);
}

/** Bìa của một dự án ở máy đang xem (cầu nối): khoá CoverProvider "peer~<máy>~<mã>/<phiên bản>", "" = bìa vẽ từ tên. */
function coverKey(book, peer) {
    var cover = book.cover && typeof book.cover === "object" ? book.cover : null;
    return cover && peer ? "peer~" + peer + "~" + book.id + "/" + (cover.version || 0) : "";
}
