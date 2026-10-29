import QtQuick
import QtTest
import ABook

// Tab "Lịch sử" của trang sách (BookPage + HistoryList): khung chờ lúc hỏi (không nháy chữ "Chưa có lịch sử nghe"), trạng thái trống, danh sách gom theo ngày,
// tổng 7 ngày qua, "Nghe tiếp từ" mở trình phát đúng chỗ, chữ dài xuống dòng ở 1024 và 1920. Máy chủ giả: DesktopApi giả; trình phát là Player thật với mạng giả
// (cuốn "width" của WidthNet). Ảnh offscreen ghi ra build/d2shots/history_*.png.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: pageFactory; BookPage {} }

    TestCase {
        id: test
        name: "HistoryTab"
        when: windowShown

        property var page: null
        property var sessions: []
        property var playerBefore: null         // cuốn đang nạp trong Player lúc vào bài thử: các tệp thử sau dùng chung Player nên phải trả lại
        // 28/10/2026 15:00 giờ máy: mọi mốc của bài thử tính từ đây
        readonly property real now: new Date(2026, 9, 28, 15, 0, 0).getTime()

        function at(daysAgo, hour, minute) { return new Date(2026, 9, 28 - daysAgo, hour, minute, 0).getTime() / 1000 }
        function session(daysAgo, hour, minute, listened, from, to) {
            const start = at(daysAgo, hour, minute)
            return {id: "s" + daysAgo + hour + minute, startedAt: start, endedAt: start + listened, listened: listened,
                    from: {chapterId: from[0], seconds: from[1]}, to: {chapterId: to[0], seconds: to[1]}}
        }
        function fixture() {
            return [
                session(10, 9, 0, 600, [1, 0], [1, 600]),                 // quá 7 ngày: không tính vào tổng tuần
                session(1, 20, 5, 1200, [1, 600], [2, 30]),
                session(0, 13, 57, 1380, [2, 30], [2, 1410]),
                session(0, 14, 40, 0, [2, 1410], [2, 1410])               // cùng phút: một mốc giờ, không "14:40-14:40"
            ]
        }
        function workshopBook() {
            return {id: "width", stage: "audio", title: "Sách có lịch sử", author: "", cover: null, edits: 0,
                    capabilities: {workshop: false, toolchain: false, link: false},
                    chapters: [{id: 1, title: "Chương 1", fullTitle: "Chương 1", available: true}, {id: 2, title: "Chương 2", fullTitle: "Chương 2", available: true}]}
        }
        function reply(path, handler) { const r = DesktopApi.responses; r[path] = handler; DesktopApi.responses = r }
        function init() {
            Theme.reduceMotion = true
            playerBefore = Player.loaded ? {id: Player.bookId, chapter: Player.chapterId} : null
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "fixture", dialogs: true}
            Api.loaded = true
            Api.notice = ""
            Nav.layers = []
            sessions = fixture()
            reply("GET /api/listen/books/width", function() { return {status: 200, data: workshopBook()} })
            reply("GET /api/listen/books/width/sessions", function() { return {status: 200, data: sessions} })
        }
        function cleanup() {
            Nav.layers = []
            Theme.reduceMotion = false
            DesktopApi.delayed = false
            if (Player.loaded) Player.pause()
            WidthNet.resetBooks()
            if (playerBefore) {
                if (Player.loaded && Player.bookId === playerBefore.id) Player.jumpTo(playerBefore.chapter, 0)
                else Player.open(playerBefore.id, playerBefore.chapter, 0, false)
                tryCompare(Player, "chapterId", playerBefore.chapter)
                Player.pause()
            }
            else if (Player.loaded) Player.close()
            if (page) page.destroy()
            page = null
            host.width = 1440
        }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function settle() { wait(350) }
        function all(item, name, found) {
            const out = found || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children) all(child, name, out)
            return out
        }
        function openPage(width) {
            host.width = width || 1440
            page = createTemporaryObject(pageFactory, host, {width: host.width, height: host.height, book: {bookId: "width", title: "Sách có lịch sử"}})
            verify(page !== null)
            tryVerify(function() { return findChild(page, "bookTabs").visible })
            const history = findChild(page, "historyList")
            history.now = now
            return history
        }
        // Mở tab và mở hết các ngày (mặc định gập như web)
        function openHistory(width) {
            const history = openPage(width)
            findChild(page, "bookTabs").picked(1)
            tryCompare(history, "status", "ready")
            settle()
            for (const fold of all(history, "historyDay")) if (!fold.expanded) fold.expanded = true
            settle()
            return history
        }

        function test_tabOrderAndLazyLoad() {
            const history = openPage()
            compare(findChild(page, "bookTabs").labels.join("|"), "Chương|Lịch sử|Nhân vật")
            compare(calls("GET", "/api/listen/books/width/sessions").length, 0)      // chưa mở tab thì chưa hỏi
            findChild(page, "bookTabs").picked(1)
            tryCompare(history, "status", "ready")
            compare(calls("GET", "/api/listen/books/width/sessions").length, 1)
            findChild(page, "bookTabs").picked(0)
            findChild(page, "bookTabs").picked(1)
            tryCompare(history, "status", "ready")
            compare(calls("GET", "/api/listen/books/width/sessions").length, 2)      // mở lại thì hỏi lại, danh sách cũ vẫn hiện trong lúc chờ
            verify(history.hasSessions)
        }
        function test_loadingShowsSkeletonNotEmptyText() {
            DesktopApi.delayed = true
            const history = openPage()
            findChild(page, "bookTabs").picked(1)
            tryCompare(history, "status", "loading")
            settle()
            verify(findChild(history, "historySkeleton").visible)
            compare(findChild(history, "historySkeleton").Accessible.name, "Đang tải lịch sử")
            verify(!findChild(history, "historyEmpty").visible, "không được nháy 'Chưa có lịch sử nghe' khi còn đang hỏi")
            verify(!findChild(history, "historyContent").visible)
            DesktopApi.delayed = false
            DesktopApi.finish()
            tryCompare(history, "status", "ready")
            settle()
            verify(!findChild(history, "historySkeleton").visible)
            verify(findChild(history, "historyContent").visible)
            verify(!findChild(history, "historyEmpty").visible)
        }
        function test_emptyHistory() {
            sessions = []
            const history = openHistory()
            const empty = findChild(history, "historyEmpty")
            tryVerify(function() { return empty.visible })
            compare(empty.title, "Chưa có lịch sử nghe")
            verify(!findChild(history, "historyContent").visible)
            verify(!findChild(history, "historySkeleton").visible)
        }
        function test_failedHistoryShowsEmptyState() {
            reply("GET /api/listen/books/width/sessions", function() { return {status: 500, data: {error: "hỏng"}} })
            const history = openPage()
            findChild(page, "bookTabs").picked(1)
            tryCompare(history, "status", "failed")
            settle()
            verify(findChild(history, "historyEmpty").visible)
        }
        function test_listGroupedByDay() {
            const history = openHistory()
            const days = all(history, "historyDay")
            compare(days.length, 3)
            compare(days.map(day => day.title).join("|"), "Hôm nay|Hôm qua|" + history.groups[2].day)
            compare(days[0].summary, "2 lượt nghe")
            compare(days[1].summary, "1 lượt nghe")
            // mới nhất trước trong ngày
            const rows = all(days[0], "historySession")
            compare(rows.length, 2)
            compare(findChild(rows[0], "historyHeadline").text, "14:40 · 0 phút")
            compare(findChild(rows[1], "historyHeadline").text, "13:57-14:20 · 23 phút")
            compare(findChild(rows[1], "historyWhere").text, "Chương 2 0:30 → Chương 2 23:30")
            compare(findChild(rows[1], "historyResume").text, "Nghe tiếp từ 23:30")
            shot("history_list", host)
        }
        function test_removedChapterIsNamedAsSuch() {
            sessions = [session(0, 10, 0, 300, [9, 5], [2, 61])]
            const history = openHistory()
            compare(findChild(history, "historyWhere").text, "chương đã gỡ 0:05 → Chương 2 1:01")
        }
        function test_weekTotalTextAndName() {
            const history = openHistory()
            // 1200 + 1380 + 0 = 2580 giây -> 43 phút; lượt 10 ngày trước không tính
            compare(findChild(history, "historyWeekLength").text, "43 phút")
            compare(findChild(history, "historyWeek").Accessible.name, "7 ngày qua: 43 phút nghe cuốn này.")
        }
        function test_resumeOpensThePlayerAtTheEndOfTheSession() {
            WidthNet.setBook({id: "width", title: "Sách có lịch sử", complete: true, chapters: [
                {id: 1, index: 1, title: "Chương 1", fullTitle: "Chương 1", available: true, duration: 2000},
                {id: 2, index: 2, title: "Chương 2", fullTitle: "Chương 2", available: true, duration: 2000}]})
            const history = openHistory()
            const spy = createTemporaryObject(spyFactory, host, {target: history, signalName: "play"})
            const rows = all(history, "historySession")
            const resume = findChild(rows[1], "historyResume")
            resume.activated()
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0], 2)
            fuzzyCompare(spy.signalArguments[0][1], 1410, 0.001)
            tryCompare(Player, "bookId", "width")
            tryCompare(Player, "chapterId", 2)
        }
        Component { id: spyFactory; SignalSpy {} }

        // ---------- chữ dài xuống dòng, không cắt ----------
        function test_longChapterNamesWrap_data() { return [{tag: "1024", w: 1024}, {tag: "1920", w: 1920}] }
        function test_longChapterNamesWrap(data) {
            const longTitle = "Chương Một Trăm Hai Mươi Ba Của Một Hành Trình Dài Tưởng Như Không Bao Giờ Kết Thúc Giữa Rừng Sâu"
            reply("GET /api/listen/books/width", function() {
                const book = workshopBook()
                book.chapters[1].title = longTitle
                return {status: 200, data: book}
            })
            const history = openHistory(data.w)
            tryVerify(function() { return page.fullBook.id === "width" && page.fullBook.chapters[1].title === longTitle })
            settle()
            const where = all(history, "historyWhere")
            verify(where.length > 0)
            for (const line of where) {
                verify(line.paintedWidth <= line.width + 0.5, "dòng nơi nghe nhô ra ngoài: " + line.text + " painted=" + line.paintedWidth + " width=" + line.width + " visible=" + line.visible)
                fuzzyCompare(line.height, line.contentHeight, 1)
                const right = line.mapToItem(page, line.paintedWidth, 0).x
                verify(right <= page.width, "dòng nơi nghe nhô ra ngoài trang")
            }
            const wrapped = where.filter(line => line.text.indexOf(longTitle) >= 0)[0]
            verify(wrapped !== undefined)
            verify(wrapped.lineCount > 1, "tên chương dài phải xuống dòng")
            for (const button of all(history, "historyResume")) {
                const edge = button.mapToItem(page, button.width, 0).x
                verify(edge <= page.width)
            }
            shot("history_long_" + data.w, host)
        }

        function shot(name, item) {
            if (!item.Window.window) return
            item.Window.window.update()
            waitForRendering(item)
            wait(450)
            const img = grabImage(item)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
    }
}
