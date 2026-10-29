import QtQuick
import QtTest
import ABook

// "Sửa sách" + "Tìm bìa" (EditBook.qml, CoverSearch.qml, EditBookRename.qml, EditBookSaveAs.qml, EditBookItems.qml): hành vi và ảnh.
// Ảnh ghi ra build/d2shots/editbook_*.png (sáng + tối, 1440x900 và cửa sổ hẹp 760) để người làm mở ra xem.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: editFactory; EditBook {} }
    Component { id: coverFactory; CoverSearch {} }
    Component { id: renameFactory; EditBookRename {} }
    Component { id: saveFactory; EditBookSaveAs {} }
    Component { id: itemsFactory; EditBookItems {} }
    Component { id: pageFactory; BookPage {} }
    Component { id: openerFactory; Button { text: "mở" } }

    TestCase {
        id: test
        name: "D2EditBook"
        when: windowShown

        property var server: ({})
        readonly property string longName: "Chuyển sinh thành người hầu của nữ hoàng ác quỷ và những ngày tháng không thể nào quên ở vương quốc phía đông "

        function textBook() {
            return {id: "b1", stage: "text", title: "Tên cũ", author: "Tác giả cũ", cover: null, edits: 3, wishes: 0,
                    capabilities: {workshop: false, toolchain: true, link: false}}
        }
        function studioBook() {
            return {id: "b1", stage: "audio", title: "Sách có giọng", author: "", cover: {version: 2}, edits: 0,
                    capabilities: {workshop: false, toolchain: true, link: false}}
        }
        function reply(path, handler) { const r = DesktopApi.responses; r[path] = handler; DesktopApi.responses = r }
        function init() {
            Theme.reduceMotion = true
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "fixture", dialogs: true}
            Api.loaded = true
            Api.saving = false
            Api.notice = ""
            Nav.layers = []
            server = textBook()
            // Máy chủ giả: GET sách trả bản hiện tại; PUT tên / tác giả sửa nó rồi trả lời như thật
            reply("GET /api/listen/books/b1", function() { return {status: 200, data: server} })
            reply("PUT /api/books/b1/title", function(body) { server = Object.assign({}, server, {title: body.title.trim().replace(/\s+/g, " ")}); return {status: 200, data: {}} })
            reply("PUT /api/books/b1/author", function(body) { server = Object.assign({}, server, {author: body.author.trim().replace(/\s+/g, " ")}); return {status: 200, data: {author: server.author}} })
            reply("PUT /api/books/b1/cover", function(body) { server = Object.assign({}, server, {cover: {version: 5}}); return {status: 200, data: {}} })
            reply("DELETE /api/books/b1/cover", function() { server = Object.assign({}, server, {cover: null}); return {status: 200, data: {}} })
            reply("DELETE /api/books/b1/edits", function() { server = Object.assign({}, server, {edits: 0}); return {status: 200, data: {}} })
            reply("GET /api/music/local", {status: 200, data: {tracks: []}})
            reply("GET /api/books/b1/readings", {status: 200, data: {readings: []}})
            reply("GET /api/books/b1/music", {status: 200, data: {hasMusic: false, enabled: true, levelDb: -20, cues: []}})
        }
        function cleanup() { DesktopApi.delayed = false; Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto" }
        function make(factory, props) {
            const item = createTemporaryObject(factory, host, Object.assign({width: host.width, height: host.height}, props || {}))
            verify(item !== null)
            return item
        }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function settle() { wait(350) }

        // ---------- hai ô, hai lần lưu: lưu ô này không mất chữ gõ dở ở ô kia ----------
        function test_titleSaveKeepsAuthorDraft() {
            const dialog = make(editFactory)
            dialog.begin(server)
            const title = findChild(dialog, "editTitle"), author = findChild(dialog, "editAuthor")
            title.text = "  Tên   mới  "
            author.text = "Tác giả đang gõ dở"
            const save = findChild(dialog, "editSaveTitle")
            verify(save.enabled)
            save.activated()
            const call = calls("PUT", "/api/books/b1/title")
            compare(call.length, 1)
            compare(call[0].body.title, "  Tên   mới  ")           // gửi nguyên chữ gõ, máy chủ làm sạch
            compare(author.text, "Tác giả đang gõ dở")
            compare(dialog.book.title, "Tên mới")
            compare(title.text, "Tên mới")                          // ô vừa lưu nạp lại chữ đã làm sạch
            compare(Api.notice, "Đã đổi tên sách")
            verify(dialog.open)
        }
        function test_authorSaveKeepsTitleDraft() {
            const dialog = make(editFactory)
            dialog.begin(server)
            const title = findChild(dialog, "editTitle"), author = findChild(dialog, "editAuthor")
            title.text = "Tên đang gõ dở"
            author.text = "Tác giả mới"
            findChild(dialog, "editSaveAuthor").activated()
            const call = calls("PUT", "/api/books/b1/author")
            compare(call.length, 1)
            compare(call[0].body.author, "Tác giả mới")
            compare(title.text, "Tên đang gõ dở")
            compare(dialog.book.author, "Tác giả mới")
            compare(Api.notice, "Đã đổi tác giả")
        }
        function test_emptyAuthorRemovesName() {
            const dialog = make(editFactory)
            dialog.begin(server)
            findChild(dialog, "editAuthor").text = "   "
            verify(findChild(dialog, "editSaveAuthor").enabled)     // sách đang có tác giả: trống cũng là một thay đổi
            findChild(dialog, "editSaveAuthor").activated()
            compare(Api.notice, "Đã bỏ tên tác giả")
        }
        function test_saveButtonsFollowRealChange() {
            const dialog = make(editFactory)
            dialog.begin(server)
            const title = findChild(dialog, "editTitle"), author = findChild(dialog, "editAuthor")
            verify(!findChild(dialog, "editSaveTitle").enabled)
            verify(!findChild(dialog, "editSaveAuthor").enabled)
            author.text = "  Tác giả   cũ "                          // cùng chữ sau khi làm sạch
            verify(!findChild(dialog, "editSaveAuthor").enabled)
            title.text = "   "
            verify(!findChild(dialog, "editSaveTitle").enabled)     // tên trống không lưu được
            title.text = "x".repeat(200)
            compare(title.text.length, 160)                          // như maxLength=160 của ô web
        }
        function test_saveFailureShowsReasonAndKeepsDraft() {
            const dialog = make(editFactory)
            dialog.begin(server)
            reply("PUT /api/books/b1/title", {status: 500, data: {error: "Ổ đĩa đầy"}})
            const title = findChild(dialog, "editTitle")
            title.text = "Tên khác"
            findChild(dialog, "editSaveTitle").activated()
            compare(Api.notice, "Chưa đổi được tên sách\nỔ đĩa đầy")
            compare(title.text, "Tên khác")
            verify(!dialog.renaming)
        }
        function test_sectionsFollowBookKind() {
            const dialog = make(editFactory)
            dialog.begin(server)                                    // sách chữ
            verify(dialog.textBook)
            tryVerify(function() { return findChild(dialog, "editAuthor").visible })
            compare(Api.notice, "")
            const audio = make(editFactory)
            audio.begin(studioBook())                               // sách đã có giọng: không có ô tác giả, có mục nhạc nền
            settle()
            verify(!findChild(audio, "editAuthor").visible || findChild(audio, "editAuthor").height === 0 || findChild(audio, "editAuthor").parent.height === 0)
        }

        // ---------- ảnh bìa ----------
        function test_coverFromFileAndRemove() {
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.setCoverImage("data:image/png;base64,abc")
            const put = calls("PUT", "/api/books/b1/cover")
            compare(put.length, 1)
            compare(put[0].body.image, "data:image/png;base64,abc")
            compare(Api.notice, "Đã đặt ảnh bìa")
            compare(findChild(dialog, "editPickCover").text, "Đổi ảnh bìa…")
            dialog.removeCover()
            compare(calls("DELETE", "/api/books/b1/cover").length, 1)
            compare(Api.notice, "Đã bỏ ảnh bìa - sách dùng bìa vẽ từ tên")
            compare(findChild(dialog, "editPickCover").text, "Chọn ảnh bìa…")
        }
        function test_coverSearchDefaultQueryAndChoose() {
            server.title = "Throne of Magical Arcana · Tập 16"
            reply("GET /api/books/b1/cover/search?q=" + encodeURIComponent("Throne of Magical Arcana"), {status: 200, data: {results: [
                {provider: "iTunes", title: "Throne of Magical Arcana", author: "Andrew Rowe", thumb: "", url: "https://fixture/a.jpg"},
                {provider: "Open Library", title: "Another", author: "", thumb: "", url: "https://fixture/b.jpg"}], failed: []}})
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.search()
            verify(dialog.searching)
            compare(dialog.title, "Tìm ảnh bìa")
            compare(dialog.description, "Bạn chọn ảnh từ các nguồn sách hoặc trên máy.")
            const query = findChild(dialog, "coverQuery")
            compare(query.text, "Throne of Magical Arcana")        // bộ truyện, không kèm "Tập 16"
            const panel = findChild(dialog, "coverSearchPanel")
            compare(panel.results.length, 2)
            settle()
            compare(findChild(dialog, "coverGrid").children.length >= 2, true)
        }
        function test_coverSearchChooseSendsUrlAndClosesStep() {
            reply("GET /api/books/b1/cover/search?q=" + encodeURIComponent("Tên cũ"), {status: 200, data: {results: [{provider: "iTunes", title: "A", author: "B", thumb: "", url: "https://fixture/a.jpg"}], failed: []}})
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.search()
            const panel = findChild(dialog, "coverSearchPanel")
            compare(panel.results.length, 1)
            panel.choose(panel.results[0])
            const put = calls("PUT", "/api/books/b1/cover")
            compare(put.length, 1)
            compare(put[0].body.url, "https://fixture/a.jpg")
            verify(!dialog.searching)
            compare(Api.notice, "Đã đặt ảnh bìa")
            verify(dialog.open)
        }
        function test_coverSearchPanelStates() {
            const panel = make(coverFactory, {width: 500})
            reply("GET /api/books/c/cover/search?q=" + encodeURIComponent("Rỗng"), {status: 200, data: {results: [], failed: []}})
            panel.begin("c", "Rỗng")
            settle()
            compare(panel.hasEmpty, true)                           // "Bạn hãy chọn ảnh trên máy"
            let picked = 0
            panel.chooseFile.connect(function() { picked++ })
            findChild(panel, "coverPickFile").clicked()
            compare(picked, 1)
            reply("GET /api/books/c/cover/search?q=" + encodeURIComponent("Lỗi"), {status: 200, data: {results: [], failed: ["google_books"]}})
            panel.query = "Lỗi"; panel.search()
            settle()
            compare(panel.failed.length, 1)
            compare(panel.hasEmpty, false)
            reply("GET /api/books/c/cover/search?q=" + encodeURIComponent("Mạng"), {status: 500, data: {error: "x"}})
            panel.query = "Mạng"; panel.search()
            compare(panel.searchError, true)
            compare(Api.notice, "")                                  // lỗi tìm chỉ hiện trong khung, không thành thông báo
        }
        function test_coverChooseErrorAndSuperseded() {
            const panel = make(coverFactory, {width: 500})
            reply("GET /api/books/c/cover/search?q=A", {status: 200, data: {results: [{provider: "iTunes", title: "T", author: "", thumb: "", url: "u1"}], failed: []}})
            panel.begin("c", "A")
            reply("PUT /api/books/c/cover", {status: 500, data: {error: "x"}})
            panel.choose(panel.results[0])
            compare(panel.chooseError, true)
            compare(panel.choosing, false)
            reply("PUT /api/books/c/cover", {status: 409, data: {error: "đã có bìa mới hơn"}})
            panel.choose(panel.results[0])
            compare(panel.chooseError, false)                        // 409: im lặng (bìa mới hơn đã được đặt), không báo lỗi, không phát chosen
            let chosen = 0
            panel.chosen.connect(function() { chosen++ })
            reply("PUT /api/books/c/cover", {status: 200, data: {}})
            panel.choose(panel.results[0])
            compare(chosen, 1)
        }
        function test_coverSearchLateReplyIgnoredAfterCancel() {
            const panel = make(coverFactory, {width: 500})
            DesktopApi.delayed = true
            reply("GET /api/books/c/cover/search?q=A", {status: 200, data: {results: [{provider: "iTunes", title: "T", author: "", thumb: "", url: "u1"}], failed: []}})
            panel.begin("c", "A")
            panel.cancel()
            DesktopApi.finish()
            compare(panel.results.length, 0)
            compare(panel.searched, false)
        }

        // ---------- Back đối xứng ----------
        function test_backFromSearchThenCloses() {
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.search()
            compare(Nav.layers.length, 2)
            verify(Nav.back())
            verify(!dialog.searching)
            verify(dialog.open)
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            verify(!dialog.open)
            compare(Nav.layers.length, 0)
        }
        function test_closeButtonFromSearchClosesWholeDialog() {
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.search()
            dialog.close()
            verify(!dialog.open)
            compare(Nav.layers.length, 0)                            // lớp bước tìm cũng gỡ
        }
        function test_revertConfirmBack() {
            const dialog = make(editFactory)
            dialog.begin(server)
            settle()
            findChild(dialog, "editRevert").clicked()
            verify(dialog.confirmRevert)
            compare(Nav.layers.length, 2)
            verify(Nav.back())
            verify(!dialog.confirmRevert)
            verify(dialog.open)
            verify(Nav.back())
            verify(!dialog.open)
        }
        function test_revertConfirmSendsRequest() {
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.askRevert()
            findChild(dialog, "editRevertConfirm").activated()
            compare(calls("DELETE", "/api/books/b1/edits").length, 1)
            compare(Api.notice, "Đã bỏ mọi thay đổi - sách như người làm sách đã đóng gói")
            verify(!dialog.confirmRevert)
            compare(Nav.layers.length, 1)
        }
        function test_revertHiddenForWorkshopOrNoEdits() {
            const dialog = make(editFactory)
            dialog.begin(Object.assign(textBook(), {edits: 0}))
            settle()
            compare(findChild(dialog, "editRevert").height > 0 && findChild(dialog, "editRevert").visible, false)
        }
        function test_restoresFocusToOpener() {
            const opener = createTemporaryObject(openerFactory, host)
            opener.forceActiveFocus()
            verify(opener.activeFocus)
            const dialog = make(editFactory)
            dialog.begin(server)
            verify(!opener.activeFocus)
            verify(Nav.back())
            verify(opener.activeFocus)
        }
        function test_focusReturnsToFindCoverAfterSearch() {
            const dialog = make(editFactory)
            dialog.begin(server)
            dialog.search()
            Nav.back()
            verify(findChild(dialog, "editFindCover").activeFocus)
        }

        // ---------- Đổi tên chương ----------
        function test_renameChapterSingleName() {
            const dialog = make(renameFactory)
            dialog.begin(textBook(), {id: 7, title: "Chương 7", subtitle: "", fullTitle: "Chương 7: Hồi kết"})
            compare(findChild(dialog, "renameLabel").text, "Chương 7: Hồi kết")
            compare(dialog.single, true)
            findChild(dialog, "renameLabel").text = "Hồi kết mới"
            reply("PUT /api/books/b1/chapters/7/title", {status: 200, data: {fullTitle: "Hồi kết mới"}})
            findChild(dialog, "renameSave").activated()
            const call = calls("PUT", "/api/books/b1/chapters/7/title")
            compare(call.length, 1)
            compare(call[0].body.title, "Hồi kết mới")
            compare(call[0].body.subtitle, "")
            compare(Api.notice, "Đã đổi tên chương: Hồi kết mới")
            verify(!dialog.open)
        }
        function test_renameChapterTwoFieldsAndRevert() {
            const dialog = make(renameFactory)
            dialog.begin(studioBook(), {id: 3, title: "Chương 3", subtitle: "Mở đầu", fullTitle: "Chương 3 - Mở đầu"})
            compare(dialog.single, false)
            compare(findChild(dialog, "renameLabel").text, "Chương 3")
            compare(findChild(dialog, "renameName").text, "Mở đầu")
            reply("PUT /api/books/b1/chapters/3/title", {status: 200, data: {fullTitle: "Chương 3"}})
            findChild(dialog, "renameRevert").clicked()
            compare(calls("PUT", "/api/books/b1/chapters/3/title")[0].body.revert, true)
        }
        function test_renameChapterErrorKeepsDialog() {
            const dialog = make(renameFactory)
            dialog.begin(textBook(), {id: 7, title: "Chương 7", subtitle: "", fullTitle: "Chương 7"})
            reply("PUT /api/books/b1/chapters/7/title", {status: 500, data: {error: "Lỗi ghi"}})
            findChild(dialog, "renameSave").activated()
            compare(Api.notice, "Chưa đổi được tên chương\nLỗi ghi")
            verify(dialog.open)
        }
        function test_renameChapterBack() {
            const dialog = make(renameFactory)
            dialog.begin(textBook(), {id: 7, title: "Chương 7", subtitle: "", fullTitle: "Chương 7"})
            compare(Nav.layers.length, 1)
            verify(Nav.back())
            verify(!dialog.open)
        }
        function test_renameLongNameWraps() {
            const dialog = make(renameFactory)
            dialog.begin(textBook(), {id: 7, title: "x", subtitle: "", fullTitle: longName.repeat(3)})
            const field = findChild(dialog, "renameLabel")
            verify(field.height > 60)
            compare(field.text.length, 160)  // ô dài tối đa 160 như bản web, nhưng ô cao thêm chứ không cắt hiển thị
        }

        // ---------- Lưu thành ----------
        function test_saveAsSendsKindAndFolder() {
            const dialog = make(saveFactory)
            dialog.begin({id: "b1", title: "x", stage: "text", wishes: 2})
            compare(dialog.kind, "abook")
            verify(findChild(dialog, "saveKind").currentIndex === 0)
            reply("POST /api/books/b1/save", {status: 200, data: {file: "D:/x.abook", folder: "D:/", size: 10, edits: 0}})
            dialog.folder = "D:/Sách"
            findChild(dialog, "saveGo").activated()
            const call = calls("POST", "/api/books/b1/save")
            compare(call.length, 1)
            compare(call[0].body.as, "abook")
            compare(call[0].body.target, "D:/Sách")
            compare(Api.notice, "Đã lưu file sách\nChưa có thay đổi nào - file giống bản gốc.")
            verify(!dialog.open)
        }
        function test_saveAsProjectFileDefaultsToProject() {
            const dialog = make(saveFactory)
            dialog.begin({id: "b1", title: "x", projectFile: {workshop: "present"}})
            compare(dialog.kind, "abookproj")
        }
        function test_quickSaveNoDialog() {
            const dialog = make(saveFactory)
            reply("POST /api/books/b1/save", {status: 200, data: {file: "a", folder: "D:/", size: 1, edits: 4}})
            dialog.quick({id: "b1"})
            compare(Api.notice, "Đã lưu file sách")
            verify(!dialog.open)
        }
        function test_saveAsErrorStillClosesLikeWeb() {
            const dialog = make(saveFactory)
            dialog.begin({id: "b1", title: "x"})
            reply("POST /api/books/b1/save", {status: 500, data: {error: "Hết chỗ"}})
            findChild(dialog, "saveGo").activated()
            compare(Api.notice, "Chưa lưu được file sách\nHết chỗ")
            verify(!dialog.open)
        }

        // ---------- mục menu: chặn / chỉ Studio ----------
        function test_menuItemsEditable() {
            const items = make(itemsFactory, {width: 280, book: textBook()})
            compare(items.editable, true)
            verify(findChild(items, "menuEdit").visible)
            verify(findChild(items, "menuSaveAs").visible)
            verify(!findChild(items, "menuBlocked").visible)
        }
        function test_menuItemsBlockedExplainsWhy() {
            const items = make(itemsFactory, {width: 280, book: {id: "x", stage: "audio", capabilities: {workshop: false, toolchain: true, link: true}}})
            compare(items.editable, false)
            verify(!findChild(items, "menuEdit").visible)
            verify(findChild(items, "menuBlocked").visible)
            compare(findChild(items, "menuBlocked").caption, "Sửa ở máy gốc.")
            verify(!findChild(items, "menuStudioOnly").visible)       // cuốn nghe thẳng: không có gì để nói về Studio
        }
        function test_menuItemsStudioOnlyNamesWhatIsMissing() {
            const items = make(itemsFactory, {width: 280, book: {id: "x", stage: "audio", capabilities: {workshop: false, toolchain: false, link: false}}})
            verify(findChild(items, "menuStudioOnly").visible)
            compare(findChild(items, "menuStudioOnly").label, "Giọng và lời đọc")
            compare(findChild(items, "menuStudioOnly").caption, "Cần cài Studio")
            items.book = {id: "x", stage: "audio", capabilities: {workshop: false, toolchain: true, link: false, sync: true}}
            compare(findChild(items, "menuStudioOnly").caption, "Làm ở Studio trên máy tính")
            items.book = {id: "x", stage: "text", capabilities: {workshop: false, toolchain: false, link: false}}
            verify(!findChild(items, "menuStudioOnly").visible)       // sách chỉ có chữ: chưa có giọng nào để đổi
        }
        function test_menuSaveNeedsEdits() {
            const items = make(itemsFactory, {width: 280, book: Object.assign(textBook(), {edits: 0})})
            verify(!findChild(items, "menuSave").enabled)
            items.book = Object.assign(textBook(), {edits: 2})
            verify(findChild(items, "menuSave").enabled)
        }

        // ---------- lối vào ở trang sách: nút "Thêm" -> "Sửa thông tin" ----------
        function test_bookPageEntryOpensEditor() {
            const page = make(pageFactory, {book: {bookId: "b1", title: "Tên cũ"}})
            let sent = null
            page.editRequested.connect(function(data) { sent = data })
            tryVerify(function() { return findChild(page, "bookMore").visible })
            findChild(page, "bookMore").clicked()
            wait(100)
            findChild(page, "menuEdit").clicked()
            verify(sent !== null)
            compare(sent.id, "b1")
            compare(Nav.layers.length, 0)                           // bảng nổi đã đóng
        }
        function test_bookPageEntryExplainsBlockedBook() {
            server = Object.assign(textBook(), {capabilities: {workshop: false, toolchain: true, link: true}})
            const page = make(pageFactory, {book: {bookId: "b1", title: "Tên cũ"}})
            tryVerify(function() { return findChild(page, "bookMore").visible })
            findChild(page, "bookMore").clicked()
            tryVerify(function() { return findChild(page, "menuBlocked") && findChild(page, "menuBlocked").visible })
            verify(!findChild(page, "menuEdit").visible)
        }

        // ---------- nhạc nền ----------
        function musicView() {
            return {hasMusic: true, enabled: true, levelDb: -20, defaultLevelDb: -20, cues: [
                {key: "c1", chapterId: 1, chapter: "Chương 1", start: 5, end: 65, title: "Đêm yên", creator: "Ai đó", silenced: false},
                {key: "c2", chapterId: 1, chapter: "Chương 1", start: 70, end: 130, title: "", creator: "", silenced: true, pinned: true}]}
        }
        function test_musicSwitchLevelSilenceAndSwap() {
            server = studioBook()
            reply("GET /api/books/b1/music", {status: 200, data: musicView()})
            reply("PUT /api/books/b1/music", function(body) { const view = musicView(); if (body.enabled !== undefined) view.enabled = body.enabled; return {status: 200, data: view} })
            reply("GET /api/books/b1/music/scenes/c1/alternatives", {status: 200, data: {mine: [{link: "local:" + "a".repeat(40), title: "Bài của tôi", creator: "Tôi", duration: 95, analysed: true, fits: true}]}})
            const dialog = make(editFactory)
            dialog.begin(server)
            settle()
            const music = findChild(dialog, "musicSwitch")
            verify(music !== null)
            compare(music.checked, true)
            music.toggled(false)
            compare(calls("PUT", "/api/books/b1/music")[0].body.enabled, false)
            findChild(dialog, "musicLevel").picked(-28)
            compare(calls("PUT", "/api/books/b1/music")[1].body.levelDb, -28)
        }
        function test_musicLoadErrorShowsRetry() {
            server = studioBook()
            reply("GET /api/books/b1/music", {status: 500, data: {error: "x"}})
            const dialog = make(editFactory)
            dialog.begin(server)
            settle()
            compare(Api.notice, "")
        }

        // ---------- tên dài xuống dòng, không cắt ----------
        function test_longTitleWrapsAndDialogFits() {
            server.title = longName.repeat(1)
            const dialog = make(editFactory)
            dialog.begin(server)
            const title = findChild(dialog, "editTitle")
            verify(title.height > 40)
            title.text = longName.repeat(2).slice(0, 160)
            verify(title.height > 60)
            const author = findChild(dialog, "editAuthor")
            author.text = "Tác giả " + longName
            verify(author.height > 60)
            verify(findChild(dialog, "editSaveTitle").x + findChild(dialog, "editSaveTitle").width <= dialog.bodyWidth + 1)
        }

        // ---------- ảnh ----------
        function shot(name, item) {
            const target = item || host
            target.Window.window.update()
            waitForRendering(target)
            wait(450)
            qtGlyphAudit.scan()
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; init(); make() } }
        function fixtureResults() {
            const out = []
            const names = [["Throne of Magical Arcana", "Andrew Rowe", "iTunes"], ["Throne of Magical Arcana: Tập mười sáu của bộ truyện dài", "Một tác giả có tên rất dài", "Open Library"],
                           ["Arcane Ascension", "Andrew Rowe", "Google Books"], ["Sorcerous Rise", "", "iTunes"], ["Cuốn thứ năm", "X", "Open Library"], ["Cuốn thứ sáu", "Y", "Google Books"]]
            for (const n of names) out.push({title: n[0], author: n[1], provider: n[2], thumb: "", url: "https://fixture/" + out.length})
            return out
        }
        function test_shots() {
            both(function() {
                for (const width of [1440, 760]) {
                    host.width = width
                    server = Object.assign(textBook(), {title: longName + longName, author: "Một tác giả có tên rất dài " + longName, cover: {version: 1}})
                    reply("GET /api/books/b1/readings", {status: 200, data: {readings: [{surface: "Haru", spoken: "Ha-ru"}, {surface: "Nguyễn Văn Tuấn Anh", spoken: "Nguyễn Văn Tuấn Anh"}]}})
                    host.height = 1500          // cao hơn nội dung: chụp cả hộp không cuộn
                    Platform.setSetting("fold.edit-book.readings", "1")
                    const dialog = make(editFactory, {width: width})
                    dialog.begin(server)
                    findChild(dialog, "editTitle").text = server.title.slice(0, 160)
                    settle()
                    shot("editbook_main_" + width, host)
                    dialog.destroy()
                    Platform.setSetting("fold.edit-book.readings", "0")
                    // sách đã có giọng: mục nhạc nền mở ra
                    Platform.setSetting("fold.edit-book.music", "1")
                    Platform.setSetting("fold.my-music.library", "1")
                    server = studioBook()
                    reply("GET /api/books/b1/music", {status: 200, data: musicView()})
                    reply("GET /api/music/local", {status: 200, data: {tracks: [{link: "local:" + "a".repeat(40), title: "Bài nhạc của tôi", creator: "Tôi", duration: 95, analysed: false, name: "x", bytes: 1}], module: {state: "missing", total: 820000000, done: 0, error: "", analysing: false, metered: false}}})
                    const audio = make(editFactory, {width: width})
                    audio.begin(Object.assign(studioBook(), {edits: 2}))
                    settle()
                    shot("editbook_music_" + width, host)
                    audio.destroy()
                    Platform.setSetting("fold.edit-book.music", "0")
                    Platform.setSetting("fold.my-music.library", "0")
                    host.height = 900
                    // tìm bìa
                    server = textBook()
                    reply("GET /api/books/b1/cover/search?q=" + encodeURIComponent("Tên cũ"), {status: 200, data: {results: fixtureResults(), failed: []}})
                    const search = make(editFactory, {width: width})
                    search.begin(server)
                    search.search()
                    settle()
                    shot("editbook_cover_" + width, host)
                    search.destroy()
                    // tìm bìa lỗi
                    reply("GET /api/books/b1/cover/search?q=" + encodeURIComponent("Tên cũ"), {status: 200, data: {results: [], failed: ["google_books", "open_library"]}})
                    const failed = make(editFactory, {width: width})
                    failed.begin(server)
                    failed.search()
                    settle()
                    shot("editbook_cover_error_" + width, host)
                    failed.destroy()
                    // hỏi lại bỏ thay đổi
                    const revert = make(editFactory, {width: width})
                    revert.begin(textBook())
                    revert.askRevert()
                    settle()
                    revert.scroll.contentY = Math.max(0, revert.scroll.contentHeight - revert.scroll.height)
                    shot("editbook_revert_" + width, host)
                    revert.destroy()
                }
                host.width = 1440
                const rename = make(renameFactory)
                rename.begin(textBook(), {id: 7, title: "Chương 7", subtitle: "", fullTitle: longName})
                settle()
                shot("editbook_rename", host)
                rename.destroy()
                const rename2 = make(renameFactory)
                rename2.begin(studioBook(), {id: 7, title: "Chương 7", subtitle: "Hồi kết", fullTitle: "Chương 7 - Hồi kết"})
                settle()
                shot("editbook_rename_two", host)
                rename2.destroy()
                const page = make(pageFactory, {book: {bookId: "b1", title: "Tên cũ"}})
                tryVerify(function() { return findChild(page, "bookMore").visible })
                findChild(page, "bookMore").clicked()
                settle()
                shot("editbook_menu", host)
                Nav.back()
                page.destroy()
                server = Object.assign(textBook(), {capabilities: {workshop: false, toolchain: false, link: true}})
                const blocked = make(pageFactory, {book: {bookId: "b1", title: "Tên cũ"}})
                tryVerify(function() { return findChild(blocked, "bookMore").visible })
                findChild(blocked, "bookMore").clicked()
                settle()
                shot("editbook_menu_blocked", host)
                Nav.back()
                blocked.destroy()
                const saveAs = make(saveFactory)
                saveAs.begin({id: "b1", title: "x", wishes: 2})
                settle()
                shot("editbook_saveas", host)
                saveAs.destroy()
            })
        }
    }
}
