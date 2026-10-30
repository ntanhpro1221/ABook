import QtQuick
import QtQuick.Dialogs
import ABook
import "ImportQueue.js" as Queue

// "Thêm sách từ file…" (listen/AddBook.tsx của bản web): EPUB / DOCX / PDF có chữ / TXT / thư mục TXT / file .abook thành sách trong thư viện. Ba bước trong một
// hộp, đổi bước bằng Collapse (mở khép tại chỗ): chọn -> xem lại chương (và gợi ý của máy) -> thêm. Chọn nhiều file thì thành hàng xem trước, mỗi cuốn qua đúng bước
// xem trước của một file. Chữ của truyện không bao giờ bị sửa. Hàm thuần nằm ở ImportQueue.js; ở đây giữ trạng thái và việc gọi máy chủ.
// Back: Esc / ✕ / bấm ra ngoài là một đường (Modal.keepOpen) - đang thêm thì giữ hộp, đang hỏi "Đóng khi còn sách chưa thêm" thì đóng câu hỏi trước (lớp Back riêng),
// hàng còn > 1 cuốn thì hỏi trước khi bỏ. Đổi tên chương là bước con của ImportChapters (cũng một lớp Back).
Modal {
    id: root
    readonly property bool expanded: Theme.widthClass(width) >= 2 && step === "review"
    property real wideT: expanded ? 1 : 0
    Behavior on wideT {
        NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
    }
    panelWidth: expanded ? Math.min(width - 2 * Theme.margin, 1160) : 560
    title: preview && queueName !== "" ? queueName + " · Thêm sách" : "Thêm sách"
    description: queue && !preview ? Queue.summaryText(Queue.summarize(queue))
               : preview ? "Xem lại chương trước khi thêm. Chữ của truyện giữ nguyên."
               : "EPUB, DOCX, PDF có chữ, TXT, thư mục TXT hay file .abook. Chọn được nhiều file."

    // ---- Trạng thái ----
    property var preview: null              // bản xem trước của cuốn đang xem (null = chưa có / đang đọc)
    property var shownPreview: null                // bản xem trước cuối cùng: bước xem trước thu lại vẫn vẽ nội dung cũ tới khi thu xong
    property string path: ""                // file / thư mục của cuốn đang xem
    property string bookTitle: ""
    property string busy: ""                // "" | "reading" | "adding"
    property string problem: ""
    property var queue: null                // hàng nhiều file (null = một file)
    property int currentId: -1
    property string working: ""
    property string leave: ""               // "" | "close" | "again": câu hỏi khi hàng còn sách chưa thêm
    property string shownLeave: ""
    property var skipped: []                // dòng ghi công người nghe chọn bỏ khỏi phần đọc
    property bool split: false
    property var footnotes: Queue.NO_FOOTNOTES
    property var picked: []                 // số thứ tự các hàng chương đang tích
    property var names: ({})                // tên chương đã đổi, theo số thứ tự hàng
    property int generation: 0              // mỗi lượt đọc một số; đóng hộp / chọn lại / lượt mới thì lượt cũ hết hiệu lực
    property var lastRead: null
    property int pickSession: -1
    property Item leaveFocus: null

    signal openBook(string id)
    signal openStudio(string id)

    readonly property var groups: shownPreview ? Queue.groupSuggestions(shownPreview.suggestions || [], shownPreview.chapters, picked) : []
    readonly property var totals: shownPreview ? Queue.pickedTotals(shownPreview.chapters, picked) : ({chapters: 0, words: 0})
    readonly property bool nothingPicked: preview !== null && picked.length === 0
    readonly property int pending: Queue.unfinished(queue)
    readonly property var notes: shownPreview ? shownPreview.notes.slice(0, shownPreview.notes.length - (shownPreview.suggestions ? shownPreview.suggestions.length : 0)) : []
    // Cuốn "đã có trong thư viện" tính theo các chương MẶC ĐỊNH; tích khác đi là bộ chữ khác, cứ thêm - máy sẽ nói nếu hoá ra đã có.
    readonly property var existing: shownPreview && Queue.isDefaultPick(shownPreview.chapters, picked) ? (shownPreview.existing || null) : null
    readonly property var sameSource: !existing && shownPreview ? (shownPreview.sameSource || null) : null
    readonly property var known: existing || sameSource
    readonly property string queueName: queue && currentId >= 0 ? Queue.queueLabel(queue, currentId) : ""
    readonly property int rest: queue && currentId >= 0 ? Queue.waitingAfter(queue, currentId).length : 0
    readonly property string step: preview ? "review" : (queue ? "queue" : "choose")
    readonly property bool canAdd: bookTitle.trim() !== "" && !nothingPicked

    onPreviewChanged: if (preview) shownPreview = preview
    onLeaveChanged: {
        if (leave !== "") {
            shownLeave = leave
            leaveFocus = Window.window ? Window.window.activeFocusItem : null
            Nav.openLayer(leaveLayer)
        } else {
            Nav.closedLayer(leaveLayer)
            const back = leaveFocus
            leaveFocus = null
            if (back && open) Later.call(root, function() { back.forceActiveFocus(Qt.BacktabFocusReason) })
        }
    }
    // Lớp Back của câu hỏi: Back đóng câu hỏi, về hộp
    readonly property QtObject leaveLayer: QtObject { function close() { root.leave = "" } }

    // ---- Lượt đọc ----
    function newSession() { return ++generation }
    // Lỗi đã hiện ngay trong hộp thì không báo thêm lần nữa ở thanh thông báo (Api.call tự đặt Api.notice)
    function send(method, route, body, done) {
        Api.call(method, route, body, function(data, error) {
            if (error && Api.notice === error) Api.notice = ""
            done(data, error)
        })
    }
    function setTitle(value) { bookTitle = value; titleField.text = value }
    function clearPreview() {
        preview = null; path = ""; skipped = []; split = false; footnotes = Queue.NO_FOOTNOTES; picked = []; names = ({})
        setTitle("")
    }
    function reset() {
        generation++
        lastRead = null; busy = ""; problem = ""; queue = null; currentId = -1; working = ""; leave = ""
        typed.text = ""
        clearPreview()
    }
    function clear() { reset() }

    function begin(paths) {
        reset(); show()
        if (paths && paths.length) startPicked(paths.map(Queue.itemFromPath))
        else pickFiles()
    }
    function pickFiles() { pickSession = newSession(); files.open() }
    function pickFolder() { pickSession = newSession(); folder.open() }
    // Vừa chọn / kéo thả xong
    function startPicked(items) {
        if (!items.length) return
        if (items.length === 1) {
            const only = items[0]
            if (only.error !== undefined) problem = only.error
            else if (only.opened) { clear(); dismiss() }
            else read({path: only.path, name: only.name})
            return
        }
        problem = ""
        queue = Queue.buildQueue(items)
        goNext(queue)
    }

    function read(item) {
        lastRead = item
        const mine = newSession()
        problem = ""
        busy = "reading"
        if (Queue.isBookFile(item.path)) {
            openBookPath(item.path, mine, function(ok, error) {
                if (mine !== root.generation) return
                if (error) { root.busy = ""; root.problem = error; return }
                root.clear()
                root.dismiss()
            })
            return
        }
        loadPreview(item, mine, function(error) {
            if (mine !== root.generation) return
            root.busy = ""
            if (error) { root.problem = error; root.path = "" }
        })
    }
    // Đọc file thành bản xem trước: cả truyện trong một file mà máy chắc là nhiều chương thì mở sẵn với "tách" đã tích (bỏ tích được).
    function loadPreview(item, mine, done) {
        path = item.path
        requestPreview(item.path, false, undefined, mine, function(first, error) {
            if (mine !== root.generation) return
            if (error) { done(error); return }
            if (!Queue.splitIsSure(first)) { root.showPreview(first, false); done(""); return }
            root.requestPreview(item.path, true, undefined, mine, function(again, failed) {
                if (mine !== root.generation) return
                root.showPreview(failed ? first : again, !failed)
                done("")
            })
        })
    }
    function requestPreview(file, splitChapters, notes, mine, done) {
        const body = {path: file, splitChapters: splitChapters}
        if (notes) body.footnotes = notes
        send("POST", "/api/listen/import/preview", body, done)
    }
    function showPreview(result, sure) {
        preview = result
        skipped = (result.suggestions || []).filter(row => row.defaultOn).map(row => row.line)
        picked = Queue.defaultPicked(result.chapters)
        names = ({})
        setTitle(result.title || "")
        split = sure
        footnotes = Queue.NO_FOOTNOTES
        titleField.forceActiveFocus(Qt.TabFocusReason)
        titleField.selectAll()
    }
    // Tích / bỏ tích "Tách theo…" hay một đề xuất về chú thích: đọc lại file với lựa chọn mới. Tên sách người dùng đã sửa giữ nguyên; chương đã bỏ tích, tên chương
    // đã đổi và gợi ý đặt lại khi danh sách chương đã khác (còn giữ khi vẫn y như trước - chú thích chỉ đổi chữ trong chương).
    function reread(next) {
        if (!path || !preview) return
        const mine = newSession()
        busy = "reading"
        requestPreview(path, next.split, Queue.footnotesToSend(next.footnotes), mine, function(result, error) {
            if (mine !== root.generation) return
            root.busy = ""
            if (error) { Api.notice = Queue.said("Chưa đọc lại được file", error); return }
            if (!(root.preview && Queue.sameRows(root.preview.chapters, result.chapters))) {
                root.picked = Queue.defaultPicked(result.chapters); root.names = ({}); root.skipped = []
            }
            root.preview = result
            root.split = next.split
            root.footnotes = next.footnotes
        })
    }

    // ---- Mở file sách .abook / .abookproj như "Mở file sách" ----
    function openBookPath(file, mine, done) {
        send("POST", "/api/listen/open-book-file", {path: file}, function(result, error) {
            if (error) { if (mine === root.generation) done(false, error); return }
            const outcome = Queue.openedOutcome(result)
            if (mine !== root.generation) {
                // Hộp đã đóng: không chuyển trang, nhưng máy đã nhập xong cuốn này - thư viện vẫn phải thấy nó.
                if (outcome.id) DesktopApi.refreshLibrary()
                return
            }
            root.applyOpened(outcome)
            done(outcome.ok, "")
        })
    }
    function applyOpened(outcome) {
        if (outcome.notice) Api.notice = outcome.notice
        if (!outcome.id) return
        DesktopApi.refreshLibrary()
        if (outcome.studio) openStudio(outcome.id)
        else openBook(outcome.id)
    }
    // "Mở file sách" ở thư viện trống: hộp chọn file của máy chủ, nhập vào thư viện, mở trang sách
    property bool opening: false
    function openFile() {
        if (opening) return
        opening = true
        send("POST", "/api/listen/open-book-file", {}, function(result, error) {
            root.opening = false
            if (error) { Api.notice = Queue.said("Không mở được file sách", error); return }
            root.applyOpened(Queue.openedOutcome(result))
        })
    }

    // ---- Hàng nhiều file ----
    function openBookFiles(items, mine, done) {
        let current = items, at = 0
        function step() {
            if (mine !== root.generation) return
            while (at < current.length && !(current[at].state === "waiting" && current[at].path !== undefined)) at++
            if (at >= current.length) { done(current); return }
            const item = current[at++]
            root.openBookPath(item.path, mine, function(ok, error) {
                current = error ? Queue.settle(current, item.id, {state: "error", note: error})
                                : Queue.settle(current, item.id, ok === false ? {state: "error", note: "Không mở được file sách này."} : {state: "opened", note: "Đã mở"})
                root.queue = current
                step()
            })
        }
        step()
    }
    // Hàng xong: không file nào lỗi thì đóng hộp (một cuốn mới duy nhất thì mở trang sách); có file lỗi thì giữ hộp để đọc lý do.
    function finish(items) {
        const summary = Queue.summarize(items)
        if (summary.failed > 0) { Feedback.play("reject"); return }
        if (summary.added) Feedback.play("confirm")
        const added = items.filter(item => item.state === "added")
        clear()
        dismiss()
        Api.notice = Queue.summaryText(summary)
        if (added.length === 1 && added[0].bookId && summary.opened === 0) openBook(added[0].bookId)
    }
    // Sang cuốn kế trong hàng: file không đọc được ghi lỗi vào hàng và đi tiếp, không chặn các cuốn sau.
    function goNext(start) {
        const mine = newSession()
        clearPreview()
        busy = "reading"
        advance(start, mine)
    }
    function advance(items, mine) {
        if (mine !== generation) return
        const next = Queue.nextWaiting(items)
        if (!next || next.path === undefined) { settleQueue(items, mine); return }
        if (Queue.isBookFile(next.path)) { openBookFiles(items, mine, function(done) { settleQueue(done, mine) }); return }
        currentId = next.id
        queue = items
        loadPreview({path: next.path, name: next.name}, mine, function(error) {
            if (mine !== root.generation) return
            if (error) {
                const rest = Queue.settle(items, next.id, {state: "error", note: error})
                root.queue = rest
                root.advance(rest, mine)
                return
            }
            root.busy = ""
        })
    }
    function settleQueue(items, mine) {
        if (mine !== generation) return
        queue = items
        busy = ""
        finish(items)
    }

    // ---- Thêm ----
    // Thêm cuốn đang xem đúng như người dùng thấy (tên, chương đã tích, gợi ý đã chọn).
    function addCurrent(separate, done) {
        const body = {path: path, title: bookTitle.trim(), separate: Boolean(separate), splitChapters: split,
                      chapters: Queue.chapterPicks(preview.chapters, picked, names)}
        if (preview.sourceFingerprint) body.sourceFingerprint = preview.sourceFingerprint
        const notes = Queue.footnotesToSend(footnotes)
        if (notes) body.footnotes = notes
        const skips = groups.filter(group => skipped.indexOf(group.line) >= 0)
        root.send("POST", "/api/listen/import", body, function(added, error) {
            if (error) { done(null, error); return }
            // Gợi ý người nghe đã chọn: bỏ dòng ấy khỏi phần đọc của cuốn mới (chữ trong sách không đổi). Hỏng thì sách vẫn đã vào thư viện.
            let at = 0
            function next() {
                if (added.how !== "new" || at >= skips.length) { DesktopApi.refreshLibrary(); done(added, ""); return }
                const group = skips[at++]
                root.send("PUT", "/api/books/" + added.id + "/skip", {line: group.line, chapters: group.chapters, skip: true}, function() { next() })
            }
            next()
        })
    }
    function add(separate) {
        if (!preview || busy || !canAdd) return
        busy = "adding"
        const mine = generation
        addCurrent(separate, function(added, error) {
            if (mine !== root.generation) return
            if (error) { root.busy = ""; Feedback.play("reject"); Api.notice = Queue.said("Chưa thêm được sách", error); return }
            if (root.queue && root.currentId >= 0) {
                // Trong hàng: cuốn này xong, sang cuốn kế (thông báo gộp ở cuối hàng).
                const done = Queue.settle(root.queue, root.currentId, added.how === "existing" ? {state: "existing", note: "Đã có trong thư viện", bookId: added.id} : {state: "added", bookId: added.id})
                root.queue = done
                root.goNext(done)
                return
            }
            if (added.how !== "existing") Feedback.play("confirm")
            Api.notice = added.how === "existing" ? "Cuốn này đã có trong thư viện" : "Đã thêm sách vào thư viện"
            root.clear()
            root.dismiss()
            root.openBook(added.id)
        })
    }
    // "Thêm phần còn lại": cuốn đang xem thêm đúng như đang hiện, các cuốn sau dùng mặc định của bước xem trước. Cuốn nào lỗi thì ghi vào hàng và đi tiếp.
    function addAll() {
        if (!queue || currentId < 0 || !preview || busy) return
        busy = "adding"
        const mine = generation
        let items = queue.slice()
        // Thư viện xếp cuốn vừa vào lên đầu: thêm từ cuốn CUỐI về cuốn đang xem (cuốn đang xem thêm sau cùng) để cả lô hiện đúng thứ tự đã chọn.
        const order = Queue.waitingAfter(items, currentId).reverse()
        let at = 0
        function ended(result) {
            items = Queue.settle(items, root.currentId, result)
            root.queue = items
            root.openBookFiles(items, mine, function(done) {
                root.busy = ""; root.working = ""
                root.queue = done
                root.clearPreview()
                root.finish(done)
            })
        }
        function mine_() { return mine === root.generation }
        function now() {
            root.working = root.bookTitle.trim()
            if (root.known) { ended({state: "existing", note: root.existing ? "Đã có trong thư viện" : "Đã thêm từ file này rồi", bookId: root.known.id}); return }
            root.addCurrent(false, function(added, error) {
                if (!mine_()) return
                ended(error ? {state: "error", note: error}
                            : added.how === "existing" ? {state: "existing", note: "Đã có trong thư viện", bookId: added.id} : {state: "added", bookId: added.id})
            })
        }
        function step() {
            if (!mine_()) return
            if (at >= order.length) { now(); return }
            const item = order[at++]
            if (item.path === undefined || Queue.isBookFile(item.path)) { step(); return }
            root.working = item.name
            root.addWithDefaults(item.path, function(result) {
                if (!mine_()) return
                items = Queue.settle(items, item.id, result)
                root.queue = items
                step()
            })
        }
        queue = items
        step()
    }
    // Thêm một cuốn đúng như bước xem trước đề xuất, không hỏi gì: tên của file, các chương mặc định, tách chương khi máy chắc. Cuốn đã có thì không thêm.
    function addWithDefaults(file, done) {
        requestPreview(file, false, undefined, 0, function(first, error) {
            if (error) { done({state: "error", note: error}); return }
            if (!Queue.splitIsSure(first)) { root.addDefaults(file, first, false, done); return }
            root.requestPreview(file, true, undefined, 0, function(again, failed) { root.addDefaults(file, failed ? first : again, !failed, done) })
        })
    }
    function addDefaults(file, result, splitChapters, done) {
        if (result.existing) { done({state: "existing", note: "Đã có trong thư viện", bookId: result.existing.id}); return }
        if (result.sameSource) { done({state: "existing", note: "Đã thêm từ file này rồi", bookId: result.sameSource.id}); return }
        const name = (result.title || "").trim()
        if (!name) { done({state: "error", note: "File này chưa có tên sách - thêm riêng để đặt tên."}); return }
        if (Queue.defaultPicked(result.chapters).length === 0) { done({state: "error", note: "File này chưa có chương nào để thêm."}); return }
        const body = {path: file, title: name, separate: false, splitChapters: splitChapters}
        if (result.sourceFingerprint) body.sourceFingerprint = result.sourceFingerprint
        send("POST", "/api/listen/import", body, function(added, error) {
            if (error) { done({state: "error", note: error}); return }
            done(added.how === "existing" ? {state: "existing", note: "Đã có trong thư viện", bookId: added.id} : {state: "added", bookId: added.id})
        })
    }
    function skipCurrent() {
        if (!queue || currentId < 0) return
        const rest = known ? Queue.settle(queue, currentId, {state: "existing", note: existing ? "Đã có trong thư viện" : "Đã thêm từ file này rồi", bookId: known.id})
                           : Queue.settle(queue, currentId, {state: "skipped", note: "Bỏ qua"})
        queue = rest
        goNext(rest)
    }
    // "Chọn lại": còn các cuốn khác trong hàng thì hỏi trước (bỏ cả hàng), không bỏ im lặng
    function chooseAgain() {
        if (pending > 1 && leave !== "again") { leave = "again"; return }
        reset()
    }
    function openExisting(id) {
        reset()
        dismiss()
        openBook(id)
    }
    function openTyped() {
        const typedPath = Queue.cleanPath(typed.text)
        if (typedPath) read({path: typedPath, name: typedPath})
    }

    // Esc / ✕ / bấm ra ngoài / Back: đang thêm thì giữ hộp; đang hỏi thì đóng câu hỏi; hàng còn > 1 cuốn thì hỏi; không thì bỏ lượt đọc dở và đóng.
    keepOpen: function() {
        if (leave !== "") { leave = ""; return true }
        if (busy === "adding") return true
        if (pending > 1) { leave = "close"; return true }
        generation++
        return false
    }
    onOpenChanged: if (!open) { generation++; leave = ""; files.close(); folder.close() }
    Component.onDestruction: Nav.closedLayer(leaveLayer)

    // ---- Chân hộp ----
    footer: [
        ImportActions {
            width: parent ? parent.width : 0
            open: root.leave === "" && ((root.queue !== null && !root.preview && root.busy === "") || root.preview !== null)
            ImportSlot {
                open: root.queue !== null && !root.preview && root.busy === ""
                Button { text: "Xong"; onClicked: root.close() }
            }
            ImportSlot {
                open: root.preview !== null
                Button { text: "Chọn lại"; kind: "ghost"; enabled: root.busy === ""; onClicked: root.chooseAgain() }
            }
            ImportSlot {
                open: root.preview !== null && root.queue !== null && !root.known
                Button { objectName: "importSkip"; text: "Bỏ cuốn này"; kind: "ghost"; enabled: root.busy === ""; onClicked: root.skipCurrent() }
            }
            ImportSlot {
                open: root.preview !== null && root.rest > 0
                Button { objectName: "importAddRest"; text: "Thêm phần còn lại"; kind: "ghost"; busy: root.busy === "adding"; enabled: root.canAdd && root.busy === ""; onActivated: root.addAll() }
            }
            ImportSlot {
                open: root.preview !== null && root.known !== null
                Button { objectName: "importAddSeparate"; text: root.existing ? "Thêm bản riêng" : "Vẫn thêm bản mới"; icon: "copy"; kind: "ghost"; busy: root.busy === "adding"; enabled: root.canAdd && root.busy === ""; onActivated: root.add(true) }
            }
            ImportSlot {
                open: root.preview !== null && root.known !== null && root.queue === null
                Button { objectName: "importOpenKnown"; text: "Mở cuốn đó"; icon: "book-open"; enabled: root.busy === ""; onClicked: root.openExisting(root.known.id) }
            }
            ImportSlot {
                open: root.preview !== null && root.known === null
                Button { objectName: "importAdd"; text: "Thêm vào thư viện"; icon: "book-plus"; busy: root.busy === "adding"; enabled: root.canAdd && root.busy !== "reading"; onActivated: root.add(false) }
            }
            ImportSlot {
                open: root.preview !== null && root.queue !== null && root.known !== null
                Button { text: "Bỏ cuốn này"; enabled: root.busy === ""; onClicked: root.skipCurrent() }
            }
        }
    ]

    // ---- Thân hộp ----
    Column {
        width: parent.width
        spacing: 0

        // Hỏi khi hàng còn sách chưa thêm (alertdialog trong hộp): mở khép tại chỗ, có lớp Back riêng
        Collapse {
            id: confirm
            objectName: "importLeave"
            width: parent.width
            open: root.leave !== ""
            Accessible.role: Accessible.AlertMessage
            Accessible.name: root.leave === "again" ? "Chọn lại khi còn sách chưa thêm" : "Đóng khi còn sách chưa thêm"
            Column {
                width: parent.width
                topPadding: 14
                bottomPadding: 14 + 16
                spacing: 12
                Text {
                    width: parent.width
                    text: root.shownLeave === "again"
                        ? "Còn " + root.pending + " cuốn chưa thêm vào thư viện. Chọn lại thì các cuốn ấy sẽ không được thêm."
                        : "Còn " + root.pending + " cuốn chưa thêm vào thư viện. Đóng bây giờ thì các cuốn ấy sẽ không được thêm."
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                    textFormat: Text.PlainText
                }
                ImportActions {
                    width: parent.width
                    Button {
                        objectName: "importLeaveDrop"
                        text: root.shownLeave === "again" ? "Bỏ và chọn lại" : "Bỏ phần còn lại"
                        kind: "ghost"
                        onClicked: {
                            if (root.leave === "again") root.chooseAgain()
                            else { root.reset(); root.dismiss() }
                        }
                    }
                    Button { objectName: "importLeaveBack"; text: "Quay lại thêm sách"; onClicked: root.leave = "" }
                }
            }
        }

        // Hàng đã chọn, đang đọc cuốn kế (không có bản xem trước)
        Collapse {
            width: parent.width
            open: root.step === "queue"
            Column {
                width: parent.width
                Collapse {
                    width: parent.width
                    open: root.busy === "reading"
                    ImportSkeleton { width: parent.width; shape: "rows"; count: 1; label: "Đang đọc file tiếp" }
                }
                Item {
                    width: parent.width
                    height: queueAfter.implicitHeight + 12
                    ImportQueueList { id: queueAfter; y: 12; width: parent.width; items: root.queue || []; currentId: root.currentId; working: root.working; tall: true }
                }
            }
        }

        // Bước chọn
        Collapse {
            width: parent.width
            open: root.step === "choose"
            Column {
                width: parent.width
                Flow {
                    width: parent.width
                    spacing: 8
                    Button {
                        objectName: "importPickFile"
                        text: root.busy === "reading" ? "Đang đọc…" : "Chọn file sách"
                        icon: "file-text"
                        busy: root.busy === "reading"
                        enabled: root.busy === ""
                        onActivated: root.pickFiles()
                    }
                    Button { text: "Chọn thư mục TXT"; icon: "folder"; kind: "ghost"; enabled: root.busy === ""; onClicked: root.pickFolder() }
                }
                Item {
                    width: parent.width
                    height: typed.height + 16
                    FormField {
                        id: typed
                        objectName: "importTyped"
                        y: 16
                        width: parent.width - openTyped.width - 8 + 14
                        label: "Đường dẫn file hay thư mục"
                        placeholderText: "…hoặc dán đường dẫn"
                        enabled: root.busy === ""
                        onAccepted: root.openTyped()
                    }
                    Button {
                        id: openTyped
                        y: 16
                        x: parent.width + 14 - width
                        text: "Mở"
                        kind: "ghost"
                        enabled: root.busy === "" && Queue.cleanPath(typed.text) !== ""
                        onClicked: root.openTyped()
                    }
                }
                Collapse {
                    width: parent.width
                    open: root.busy === "reading" && root.step === "choose"
                    Item {
                        width: parent.width
                        height: skeleton.implicitHeight + 16
                        ImportSkeleton { id: skeleton; y: 16; width: parent.width; shape: "cards"; count: 2; label: "Đang đọc file sách" }
                    }
                }
                Item {
                    width: parent.width
                    height: failure.height + (failure.open ? 12 : 0)
                    ImportError { id: failure; y: 12; width: parent.width; message: root.step === "choose" ? root.problem : ""; onRetry: { if (root.lastRead) root.read(root.lastRead); else root.pickFiles() } }
                }
                Text {
                    width: parent.width
                    topPadding: 16
                    text: "PDF phải có chữ - PDF chụp từ máy quét thì ABook chưa đọc được."
                    color: Theme.text3
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeCaption
                    textFormat: Text.PlainText
                }
            }
        }

        // Bước xem lại chương
        Collapse {
            id: review
            objectName: "importReview"
            width: parent.width
            open: root.step === "review"
            Item {
                id: reviewLayout
                width: parent.width
                implicitHeight: Math.max(reviewOptions.y + reviewOptions.height, reviewChapters.y + reviewChapters.height)
                height: implicitHeight
                Column {
                    id: reviewMeta
                    objectName: "importDetailsColumn"
                    width: parent.width + (Math.min(360, (parent.width - Theme.s32) / 2) - parent.width) * Math.min(1, root.wideT * 2)
                    Collapse {
                        width: parent.width
                        open: root.queue !== null && root.preview !== null
                        Item {
                            width: parent.width
                            height: queueBefore.implicitHeight + 12 + 16
                            ImportQueueList { id: queueBefore; y: 12; width: parent.width; items: root.queue || []; currentId: root.currentId; working: root.working }
                        }
                    }
                    Text {
                        width: parent.width
                        text: "Tên sách"
                        color: Theme.text
                        font.pixelSize: Theme.sizeBodySmall
                        font.weight: Theme.weightMedium
                    }
                    Item {
                        width: parent.width
                        height: titleField.height + 6
                        FormField {
                            id: titleField
                            objectName: "importTitle"
                            y: 6
                            width: parent.width
                            label: "Tên sách"
                            placeholderText: "Tên hiển thị trong thư viện"
                            invalid: root.bookTitle.trim() === ""
                            font.pixelSize: 15
                            font.weight: Theme.weightMedium
                            topPadding: 11
                            bottomPadding: 11
                            leftPadding: 14
                            rightPadding: 14
                            implicitHeight: Math.max(44, contentHeight + 22)
                            background: Rectangle {
                                color: Theme.bg
                                radius: Theme.radiusCover
                                border.width: 1
                                border.color: titleField.invalid ? Theme.danger : titleField.activeFocus ? Theme.focus : Theme.line
                                Behavior on border.color { ColorAnimation { duration: Theme.motionFast } }
                            }
                            onTextChanged: root.bookTitle = text
                        }
                    }
                    Collapse {
                        width: parent.width
                        open: root.shownPreview !== null && Boolean(root.shownPreview.author)
                        Text {
                            width: parent.width
                            topPadding: 6
                            text: "Tác giả: " + (root.shownPreview && root.shownPreview.author ? root.shownPreview.author : "")
                            color: Theme.text2
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                            textFormat: Text.PlainText
                        }
                    }
                    // Số chương, số chữ + Chọn hết / Bỏ chọn hết
                    Item {
                        id: totalsRow
                        width: parent.width
                        readonly property bool stacked: summaryFlow.implicitWidth + 12 + links.implicitWidth > width
                        height: 16 + (stacked && links.visible ? summaryFlow.height + 4 + links.height : Math.max(summaryFlow.height, links.height))
                        Flow {
                            id: summaryFlow
                            y: 16
                            width: parent.width - (totalsRow.stacked ? 0 : links.implicitWidth + 12)
                            spacing: 4
                            Text {
                                objectName: "importTotals"
                                text: root.totals.chapters + (shownPreview && root.totals.chapters !== root.shownPreview.chapters.length ? " / " + root.shownPreview.chapters.length : "") + " chương"
                                color: Theme.text
                                font.pixelSize: Theme.sizeBodySmall
                                font.weight: 600
                                font.features: { "tnum": 1 }
                            }
                            Text {
                                text: "· " + Queue.formatNumber(root.totals.words) + " chữ"
                                color: Theme.text2
                                font.pixelSize: Theme.sizeBodySmall
                                font.features: { "tnum": 1 }
                            }
                        }
                        Row {
                            id: links
                            readonly property real implicitWidth: childrenRect.width
                            visible: root.shownPreview !== null && root.shownPreview.chapters.length > 1
                            x: totalsRow.stacked ? 0 : parent.width - width
                            y: totalsRow.stacked ? 16 + summaryFlow.height + 4 : 16
                            spacing: 12
                            Repeater {
                                model: [{label: "Chọn hết", all: true}, {label: "Bỏ chọn hết", all: false}]
                                Interactive {
                                    id: link
                                    required property var modelData
                                    width: linkText.implicitWidth
                                    height: Math.max(20, linkText.implicitHeight)
                                    enabled: root.busy === ""
                                    opacity: enabled ? 1 : 0.5
                                    ringMargin: 2
                                    Accessible.role: Accessible.Button
                                    Accessible.name: modelData.label
                                    onClicked: root.picked = modelData.all ? root.shownPreview.chapters.map(c => c.index) : []
                                    Text {
                                        id: linkText
                                        text: link.modelData.label
                                        color: Theme.accentText
                                        font.pixelSize: Theme.sizeCaption
                                        font.underline: link.hovered
                                    }
                                }
                            }
                        }
                    }
                    // Tách theo các dòng “Chương N” (file TXT cả truyện)
                    Collapse {
                        width: parent.width
                        open: root.shownPreview !== null && Boolean(root.shownPreview.splitOffer)
                        Item {
                            width: parent.width
                            height: splitCheck.height + 12
                            ImportCheck {
                                id: splitCheck
                                objectName: "importSplit"
                                y: 12
                                width: parent.width
                                label: root.shownPreview && root.shownPreview.splitOffer ? Queue.splitLabel(root.shownPreview) : ""
                                help: root.split ? "Mỗi dòng “Chương N” mở một chương mới; chữ của truyện giữ nguyên."
                                                 : "Cả truyện đang là một chương. Tích để tách theo các dòng ấy; chữ giữ nguyên."
                                checked: root.split
                                enabled: root.busy === ""
                                onToggled: value => root.reread({split: value, footnotes: root.footnotes})
                            }
                        }
                    }

                    Collapse {
                        width: parent.width
                        open: root.nothingPicked
                        Text {
                            objectName: "importNothingPicked"
                            width: parent.width
                            topPadding: 8
                            text: "Chưa chọn chương nào - tích ít nhất một chương để thêm vào thư viện."
                            color: Theme.danger
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                            textFormat: Text.PlainText
                        }
                    }
                }
                Column {
                    id: reviewOptions
                    objectName: "importOptionsColumn"
                    width: reviewMeta.width
                    y: reviewMeta.height + (reviewChapters.height + Theme.s16) * (1 - Math.max(0, root.wideT * 2 - 1))
                    // Định dạng: ghi chú máy đã đổi định dạng
                    Collapse {
                        width: parent.width
                        open: root.notes.length > 0
                        Item {
                            width: parent.width
                            height: formatFold.height + 12
                            ImportFold {
                                id: formatFold
                                objectName: "importFormat"
                                y: 12
                                width: parent.width
                                storageKey: "format"
                                title: "Định dạng"
                                summary: root.notes.length + " ghi chú"
                                Column {
                                    width: parent.width
                                    leftPadding: 12
                                    rightPadding: 12
                                    bottomPadding: 12
                                    spacing: 4
                                    Text {
                                        width: parent.width - 24
                                        text: "Máy đã đổi định dạng - chữ của truyện giữ nguyên"
                                        color: Theme.text
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeCaption
                                        font.weight: Theme.weightMedium
                                        textFormat: Text.PlainText
                                    }
                                    Repeater {
                                        model: root.notes.slice(0, 6)
                                        Text {
                                            required property string modelData
                                            width: parent.width - 24
                                            text: modelData
                                            color: Theme.text2
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeCaption
                                            textFormat: Text.PlainText
                                        }
                                    }
                                    Text {
                                        width: parent.width - 24
                                        visible: root.notes.length > 6
                                        text: "…và " + (root.notes.length - 6) + " ghi chú nữa."
                                        color: Theme.text2
                                        font.pixelSize: Theme.sizeCaption
                                    }
                                }
                            }
                        }
                    }
                    // Chú thích: đề xuất về chú thích trong sách (EPUB / DOCX)
                    Collapse {
                        width: parent.width
                        open: root.shownPreview !== null && Boolean(root.shownPreview.footnotes)
                        Item {
                            width: parent.width
                            height: noteFold.height + 12
                            ImportFold {
                                id: noteFold
                                objectName: "importFootnotes"
                                y: 12
                                width: parent.width
                                storageKey: "footnotes"
                                title: "Chú thích"
                                Column {
                                    id: noteBody
                                    width: parent.width
                                    readonly property var offer: root.shownPreview && root.shownPreview.footnotes ? root.shownPreview.footnotes : ({found: 0, marks: 0, examples: []})
                                    readonly property var said: Queue.footnoteSummary(offer)
                                    leftPadding: 12
                                    rightPadding: 12
                                    bottomPadding: 12
                                    Column {
                                        width: parent.width - 24
                                        topPadding: 12
                                        spacing: 2
                                        Text {
                                            width: parent.width
                                            text: noteBody.said.title + " - ABook không tự bỏ hay sửa chữ của truyện"
                                            color: Theme.text
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeCaption
                                            font.weight: Theme.weightMedium
                                            textFormat: Text.PlainText
                                        }
                                        Text {
                                            width: parent.width
                                            visible: text !== ""
                                            text: noteBody.said.example
                                            color: Theme.text2
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeCaption
                                            textFormat: Text.PlainText
                                        }
                                    }
                                    Collapse {
                                        width: parent.width - 24
                                        open: noteBody.offer.marks > 0
                                        ImportCheck {
                                            width: parent.width
                                            label: "Không đọc số chú thích"
                                            help: "Bỏ các con số như ² hay [3] khỏi phần đọc; lời chú không đổi."
                                            checked: root.footnotes.hideMarks
                                            enabled: root.busy === ""
                                            onToggled: value => root.reread({split: root.split, footnotes: {hideMarks: value, notes: root.footnotes.notes}})
                                        }
                                    }
                                    ImportCheck {
                                        width: parent.width - 24
                                        label: "Đọc lời chú ở cuối chương"
                                        help: "Mỗi lời chú nằm ở cuối chương có số gọi nó, kể cả khi trong sách nó nằm ở chương riêng."
                                        checked: root.footnotes.notes === "end"
                                        enabled: root.busy === ""
                                        onToggled: value => root.reread({split: root.split, footnotes: {hideMarks: root.footnotes.hideMarks, notes: value ? "end" : ""}})
                                    }
                                    ImportCheck {
                                        width: parent.width - 24
                                        label: "Bỏ lời chú"
                                        help: "Phần đọc không có lời chú nào. Bỏ tích để có lại."
                                        checked: root.footnotes.notes === "drop"
                                        enabled: root.busy === ""
                                        onToggled: value => root.reread({split: root.split, footnotes: {hideMarks: root.footnotes.hideMarks, notes: value ? "drop" : ""}})
                                    }
                                    Text {
                                        width: parent.width - 24
                                        topPadding: 4
                                        text: "Không tích gì thì sách giữ nguyên như trong file."
                                        color: Theme.text2
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeCaption
                                        textFormat: Text.PlainText
                                    }
                                }
                            }
                        }
                    }
                    // Gợi ý phần đọc: dòng ghi công người nghe có thể bỏ khỏi phần đọc
                    Collapse {
                        width: parent.width
                        open: root.groups.length > 0
                        Item {
                            width: parent.width
                            height: hintFold.height + 12
                            ImportFold {
                                id: hintFold
                                objectName: "importSuggestions"
                                y: 12
                                width: parent.width
                                storageKey: "suggestions"
                                title: "Gợi ý phần đọc"
                                summary: root.groups.length + " nhóm"
                                Column {
                                    width: parent.width
                                    leftPadding: 12
                                    rightPadding: 12
                                    bottomPadding: 12
                                    Text {
                                        width: parent.width - 24
                                        topPadding: 2
                                        text: "Dòng bỏ chỉ bị bỏ qua khi đọc; chữ của sách giữ nguyên."
                                        color: Theme.text2
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeCaption
                                        textFormat: Text.PlainText
                                    }
                                    Item {
                                        width: parent.width - 24
                                        height: 8 + hintList.height
                                        Flickable {
                                            id: hintList
                                            y: 8
                                            width: parent.width
                                            height: Math.min(160, hintColumn.height)
                                            contentWidth: width
                                            contentHeight: hintColumn.height
                                            clip: true
                                            boundsBehavior: Flickable.StopAtBounds
                                            Column {
                                                id: hintColumn
                                                width: hintList.width
                                                Repeater {
                                                    model: root.groups
                                                    ImportCheck {
                                                        required property var modelData
                                                        width: hintColumn.width
                                                        inView: y + 11 >= hintList.contentY && y + 31 <= hintList.contentY + hintList.height
                                                        label: "Bỏ dòng này khỏi phần đọc"
                                                        help: "“" + modelData.line + "” - " + Queue.where(modelData.chapters)
                                                        checked: root.skipped.indexOf(modelData.line) >= 0
                                                        enabled: root.busy === ""
                                                        onToggled: value => root.skipped = value ? root.skipped.concat([modelData.line]) : root.skipped.filter(line => line !== modelData.line)
                                                    }
                                                }
                                            }
                                            SmoothWheel { flick: hintList }
                                        }
                                        ScrollEdges { target: hintList; color: Theme.panel; x: hintList.x; y: hintList.y; width: hintList.width; height: hintList.height }
                                        Scrollbar { target: hintList }
                                    }
                                }
                            }
                        }
                    }
                    // Cuốn đã có trong thư viện
                    Collapse {
                        width: parent.width
                        open: root.known !== null
                        Text {
                            objectName: "importKnown"
                            width: parent.width
                            topPadding: 12 + 12
                            bottomPadding: 12
                            text: root.existing ? "Cuốn này đã có trong thư viện: “" + root.existing.title + "”."
                                : root.sameSource ? "Bạn đã thêm file này thành “" + root.sameSource.title + "” (" + root.sameSource.chapters + " chương)." : ""
                            color: Theme.accentText
                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                            font.pixelSize: Theme.sizeBodySmall
                            textFormat: Text.PlainText
                        }
                    }
                    // Đang thêm cả lô
                    Collapse {
                        width: parent.width
                        open: root.busy === "adding" && root.working !== "" && root.queue !== null
                        Item {
                            width: parent.width
                            height: adding.implicitHeight + 12
                            ImportSkeleton { id: adding; y: 12; width: parent.width; shape: "rows"; count: 1; label: "Đang thêm " + root.working }
                        }
                    }
                }
                Item {
                    id: reviewChapters
                    objectName: "importChapterColumn"
                    x: (reviewMeta.width + Theme.s32) * Math.min(1, root.wideT * 2)
                    y: (reviewMeta.height + Theme.s16) * (1 - Math.max(0, root.wideT * 2 - 1))
                    width: parent.width - x
                    height: chapterList.height + 8
                    ImportChapters {
                        id: chapterList
                        x: 0
                        y: 8
                        width: parent.width
                        chapters: root.shownPreview ? root.shownPreview.chapters : []
                        picked: root.picked
                        names: root.names
                        locked: root.busy !== ""
                        onPick: (index, on) => root.picked = on ? root.picked.concat([index]) : root.picked.filter(n => n !== index)
                        onRename: (chapter, value) => root.names = Queue.renameChapter(root.names, chapter, value)
                    }
                }
            }
        }
    }

    FileDialog {
        id: files
        title: "Chọn file sách (chọn được nhiều file một lúc)"
        fileMode: FileDialog.OpenFiles
        nameFilters: ["Sách (*.epub *.docx *.pdf *.txt *.abook *.abookproj)", "Tất cả file (*)"]
        onAccepted: {
            if (root.pickSession !== root.generation || !root.open) return
            root.startPicked(selectedFiles.map(file => Queue.itemFromPath(DesktopApi.localPath(file))))
        }
    }
    FolderDialog {
        id: folder
        title: "Chọn thư mục có các chương TXT"
        onAccepted: {
            if (root.pickSession !== root.generation || !root.open) return
            const picked = DesktopApi.localPath(selectedFolder)
            root.read({path: picked, name: Queue.fileName(picked)})
        }
    }
}
