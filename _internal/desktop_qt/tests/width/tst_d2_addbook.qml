import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Hộp "Thêm sách" (AddBook.qml): hành vi (xem trước -> thêm, đổi tên chương, hàng nhiều file, hỏi khi đóng, lỗi + thử lại, không mở lại sau khi huỷ) và ảnh
// offscreen sáng + tối ở 1440 x 900 và 760 hẹp (build/d2shots/addbook_*.png, hàm shot() như tst_d2_shots.qml). Dữ liệu giả đặt vào DesktopApi giả.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Item { id: narrowHost; width: 760; height: 900; clip: true; Rectangle { anchors.fill: parent; color: Theme.bg } }
    Component { id: addFactory; AddBook {} }
    Component { id: libraryFactory; LibraryScreen {} }

    TestCase {
        id: test
        name: "D2AddBook"
        when: windowShown

        property var opened: []
        function init() {
            Theme.reduceMotion = false
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "fixture"}
            Api.loaded = true
            Api.notice = ""
            Nav.layers = []
            Platform.reset()
            opened = []
        }
        function cleanup() { DesktopApi.delayed = false; Nav.layers = []; Theme.mode = "auto"; Theme.reduceMotion = false }

        function make(props, parentItem) {
            const into = parentItem || host
            const item = createTemporaryObject(addFactory, into, Object.assign({width: into.width, height: into.height}, props || {}))
            verify(item !== null)
            item.openBook.connect(id => opened.push(id))
            return item
        }
        function find(item, name) { return findChild(item, name) }
        function findButton(item, text) {
            if (item.text === text && item.kind !== undefined && item.visible && item.width > 0) return item
            for (const child of item.children || []) { const found = findButton(child, text); if (found) return found }
            return null
        }
        function allText(item, out) {
            out = out || []
            if (item.visible === false) return out
            if (item.text !== undefined && item.visible !== false) out.push(String(item.text))
            for (const child of item.children || []) allText(child, out)
            return out
        }
        function chapters(count, lengthy) {
            const rows = []
            for (let i = 1; i <= count; ++i) {
                const row = {index: i, title: lengthy ? "Chương " + i + ": " + "Cuộc gặp gỡ bất ngờ ở bến sông cũ ".repeat(3) : "Chương " + i, firstLine: i % 3 === 0 ? "Dòng đầu của chương " + i + " là một câu khá dài để thử xuống dòng." : "", words: 800 + i * 137, chars: 0}
                if (i === 1) { row.included = false; row.short = true; row.title = "Bìa"; row.words = 12 }
                if (i === 2 && count > 5) { row.included = false; row.matter = "Mục lục" }
                rows.push(row)
            }
            return rows
        }
        function book(extra) {
            return Object.assign({title: "Tên sách", author: "Tác giả", sourceFingerprint: "fp-1", chapters: chapters(6), totals: {chapters: 6, words: 9000}, notes: [], hasCover: false}, extra || {})
        }
        // Mỗi file một đáp riêng theo đường dẫn
        function previews(map) {
            return function(body) {
                const data = map[body.path] || map["*"]
                if (data && data.__error) return {status: 500, data: {error: data.__error}}
                return {status: 200, data: data}
            }
        }
        function importCalls() { return DesktopApi.requests.filter(r => r.path === "/api/listen/import") }
        function previewCalls() { return DesktopApi.requests.filter(r => r.path === "/api/listen/import/preview") }
        function pick(item, path) { return Object.assign({}, item, {path: path}) }

        // ---- Hành vi ----
        function test_stepsAndPayload() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}, "/api/listen/import": {status: 200, data: {id: "new-id", how: "new"}}}
            const dialog = make()
            dialog.begin(["D:/x/Truyện.epub"])
            compare(dialog.step, "review")
            compare(dialog.title, "Thêm sách")
            compare(dialog.picked.join(), "3,4,5,6")      // bìa và mục lục chưa tích
            compare(previewCalls().length, 1)
            compare(previewCalls()[0].body.splitChapters, false)
            compare(find(dialog, "importTotals").text, "4 / 6 chương")
            dialog.names = {3: "Tên mới của chương ba"}
            dialog.add(false)
            const call = importCalls()[0]
            compare(call.body.path, "D:/x/Truyện.epub")
            compare(call.body.title, "Tên sách")
            compare(call.body.sourceFingerprint, "fp-1")
            compare(call.body.separate, false)
            compare(call.body.chapters.map(c => c.index).join(), "3,4,5,6")
            compare(call.body.chapters[0].title, "Tên mới của chương ba")
            compare(call.body.chapters[1].title, undefined)
            compare(call.body.footnotes, undefined)
            compare(Api.notice, "Đã thêm sách vào thư viện")
            compare(opened.join(), "new-id")
            verify(!dialog.open)
        }

        function activeField(item) {
            let found = null
            const walk = function(node) {
                if (node.objectName === "importRenameField" && node.visible) found = node
                for (const c of node.children || []) walk(c)
            }
            walk(item)
            return found
        }
        function test_renameIsABackLayerAndTitleKeepsDrafts() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}, "/api/listen/import": {status: 200, data: {id: "n", how: "new"}}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            const list = find(dialog, "importChapters")
            list.startEdit(3)
            compare(list.editing, 3)
            verify(Nav.layers[Nav.layers.length - 1] === list.backLayer)
            tryVerify(function() { return activeField(dialog) !== null })
            const field = activeField(dialog)
            field.text = "Tên chương bị huỷ"
            verify(Nav.back())                      // Back huỷ việc gõ, về hộp
            compare(list.editing, -1)
            verify(dialog.open)
            compare(dialog.names[3], undefined)
            list.startEdit(3)
            tryVerify(function() { return activeField(dialog) !== null })
            activeField(dialog).text = "  Tên   chương  mới "
            activeField(dialog).accepted()
            compare(list.editing, -1)
            compare(dialog.names[3], "Tên chương mới")
            find(dialog, "importTitle").text = "Tên sách sửa lần hai"
            compare(dialog.names[3], "Tên chương mới")      // sửa tên sách không làm mất tên chương đã đổi
            dialog.add(false)
            const call = importCalls()[0]
            compare(call.body.title, "Tên sách sửa lần hai")
            compare(call.body.chapters.filter(c => c.index === 3)[0].title, "Tên chương mới")
            compare(call.body.chapters.length, 4)
        }
        function test_excludedChaptersAndNothingPicked() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            find(dialog, "importChapters").pick(4, false)
            compare(dialog.picked.join(), "3,5,6")
            compare(find(dialog, "importTotals").text, "3 / 6 chương")
            dialog.picked = []
            verify(dialog.nothingPicked)
            dialog.add(false)                       // không có chương nào thì không gửi
            compare(importCalls().length, 0)
            tryVerify(function() { return find(dialog, "importNothingPicked").visible })
            verify(!find(dialog, "importAdd").enabled)
        }
        function test_cancelledPreviewCannotReopenQueue() {
            DesktopApi.delayed = true
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub", "D:/x/b.epub"])
            dialog.close()                          // còn hai cuốn: hỏi trước
            compare(dialog.leave, "close")
            find(dialog, "importLeaveDrop").clicked()
            DesktopApi.finish()
            compare(dialog.preview, null)
            verify(!dialog.open)
            compare(importCalls().length, 0)
        }
        function test_errorThenRetry() {
            let calls = 0
            DesktopApi.responses = {"/api/listen/import/preview": function() {
                calls++
                return calls === 1 ? {status: 500, data: {error: "Máy chủ bận, thử lại sau."}} : {status: 200, data: book()}
            }}
            const dialog = make()
            dialog.begin(["D:/x/hỏng.epub"])
            compare(dialog.problem, "Máy chủ bận, thử lại sau.")
            compare(dialog.step, "choose")
            compare(Api.notice, "")                 // lỗi đã hiện trong hộp, không báo thêm lần nữa
            tryVerify(function() { return findButton(dialog, "Thử lại") !== null })
            findButton(dialog, "Thử lại").clicked()
            compare(calls, 2)
            compare(dialog.step, "review")
            compare(dialog.problem, "")
        }
        function test_addErrorKeepsDialog() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}, "/api/listen/import": {status: 500, data: {error: "Ổ đĩa đã đầy."}}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            dialog.add(false)
            compare(Api.notice, "Chưa thêm được sách - Ổ đĩa đã đầy.")
            compare(dialog.busy, "")
            verify(dialog.open)
            compare(dialog.step, "review")
        }
        function test_splitOfferReadsTwiceAndToggles() {
            DesktopApi.responses = {"/api/listen/import/preview": function(body) {
                return {status: 200, data: book({splitOffer: 6, splitHeadings: 6, chapters: chapters(body.splitChapters ? 6 : 1)})}
            }}
            const dialog = make()
            dialog.begin(["D:/x/cả truyện.txt"])
            compare(previewCalls().length, 2)
            compare(previewCalls()[1].body.splitChapters, true)
            verify(dialog.split)
            compare(dialog.shown.chapters.length, 6)
            find(dialog, "importSplit").toggled(false)
            compare(previewCalls().length, 3)
            compare(previewCalls()[2].body.splitChapters, false)
            verify(!dialog.split)
            compare(dialog.shown.chapters.length, 1)
        }
        function test_footnoteChoiceRereadsAndSends() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book({footnotes: {found: 3, marks: 3, examples: []}})}, "/api/listen/import": {status: 200, data: {id: "n", how: "new"}}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            dialog.names = {3: "Giữ tên"}
            dialog.reread({split: false, footnotes: {hideMarks: true, notes: "end"}})
            compare(previewCalls()[1].body.footnotes.notes, "end")
            compare(dialog.names[3], "Giữ tên")      // danh sách chương vẫn y như trước: giữ phần người dùng đã đổi
            dialog.add(false)
            compare(importCalls()[0].body.footnotes.hideMarks, true)
        }
        function test_knownBookOpensOrAddsSeparate() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book({existing: {id: "old", title: "Đã có"}})}, "/api/listen/import": {status: 200, data: {id: "copy", how: "new"}}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            verify(dialog.known !== null)
            tryVerify(function() { return find(dialog, "importOpenKnown").visible && !find(dialog, "importAdd").visible })
            find(dialog, "importOpenKnown").clicked()
            compare(opened.join(), "old")
            verify(!dialog.open)
            const again = make()
            again.begin(["D:/x/a.epub"])
            again.add(true)
            compare(importCalls()[0].body.separate, true)
        }
        function test_queueAddSkipAndLeaveConfirm() {
            DesktopApi.responses = {"/api/listen/import/preview": previews({"D:/q/A.epub": book({title: "Sách A"}), "D:/q/B.epub": book({title: "Sách B"}), "D:/q/C.epub": book({title: "Sách C"})}),
                                    "/api/listen/import": function(body) { return {status: 200, data: {id: "id-" + body.title, how: "new"}} }}
            const dialog = make()
            dialog.begin(["D:/q/A.epub", "D:/q/B.epub", "D:/q/C.epub"])
            compare(dialog.title, "Sách 1/3 · Thêm sách")
            compare(dialog.pending, 3)
            // Esc / ✕ khi còn > 1 cuốn: hỏi, có lớp Back riêng; Back về hộp
            dialog.close()
            compare(dialog.leave, "close")
            verify(dialog.open)
            verify(Nav.layers[Nav.layers.length - 1] === dialog.leaveLayer)
            verify(Nav.back())
            compare(dialog.leave, "")
            verify(dialog.open)
            dialog.close()
            find(dialog, "importLeaveBack").clicked()
            compare(dialog.leave, "")
            verify(dialog.open)
            // "Chọn lại" cũng hỏi
            dialog.chooseAgain()
            compare(dialog.leave, "again")
            Nav.back()
            compare(dialog.leave, "")
            // Thêm A, bỏ B, thêm C
            dialog.add(false)
            compare(dialog.queue[0].state, "added")
            compare(dialog.title, "Sách 2/3 · Thêm sách")
            compare(dialog.bookTitle, "Sách B")
            find(dialog, "importSkip").clicked()
            compare(dialog.queue[1].state, "skipped")
            compare(dialog.title, "Sách 3/3 · Thêm sách")
            dialog.add(false)
            compare(importCalls().map(c => c.body.title).join("|"), "Sách A|Sách C")
            compare(Api.notice, "Đã thêm 2 sách · bỏ qua 1 cuốn")
            verify(!dialog.open)
            compare(opened.length, 0)               // hai cuốn mới: không nhảy vào trang sách nào
        }
        function test_queueLeaveDropClosesAndChooseAgainResets() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}}
            const dialog = make()
            dialog.begin(["D:/q/A.epub", "D:/q/B.epub"])
            dialog.close()
            find(dialog, "importLeaveDrop").clicked()
            verify(!dialog.open)
            compare(importCalls().length, 0)
            const again = make()
            again.begin(["D:/q/A.epub", "D:/q/B.epub"])
            again.chooseAgain()
            compare(again.leave, "again")
            compare(find(again, "importLeaveDrop").text, "Bỏ và chọn lại")
            find(again, "importLeaveDrop").clicked()
            compare(again.step, "choose")
            compare(again.queue, null)
            verify(again.open)
        }
        function test_addRestKnownAndBookFilesLast() {
            DesktopApi.responses = {"/api/listen/import/preview": previews({"D:/q/A.epub": book({title: "Sách A"}), "D:/q/B.txt": book({title: "Sách B"}), "D:/q/C.epub": book({title: "Sách C", existing: {id: "old", title: "Sách C đã có"}})}),
                                    "/api/listen/import": function(body) { return {status: 200, data: {id: "id-" + body.title, how: "new"}} },
                                    "/api/listen/open-book-file": {status: 200, data: {id: "from-file", how: "new"}}}
            const dialog = make()
            dialog.begin(["D:/q/Z.abook", "D:/q/A.epub", "D:/q/B.txt", "D:/q/C.epub"])
            compare(dialog.queue.map(q => q.name).join("|"), "A.epub|B.txt|C.epub|Z.abook")     // file sách xếp cuối
            compare(dialog.rest, 3)                 // B, C và file .abook cuối hàng
            find(dialog, "importAddRest").activated()
            // Thêm từ cuốn cuối về cuốn đang xem; cuốn đã có không thêm
            compare(importCalls().map(c => c.body.title).join("|"), "Sách B|Sách A")
            compare(opened.join(), "from-file")
            compare(Api.notice, "Đã thêm 2 sách · đã mở 1 file sách · 1 cuốn đã có trong thư viện")
            verify(!dialog.open)
        }
        function test_queueErrorKeepsDialogForReading() {
            DesktopApi.responses = {"/api/listen/import/preview": previews({"D:/q/A.epub": {__error: "File hỏng."}, "D:/q/B.epub": {__error: "Không phải sách."}})}
            const dialog = make()
            dialog.begin(["D:/q/A.epub", "D:/q/B.epub"])
            compare(dialog.step, "queue")
            compare(dialog.queue.map(q => q.state).join(), "error,error")
            verify(dialog.open)
            compare(dialog.description, "2 file chưa đọc được")
            tryVerify(function() { return findButton(dialog, "Xong") !== null })
            findButton(dialog, "Xong").clicked()
            verify(!dialog.open)
        }
        function test_unsupportedSingleFileSaysWhy() {
            const dialog = make()
            dialog.begin(["D:/x/ảnh bìa.jpg"])
            compare(dialog.problem, "Chưa hỗ trợ .jpg. Chọn EPUB, DOCX, PDF có chữ, TXT hoặc .abook.")
            compare(previewCalls().length, 0)
        }
        function test_typedPathAndBackClosesDialog() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}}
            const dialog = make()
            dialog.show()
            const typed = find(dialog, "importTyped")
            typed.text = "  \"D:/Truyện/Tên truyện.epub\"  "
            typed.accepted()
            compare(previewCalls()[0].body.path, "D:/Truyện/Tên truyện.epub")
            verify(Nav.back())                      // Back từ hộp: đóng hộp
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
        }
        function test_longTextWrapsNeverCut() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: longBook()}}
            // Keep the original narrow-dialog stress case; WideScreens covers
            // the same fields and chapter names in both columns and in motion.
            const dialog = make({}, narrowHost)
            dialog.begin(["D:/Truyện/" + "Tên file rất dài ".repeat(12) + ".epub", "D:/Truyện/b.epub"])
            const names = []
            const gather = function(item) { if (item.objectName === "importQueueName") names.push(item); for (const c of item.children || []) gather(c) }
            gather(dialog)
            verify(names[0].height > names[0].font.pixelSize * 3)      // tên file dài xuống nhiều dòng
            const title = find(dialog, "importTitle")
            title.text = "Tên sách rất dài ".repeat(20)
            verify(title.height >= 44 + 15)                            // tên sách dài xuống dòng, ô cao thêm
            const list = find(dialog, "importChapters")
            verify(list.buttonFor(2).height > 50)                      // tên chương dài xuống 3 dòng
            dialog.reset()
            const typed = find(dialog, "importTyped")
            typed.text = "D:/Truyện/" + "một đường dẫn rất dài ".repeat(10)
            verify(typed.height > 40)
        }
        function test_stepsAnimateGeometrically() {
            Theme.reduceMotion = false
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            const review = find(dialog, "importReview")
            verify(review.reveal < 1)               // mở dần, không bật tắt cứng
            tryVerify(function() { return review.reveal === 1 }, 2000)
            dialog.reset()
            verify(review.reveal > 0)               // khép dần
            tryVerify(function() { return review.reveal === 0 }, 2000)
        }
        function click(item) { VisualReady.render(this, host.Window.window, host, qtVisualReady); mouseClick(item) }
        function test_realClicksOnRowsAndLinks() {
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book()}}
            const dialog = make()
            dialog.begin(["D:/x/a.epub"])
            tryVerify(function() { return dialog.shown !== null && dialog.visible })
            tryVerify(function() { return find(dialog, "importChapters").buttonFor(4) !== null })
            const list = find(dialog, "importChapters")
            click(list.buttonFor(4))           // bấm tên chương: mở ô sửa
            compare(list.editing, 4)
            verify(Nav.back())
            compare(list.editing, -1)
            // Ô tích của hàng 3
            let box = null
            const walk = function(n) { if (n.checked !== undefined && n.label === "Đưa vào sách: Chương 3") box = n; for (const c of n.children || []) walk(c) }
            walk(list)
            verify(box !== null)
            click(box)
            compare(dialog.picked.indexOf(3), -1)
            click(box)
            verify(dialog.picked.indexOf(3) >= 0)
            // "Bỏ chọn hết" rồi "Chọn hết"
            const none = findLink(dialog, "Bỏ chọn hết"), all = findLink(dialog, "Chọn hết")
            click(none)
            compare(dialog.picked.length, 0)
            click(all)
            compare(dialog.picked.length, 6)
        }
        function findLink(item, name) {
            if (item.Accessible && item.Accessible.name === name && item.hovered !== undefined && item.visible) return item
            for (const c of item.children || []) { const f = findLink(c, name); if (f) return f }
            return null
        }
        function test_emptyPickDoesNothing() {
            const dialog = make()
            dialog.show()
            DesktopApi.requests = []
            dialog.startPicked([])
            compare(dialog.step, "choose")
            compare(DesktopApi.requests.length, 0)
        }

        // ---- Ảnh ----
        function shot(name, item) {
            const target = item || host
            target.Window.window.update()
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            qtGlyphAudit.scan()
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }
        function openFolds() { for (const key of ["format", "footnotes", "suggestions"]) Platform.setSetting("fold.addbook." + key, "1") }
        function longBook() {
            return book({title: "Tôi chuyển sinh thành một con slime ở thế giới khác: Tập mười hai - Hồi ký của người kể chuyện cuối cùng bên bờ sông Hồng",
                         author: "Fuse", chapters: chapters(40, true).map((c, i) => i % 7 === 4 ? Object.assign(c, {title: "Chương " + c.index}) : c)})
        }
        function pdfBook() {
            return book({title: "Hoa trên đỉnh núi", chapters: chapters(12), notes: ["Đã gộp các dòng bị ngắt giữa câu ở 41 chỗ", "Đã bỏ số trang ở chân mỗi trang", "Đã bỏ 12 dòng đầu trang lặp lại", "Dòng “Dịch: Nhóm dịch Hoa Sen” lặp ở đầu 2 chương - bạn có thể bỏ khỏi phần đọc", "Dòng “Ủng hộ nhóm dịch tại trang chủ” ở cuối 1 chương - bạn có thể bỏ khỏi phần đọc"],
                         suggestions: [{chapter: 3, line: "Dịch: Nhóm dịch Hoa Sen", defaultOn: true}, {chapter: 4, line: "Dịch: Nhóm dịch Hoa Sen", defaultOn: true}, {chapter: 5, line: "Ủng hộ nhóm dịch tại trang chủ"}],
                         footnotes: {found: 14, marks: 14, examples: [{mark: "…bên bờ sông²", note: "Sông Hồng, đoạn chảy qua Hà Nội."}]}})
        }
        function scenes(suffix, parentItem) {
            const sized = parentItem || host
            // Bước chọn, đang đọc, lỗi
            let dialog = make(null, parentItem)
            dialog.begin([])
            shot("addbook_choose" + suffix, sized)
            dialog.problem = "Chưa đọc được file này: tệp bị hỏng hoặc không đúng định dạng EPUB. Bạn thử chọn lại file khác."
            dialog.lastRead = {path: "D:/Truyện/hỏng.epub", name: "hỏng.epub"}
            shot("addbook_error" + suffix, sized)
            dialog.problem = ""
            dialog.busy = "reading"
            shot("addbook_reading" + suffix, sized)
            dialog.destroy()
            // Xem lại: sách tên rất dài, nhiều chương
            openFolds()
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: longBook()}}
            dialog = make(null, parentItem)
            dialog.begin(["D:/Truyện/slime.epub"])
            shot("addbook_review" + suffix, sized)
            dialog.destroy()
            // Ghi chú, gợi ý bỏ dòng, chú thích (PDF / EPUB)
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: pdfBook()}}
            dialog = make(null, parentItem)
            dialog.begin(["D:/Truyện/hoa.pdf"])
            shot("addbook_notes" + suffix, sized)
            dialog.destroy()
            // File TXT cả truyện: tách chương
            DesktopApi.responses = {"/api/listen/import/preview": previews({"*": book({chapters: chapters(2).map(c => Object.assign(c, {included: undefined})), splitOffer: 120, splitHeadings: 2})})}
            dialog = make(null, parentItem)
            dialog.begin(["D:/Truyện/cả truyện.txt"])
            shot("addbook_split" + suffix, sized)
            dialog.destroy()
            // Đã có trong thư viện
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book({existing: {id: "old", title: "Tên sách đã có trong thư viện của bạn"}})}}
            dialog = make(null, parentItem)
            dialog.begin(["D:/Truyện/trùng.epub"])
            shot("addbook_known" + suffix, sized)
            dialog.destroy()
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: book({sameSource: {id: "old", title: "Tên sách thêm lần trước", chapters: 12}})}}
            dialog = make(null, parentItem)
            dialog.begin(["D:/Truyện/trùng.epub"])
            shot("addbook_samesource" + suffix, sized)
            dialog.destroy()
        }
        function test_shots() { both(function() { scenes("") }) }
        function test_shotsNarrow() { both(function() { scenes("_narrow", narrowHost) }) }
        function queueMap() {
            return previews({"D:/q/Tôi chuyển sinh thành slime - tập 12 - bản dịch đầy đủ có minh hoạ.epub": longBook(), "D:/q/B.epub": book({title: "Sách B"}), "D:/q/C.epub": book({title: "Sách C", existing: {id: "old", title: "Sách C đã có"}}),
                             "D:/q/D.epub": {__error: "File hỏng: không đọc được phần mục lục của sách này."}})
        }
        function queueFiles() { return ["D:/q/Tôi chuyển sinh thành slime - tập 12 - bản dịch đầy đủ có minh hoạ.epub", "D:/q/B.epub", "D:/q/C.epub", "D:/q/D.epub", "D:/q/E.abook"] }
        function scenesQueue(suffix, parentItem) {
            const sized = parentItem || host
            DesktopApi.responses = {"/api/listen/import/preview": queueMap(), "/api/listen/import": function(body) { return {status: 200, data: {id: "id-" + body.title, how: "new"}} },
                                    "/api/listen/open-book-file": {status: 200, data: {id: "from-file", how: "new"}}}
            // Cuốn đầu của hàng 5 file
            let dialog = make(null, parentItem)
            dialog.begin(queueFiles())
            shot("addbook_queue" + suffix, sized)
            // Hỏi khi đóng
            dialog.close()
            shot("addbook_leave" + suffix, sized)
            Nav.back()
            // Sang cuốn thứ hai (đã thêm cuốn đầu), rồi cuốn "đã có": nút chính là "Bỏ cuốn này"
            dialog.add(false)
            dialog.skipCurrent()
            shot("addbook_queue_known" + suffix, sized)
            dialog.destroy()
            // Đang thêm cả lô (trả lời chậm)
            dialog = make(null, parentItem)
            dialog.begin(queueFiles())
            DesktopApi.delayed = true
            dialog.addAll()
            shot("addbook_adding" + suffix, sized)
            DesktopApi.delayed = false
            DesktopApi.finish()
            dialog.destroy()
            // Xong mà có file lỗi: hộp ở lại để đọc lý do
            DesktopApi.responses = {"/api/listen/import/preview": previews({"D:/q/A.epub": {__error: "File hỏng."}, "D:/q/B.epub": {__error: "Không phải sách: thiếu mục lục."}}),
                                    "/api/listen/open-book-file": {status: 200, data: {error: "File này của phiên bản mới hơn.", file: "C.abook"}}}
            dialog = make(null, parentItem)
            dialog.begin(["D:/q/A.epub", "D:/q/B.epub", "D:/q/ảnh.jpg", "D:/q/C.abook"])
            shot("addbook_queue_done" + suffix, sized)
            dialog.destroy()
            // Đổi tên một chương
            openFolds()
            DesktopApi.responses = {"/api/listen/import/preview": {status: 200, data: longBook()}}
            dialog = make(null, parentItem)
            dialog.begin(["D:/q/slime.epub"])
            find(dialog, "importChapters").startEdit(3)
            host.Window.window.update(); waitForRendering(sized)
            shot("addbook_rename" + suffix, sized)
            Nav.back()
            dialog.destroy()
        }
        function test_shotsQueue() { both(function() { scenesQueue("") }) }
        function test_shotsQueueNarrow() { both(function() { scenesQueue("_narrow", narrowHost) }) }
        // Cửa vào ở thư viện: trống (nút chính lớn + hai lối phụ), có sách (nút "Thêm sách" ở đầu màn), kéo file vào
        function scenesLibrary(suffix, width) {
            for (const count of [0, 12]) {
                Backend.library.count = count
                const page = createTemporaryObject(libraryFactory, host, {width: width, height: host.height})
                verify(page !== null)
                if (count === 0) {
                    shot("addbook_library_empty" + suffix, page)
                    find(page, "importDrop").shown = true
                    shot("addbook_drop" + suffix, page)
                } else shot("addbook_library_header" + suffix, page)
                page.destroy()
            }
            Backend.library.count = 200
        }
        function test_shotsLibrary() { both(function() { scenesLibrary("", 1440) }) }
        function test_shotsLibraryNarrow() { both(function() { scenesLibrary("_narrow", 760) }) }
        function test_libraryEntryPoints() {
            Backend.library.count = 0
            const page = createTemporaryObject(libraryFactory, host, {width: 1000, height: host.height})
            const asked = []
            page.addRequested.connect(paths => asked.push(paths.length))
            let file = 0, studio = 0
            page.openFileRequested.connect(() => file++)
            page.studioRequested.connect(() => studio++)
            tryVerify(function() { return find(page, "emptyAdd").visible })
            find(page, "emptyAdd").clicked()
            find(page, "emptyOpenFile").clicked()
            find(page, "emptyStudio").clicked()
            compare(asked.join(), "0")
            compare(file, 1)
            compare(studio, 1)
            compare(find(page, "emptyAdd").kind, "primary")
            compare(find(page, "emptyAdd").size, "lg")
            Backend.library.count = 200
        }
    }
}
