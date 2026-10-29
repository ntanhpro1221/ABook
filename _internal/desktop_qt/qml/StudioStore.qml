import QtQuick
import ABook
import "StudioLogic.js" as Logic
import "PeerStudio.js" as Peer

// Dữ liệu của Studio (data.ts + api.ts của bản web): danh sách dự án, MỘT dự án đang mở, và các lệnh Bắt đầu / Tạm dừng / Dừng...
// Mọi lời gọi đi đúng đường của web: `/api/...` của máy này, hay `/api/peers/<mã máy>/studio/api/...` khi đang mở Studio của máy tính đã ghép
// (throughPeer của shared/peerStudio.ts) - cùng một giao diện nói chuyện với máy nào cũng được.
// Nhịp hỏi như web (useLibrary 5 s khi có sách chạy / 15 s; useBook 3 s / 15 s, lùi dần khi lỗi, thôi hẳn khi 404) nhưng CHỈ khi cửa sổ đang thấy
// (`active` = UiActivity.running): ẩn / thu nhỏ thì không hỏi, hiện lại thì hỏi ngay một lần.
QtObject {
    id: root
    property string peer: ""
    property var peerInfo: null                     // /api/app của máy kia (Studio của máy khác)
    property bool active: true
    property bool libraryWanted: false
    readonly property var info: peer ? (peerInfo || ({})) : Api.info
    readonly property bool remote: Boolean(info && info.remote)
    readonly property string computerName: Peer.listenOnlyOwner(info)
    readonly property var studioState: Logic.studioMissing(info && info.studio)
    signal listenOnlyHit()                          // 403 listenOnly: Studio của máy kia vừa đổi sang chỉ nghe
    signal peerSilent(string message)               // máy kia im (503 unreachable)

    // ---- đường truyền ----
    function path(p) { return Logic.peerPath(p, peer) }
    // done(status, data); lỗi chung của bản web (listenOnly, unreachable) báo qua tín hiệu
    function request(method, p, body, done) {
        if (!Api.transport) { if (done) done(0, null); return 0 }
        const mine = peer
        return Api.transport.request(method, path(p), body === undefined ? null : body, function(status, data) {
            if (mine === root.peer && status >= 400) {
                if (status === 403 && data && data.listenOnly === true) root.listenOnlyHit()
                if (mine && data && data.unreachable) root.peerSilent(String(data.error || ""))
            }
            if (done) done(status, data)
        })
    }
    function ok(status) { return status >= 200 && status < 300 }
    // Như Api.quiet (done(data, lỗi, thân)) nhưng đi đúng máy của Studio: tab Nhân vật tự hiện lỗi tại chỗ thay vì đặt Api.notice
    function quiet(method, p, body, done) {
        return request(method, p, body, function(status, data) {
            if (ok(status)) { if (done) done(data, null) }
            else if (done) done(null, data && (data.message || data.error) || (status === 0 ? errorText(0, null) : "Không làm được lúc này."), data)
        })
    }
    // Lời lỗi cho người nghe (serverMessage + failureText của web)
    function errorText(status, data) {
        if (status === 0) return "Mất kết nối tới ABook."
        const raw = String(data && (data.error || data.message) || "Lỗi " + status)
        return status >= 500 && /^[A-Z][A-Za-z]*(?:Error|Exception|Interrupt|Iteration|Exit)(?::|$)/.test(raw.trim())
            ? "Máy gặp lỗi không ngờ khi làm việc này. Thử lại; nếu vẫn lỗi, mở Chi tiết để gửi cho người hỗ trợ." : raw
    }
    function say(title, description) { Api.notice = description ? title + "\n" + description : title }
    function fail(title, status, data) { say(title, errorText(status, data)) }

    // ---- danh sách dự án ----
    property var libraryData: null                  // {root, rootMissing, books}
    property string libraryError: ""
    property bool libraryLoading: libraryData === null && libraryError === ""
    property int libraryAsk: 0
    onLibraryWantedChanged: if (libraryWanted) loadLibrary()
    // Đổi máy (hay về máy này): danh sách của máy trước không thuộc máy sau
    onPeerChanged: { libraryData = null; libraryError = ""; libraryAsk++; if (libraryWanted) loadLibrary() }
    readonly property var books: libraryData ? libraryData.books || [] : []
    function loadLibrary() {
        const ask = ++libraryAsk
        const mine = peer
        request("GET", "/api/library", null, function(status, data) {
            if (ask !== root.libraryAsk || mine !== root.peer) return
            if (ok(status) && data) { root.libraryData = data; root.libraryError = "" }
            else root.libraryError = errorText(status, data)
        })
    }
    property Timer libraryTimer: Timer {
        objectName: "libraryPoll"
        interval: Logic.libraryInterval(root.books)
        running: root.active && root.libraryWanted
        repeat: true
        onTriggered: root.loadLibrary()
    }

    // ---- MỘT dự án đang mở ----
    property string bookId: ""
    property var bookData: null                     // {book, chapters}
    property var bookError: null                    // null = lần hỏi gần nhất ổn; không thì {status, text}
    property int bookErrors: 0
    property int bookAsk: 0
    readonly property bool bookLoading: bookId !== "" && bookData === null && bookError === null
    readonly property string bookFailure: bookId === "" ? "" : Logic.bookFailure(bookData !== null, bookError ? bookError.status : null)
    readonly property var book: bookData ? bookData.book : null
    readonly property var chapters: bookData ? bookData.chapters || [] : []
    function openBook(id) {
        if (id === bookId) { loadBook(); return }
        bookId = id
        bookData = null; bookError = null; bookErrors = 0
        if (id) loadBook()
    }
    function loadBook() {
        if (!bookId) return
        const ask = ++bookAsk
        const id = bookId
        request("GET", "/api/books/" + id, null, function(status, data) {
            if (ask !== root.bookAsk || id !== root.bookId) return
            if (ok(status) && data && data.book) { root.bookData = data; root.bookError = null; root.bookErrors = 0 }
            else { root.bookError = {status: status, text: errorText(status, data)}; root.bookErrors++ }
        })
    }
    property Timer bookTimer: Timer {
        objectName: "bookPoll"
        interval: Math.max(1, Logic.pollDelay(Logic.bookInterval(root.book), root.bookError ? root.bookError.status : null, root.bookErrors))
        running: root.active && root.bookId !== "" && Logic.pollDelay(Logic.bookInterval(root.book), root.bookError ? root.bookError.status : null, root.bookErrors) > 0
        repeat: true
        onTriggered: root.loadBook()
    }
    // Đặt phản hồi của máy chủ (trạng thái SẼ có sau lệnh) vào trang sách và danh sách ngay, không đợi nhịp hỏi kế (adoptSummary của web).
    function adopt(summary) {
        bookAsk++
        if (bookData && bookData.book && bookData.book.id === summary.id) bookData = Object.assign({}, bookData, {book: summary})
        if (libraryData) libraryData = Object.assign({}, libraryData, {books: libraryData.books.map(function(entry) { return entry.id === summary.id ? Object.assign({}, entry, summary) : entry })})
    }
    // Cửa sổ vừa hiện lại: hỏi ngay một lần thay vì đợi nhịp kế
    function refreshNow() { if (libraryWanted) loadLibrary(); if (bookId) loadBook() }
    function refresh(id) { loadLibrary(); if (id && id === bookId) loadBook() }

    // ---- lệnh (scope "start-stop" của web: một lệnh một lúc) ----
    property bool starting: false
    property bool pausing: false
    property bool stopping: false
    readonly property bool commanding: starting || pausing || stopping
    function start(id) {
        if (commanding) return
        starting = true
        request("POST", "/api/books/" + id + "/start", null, function(status, data) {
            root.starting = false
            if (!ok(status)) { root.fail("Không bắt đầu được", status, data); return }
            root.refresh(id)
            Api.notice = data && data.queuePosition ? "Đã xếp hàng - tự bắt đầu khi cuốn đang chạy xong (cần mở app)" : "Đang khởi động"
        })
    }
    // Studio chưa cài / cần cập nhật: nói thẳng ở đây thay vì gửi lệnh rồi nhận lỗi (Actions.begin của web)
    function begin(id, goSettings) {
        const missing = studioState
        if (!missing.missing) { start(id); return }
        const refusal = Logic.startRefusal(missing)
        Api.toast(refusal.title + "\n" + refusal.description, remote ? {} : {action: {label: missing.action, run: goSettings}})
    }
    // "Tạm dừng" / "Tiếp tục": tiến trình vẫn sống, làm tiếp đúng chỗ - an toàn cả giữa pha phân tích (khác "Dừng"!)
    function pause(id, paused, battery) {
        if (commanding) return
        pausing = true
        request("POST", "/api/books/" + id + "/pause", {paused: paused}, function(status, data) {
            root.pausing = false
            if (!ok(status)) { root.refresh(id); root.fail(paused ? "Không tạm dừng được" : "Không làm tiếp được", status, data); return }
            root.adopt(data)
            const notice = Logic.pauseNotice(paused, data, Boolean(battery))
            root.say(notice.title, notice.description)
        })
    }
    function stop(id, wasPaused) {
        if (commanding) return
        stopping = true
        request("POST", "/api/books/" + id + "/stop", null, function(status, data) {
            root.stopping = false
            if (!ok(status)) { root.refresh(id); root.fail("Không dừng được", status, data); return }
            root.adopt(data)
            Api.notice = wasPaused ? "Đang dừng hẳn - mọi thứ đã xong được giữ nguyên" : "Sẽ dừng ở chỗ an toàn kế tiếp - mọi thứ đã xong được giữ nguyên"
        })
    }
    // "Bỏ xếp hàng": lệnh riêng, máy chủ CHỈ bỏ khỏi hàng (dừng giữa pha phân tích là đổi quyển sách)
    function leaveQueue(id) {
        if (commanding) return
        request("POST", "/api/books/" + id + "/dequeue", null, function(status, data) {
            root.refresh(id)
            if (!ok(status)) root.fail("Chưa bỏ xếp hàng được", status, data)
            else Api.notice = "Đã bỏ xếp hàng - cuốn này không tự bắt đầu nữa"
        })
    }
    function reveal(id) {
        request("POST", "/api/books/" + id + "/reveal", null, function(status, data) {
            if (!ok(status)) root.fail("Không mở được thư mục", status, data)
        })
    }
    function rename(id, title, done) {
        request("PUT", "/api/books/" + id + "/title", {title: title}, function(status, data) {
            if (!ok(status)) { root.fail("Chưa đổi được tên", status, data); if (done) done(false); return }
            root.loadLibrary()
            if (id === root.bookId) root.loadBook()
            Api.notice = "Đã đổi tên thành “" + data.title + "”"
            if (done) done(true)
        })
    }
    // Xoá = cả thư mục dự án vào Thùng rác (khôi phục được trong ít giây qua "Hoàn tác", trash_pending.py)
    function remove(id, title, done) {
        request("DELETE", "/api/books/" + id, null, function(status, data) {
            if (!ok(status)) { root.fail("Chưa xoá được", status, data); if (done) done(false); return }
            root.loadLibrary()
            if (done) done(true)
            const message = "Đã xoá dự án “" + title + "”"
            if (data && data.undo) {
                Api.toast(message, {duration: 28000, action: {label: "Hoàn tác", run: function() { root.undoRemove(data.undo, title) }}})
            } else Api.notice = message
        })
    }
    function undoRemove(token, title) {
        request("POST", "/api/trash/" + token + "/undo", {}, function(status, data) {
            if (!ok(status)) { root.fail("Chưa hoàn tác được", status, data); return }
            root.loadLibrary()
            Api.notice = data && data.renamed && data.title ? "Đã khôi phục “" + title + "” vào thư mục “" + data.title + "”" : "Đã khôi phục “" + title + "”"
        })
    }
    function restoreBackup(id, title, done) {
        request("POST", "/api/books/" + id + "/restore-backup", null, function(status, data) {
            root.loadLibrary()
            if (!ok(status)) { root.fail("Chưa khôi phục được", status, data); if (done) done(false); return }
            Api.notice = "Đã khôi phục “" + title + "” từ bản sao"
            if (done) done(true)
        })
    }
    // "Mở dự án có sẵn…": chọn thư mục rồi mở nó (pickFolder + useOpenBook của web)
    function openExisting(done) {
        request("POST", "/api/dialog/folder", {title: "Chọn thư mục một cuốn sách đã tạo", start: ""}, function(status, data) {
            if (!ok(status)) { root.fail("Không mở được sách", status, data); return }
            if (!data || !data.path) return
            root.request("POST", "/api/books/open", {path: data.path}, function(s2, d2) {
                if (!root.ok(s2)) { root.fail("Không mở được sách", s2, d2); return }
                root.loadLibrary()
                if (done) done(d2.id)
            })
        })
    }

    // ---- nhân vật và "Duyệt trước khi thu" ----
    signal castEdited(string bookId)                // một việc sửa dàn nhân vật vừa ghi xong: danh sách người, hộp việc, cách đọc tên đọc lại
    signal precastChanged(string bookId)
    function editedCast(id) {
        if (id === bookId) loadBook()
        if (libraryWanted) loadLibrary()
        castEdited(id)
    }
    // Công tắc "Duyệt trước khi thu" (PrecastWaitSwitch): PUT /precast {wait}; lời đáp là trạng thái mới của màn duyệt
    function setPrecastWait(id, wait, done) {
        request("PUT", "/api/books/" + id + "/precast", {wait: wait}, function(status, data) {
            if (!ok(status)) { root.fail("Chưa đổi được", status, data); if (done) done(false); return }
            if (id === bookId) loadBook()
            if (libraryWanted) loadLibrary()
            precastChanged(id)
            if (done) done(true)
        })
    }

    // ---- chương ----
    // "Thu lại cả chương" (ChapterMenu của ProjectScreen.tsx): đặt lại mọi câu đã thu của chương để thu lại với hạt giống mới
    function retakeChapter(id, chapter, done) {
        request("POST", "/api/books/" + id + "/chapters/" + chapter.id + "/retake", null, function(status, data) {
            if (!ok(status)) { root.fail("Chưa ghi được", status, data); if (done) done(false); return }
            Api.notice = "Đã ghi: thu lại " + data.lines + " câu của " + chapter.displayTitle
            root.refresh(id)
            if (done) done(true)
        })
    }
    // Số chương mới của truyện gốc ("Thêm N chương", useContinuation): chỉ hỏi khi phân tích đã xong
    function loadContinuation(id, done) {
        request("GET", "/api/books/" + id + "/continuation", null, function(status, data) {
            done(ok(status) && data && data.paths ? data.paths.length : 0)
        })
    }

    // ---- Nhật ký (useActivity) ----
    function loadActivity(id, technical, done) {
        request("GET", "/api/books/" + id + "/activity" + (technical ? "?technical=1" : ""), null, done)
    }
}
