import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Mọi hộp hỏi của Studio và việc chạy theo mục menu "…" / nút chính: dùng chung cho màn Dự án (menu của hàng) và trang một dự án, để một việc
// chỉ có MỘT chỗ làm. `perform(key, book)` chạy một mục menu của StudioLogic.projectMenu / rowMenu; `runPrimary(kind, book)` chạy nút chính.
// Việc cần sang màn khác thì phát tín hiệu: `listenRequested`, `newProjectRequested`, `removed`.
Item {
    id: root
    anchors.fill: parent
    property var store: null
    property bool local: true                  // false: Studio của máy tính khác
    property string computer: "máy tính"
    property int next: 0                       // số chương mới của truyện gốc (useContinuation)
    signal listenRequested(string id)
    signal newProjectRequested(string mode, string id)
    signal removed(string id)
    signal detailsRequested(var book)

    property var target: ({})
    property string mode: ""
    property bool deleting: false
    property bool restoring: false

    function goSettings() { if (Nav.stack) Nav.stack.show(2) }
    // Bản sống của dự án (số thay đổi, đang chạy...) để hộp Xuất / Áp dụng đọc theo, không chụp một lần lúc mở
    function liveOf(book) {
        if (!store || !book) return book
        if (store.book && store.book.id === book.id) return store.book
        return store.books.filter(function(item) { return item.id === book.id })[0] || book
    }

    // ---- nút chính ----
    function runPrimary(kind, book) {
        if (!store) return
        if (kind === "unpause") store.pause(book.id, false, book.paused === "battery")
        else if (kind === "pause") store.pause(book.id, true)
        else if (kind === "start" || kind === "record" || kind === "continue") store.begin(book.id, goSettings)
        else if (kind === "reanalyze") newProjectRequested("redo", book.id)
        else if (kind === "apply") applyChanges.begin(liveOf(book))
        else if (kind === "listen") listenRequested(book.id)
    }
    // ---- mục menu ----
    function perform(key, book) {
        if (!store) return
        if (key === "rename") rename.begin(book)
        else if (key === "delete") ask("delete", book)
        else if (key === "restore") ask("restore", book)
        else if (key === "reveal") store.reveal(book.id)
        else if (key === "listen") listenRequested(book.id)
        else if (key === "continueBook") newProjectRequested("continue", book.id)
        else if (key === "addChapters") newProjectRequested("continue", book.id)
        else if (key === "redo") newProjectRequested("redo", book.id)
        else if (key === "resumeAnyway") ask("resume", book)
        else if (key === "stop") ask("stop", book)
        else if (key === "apply") applyChanges.begin(liveOf(book))
        else if (key === "leaveQueue") store.leaveQueue(book.id)
        else if (key === "export") exportBook.begin(liveOf(book))
        else if (key === "details") ask("details", book)
    }

    function ask(kind, book) {
        target = book
        mode = kind
        confirm.warn = false
        deleting = false; restoring = false
        const title = book.title || ""
        if (kind === "delete") {
            const busy = Boolean(book.running || book.starting)
            confirm.title = "Xoá dự án “" + title + "”?"
            confirm.description = Logic.deleteDescription()
            confirm.lines = (book.path && local ? [{text: book.path, tone: "muted"}] : []).concat(busy ? [{text: "Sách đang chạy - dừng sách trước rồi mới xoá được.", tone: "warning"}] : [])
            confirm.actions = [{key: "later", text: "Để sau"}, {key: "go", text: "Chuyển vào Thùng rác", icon: "trash-2", kind: "danger", enabled: !busy, busy: false}]
        } else if (kind === "restore") {
            confirm.title = "Khôi phục “" + title + "” từ bản sao cũ?"
            confirm.description = "Việc làm sau lần nâng cấp phải làm lại; chương đã thu và bản hỏng vẫn được giữ."
            confirm.lines = []
            confirm.actions = [{key: "later", text: "Để sau"}, {key: "go", text: "Khôi phục", icon: "history", kind: "primary"}]
        } else if (kind === "stop") {
            const inAnalysis = book.phase === "analysis"
            const warning = Logic.stopWarning(book)
            confirm.title = Logic.stopTitle(book)
            confirm.description = Logic.stopDescription(book)
            confirm.warn = Boolean(warning)
            confirm.lines = warning ? [{text: warning.fact, tone: "bold"}, {text: warning.advice, tone: "muted"}] : []
            const actions = [{key: "later", text: book.paused ? "Để nguyên" : "Để chạy tiếp"}]
            if (inAnalysis && !book.paused && book.canPause) actions.push({key: "pause", text: "Tạm dừng", icon: "pause", kind: "primary"})
            actions.push({key: "go", text: inAnalysis ? "Vẫn dừng" : "Dừng", icon: "square", kind: "danger"})
            confirm.actions = actions
        } else if (kind === "resume") {
            const warning = Logic.resumeWarning(book)
            confirm.title = "Tiếp tục phân tích?"
            confirm.description = ""
            confirm.warn = true
            confirm.lines = [{text: warning.fact, tone: "bold"}, {text: warning.cost.trim()}, {text: warning.advice, tone: "muted"}]
            // Studio từ xa không tạo lại sách được: chỉ còn "Vẫn tiếp tục", và đó là nút chính
            confirm.actions = local
                ? [{key: "later", text: "Để sau"}, {key: "go", text: "Vẫn tiếp tục", icon: "play"}, {key: "redo", text: "Phân tích lại", icon: "rotate-ccw", kind: "primary"}]
                : [{key: "later", text: "Để sau"}, {key: "go", text: "Vẫn tiếp tục", icon: "play", kind: "primary"}]
        } else if (kind === "details") {
            confirm.title = "Chi tiết dự án"
            confirm.description = title
            confirm.lines = Logic.projectDetails(book).map(function(line) { return {text: line, tone: "muted"} })
            confirm.actions = [{key: "later", text: "Đóng", kind: "primary"}]
        }
        confirm.show()
    }
    function answered(key) {
        const book = target, id = target.id
        if (key === "later") { confirm.close(); return }
        if (mode === "delete") {
            deleting = true
            confirm.actions = confirm.actions.map(function(a) { return a.key === "go" ? Object.assign({}, a, {busy: true}) : a })
            if (Player.loaded && Player.bookId === id) Player.close()      // cuốn đang nghe giữ file chương mở
            store.remove(id, book.title, function(ok) { confirm.dismiss(); if (ok) root.removed(id) })
        } else if (mode === "restore") {
            confirm.actions = confirm.actions.map(function(a) { return a.key === "go" ? Object.assign({}, a, {busy: true}) : a })
            store.restoreBackup(id, book.title, function() { confirm.dismiss() })
        } else if (mode === "stop") {
            confirm.dismiss()
            if (key === "pause") store.pause(id, true)
            else store.stop(id, Boolean(book.paused))
        } else if (mode === "resume") {
            confirm.dismiss()
            if (key === "redo") newProjectRequested("redo", id)
            else store.begin(id, goSettings)
        }
    }

    StudioRename { id: rename; store: root.store }
    ExportBook { id: exportBook; store: root.store; onApplyFirst: applyChanges.begin(root.liveOf(exportBook.book)) }
    ApplyChanges { id: applyChanges; store: root.store; onApplied: root.store.begin(applyChanges.bookId, root.goSettings) }
    Binding { target: exportBook; property: "live"; value: root.liveOf(exportBook.snapshot); when: exportBook.open; restoreMode: Binding.RestoreNone }
    Binding { target: applyChanges; property: "live"; value: root.liveOf(applyChanges.snapshot); when: applyChanges.open; restoreMode: Binding.RestoreNone }
    StudioConfirm { id: confirm; objectName: "studioConfirm"; panelWidth: 480; onChosen: key => root.answered(key) }
}
