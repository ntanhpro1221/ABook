.import "UiStrings.js" as S
.pragma library
.import "CastLogic.js" as Cast

// Hàm thuần của phần đầu trang sách (listen/BookScreen.tsx, labels.ts, LibraryScreen.tsx bookStatusText): dòng tình trạng dưới tên, dòng dưới thanh
// tiến độ, nhãn "Đọc" / "Đọc tiếp". `book` là lời đáp GET /api/listen/books/<id>. Chữ giữ đúng từng chữ của bản web.

function formatLength(seconds) { return Cast.formatLength(seconds) }
// Như formatLength nhưng làm tròn LÊN tới phút (thời gian còn lại).
function formatLengthUp(seconds) {
    if (!isFinite(seconds) || seconds <= 0) return S.s_0_phut_66a3b36a
    return Cast.formatLength(Math.ceil(seconds / 60) * 60)
}

// Các cụm của dòng phụ trang sách: chi tiết (đã nối " · " ở librarymodel.cpp) + số chương; mỗi cụm một khối không gãy trong Flow của BookPage.
function metaParts(detail, chapters) {
    return String(detail || "").split(/\s·\s/).concat(chapters ? [chapters] : []).filter(function(part) { return part !== "" })
}

function progressOf(book) { return book && book.progress && typeof book.progress === "object" ? book.progress : {} }

function textBookLine(speaks) { return speaks ? S.s_chi_co_chu_u00a0_u00a0nghe_bang_giong_doc_9734cee8 : S.s_chi_co_chu_u00a0_u00a0may_nay_chua_co_gion_3f3880c2 }

// Tên máy đang giữ cuốn nghe thẳng: tên máy tính đã ghép, "máy khác" khi chưa biết tên, "máy tính" khi chỉ biết là của máy tính.
function remoteName(book) { return typeof book.remote === "object" && book.remote ? book.remote.computer || S.s_may_khac_95db1846 : S.s_may_tinh_8eafc226 }
function remotePlace(book) { return S.s_tren_54f68805 + remoteName(book) }
function remoteUnfinishedLine(book) {
    const name = remoteName(book)
    return name.charAt(0).toUpperCase() + name.slice(1) + S.s_con_dang_lam_chuong_moi_hien_o_day_khi_xon_f1c5da10
}

function progressText(book, speaks) {
    if (book.stage === "text") {
        const lead = String(book.author || "").trim() || (speaks ? "" : S.s_chi_co_chu_bf879f2c)
        return (lead ? lead + "\u00a0·\u00a0" : "") + book.chaptersTotal + S.s_chuong_9e6a01dc
    }
    const p = progressOf(book)
    const chapters = book.chaptersAvailable + "/" + book.chaptersTotal + S.s_chuong_9e6a01dc
    if (p.finished) return S.s_da_nghe_xong_d276b702
    if (p.caughtUp) return S.s_da_nghe_het_phan_da_co_u00a0_u00a0_0cb260be + chapters
    if (!book.complete) return book.producing ? chapters + S.s_u00a0_u00a0dang_thu_93138236 : chapters
    const heard = Number(p.heardSeconds || 0)
    const left = Math.max(0, Number(book.duration || 0) - heard)
    if (heard <= 0) return formatLength(book.duration)
    return S.s_con_71d0e2b2 + formatLengthUp(left / (book.state && book.state.rate ? book.state.rate : 1))
}

function bookStatusText(book, speaks) {
    const status = progressText(book, Boolean(speaks))
    return book.remote ? remotePlace(book) + "\u00a0·\u00a0" + status : status
}

// Dòng tình trạng ngay dưới tên: sách chỉ có chữ, hay sách chưa đủ chương (đang thu / máy khác còn làm / file cũ / dừng thu); "" khi đủ chương.
function statusLine(book, speaks) {
    if (book.stage === "text") return textBookLine(speaks)
    if (book.complete || book.id === undefined) return ""
    if (book.producing) return S.s_dang_thu_chuong_moi_tu_hien_khi_xong_123d0db2
    if (book.remote) return remoteUnfinishedLine(book)
    if (book.imported) return S.s_chua_du_chuong_mo_file_sach_moi_hon_de_ngh_ca290cd2
    return S.s_chua_du_chuong_dang_dung_thu_3653bcf7
}

// Một dòng dưới thanh tiến độ. "còn" tính theo phần ĐÃ PHỦ - nói rõ "chưa nghe" để khỏi lẫn với "còn X" theo vị trí ở màn Đang nghe.
function progressLine(book, listening, failed) {
    const p = progressOf(book)
    if (p.finished || p.caughtUp) return bookStatusText(book)
    const heard = Number(p.heardSeconds || 0)
    if (heard > 0) return S.s_da_nghe_52f8acbb + formatLength(heard) + S.s_u00a0_u00a0con_14802631 + formatLength(Math.max(0, Number(book.duration || 0) - heard)) + S.s_chua_nghe_39f63ea8
    if (listening) return failed ? S.s_chua_phat_duoc_3ecb850e : S.s_dang_nghe_9310d8cf
    return S.s_chua_nghe_2fbea4c8
}

// Chỗ đọc đã lưu, nếu chương ấy còn trong sách (readingPosition.ts latestReading - bản máy tính chỉ có chỗ đọc đã lưu ở máy chủ).
function latestReading(book) {
    const saved = book && book.state ? book.state.reading : null
    return saved && (book.chapters || []).some(c => c.id === saved.chapterId) ? saved : null
}

function readLabel(book, listening) { return listening ? S.s_doc_5709880c : latestReading(book) ? S.s_doc_tiep_633d731b : S.s_doc_5709880c }
