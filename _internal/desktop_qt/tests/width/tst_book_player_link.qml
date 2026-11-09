import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook
import "ParityFixtures.js" as Fixture

// Trang sách và trình phát của cùng một cuốn nối nhau 1 chạm (DESIGN.md L3b, L3c): mỗi phép đo là đúng một mouseClick.
Item {
    id: host
    width: 1200; height: 900
    Component { id: bar; PlayerBar {} }
    Component { id: now; NowPlaying {} }
    Component { id: page; BookPage {} }
    SignalSpy { id: first }
    SignalSpy { id: second }
    TestCase {
        name: "BookPlayerLink"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.preferences = {}; Nav.layers = []
            Theme.reduceMotion = true
            WidthNet.setBook(Fixture.playerBook(false))
            DesktopApi.responses = {"/api/listen/books/width": {status: 200, data: Fixture.playerBook(false)}}
            Player.open("width", 1, 0, true); Player.pause()
            tryVerify(function() { return Player.loaded })
            first.clear(); second.clear()
        }
        function cleanup() { first.target = null; second.target = null; Nav.layers = []; Player.pause(); Theme.reduceMotion = false; WidthNet.resetBooks(); Player.open("width", 1, 0, false) }
        function click(item) {
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            verify(item !== null && item.visible)
            mouseClick(item)
        }
        function bookPage(width) {
            const made = createTemporaryObject(page, host, {book: {bookId: "width", title: "Miền đất", detail: "Giọng Đức Trí · 5 chương · 5 giờ 45 phút"}, width: width || 1000, height: 900})
            verify(made !== null)
            tryVerify(function() { return made.loaded })
            return made
        }

        function test_barBookNameOpensThePageNotThePlayer() {
            const made = createTemporaryObject(bar, host, {width: host.width})
            tryCompare(made, "appear", 1)
            first.signalName = "bookRequested"; first.target = made
            second.signalName = "openRequested"; second.target = made
            click(findChild(made, "playerBookLink"))
            compare(first.count, 1)
            compare(second.count, 0)
        }
        function test_barElsewhereStillOpensThePlayer() {
            const made = createTemporaryObject(bar, host, {width: host.width})
            tryCompare(made, "appear", 1)
            first.signalName = "bookRequested"; first.target = made
            second.signalName = "openRequested"; second.target = made
            click(findChild(made, "barChapterTitle"))
            compare(second.count, 1)
            compare(first.count, 0)
        }
        function test_bookNameInThePlayerRequestsThePage() {
            const made = createTemporaryObject(now, host, {width: host.width, height: host.height})
            made.show()
            tryVerify(function() { return made.visible && findChild(made, "playerBookLink").visible })
            first.signalName = "bookRequested"; first.target = made
            click(findChild(made, "playerBookLink"))
            compare(first.count, 1)
        }
        function test_morePageRowRequestsTheBookPage() {
            const made = createTemporaryObject(now, host, {width: host.width, height: host.height})
            made.show()
            tryVerify(function() { return made.visible && findChild(made, "nowMore").visible })
            click(findChild(made, "nowMore"))
            tryCompare(findChild(made, "nowMoreMenu"), "open", true)
            first.signalName = "bookRequested"; first.target = made
            click(findChild(made, "nowBookPage"))
            compare(first.count, 1)
            tryCompare(findChild(made, "nowMoreMenu"), "open", false)
        }
        function test_coverOfTheLoadedBookOpensThePlayer() {
            const made = bookPage()
            first.signalName = "nowPlayingRequested"; first.target = made
            click(findChild(made, "bookCoverOpen"))
            compare(first.count, 1)
        }
        function test_coverOfAnotherBookIsOnlyAPicture() {
            const made = createTemporaryObject(page, host, {book: {bookId: "other", title: "Sách khác"}, width: 1000, height: 900})
            verify(!findChild(made, "bookCoverOpen").visible)
        }
        function test_primaryResumesThenOpensThePlayer() {
            const made = bookPage()
            first.signalName = "nowPlayingRequested"; first.target = made
            click(findChild(made, "bookPrimary"))
            tryCompare(first, "count", 1)
        }
        function test_primaryPausesWithoutOpeningThePlayer() {
            const made = bookPage()
            Player.toggle()
            tryVerify(function() { return Player.playing })
            first.signalName = "nowPlayingRequested"; first.target = made
            click(findChild(made, "bookPrimary"))
            verify(!Player.playing)
            compare(first.count, 0)
        }
        function test_metaClustersWrapWhole() {
            const made = bookPage()
            const flow = findChild(made, "bookMeta")
            flow.width = 150
            tryVerify(function() { return flow.children.length >= 4 })
            const clusters = []
            for (const child of flow.children) if (child.detail !== undefined) clusters.push(child)
            compare(clusters.map(c => c.detail).join("|"), "Giọng Đức Trí|5 chương|5 giờ 45 phút")
            // Flow xếp lại ở lượt polish sau khi đổi bề ngang: chờ lượt ấy
            tryVerify(function() { return new Set(clusters.map(c => Math.round(c.y))).size >= 2 }, 2000, "bề ngang này phải làm dòng phụ xuống hàng")
            for (const cluster of clusters) fuzzyCompare(cluster.height, clusters[0].height, 1, cluster.detail + " phải nằm trọn một dòng")
        }
    }
}
