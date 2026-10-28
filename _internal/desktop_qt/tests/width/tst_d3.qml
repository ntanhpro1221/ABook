import QtQuick
import QtTest
import ABook

// D3: các chỗ hở D2 để lại, mỗi mục một nhóm phép thử (hành vi + chuyển động) và ảnh sáng / tối ghi ra build/d2shots/d3_*.png:
//   1. "Mở Studio" của máy tính đã ghép (OtherComputers -> Nav.studioPeer -> StudioScreen + PeerBar)
//   2. menu "…" của dòng chương ở trang sách: Nghe từ đầu chương, Đã nghe xong / Chưa nghe, Đổi tên chương… (hộp EditBookRename)
//   3. "Tự chọn nhạc nền" nạp lại nhạc của cuốn đang nghe ngay (Music.reload)
//   4. Phím tắt chữ (PlayerKeys + hộp Phím tắt), Âm thanh chạm (Feedback), Nền đọc (Theme.read trong ReadAlongView)
//   5. kênh "abook-update-checked" của vỏ (Backend.updateChecked) thay cho hỏi /api/app định kỳ
//   6. lời báo có nút (Api.toast + Toast: "Hoàn tác", "Mở thư mục")
// Player / Music / ReadAlong / Feedback là bản C++ thật trên âm thanh + mạng giả (tests/test_width.cpp); HTTP của QML qua DesktopApi giả.
Item {
    id: host
    width: 1280
    height: 860
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: studioFactory; StudioScreen {} }
    Component { id: devicesFactory; SettingsDevices {} }
    Component { id: bookFactory; BookPage {} }
    Component { id: renameFactory; EditBookRename {} }
    Component { id: listenFactory; SettingsListen {} }
    Component { id: lookFactory; SettingsLook {} }
    Component { id: keysFactory; PlayerKeys {} }
    Component { id: shortcutsFactory; ShortcutsDialog {} }
    Component { id: readFactory; ReadAlongView {} }
    Component { id: speedFactory; SpeedPopover {} }
    Component { id: switchFactory; Switch {} }
    Component { id: seekFactory; SeekBar {} }
    Component { id: updateFactory; AdvancedUpdate {} }
    Component { id: toastFactory; Toast {} }
    Component { id: templatesFactory; BookTemplates {} }
    Component { id: saveAsFactory; EditBookSaveAs {} }
    SignalSpy { id: spy }

    TestCase {
        id: test
        name: "D3"
        when: windowShown

        readonly property string peerId: "c0ffee000001"
        readonly property string appPath: "GET /api/peers/c0ffee000001/studio/api/app"

        function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function all(item, name, out) {
            out = out || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children || []) all(child, name, out)
            return out
        }
        function one(item, name) { const found = all(item, name); verify(found.length > 0, "thiếu " + name); return found[0] }
        function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
        function texts(item, out) {
            out = out || []
            if (item.text !== undefined && shown(item)) out.push(String(item.text))
            for (const child of item.children || []) texts(child, out)
            return out
        }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function shot(name, item) {
            const target = item || host
            waitForRendering(target)
            wait(300)
            qtGlyphAudit.scan()
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/d3_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        // Thanh phát đứng ở chương / giây cho trước, đang dừng (open không tự phát thì không đè sách đang nạp)
        function loadAt(chapter, at) { Player.open("width", chapter, at, true); Player.pause(); compare(Player.chapterId, chapter) }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }

        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "0.4.147"}
            Api.loaded = true
            Api.saving = false
            Api.notice = ""
            Nav.layers = []
            Nav.studioPeer = ""
            Theme.reduceMotion = true
            Theme.readingSurface = "auto"
            Feedback.sounds = true
        }
        function cleanup() {
            Theme.mode = "auto"; Theme.reduceMotion = false; Theme.readingSurface = "auto"
            Nav.layers = []; Nav.studioPeer = ""; Api.notice = ""
            DesktopApi.delayed = false
            if (Player.volume === 0) Player.toggleMute()
            Player.setRate(1)
        }

        // ================= 1. "Mở Studio" của máy tính đã ghép =================
        function peerApp(over) { return {status: 200, data: Object.assign({version: "0.4.147", peer: {id: peerId, name: "Máy bàn phòng làm việc"}}, over || {})} }
        function makeStudio() {
            const page = createTemporaryObject(studioFactory, host, {width: 1100, height: 760})
            verify(page !== null)
            return page
        }
        function test_openStudioButtonOpensPeerStudio() {
            const now = Date.now() / 1000
            reply("GET /api/sync", {status: 200, data: {enabled: false, wanted: false, devices: [], addresses: [], awayAddresses: []}})
            reply("GET /api/computers", {status: 200, data: {name: "NGDtuanh-PC", computers: [
                {id: peerId, name: "Máy bàn phòng làm việc", host: "192.168.1.40", port: 47630, connectedVia: "192.168.1.40:47630", lastSeen: now - 30, kind: "computer"}]}})
            reply("GET /api/computers/bluetooth", {status: 200, data: {devices: []}})
            Platform.setSetting("fold.other-computers." + peerId, "1")
            const page = createTemporaryObject(devicesFactory, host, {x: 100, width: 888})
            tryVerify(function() { return all(page, "openStudio").some(b => shown(b)) }, 3000)
            const button = all(page, "openStudio").filter(b => shown(b))[0]
            compare(button.text, "Mở Studio")
            compare(button.Accessible.name, "Mở Studio của Máy bàn phòng làm việc")
            compare(button.icon, "clapperboard")
            button.clicked()
            compare(Nav.studioPeer, peerId)
        }
        function test_peerStudioBarAndHome() {
            reply(appPath, peerApp())
            const page = makeStudio()
            compare(page.view, "own")
            verify(!shown(one(page, "peerBar")))
            Nav.openPeerStudio(peerId)
            compare(calls("GET", "/api/peers/" + peerId + "/studio/api/app").length, 1)
            compare(page.view, "open")
            tryVerify(function() { return shown(one(page, "peerBar")) })
            compare(one(page, "peerLine").text, "Đang mở Studio của Máy bàn phòng làm việc")
            compare(one(page, "peerHome").text, "Về máy này")
            tryVerify(function() { return shown(one(page, "projectsHeader")) })       // Studio của máy kia mở bằng cùng danh sách dự án
            one(page, "peerHome").clicked()
            compare(Nav.studioPeer, "")
            compare(page.view, "own")
            tryVerify(function() { return !shown(one(page, "peerBar")) })
        }
        function test_peerBarOpensAndClosesByHeight() {
            Theme.reduceMotion = false
            reply(appPath, peerApp())
            const page = makeStudio()
            const bar = one(page, "peerBar")
            Nav.studioPeer = peerId
            const full = 16 + 32 + 1
            let mid = false
            tryVerify(function() { if (bar.height > 2 && bar.height < full - 2) mid = true; return bar.height >= full - 0.5 }, 2000)
            verify(mid, "thanh mở ra theo chiều cao, không bật cứng")
            Nav.studioPeer = ""
            mid = false
            tryVerify(function() { if (bar.height > 2 && bar.height < full - 2) mid = true; return bar.height === 0 }, 2000)
            verify(mid, "thanh khép lại theo chiều cao")
        }
        function test_peerListenOnlyExplainsWhere() {
            reply(appPath, peerApp({listenOnly: true}))
            const page = makeStudio()
            Nav.studioPeer = peerId
            compare(page.view, "closed")
            tryVerify(function() { return shown(one(page, "studioClosed")) })
            compare(one(one(page, "studioClosed"), "emptyTitle").text, "Chỉ nghe - bật quyền sửa ở Máy bàn phòng làm việc: Cài đặt > Thiết bị")
            verify(hasText(page, "Sách của máy ấy vẫn nghe được ở Thư viện."))
            compare(one(page, "studioClosedLibrary").text, "Về Thư viện")
            one(page, "studioClosedLibrary").clicked()
            compare(Nav.studioPeer, "")
        }
        function test_peerSilentRetriesUntilBack() {
            reply(appPath, {status: 503, data: {error: "Máy bàn phòng làm việc không trả lời", unreachable: true}})
            const page = makeStudio()
            Nav.studioPeer = peerId
            compare(page.view, "trouble")
            tryVerify(function() { return shown(one(page, "peerTrouble")) })
            compare(one(one(page, "peerTrouble"), "emptyTitle").text, "Máy bàn phòng làm việc không trả lời")
            verify(hasText(page, "Studio tự mở khi máy ấy trả lời lại."))
            compare(one(page, "peerTroubleHome").text, "Về máy này")
            // máy ấy trả lời lại: lần hỏi kế (5 giây) tự mở Studio, người dùng không bấm gì
            reply(appPath, peerApp())
            tryVerify(function() { return page.view === "open" }, 7000)
            compare(calls("GET", "/api/peers/" + peerId + "/studio/api/app").length, 2)
        }
        function test_peerMismatchSaysWhyAndDoesNotRetry() {
            reply(appPath, {status: 409, data: {error: "Hai máy đang chạy hai bản ABook khác nhau", mismatch: true}})
            const page = makeStudio()
            Nav.studioPeer = peerId
            compare(page.view, "trouble")
            verify(!page.silent)
            tryVerify(function() { return shown(one(page, "peerTrouble")) })
            verify(!hasText(page, "Studio tự mở khi máy ấy trả lời lại."))
            one(page, "peerTroubleHome").clicked()
            compare(page.view, "own")
        }
        function test_peerViewSwapsToTheLatestState() {
            reply(appPath, peerApp())
            const page = makeStudio()
            Nav.studioPeer = peerId
            tryCompare(page, "shownView", "open")
            Nav.studioPeer = ""                       // hai lần đổi trong cùng một lượt: thân phải ra màn cuối
            reply(appPath, peerApp({listenOnly: true}))
            Nav.studioPeer = peerId
            tryCompare(page, "shownView", "closed")
            tryCompare(page, "phase", 1)
            verify(shown(one(page, "studioClosed")))
        }
        function test_peerLateAnswerAfterHomeIgnored() {
            DesktopApi.delayed = true
            reply(appPath, peerApp())
            const page = makeStudio()
            Nav.studioPeer = peerId
            compare(page.view, "loading")
            Nav.studioPeer = ""
            DesktopApi.finish()
            compare(page.view, "own")
            verify(page.peerInfo === null)
        }
        function test_shotsPeerStudio() {
            both(function() {
                reply(appPath, peerApp())
                let page = makeStudio()
                Nav.studioPeer = peerId
                shot("peer_open", page)
                Nav.studioPeer = ""
                reply(appPath, peerApp({listenOnly: true}))
                Nav.studioPeer = peerId
                shot("peer_listen_only", page)
                Nav.studioPeer = ""
                page.destroy()
            })
        }

        // ================= 2. menu "…" của dòng chương =================
        function fullBook(caps) {
            return {id: "width", title: "Sách width", capabilities: caps || {workshop: false, link: false, toolchain: true}, records: [{id: "r1", active: true}]}
        }
        function makeBook(caps) {
            reply("GET /api/listen/books/width", {status: 200, data: fullBook(caps)})
            const page = createTemporaryObject(bookFactory, host, {width: 1200, height: 800, book: {bookId: "width", title: "Sách width"}})
            verify(page !== null)
            tryVerify(function() { return all(page, "bookChapterRow").length > 3 }, 3000)
            return page
        }
        function rowOf(page, number) { return all(page, "bookChapterRow").filter(r => r.title === "Chương " + number)[0] }
        function test_chapterMoreShowsOnHoverAndOpensMenu() {
            const page = makeBook()
            loadAt(1, 0)
            const row = rowOf(page, 3)
            const more = one(row, "chapterMore")
            compare(more.Accessible.name, "Tuỳ chọn Chương 3 · Tên 3")
            verify(more.visible)
            compare(more.opacity, 0)           // chỉ hiện khi rê chuột vào hàng
            mouseMove(row, 40, row.height / 2)
            tryCompare(more, "opacity", 1)
            mouseClick(more)
            compare(Player.chapterId, 1, "bấm “…” không phát chương")
            verify(!Player.playing)
            const menu = one(page, "chapterMenu")
            verify(menu.open)
            compare(one(page, "chapterFromStart").text, "Nghe từ đầu chương")
            compare(one(page, "chapterDone").text, "Đã nghe xong")
            compare(one(page, "chapterRename").text, "Đổi tên chương…")
            compare(one(page, "chapterRename").icon, "text-cursor-input")
            compare(one(page, "chapterDone").icon, "check-check")
            verify(row.menuOpen)
            mouseMove(host, 5, 5)
            compare(more.opacity, 1)           // menu đang mở: nút giữ hiện
            Nav.back()
            verify(!menu.open)
        }
        function test_chapterRowClickStillPlays() {
            const page = makeBook()
            loadAt(1, 0)
            const row = rowOf(page, 3)
            mouseClick(row, 60, row.height / 2)
            tryCompare(Player, "chapterId", 3)
            verify(Player.playing)
            Player.pause()
        }
        function test_chapterMenuOpensAndClosesGeometrically() {
            Theme.reduceMotion = false
            const page = makeBook()
            const menu = one(page, "chapterMenu")
            one(rowOf(page, 2), "chapterMore").clicked()
            let mid = false
            tryVerify(function() { if (menu.shown > 0.05 && menu.shown < 0.95) mid = true; return menu.shown === 1 }, 2000)
            verify(mid)
            menu.close()
            tryVerify(function() { return menu.shown === 0 }, 2000)
        }
        function test_chapterMenuDoesNotCoverItsButton() {
            const page = makeBook()
            for (const number of [2, 9]) {
                const more = one(rowOf(page, number), "chapterMore")
                more.clicked()
                const menu = one(page, "chapterMenu")
                tryCompare(menu, "shown", 1)
                const panel = menu.children[menu.children.length - 1]
                const a = more.mapToItem(menu, 0, 0)
                verify(panel.y + panel.height <= a.y + 0.5 || panel.y >= a.y + more.height - 0.5,
                       "menu trên / dưới nút “…”, không đè lên nó (" + panel.y + "," + panel.height + " vs " + a.y + ")")
                compare(panel.height, 4 * Theme.buttonHeight + 2 * menu.pad)
                menu.close()
                tryCompare(menu, "shown", 0)
            }
        }
        function test_chapterMenuPlaysFromStart() {
            const page = makeBook()
            loadAt(1, 40)
            one(rowOf(page, 4), "chapterMore").clicked()
            one(page, "chapterFromStart").clicked()
            tryCompare(Player, "chapterId", 4)
            verify(Player.clock.position < 1)
            verify(!one(page, "chapterMenu").open)
            Player.pause()
        }
        function test_chapterMenuMarksDoneWithShownRecord() {
            const page = makeBook()
            one(rowOf(page, 5), "chapterMore").clicked()
            one(page, "chapterDone").clicked()
            const posted = calls("POST", "/api/listen/books/width/chapters/5/done")
            compare(posted.length, 1)
            compare(posted[0].body.done, true)
            compare(posted[0].body.record, "r1")
            verify(!one(page, "chapterMenu").open)
        }
        function test_chapterMenuRenameOpensDialogAndSaves() {
            const page = makeBook()
            const dialog = createTemporaryObject(renameFactory, host)
            page.renameRequested.connect((data, chapter) => dialog.begin(data, chapter))
            one(rowOf(page, 6), "chapterMore").clicked()
            one(page, "chapterRename").clicked()
            verify(dialog.open)
            compare(dialog.title, "Đổi tên chương")
            compare(dialog.label, "Chương 6")
            compare(dialog.name, "Tên 6")
            reply("PUT /api/books/width/chapters/6/title", {status: 200, data: {fullTitle: "Chương 6 · Hồi kết"}})
            dialog.save({title: "Chương 6", subtitle: "Hồi kết"})
            compare(calls("PUT", "/api/books/width/chapters/6/title")[0].body.subtitle, "Hồi kết")
            compare(Api.notice, "Đã đổi tên chương: Chương 6 · Hồi kết")
            verify(!dialog.open)
        }
        function test_chapterMenuNoRenameForLinkedBook() {
            const page = makeBook({workshop: false, link: true, toolchain: true})
            tryVerify(function() { return page.fullBook.id === "width" })
            verify(!page.canRename)
            one(rowOf(page, 1), "chapterMore").clicked()
            tryVerify(function() { return one(page, "chapterDone").visible })
            verify(!one(page, "chapterRename").visible)
        }
        function test_shotsChapterMenu() {
            both(function() {
                const page = makeBook()
                const row = rowOf(page, 3)
                mouseMove(row, 40, row.height / 2)
                one(row, "chapterMore").clicked()
                shot("chapter_menu", page)
                one(page, "chapterMenu").close()
                page.destroy()
            })
        }

        // ================= 3. "Tự chọn nhạc nền" nạp lại nhạc ngay =================
        function test_autoMusicReloadsPlayingBookNow() {
            loadAt(1, 0)
            const page = createTemporaryObject(listenFactory, host, {width: 700})
            const switches = all(page, "").filter(i => i.label === "Tự chọn nhạc nền" && i.toggled !== undefined && i.checked !== undefined && i.implicitWidth === 44)
            compare(switches.length, 1)
            const cues = WidthNet.count("GET", "/api/books/width/music/chapters/1")
            const views = WidthNet.count("GET", "/api/books/width/music")
            switches[0].clicked()
            compare(calls("PUT", "/api/preferences")[0].body.autoMusic, false)
            compare(WidthNet.count("GET", "/api/books/width/music/chapters/1"), cues + 1)
            compare(WidthNet.count("GET", "/api/books/width/music"), views + 1)
            compare(Api.notice, "Đã tắt tự chọn nhạc nền")
        }
        function test_autoMusicFailureDoesNotReload() {
            loadAt(1, 0)
            reply("PUT /api/preferences", {status: 500, data: {error: "Ổ đĩa đầy"}})
            const page = createTemporaryObject(listenFactory, host, {width: 700})
            const toggle = all(page, "").filter(i => i.label === "Tự chọn nhạc nền" && i.implicitWidth === 44)[0]
            const cues = WidthNet.count("GET", "/api/books/width/music/chapters/1")
            toggle.clicked()
            compare(WidthNet.count("GET", "/api/books/width/music/chapters/1"), cues)
            compare(Api.notice, "Chưa lưu được cài đặt\nỔ đĩa đầy")
        }

        // ================= 4a. Phím tắt chữ =================
        function key(k, text, modifiers) { return {key: k, text: text || "", modifiers: modifiers || 0, isAutoRepeat: false} }
        function test_letterShortcutsWork() {
            loadAt(2, 10)
            const keys = createTemporaryObject(keysFactory, host)
            spy.clear(); spy.target = keys; spy.signalName = "shortcutsRequested"
            verify(keys.handle(key(Qt.Key_M, "m")))
            compare(Player.volume, 0)
            verify(keys.handle(key(Qt.Key_M, "M", Qt.ShiftModifier)))
            compare(Player.volume, 0.9)
            const rate = Player.rate
            verify(keys.handle(key(Qt.Key_BracketRight, "]")))
            verify(Player.rate > rate)
            verify(keys.handle(key(Qt.Key_BracketLeft, "[")))
            compare(Player.rate, rate)
            verify(keys.handle(key(Qt.Key_Question, "?", Qt.ShiftModifier)))
            compare(spy.count, 1)
            // Shift + mũi tên: chương; mũi tên: 15 giây; Ctrl không thuộc phím của trình phát
            verify(keys.handle(key(Qt.Key_Right, "", Qt.ShiftModifier)))
            compare(Player.chapterId, 3)
            verify(keys.handle(key(Qt.Key_Left, "", Qt.ShiftModifier)))
            compare(Player.chapterId, 2)
            verify(!keys.handle(key(Qt.Key_M, "m", Qt.ControlModifier)))
            verify(!keys.handle(key(Qt.Key_A, "a")))
        }
        function test_letterShortcutsOffKeepsSpaceAndArrows() {
            loadAt(2, 30)
            const keys = createTemporaryObject(keysFactory, host, {letters: false})
            spy.clear(); spy.target = keys; spy.signalName = "shortcutsRequested"
            verify(!keys.handle(key(Qt.Key_M, "m")))
            compare(Player.volume, 0.9)
            verify(!keys.handle(key(Qt.Key_BracketRight, "]")))
            verify(!keys.handle(key(Qt.Key_Question, "?")))
            compare(spy.count, 0)
            verify(keys.handle(key(Qt.Key_Space, " ")))
            verify(Player.playing)
            verify(keys.handle(key(Qt.Key_Space, " ")))
            verify(!Player.playing)
            const at = Player.clock.position
            verify(keys.handle(key(Qt.Key_Left, "")))
            verify(Player.clock.position < at)
        }
        function test_shortcutsDialogSaysWhereToSwitch() {
            const dialog = createTemporaryObject(shortcutsFactory, host)
            dialog.show()
            compare(dialog.title, "Phím tắt")
            compare(dialog.description, "Dùng được ở mọi màn hình, trừ khi đang gõ chữ.")
            tryVerify(function() { return shown(one(dialog, "shortcutsTail")) })
            compare(one(dialog, "shortcutsTail").text, "Tắt phím một chữ cái ở Cài đặt › Giao diện.")
            dialog.letters = false
            compare(one(dialog, "shortcutsTail").text, "Phím một chữ cái đang tắt (bật ở Cài đặt › Giao diện). Space, mũi tên, Esc vẫn chạy.")
            verify(hasText(dialog, "Tắt / bật tiếng (đang tắt)"))
            Nav.back()
            verify(!dialog.open)
        }
        function test_settingsListStillHidesTailWhenOn() {
            const page = createTemporaryObject(lookFactory, host, {width: 700})
            const tail = one(page, "shortcutsTail")
            verify(!shown(tail))
            Api.preferences = {theme: "system", letterShortcuts: false}
            tryVerify(function() { return shown(tail) })
            compare(tail.text, "Phím một chữ cái đang tắt. Space, mũi tên, Esc vẫn chạy.")
        }
        function test_shotsShortcutsDialog() {
            both(function() {
                const dialog = createTemporaryObject(shortcutsFactory, host)
                dialog.show()
                shot("shortcuts")
                dialog.dismiss()
                dialog.destroy()
            })
        }

        // ================= 4b. Âm thanh chạm =================
        function test_touchSoundOnSwitchAndSpeed() {
            Player.pause()
            const before = Feedback.played
            const toggle = createTemporaryObject(switchFactory, host, {label: "Thử"})
            toggle.clicked()
            compare(Feedback.played, before + 1)
            compare(Feedback.lastKind, "toggle")
            Feedback.sounds = false              // "Âm thanh chạm" tắt
            toggle.clicked()
            compare(Feedback.played, before + 1)
            Feedback.sounds = true
            toggle.enabled = false               // công tắc mờ: không tiếng
            toggle.clicked()
            compare(Feedback.played, before + 1)
            // Tốc độ đọc: chọn một mức là "toggle"
            loadAt(1, 0)
            const speed = createTemporaryObject(speedFactory, host)
            const choices = all(speed, "").filter(i => i.clicked !== undefined && i.modelData === 1.5)
            verify(choices.length > 0)
            choices[0].clicked()
            compare(Feedback.played, before + 2)
            compare(Player.rate, 1.5)
        }
        function test_touchSoundTickWhenDraggingAcrossFifteenSeconds() {
            loadAt(1, 0)
            tryVerify(function() { return Player.clock.duration > 0 })
            const bar = createTemporaryObject(seekFactory, host, {x: 20, y: 20, width: 1000, height: 24})
            const before = Feedback.played
            const step = bar.width * 15 / Player.clock.duration     // px của 15 giây
            mousePress(bar, step * 0.2, 12)
            mouseMove(bar, step * 0.6, 12)                           // trong cùng khoảng 15 giây: không tiếng
            compare(Feedback.played, before)
            mouseMove(bar, step * 1.3, 12)                           // qua mốc 15 giây: "tích"
            compare(Feedback.played, before + 1)
            compare(Feedback.lastKind, "tick")
            mouseRelease(bar, step * 1.3, 12)
            mouseMove(bar, step * 2.5, 12)                           // rê chuột (không kéo): không tiếng
            compare(Feedback.played, before + 1)
        }
        function test_touchSoundSilentWhileBookPlays() {
            Player.open("width", 1, 0, true)
            tryVerify(function() { return Player.playing })
            const before = Feedback.played
            const toggle = createTemporaryObject(switchFactory, host, {label: "Thử"})
            toggle.clicked()
            compare(Feedback.played, before)
            Player.pause()
            toggle.clicked()
            compare(Feedback.played, before + 1)
        }

        // ================= 4c. Nền đọc =================
        function test_readingSurfaceFollowsSettingNotTheme() {
            const view = createTemporaryObject(readFactory, host, {width: 600, height: 500})
            const bg = one(view, "readingSurface")
            Theme.mode = "light"
            tryCompare(bg, "color", Qt.color("#fbfaf7"))                         // Tự động + sáng = Giấy
            Theme.mode = "dark"
            tryCompare(bg, "color", Qt.color("#121110"))                         // Tự động + tối = Đêm
            Theme.readingSurface = "ivory"                               // Ngà trong app tối: vẫn nền Ngà, chữ Ngà
            tryCompare(bg, "color", Qt.color("#f3ead8"))
            compare(String(view.surface.fg), "#3b2f1e")
            Theme.mode = "light"
            Theme.readingSurface = "night"
            tryCompare(bg, "color", Qt.color("#121110"))
            compare(view.surface.along, 0.18)
            compare(view.surface.word, 0.3)
            Theme.readingSurface = "paper"
            compare(view.surface.along, 0.26)
        }
        function test_readingSurfaceCrossFades() {
            Theme.reduceMotion = false
            Theme.mode = "light"
            const view = createTemporaryObject(readFactory, host, {width: 600, height: 500})
            const bg = one(view, "readingSurface")
            Theme.readingSurface = "night"
            wait(Theme.motionSlow / 3)
            verify(String(bg.color) !== "#121110" && String(bg.color) !== "#fbfaf7", "nền mờ chéo, không đổi cứng: " + bg.color)
            tryCompare(bg, "color", Qt.color("#121110"), 2000)
        }
        function test_shotsReadingSurfaces() {
            loadAt(1, 6)
            ReadAlong.active = true
            for (const surface of ["paper", "ivory", "night"]) {
                Theme.mode = "light"
                Theme.readingSurface = surface
                const view = createTemporaryObject(readFactory, host, {width: 720, height: 520})
                tryVerify(function() { return ReadAlong.status === "ready" }, 3000)
                shot("reading_" + surface, view)
                view.destroy()
            }
            ReadAlong.active = false
        }

        // ================= 5. kênh "abook-update-checked" =================
        function test_updateCheckedArrivesThroughShellChannel() {
            Api.info = {version: "0.4.147", dialogs: true, canCheckUpdate: true}
            const card = createTemporaryObject(updateFactory, host, {width: 600})
            card.check()
            verify(card.checking)
            Backend.updateChecked({state: "latest"})
            verify(!card.checking)
            compare(card.line.text, "ABook 0.4.147 là bản mới nhất.")
            card.check()
            Backend.updateChecked({state: "failed", message: "Bản chạy từ mã nguồn không tự cập nhật"})
            compare(card.line.tone, "error")
            compare(card.line.text, "Bản chạy từ mã nguồn không tự cập nhật")
            // không còn hỏi /api/app định kỳ trong lúc chờ
            card.check()
            wait(3300)
            compare(calls("GET", "/api/app").length, 0)
            Backend.updateChecked({state: "found"})
            compare(card.line, null)
            // kết quả tới khi không ai đang chờ: bỏ qua
            Backend.updateChecked({state: "latest"})
            compare(card.line, null)
        }
        function test_updateFailedEventReleasesInstall() {
            Api.info = {version: "0.4.147", dialogs: true, canCheckUpdate: true, update: {version: "0.4.148", notes: ""}}
            const card = createTemporaryObject(updateFactory, host, {width: 600})
            card.install()
            verify(card.installing)
            Backend.hostEvent("abook-update-failed", "Đường tải bản mới đứng yên quá lâu.")
            verify(!card.installing)
        }

        // ================= 6. lời báo có nút =================
        function makeToast() {
            const toast = createTemporaryObject(toastFactory, host, {x: host.width - 356 - 16, y: 16})
            verify(toast !== null)
            return toast
        }
        function test_toastShowsTitleDescriptionAndAction() {
            const toast = makeToast()
            let ran = 0
            Api.toast("Đã lưu file sách\nChưa có thay đổi nào - file giống bản gốc.", {duration: 8000, action: {label: "Mở thư mục", run: function() { ran++ }}})
            tryVerify(function() { return toast.t === 1 })
            compare(one(toast, "toastTitle").text, "Đã lưu file sách")
            compare(one(toast, "toastDescription").text, "Chưa có thay đổi nào - file giống bản gốc.")
            compare(toast.duration, 8000)
            const action = one(toast, "toastAction")
            verify(shown(action))
            compare(action.Accessible.name, "Mở thư mục")
            mouseClick(action)
            compare(ran, 1)
            compare(Api.notice, "")
            tryVerify(function() { return !toast.visible })
        }
        function test_plainNoticeHasNoActionAndExpires() {
            const toast = makeToast()
            Api.toast("Có nút", {action: {label: "Hoàn tác", run: function() {}}})
            Api.notice = "Đã đổi tên chương: Chương 1"   // gán thẳng: lời trơn, không mang nút của lời trước
            compare(Api.noticeAction, null)
            tryVerify(function() { return toast.t === 1 })
            verify(!shown(one(toast, "toastAction")))
            compare(toast.duration, 4000)
            tryCompare(Api, "notice", "", 6000)
        }
        function test_toastCloseButtonAndHoverPause() {
            const toast = makeToast()
            Api.toast("Đã xoá mẫu “Nhanh”", {duration: 300, action: {label: "Hoàn tác", run: function() {}}})
            mouseMove(toast, toast.width / 2, 20)
            wait(700)
            compare(Api.notice, "Đã xoá mẫu “Nhanh”", "rê chuột vào thì dừng đếm")
            compare(one(toast, "toastClose").Accessible.name, "Đóng thông báo")
            mouseClick(one(toast, "toastClose"))
            compare(Api.notice, "")
        }
        function test_sameToastAgainShowsAgain() {
            const toast = makeToast()
            Api.toast("Đã xoá mẫu “A”", {action: {label: "Hoàn tác", run: function() {}}})
            spy.clear(); spy.target = Api; spy.signalName = "noticeChanged"
            Api.toast("Đã xoá mẫu “A”", {action: {label: "Hoàn tác", run: function() {}}})
            verify(spy.count >= 2)
            compare(Api.notice, "Đã xoá mẫu “A”")
        }
        function test_toastSlidesAndScales() {
            Theme.reduceMotion = false
            const toast = makeToast()
            const card = toast.children[toast.children.length - 1]
            Api.notice = "Đã thêm sách vào thư viện"
            let mid = false
            tryVerify(function() { if (toast.t > 0.05 && toast.t < 0.95 && card.scale < 1) mid = true; return toast.t === 1 }, 2000)
            verify(mid, "mở bằng trượt + thu phóng")
            Api.notice = ""
            tryVerify(function() { return !toast.visible }, 2000)
        }
        function test_longToastWrapsNeverCut() {
            const toast = makeToast()
            const text = "Không lưu được mẫu\n" + "Tênkhôngcóchỗngắtrấtrấtrấtrấtrấtrấtrấtrấtrấtrấtrấtrấtrấtdài và một câu rất dài nữa để xuống nhiều dòng trong thẻ"
            Api.toast(text, {action: {label: "Hoàn tác", run: function() {}}})
            tryVerify(function() { return toast.t === 1 })
            const description = one(toast, "toastDescription")
            verify(description.lineCount > 1)
            verify(description.contentWidth <= description.width + 1)
            const action = one(toast, "toastAction")
            verify(description.parent.x + description.parent.width <= action.x, "chữ không chạy dưới nút")
            verify(toast.height >= description.y + description.height + 28, "thẻ cao theo chữ")
        }
        function test_templateUndoAndSaveAsFolderUseToastAction() {
            Api.preferences = {theme: "system", bookTemplates: [{name: "Nhanh gọn", narrator: "", profile: "fast", analysisModel: "", startNow: true, precastWait: false}]}
            reply("POST /api/book-templates", function(body) { return {status: 200, data: {bookTemplates: body.op === "delete" ? [] : Api.preferences.bookTemplates}} })
            const templates = createTemporaryObject(templatesFactory, host, {width: 600})
            templates.removeTemplate({name: "Nhanh gọn", profile: "fast"})
            compare(Api.notice, "Đã xoá mẫu “Nhanh gọn”")
            compare(Api.noticeAction.label, "Hoàn tác")
            compare(Api.noticeDuration, 10000)
            compare(all(templates, "undoDelete").length, 0)      // không còn nút Hoàn tác riêng trong trang
            Api.runNoticeAction()
            const posts = calls("POST", "/api/book-templates")
            compare(posts[posts.length - 1].body.op, "restore")
            // "Lưu thành…": "Mở thư mục" mở đúng thư mục vừa lưu
            const saveAs = createTemporaryObject(saveAsFactory, host)
            reply("POST /api/books/b1/save", {status: 200, data: {file: "D:/Sách/x.abook", folder: "D:/Sách", size: 10, edits: 2}})
            saveAs.quick({id: "b1"})
            compare(Api.notice, "Đã lưu file sách")
            compare(Api.noticeAction.label, "Mở thư mục")
            compare(Api.noticeDuration, 8000)
            Api.runNoticeAction()
            compare(calls("POST", "/api/reveal-export")[0].body.folder, "D:/Sách")
        }
        function test_shotsToast() {
            both(function() {
                const toast = makeToast()
                Api.toast("Đã lưu file sách\nChưa có thay đổi nào - file giống bản gốc.", {duration: 60000, action: {label: "Mở thư mục", run: function() {}}})
                shot("toast_action")
                Api.toast("Đã xoá mẫu “Truyện kinh dị đọc đêm khuya của bạn”", {duration: 60000, action: {label: "Hoàn tác", run: function() {}}})
                shot("toast_undo")
                Api.notice = ""
                toast.destroy()
            })
        }
    }
}
