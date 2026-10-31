.pragma library
.import "CastLogic.js" as Cast

// Hàm thuần của phần đầu trang sách (listen/BookScreen.tsx, labels.ts, LibraryScreen.tsx bookStatusText): dòng tình trạng dưới tên, dòng dưới thanh
// tiến độ, nhãn "Đọc" / "Đọc tiếp". `book` là lời đáp GET /api/listen/books/<id>. Chữ giữ đúng từng chữ của bản web.

function formatLength(seconds) { return Cast.formatLength(seconds) }
// Như formatLength nhưng làm tròn LÊN tới phút (thời gian còn lại).
function formatLengthUp(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return "0 phút"
    return Cast.formatLength(Math.ceil(seconds / 60) * 60)
}

function progressOf(book) { return book && book.progress && typeof book.progress === "object" ? book.progress : {} }

function textBookLine(speaks) { return speaks ? "Chỉ có chữ · nghe bằng giọng đọc" : "Chỉ có chữ · máy này chưa có giọng đọc" }

// Tên máy đang giữ cuốn nghe thẳng: tên máy tính đã ghép, "máy khác" khi chưa biết tên, "máy tính" khi chỉ biết là của máy tính.
function remoteName(book) { return typeof book.remote === "object" && book.remote ? book.remote.computer || "máy khác" : "máy tính" }
function remotePlace(book) { return "Trên " + remoteName(book) }
function remoteUnfinishedLine(book) {
    const name = remoteName(book)
    return name.charAt(0).toUpperCase() + name.slice(1) + " còn đang làm, chương mới hiện ở đây khi xong"
}

function progressText(book, speaks) {
    if (book.stage === "text") {
        const lead = String(book.author || "").trim() || (speaks ? "" : "Chỉ có chữ")
        return (lead ? lead + " · " : "") + book.chaptersTotal + " chương"
    }
    const p = progressOf(book)
    const chapters = book.chaptersAvailable + "/" + book.chaptersTotal + " chương"
    if (p.finished) return "Đã nghe xong"
    if (p.caughtUp) return "Đã nghe hết phần đã có · " + chapters
    if (!book.complete) return book.producing ? chapters + " · đang thu" : chapters
    const heard = Number(p.heardSeconds || 0)
    const left = Math.max(0, Number(book.duration || 0) - heard)
    if (heard <= 0) return formatLength(book.duration)
    return "Còn " + formatLengthUp(left / (book.state && book.state.rate ? book.state.rate : 1))
}

function bookStatusText(book, speaks) {
    const status = progressText(book, Boolean(speaks))
    return book.remote ? remotePlace(book) + " · " + status : status
}

// Dòng tình trạng ngay dưới tên: sách chỉ có chữ, hay sách chưa đủ chương (đang thu / máy khác còn làm / file cũ / dừng thu); "" khi đủ chương.
function statusLine(book, speaks) {
    if (book.stage === "text") return textBookLine(speaks)
    if (book.complete || book.id === undefined) return ""
    if (book.producing) return "Đang thu; chương mới tự hiện khi xong."
    if (book.remote) return remoteUnfinishedLine(book)
    if (book.imported) return "Chưa đủ chương; mở file sách mới hơn để nghe tiếp."
    return "Chưa đủ chương; đang dừng thu."
}

// Một dòng dưới thanh tiến độ. "còn" tính theo phần ĐÃ PHỦ - nói rõ "chưa nghe" để khỏi lẫn với "còn X" theo vị trí ở màn Đang nghe.
function progressLine(book, listening, failed) {
    const p = progressOf(book)
    if (p.finished || p.caughtUp) return bookStatusText(book)
    const heard = Number(p.heardSeconds || 0)
    if (heard > 0) return "Đã nghe " + formatLength(heard) + " · còn " + formatLength(Math.max(0, Number(book.duration || 0) - heard)) + " chưa nghe"
    if (listening) return failed ? "Chưa phát được" : "Đang nghe"
    return "Chưa nghe"
}

// Chỗ đọc đã lưu, nếu chương ấy còn trong sách (readingPosition.ts latestReading - bản máy tính chỉ có chỗ đọc đã lưu ở máy chủ).
function latestReading(book) {
    const saved = book && book.state ? book.state.reading : null
    return saved && (book.chapters || []).some(c => c.id === saved.chapterId) ? saved : null
}

function readLabel(book, listening) { return listening ? "Đọc" : latestReading(book) ? "Đọc tiếp" : "Đọc" }
