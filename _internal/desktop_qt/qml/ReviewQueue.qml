import QtQuick
import ABook
import "ReviewLogic.js" as R
import "WorkLogic.js" as W

// Tab "Cần nghe lại" (ReviewQueue.tsx, webui/reviews.py): câu mà khâu tự kiểm tra không chắc. Nghe từng câu, bấm Ổn hoặc Cần thu lại. "Cần thu lại" ghi một yêu cầu cho dây chuyền:
// câu được thu lại bằng hạt giống MỚI ở lần chạy tới (sách đã xong thì nút "Áp dụng thay đổi" ở trang dự án). Lỗi đọc sai chữ / tên thì sửa ở Kịch bản - thu lại y chữ không chữa được.
// Danh sách tải theo trang (con trỏ), hỏi lại định kỳ khi sách đang chạy; phán quyết hiện ngay rồi hỏi lại máy chủ. "Nghe liền": phát lần lượt mọi câu nghe được, phán bằng phím O / R.
Item {
    id: root
    objectName: "reviewQueue"
    property var work: null
    property bool active: false
    property string filter: "todo"
    property bool showMinor: false
    property var pages: []                      // các trang đã tải; [0] là trang đầu
    property bool fetchingNext: false
    property int generation: 0
    property bool continuous: false
    property string playingId: ""
    property int playingIndex: 0
    property string focusAfter: ""
    property string lastRedo: ""
    signal openScript(int chapterId, string stableId)
    signal revealRequested(var row)

    readonly property string empty: "empty"
    readonly property var book: work ? work.book : null
    readonly property string bookId: work ? work.bookId : ""
    readonly property var view: pages.length === 0 ? null : {
        counts: pages[0].counts || ({}),
        pending: pages[0].pending || 0,
        redoChapters: pages[0].redoChapters || [],
        items: pages.reduce(function(all, page) { return all.concat(page.items || []) }, []),
        nextCursor: pages[pages.length - 1].nextCursor || null,
        remaining: pages[pages.length - 1].remaining || 0
    }
    readonly property bool unrecorded: R.notRecordedYet(book ? book.segments : null)
    readonly property var items: view ? view.items.filter(function(item) { return filter === "todo" ? !R.handled(item) : R.handled(item) }) : []
    readonly property int playableCount: items.filter(function(item) { return rowClip(item) !== null }).length
    readonly property int minor: view ? R.minorCount(view.counts) : 0
    readonly property bool wide: width >= 760
    readonly property bool keysOn: visible && Nav.uiVisible && !Nav.popupOpen && Api.preferences.letterShortcuts !== false
    readonly property bool judging: keysOn && continuous && !typing()
    readonly property var lead: view ? R.leadLine(view, unrecorded) : ({strong: "", rest: ""})
    readonly property var query: first
    width: parent ? parent.width : 600
    height: stack.height

    function rowClip(item) { return work && work.store ? R.clipOf(item, bookId, work.store.path) : null }
    function pathFor(cursor) {
        return work.path("/review?filter=" + filter + (showMinor ? "&all=1" : "") + (cursor ? "&cursor=" + encodeURIComponent(cursor) : ""))
    }
    function typing() {
        const focus = Window.window ? Window.window.activeFocusItem : null
        return Boolean(focus) && typeof focus.cursorPosition === "number"
    }
    function indexOfId(id) {
        for (let i = 0; i < items.length; ++i) if ("review-" + items[i].segmentId === id) return i
        return -1
    }

    // ---- tải và phân trang ----
    StudioQuery {
        id: first
        store: root.work ? root.work.store : null
        path: root.work && root.bookId !== "" ? root.pathFor("") : ""
        wanted: root.active && root.work !== null && root.bookId !== ""
        interval: root.work ? root.work.producing : 0
        onLoaded: answer => root.adopt(answer)
        onDataChanged: if (data === null) { root.generation++; root.pages = []; root.fetchingNext = false }
    }
    Connections {
        target: root.work
        ignoreUnknownSignals: true
        function onReviewChanged() { first.invalidate() }
    }
    // Trang đầu vừa hỏi lại: các trang đã nạp thêm cũng hỏi lại theo con trỏ (refetch của useInfiniteQuery), xong mới thay
    function adopt(answer) {
        const extra = pages.length - 1
        const mine = ++generation
        fetchingNext = false
        if (extra <= 0 || !answer.nextCursor) { pages = [answer]; return }
        const result = [answer]
        function more(cursor) {
            if (result.length > extra || !cursor) { if (mine === root.generation) root.pages = result; return }
            work.store.request("GET", root.pathFor(cursor), null, function(status, page) {
                if (mine !== root.generation) return
                if (root.work.ok(status) && page) { result.push(page); more(page.nextCursor) } else root.pages = result
            })
        }
        more(answer.nextCursor)
    }
    function loadNext() {
        const last = pages.length ? pages[pages.length - 1] : null
        if (!last || !last.nextCursor || fetchingNext) return
        fetchingNext = true
        const mine = generation
        work.store.request("GET", pathFor(last.nextCursor), null, function(status, page) {
            if (mine !== root.generation) return
            root.fetchingNext = false
            if (!root.work.ok(status) || !page) { root.work.fail("Chưa tải thêm được câu", status, page); return }
            root.pages = root.pages.concat([page])
        })
    }
    function refresh() { first.invalidate(); work.afterReview() }

    // ---- phán quyết ----
    function setVerdict(stableId, value) {
        pages = pages.map(function(page) {
            return Object.assign({}, page, {items: (page.items || []).map(function(item) { return item.stableId === stableId ? Object.assign({}, item, {verdict: value}) : item })})
        })
    }
    function neighbour(index) {
        const near = items[index + 1] || items[index - 1]
        return near ? near.stableId : empty
    }
    function judge(item, value) {
        const index = items.findIndex(function(current) { return current.stableId === item.stableId })
        if (index < 0) return                   // hàng đang ra chỉ giữ hình, không được gửi thêm phán quyết
        // Câu vừa phán rời danh sách đang lọc: đưa tiêu điểm sang câu kế (hay câu trước), đừng để nó rơi về đầu trang
        const leaves = filter === "todo" ? value !== null : value === null
        if (leaves) { focusAfter = neighbour(index); Qt.callLater(root.settleFocus) }
        setVerdict(item.stableId, value)
        work.saveVerdict(item, value, function() {})
    }
    function spoken(item) {
        const index = items.findIndex(function(current) { return current.stableId === item.stableId })
        focusAfter = neighbour(index)
        Qt.callLater(root.settleFocus)
        refresh()
    }

    // ---- tiêu điểm ----
    function findRow(key) {
        let found = null
        function walk(node) {
            if (found) return
            for (const child of node.children) {
                if (child.objectName === "reviewRow" && child.key === key) { found = child; return }
                walk(child)
            }
        }
        walk(stack)
        return found
    }
    function settleFocus() {
        const key = focusAfter
        focusAfter = ""
        if (key === "") return
        if (key === empty) { emptyBlock.forceActiveFocus(); return }
        const row = findRow(key)
        if (row) { row.focusFirst(); revealRequested(row) }
    }

    // ---- nghe liền ----
    function playAt(from) {
        let next = null
        let source = null
        for (let i = Math.max(from, 0); i < items.length && !next; ++i) {
            source = rowClip(items[i])
            if (source) next = items[i]
        }
        if (!next) {
            continuous = false
            work.say("Đã nghe hết các câu trong danh sách")
            return
        }
        Clip.toggle("review-" + next.segmentId, source.src, source.start, source.end)
        const row = findRow(next.stableId)
        if (row) revealRequested(row)
    }
    function heardClip() {
        const now = Clip.current
        const was = playingId
        if (now.indexOf("review-") === 0) { playingId = now; playingIndex = Math.max(indexOfId(now), 0); return }
        playingId = ""
        if (!continuous || now !== "" || was === "") return
        // Câu vừa nghe còn trong danh sách thì sang câu sau nó; đã phán (rời danh sách) thì câu sau dồn lên đúng chỗ ấy
        const still = indexOfId(was)
        playAt(still >= 0 ? still + 1 : playingIndex)
    }
    Connections { target: Clip; function onCurrentChanged() { root.heardClip() } }
    function judgePlaying(value) {
        const index = indexOfId(playingId)
        if (index < 0) return
        judge(items[index], value)
        Clip.stop()                             // sang câu kế ngay (heardClip bắt lúc clip dừng)
    }
    Shortcut { sequences: ["O"]; enabled: root.judging; onActivated: root.judgePlaying("ok") }
    Shortcut { sequences: ["R"]; enabled: root.judging; onActivated: root.judgePlaying("redo") }

    onViewChanged: if (view && view.redoChapters.length > 0) lastRedo = R.redoLine(view.redoChapters.length)

    Column {
        id: stack
        width: parent.width
        EditBookSkeleton {
            objectName: "reviewSkeleton"
            visible: first.loading
            width: parent.width
            y: 24
            shape: "rows"
            count: 4
            label: "Đang tải câu nghe"
        }
        EditBookError {
            objectName: "reviewError"
            width: parent.width
            open: first.error !== null && root.view === null
            message: "Bạn hãy kiểm tra kết nối rồi tải lại câu cần nghe."
            onRetry: first.load()
        }
        Column {
            id: content
            objectName: "reviewContent"
            visible: root.view !== null
            width: parent.width
            Item { width: 1; height: 16 }
            Flow {
                width: parent.width
                spacing: 12
                Text {
                    objectName: "reviewLead"
                    width: Math.min(implicitWidth, parent.width)
                    textFormat: Text.RichText
                    text: (root.lead.strong !== "" ? "<b><span style=\"color:" + W.cssColor(Theme.text) + "\">" + W.esc(root.lead.strong) + "</span></b>" : "") + W.esc(root.lead.rest)
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                ChoiceRow {
                    objectName: "reviewFilter"
                    label: "Lọc"
                    value: root.filter
                    options: [{value: "todo", label: "Chưa xem"}, {value: "done", label: "Đã xem"}]
                    onPicked: value => { root.filter = value }
                }
            }
            Collapse {
                objectName: "reviewListen"
                width: parent.width
                open: root.playableCount > 1 || root.continuous
                Flow {
                    width: parent.width
                    topPadding: 12
                    spacing: 12
                    Button {
                        objectName: root.continuous ? "reviewStopAll" : "reviewListenAll"
                        size: "sm"
                        kind: "ghost"
                        icon: root.continuous ? "square" : "list-music"
                        text: root.continuous ? "Dừng nghe liền" : "Nghe liền " + root.playableCount + " câu"
                        onClicked: {
                            if (root.continuous) { root.continuous = false; Clip.stop() }
                            else { root.continuous = true; root.playAt(0) }
                        }
                    }
                    Row {
                        objectName: "reviewHint"
                        visible: root.continuous && root.wide
                        height: 40
                        spacing: 6
                        Text { anchors.verticalCenter: parent.verticalCenter; text: "Đang nghe liền:"; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                        LookKbd { anchors.verticalCenter: parent.verticalCenter; text: "O" }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: "Ổn ·"; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                        LookKbd { anchors.verticalCenter: parent.verticalCenter; text: "R" }
                        Text { anchors.verticalCenter: parent.verticalCenter; text: "Cần thu lại - rồi sang câu kế"; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                    }
                }
            }
            Collapse {
                objectName: "reviewRedo"
                width: parent.width
                open: root.view !== null && root.view.redoChapters.length > 0
                Column {
                    width: parent.width
                    Item { width: 1; height: 12 }
                    Text {
                        objectName: "reviewRedoLine"
                        width: parent.width
                        topPadding: 10
                        text: root.lastRedo
                        color: Theme.danger
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    MoreInfo {
                        width: parent.width
                        Text { width: parent.width; text: "Chạy tiếp hoặc Áp dụng thay đổi để thu lại."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
                    }
                }
            }
            Item { width: 1; height: 12 }
            StudioRows {
                objectName: "reviewRows"
                width: parent.width
                items: root.items
                keyField: "stableId"
                delegate: rowDelegate
            }
            // Hết việc: nói thẳng vì sao (chưa có bản thu / đã xem hết / chưa đánh dấu câu nào)
            Collapse {
                objectName: "reviewEmptyBlock"
                width: parent.width
                open: root.view !== null && root.items.length === 0
                Item {
                    id: emptyBlock
                    objectName: "reviewEmpty"
                    width: parent.width
                    height: emptyState.height + 16
                    EmptyState {
                        id: emptyState
                        y: 16
                        width: parent.width
                        topPadding: 40
                        bottomPadding: 40
                        icon: "shield-check"
                        title: R.emptyTitle(root.filter, root.unrecorded)
                        text: R.emptyText(root.filter, root.unrecorded)
                    }
                }
            }
            Collapse {
                width: parent.width
                open: root.view !== null && root.view.nextCursor !== null
                Item {
                    width: parent.width
                    height: 16 + more.height
                    Button {
                        id: more
                        objectName: "reviewMore"
                        y: 16
                        kind: "ghost"
                        enabled: !root.fetchingNext
                        text: R.loadMoreText(root.view ? root.view.remaining : 0, root.fetchingNext)
                        onClicked: root.loadNext()
                    }
                }
            }
            Collapse {
                width: parent.width
                open: root.minor > 0
                Item {
                    width: parent.width
                    height: 16 + minorToggle.height
                    TextLink {
                        id: minorToggle
                        objectName: "reviewMinor"
                        y: 16
                        text: (root.showMinor ? "Ẩn " : "Hiện ") + root.minor + " câu nhẹ"
                        onClicked: root.showMinor = !root.showMinor
                    }
                }
            }
            Item { width: 1; height: 24 }
        }
    }

    Component {
        id: rowDelegate
        ReviewRow {
            property var modelData: ({})
            work: root.work
            item: modelData || ({})
            twins: R.twinsOf(root.items, item)
            onVerdict: value => root.judge(item, value)
            onOpenScript: (chapterId, stableId) => root.openScript(chapterId, stableId)
            onSpoken: root.spoken(item)
        }
    }
}
