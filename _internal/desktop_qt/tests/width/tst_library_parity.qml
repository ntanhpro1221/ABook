import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook
import "../../qml/LibraryLogic.js" as Logic

Item {
    id: host
    width: 1024; height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: library; LibraryScreen {} }
    TestCase {
        name: "LibraryParity"
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function clickReady(item, x, y, button, modifiers, delay) {
            ready()
            mouseClick(item, x, y, button, modifiers, delay)
        }
        when: windowShown
        property var fixture: [
            {bookId: "a", title: "Miền đất · Tập 10", author: "Đặng An", narrator: "Đức Trí", progress: 0.2, listeningProgress: {heardSeconds: 10}, state: {last: {at: 2}}, addedAt: 2},
            {bookId: "b", title: "Miền đất · Tập 2", author: "Bình", progress: 1, listeningProgress: {finished: true}, addedAt: 4, source: "Máy của bạn"},
            {bookId: "c", title: "Cuốn mới", stage: "text", addedAt: 3}
        ]
        function init() { Theme.reduceMotion = false; Nav.layers = []; Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme) }
        function cleanup() { Nav.layers = []; Theme.reduceMotion = false }
        function test_filters_search_sort() {
            compare(fixture.filter(b => Logic.matches(b, "listening", "")).length, 1)
            compare(fixture.filter(b => Logic.matches(b, "finished", "")).length, 1)
            compare(fixture.filter(b => Logic.matches(b, "new", "")).length, 1)
            verify(Logic.matches(fixture[0], "all", "dang an"))
            verify(Logic.matches(fixture[0], "all", "duc tri"))
            verify(!Logic.matches(fixture[0], "new", "duc tri"))
            compare(Logic.sort(fixture, "title").map(b => b.bookId).join(), "c,b,a")
            compare(Logic.sort(fixture, "added")[0].bookId, "b")
            compare(Logic.sort(fixture, "author")[2].bookId, "c")
            compare(Logic.listening(fixture, "c").bookId, "c")
            compare(Logic.listening(fixture, "").bookId, "a")
            compare(Logic.listening(fixture, "b").bookId, "a")
            compare(Logic.otherBooks([
                {bookId: "current", chaptersAvailable: 2}, {bookId: "done", chaptersAvailable: 2, listeningProgress: {finished: true}},
                {bookId: "caught", chaptersAvailable: 2, listeningProgress: {caughtUp: true}}, {bookId: "next", chaptersAvailable: 2},
                {bookId: "text", stage: "text", chaptersAvailable: 0}, {bookId: "new", chaptersAvailable: 2},
                {bookId: "older", chaptersAvailable: 2, state: {last: {at: 2}}}, {bookId: "recent", chaptersAvailable: 2, state: {last: {at: 3}}}
            ], "current", "next").map(b => b.bookId).join(), "recent,older,new")
        }
        function test_series_identity() {
            const groups = Logic.sections(fixture)
            compare(groups.length, 2); compare(groups[0].books.map(b => b.bookId).join(), "b,a")
            verify(groups[0].remote)
            const chain = Logic.sections([{bookId: "root", title: "Ban đầu"}, {bookId: "next", title: "Tên khác", series: {root: "root", part: 2}}, {bookId: "other", title: "Ban đầu · Phần 3"}])
            compare(chain.length, 2); compare(chain[0].books.length, 2)
            const ambiguous = Logic.sections([{bookId: "x", title: "Bộ"}, {bookId: "y", title: "Bộ"}, {bookId: "z", title: "Bộ · Tập 2"}])
            compare(ambiguous.length, 3)
        }
        function test_controls_and_back() {
            const page = createTemporaryObject(library, host, {width: host.width, height: host.height})
            verify(page)
            const find = findChild(page, "librarySearch")
            clickReady(find); tryVerify(function() { return (Nav.layers.length) === (1) })
            const field = findChild(page, "librarySearchField")
            field.text = "khong co"; tryCompare(page, "count", 0)
            Nav.back(); tryCompare(page, "query", ""); tryVerify(function() { return (Nav.layers.length) === (0) })
            clickReady(findChild(page, "filter_finished")); tryCompare(page, "filter", "finished")
            clickReady(findChild(page, "librarySort")); tryVerify(function() { return (Nav.layers.length) === (1) })
            ready(); keyClick(Qt.Key_Down); keyClick(Qt.Key_Return); tryCompare(page, "sortOrder", "title"); tryVerify(function() { return (Nav.layers.length) === (0) })
            tryVerify(function() { return findChild(page, "librarySort").activeFocus })
            page.destroy()
        }
        function test_live_results_and_series() {
            const page = createTemporaryObject(library, host, {width: host.width, height: host.height})
            page.books = fixture
            tryCompare(page, "count", 2)
            page.activate(0); tryVerify(function() { return findChild(page, "librarySeries").open }); tryVerify(function() { return (Nav.layers.length) === (1) })
            Nav.back(); tryVerify(function() { return (Nav.layers.length) === (0) })
            page.filter = "finished"; tryCompare(page, "count", 1)
            tryVerify(function() { return (page.filtered[0].bookId) === ("b") })
            page.query = "zzzz"; tryCompare(page, "count", 0)
            page.destroy()
        }
        function test_filter_motion_keyboard_and_refresh_preserves_scroll() {
            const page = createTemporaryObject(library, host, {width: 792, height: 700})
            tryVerify(function() { return page.list.count > 0 }); ready(); page.list.contentY = 400; const before = page.list.contentY
            Backend.library.revision++; tryVerify(function() { return Math.abs((page.list.contentY) - (before)) <= 1 })
            page.list.forceActiveFocus(); keyClick(Qt.Key_Right); compare(page.current, 1)
            Theme.reduceMotion = false
            page.filter = "finished"; tryVerify(function() { return page.resultsOpacity > 0 && page.resultsOpacity < 1 })
            tryCompare(page, "count", 0)
            page.destroy()
        }
    }
}
