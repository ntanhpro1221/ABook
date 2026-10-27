.pragma library

// Thư viện của máy tính đang xem qua cầu nối (GET /api/peers/<máy>/studio/api/listen/library): cùng cách đọc mỗi cuốn với LibraryModel::setBooks
// (src/librarymodel.cpp) để ô sách của hai thư viện giống hệt nhau. Bìa đi qua cầu nối của máy chủ máy này: khoá "peer~<máy>~<mã>/<phiên bản>"
// (CoverProvider đổi thành /api/peers/<máy>/studio/media/books/<mã>/cover).

/** "45 phút", "2 giờ", "1 giờ 5 phút"; "" khi chưa có (LibraryModel::durationText). */
function durationText(seconds) {
    var minutes = Math.round((seconds || 0) / 60);
    if (minutes <= 0) return "";
    var h = Math.floor(minutes / 60), m = minutes % 60;
    if (h === 0) return m + " phút";
    return m === 0 ? h + " giờ" : h + " giờ " + m + " phút";
}

function book(item, peer) {
    var progress = item.progress || {};
    var producing = Boolean(item.producing);
    var detail = producing ? "Đang làm · " + (item.chaptersAvailable || 0) + "/" + (item.chaptersTotal || 0) + " chương" : durationText(item.duration);
    var author = item.author || "";
    var cover = item.cover && typeof item.cover === "object" ? item.cover : null;
    return {
        bookId: item.id,
        title: item.title || "",
        author: author,
        subtitle: producing || !author ? detail : author,
        narrator: item.narrator || "",
        detail: detail,
        coverKey: cover ? "peer~" + peer + "~" + item.id + "/" + (cover.version || 0) : "",
        progress: progress.finished ? 1 : (progress.fraction || 0),
        source: item.remote && typeof item.remote === "object" ? (item.remote.computer || "") : "",
        chapters: item.chaptersTotal || 0,
        lastChapter: item.lastChapterTitle || "",
        producing: producing,
        peer: peer
    };
}

/** Các cuốn của lời đáp (`{books: [...]}` hay mảng), bỏ cuốn không có mã. */
function books(data, peer) {
    var list = Array.isArray(data) ? data : (data && Array.isArray(data.books) ? data.books : []);
    return list.filter(function(item) { return item && item.id }).map(function(item) { return book(item, peer) });
}
