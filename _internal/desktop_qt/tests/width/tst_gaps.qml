import QtQuick
import QtTest
import "ModalLayer.js" as ModalLayer
import "VisualReady.js" as VisualReady
import ABook
import "../../qml/FindLogic.js" as Find
import "../../qml/BookLogic.js" as BookText

// Lỗ "chỉ web" của các màn ngoài Studio (docs/UI_PARITY_QT.md mục c): logic "Tìm trong sách" chép đủ ca của web listen/findText.test.ts (+ findStatus),
// dòng chữ phần đầu trang sách (BookScreen.tsx / LibraryScreen.tsx bookStatusText), rồi giao diện: hàng nút phụ Đọc / Tìm / Từ đầu / Thêm, hộp Tìm
// (nạp gộp search-texts, bàn phím, mở màn đọc đúng đoạn), "Nghe lại từ đầu" kèm "Quay lại chỗ cũ", "Không tìm thấy sách này", nút "Nghe ngay" của thẻ
// sách chỉ có chữ. Ảnh offscreen ghi ra build/d2shots/gaps_*.png.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: pageFactory; BookPage {} }
    Component { id: cellFactory; BookCell {} }

    // ---- logic thuần (findText.test.ts) ----
    TestCase {
        name: "FindLogic"
        function hitsOf(text, query) { return Find.findInSegments(1, [{text: text}], Find.foldedQuery(query)) }

        function test_foldsMarksAndCase() {
            compare(hitsOf("Anh Nguyễn bước vào.", "nguyen").length, 1)
            compare(hitsOf("Cô gặp ĐỨC TRÍ ở cổng.", "duc tri").length, 1)
            compare(hitsOf("Cô gặp ĐỨC TRÍ ở cổng.", "ĐỨC trí").length, 1)
            compare(hitsOf("Tran Nhan Tong", "Trần").length, 1)
            compare(hitsOf("Trần Nhân Tông", "tran nhan").length, 1)
            compare(hitsOf("Nguyễn Du", "nguyễn").length, 1)
            compare(hitsOf("Nguyẽn Du", "nguyễn").length, 1)        // chữ tổ hợp (NFD)
        }
        function test_whitespaceAndShortQuery() {
            compare(hitsOf("cuối\ncùng rồi", "cuoi cung").length, 1)
            compare(Find.foldedQuery("a"), "")
            compare(Find.foldedQuery("  an "), "an")
            compare(Find.foldedQuery("Đ"), "")
            compare(hitsOf("Anh Nguyễn bước vào.", "lan").length, 0)
        }
        function test_snippetMarksOriginalText() {
            const hit = hitsOf("Hôm đó anh Nguyễn Văn An bước vào quán.", "nguyen van")[0]
            compare(hit.snippet.match, "Nguyễn Văn")
            compare(hit.snippet.before, "Hôm đó anh ")
            compare(hit.snippet.after, " An bước vào quán.")
        }
        function test_longSnippetCutsAtWords() {
            const text = "mở đầu rất dài ".repeat(10) + "Nguyễn" + " phần đuôi cũng dài ".repeat(10)
            const snippet = hitsOf(text, "nguyen")[0].snippet
            verify(snippet.before.startsWith("…"))
            verify(snippet.after.endsWith("…"))
            compare(snippet.match, "Nguyễn")
            verify(snippet.before.length < 60)
            verify(snippet.after.length < 90)
        }
        function test_detachedMarkStaysInMatch() {
            const text = "xin chào Hanh́ nhé"
            const folded = Find.foldedText(text)
            const span = Find.originalSpan(text, folded, folded.indexOf("hanh"), 4)
            compare(text.slice(span[0], span[1]), "Hanh́")
            compare(JSON.stringify(Find.snippetOf("Một đoạn ngắn.", null)), JSON.stringify({before: "", match: "", after: "Một đoạn ngắn."}))
        }
        function test_sceneBreakSkippedSentenceIndexKept() {
            const segments = Find.paragraphs({segments: [{text: "Chương 7"}, {text: "Mở đầu yên ắng."}, {text: "***", sceneBreak: true}, {text: "Lan bước vào, gặp Nguyễn."}, {text: "Hết."}]})
            const hits = Find.findInSegments(7, segments, Find.foldedQuery("nguyen"))
            compare(hits.length, 1)
            compare(hits[0].sentence, 3)
            compare(Find.findInSegments(7, segments, Find.foldedQuery("***")).length, 0)
        }
        function test_textChapterParagraphsSkipLines() {
            const paragraphs = Find.paragraphs({text: "Nguồn: web\n\nĐoạn một.\nvẫn đoạn một.\n\n\nĐoạn hai."}, ["Nguồn: web"])
            compare(paragraphs.map(p => p.text), ["Đoạn một.\nvẫn đoạn một.", "Đoạn hai."])
        }
        function scanBook(texts, query, limit) {
            const needle = Find.foldedQuery(query)
            const state = {hits: [], total: 0, scanned: 0, chapters: texts.length, failed: 0, done: false}
            texts.forEach((text, i) => Find.scan(state, i + 1, text === null ? null : Find.prepare(Find.paragraphs({text: text})), needle, limit))
            state.done = true
            return state
        }
        function test_wholeBookOrderAndTotal() {
            const state = scanBook(["Chương 1\n\nTrời mưa. Nguyễn đi một mình.", "Chương 2\n\nKhông có ai ở đây.",
                                    "Chương 3\n\nNguyễn về nhà.\n\nNgười nhà tên Nguyên đã đợi.\n\nHết."], "nguyen")
            compare(state.total, 3)
            compare(JSON.stringify(state.hits.map(h => [h.chapterId, h.sentence])), JSON.stringify([[1, 1], [3, 1], [3, 2]]))
        }
        function test_limitCountsAllAndFailedChapters() {
            const many = []
            for (let i = 0; i < 30; ++i) many.push("Chương\n\nLan.\n\nLan nữa.")
            const state = scanBook(many, "lan", 25)
            compare(state.hits.length, 25)
            compare(state.total, 60)
            compare(Find.findStatus("lan", state, state.hits.length), "60 kết quả. Đang hiện 25 kết quả đầu, còn 35 kết quả - gõ thêm chữ để thu hẹp.")
            const broken = scanBook(["Lan.", null], "lan")
            compare(broken.failed, 1)
            compare(Find.findStatus("lan", broken, 1), "1 kết quả. 1 chương chưa đọc được nên chưa tìm trong đó.")
        }
        function test_statusTexts() {
            compare(Find.findStatus("", null, 0), "Gõ chữ hay câu cần tìm - không cần gõ dấu, hoa hay thường đều được.")
            compare(Find.findStatus("a", null, 0), "Gõ ít nhất 2 ký tự.")
            compare(Find.findStatus("an", null, 0), "Đang tìm…")
            compare(Find.findStatus("an", {hits: [], total: 1234, scanned: 3, chapters: 1200, failed: 0, done: false}, 0), "Đang tìm… đã xem 3/1.200 chương, thấy 1.234 chỗ.")
            compare(Find.findStatus(" Lan ", {hits: [], total: 0, scanned: 2, chapters: 2, failed: 0, done: true}, 0), "Không thấy “Lan” trong sách.")
            compare(Find.snippetHtml({before: "a<b", match: "c&d", after: ""}, "#fff", "#000"), "a&lt;b<span style=\"background-color:#fff;color:#000;font-weight:600\">c&amp;d</span>")
        }
    }

    // ---- dòng chữ phần đầu trang sách ----
    TestCase {
        name: "BookLogic"
        function book(extra) {
            return Object.assign({id: "b", stage: "audio", complete: true, producing: false, chaptersAvailable: 3, chaptersTotal: 5, duration: 7200,
                                  progress: {heardSeconds: 0, finished: false, caughtUp: false}, state: {}, chapters: [{id: 1}, {id: 2}]}, extra || {})
        }
        function test_statusLine() {
            compare(BookText.statusLine(book({stage: "text"}), true), "Chỉ có chữ · nghe bằng giọng đọc")
            compare(BookText.statusLine(book({stage: "text"}), false), "Chỉ có chữ · máy này chưa có giọng đọc")
            compare(BookText.statusLine(book(), false), "")
            compare(BookText.statusLine(book({complete: false, producing: true}), false), "Đang thu; chương mới tự hiện khi xong.")
            compare(BookText.statusLine(book({complete: false, remote: {computer: "laptop"}}), false), "Laptop còn đang làm, chương mới hiện ở đây khi xong")
            compare(BookText.statusLine(book({complete: false, remote: {}}), false), "Máy khác còn đang làm, chương mới hiện ở đây khi xong")
            compare(BookText.statusLine(book({complete: false, imported: true}), false), "Chưa đủ chương; mở file sách mới hơn để nghe tiếp.")
            compare(BookText.statusLine(book({complete: false}), false), "Chưa đủ chương; đang dừng thu.")
        }
        function test_progressLine() {
            compare(BookText.progressLine(book(), false, false), "Chưa nghe")
            compare(BookText.progressLine(book(), true, false), "Đang nghe")
            compare(BookText.progressLine(book(), true, true), "Chưa phát được")
            compare(BookText.progressLine(book({progress: {heardSeconds: 1800}}), false, false), "Đã nghe 30 phút · còn 1 giờ 30 phút chưa nghe")
            compare(BookText.progressLine(book({progress: {heardSeconds: 7200, finished: true}}), false, false), "Đã nghe xong")
            compare(BookText.progressLine(book({complete: false, producing: true, progress: {heardSeconds: 10, caughtUp: true}}), false, false), "Đã nghe hết phần đã có · 3/5 chương")
            compare(BookText.progressLine(book({remote: {computer: "Laptop"}, progress: {finished: true}}), false, false), "Trên Laptop · Đã nghe xong")
        }
        function test_lengthsAndReadLabel() {
            compare(BookText.formatLengthUp(129), "3 phút")
            compare(BookText.formatLengthUp(0), "0 phút")
            compare(BookText.progressText(book({progress: {heardSeconds: 3600}, state: {rate: 2}}), false), "Còn 30 phút")
            compare(BookText.progressText(book({stage: "text", author: "Nam Cao"}), true), "Nam Cao · 5 chương")
            compare(BookText.progressText(book({stage: "text"}), false), "Chỉ có chữ · 5 chương")
            compare(BookText.readLabel(book(), false), "Đọc")
            compare(BookText.readLabel(book({state: {reading: {chapterId: 2, index: 4}}}), false), "Đọc tiếp")
            compare(BookText.readLabel(book({state: {reading: {chapterId: 9, index: 4}}}), false), "Đọc")
            compare(BookText.readLabel(book({state: {reading: {chapterId: 2, index: 4}}}), true), "Đọc")
        }
    }

    // ---- giao diện ----
    TestCase {
        id: test
        name: "Gaps"
        when: windowShown
        property var page: null
        property var playerBefore: null
        property var server: ({})
        readonly property string longTitle: "Một cuốn sách có cái tên rất dài để thử xem nút chính và hàng nút phụ có giữ được hai mép thẳng nhau không"

        function reply(path, handler) { const r = DesktopApi.responses; r[path] = handler; DesktopApi.responses = r }
        function chapters() {
            return [{id: 1, index: 1, title: "Chương 1", fullTitle: "Chương 1 · Mưa", available: true, duration: 600},
                    {id: 2, index: 2, title: "Chương 2", fullTitle: "Chương 2 · Về nhà", available: true, duration: 600},
                    {id: 3, index: 3, title: "Chương 3", fullTitle: "Chương 3 · Hỏng", available: true, duration: 600}]
        }
        function init() {
            Theme.reduceMotion = true
            // "gaps" chỉ sống trong file này (bộ phát có thể đã tự nạp lại nó ở test trước): không coi là trạng thái cần trả lại.
            playerBefore = Player.loaded && Player.bookId !== "gaps" ? {id: Player.bookId, chapter: Player.chapterId} : null
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "fixture", dialogs: true}
            Api.loaded = true
            Api.notice = ""
            Api.voiceList = []
            Nav.layers = []
            WidthNet.setBook({id: "gaps", title: "Sách tìm chữ", complete: true, chapters: chapters(),
                              state: {chapters: {"2": {heard: 75, done: false, duration: 600}}, last: {chapterId: 2, seconds: 75, at: Date.now() / 1000 - 60}}})
            server = {id: "gaps", stage: "audio", title: "Sách tìm chữ", complete: true, producing: false, chaptersAvailable: 3, chaptersTotal: 3,
                      duration: 1800, progress: {heardSeconds: 75, fraction: 0.04, finished: false, caughtUp: false}, records: [],
                      capabilities: {workshop: false, toolchain: false, link: false}, state: {}, chapters: chapters()}
            reply("GET /api/listen/books/gaps", function() { return {status: 200, data: server} })
            reply("GET /api/listen/books/gaps/sessions", {status: 200, data: []})
            reply("GET /api/listen/books/gaps/search-texts?chapters=1,2,3", {status: 200, data: {chapters: [
                {id: 1, segments: [{text: "Chương 1"}, {text: "Trời mưa. Nguyễn đi một mình."}]},
                {id: 2, segments: [{text: "Chương 2"}, {text: "Nguyễn về nhà."}, {text: "***", sceneBreak: true}, {text: "Người nhà tên Nguyên đã đợi."}]},
                {id: 3, failed: true}]}})
            reply("GET /api/books/gaps/chapters/2/script", {status: 200, data: {segments: [
                {text: "Chương 2", start: 0}, {text: "Nguyễn về nhà.", start: 3}, {text: "***", sceneBreak: true}, {text: "Người nhà tên Nguyên đã đợi.", start: 9}]}})
        }
        function cleanup() {
            Nav.layers = []
            Theme.reduceMotion = false
            Theme.mode = "auto"
            Api.notice = ""
            Api.voiceList = []
            if (Player.loaded) Player.pause()
            WidthNet.resetBooks()
            if (playerBefore) {
                if (Player.loaded && Player.bookId === playerBefore.id) Player.jumpTo(playerBefore.chapter, 0)
                else {
                    if (Player.loaded) Player.close()      // mở không tự phát thì không đè cuốn đang nạp
                    Player.open(playerBefore.id, playerBefore.chapter, 0, false)
                }
                tryCompare(Player, "chapterId", playerBefore.chapter)
                Player.pause()
            }
            else if (Player.loaded) Player.close()
            if (page) page.destroy()
            page = null
            host.width = 1440
        }
        // gồm cả hộp / bảng nổi do `item` mở (WindowLayer nằm ở gốc cửa sổ, không còn là con của trang)
        function all(item, name) { return ModalLayer.findAll(item, name) }
        function one(item, name) { return all(item, name)[0] }
        function openPage(width, bookId, title) {
            host.width = width || 1440
            page = createTemporaryObject(pageFactory, host, {width: host.width, height: host.height, book: {bookId: bookId || "gaps", title: title || "Sách tìm chữ"}})
            verify(page !== null)
        }
        function ready() {
            openPage()
            tryVerify(function() { return page.fullBook.id === "gaps" && one(page, "bookActions").visible })
        }
        function shoot(name) {
            let before = null
            tryVerify(function() {
                const image = grabImage(VisualReady.grabTarget(host.Window.window, host))
                const same = before !== null && image.equals(before)
                before = image
                return same
            })
            const path = Qt.resolvedUrl("../../build/d2shots/gaps_" + name + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            before.save(path)
        }
        function shootBoth(name) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shoot(name + "_" + mode) } Theme.mode = "auto" }

        function test_secondaryRowLabelsAndStates() {
            ready()
            compare(one(page, "bookPrimary").text, "Nghe tiếp · Chương 2")
            compare(one(page, "bookProgressLine").text, "Đã nghe 1 phút · còn 29 phút chưa nghe")
            compare(one(page, "bookStatusLine").visible, false)
            const row = one(page, "bookSecondary")
            compare(row.Accessible.name, "Việc với sách")
            const read = one(page, "bookRead"), find = one(page, "bookFind"), restart = one(page, "bookRestart"), more = one(page, "bookMore")
            compare([read.label, find.label, restart.label, more.label], ["Đọc", "Tìm", "Từ đầu", "Thêm"])
            compare(find.Accessible.name, "Tìm chữ trong sách")
            compare(restart.Accessible.name, "Nghe lại từ đầu")
            compare(more.Accessible.name, "Thêm việc với sách")
            verify(restart.enabled)
            // Hai đầu hàng phụ thẳng hai mép của khung hàng (ít nhất 256, không hẹp hơn nút chính).
            const primary = one(page, "bookPrimary")
            fuzzyCompare(row.width, Math.max(256, primary.implicitWidth), 1)
            fuzzyCompare(more.mapToItem(row, more.width, 0).x, row.width, 1)
            fuzzyCompare(read.mapToItem(row, 0, 0).x, 0, 0.5)
            mouseClick(more)
            tryVerify(function() { return one(page, "bookMoreMenu").open })
            compare(one(page, "bookMoreMenu").Accessible.name, "Việc với sách")
            compare(Nav.layers.length, 1)
            Nav.back()
            tryVerify(function() { return !one(page, "bookMoreMenu").open })
            shootBoth("book")
        }
        function test_findInBookKeyboardAndReader() {
            ready()
            mouseClick(one(page, "bookFind"))
            const finder = one(page, "findInBook")
            tryVerify(function() { return finder.open })
            compare(finder.description, "Sách tìm chữ")
            const field = one(finder, "findQuery")
            tryVerify(function() { return field.activeFocus })
            compare(one(finder, "findStatus").text, "Gõ chữ hay câu cần tìm - không cần gõ dấu, hoa hay thường đều được.")
            field.text = "n"
            compare(one(finder, "findStatus").text, "Gõ ít nhất 2 ký tự.")
            field.text = "nguyen"
            tryVerify(function() { return finder.progress && finder.progress.done })
            compare(finder.hits.length, 3)
            compare(one(finder, "findStatus").text, "3 kết quả. 1 chương chưa đọc được nên chưa tìm trong đó.")
            compare(JSON.stringify(finder.hits.map(h => [h.chapterId, h.sentence])), JSON.stringify([[1, 1], [2, 1], [2, 3]]))
            // Một lần hỏi gộp cho cả ba chương.
            compare(DesktopApi.requests.filter(r => r.path.indexOf("/search-texts") >= 0).length, 1)
            const rows = all(finder, "findHit")
            compare(rows.length, 3)
            verify(one(rows[1], "findExcerpt").text.indexOf("font-weight:600\">Nguyễn</span>") >= 0)
            shootBoth("find")
            keyClick(Qt.Key_Down)
            verify(rows[0].activeFocus)
            keyClick(Qt.Key_Down)
            verify(rows[1].activeFocus)
            keyClick(Qt.Key_Up); keyClick(Qt.Key_Up)
            verify(field.activeFocus)
            // Gõ lại từ khoá: chữ đã nạp giữ trong hộp, không hỏi máy chủ lần nữa.
            field.text = "nguyen ve"
            tryVerify(function() { return finder.progress && finder.progress.done })
            compare(finder.hits.length, 1)
            compare(DesktopApi.requests.filter(r => r.path.indexOf("/search-texts") >= 0).length, 1)
            keyClick(Qt.Key_Return)
            tryVerify(function() { return !finder.open })
            const reader = one(page, "chapterReader")
            tryVerify(function() { return reader.open && reader.chapter && reader.chapter.id === 2 && !reader.loading })
            tryVerify(function() { return all(reader, "readerFound").length === 1 })
            compare(one(reader, "readerFound").text, "Nguyễn về nhà.")
            Nav.back()
            tryVerify(function() { return !reader.open })
            // Đóng hộp là thả chữ đã nạp: mở lại thì hỏi lại.
            mouseClick(one(page, "bookFind"))
            tryVerify(function() { return finder.open })
            compare(field.text, "")
            field.text = "nguyen"
            tryVerify(function() { return finder.progress && finder.progress.done })
            compare(DesktopApi.requests.filter(r => r.path.indexOf("/search-texts") >= 0).length, 2)
            Nav.back()
            tryVerify(function() { return !finder.open })
        }
        function test_findFallsBackToEachChapter() {
            reply("GET /api/listen/books/gaps/search-texts?chapters=1,2,3", {status: 409, data: {message: "Sách của máy khác: tìm từng chương"}})
            reply("GET /api/books/gaps/chapters/1/script", {status: 200, data: {segments: [{text: "Không có gì."}]}})
            reply("GET /api/books/gaps/chapters/3/script", {status: 503, data: {message: "Máy kia chưa trả lời."}})
            ready()
            mouseClick(one(page, "bookFind"))
            const finder = one(page, "findInBook")
            tryVerify(function() { return finder.open })
            one(finder, "findQuery").text = "nguyen"
            tryVerify(function() { return finder.progress && finder.progress.done })
            compare(finder.hits.length, 2)
            compare(finder.progress.failed, 1)
            verify(DesktopApi.requests.some(r => r.path === "/api/books/gaps/chapters/2/script"))
            compare(Api.notice, "")             // lỗi của từng chương không thành lời báo
        }
        // Bộ phát tự nạp lại cuốn nghe gần nhất (chính "gaps"): đóng nó để trang ở trạng thái "không đang nghe cuốn này".
        function notListening() {
            if (Player.loaded) Player.close()
            tryCompare(page, "listening", false)
        }
        function test_restartOffersWayBack() {
            ready()
            notListening()
            mouseClick(one(page, "bookRestart"))
            tryCompare(Player, "bookId", "gaps")
            compare(Player.chapterId, 1)
            compare(Api.notice, "Đang nghe lại từ đầu")
            compare(Api.noticeAction.label, "Quay lại chỗ cũ")
            Api.runNoticeAction()
            tryCompare(Player, "chapterId", 2)      // về chương cũ (sách thử không có audio nên vị trí trong chương không đo được)
        }
        function test_textOnlyBookReadsFirst() {
            WidthNet.setBook({id: "gaps", title: "Sách tìm chữ", complete: true, chapters: [{id: 1, title: "Chương 1", state: "text", available: false}]})
            server = Object.assign({}, server, {stage: "text", chapters: [{id: 1, title: "Chương 1", fullTitle: "Chương 1", state: "text"}], state: {reading: {chapterId: 1, index: 0}}})
            ready()
            notListening()
            compare(one(page, "bookPrimary").text, "Đọc tiếp")
            compare(one(page, "bookPrimary").icon, "book-open")
            compare(one(page, "bookStatusLine").text, "Chỉ có chữ · máy này chưa có giọng đọc")
            verify(!one(page, "bookRead").visible)
            verify(!one(page, "bookRestart").visible)
            verify(!one(page, "bookProgress").visible)
        }
        function test_missingBook() {
            reply("GET /api/listen/books/missing", {status: 404, data: {message: "Không có sách này"}})
            openPage(1440, "missing", "Sách đã xoá")
            const empty = one(page, "bookMissing")
            tryVerify(function() { return empty.visible && empty.opacity === 1 })
            compare(empty.title, "Không tìm thấy sách này")
            compare(empty.text, "Sách có thể đã bị chuyển sang thư mục khác hoặc bị xoá khỏi thư viện.")
            verify(!one(page, "bookStage").visible)
            verify(one(page, "bookMissingBack").visible)
        }
        function test_longTitleAt1024() {
            server = Object.assign({}, server, {title: longTitle})
            host.width = 1024
            page = createTemporaryObject(pageFactory, host, {width: 1024, height: host.height, book: {bookId: "gaps", title: longTitle}})
            tryVerify(function() { return page.fullBook.id === "gaps" && one(page, "bookActions").visible })
            const primary = one(page, "bookPrimary")
            verify(primary.width <= one(page, "bookInfo").width + 0.5)
            shootBoth("book_1024")
        }
        // Bố cục vừa (1024 trừ thanh bên): hàng nút phụ đứng cạnh nút chính, phần trên không cao hơn bìa.
        function test_mediumWidthKeepsChaptersRoom() {
            openPage(792)
            tryVerify(function() { return page.fullBook.id === "gaps" && one(page, "bookActions").visible })
            verify(!page.expanded)
            const primary = one(page, "bookPrimary")
            const row = one(page, "bookSecondary")
            const a = primary.mapToItem(page, 0, primary.height / 2)
            const b = row.mapToItem(page, 0, row.height / 2)
            fuzzyCompare(a.y, b.y, 1)
            verify(b.x >= a.x + primary.width)
            compare(one(page, "bookSummary").height, one(page, "bookCover").height)
            shootBoth("book_792")
        }
        function test_textCellSaysListenNow() {
            const cell = createTemporaryObject(cellFactory, host, {title: "Truyện chữ", book: {bookId: "t", stage: "text"}, playVisible: true})
            const play = one(cell, "libraryTilePlay")
            compare(play.icon, "book-open")
            compare(play.tip, "Đọc Truyện chữ")
            Api.voiceList = [{id: "vi-local"}]
            compare(play.icon, "play")
            compare(play.tip, "Nghe ngay Truyện chữ")
            cell.book = {bookId: "a", stage: "audio"}
            compare(play.tip, "Nghe Truyện chữ")
        }
    }
}
