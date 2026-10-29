import QtQuick
import QtTest
import ABook

// Studio S1: danh sách dự án (bảng gọn, các trạng thái rỗng / chờ / lỗi), trang một dự án (MỘT nút chính theo trạng thái, "Tạm dừng" gọi lệnh tạm dừng
// chứ không dừng, tab + "Thêm", danh sách chương, Nhật ký) và Studio của máy tính đã ghép (mọi lời gọi qua /api/peers/<mã>/studio/...).
// HTTP là DesktopApi giả; ảnh sáng / tối ghi ra build/d2shots/s1_*.png để tự nhìn.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: studioFactory; StudioScreen {} }

    TestCase {
        id: test
        name: "Studio1"
        when: windowShown

        readonly property string peerId: "c0ffee000001"
        readonly property string peerBase: "/api/peers/c0ffee000001/studio"

        function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function callsLike(method, pattern) { return DesktopApi.requests.filter(r => r.method === method && pattern.test(r.path)) }
        function all(item, name, out) {
            out = out || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children || []) all(child, name, out)
            return out
        }
        function one(item, name) { const found = all(item, name); verify(found.length > 0, "thiếu " + name); return found.filter(shown)[0] || found[0] }
        function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
        function texts(item, out) {
            out = out || []
            if (item.text !== undefined && shown(item)) out.push(String(item.text))
            for (const child of item.children || []) texts(child, out)
            return out
        }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function hasPart(item, part) { return texts(item).some(t => t.indexOf(part) >= 0) }
        function shot(name, item) {
            const target = item || host
            waitForRendering(target)
            wait(300)
            const path = Qt.resolvedUrl("../../build/d2shots/s1_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(target).save(path)
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
        function library(books, extra) { return {status: 200, data: Object.assign({root: "D:\\Sách", rootMissing: false, books: books}, extra || {})} }
        function detail(b, chapters) { return {status: 200, data: {book: b, chapters: chapters || []}} }
        function bookStates() {
            return {
                idle: book("idle", {phase: "idle", statusLabel: "Chưa bắt đầu", chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0},
                                    progress: {overall: 0, analysis: 0, synthesis: 0}}),
                running: book("running", {phase: "analysis", statusLabel: "Đang phân tích", running: true, canPause: true, progress: {overall: 0.3, analysis: 0.3, synthesis: 0},
                                          chapters: {total: 3, completed: 1, redo: 0, missingAudio: 0, failed: 0, working: 0}}),
                paused: book("paused", {phase: "analysis", statusLabel: "Đang phân tích", running: true, canPause: true, paused: "user", progress: {overall: 0.3, analysis: 0.3, synthesis: 0},
                                        chapters: {total: 3, completed: 1, redo: 0, missingAudio: 0, failed: 0, working: 0}}),
                stopped: book("stopped", {phase: "synthesis", statusLabel: "Đã dừng", chapters: {total: 3, completed: 1, redo: 0, missingAudio: 0, failed: 0, working: 0},
                                          progress: {overall: 0.5, analysis: 1, synthesis: 0.2}}),
                done: book("done", {}),
                apply: book("apply", {pendingChanges: 3})
            }
        }

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
            Theme.reduceMotion = true
        }
        function cleanup() {
            Theme.mode = "auto"; Theme.reduceMotion = false
            Nav.layers = []; Nav.studioPeer = ""; Api.notice = ""
            DesktopApi.delayed = false
        }
        function makeStudio(width, height) {
            const page = createTemporaryObject(studioFactory, host, {width: width || 1280, height: height || 900})
            verify(page !== null)
            return page
        }
        function listed(page, count) { tryVerify(function() { return all(page, "projectName").filter(shown).length >= count }, 3000) }
        function openBook(b, chapters, width) {
            reply("GET /api/library", library([b]))
            reply("GET /api/books/" + b.id, detail(b, chapters))
            const page = makeStudio(width)
            listed(page, 1)
            page.openProject(b.id)
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            return page
        }
        function keys(page) {
            const model = page.projectsScreenModel
            const out = []
            for (let i = 0; i < model.count; ++i) out.push(model.get(i).key)
            return out
        }
        function pickMenu(page, key) {
            tryVerify(function() { return all(page, "menu_" + key).filter(shown).length > 0 }, 2000)
            one(page, "menu_" + key).clicked()
        }
        function confirmShown(page) { return all(page, "studioConfirm").filter(shown)[0] }

        // ================= 1. bảng dự án =================
        function test_tableRendersAndSorts() {
            const old = book("old", {title: "Cuốn cũ", updatedAt: stamp() - 86400 * 3})
            const live = book("live", {title: "Đang chạy", phase: "synthesis", statusLabel: "Đang thu âm", running: true, canPause: true, progress: {overall: 0.4, analysis: 1, synthesis: 0.4},
                                       chapters: {total: 10, completed: 4, redo: 0, missingAudio: 0, failed: 0, working: 1}})
            const needs = book("needs", {title: "Còn việc", pendingChanges: 2, chapters: {total: 3, completed: 3, redo: 0, missingAudio: 1, failed: 0, working: 0}})
            const volumeOne = book("v1", {title: "Lò rèn · Tập 1"})
            const volumeTwo = book("v2", {title: "Lò rèn · Tập 2"})
            reply("GET /api/library", library([old, needs, volumeOne, volumeTwo, live]))
            const page = makeStudio(1280)
            listed(page, 5)
            // đang chạy lên đầu, rồi theo thứ tự máy chủ; cuốn nhiều phần gom dưới một dòng tên
            compare(keys(page), ["book:live", "book:old", "book:needs", "series:Lò rèn", "book:v1", "book:v2"])
            compare(one(page, "groupHead").text, "Lò rèn · 2 tập")
            verify(hasText(page, "5 dự án"))
            verify(shown(one(page, "newProject")))
            compare(one(page, "newProject").text, "Dự án mới")
            for (const head of ["Dự án", "Trạng thái", "Tiến độ", "Cập nhật"]) verify(hasText(page, head), head)
            // sách xong là mặc định: không đeo nhãn; việc còn lại nói ngay trên dòng
            const details = all(page, "projectDetail").map(t => t.text)
            verify(details.some(t => t.indexOf("2 thay đổi chờ áp") >= 0 && t.indexOf("1 chương mất audio") >= 0), JSON.stringify(details))
            const pills = all(page, "projectStatus").filter(shown)
            compare(pills.length, 1)
            compare(pills[0].label, "Đang thu âm")
            both("projects_wide", page)
            // hẹp hơn: bỏ cột "Cập nhật"; hẹp nữa: trạng thái và tiến độ xếp dưới tên
            page.width = 1024
            tryCompare(page, "projectsKind", "mid")
            verify(!hasText(page, "Cập nhật"))
            compare(page.projectsKind, "mid")
            page.width = 720
            tryCompare(page, "projectsKind", "stacked")
            compare(page.projectsKind, "stacked")
            verify(!hasText(page, "Trạng thái"))
        }
        function test_pollingUpdatesRowsInPlace() {
            reply("GET /api/library", library([book("a", {title: "Cuốn a", updatedAt: stamp() - 100}), book("b", {title: "Cuốn b"})]))
            const page = makeStudio()
            listed(page, 2)
            const list = page.projectsList
            const first = list.itemAtIndex(0)
            verify(first !== null)
            reply("GET /api/library", library([book("a", {title: "Cuốn a", updatedAt: stamp()}), book("b", {title: "Cuốn b"})]))
            page.studioStore.loadLibrary()
            wait(50)   // fixed: proves absence
            verify(list.itemAtIndex(0) === first, "hàng giữ nguyên khi dữ liệu đổi")
            reply("GET /api/library", library([book("a", {title: "Cuốn a"}), book("b", {title: "Cuốn b"}), book("c", {title: "Cuốn c"})]))
            page.studioStore.loadLibrary()
            tryVerify(function() { return all(page, "projectName").filter(shown).length === 3 })
        }
        function test_loadingEmptyErrorAndMissingStates() {
            DesktopApi.delayed = true
            reply("GET /api/library", library([]))
            const page = makeStudio()
            verify(shown(one(page, "projectsSkeleton")))
            verify(!shown(one(page, "projectsEmpty")))
            DesktopApi.finish()
            tryVerify(function() { return shown(one(page, "projectsEmpty")) })
            compare(one(one(page, "projectsEmpty"), "emptyTitle").text, "Chưa có dự án")
            compare(one(page, "newProjectEmpty").text, "Dự án mới")
            verify(!shown(one(page, "newProject")))
            verify(!shown(one(page, "projectsSkeleton")))
            both("projects_empty", page)
            // lỗi mạng: lời nói thẳng + Thử lại
            DesktopApi.delayed = false
            reply("GET /api/library", {status: 500, data: {error: "hỏng"}})
            page.studioStore.libraryData = null
            page.studioStore.loadLibrary()
            tryVerify(function() { return shown(one(page, "projectsError")) })
            verify(hasText(page, "Chưa tải được danh sách dự án; bạn hãy kiểm tra kết nối rồi thử lại."))
            reply("GET /api/library", library([book("a", {title: "Đã về"})]))
            page.studioStore.loadLibrary()
            tryVerify(function() { return hasText(page, "Đã về") })
            // thiếu thư mục thư viện
            reply("GET /api/library", library([], {rootMissing: true, root: "E:\\Sách của tôi"}))
            page.studioStore.loadLibrary()
            tryVerify(function() { return shown(one(page, "projectsMissing")) })
            compare(one(one(page, "projectsMissing"), "emptyTitle").text, "Không thấy thư mục thư viện “Sách của tôi”")
            verify(hasText(page, "Chọn thư mục"))
        }
        function test_newProjectButtonOpensTheBuilder() {
            reply("GET /api/library", library([book("a")]))
            const page = makeStudio()
            listed(page, 1)
            one(page, "newProject").clicked()
            tryCompare(page, "shownKey", "route:new")
            tryCompare(page, "phase", 1)
            verify(shown(one(page, "newProjectScreen")))
            verify(hasText(page, "Tạo sách nói"))
            verify(Nav.layers.length > 0, "màn con là một lớp của Back")
            verify(Nav.back())
            tryCompare(page, "shownKey", "route:list")
            compare(Nav.layers.length, 0)
        }
        function test_brokenRowsSayWhyAndOnlyBusyRetries() {
            const broken = book("bad", {title: "Sổ hỏng", broken: "thiếu tệp", brokenKind: "corrupt", backup: true})
            const busy = book("busy", {title: "Bị giữ", broken: "tệp đang mở", brokenKind: "busy"})
            reply("GET /api/library", library([broken, busy]))
            const page = makeStudio()
            tryVerify(function() { return all(page, "brokenLine").filter(shown).length === 2 })
            const lines = all(page, "brokenLine").map(t => t.text)
            verify(lines.indexOf("Không đọc được: thiếu tệp") >= 0, JSON.stringify(lines))
            verify(lines.indexOf("Chưa mở được: tệp đang mở") >= 0, JSON.stringify(lines))
            compare(all(page, "brokenRetry").filter(shown).length, 1)
            const before = calls("GET", "/api/library").length
            one(page, "brokenRetry").clicked()
            tryVerify(function() { return calls("GET", "/api/library").length > before })
            // khôi phục bản sao: mở "…" của dự án hỏng
            all(page, "projectMore").filter(shown)[0].clicked()
            pickMenu(page, "restore")
            tryVerify(function() { return confirmShown(page) !== undefined })
            verify(hasPart(page, "Khôi phục “Sổ hỏng” từ bản sao cũ?"))
            confirmShown(page).chosen("go")
            tryVerify(function() { return calls("POST", "/api/books/bad/restore-backup").length === 1 })
        }
        function test_rowMenuRenameAndDelete() {
            reply("GET /api/library", library([book("a", {title: "Cuốn a"})]))
            reply("PUT /api/books/a/title", {status: 200, data: {id: "a", title: "Tên mới"}})
            reply("DELETE /api/books/a", {status: 200, data: {ok: true, undo: "tok1"}})
            const page = makeStudio()
            listed(page, 1)
            one(page, "projectMore").clicked()
            pickMenu(page, "rename")
            const field = one(page, "studioRenameField")
            tryVerify(function() { return shown(field) })
            compare(field.text, "Cuốn a")
            verify(!one(page, "studioRenameSave").enabled, "tên chưa đổi thì chưa lưu được")
            field.text = "Tên mới"
            verify(one(page, "studioRenameSave").enabled)
            one(page, "studioRenameSave").activated()
            tryVerify(function() { return calls("PUT", "/api/books/a/title").length === 1 })
            compare(calls("PUT", "/api/books/a/title")[0].body.title, "Tên mới")
            tryVerify(function() { return Api.notice.indexOf("Đã đổi tên thành") === 0 })
            // xoá: hỏi lại, rồi vào Thùng rác kèm "Hoàn tác"
            one(page, "projectMore").clicked()
            pickMenu(page, "delete")
            tryVerify(function() { return confirmShown(page) !== undefined })
            verify(hasPart(page, "Xoá dự án “Cuốn a”?"))
            confirmShown(page).chosen("go")
            tryVerify(function() { return calls("DELETE", "/api/books/a").length === 1 })
        }

        // ================= 2. trang một dự án: nút chính =================
        function test_primary_data() {
            const s = bookStates()
            return [
                {tag: "idle", book: s.idle, label: "Bắt đầu", icon: "wand-sparkles"},
                {tag: "running", book: s.running, label: "Tạm dừng", icon: "pause"},
                {tag: "paused", book: s.paused, label: "Tiếp tục", icon: "play"},
                {tag: "stopped", book: s.stopped, label: "Tiếp tục", icon: "play"},
                {tag: "done", book: s.done, label: "Nghe trong Thư viện", icon: "headphones"},
                {tag: "apply", book: s.apply, label: "Áp dụng 3 thay đổi", icon: "refresh-cw"}
            ]
        }
        function test_primary(d) {
            const page = openBook(d.book, [chapter(1)])
            const button = one(page, "primaryButton")
            verify(shown(button))
            compare(button.text, d.label)
            compare(button.icon, d.icon)
            compare(all(page, "primaryButton").filter(shown).length, 1, "chỉ MỘT nút chính")
            verify(shown(one(page, "bookMore")))
            if (d.tag === "running") both("project_running", page)
        }
        function test_startingAndStoppingShowOnlyAWaitingButton() {
            const page = openBook(book("wait", {phase: "analysis", running: true, starting: true}), [])
            compare(one(page, "primaryButton").text, "Đang khởi động")
            verify(one(page, "primaryButton").busy)
            reply("GET /api/books/wait", detail(book("wait", {phase: "analysis", running: true, canPause: true, stopping: true}), []))
            page.studioStore.loadBook()
            tryVerify(function() { return one(page, "primaryButton").text === "Đang dừng…" })
            verify(!one(page, "primaryButton").enabled || one(page, "primaryButton").busy)
        }
        function test_pauseCallsPauseNeverStop() {
            const running = bookStates().running
            reply("POST /api/books/running/pause", {status: 200, data: Object.assign({}, running, {paused: "user"})})
            const page = openBook(running, [chapter(1)])
            one(page, "primaryButton").clicked()
            tryVerify(function() { return calls("POST", "/api/books/running/pause").length === 1 })
            compare(calls("POST", "/api/books/running/pause")[0].body, {paused: true})
            compare(calls("POST", "/api/books/running/stop").length, 0, "Tạm dừng KHÔNG BAO GIỜ gọi dừng")
            tryVerify(function() { return one(page, "primaryButton").text === "Tiếp tục" })
            tryVerify(function() { return Api.notice.indexOf("Đang tạm dừng") === 0 })
            // làm tiếp cũng là lệnh tạm dừng (paused: false)
            reply("POST /api/books/running/pause", {status: 200, data: running})
            one(page, "primaryButton").clicked()
            tryVerify(function() { return calls("POST", "/api/books/running/pause").length === 2 })
            compare(calls("POST", "/api/books/running/pause")[1].body, {paused: false})
            compare(calls("POST", "/api/books/running/stop").length, 0)
        }
        function test_stopOnlyInMenuWithAnalysisWarning() {
            const running = bookStates().running
            reply("POST /api/books/running/stop", {status: 200, data: Object.assign({}, running, {stopping: true})})
            const page = openBook(running, [chapter(1)])
            one(page, "bookMore").clicked()
            pickMenu(page, "stop")
            tryVerify(function() { return confirmShown(page) !== undefined })
            const dialog = confirmShown(page)
            compare(dialog.title, "Dừng phân tích?")
            verify(hasPart(dialog, "Phần đã phân tích được giữ nguyên, nhưng làm tiếp từ chỗ dừng"), "phải có lời cảnh báo của bản web")
            verify(hasPart(dialog, "có thể ra một cuốn khác"))
            verify(hasPart(dialog, "Cần nghỉ thì bấm Tạm dừng"))
            verify(shown(one(dialog, "confirm_pause")), "ngay trong hộp có đường Tạm dừng")
            compare(calls("POST", "/api/books/running/stop").length, 0, "chưa bấm thì chưa dừng")
            both("project_stop_dialog", host)
            dialog.chosen("later")
            tryVerify(function() { return confirmShown(page) === undefined })
            compare(calls("POST", "/api/books/running/stop").length, 0)
            one(page, "bookMore").clicked()
            pickMenu(page, "stop")
            tryVerify(function() { return confirmShown(page) !== undefined })
            confirmShown(page).chosen("go")
            tryVerify(function() { return calls("POST", "/api/books/running/stop").length === 1 })
        }
        function test_resumeAfterInterruptedAnalysisAsksFirst() {
            const cut = book("cut", {phase: "analysis", statusLabel: "Đã dừng", analysisInterrupted: true, chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0},
                                     progress: {overall: 0.2, analysis: 0.2, synthesis: 0}, segments: {total: 100, analyzed: 40, recorded: 0, finished: 0, failed: 0, warnings: 0}})
            const page = openBook(cut, [])
            compare(one(page, "primaryButton").text, "Phân tích lại")
            verify(hasPart(page, "Phân tích đã dừng giữa chừng (còn 60/100 câu)"))
            one(page, "bookMore").clicked()
            pickMenu(page, "resumeAnyway")
            tryVerify(function() { return confirmShown(page) !== undefined })
            verify(hasPart(confirmShown(page), "Phân tích của “Cuốn cut” đã dừng giữa chừng."))
            compare(calls("POST", "/api/books/cut/start").length, 0)
            confirmShown(page).chosen("go")
            tryVerify(function() { return calls("POST", "/api/books/cut/start").length === 1 })
        }
        function test_applyChangesAsksThenStarts() {
            const page = openBook(bookStates().apply, [chapter(1)])
            compare(one(page, "primaryButton").text, "Áp dụng 3 thay đổi")
            one(page, "primaryButton").clicked()
            tryVerify(function() { return confirmShown(page) !== undefined })
            compare(confirmShown(page).title, "Áp dụng 3 thay đổi?")
            compare(calls("POST", "/api/books/apply/start").length, 0)
            confirmShown(page).chosen("go")
            tryVerify(function() { return calls("POST", "/api/books/apply/start").length === 1 })
        }
        function test_startRefusedWhenStudioMissing() {
            Api.info = {version: "0.4.150", studio: {installed: false}, dialogs: true}
            const page = openBook(bookStates().idle, [])
            one(page, "primaryButton").clicked()
            wait(100)   // fixed: proves absence
            compare(calls("POST", "/api/books/idle/start").length, 0, "không gửi lệnh rồi nhận lỗi")
            verify(shown(one(page, "primaryButton")))
        }
        function test_startSendsStart() {
            const page = openBook(bookStates().idle, [])
            reply("POST /api/books/idle/start", {status: 200, data: {}})
            one(page, "primaryButton").clicked()
            tryVerify(function() { return calls("POST", "/api/books/idle/start").length === 1 })
            tryVerify(function() { return Api.notice === "Đang khởi động" })
        }
        function test_moreMenuListsTheRest() {
            const page = openBook(bookStates().done, [chapter(1)])
            one(page, "bookMore").clicked()
            tryVerify(function() { return all(page, "menu_rename").filter(shown).length > 0 })
            for (const key of ["export", "reveal", "details", "rename", "continueBook", "delete"]) verify(all(page, "menu_" + key).filter(shown).length > 0, key)
            verify(all(page, "menu_stop").filter(shown).length === 0, "sách không chạy thì không có Dừng")
            pickMenu(page, "details")
            tryVerify(function() { return confirmShown(page) !== undefined })
            compare(confirmShown(page).title, "Chi tiết dự án")
            verify(hasPart(confirmShown(page), "Giọng kể Mai"))
        }

        // ================= 3. tab =================
        function test_tabsAndMoreOverflow() {
            const page = openBook(bookStates().done, [chapter(1)])
            for (const key of ["chapters", "work", "review", "cast", "music"]) verify(shown(one(page, "tab_" + key)), key)
            compare(one(page, "tab_chapters").Accessible.name, "Chương")
            compare(one(page, "tab_work").Accessible.name, "Việc cần duyệt")
            compare(one(page, "tab_review").Accessible.name, "Cần nghe lại")
            compare(one(page, "tab_cast").Accessible.name, "Nhân vật")
            compare(one(page, "tab_music").Accessible.name, "Nhạc nền")
            compare(one(page, "tab_moreLabel").text, "Thêm")
            // tab chưa làm: một câu trung tính
            one(page, "tab_music").clicked()
            tryCompare(page, "shownTab", "music")
            tryCompare(page, "phase", 1)
            verify(hasText(page, "Mục này chưa mở trong bản này."))
            compare(one(page, "tab_moreLabel").text, "Thêm")
            // "Thêm" mang tên tab đang chọn trong nó
            one(page, "tab_more").clicked()
            for (const key of ["script", "activity"]) tryVerify(function() { return all(page, "menu_" + key).filter(shown).length > 0 })
            verify(all(page, "menu_precast").filter(shown).length === 0, "Duyệt trước khi thu chỉ có khi đang chờ duyệt")
            pickMenu(page, "script")
            tryCompare(page, "shownTab", "script")
            compare(one(page, "tab_moreLabel").text, "Kịch bản")
            one(page, "tab_more").clicked()
            pickMenu(page, "activity")
            tryCompare(page, "shownTab", "activity")
            compare(one(page, "tab_moreLabel").text, "Nhật ký")
            one(page, "tab_chapters").clicked()
            tryCompare(page, "shownTab", "chapters")
            compare(one(page, "tab_moreLabel").text, "Thêm")
        }
        function test_precastTabInsideMore() {
            const held = book("held", {phase: "casting", statusLabel: "Chờ bạn duyệt", precast: {ready: true, held: true}, chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}})
            const page = openBook(held, [])
            compare(one(page, "primaryButton").text, "Thu âm")
            one(page, "tab_more").clicked()
            tryVerify(function() { return all(page, "menu_precast").filter(shown).length > 0 })
            pickMenu(page, "precast")
            tryCompare(page, "shownTab", "precast")
            compare(one(page, "tab_moreLabel").text, "Duyệt trước khi thu")
        }
        function test_tabsFitNarrowWindow() {
            const page = openBook(bookStates().done, [chapter(1)], 560)
            const tabs = one(page, "projectTabs")
            verify(tabs.width <= 560)
            const more = one(page, "tab_more")
            verify(more !== null)
            // không đủ chỗ thì cuộn ngang, không cắt chữ
            for (const key of ["chapters", "work", "review", "cast", "music"]) verify(one(page, "tab_" + key).width > 20, key)
        }

        // ================= 4. danh sách chương =================
        function chapterSet() {
            return [
                chapter(1, {title: "Mở đầu", displayTitle: "Mở đầu", subtitle: "Lên đường"}),
                chapter(2, {status: "synthesizing", statusLabel: "Đang thu âm", segments: {total: 10, analyzed: 10, recorded: 5, finished: 5, failed: 0, warnings: 0}, playable: false, completedAt: null}),
                chapter(3, {status: "failed", statusLabel: "Lỗi", lastError: "CUDA out of memory", playable: false, completedAt: null}),
                chapter(4, {statusLabel: "Mất file audio", playable: false}),
                chapter(5, {status: "pending", statusLabel: "Chờ", segments: {total: 0, analyzed: 0, recorded: 0, finished: 0, failed: 0, warnings: 0}, playable: false, seconds: 0, completedAt: null})
            ]
        }
        function test_chapterList() {
            const b = book("c1", {phase: "synthesis", statusLabel: "Đang thu âm", running: true, canPause: true, chapters: {total: 5, completed: 2, redo: 0, missingAudio: 1, failed: 1, working: 1}})
            const page = openBook(b, chapterSet())
            tryVerify(function() { return all(page, "chapterTitle").filter(shown).length === 5 })
            const titles = all(page, "chapterTitle").map(t => t.text)
            compare(titles, ["Mở đầu", "Chương 2", "Chương 3", "Chương 4", "Chương 5"])
            compare(all(page, "chapterSubtitle").filter(shown).map(t => t.text)[0], "Lên đường")
            // đang thu: vạch + 5/10; chương lỗi nói bằng lời cho người nghe
            compare(all(page, "chapterBar").filter(shown).length, 1)
            verify(hasText(page, "5/10"))
            verify(hasText(page, "Card đồ hoạ hết bộ nhớ."))
            verify(hasText(page, "Lỗi"))
            verify(hasText(page, "Mất file audio"))
            // chương xong có độ dài; chưa thu thì số câu
            verify(hasText(page, "5 phút"))
            verify(hasText(page, "10 câu"))
            compare(all(page, "chapterNumber").filter(shown).map(t => t.text).slice(0, 2), ["1", "2"])
            // hàng không đổi chỗ khi dữ liệu đổi (nhịp hỏi 3 giây)
            const first = page.projectScreenList.itemAtIndex(0)
            page.studioStore.loadBook()
            wait(50)   // fixed: proves absence
            verify(page.projectScreenList.itemAtIndex(0) === first)
            both("project_chapters", page)
            // "…" của chương: nghe, kịch bản, thu lại cả chương (có hộp hỏi)
            reply("POST /api/books/c1/chapters/1/retake", {status: 200, data: {lines: 10}})
            all(page, "chapterMore")[0].clicked()
            pickMenu(page, "retake")
            tryVerify(function() { return all(page, "retakeConfirm").filter(shown).length > 0 })
            compare(one(page, "retakeConfirm").title, "Thu lại cả Mở đầu?")
            one(page, "retakeConfirm").chosen("go")
            tryVerify(function() { return calls("POST", "/api/books/c1/chapters/1/retake").length === 1 })
        }
        function test_chapterListEmptyAndFailureStates() {
            const page = openBook(bookStates().idle, [])
            tryVerify(function() { return shown(one(page, "tabEmpty")) })
            compare(one(one(page, "tabEmpty"), "emptyTitle").text, "Chưa có chương nào")
            // sách đã bị xoá: thôi hỏi, nói thẳng, có đường về
            reply("GET /api/books/idle", {status: 404, data: {error: "không có"}})
            page.studioStore.loadBook()
            tryVerify(function() { return shown(one(page, "projectGone")) })
            compare(one(one(page, "projectGone"), "emptyTitle").text, "Dự án này không còn")
            one(page, "projectGoneBack").clicked()
            tryCompare(page, "shownKey", "route:list")
        }
        function test_staleStripKeepsOldBook() {
            const page = openBook(bookStates().done, [chapter(1)])
            reply("GET /api/books/done", {status: 0, data: null})
            page.studioStore.loadBook()
            tryVerify(function() { return shown(one(page, "projectStale")) })
            verify(hasText(page, "Mất kết nối tới ABook, đang thử lại…"))
            verify(shown(one(page, "primaryButton")), "vẫn giữ trang với bản cũ")
        }
        function test_bookPollingFollowsLiveness() {
            const running = bookStates().running
            const page = openBook(running, [chapter(1)])
            compare(page.studioStore.bookTimer.interval, 3000)
            verify(page.studioStore.bookTimer.running)
            reply("GET /api/books/running", detail(bookStates().done, [chapter(1)]))
            page.studioStore.loadBook()
            tryVerify(function() { return page.studioStore.bookTimer.interval === 15000 })
            // lỗi liên tiếp: lùi dần; 404: thôi hẳn
            reply("GET /api/books/running", {status: 500, data: {error: "x"}})
            page.studioStore.loadBook()
            tryVerify(function() { return page.studioStore.bookTimer.interval === 30000 })
            reply("GET /api/books/running", {status: 404, data: {error: "x"}})
            page.studioStore.loadBook()
            tryVerify(function() { return !page.studioStore.bookTimer.running })
        }
        function test_pollingStopsWhenWindowHidden() {
            const page = openBook(bookStates().running, [chapter(1)])
            verify(page.studioStore.bookTimer.running)
            page.visible = false
            tryVerify(function() { return !page.studioStore.bookTimer.running })
            verify(!page.studioStore.libraryTimer.running)
            const before = calls("GET", "/api/books/running").length
            page.visible = true
            tryVerify(function() { return page.studioStore.bookTimer.running })
            tryVerify(function() { return calls("GET", "/api/books/running").length > before }, 2000)
            page.goList()
            tryCompare(page, "shownKey", "route:list")
            tryVerify(function() { return page.studioStore.libraryTimer.running })
            page.visible = false
            tryVerify(function() { return !page.studioStore.libraryTimer.running })
        }

        // ================= 5. Nhật ký =================
        function test_activityTab() {
            const b = bookStates().running
            const today = stamp()
            reply("GET /api/books/running/activity", {status: 200, data: [
                {id: "2", at: today, level: "warning", text: "Máy chậm lại"},
                {id: "1", at: today - 60, level: "info", text: "Bắt đầu phân tích"},
                {id: "0", at: today - 86400 * 3, level: "success", text: "Tạo dự án"}]})
            reply("GET /api/books/running/activity?technical=1", {status: 200, data: [
                {id: "2", at: today, level: "warning", code: "pipeline.slow", text: "gpu 91%"}]})
            const page = openBook(b, [chapter(1)])
            one(page, "tab_more").clicked()
            pickMenu(page, "activity")
            tryCompare(page, "shownTab", "activity")
            tryVerify(function() { return all(page, "activityText").filter(shown).length === 3 })
            compare(all(page, "activityText").map(t => t.text), ["Máy chậm lại", "Bắt đầu phân tích", "Tạo dự án"])
            verify(hasText(page, "3 mục gần nhất"))
            compare(all(page, "activityDay").filter(shown).length, 2, "hai ngày -> hai đầu nhóm")
            both("project_activity", page)
            one(page, "activityTechnical").clicked()
            tryVerify(function() { return calls("GET", "/api/books/running/activity?technical=1").length === 1 })
            tryVerify(function() { return all(page, "activityTech").filter(shown).length === 1 })
            verify(hasPart(page, "pipeline.slow"))
            verify(hasText(page, "Ẩn chi tiết kỹ thuật"))
            // trống: lời mời
            reply("GET /api/books/idle/activity", {status: 200, data: []})
            const empty = openBook(bookStates().idle, [])
            one(empty, "tab_more").clicked()
            pickMenu(empty, "activity")
            tryCompare(empty, "shownTab", "activity")
            tryVerify(function() { return shown(one(empty, "tabEmpty")) })
            compare(one(one(empty, "tabEmpty"), "emptyTitle").text, "Chưa có gì")
        }

        // ================= 6. tên dài =================
        function test_longTitlesWrapAtBothWidths_data() { return [{tag: "w1024", w: 1024}, {tag: "w1920", w: 1920}] }
        function test_longTitlesWrapAtBothWidths(d) {
            const title = "Chuyện kể về người thợ rèn đã đi qua bảy mươi hai dặm đường núi để tìm lại thanh kiếm mà ông nội cậu đã giấu dưới gốc cây đa cổ thụ đầu làng"
            const b = book("long", {title: title})
            const page = openBook(b, [chapter(1, {title: title, displayTitle: title, subtitle: "Phụ đề cũng rất dài, " + title})], d.w)
            const own = all(page, "projectHeader")[0]
            const heads = []
            function find(item) { if (item.text === title && item.paintedWidth !== undefined) heads.push(item); for (const c of item.children || []) find(c) }
            find(page)
            verify(heads.length >= 1)
            for (const text of heads.filter(shown)) {
                verify(text.contentWidth <= text.width + 0.5, "chữ tràn ngang: " + text.contentWidth + " > " + text.width)
                verify(text.contentHeight >= text.font.pixelSize * 1.5, "tên dài phải xuống dòng")
            }
            const chap = one(page, "chapterTitle")
            verify(chap.contentWidth <= chap.width + 0.5)
            verify(chap.contentHeight >= chap.font.pixelSize * 1.5)
            verify(page.projectScreenList.contentWidth <= page.projectScreenList.width + 0.5, "không tràn ngang")
            // trang danh sách
            page.goList()
            tryCompare(page, "shownKey", "route:list")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectName").filter(shown).length === 1 })
            const name = one(page, "projectName")
            verify(name.contentWidth <= name.width + 0.5)
            verify(name.contentHeight >= name.font.pixelSize * 1.5)
            shot("long_" + d.tag, page)
        }

        // ================= 7. Studio của máy tính đã ghép =================
        function peerApp(over) { return {status: 200, data: Object.assign({version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn phòng làm việc"}}, over || {})} }
        function test_peerRoutesEveryRequestThroughTheBridge() {
            const running = bookStates().running
            reply("GET " + peerBase + "/api/app", peerApp())
            reply("GET " + peerBase + "/api/library", library([running, book("done", {title: "Đã xong"})]))
            reply("GET " + peerBase + "/api/books/running", detail(running, [chapter(1)]))
            reply("POST " + peerBase + "/api/books/running/pause", {status: 200, data: Object.assign({}, running, {paused: "user"})})
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryCompare(page, "view", "open")
            listed(page, 2)
            tryVerify(function() { return shown(one(page, "peerBar")) })
            compare(calls("GET", peerBase + "/api/library").length >= 1, true)
            page.openProject("running")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return shown(one(page, "primaryButton")) })
            compare(one(page, "primaryButton").text, "Tạm dừng")
            one(page, "primaryButton").clicked()
            tryVerify(function() { return calls("POST", peerBase + "/api/books/running/pause").length === 1 })
            compare(calls("POST", peerBase + "/api/books/running/pause")[0].body, {paused: true})
            // KHÔNG một lời gọi nào đi thẳng vào máy này
            const direct = DesktopApi.requests.filter(r => (/^\/api\/(library|books)/).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct))
            both("peer_project", page)
        }
        function test_peerDeleteAndRestoreSayTheyAreOnTheComputer() {
            const broken = book("bad", {title: "Sổ hỏng", broken: "thiếu tệp", brokenKind: "corrupt", backup: true})
            reply("GET " + peerBase + "/api/app", peerApp())
            reply("GET " + peerBase + "/api/library", library([book("a", {title: "Cuốn a"}), broken]))
            const page = makeStudio()
            Nav.studioPeer = peerId
            listed(page, 1)
            // "…" của hàng chỉ hiện khi rê chuột (opacity 0) nhưng vẫn bấm được: lấy nút của hàng "Cuốn a", không phải hàng hỏng
            tryVerify(function() { return all(page, "projectMore").filter(n => shown(n.parent)).length > 0 })
            all(page, "projectMore").filter(n => shown(n.parent))[0].clicked()
            tryVerify(function() { return all(page, "menu_onComputer").filter(shown).length > 0 })
            compare(one(page, "menu_onComputer").text, "Xoá dự án ở máy tính Máy bàn phòng làm việc")
            verify(!one(page, "menu_onComputer").enabled)
            verify(all(page, "menu_delete").filter(shown).length === 0)
            verify(Nav.back())
            // dự án hỏng: nói thẳng việc nằm ở máy tính
            tryVerify(function() { return all(page, "brokenOnComputer").filter(shown).length === 1 })
            verify(hasText(page, "Khôi phục hoặc xoá ở máy tính Máy bàn phòng làm việc"))
        }
        function test_peerChapterRowsDoNotPlayLocally() {
            const b = bookStates().done
            reply("GET " + peerBase + "/api/app", peerApp())
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + "/api/books/done", detail(b, [chapter(1)]))
            const page = makeStudio()
            Nav.studioPeer = peerId
            listed(page, 1)
            page.openProject("done")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "chapterTitle").filter(shown).length === 1 })
            verify(!one(page, "chapterRowButton").enabled)
        }
        function test_peerSwitchResetsToTheList() {
            const b = bookStates().done
            reply("GET " + peerBase + "/api/app", peerApp())
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + "/api/books/done", detail(b, [chapter(1)]))
            const page = openBook(b, [chapter(1)])
            Nav.studioPeer = peerId
            tryCompare(page, "route", "list")
            compare(page.studioStore.bookId, "")
        }
        function test_backClosesProjectThenReselectGoesHome() {
            const page = openBook(bookStates().done, [chapter(1)])
            verify(Nav.layers.length > 0)
            verify(Nav.back())
            tryCompare(page, "shownKey", "route:list")
            compare(page.studioStore.bookId, "")
            compare(Nav.layers.length, 0)
        }
    }
}
