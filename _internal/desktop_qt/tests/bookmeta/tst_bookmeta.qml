import "../../qml/UiStrings.js" as S
import QtQuick
import QtTest
import "../../qml" as Subject
import ABook
import "../width/ParityFixtures.js" as Fixture
import "../width/VisualReady.js" as VisualReady

Item {
    id: host
    width: 420
    height: 900
    FontLoader { id: regular; source: "../../fonts/BeVietnamPro-Regular.ttf" }
    FontLoader { id: medium; source: "../../fonts/BeVietnamPro-Medium.ttf" }
    FontLoader { id: bold; source: "../../fonts/BeVietnamPro-Bold.ttf" }
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: details; Subject.BookMetadataDetails {} }
    Component { id: card; Subject.BookCell {} }
    Component { id: editor; Subject.EditBook {} }
    Component { id: project; Subject.ProjectScreen {} }
    Component { id: page; Subject.BookPage {} }
    TestCase {
        name: "BookMetadata"
        when: windowShown
        function init() { Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme); Theme.reduceMotion = false }
        function capture(name) {
            const path = Qt.resolvedUrl("../../build/bookmeta/" + name + ".png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(host).save(path)
            verify(qtUiTree.save(path, host))
        }
        function initTestCase() { tryCompare(regular, "status", FontLoader.Ready); tryCompare(medium, "status", FontLoader.Ready); tryCompare(bold, "status", FontLoader.Ready) }
        property var book: ({bookId: "sample", title: "Hồ giấy", author: "Người Viết", illustrator: "Người Vẽ", altTitles: ["Paper Lake"], genres: ["Fantasy", "Adventure"], summary: "Một chiếc thuyền giấy trôi quanh hồ nhỏ. ".repeat(20) + "\n\nĐoạn cuối nguyên vẹn."})
        function test_detailsAndExpansion() {
            const value = createTemporaryObject(details, host, {width: 372, x: 24, y: 24, book: book})
            verify(value !== null)
            const closed = value.height
            capture("details-collapsed")
            value.expanded = true
            tryVerify(function() { return value.height > closed + 10 })
            VisualReady.waitSettled(this, value, qtVisualReady)
            verify(value.summary.endsWith("Đoạn cuối nguyên vẹn."))
            waitForRendering(host)
            capture("details")
            value.expanded = false
            tryCompare(value, "height", closed)
        }
        function test_authorCard() {
            const value = createTemporaryObject(card, host, {width: 180, x: 24, y: 24, coverWidth: 180, title: book.title, book: book})
            verify(value !== null)
            compare(findChild(value, "bookCellAuthor").text, book.author)
            verify(findChild(value, "bookCellAuthor").height > 0)
            // Dòng tình trạng như web / điện thoại, cả khi sách có tác giả; không lặp tác giả, không "…".
            const status = findChild(value, "bookCellSubtitle")
            value.book = Object.assign({}, book, {stage: "text", chaptersTotal: 3, chaptersAvailable: 0})
            compare(value.statusText, "3" + S.s_chuong_9e6a01dc)
            value.book = Object.assign({}, book, {stage: "done", complete: true, chaptersTotal: 2, chaptersAvailable: 2, duration: 7200,
                                                  progress: 0.5, listeningProgress: {heardSeconds: 3600}})
            verify(value.statusText.startsWith(S.s_con_71d0e2b2), value.statusText)
            value.book = Object.assign({}, book, {stage: "done", complete: true, chaptersTotal: 2, chaptersAvailable: 2, duration: 7200,
                                                  progress: 1, listeningProgress: {finished: true}})
            compare(value.statusText, S.s_da_nghe_xong_d276b702)
            compare(status.text, S.s_da_nghe_xong_d276b702)
            compare(status.elide, Text.ElideNone)
            verify(!status.truncated)
            value.subtitle = "2" + S.s_tap_269b0b3d
            compare(value.statusText, "2" + S.s_tap_269b0b3d)
            value.subtitle = ""
            waitForRendering(host)
            capture("card")
        }
        function test_longAuthorIsNeverCut() {
            // Tác giả là chữ người dùng: thu cỡ hay xuống dòng (OneLineFit), không bao giờ "…".
            const long = Object.assign({}, book, {author: "Người Viết Có Một Cái Tên Dài Hơn Cả Bề Ngang Của Bìa Sách"})
            const value = createTemporaryObject(card, host, {width: 180, x: 24, y: 24, coverWidth: 180, title: long.title, book: long})
            verify(value !== null)
            const author = findChild(value, "bookCellAuthor")
            compare(author.text, long.author)
            compare(author.elide, Text.ElideNone)
            verify(!author.truncated)
            verify(author.fit === "shrunk" || author.fit === "wrap", author.fit)
            verify(author.width <= 180)
        }
        function test_missingMetadata() {
            const value = createTemporaryObject(details, host, {width: 372, book: {}})
            compare(value.summary, "")
            compare(value.characters.length, 0)
        }
        function test_playerEditorContainsAllMetadataFields() {
            const value = createTemporaryObject(editor, host, {width: 1000, height: 900})
            verify(value !== null)
            value.begin(Object.assign({id: "sample"}, book))
            compare(value.metadataDraft.summary, book.summary)
            compare(value.metadataDraft.author, book.author)
            verify(!findChild(value, "editSaveMetadata").enabled)   // một nút "Lưu thông tin", khoá khi chưa đổi gì
            value.close()
        }
        function test_studioMetadataEditorOpens() {
            const value = createTemporaryObject(project, host, {width: 1000, height: 900})
            verify(value !== null)
            value.metadataProblem = "Lỗi của lần lưu trước"
            value.beginMetadata()
            compare(value.metadataDraft.summary, "")
            compare(value.metadataProblem, "")
        }
        function test_completeBookPageShowsMetadata() {
            const data = Object.assign(Fixture.playerBook(true), book, {id: "width"})
            WidthNet.setBook(data)
            DesktopApi.responses = {"/api/listen/books/width": {status: 200, data: data}}
            const value = createTemporaryObject(page, host, {width: 420, height: 900, book: {bookId: "width", title: book.title}})
            verify(value !== null)
            tryCompare(value, "loaded", true)
            VisualReady.waitSettled(this, value, qtVisualReady)
            capture("book-page")
            WidthNet.resetBooks()
        }
    }
}
