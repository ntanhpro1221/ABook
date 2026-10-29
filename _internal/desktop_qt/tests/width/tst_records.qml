import QtQuick
import QtTest
import ABook

// "Hồ sơ nghe" của trang sách (BookPage + RecordChip + RecordMenu + RecordDialogs): một hồ sơ thì việc nằm trong menu "Thêm", từ hai hồ sơ thì có nút
// "Hồ sơ nghe: {tên}"; tạo / đổi tên / chuyển sang cuốn khác / xoá / chuyển hồ sơ đi đúng các đường của web (lời gửi, lời báo), "Đã nghe xong" cho cả cuốn,
// các lớp nằm trên ngăn xếp Back, chữ dài xuống dòng ở 1024 và 1920. Máy chủ giả: DesktopApi giả; trình phát là Player thật với mạng giả (cuốn "width").
// Ảnh offscreen ghi ra build/d2shots/records_*.png.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: pageFactory; BookPage {} }
    Component { id: dialogsFactory; RecordDialogs {} }
    Component { id: spyFactory; SignalSpy {} }

    TestCase {
        id: test
        name: "ListeningRecords"
        when: windowShown

        property var server: ({})
        property var page: null
        property var dialogs: null
        property var playerBefore: null         // cuốn đang nạp trong Player lúc vào bài thử: các tệp thử sau dùng chung Player nên phải trả lại
        readonly property string longName: "Lần nghe thứ nhất của một chuyến đường dài tưởng như không bao giờ kết thúc giữa rừng sâu"

        function record(id, name, active, withPlace) {
            return {id: id, name: name, active: active, last: withPlace ? {chapterId: 2, seconds: 75} : null, updatedAt: withPlace ? Date.now() / 1000 - 86400 : 0}
        }
        function bookWith(records, finished) {
            return {id: "width", stage: "audio", title: "Sách nhiều lần nghe", author: "", cover: null, edits: 0,
                    capabilities: {workshop: false, toolchain: false, link: false},
                    progress: {finished: Boolean(finished)}, records: records,
                    chapters: [{id: 1, title: "Chương 1", fullTitle: "Chương 1", available: true}, {id: 2, title: "Chương 2", fullTitle: "Chương 2", available: true}]}
        }
        function one() { return bookWith([record("r1", "Lần nghe 1", true, true)]) }
        function two() { return bookWith([record("r1", "Lần nghe 1", true, true), record("r2", "Bản của Lan", false, false)]) }
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
            WidthNet.setBook({id: "width", title: "Sách nhiều lần nghe", complete: true, chapters: [
                {id: 1, index: 1, title: "Chương 1", fullTitle: "Chương 1", available: true, duration: 2000},
                {id: 2, index: 2, title: "Chương 2", fullTitle: "Chương 2", available: true, duration: 2000}]})
            server = one()
            reply("GET /api/listen/books/width", function() { return {status: 200, data: server} })
            reply("GET /api/listen/books/width/sessions", {status: 200, data: []})
            reply("GET /api/listen/library", {status: 200, data: [
                {id: "width", title: "Sách nhiều lần nghe"}, {id: "other", title: "Cuốn khác"}, {id: "third", title: "Cuốn thứ ba"}]})
            reply("POST /api/listen/books/width/records", {status: 200, data: {id: "r9"}})
            reply("PUT /api/listen/books/width/records/r1", {status: 200, data: {}})
            reply("DELETE /api/listen/books/width/records/r1", {status: 200, data: {}})
            reply("POST /api/listen/books/width/records/r1/move", {status: 200, data: {}})
            reply("POST /api/listen/books/width/records/r2/activate", {status: 200, data: {}})
            reply("POST /api/listen/books/width/finished", {status: 200, data: {}})
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
            if (dialogs) dialogs.destroy()
            page = null
            dialogs = null
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
            dialogs = createTemporaryObject(dialogsFactory, host, {})
            page = createTemporaryObject(pageFactory, host, {width: host.width, height: host.height, book: {bookId: "width", title: "Sách nhiều lần nghe"}})
            verify(page !== null && dialogs !== null)
            page.recordRequested.connect((kind, data) => dialogs.begin(kind, data))
            tryVerify(function() { return page.fullBook.id === "width" })
            settle()
        }
        function openMore() {
            findChild(page, "bookMore").clicked()
            tryVerify(function() { return findChild(page, "bookMoreMenu").open })
            settle()
        }
        function openRecordMenu() {
            findChild(page, "recordChip").clicked()
            tryVerify(function() { return findChild(page, "recordMenu").open })
            settle()
        }
        function confirm() { return all(dialogs, "recordConfirm")[0] }
        function waitDialogOpen() { tryVerify(function() { return dialogs.open }); settle() }

        // ---------- một hồ sơ: các việc nằm trong menu "Thêm" ----------
        function test_oneRecordMenuHoldsTheActions() {
            openPage()
            verify(!findChild(page, "recordChip").visible)                 // một hồ sơ: không có nút "Hồ sơ nghe:"
            openMore()
            const create = findChild(page, "recordRow.create"), move = findChild(page, "recordRow.move")
            const rename = findChild(page, "recordRow.rename"), del = findChild(page, "recordRow.delete")
            const finished = findChild(page, "menuFinished")
            compare(create.text, "Hồ sơ mới")
            compare(move.text, "Chuyển hồ sơ")
            compare(rename.text, "Đổi tên hồ sơ…")
            compare(del.text, "Xoá hồ sơ…")
            compare(finished.text, "Đã nghe xong")
            verify(del.danger && !create.danger && !rename.danger && !move.danger)
            // thứ tự: Hồ sơ mới, Chuyển, Đổi tên, rồi "Đã nghe xong", Xoá nằm dưới cùng sau vạch ngăn
            const y = item => item.mapToItem(page, 0, 0).y
            verify(y(create) < y(move) && y(move) < y(rename) && y(rename) < y(finished) && y(finished) < y(del))
            compare(Nav.layers.length, 1)
            Nav.back()
            tryVerify(function() { return !findChild(page, "bookMoreMenu").open })
            shot("records_menu_one", host)
        }
        function test_textOnlyBookHasNoFinishedItem() {
            server = Object.assign(one(), {stage: "text"})
            openPage()
            openMore()
            verify(!findChild(page, "menuFinished").visible)
        }
        function test_manyRecordsUseTheChipInstead() {
            server = two()
            openPage()
            const chip = findChild(page, "recordChip")
            verify(chip.visible)
            compare(chip.Accessible.name, "Hồ sơ nghe: Lần nghe 1")
            compare(findChild(page, "recordChipName").text, "Lần nghe 1")
            openMore()
            verify(findChild(page, "recordRow.create") === null || !findChild(page, "recordRow.create").visible)
            verify(findChild(page, "recordRow.delete") === null || !findChild(page, "recordRow.delete").visible)
            Nav.back()
            tryVerify(function() { return !findChild(page, "bookMoreMenu").open })
            openRecordMenu()
            const choices = all(page, "recordChoice")
            compare(choices.length, 2)
            compare(choices[0].Accessible.name, "Lần nghe 1")
            verify(choices[0].Accessible.checked && !choices[1].Accessible.checked)
            verify(all(choices[0], "recordChoiceLine")[0].text.indexOf("Chương 2 · 1:15 · nghe gần nhất ") === 0)
            compare(all(choices[1], "recordChoiceLine")[0].text, "chưa nghe")
            compare(findChild(page, "recordAction.create").text, "Hồ sơ mới")
            compare(findChild(page, "recordAction.rename").text, "Đổi tên hồ sơ này…")
            compare(findChild(page, "recordAction.move").text, "Chuyển sang cuốn khác…")
            compare(findChild(page, "recordAction.delete").text, "Xoá hồ sơ này…")
            verify(findChild(page, "recordAction.delete").danger)
            compare(Nav.layers.length, 1)
            shot("records_menu_many", host)
            Nav.back()
            tryVerify(function() { return !findChild(page, "recordMenu").open })
            compare(Nav.layers.length, 0)
        }

        // ---------- tạo / đổi tên / xoá / chuyển ----------
        function test_createSendsNameAndStartsOver() {
            openPage()
            openMore()
            findChild(page, "recordRow.create").clicked()
            waitDialogOpen()
            compare(dialogs.title, "Nghe lại từ đầu")
            compare(dialogs.description, "Hồ sơ mới nghe từ đầu; hồ sơ cũ vẫn giữ nguyên.")
            compare(findChild(dialogs, "recordName").text, "Lần nghe 2")
            compare(confirm().text, "Tạo và nghe từ đầu")
            compare(Nav.layers.length, 1)                                 // hộp là một lớp Back
            findChild(dialogs, "recordName").text = "  Lần của Lan  "
            confirm().activated()
            const sent = calls("POST", "/api/listen/books/width/records")
            compare(sent.length, 1)
            compare(sent[0].body.name, "Lần của Lan")
            tryVerify(function() { return !dialogs.open })
            compare(Api.notice, "Hồ sơ mới “Lần của Lan” - nghe từ chương đầu")
            tryCompare(Player, "bookId", "width")
            tryCompare(Player, "chapterId", 1)                            // nghe từ chương đầu
            compare(Nav.layers.length, 0)
        }
        function test_renameNeedsANameAndKeepsThePlayer() {
            openPage()
            openMore()
            findChild(page, "recordRow.rename").clicked()
            waitDialogOpen()
            compare(dialogs.title, "Đổi tên hồ sơ")
            const field = findChild(dialogs, "recordName")
            compare(field.text, "Lần nghe 1")
            field.text = "   "
            verify(!confirm().enabled)
            field.text = "Lần của Hạ"
            verify(confirm().enabled)
            compare(confirm().text, "Lưu")
            confirm().activated()
            const sent = calls("PUT", "/api/listen/books/width/records/r1")
            compare(sent.length, 1)
            compare(sent[0].body.name, "Lần của Hạ")
            tryVerify(function() { return !dialogs.open })
            compare(Api.notice, "Đã đổi tên hồ sơ")
        }
        function test_nameIsCappedAtSixtyCharacters() {
            openPage()
            openMore()
            findChild(page, "recordRow.rename").clicked()
            waitDialogOpen()
            findChild(dialogs, "recordName").text = "x".repeat(80)
            compare(findChild(dialogs, "recordName").text.length, 60)
        }
        function test_deleteAsksFirstAndSaysWhatIsLost() {
            openPage()
            openMore()
            findChild(page, "recordRow.delete").clicked()
            waitDialogOpen()
            compare(dialogs.title, "Xoá hồ sơ “Lần nghe 1”?")
            compare(dialogs.description, "Chỗ nghe, lịch sử của hồ sơ này mất hẳn trên mọi máy. Sách giữ nguyên; đây là hồ sơ duy nhất nên cuốn sẽ như chưa nghe lần nào.")
            compare(confirm().text, "Xoá hồ sơ")
            compare(confirm().kind, "danger")
            compare(calls("DELETE", "/api/listen/books/width/records/r1").length, 0)      // chưa bấm thì chưa xoá
            confirm().activated()
            compare(calls("DELETE", "/api/listen/books/width/records/r1").length, 1)
            tryVerify(function() { return !dialogs.open })
            compare(Api.notice, "Đã xoá hồ sơ “Lần nghe 1”")
        }
        function test_deleteWithManyRecordsSaysTheBookMovesOn() {
            server = two()
            openPage()
            openRecordMenu()
            findChild(page, "recordAction.delete").clicked()
            waitDialogOpen()
            verify(dialogs.description.indexOf("cuốn chuyển sang hồ sơ nghe gần nhất còn lại.") > 0)
            Nav.back()
            tryVerify(function() { return !dialogs.open })
            compare(Nav.layers.length, 0)
            compare(calls("DELETE", "/api/listen/books/width/records/r1").length, 0)
        }
        function test_moveAsksForTheOtherBook() {
            openPage()
            openMore()
            findChild(page, "recordRow.move").clicked()
            waitDialogOpen()
            compare(dialogs.title, "Chuyển hồ sơ “Lần nghe 1” sang cuốn khác")
            compare(dialogs.description, "Chỗ nghe, lịch sử đi theo hồ sơ sang cuốn kia. Cuốn này sẽ như chưa nghe lần nào.")
            const picker = findChild(dialogs, "recordTarget")
            tryVerify(function() { return picker.visible })
            compare(picker.options.map(o => o.label).join("|"), "Cuốn khác|Cuốn thứ ba")      // không có chính cuốn này
            compare(picker.placeholder, "Chọn cuốn…")
            compare(calls("GET", "/api/listen/library").length, 1)
            verify(!confirm().enabled)                                    // chưa chọn cuốn nhận
            picker.picked("other")
            verify(confirm().enabled)
            compare(confirm().text, "Chuyển")
            confirm().activated()
            const sent = calls("POST", "/api/listen/books/width/records/r1/move")
            compare(sent.length, 1)
            compare(sent[0].body.book, "other")
            tryVerify(function() { return !dialogs.open })
            compare(Api.notice, "Đã chuyển hồ sơ “Lần nghe 1” sang “Cuốn khác”")
            compare(Api.noticeAction.label, "Mở cuốn ấy")
            const spy = createTemporaryObject(spyFactory, host, {target: dialogs, signalName: "openBook"})
            Api.noticeAction.run()
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0], "other")
        }
        function test_moveWaitsForTheLibraryWithoutFlashingTheEmptyText() {
            DesktopApi.delayed = false
            openPage()
            openMore()
            DesktopApi.delayed = true
            findChild(page, "recordRow.move").clicked()
            waitDialogOpen()
            verify(findChild(dialogs, "recordLoading").visible)
            compare(findChild(dialogs, "recordLoading").text, "Đang mở thư viện…")
            verify(!findChild(dialogs, "recordNoOthers").visible)
            verify(!confirm().enabled)
            DesktopApi.delayed = false
            DesktopApi.finish()
            tryVerify(function() { return findChild(dialogs, "recordTarget").visible })
            verify(!findChild(dialogs, "recordLoading").visible)
        }
        function test_moveWithNoOtherBookSaysSo() {
            reply("GET /api/listen/library", {status: 200, data: [{id: "width", title: "Sách nhiều lần nghe"}]})
            openPage()
            openMore()
            findChild(page, "recordRow.move").clicked()
            waitDialogOpen()
            tryVerify(function() { return findChild(dialogs, "recordNoOthers").visible })
            compare(findChild(dialogs, "recordNoOthers").text, "Thư viện chưa có cuốn nào khác.")
            verify(!findChild(dialogs, "recordTarget").visible)
            verify(!confirm().enabled)
        }

        // ---------- chuyển hồ sơ ----------
        function test_activateOtherRecordSwitchesAndReopensThePlayer() {
            server = two()
            openPage()
            Player.open("width", 1, 0, false)
            tryCompare(Player, "bookId", "width")
            openRecordMenu()
            const choices = all(page, "recordChoice")
            choices[0].clicked()                                          // đang dùng rồi: không gửi gì
            compare(calls("POST", "/api/listen/books/width/records/r2/activate").length, 0)
            tryVerify(function() { return !findChild(page, "recordMenu").open })
            openRecordMenu()
            all(page, "recordChoice")[1].clicked()
            const sent = calls("POST", "/api/listen/books/width/records/r2/activate")
            compare(sent.length, 1)
            compare(sent[0].body, null)
            compare(Api.notice, "Đang dùng hồ sơ “Bản của Lan”")
            tryCompare(Player, "bookId", "width")                         // nạp lại ở trạng thái dừng
            verify(Player.loaded)
        }

        // ---------- đánh dấu cả cuốn ----------
        function test_finishedToggleWritesToTheActiveRecord() {
            openPage()
            openMore()
            findChild(page, "menuFinished").clicked()
            const sent = calls("POST", "/api/listen/books/width/finished")
            compare(sent.length, 1)
            compare(sent[0].body.finished, true)
            compare(sent[0].body.record, "r1")
        }
        function test_finishedBookOffersTheOpposite() {
            server = bookWith([record("r1", "Lần nghe 1", true, true)], true)
            openPage()
            openMore()
            compare(findChild(page, "menuFinished").text, "Chưa nghe xong")
            findChild(page, "menuFinished").clicked()
            compare(calls("POST", "/api/listen/books/width/finished")[0].body.finished, false)
        }

        // ---------- chữ dài xuống dòng, không cắt ----------
        function test_longRecordNameWraps_data() { return [{tag: "1024", w: 1024}, {tag: "1920", w: 1920}] }
        function test_longRecordNameWraps(data) {
            server = bookWith([record("r1", longName, true, true), record("r2", "Bản của Lan", false, false)])
            openPage(data.w)
            const chip = findChild(page, "recordChip")
            verify(chip.visible)
            const name = findChild(page, "recordChipName")
            verify(name.lineCount > 1, "tên hồ sơ dài phải xuống dòng")
            verify(name.paintedWidth <= name.width + 0.5)
            const edge = chip.mapToItem(page, chip.width, 0).x
            verify(edge <= page.width, "nút Hồ sơ nghe nhô ra ngoài trang")
            verify(chip.height >= name.height + 12 - 0.5, "nút phải cao ôm hết tên")
            shot("records_chip_long_" + data.w, host)
            openRecordMenu()
            const names = all(page, "recordChoiceName")
            verify(names[0].lineCount > 1)
            for (const item of names.concat(all(page, "recordChoiceLine"))) {
                fuzzyCompare(item.height, item.contentHeight, 1)
                verify(item.mapToItem(page, item.paintedWidth, 0).x <= page.width, item.objectName + " nhô ra ngoài")
            }
            shot("records_menu_long_" + data.w, host)
            Nav.back()
            tryVerify(function() { return !findChild(page, "recordMenu").open })
            findChild(page, "recordChip").clicked()
            tryVerify(function() { return findChild(page, "recordMenu").open })
            findChild(page, "recordAction.rename").clicked()
            waitDialogOpen()
            shot("records_rename_long_" + data.w, host)
        }
        function test_longTitleInDeleteDialog() {
            server = bookWith([record("r1", longName, true, true)])
            openPage()
            openMore()
            findChild(page, "recordRow.delete").clicked()
            waitDialogOpen()
            verify(dialogs.title.indexOf(longName) > 0)
            shot("records_delete_long", host)
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
