import QtQuick
import QtTest
import ABook

// D4: mỗi mục một nhóm phép thử (hành vi + chuyển động) và ảnh sáng / tối ghi ra build/d2shots/d4_*.png:
//   1. màn đọc "Đọc chương này" (menu "…" của dòng chương, bấm dòng chương chưa có audio): ReaderScreen + ChapterText + ReadAlongView
//   2. lời báo chồng như sonner (visibleToasts 2): Api.toasts + Toast.qml, "Chi tiết" (ToastDetails)
// Player / ReadAlong / ChapterText là bản C++ thật trên âm thanh + mạng giả (tests/test_width.cpp, cuốn "reader"); HTTP của QML qua DesktopApi giả.
Item {
    id: host
    width: 1280
    height: 860
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: bookFactory; BookPage {} }
    Component { id: readerFactory; ReaderScreen {} }
    Component { id: readFactory; ReadAlongView {} }
    Component { id: toastFactory; Toast {} }
    SignalSpy { id: spy }

    TestCase {
        id: test
        name: "D4"
        when: windowShown

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
            const img = grabImage(target)
            const path = Qt.resolvedUrl("../../build/d2shots/d4_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
        function both(make) { for (const mode of ["light", "dark"]) { Theme.mode = mode; make() } }

        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "0.4.147"}
            Api.loaded = true
            Api.saving = false
            Api.toasts = []
            Api.reader = ({})
            Api.toasts = []
            Api.readerLoaded = false
            Nav.layers = []
            Nav.studioPeer = ""
            Theme.reduceMotion = true
            Theme.readingSurface = "auto"
            // trình phát đứng ở cuốn khác: câu đang nghe của phép thử trước không kéo màn đọc đi
            if (Player.bookId !== "width") { Player.open("width", 1, 0, true); Player.pause() }
        }
        function cleanup() {
            Theme.mode = "auto"; Theme.reduceMotion = false; Theme.readingSurface = "auto"
            Nav.layers = []; Nav.studioPeer = ""; Api.toasts = []
            DesktopApi.delayed = false
            if (Player.playing) Player.pause()
        }

        // ================= 1. màn đọc "Đọc chương này" =================
        function readerBook(over) {
            const chapters = [1, 2, 3, 4].map(n => ({id: n, title: "Chương " + n, subtitle: "Tên " + n, state: n === 3 ? "text" : null, available: n !== 3}))
            return Object.assign({id: "reader", title: "Sách reader", chapters: chapters, records: [{id: "r1", active: true}], state: {}}, over || {})
        }
        function makeReader(chapterId, over) {
            const page = createTemporaryObject(readerFactory, host, {width: 1100, height: 760, book: readerBook(over), chapterId: chapterId || 1})
            verify(page !== null)
            return page
        }
        function chapterText(page) { return one(page, "readerText").source }
        // Chữ đã có và màn đã tới chỗ mở (restore() đặt chỗ ở lượt sự kiện kế)
        function ready(page) { tryCompare(chapterText(page), "status", "ready", 3000); wait(50) }
        function bookPage(id) {
            reply("GET /api/listen/books/" + id, {status: 200, data: readerBook({id: id})})
            const page = createTemporaryObject(bookFactory, host, {width: 1200, height: 800, book: {bookId: id, title: "Sách " + id}})
            tryVerify(function() { return all(page, "bookChapterRow").length > 2 }, 3000)
            tryVerify(function() { return page.fullBook.id === id })
            return page
        }
        function rowOf(page, number) { return all(page, "bookChapterRow").filter(r => r.title === "Chương " + number)[0] }

        function test_menuHasReadThisChapterInWebOrder() {
            const page = bookPage("width")
            spy.clear(); spy.target = page; spy.signalName = "readRequested"
            one(rowOf(page, 2), "chapterMore").clicked()
            const read = one(page, "chapterRead")
            compare(read.text, "Đọc chương này")
            compare(read.icon, "book-open")
            // thứ tự của web: Nghe từ đầu chương, Đọc chương này, Đã nghe xong, Đổi tên chương…
            tryVerify(function() { return one(page, "chapterFromStart").y < read.y && read.y < one(page, "chapterDone").y })
            // cuốn không sửa được: ba hàng, bảng cao đúng ba hàng
            compare(one(page, "chapterMenu").children[one(page, "chapterMenu").children.length - 1].height,
                    3 * Theme.buttonHeight + 2 * one(page, "chapterMenu").pad)
            read.clicked()
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0].id, "width")
            compare(spy.signalArguments[0][1], 2)
            verify(!one(page, "chapterMenu").open)
        }
        function test_menuClickDoesNotReachTheRowBeneath() {
            const page = bookPage("width")
            Player.pause()
            const before = Player.chapterId
            spy.clear(); spy.target = page; spy.signalName = "readRequested"
            one(rowOf(page, 2), "chapterMore").clicked()
            const menu = one(page, "chapterMenu")
            tryCompare(menu, "shown", 1)
            mouseClick(one(page, "chapterRead"))
            compare(spy.count, 1)
            wait(50)
            compare(Player.chapterId, before, "bấm hàng của menu không phát dòng chương nằm dưới nó")
            verify(!Player.playing)
        }
        function test_tapsOnTheBarStayOnTheBar() {
            const page = makeReader(1)
            ready(page)
            tryCompare(one(page, "readerControls"), "opacity", 1)
            mouseClick(one(page, "readerType"))
            tryCompare(one(page, "readerTypePanel"), "shown", 1)
            mouseClick(all(one(page, "readerSizes"), "readerChoice")[1])
            wait(50)
            compare(Player.bookId, "width", "bấm thanh / hộp cỡ chữ không nghe chữ bên dưới")
            compare(Api.reader.size, 18)
            one(page, "readerTypePanel").close()
        }
        function test_rowWithoutAudioOpensReaderAndStillHasMenu() {
            const page = bookPage("reader")
            spy.clear(); spy.target = page; spy.signalName = "readRequested"
            const row = rowOf(page, 3)
            verify(!row.playable)
            verify(row.hasMenu)
            mouseClick(row, 60, row.height / 2)
            compare(spy.count, 1)
            compare(spy.signalArguments[0][1], 3)
            verify(!Player.playing)
            // menu của chương chưa có audio: chỉ "Đọc chương này" (và đổi tên nếu được)
            one(row, "chapterMore").clicked()
            tryVerify(function() { return one(page, "chapterRead").visible })
            verify(!one(page, "chapterFromStart").visible)
            verify(!one(page, "chapterDone").visible)
        }
        function test_readerHeaderTextHintNextAndControls() {
            const page = makeReader(1)
            ready(page)
            compare(one(page, "readerTitle").text, "Tên 1")
            compare(one(page, "readerBack").tip, "Về trang sách (Esc)")
            compare(one(page, "readerBack").icon, "arrow-left")
            tryVerify(function() { return hasText(page, "Bấm chữ để nghe từ đó.") })
            compare(one(page, "readerPrevious").tip, "Chương trước")
            compare(one(page, "readerPrevious").icon, "skip-back")
            verify(!one(page, "readerPrevious").enabled)
            compare(one(page, "readerNextChapter").tip, "Chương sau")
            compare(one(page, "readerNextChapter").icon, "skip-forward")
            compare(one(page, "readerListen").text, "Nghe từ đây")
            compare(one(page, "readerListen").icon, "headphones")
            compare(one(page, "readerType").tip, "Cỡ chữ và giãn dòng")
            compare(one(page, "readerType").icon, "type")
            compare(one(page, "readerControls").Accessible.name, "Điều khiển đọc")
            // cuối chương: thẻ "Chương tiếp theo"
            const list = one(page, "readerText").view
            list.positionViewAtEnd()
            tryVerify(function() { return hasText(page, "Chương tiếp theo") && hasText(page, "Tên 2") })
            mouseClick(one(page, "readerNext"))
            compare(page.chapterId, 2)
        }
        function test_readerUsesReadingSurfaceAndTheSameSizeAsReadAlong() {
            const page = makeReader(1)
            ready(page)
            const view = one(page, "readerText")
            Theme.readingSurface = "ivory"
            compare(String(view.surface.bg), String(Theme.readingSurfaces.ivory.bg))
            compare(view.fontPx, Theme.sizeReading)
            compare(view.leading, Theme.lineHeightReading)
            // hộp "Cỡ chữ và giãn dòng": mở trên nút, chọn 24 và 1,9
            one(page, "readerType").clicked()
            const panel = one(page, "readerTypePanel")
            tryCompare(panel, "shown", 1)
            verify(hasText(panel, "Cỡ chữ") && hasText(panel, "Giãn dòng") && hasText(panel, "1,7"))
            const sizes = all(one(page, "readerSizes"), "readerChoice")
            compare(sizes.map(c => c.Accessible.name).join("|"), "Cỡ chữ 16|Cỡ chữ 18|Cỡ chữ 20|Cỡ chữ 22|Cỡ chữ 24")
            mouseClick(sizes[4])
            mouseClick(all(one(page, "readerLeadings"), "readerChoice")[2])
            compare(Api.reader.size, 24)
            compare(Api.reader.leading, 1.9)
            compare(view.fontPx, 24)
            compare(view.leading, 1.9)
            compare(JSON.parse(Platform.store["abook-reader"]).size, 24)
            // "Đọc theo" của Đang nghe dùng cùng cỡ
            const along = createTemporaryObject(readFactory, host, {width: 600, height: 400})
            compare(along.fontPx, 24)
            compare(along.leading, 1.9)
            panel.close()
        }
        function test_typeChoiceLineSlides() {
            Theme.reduceMotion = false
            const page = makeReader(1)
            ready(page)
            one(page, "readerType").clicked()
            tryCompare(one(page, "readerTypePanel"), "shown", 1)
            const line = one(one(page, "readerSizes"), "readerChoiceLine")
            const sizes = all(one(page, "readerSizes"), "readerChoice")
            tryCompare(line, "x", sizes[2].x)
            mouseClick(sizes[0])
            let mid = false
            tryVerify(function() { if (line.x > sizes[0].x + 1 && line.x < sizes[2].x - 1) mid = true; return line.x === sizes[0].x }, 2000)
            verify(mid, "gạch chân trượt, không nhảy")
            one(page, "readerTypePanel").close()
        }
        function test_listenHereStartsAtTheFirstVisibleSentence() {
            const page = makeReader(1)
            ready(page)
            const list = one(page, "readerText").view
            const item = list.itemAtIndex(1)
            verify(item !== null)
            list.contentY = item.y + 4
            wait(50)
            const first = one(page, "readerText").firstVisibleSegment()
            verify(first >= 1)
            mouseClick(one(page, "readerListen"))
            tryCompare(Player, "bookId", "reader")
            compare(Player.chapterId, 1)
            verify(Player.playing)
            verify(Math.abs(Player.clock.position - first * 2) < 0.5, "nghe từ câu đầu còn thấy: " + Player.clock.position)
            compare(Api.reader.tapped, true)
            tryVerify(function() { return !hasText(page, "Bấm chữ để nghe từ đó.") })    // đã nghe từ một câu: thôi nhắc
            Player.pause()
        }
        function test_playingSentenceLightsUpOnlyInItsChapter() {
            Player.open("reader", 1, 10.5, true); Player.pause()
            const page = makeReader(1)
            ready(page)
            const text = chapterText(page)
            verify(text.listeningHere)
            tryCompare(text, "currentSegment", 5)
            page.chapterId = 2
            tryCompare(text, "currentSegment", -1)
        }
        function test_readerFollowsTheVoiceToTheNextChapter() {
            Player.open("reader", 1, 0, true); Player.pause()
            const page = makeReader(1)
            ready(page)
            Player.next()
            tryCompare(page, "chapterId", 2)
            // đang mở chương khác chương đang nghe: để yên
            page.chapterId = 3
            Player.previous()
            wait(50)
            compare(page.chapterId, 3)
        }
        function test_chapterSwapSlidesIn() {
            Theme.reduceMotion = false
            const page = makeReader(1)
            ready(page)
            tryCompare(one(page, "readerControls"), "opacity", 1)
            mouseClick(one(page, "readerNextChapter"))
            compare(page.chapterId, 2)
            let mid = false
            tryVerify(function() { if (page.swapT > 0.05 && page.swapT < 0.95) mid = true; return page.swapT === 1 }, 2000)
            verify(mid, "tên + chữ chương mới trôi vào, không đổi cứng")
            compare(page.index, 1)
        }
        function test_textOnlyChapterReadsWithoutListen() {
            const page = makeReader(3)
            ready(page)
            verify(!chapterText(page).timed)
            tryVerify(function() { return hasText(page, "Máy này chưa có giọng đọc.") })
            verify(hasText(page, "Đoạn một của chương chỉ có chữ."))
            verify(!shown(one(page, "readerListen")))
        }
        function test_chapterWithoutScriptShowsWhy() {
            const missing = makeReader(2)
            tryCompare(chapterText(missing), "status", "failed", 3000)
            tryVerify(function() { return hasText(missing, "Không mở được chương này") })
            verify(hasText(missing, "Chương có thể không còn trong sách."))
            verify(hasText(missing, "Về trang sách"))
            const silent = makeReader(4)
            tryCompare(chapterText(silent), "status", "failed", 3000)
            tryVerify(function() { return hasText(silent, "Máy giữ sách chưa trả lời.") })
        }
        function test_readingPositionIsSavedAndRestored() {
            const page = makeReader(1)
            ready(page)
            const list = one(page, "readerText").view
            list.positionViewAtIndex(12, ListView.Beginning)
            list.contentY += 1
            const index = one(page, "readerText").firstVisibleSegment()
            verify(index >= 11 && index <= 13, "câu đầu còn thấy " + index)
            tryVerify(function() { return calls("POST", "/api/listen/books/reader/reading").length > 0 }, 4000)
            const body = calls("POST", "/api/listen/books/reader/reading").slice(-1)[0].body
            compare(body.chapterId, 1)
            compare(body.index, index)
            compare(body.record, "r1")
            verify(/^fnv1a64:[0-9a-f]{16}$/.test(body.anchor.textHash))
            verify(body.rev.counter >= 1)
            compare(body.pending, undefined)
            const local = JSON.parse(Platform.store["abook-reading-reader#r1"])
            compare(local.index, index)
            compare(local.pending, false)          // ACK đúng phiên bản: bản trên máy thôi chờ
            page.destroy()
            // mở lại: tới đúng chỗ đọc dở của hồ sơ
            Platform.reset()
            const again = makeReader(1, {state: {reading: body}})
            ready(again)
            tryVerify(function() { return Math.abs(one(again, "readerText").firstVisibleSegment() - index) <= 1 }, 2000)
        }
        function test_saveFailureKeepsLocalCopyAndSays() {
            reply("POST /api/listen/books/reader/reading", {status: 500, data: {message: "Ổ đĩa đầy."}})
            const page = makeReader(1)
            ready(page)
            const list = one(page, "readerText").view
            list.positionViewAtIndex(8, ListView.Beginning)
            list.contentY += 1
            tryVerify(function() { return Api.notice !== "" }, 4000)
            compare(Api.notice, "Chưa lưu được chỗ đọc vào hồ sơ\nBạn vẫn có bản lưu trên máy này. Ổ đĩa đầy.")
            verify(JSON.parse(Platform.store["abook-reading-reader#r1"]).pending)
        }
        function test_controlsFadeOnScrollAndComeBackOnTap() {
            Theme.reduceMotion = false
            const page = makeReader(1)
            ready(page)
            const bar = one(page, "readerControls")
            tryCompare(bar, "opacity", 1)
            const restY = bar.y
            one(page, "readerText").userScrolled()
            compare(page.controls, false)
            let moved = false
            tryVerify(function() { if (bar.y > restY + 1) moved = true; return bar.opacity === 0 }, 2000)
            verify(moved, "thanh trôi xuống khi khuất")
            one(page, "readerText").pageTapped()
            tryCompare(bar, "opacity", 1)
            tryCompare(bar, "y", restY)
        }
        function test_toastSitsUnderTheReaderHeader() {
            const page = makeReader(1)
            ready(page)
            const header = one(page, "readerHeader")
            compare(Nav.toastTop, header.mapToItem(null, 0, header.height).y + 8)
            page.destroy()
            wait(0)
            compare(Nav.toastTop, 0)
        }
        // ================= 2. lời báo chồng như sonner =================
        function makeToaster() {
            Api.toasts = []
            const toaster = createTemporaryObject(toastFactory, host, {x: host.width - 356 - 16, y: 16})
            verify(toaster !== null)
            return toaster
        }
        function cards(toaster) { return all(toaster, "toastCard") }
        function cardOf(toaster, title) { return cards(toaster).filter(c => c.shownEntry && c.shownEntry.title === title)[0] }
        function settled(toaster) { return cards(toaster).every(c => Math.abs(c.y - c.targetY) < 0.5 && Math.abs(c.opacity - c.targetOpacity) < 0.01) }
        function test_twoToastsStackThirdHides() {
            const toaster = makeToaster()
            Api.toast("Lời thứ nhất", {duration: 60000})
            Api.toast("Lời thứ hai", {duration: 60000})
            tryVerify(function() { return settled(toaster) })
            const front = cardOf(toaster, "Lời thứ hai"), back = cardOf(toaster, "Lời thứ nhất")
            compare(front.order, 0)
            compare(front.y, 0)
            compare(front.scale, 1)
            // thẻ sau nấp dưới: thấp hơn 14 px, nhỏ đi 5 %, cao bằng thẻ trước, chữ ẩn
            compare(back.order, 1)
            compare(back.y, 14)
            verify(Math.abs(back.scale - 0.95) < 0.001)
            compare(back.height, front.height)
            tryVerify(function() { return !shown(one(back, "toastTitle")) })
            compare(toaster.height, front.height + 14)
            Api.toast("Lời thứ ba", {duration: 60000})
            tryVerify(function() { return settled(toaster) })
            compare(cardOf(toaster, "Lời thứ nhất").opacity, 0)      // quá 2 thẻ: thẻ cũ nhất ẩn, chưa mất
            compare(Api.toasts.length, 3)
            compare(Api.notice, "Lời thứ ba")
            // khép thẻ trước: thẻ cũ nhất hiện lại ở chỗ thứ hai
            Api.dismiss(Api.toasts[0].id)
            tryVerify(function() { return settled(toaster) && cards(toaster).length === 2 })
            compare(cardOf(toaster, "Lời thứ nhất").opacity, 1)
            compare(cardOf(toaster, "Lời thứ nhất").y, 14)
            compare(Api.notice, "Lời thứ hai")
        }
        function test_hoverExpandsAndPauses() {
            const toaster = makeToaster()
            Api.toast("Lời thứ nhất", {duration: 400})
            Api.toast("Lời thứ hai", {duration: 400})
            tryVerify(function() { return settled(toaster) })
            mouseMove(toaster, toaster.width / 2, 10)
            verify(toaster.expanded)
            const front = cardOf(toaster, "Lời thứ hai"), back = cardOf(toaster, "Lời thứ nhất")
            tryVerify(function() { return settled(toaster) })
            compare(back.y, front.height + 14)                         // xoè: xếp dọc, cách 14
            compare(back.scale, 1)
            verify(shown(one(back, "toastTitle")))
            wait(700)
            compare(Api.toasts.length, 2, "rê chuột vào: mọi thẻ dừng đếm")
            mouseMove(host, 10, host.height - 10)
            tryCompare(Api, "notice", "", 3000)
        }
        function test_newToastSlidesInOthersSlideDown() {
            Theme.reduceMotion = false
            const toaster = makeToaster()
            Api.toast("Lời thứ nhất", {duration: 60000})
            tryVerify(function() { return settled(toaster) })
            const first = cardOf(toaster, "Lời thứ nhất")
            Api.toast("Lời thứ hai", {duration: 60000})
            const second = cardOf(toaster, "Lời thứ hai")
            let enter = false, push = false
            tryVerify(function() {
                if (second.y < -1) enter = true
                if (first.y > 0.5 && first.y < 13.5) push = true
                return settled(toaster)
            }, 2000)
            verify(enter, "thẻ mới trượt xuống từ trên")
            verify(push, "thẻ cũ trôi xuống chỗ thứ hai, không nhảy")
            // khép thẻ trước: nó trượt lên mất, thẻ sau trôi lên chỗ trước
            Api.dismiss(Api.toasts[0].id)
            let out = false, forward = false
            tryVerify(function() {
                if (second.y < -1) out = true
                if (first.y > 0.5 && first.y < 13.5) forward = true
                return cards(toaster).length === 1 && settled(toaster)
            }, 2000)
            verify(out && forward)
        }
        function test_reducedMotionOnlyFades() {
            Theme.reduceMotion = true
            const toaster = makeToaster()
            Api.toast("Lời thứ nhất", {duration: 60000})
            const card = cardOf(toaster, "Lời thứ nhất")
            let moved = false, faded = false
            tryVerify(function() { if (card.y !== 0) moved = true; if (card.opacity > 0 && card.opacity < 1) faded = true; return card.opacity === 1 }, 2000)
            verify(!moved && faded)
        }
        function test_sameIdReplacesInPlace() {
            const toaster = makeToaster()
            Api.toast("Chưa lưu được chỗ đọc vào hồ sơ\nLỗi một", {id: "reading-save", duration: 60000})
            Api.toast("Lời khác", {duration: 60000})
            Api.toast("Chưa lưu được chỗ đọc vào hồ sơ\nLỗi hai", {id: "reading-save", duration: 60000})
            compare(Api.toasts.length, 2)
            compare(Api.toasts[1].description, "Lỗi hai")
            tryVerify(function() { return settled(toaster) })
            compare(cards(toaster).length, 2)
        }
        function test_detailsOpensClosesAndHoldsTheToast() {
            Theme.reduceMotion = false
            const toaster = makeToaster()
            let ran = 0
            Api.toast("Chưa chỉnh được nhạc nền\nMáy chủ trả lời lỗi 500.", {duration: 400, action: {label: "Thử lại", run: function() { ran++ }}})
            tryVerify(function() { return settled(toaster) })
            const card = cards(toaster)[0]
            const button = one(card, "toastAction")
            compare(button.Accessible.name, "Chi tiết")
            mouseClick(button)
            const panel = one(toaster, "toastDetails")
            let mid = false
            tryVerify(function() { if (panel.shown > 0.05 && panel.shown < 0.95) mid = true; return panel.shown === 1 }, 2000)
            verify(mid, "bảng chi tiết mở bằng trượt + hiện dần")
            compare(panel.Accessible.name, "Chi tiết thông báo")
            verify(hasText(panel, "Máy chủ trả lời lỗi 500.") && hasText(panel, "Thử lại"))
            verify(panel.y >= card.y + card.height + 12 - 0.5)
            wait(700)
            compare(Api.toasts.length, 1, "đang đọc chi tiết: thẻ không tự khép")
            Nav.back()                                                  // Back đóng bảng trước
            tryCompare(panel, "shown", 0)
            compare(Api.toasts.length, 1)
            mouseClick(button)
            tryCompare(panel, "shown", 1)
            toaster.pressedAt(Qt.point(5, 5))                          // bấm chỗ khác trong cửa sổ
            tryCompare(panel, "shown", 0)
            mouseClick(button)
            tryCompare(panel, "shown", 1)
            mouseClick(one(toaster, "toastDetailsAction"))
            compare(ran, 1)
            compare(Api.toasts.length, 0)
        }
        function test_closeButtonSitsInTheCorner() {
            const toaster = makeToaster()
            Api.toast("Đã thêm sách vào thư viện", {duration: 60000})
            tryVerify(function() { return settled(toaster) })
            const card = cards(toaster)[0], close = one(card, "toastClose")
            compare(close.x + close.width, card.width - 12)            // styles.css: ✕ trong góc phải, cách 12
            compare(close.y, 16)
            compare(close.Accessible.name, "Đóng thông báo")
            mouseClick(close)
            compare(Api.toasts.length, 0)
        }
        function test_shotsToastStack() {
            both(function() {
                const toaster = makeToaster()
                Api.toast("Đã lưu file sách", {duration: 60000, action: {label: "Mở thư mục", run: function() {}}})
                Api.toast("Chưa lưu được chỗ đọc vào hồ sơ\nBạn vẫn có bản lưu trên máy này. Ổ đĩa đầy.", {duration: 60000})
                tryVerify(function() { return settled(toaster) })
                shot("toast_stack", host)
                mouseMove(toaster, toaster.width / 2, 10)
                tryVerify(function() { return toaster.expanded && settled(toaster) })
                shot("toast_expanded", host)
                mouseClick(one(cards(toaster).filter(c => c.order === 0)[0], "toastAction"))
                tryCompare(one(toaster, "toastDetails"), "shown", 1)
                shot("toast_details", host)
                toaster.closeDetails()
                mouseMove(host, 10, host.height - 10)
                Api.toasts = []
                toaster.destroy()
                wait(0)
            })
        }

        // ================= 1. (tiếp) màn đọc =================
        function test_shotsReader() {
            both(function() {
                const page = makeReader(1)
                ready(page)
                shot("reader", page)
                one(page, "readerType").clicked()
                tryCompare(one(page, "readerTypePanel"), "shown", 1)
                shot("reader_type", page)
                one(page, "readerTypePanel").close()
                page.destroy()
                const text = makeReader(3)
                ready(text)
                shot("reader_text_only", text)
                text.destroy()
            })
            Theme.mode = "light"
            for (const surface of ["paper", "ivory", "night"]) {
                Theme.readingSurface = surface
                const page = makeReader(1)
                ready(page)
                shot("reader_" + surface, page)
                page.destroy()
            }
        }
    }
}
