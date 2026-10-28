.pragma library

function books() {
    return [
        {id: "width", bookId: "width", title: "Miền đất · Tập 1", author: "Đặng An", subtitle: "Đặng An", narrator: "Đức Trí", chaptersTotal: 3, chaptersAvailable: 2, duration: 200, complete: false, producing: true,
            progress: 0.3, listeningProgress: {fraction: 0.3, heardSeconds: 60, totalSeconds: 200}, state: {last: {at: 1793000000, chapterId: 1, seconds: 40}}, lastChapter: "Chương 1 · Lên đường"},
        {id: "next", bookId: "next", title: "Miền đất · Tập 2", author: "Đặng An", subtitle: "Đặng An", chaptersTotal: 3, chaptersAvailable: 3, duration: 300, complete: true, progress: 0, listeningProgress: {}},
        {id: "fresh", bookId: "fresh", title: "Những ngày bình yên", author: "Nguyễn Bình", subtitle: "Nguyễn Bình · 2 chương", stage: "text", chaptersTotal: 2, chaptersAvailable: 0, progress: 0, listeningProgress: {}},
        {id: "finished", bookId: "finished", title: "Con đường bên sông", author: "Người kể chuyện", subtitle: "Đã nghe xong", chaptersAvailable: 2, duration: 300, complete: true, progress: 1, listeningProgress: {finished: true, heardSeconds: 300, totalSeconds: 300}},
        {id: "remote", bookId: "remote", title: "Chuyện kể đêm mưa", subtitle: "4 giờ · 12 chương", source: "Máy của bạn", remote: {computer: "Máy của bạn"}, progress: 0, chaptersAvailable: 12, listeningProgress: {}}
    ]
}
function playerBook(complete) {
    return {id: "width", title: "Miền đất · Tập 1", narrator: "Đức Trí", complete: complete, producing: !complete,
        state: {chapters: {}}, chapters: [
            {id: 1, index: 1, title: "Chương 1", subtitle: "Lên đường", fullTitle: "Chương 1 · Lên đường", available: true, duration: 100},
            {id: 2, index: 2, title: "Chương 2", subtitle: "Bên bờ sông", fullTitle: "Chương 2 · Bên bờ sông", available: true, duration: 100},
            {id: 3, index: 3, title: "Chương 3", subtitle: "Chuyến đi tiếp nối", fullTitle: "Chương 3 · Chuyến đi tiếp nối", available: false, duration: 0}
        ]}
}
function responses() {
    return {
        "/api/books/width/suggestions": {status: 200, data: {suggestions: [{chapter: 1, line: "Nguồn: bản dịch được chia sẻ", skipped: false}, {chapter: 2, line: "Nguồn: bản dịch được chia sẻ", skipped: false}]}},
        "/api/listen/books/width": {status: 200, data: playerBook(false)},
        "/api/books/width/chapters/3/script": {status: 200, data: {segments: [
            {text: "Buổi sáng ấy, chúng tôi đi qua con đường nhỏ bên bờ sông."},
            {text: "Gió thổi qua những hàng cây. Phía trước là một miền đất mới, còn bạn có thể thong thả đọc chương này trong lúc chờ bản thu."}
        ]}},
        "/api/listen/books/fresh": {status: 200, data: {id: "fresh", chapters: [{id: 1, title: "Chương 1 · Bình yên", state: "text"}, {id: 2, title: "Chương 2 · Sáng mai", state: "text"}]}},
        "/api/listen/books/fresh/chapters/1/text": {status: 200, data: {text: "Buổi sáng ấy, chúng tôi đi qua con đường nhỏ bên bờ sông.\n\nGió thổi qua những hàng cây, mang theo mùi hương của một ngày mới. Bạn có thể chọn một chương khác ở danh sách phía trên."}}
    }
}
