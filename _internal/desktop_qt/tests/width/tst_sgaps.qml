import QtQuick
import QtTest
import "ModalLayer.js" as ModalLayer
import "VisualReady.js" as VisualReady
import ABook

// Lỗ "chỉ web" ở các màn Studio (SGAPS): "Các bước" + tiến độ cả sách đầu trang dự án, "Thử lại" của lỗi khởi động, "Dùng pin", hàng tiêu đề bảng chương,
// "Sửa chữ" / "Thu lại chương" trong hộp thu lại, lời mời "Duyệt" khi phân tích xong, đầu nhóm của ô chọn model và tên trợ năng còn thiếu.
// HTTP là DesktopApi giả; ảnh ghi ra build/d2shots/sgaps_*.png để tự nhìn.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: studioFactory; StudioScreen {} }
    Component { id: progressFactory; SidebarProgress { width: 220 } }
    Component {
        id: selectFactory
        Select {
            width: 320
            label: "Model phân tích"
            options: [{value: "", label: "Mặc định của ABook (khuyên dùng)"}, {header: "Bản khác (thử nghiệm)"},
                      {value: "a", label: "1. Bản thử nghiệm · nhanh"}, {value: "b", label: "2. Bản thử nghiệm"}]
        }
    }
    Component { id: sampleFactory; CastSample { clipId: "voice-Mai"; url: "x"; label: "Nghe thử giọng Mai"; stopLabel: "Dừng nghe Mai" } }
    SignalSpy { id: spy }

    TestCase {
        id: test
        name: "SGaps"
        when: windowShown

        function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function all(item, name) { return ModalLayer.findAll(item, name) }
        function one(item, name) { const found = all(item, name); verify(found.length > 0, "thiếu " + name); return found.filter(shown)[0] || found[0] }
        function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
        function texts(item) { return ModalLayer.collect(item, node => node.text !== undefined && shown(node)).map(node => String(node.text)) }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function hasPart(item, part) { return texts(item).some(t => t.indexOf(part) >= 0) }
        function shot(name, item) {
            const target = item || host
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            const path = Qt.resolvedUrl("../../build/d2shots/sgaps_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(VisualReady.grabTarget(host.Window.window, target)).save(path)
        }
        function both(name, item) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shot(name, item) } Theme.mode = "auto" }

        // ---- dữ liệu giả ----
        function stamp() { return Math.floor(Date.now() / 1000) }
        function book(id, over) {
            return Object.assign({
                id: id, title: "Cuốn " + id, statusLabel: "Hoàn tất", running: false, starting: false, paused: "", canPause: false, stopping: false,
                phase: "done", queuePosition: 0, pendingChanges: 0, audioSeconds: 5400, eta: null, startError: "", lastError: "", runEnd: null,
                createdAt: stamp() - 86400, updatedAt: stamp() - 3600, path: "D:\\Sách\\" + id, castLocked: false, precast: null,
                chapters: {total: 3, completed: 3, redo: 0, missingAudio: 0, failed: 0, working: 0},
                segments: {total: 120, analyzed: 120, recorded: 120, finished: 120, failed: 0, warnings: 0},
                progress: {overall: 1, analysis: 1, synthesis: 1},
                settings: {narrator: "Mai", profile: "balanced", profileLabel: "Cân bằng"}
            }, over || {})
        }
        function chapter(id, over) {
            return Object.assign({
                id: id, index: id, title: "Chương " + id, displayTitle: "Chương " + id, subtitle: "", fullTitle: "Chương " + id, status: "completed", statusLabel: "Đã thu",
                segments: {total: 10, analyzed: 10, recorded: 10, finished: 10, failed: 0, warnings: 0}, seconds: 300, playable: true, redo: false,
                startedAt: stamp() - 7200, completedAt: stamp() - 3600, lastError: ""
            }, over || {})
        }
        function analysing(over) {
            return book("an", Object.assign({phase: "analysis", statusLabel: "Đang phân tích", running: true, canPause: true,
                                              progress: {overall: 0.3, analysis: 0.42, synthesis: 0},
                                              chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}}, over || {}))
        }
        function library(books) { return {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: books}} }
        function detail(b, chapters) { return {status: 200, data: {book: b, chapters: chapters || []}} }

        function init() {
            DesktopApi.reset()
            Platform.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "0.4.150", studio: {installed: true}, dialogs: true}
            Api.loaded = true
            Api.saving = false
            Api.notice = ""
            Nav.layers = []
            Nav.studioPeer = ""
            Nav.uiVisible = true
            Theme.reduceMotion = false
        }
        function cleanup() {
            Theme.mode = "auto"; Theme.reduceMotion = false
            Nav.layers = []; Nav.studioPeer = ""; Api.notice = ""
            DesktopApi.delayed = false
        }
        function openBook(b, chapters, width) {
            reply("GET /api/library", library([b]))
            reply("GET /api/books/" + b.id, detail(b, chapters))
            const page = createTemporaryObject(studioFactory, host, {width: width || 1280, height: 900})
            verify(page !== null)
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject(b.id)
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            return page
        }
        function setBook(page, b) { reply("GET /api/books/" + b.id, detail(b, page.studioStore.chapters)); page.studioStore.loadBook() }
        function stepMark(page, index) { return one(page, "projectStepMark_" + index) }

        // ---- "Các bước" (ProductionPanel) ----
        function test_stepsFollowThePhaseAndRememberTheFold() {
            const page = openBook(analysing({settings: {narrator: "Mai", profile: "balanced", analyzer: ""}}), [chapter(1, {status: "pending", segments: {total: 10, analyzed: 4, recorded: 0, finished: 0, failed: 0, warnings: 0}, completedAt: 0, playable: false})])
            const steps = one(page, "projectSteps")
            verify(shown(steps))
            compare(steps.title, "Các bước")
            compare(steps.summary, "Phân tích truyện")
            // mặc định gập; mở thì nhớ theo cuốn
            verify(!steps.expanded)
            steps.children[0].clicked()
            tryCompare(steps, "expanded", true)
            compare(Platform.setting("fold.project.an.steps", ""), "1")
            tryVerify(function() { return shown(stepMark(page, 0)) })
            compare(stepMark(page, 0).name, "audio-lines")
            verify(hasText(page, "Phân tích truyện"))
            verify(hasText(page, "Phân vai"))
            verify(hasText(page, "Thu âm và kiểm tra"))
            verify(hasText(page, "Đọc cả truyện để nhận ra lời thoại, ai đang nói và cảm xúc từng câu."))
            verify(hasText(page, "Trao cho mỗi nhân vật một giọng riêng và khoá cách đọc tên."))
            verify(hasText(page, "42%"))
            // ba bước đứng cạnh nhau khi rộng
            const a = one(page, "projectStep_0"), b = one(page, "projectStep_1")
            compare(a.mapToItem(page, 0, 0).y, b.mapToItem(page, 0, 0).y)
            verify(b.mapToItem(page, 0, 0).x > a.mapToItem(page, 0, 0).x + a.width)
            both("steps_running", page)
            // tạm dừng: dấu dừng thay sóng; đổi sang thu âm: bước 1 xong, bước 3 đang làm
            setBook(page, analysing({paused: "user"}))
            tryCompare(stepMark(page, 0), "name", "pause")
            setBook(page, analysing({phase: "synthesis", statusLabel: "Đang thu âm", progress: {overall: 0.6, analysis: 1, synthesis: 0.25}}))
            tryCompare(steps, "summary", "Thu âm và kiểm tra")
            tryVerify(function() { return shown(stepMark(page, 2)) && stepMark(page, 2).name === "audio-lines" })
            verify(!shown(stepMark(page, 0)))
            // xác định người nói: dòng của bước 1 nói số chương
            setBook(page, analysing({speakerPass: {active: true, done: 2, total: 5}}))
            tryVerify(function() { return hasText(page, "Xác định người nói từng câu: 2/5 chương.") })
            // sách xong: khối khép lại
            setBook(page, book("an"))
            tryVerify(function() { return !shown(steps) })
        }
        function test_stepsStackOnANarrowPage() {
            Platform.setSetting("fold.project.an.steps", "1")
            const page = openBook(analysing(), [], 560)
            const a = one(page, "projectStep_0"), b = one(page, "projectStep_1")
            tryVerify(function() { return shown(a) })
            verify(b.mapToItem(page, 0, 0).y > a.mapToItem(page, 0, 0).y + a.height - 1)
            compare(a.width, b.width)
            both("steps_560", page)
        }
        function test_logLostWarningOnlyWhileRunning() {
            const page = openBook(analysing({logLost: {lines: 12}}), [])
            tryVerify(function() { return shown(one(page, "projectLogLost")) })
            verify(hasPart(page, "nhật ký làm sách không ghi được (12 dòng đã bỏ)"))
            setBook(page, analysing({running: false, logLost: {lines: 12}}))
            tryVerify(function() { return !shown(one(page, "projectLogLost")) })
        }
        function test_sideSourceErrorShowsOnce() {
            reply("GET /api/books/se/edits-inbox", {status: 503, data: {error: "Máy bận"}})
            const page = openBook(book("se"), [])
            const strip = one(page, "projectSideError")
            tryVerify(function() { return shown(strip) })
            verify(hasText(page, "Chưa tải được Máy bận; tự thử lại, hoặc làm mới trang."))
            both("side_error", page)
        }
        function test_sideSourceGoneIsNotAnError() {
            reply("GET /api/books/se/edits-inbox", {status: 404, data: {error: "Không thấy sách"}})
            const page = openBook(book("se"), [])
            tryVerify(function() { return calls("GET", "/api/books/se/edits-inbox").length > 0 })
            verify(!shown(one(page, "projectSideError")))
            // nhật ký trả 200 mà không phải danh sách: không phải lỗi tải
            page.openProjectTab("activity")
            tryVerify(function() { return calls("GET", "/api/books/se/activity").length > 0 })
            waitForRendering(page)
            verify(!shown(one(page, "projectSideError")))
            // nhật ký hỏng thật thì dải hiện
            reply("GET /api/books/se/activity", {status: 500, data: {error: "Hết chỗ"}})
            page.openProjectTab("chapters")
            tryCompare(one(page, "projectScreen"), "shownTab", "chapters")
            page.openProjectTab("activity")
            tryVerify(function() { return shown(one(page, "projectSideError")) })
            verify(hasText(page, "Chưa tải được Hết chỗ; tự thử lại, hoặc làm mới trang."))
        }

        // ---- tiến độ cả sách ----
        function test_headerProgressSaysWhyItStands() {
            const page = openBook(analysing(), [])
            compare(one(page, "projectBar").Accessible.name, "Tiến độ cả sách")
            compare(one(page, "projectBar").size, "xs")
            tryCompare(one(page, "projectProgressNote"), "text", "đang ước tính thời gian…")
            setBook(page, analysing({eta: {phase: "analysis", seconds: 3600}}))
            tryCompare(one(page, "projectProgressNote"), "text", "pha phân tích còn khoảng 1 giờ")
            setBook(page, analysing({stopping: true}))
            tryCompare(one(page, "projectProgressNote"), "text", "đang dừng")
            setBook(page, analysing({paused: "precast", precast: {ready: true, held: true, wait: true, announcedAt: 100}}))
            tryCompare(one(page, "projectProgressNote"), "text", "chờ bạn duyệt rồi bấm Thu âm")
            // tạm dừng thường đã nói ở trạng thái đầu trang
            setBook(page, analysing({paused: "user"}))
            tryVerify(function() { return !shown(one(page, "projectProgressNote")) })
        }

        // ---- lỗi khởi động, pin, menu dự án ----
        function test_startErrorOffersRetry() {
            const b = book("se", {phase: "synthesis", statusLabel: "Đã dừng", startError: "Chưa cài Ollama.", progress: {overall: 0.5, analysis: 1, synthesis: 0.2},
                                  chapters: {total: 3, completed: 1, redo: 0, missingAudio: 0, failed: 0, working: 0}})
            const page = openBook(b, [])
            tryVerify(function() { return shown(one(page, "projectStartError")) })
            verify(hasText(page, "Không khởi động được: Chưa cài Ollama."))
            reply("POST /api/books/se/start", {status: 200, data: b})
            const retry = one(page, "projectStartRetry")
            compare(retry.text, "Thử lại")
            compare(retry.icon, "rotate-ccw")
            mouseClick(retry)
            tryVerify(function() { return calls("POST", "/api/books/se/start").length === 1 })
            // đang chạy thì không có nút
            setBook(page, Object.assign({}, b, {running: true}))
            tryVerify(function() { return !shown(one(page, "projectStartRetry")) })
        }
        function test_batteryReasonFoldsUnderUsePower() {
            const page = openBook(analysing({paused: "battery"}), [])
            const battery = one(page, "projectBattery")
            tryVerify(function() { return shown(battery) })
            compare(battery.label, "Dùng pin")
            verify(hasText(page, "Studio tạm dừng; cắm sạc để tiếp tục."))
            verify(!hasPart(page, "Làm sách trên pin chậm"))
            battery.open = true
            tryVerify(function() { return hasText(page, "Làm sách trên pin chậm và hao pin. Bấm “Tiếp tục” để làm ngay trên pin, hoặc đổi ở Cài đặt › Studio.") })
        }
        function test_projectMenuNamesTheBook() {
            const page = openBook(book("menu", {title: "Kiếm Lai"}), [chapter(1)])
            compare(one(page, "bookMore").Accessible.name, "Tuỳ chọn dự án Kiếm Lai")
            compare(one(page, "bookMore").tip, "Tuỳ chọn dự án")
        }

        // ---- bảng chương ----
        function test_chapterTableHasColumnHeads() {
            const working = chapter(2, {status: "synthesizing", statusLabel: "Đang thu", segments: {total: 10, analyzed: 10, recorded: 5, finished: 5, failed: 0, warnings: 0}, completedAt: 0})
            const page = openBook(analysing({phase: "synthesis", progress: {overall: 0.6, analysis: 1, synthesis: 0.3}}), [chapter(1), working])
            const head = one(page, "chapterHead")
            tryVerify(function() { return shown(head) })
            for (const word of ["#", "Chương", "Trạng thái", "Độ dài", "Xong lúc"]) verify(hasText(head, word), word)
            // cột thẳng hàng với hàng chương
            const status = all(page, "chapterStatus").filter(shown)[0]
            const statusHead = head.children.filter(c => c.text === "Trạng thái")[0]
            compare(Math.round(statusHead.mapToItem(page, 0, 0).x), Math.round(status.mapToItem(page, 0, 0).x))
            // vạch đang thu nói đang thu hay đứng giữa chương
            compare(status.Accessible.description, "Đang thu âm")
            shot("chapter_head", page)
        }
        function test_chapterHeadNarrowKeepsNumberAndTitle() {
            const page = openBook(book("n"), [chapter(1)], 700)
            const head = one(page, "chapterHead")
            tryVerify(function() { return shown(head) })
            verify(hasText(head, "Chương"))
            verify(!hasText(head, "Độ dài"))
        }

        // ---- hộp thu lại cả chương ----
        function test_retakeDialogOffersScriptAndWhy() {
            const page = openBook(book("rt"), [chapter(1, {displayTitle: "Mở đầu"})])
            all(page, "chapterMore")[0].clicked()
            tryVerify(function() { return all(page, "menu_retake").filter(shown).length > 0 }, 2000)
            one(page, "menu_retake").clicked()
            tryVerify(function() { return all(page, "retakeConfirm").filter(shown).length > 0 })
            const more = one(page, "retakeMore")
            compare(more.label, "Thu lại chương")
            more.open = true
            tryVerify(function() { return hasText(page, "Dùng hạt giống mới cho cả chương. Sai người nói hoặc chữ thì sửa Kịch bản trước; thu lại cùng chữ không chữa được.") })
            both("retake", page)
            const edit = one(page, "retakeEdit")
            compare(edit.text, "Sửa chữ")
            mouseClick(edit)
            tryCompare(page, "shownTab", "script")
            tryVerify(function() { return all(page, "retakeConfirm").filter(shown).length === 0 })
            compare(calls("POST", "/api/books/rt/chapters/1/retake").length, 0)
        }

        // ---- lời mời "Duyệt" khi phân tích xong (usePrecastInvites) ----
        function test_precastInviteOncePerMilestone() {
            const held = book("pc", {title: "Đấu La", phase: "casting", statusLabel: "Chờ duyệt", running: true, paused: "precast",
                                    precast: {ready: true, held: true, wait: true, announcedAt: 100},
                                    chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}, progress: {overall: 0.4, analysis: 1, synthesis: 0}})
            reply("GET /api/library", library([held]))
            const progress = createTemporaryObject(progressFactory, host)
            tryCompare(Api, "notice", "“Đấu La” đang chờ bạn duyệt")
            verify(Api.noticeAction !== null)
            compare(Api.noticeAction.label, "Duyệt")
            compare(Api.noticeDuration, 30000)
            compare(Platform.setting("precast.invited.pc", ""), "100")
            spy.target = progress; spy.signalName = "precastRequested"; spy.clear()
            Api.runNoticeAction()
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0], "pc")
            // cùng mốc: không mời lại
            Api.notice = ""
            progress.store.libraryData = {books: [Object.assign({}, held)]}
            compare(Api.notice, "")
            // mốc mới mà đang ở chính trang dự án ấy: ghi nhớ, không mời
            progress.openProject = "pc"
            progress.store.libraryData = {books: [Object.assign({}, held, {precast: {ready: true, held: true, wait: true, announcedAt: 200}})]}
            compare(Api.notice, "")
            compare(Platform.setting("precast.invited.pc", ""), "200")
            // đã thu chương mà không giữ chờ: hết đúng lúc
            progress.openProject = ""
            progress.store.libraryData = {books: [book("late", {phase: "synthesis", precast: {ready: true, held: false, announcedAt: 300},
                                                                 chapters: {total: 3, completed: 1, redo: 0, missingAudio: 0, failed: 0, working: 0}})]}
            compare(Api.notice, "")
            progress.store.libraryData = {books: [book("fresh", {title: "Mới", phase: "casting", precast: {ready: true, held: false, announcedAt: 300},
                                                                  chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}})]}
            compare(Api.notice, "“Mới” đã phân tích xong")
        }
        function test_inviteOpensThePrecastTab() {
            const held = book("pt", {phase: "casting", statusLabel: "Chờ duyệt", running: true, paused: "precast",
                                    precast: {ready: true, held: true, wait: true, announcedAt: 100},
                                    chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}, progress: {overall: 0.4, analysis: 1, synthesis: 0}})
            reply("GET /api/library", library([held]))
            reply("GET /api/books/pt", detail(held, [chapter(1, {status: "pending", completedAt: 0, playable: false})]))
            reply("GET /api/books/pt/precast", {status: 200, data: {upcoming: []}})
            const page = createTemporaryObject(studioFactory, host, {width: 1280, height: 900})
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            // từ danh sách: mở dự án rồi chọn tab khi trang dựng xong
            page.openProject("pt")
            page.openProjectTab("precast")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "shownTab", "precast")
            // trang đã dựng: chọn ngay
            page.openProjectTab("chapters")
            tryCompare(page, "shownTab", "chapters")
        }

        // ---- ô chọn có đầu nhóm, tên trợ năng ----
        function test_selectGroupHeaderIsNotPickable() {
            const select = createTemporaryObject(selectFactory, host, {x: 20, y: 20})
            spy.target = select; spy.signalName = "picked"; spy.clear()
            select.forceActiveFocus()
            keyClick(Qt.Key_Down)
            const popup = select.data.filter(o => o && o.contentItem !== undefined && o.closePolicy !== undefined)[0]
            verify(popup !== undefined)
            const rows = popup.contentItem
            tryVerify(function() { return rows.visible && rows.count === 4 })
            compare(rows.currentIndex, 0)
            keyClick(Qt.Key_Down)
            compare(rows.currentIndex, 2)        // nhảy qua đầu nhóm
            keyClick(Qt.Key_Up)
            compare(rows.currentIndex, 0)
            const header = rows.itemAtIndex(1)
            verify(!header.enabled)
            compare(header.Accessible.name, "Bản khác (thử nghiệm)")
            rows.pick(1)
            compare(spy.count, 0)
            rows.pick(3)
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0], "b")
        }
        function test_newVoiceSampleNamesTheVoiceWhenStopping() {
            const sample = createTemporaryObject(sampleFactory, host)
            compare(sample.Accessible.name, "Nghe thử giọng Mai")
            compare(sample.stopLabel, "Dừng nghe Mai")
        }
    }
}
