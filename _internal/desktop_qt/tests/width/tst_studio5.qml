import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import "ModalLayer.js" as ModalLayer
import ABook
import "../../qml/ExportLogic.js" as Export
import "../../qml/StudioLogic.js" as Studio
import "../../qml/StudioSetupLogic.js" as Setup
import "../../qml/NewProjectLogic.js" as Credits

// Studio S5: hộp Xuất (bốn kiểu, nơi lưu, tiến độ nền, kết quả, huỷ, nối lại), hộp Áp dụng (danh sách, bỏ, nghe thử, bản khoá khi sách chạy), khung Lỗi chương, "Chữ sáng",
// và các bài test của bản web chép sang: exportText, credits, bookFilePacking, errorText, analyzerLabel, applyChangesLocked, exportTextOnly. Máy chủ giả giữ trạng thái;
// HTTP là DesktopApi giả; hộp chọn thư mục là NativeFolders giả (không bao giờ mở hộp thật). Ảnh sáng / tối ghi ra build/d2shots/s5_*.png để tự nhìn.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    // Hộp / bảng nổi và hộp chọn đều nằm dưới gốc cửa sổ (WindowLayer, Overlay)
    readonly property var overlay: Window.window ? Window.window.contentItem : null
    Component { id: studioFactory; StudioScreen {} }
    Component { id: listFactory; PendingList { width: 500 } }

    TestCase {
        id: test
        name: "Studio5"
        when: windowShown

        readonly property string peerId: "c0ffee000001"
        readonly property string peerBase: "/api/peers/c0ffee000001/studio"
        readonly property string base: "/api/books/a"
        property var server: ({})

        function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        // gồm cả hộp / bảng nổi do `item` mở (WindowLayer nằm ở gốc cửa sổ, không còn là con của trang)
        function all(item, name) { return ModalLayer.findAll(item, name) }
        function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
        function one(item, name) { const found = all(item, name); verify(found.length > 0, "thiếu " + name); return found.filter(shown)[0] || found[0] }
        function has(item, name) { return all(item, name).filter(shown).length > 0 }
        function texts(item) { return ModalLayer.collect(item, node => node.text !== undefined && shown(node)).map(node => String(node.text)) }
        function textOf(item, name) { const found = all(item, name).filter(shown)[0]; return found ? String(found.text) : "" }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function hasPart(item, part) { return texts(item).some(t => t.indexOf(part) >= 0) }
        function all2(item, test) { return ModalLayer.collect(item, test) }
        function shot(name, item) {
            const target = item || host
            tryVerify(function() { return all2(target, n => n.settled === false && n.reveal !== undefined).length === 0 }, 3000)
            waitForRendering(target)
            const path = Qt.resolvedUrl("../../build/d2shots/s5_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(VisualReady.grabTarget(host.Window.window, target)).save(path)
        }
        function both(name, item) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shot(name, item) } Theme.mode = "auto" }
        function noCut(item) {
            for (const text of all2(item, t => t.contentWidth !== undefined && t.wrapMode !== undefined && shown(t) && String(t.text) !== "")) {
                verify(text.contentWidth <= text.width + 1, "chữ tràn ngang: " + String(text.text).slice(0, 40) + " " + text.contentWidth + ">" + text.width)
                verify(text.contentHeight <= text.height + 1 || text.height === 0, "chữ bị cắt: " + String(text.text).slice(0, 40))
            }
        }
        function clone(v) { return JSON.parse(JSON.stringify(v)) }
        function stamp() { return Math.floor(Date.now() / 1000) }
        function longText() {
            return "Một đoạn chữ rất dài của người dùng, viết liền một mạch không ngắt để thử xem giao diện xuống dòng đúng chỗ hay tràn ra ngoài khung: "
                + "Nguyễn Thị Hạ Vy Của Vương Quốc Phía Đông Xa Xôi Và Những Ngày Tháng Không Thể Nào Quên Được cùng những người bạn đồng hành của cô ấy."
        }

        // ---- dữ liệu giả ----
        function book(id, over) {
            return Object.assign({
                id: id, title: "Cuốn " + id, statusLabel: "Đang dừng", running: false, starting: false, paused: "", canPause: false, stopping: false,
                phase: "done", queuePosition: 0, pendingChanges: 0, audioSeconds: 5400, eta: null, startError: "", lastError: "", runEnd: null,
                createdAt: stamp() - 86400, updatedAt: stamp() - 3600, path: "D:\\Sách\\" + id, castLocked: true, precast: null,
                chapters: {total: 3, completed: 3, redo: 0, missingAudio: 0, failed: 0, working: 0},
                segments: {total: 120, analyzed: 120, recorded: 120, finished: 120, failed: 0, warnings: 0},
                progress: {overall: 1, analysis: 1, synthesis: 1}, settings: {narrator: "Mai", profile: "balanced", profileLabel: "Cân bằng"}
            }, over || {})
        }
        function chapter(id, over) {
            return Object.assign({id: id, index: id, title: "Chương " + id, displayTitle: "Chương " + id, subtitle: "", fullTitle: "Chương " + id, status: "completed", statusLabel: "Đã thu",
                    segments: {total: 10, analyzed: 10, recorded: 10, finished: 10, failed: 0, warnings: 0}, seconds: 300, playable: true, redo: false,
                    startedAt: stamp() - 7200, completedAt: stamp() - 3600, lastError: ""}, over || {})
        }
        function library(books) { return {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: books}} }
        function ffmpegStatus(over) {
            return Object.assign({ready: false, outdated: false, downloading: false, done: 0, total: 0, error: "", bytes: 75000000, blocked: ""}, over || {})
        }
        function pendingFixture(over) {
            return Object.assign({
                items: [
                    {kind: "pronunciation", label: "“Lucien” đọc là “lu-xi-ăng”", lines: 4, section: "pronunciations", key: "Lucien", requestedAt: 1},
                    {kind: "speaker", label: "“Đi thôi,” - Natasha", chapter: "Chương 2", lines: 1, section: "speakers", key: "c2s4", requestedAt: 2, from: "Máy bàn"},
                    {kind: "voice", label: "Lan đổi sang giọng Hương", lines: 0, section: "voices", key: "Lan", requestedAt: 3, voice: {character: "Lan", preset: "huong"}, voiceLabel: "Hương"}],
                lines: 5, chapters: ["Chương 1", "Chương 2"], seconds: 180, measured: true}, over || {})
        }

        // ---- máy chủ giả có trạng thái ----
        function serve(extra) {
            server = Object.assign({
                parts: {parts: [{id: "a", title: "Cuốn a", part: 1, current: true}]}, history: [], size: {bytes: 5000000, parts: 1}, music: {available: false, enabled: false},
                ffmpeg: ffmpegStatus({ready: true}), wordTimings: {state: "idle", lines: 120, words: 0}, running: {}, pending: pendingFixture(), posted: [],
                jobs: {"mp3-job": {state: "idle"}, "m4b-job": {state: "idle"}, "bookfile-job": {state: "idle"}, "projectfile-job": {state: "idle"}}, music_state: {active: false, done: 0, total: 0}
            }, extra || {})
            for (const prefix of ["", peerBase]) {
                reply("GET " + prefix + base + "/parts", function() { return {status: 200, data: clone(server.parts)} })
                reply("GET " + prefix + base + "/export-history", function() { return {status: 200, data: clone(server.history)} })
                reply("GET " + prefix + base + "/export-size", function() { return {status: 200, data: clone(server.size)} })
                reply("GET " + prefix + base + "/export-size?series=1", function() { return {status: 200, data: clone(server.size)} })
                reply("GET " + prefix + base + "/export-music", function() { return {status: 200, data: clone(server.music)} })
                reply("GET " + prefix + base + "/music-export", function() { return {status: 200, data: clone(server.music_state)} })
                reply("GET " + prefix + base + "/music-export?kind=projectfile", function() { return {status: 200, data: clone(server.music_state)} })
                reply("GET " + prefix + "/api/ffmpeg", function() { return {status: 200, data: clone(server.ffmpeg)} })
                reply("POST " + prefix + "/api/ffmpeg", function() { server.ffmpeg = ffmpegStatus({downloading: true, done: 25, total: 100}); return {status: 200, data: clone(server.ffmpeg)} })
                reply("POST " + prefix + "/api/ffmpeg/cancel", function() { server.ffmpeg = ffmpegStatus(); return {status: 200, data: clone(server.ffmpeg)} })
                reply("GET " + prefix + "/api/export-jobs", function() {
                    const out = {}
                    for (const [seg, name] of [["mp3-job", "mp3"], ["m4b-job", "m4b"], ["bookfile-job", "bookfile"], ["projectfile-job", "projectfile"]])
                        out[name] = server.jobs[seg].state === "running" ? [Object.assign({bookId: "a"}, clone(server.jobs[seg]))] : []
                    return {status: 200, data: out}
                })
                reply("GET " + prefix + base + "/word-timings", function() { return {status: 200, data: clone(server.wordTimings)} })
                reply("POST " + prefix + base + "/word-timings", function() { server.wordTimings = {state: "running", lines: 120, words: 0, done: 30, total: 120}; return {status: 200, data: clone(server.wordTimings)} })
                reply("GET " + prefix + base + "/pending-changes", function() { return {status: 200, data: clone(server.pending)} })
                reply("POST " + prefix + base + "/pending-changes/withdraw", function(body) {
                    server.pending.items = server.pending.items.filter(i => !(i.section === body.section && i.key === body.key))
                    return {status: 200, data: {}}
                })
                reply("POST " + prefix + base + "/voice/preview", {status: 200, data: {url: "/media/previews/p1.wav", text: "“Anh đi đâu thế?”"}})
                reply("POST " + prefix + "/api/reveal-export", {status: 200, data: {}})
                for (const seg of ["mp3-job", "m4b-job", "bookfile-job", "projectfile-job"]) {
                    reply("GET " + prefix + base + "/" + seg, function() { return {status: 200, data: clone(server.jobs[seg])} })
                    reply("POST " + prefix + base + "/" + seg, function(body) {
                        server.posted = server.posted.concat([{seg: seg, body: body}])
                        server.jobs[seg] = Object.assign({state: "running", id: "j-" + seg}, server.running[seg] || {})
                        return {status: 200, data: {state: "running", id: "j-" + seg}}
                    })
                    reply("POST " + prefix + base + "/" + seg + "/cancel", function() { server.jobs[seg] = {state: "cancelled"}; return {status: 200, data: {}} })
                }
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
            Clip.stop()
        }
        function cleanup() {
            Theme.mode = "auto"; Theme.reduceMotion = false
            Nav.layers = []; Nav.studioPeer = ""; Api.notice = ""
            DesktopApi.delayed = false
            Clip.stop()
        }
        function makeStudio(width, height) {
            const page = createTemporaryObject(studioFactory, host, {width: width || 1280, height: height || 900})
            verify(page !== null)
            return page
        }
        function openProject(width, b, chapters) {
            const row = b || book("a")
            reply("GET /api/library", library([row]))
            reply("GET " + base, {status: 200, data: {book: row, chapters: chapters || [chapter(1), chapter(2), chapter(3)]}})
            const page = makeStudio(width)
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            return page
        }
        function screenOf(page) { return page.projectScreenList.parent }
        function exportDlg(page) { return all(page, "exportBook").filter(shown)[0] }
        function applyDlg(page) { return all(page, "applyChanges").filter(shown)[0] }
        function openExport(b, width) {
            const row = b || book("a")
            const page = openProject(width, row)
            screenOf(page).dialogs.perform("export", row)
            tryVerify(function() { return exportDlg(page) !== undefined }, 3000)
            tryVerify(function() { return calls("GET", base + "/parts").length >= 1 }, 3000)
            return page
        }
        function pickKind(dlg, kind) {
            one(dlg, "exportKind_" + kind).choose()
            tryCompare(dlg, "kind", kind, 3000)
        }
        function goExport(dlg) {
            tryVerify(function() { return one(dlg, "confirm_go").enabled }, 3000)
            one(dlg, "confirm_go").clicked()
        }
        function stepJob(seg, state) { server.jobs[seg] = state }

        // ================= A. bài test của bản web, chép sang =================
        // ---- exportText.test.ts ----
        function test_exportNoteSaysTheExportUsesTheOldRecording() {
            compare(Export.redoExportNote(3, false), "3 chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy.")
            compare(Export.redoExportNote(1, true),
                    "1 chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy; tên giọng ghi trong sách có thể đã là giọng mới.")
        }
        function test_exportNoteIsSilentWhenNothingWaits() { compare(Export.redoExportNote(0, true), null) }

        // ---- credits.test.ts ----
        function test_creditsCountTheFirstLinesWhenNoChapterEndsWithASupportLine() {
            const credits = Credits.creditSummary([{credits: ["TL : NicK"]}, {credits: ["TL : NicK"]}, {credits: []}])
            compare(credits, {lines: 2, head: 2, tail: 0, chapters: 2, examples: ["“TL : NicK”"]})
            compare(Credits.creditKind(credits), "dòng ghi công")
            compare(Credits.creditWhere(credits), "dòng ghi công người dịch ở đầu chương")
        }
        function test_creditsListTheEndOfChapterLinesToo() {
            const credits = Credits.creditSummary([
                {credits: ["TL : NicK"], tailCredits: ["Ủng hộ qua Momo 0912345678"]},
                {credits: [], tailCredits: ["Đọc truyện full tại truyenfull.vn"]},
                {credits: ["Editor: Deemo"]}])
            compare(credits.lines, 4)
            compare(credits.chapters, 3)
            compare(credits.examples, ["“TL : NicK”", "“Editor: Deemo”", "“Ủng hộ qua Momo 0912345678” (cuối chương)"])
            compare(Credits.creditKind(credits), "dòng ghi công, xin ủng hộ, quảng cáo")
        }
        function test_creditsNameOnlyTheEndWhenThatIsAllThereIs() {
            const credits = Credits.creditSummary([{tailCredits: ["Hết chương 8"]}])
            compare(credits.examples, ["“Hết chương 8” (cuối chương)"])
            compare(Credits.creditWhere(credits), "dòng xin ủng hộ, quảng cáo hay nguồn ở cuối chương")
        }
        readonly property var creditFiles: [
            {name: "1.txt", credits: ["TL : NicK"], tailCredits: ["Ủng hộ qua Momo"]},
            {name: "2.txt", credits: []},
            {name: "3.txt", tailCredits: ["Hết chương 3", "Nguồn: truyenfull.vn"]}]
        function test_creditsListEveryLineByChapter() {
            compare(Credits.creditRows(creditFiles, f => f.name), [
                {chapter: "1.txt", head: ["TL : NicK"], tail: ["Ủng hộ qua Momo"]},
                {chapter: "3.txt", head: [], tail: ["Hết chương 3", "Nguồn: truyenfull.vn"]}])
        }
        function test_creditsDropHeadAndTailSeparately() {
            const credits = Credits.creditSummary(creditFiles)
            compare(Credits.droppedLines(credits, Credits.KEEP_CREDITS), 0)
            compare(Credits.droppedLines(credits, {head: true, tail: false}), 1)
            compare(Credits.droppedLines(credits, {head: false, tail: true}), 3)
            compare(Credits.droppedLines(credits, {head: true, tail: true}), 4)
        }
        function test_creditsOnlyTailDroppedSaysTheHeadLinesAreStillRead() {
            const drop = {head: false, tail: true}
            compare(Credits.creditLine("Dịch: Nhóm Lục Bình", "head", drop), {text: "“Dịch: Nhóm Lục Bình” (đầu chương, vẫn đọc)", dropped: false})
            compare(Credits.creditLine("Ủng hộ qua Momo", "tail", drop), {text: "“Ủng hộ qua Momo” (cuối chương, bỏ)", dropped: true})
            compare(Credits.creditLine("TL : NicK", "head", Credits.KEEP_CREDITS), {text: "“TL : NicK” (đầu chương)", dropped: false})
        }

        // ---- bookFilePacking.test.ts ----
        function test_packBookFileGivesTheJobAtOnceThenFollows_data() { return [{tag: "một file", single: true}, {tag: "mỗi phần một file", single: false}] }
        function test_packBookFileGivesTheJobAtOnceThenFollows(data) {
            const seen = []
            const result = {folder: "out", parts: [1, 2, 3]}
            let followed = 0, got = null
            const request = function(method, path, body, done) { seen.push({method: method, path: path, body: body}); done(200, {state: "running", id: "j1"}) }
            const follow = function(done) { followed++; done(null, result) }
            Export.packBookFile(request, "b1", {target: "out", series: true, single: data.single}, follow, false, function(error, packed) { got = packed })
            compare(got, result)
            compare(seen, [{method: "POST", path: "/api/books/b1/bookfile-job", body: {target: "out", series: true, single: data.single}}])
            compare(followed, 1)
        }
        function test_packBookFileReattachOnlyFollowsTheExistingJob() {
            const seen = []
            let got = null
            const request = function(method, path, body, done) { seen.push(path) }
            Export.packBookFile(request, "b1", {target: "", series: true}, function(done) { done(null, {file: "old.abook"}) }, true, function(error, packed) { got = packed })
            compare(got, {file: "old.abook"})
            compare(seen.length, 0)
        }
        function test_packBookFileRefusedStartNeverFollows() {
            let followed = 0, failure = ""
            const request = function(method, path, body, done) { done(409, {message: "Dự án đang chạy"}) }
            Export.packBookFile(request, "b1", {target: ""}, function(done) { followed++ }, false, function(error) { failure = error })
            compare(failure, "Dự án đang chạy")
            compare(followed, 0)
        }

        // ---- errorText.test.ts ----
        function test_errorTextSaysGraphicsMemoryAndTheNextStep() {
            const shown = Studio.friendlyError("RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB")
            compare(shown.summary, "Card đồ hoạ hết bộ nhớ.")
            verify(shown.hint.indexOf("bấm Tiếp tục") >= 0)
            verify(shown.detail.indexOf("CUDA out of memory") >= 0)
        }
        function test_errorTextRecognisesOllamaAndFullDisk() {
            verify(Studio.friendlyError("httpx.ConnectError: [WinError 10061] No connection could be made because the target machine actively refused it").summary.indexOf("Ollama") >= 0)
            compare(Studio.friendlyError("OSError: [Errno 28] No space left on device").summary, "Ổ đĩa hết chỗ trống.")
            compare(Studio.friendlyError("OSError: [WinError 112] There is not enough space on the disk").summary, "Ổ đĩa hết chỗ trống.")
        }
        function test_errorTextBundledStudioDoesNotPointAtTheTrayIcon() {
            const raw = "httpx.ConnectError: actively refused it"
            verify(Studio.friendlyError(raw).hint.indexOf("khay hệ thống") >= 0)
            const bundled = Studio.friendlyError(raw, true)
            verify(bundled.hint.indexOf("khay") < 0)
            verify(bundled.hint.indexOf("Sửa Studio") >= 0)
            verify(Studio.friendlyError("OSError: [Errno 28] No space left on device", true).hint.indexOf("Giải phóng") >= 0)
        }
        function test_errorTextHalfInstalledStudioSpeaksToTheListener() {
            const raw = "Lỗi ở bước ollama: URLError: <urlopen error [Errno 11001] getaddrinfo failed>"
            const shown = Setup.friendlySetupError(raw)
            compare(shown.summary, "Mất mạng giữa chừng - bấm Cài tiếp để làm tiếp.")
            compare(shown.detail, raw)
            compare(Setup.friendlySetupError("Đã dừng - bấm Cài tiếp để làm tiếp từ bước dở."), {summary: "Đã dừng - bấm Cài tiếp để làm tiếp từ bước dở.", detail: ""})
        }
        function test_errorTextInterruptedAnalysisPointsAtRedoNotContinue() {
            for (const raw of ["RuntimeError: CUDA out of memory", "httpx.ConnectError: actively refused it", "OSError: [Errno 28] No space left on device", "KeyError: 'x'"]) {
                verify(/[Bb]ấm Tiếp tục/.test(Studio.friendlyError(raw).hint), raw)
                for (const studio of [false, true]) {
                    const redo = Studio.friendlyError(raw, studio, true).hint
                    verify(!/[Bb]ấm Tiếp tục/.test(redo), raw + " " + redo)
                    verify(/Làm lại phân tích từ đầu/.test(redo), raw)
                }
            }
        }
        function test_errorTextSqliteFullAndResourceGateAreFullDisk() {
            compare(Studio.friendlyError("sqlite3.OperationalError: database or disk is full").summary, "Ổ đĩa hết chỗ trống.")
            const gate = Studio.friendlyError("disk free 4.0 GB", true)
            compare(gate.summary, "Ổ đĩa chứa thư viện sách chỉ còn 4.0 GB.")
            verify(gate.hint.indexOf("Giải phóng thêm dung lượng") >= 0)
            verify(!/[Bb]ấm Tiếp tục/.test(Studio.friendlyError("disk free 8.0 GB", true, true).hint))
        }
        function test_errorTextAnalysisModelMissingIsNotAConnectionError() {
            const raw = "Ollama/Qwen model abook-analyzer:v4 không sẵn sàng. Pipeline dừng thay vì âm thầm hạ chất lượng phân tích toàn book."
            const unknown = Studio.friendlyError(raw, true)
            verify(unknown.summary.indexOf("Ollama chưa chạy hoặc chưa có model") >= 0)
            verify(unknown.hint.indexOf("Sửa Studio") >= 0)
            const lost = Studio.friendlyError(raw, true, false, true)
            compare(lost.summary, "Studio mất model phân tích truyện (file đã bị xoá hay hỏng).")
            verify(lost.hint.indexOf("Sửa Studio") >= 0)
            compare(lost.detail, raw)
            verify(Studio.friendlyError(raw, true, true, true).hint.indexOf("Làm lại phân tích từ đầu") >= 0)
            verify(Studio.friendlyError("httpx.ConnectError: actively refused it", true, false, false).summary.indexOf("kết nối được Ollama") >= 0)
        }
        function test_errorTextUnknownErrorIsGenericAndTheRawTextIsOnlyDetail() {
            const shown = Studio.friendlyError("  KeyError: 'speaker'  ")
            compare(shown.summary, "Có lỗi khi làm sách.")
            verify(shown.summary.indexOf("KeyError") < 0)
            compare(shown.detail, "KeyError: 'speaker'")
        }

        // ---- analyzerLabel.test.ts ----
        function test_analyzerLabelOwnModelSaysTheVersionNumber() { compare(Studio.analyzerLabel("abook-analyzer:v4"), "Bộ phân tích bản 4") }
        function test_analyzerLabelCustomModelHidesTheTechnicalKey() {
            compare(Studio.analyzerLabel("qwen3:8b"), "Bộ phân tích tuỳ chọn")
            compare(Studio.analyzerLabel("custom:latest"), "Bộ phân tích tuỳ chọn")
        }
        function test_narratorLabelShowsThePendingVoiceAndWaitsForApply() {
            compare(Studio.narratorLabel({narrator: "Phạm Tuyên", narratorPending: "Hải Đăng"}), "Giọng kể Hải Đăng (chờ áp dụng)")
            compare(Studio.narratorLabel({narrator: "Phạm Tuyên", narratorPending: ""}), "Giọng kể Phạm Tuyên")
            compare(Studio.narratorLabel({narrator: ""}), "")
        }

        // ---- applyChangesLocked.test.tsx ----
        readonly property var lockedItem: ({kind: "speaker", label: "“Xin chào” - Natasha", lines: 1, section: "speakers", key: "c1s2", requestedAt: 1})
        function test_dropButtonIsEnabledWhetherOrNotTheBookRuns() {
            const list = createTemporaryObject(listFactory, host, {items: [lockedItem]})
            tryVerify(function() { return all(list, "pendingDrop").length === 1 }, 3000)
            const drop = all(list, "pendingDrop")[0]
            compare(drop.Accessible.name, "Bỏ đổi người nói: “Xin chào” - Natasha")
            compare(drop.enabled, true)
        }
        function test_dropButtonsTurnOffWhileOneIsBeingDropped() {
            const list = createTemporaryObject(listFactory, host, {items: [lockedItem], dropping: "speakers:c1s2"})
            tryVerify(function() { return all(list, "pendingDrop").length === 1 }, 3000)
            compare(all(list, "pendingDrop")[0].enabled, false)
        }
        function test_dropLabelNamesWhatItDrops() {
            compare(Export.dropLabel({kind: "pronunciation", label: "“Lucien” đọc là “lu-xi-ăng”"}), "Bỏ cách đọc “Lucien”")
            compare(Export.dropLabel({kind: "pronunciation", label: "cách đọc không có ngoặc"}), "Bỏ cách đọc: cách đọc không có ngoặc")
            compare(Export.dropLabel({kind: "voice", label: "Lan đổi giọng"}), "Bỏ đổi giọng: Lan đổi giọng")
            compare(Export.dropLabel({kind: "retake", label: "Chương 3"}), "Bỏ thu lại: Chương 3")
        }

        // ---- exportTextOnly.test.tsx ----
        function test_textOnlyProjectCanExportAbookAndTheDialogSaysItCarriesTheText() {
            serve()
            const page = openExport(book("a", {chapters: {total: 2, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}}))
            const dlg = exportDlg(page)
            pickKind(dlg, "abook")
            tryVerify(function() { return one(dlg, "confirm_go").enabled }, 3000)
            compare(one(dlg, "confirm_go").text, "Lưu và xuất")
            tryVerify(function() { return hasPart(dlg, "chỉ mang chữ") }, 3000)
        }
        function test_projectWithNoChaptersAtAllCannotExportAbook() {
            serve()
            const page = openExport(book("a", {chapters: {total: 0, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}}))
            const dlg = exportDlg(page)
            pickKind(dlg, "abook")
            compare(one(dlg, "confirm_go").enabled, false)
            compare(one(dlg, "confirm_go").text, "Lưu và xuất")
        }
        function test_mp3StaysBlockedWhileNoChapterHasAudio() {
            serve()
            const page = openExport(book("a", {chapters: {total: 2, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}}))
            const dlg = exportDlg(page)
            compare(dlg.kind, "mp3")
            compare(one(dlg, "confirm_go").enabled, false)
        }

        // ================= B. hộp Xuất =================
        function test_exportDialogListsTheKindsAndSaysWhatTheExportWillHave() {
            serve()
            const page = openExport(book("a", {chapters: {total: 4, completed: 3, redo: 0, missingAudio: 1, failed: 0, working: 0}}))
            const dlg = exportDlg(page)
            compare(dlg.title, "Xuất “Cuốn a”")
            compare(dlg.description, "2 chương sẽ vào bản xuất.")
            for (const kind of ["mp3", "abook", "m4b", "abookproj"]) verify(has(dlg, "exportKind_" + kind), kind)
            verify(hasText(dlg, "Thư mục MP3") && hasText(dlg, "File .abook") && hasText(dlg, "Sách nói M4B") && hasText(dlg, "Cả dự án (.abookproj)"))
            verify(hasText(dlg, "Bấm nút bên dưới rồi chọn thư mục để lưu."))
            tryVerify(function() { return hasPart(dlg, "2/4 chương chưa có audio (1 chương mất file) - không có trong bản xuất.") }, 3000)
            compare(one(dlg, "confirm_go").text, "Lưu và xuất")
            verify(one(dlg, "confirm_go").enabled)
            verify(has(dlg, "exportKindLine"))
            noCut(dlg)
            both("export_form", page)
        }
        function test_exportKindsSlideTheLineAndKeysMoveTheChoice() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            const line = one(dlg, "exportKindLine")
            const first = line.y
            pickKind(dlg, "m4b")
            verify(line.y > first)
            const row = one(dlg, "exportKind_m4b")
            row.forceActiveFocus()
            keyClick(Qt.Key_Down)
            tryCompare(dlg, "kind", "abookproj")
            keyClick(Qt.Key_Up)
            tryCompare(dlg, "kind", "m4b")
        }
        function test_exportEscBackClosesTheDialogThroughTheBackStack() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            verify(Nav.layers.length > 0)
            Nav.back()
            tryVerify(function() { return !dlg.open }, 3000)
        }

        function test_mp3ExportPicksAFolderStartsTheJobAndShowsProgressThenTheResult() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            goExport(dlg)
            tryVerify(function() { return DesktopApi.folders.length === 1 }, 3000)
            compare(DesktopApi.folders[0].title, "Chọn nơi lưu")
            tryVerify(function() { return calls("POST", base + "/mp3-job").length === 1 }, 3000)
            compare(calls("POST", base + "/mp3-job")[0].body, {target: "D:/Đã xuất"})
            tryCompare(dlg, "phase", "busy", 3000)
            tryVerify(function() { return has(dlg, "exportIndeterminate") }, 3000)
            stepJob("mp3-job", {state: "running", phase: "chapters", chapter: 2, chapters: 3, elapsed: 20})
            tryVerify(function() { return has(dlg, "exportBar") && one(dlg, "exportBusyTitle").text === "Đang ghi chương 2/3" }, 4000)
            verify(one(dlg, "exportBusyNote").text.indexOf("3 chương; đóng hộp vẫn xuất nền và báo khi xong.") === 0)
            compare(one(dlg, "confirm_cancel").text, "Huỷ xuất")
            compare(one(dlg, "confirm_later").text, "Đóng, cứ để chạy")
            both("export_busy", page)
            stepJob("mp3-job", {state: "done", result: {folder: "D:\\Đã xuất\\Cuốn a", files: 3, size: 15000000}})
            tryCompare(dlg, "phase", "finished", 4000)
            compare(one(dlg, "exportDoneTitle").text, "Đã xuất MP3")
            verify(one(dlg, "exportDoneDetail").text.indexOf("Cuốn a · 3 file · 14 MB") === 0)
            compare(one(dlg, "confirm_done").text, "Xong")
            one(dlg, "confirm_reveal").clicked()
            tryVerify(function() { return calls("POST", "/api/reveal-export").length === 1 }, 3000)
            compare(calls("POST", "/api/reveal-export")[0].body, {folder: "D:\\Đã xuất\\Cuốn a"})
            both("export_done", page)
            one(dlg, "confirm_done").clicked()
            tryVerify(function() { return !dlg.open }, 3000)
        }
        function test_cancellingTheFolderPickerStartsNothing() {
            serve()
            DesktopApi.folderAnswer = ""
            const page = openExport()
            goExport(exportDlg(page))
            tryVerify(function() { return DesktopApi.folders.length === 1 }, 3000)
            wait(50)   // fixed: proves absence
            compare(calls("POST", base + "/mp3-job").length, 0)
            compare(exportDlg(page).phase, "form")
        }
        function test_abookExportFollowsPackingPhasesThenNamesTheFile() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            pickKind(dlg, "abook")
            tryVerify(function() { return has(dlg, "exportEstimate") }, 3000)
            verify(one(dlg, "exportEstimate").text.indexOf("Cỡ ước tính: khoảng 4,8 MB") === 0)
            goExport(dlg)
            tryVerify(function() { return calls("POST", base + "/bookfile-job").length === 1 }, 3000)
            compare(DesktopApi.folders[0].title, "Chọn nơi lưu")
            compare(calls("POST", base + "/bookfile-job")[0].body, {target: "D:/Đã xuất", series: false})
            stepJob("bookfile-job", {state: "running", phase: "listen", done: 1, total: 3})
            tryVerify(function() { return has(dlg, "exportBar") && one(dlg, "exportBusyTitle").text === "Đang đóng gói (1/3 chương)…" }, 4000)
            stepJob("bookfile-job", {state: "done", result: {file: "D:\\Đã xuất\\Cuốn a.abook", folder: "D:\\Đã xuất", size: 5000000}})
            tryCompare(dlg, "phase", "finished", 4000)
            compare(one(dlg, "exportDoneTitle").text, "Đã xuất file sách")
            compare(one(dlg, "exportDoneDetail").text, "D:\\Đã xuất\\Cuốn a.abook · 4,8 MB")
        }
        function test_projectExportSendsOnlyTheTargetAndAFailureSaysItInWords() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            pickKind(dlg, "abookproj")
            compare(one(dlg, "confirm_go").text, "Lưu và xuất")
            goExport(dlg)
            tryVerify(function() { return calls("POST", base + "/projectfile-job").length === 1 }, 3000)
            compare(DesktopApi.folders[0].title, "Chọn nơi lưu")
            compare(calls("POST", base + "/projectfile-job")[0].body, {target: "D:/Đã xuất"})
            stepJob("projectfile-job", {state: "running", phase: "hash", done: 1048576, total: 4194304})
            tryVerify(function() { return has(dlg, "exportBar") && one(dlg, "exportBusyTitle").text.indexOf("Đang đóng gói (1 MB/4 MB)") === 0 }, 4000)
            verify(one(dlg, "exportBusyNote").text === "đóng hộp vẫn xuất nền và báo khi xong.")
            stepJob("projectfile-job", {state: "error", error: "PermissionError: [Errno 13] Permission denied: 'D:/x'"})
            tryCompare(dlg, "phase", "form", 4000)
            tryVerify(function() { return Api.notice.indexOf("Chưa gói được dự án") === 0 }, 3000)
            verify(Api.notice.indexOf("Chưa ghi được vào thư mục đã chọn") > 0)
            verify(Api.notice.indexOf("PermissionError") > 0)
        }
        function test_exportRefusedAtTheStartShowsTheServerMessage() {
            serve()
            reply("POST " + base + "/m4b-job", {status: 409, data: {message: "Chưa có chương nào để xuất."}})
            const page = openExport()
            const dlg = exportDlg(page)
            pickKind(dlg, "m4b")
            goExport(dlg)
            tryVerify(function() { return Api.notice === "Chưa xuất được M4B\nChưa có chương nào để xuất." }, 3000)
            compare(dlg.phase, "form")
        }
        function test_cancellingAnExportTellsTheServerAndReturnsToTheForm() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            goExport(dlg)
            tryCompare(dlg, "phase", "busy", 3000)
            one(dlg, "confirm_cancel").clicked()
            tryVerify(function() { return calls("POST", base + "/mp3-job/cancel").length === 1 }, 3000)
            tryVerify(function() { return one(dlg, "exportBusyTitle").text === "Đang huỷ…" || dlg.phase === "form" }, 3000)
            tryCompare(dlg, "phase", "form", 4000)
            tryVerify(function() { return Api.notice === "Đã dừng xuất" }, 3000)
        }
        function test_closingTheDialogKeepsExportingAndTheFinishIsAnnounced() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            goExport(dlg)
            tryCompare(dlg, "phase", "busy", 3000)
            one(dlg, "confirm_later").clicked()
            tryVerify(function() { return !dlg.open }, 3000)
            stepJob("mp3-job", {state: "done", result: {folder: "D:\\Đã xuất\\Cuốn a", files: 3, size: 15000000, chapters: 2, chaptersTotal: 3}})
            tryVerify(function() { return Api.notice.indexOf("Đã xuất MP3") === 0 }, 4000)
            verify(Api.notice.indexOf("2/3 chương - chương chưa xong không có trong file") > 0)
            compare(dlg.finished, null)
        }
        function test_openingTheDialogWhileTheServerIsExportingFollowsTheJobInstead() {
            serve({jobs: {"mp3-job": {state: "idle"}, "m4b-job": {state: "idle"}, "bookfile-job": {state: "idle"},
                          "projectfile-job": {state: "running", id: "p1", phase: "write", done: 1048576, total: 2097152}}})
            const page = openExport()
            const dlg = exportDlg(page)
            tryCompare(dlg, "phase", "busy", 3000)
            compare(dlg.kind, "abookproj")
            tryVerify(function() { return has(dlg, "exportBar") }, 4000)
            compare(calls("POST", base + "/projectfile-job").length, 0)
            compare(DesktopApi.folders.length, 0)
        }
        function test_nothingIsAskedWhileTheWindowIsHidden() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            goExport(dlg)
            tryCompare(dlg, "phase", "busy", 3000)
            tryVerify(function() { return calls("GET", base + "/mp3-job").length >= 1 }, 3000)
            const store = screenOf(page).store
            store.active = false
            wait(200)  // fixed: proves absence (a request already in flight lands before the count)
            const before = calls("GET", base + "/mp3-job").length
            wait(1500) // fixed: proves absence (the poll interval is 1 s)
            compare(calls("GET", base + "/mp3-job").length, before)
            store.active = true
            tryVerify(function() { return calls("GET", base + "/mp3-job").length > before }, 3000)
        }

        function test_wholeSeriesAsksScopeAndLayoutAndSendsThem() {
            serve({parts: {parts: [{id: "a", title: "Cuốn a", part: 1, current: true}, {id: "b", title: "Cuốn b", part: 2, current: false}]}})
            const page = openExport()
            const dlg = exportDlg(page)
            tryVerify(function() { return has(dlg, "exportScope") }, 3000)
            one(dlg, "exportScope").picked("series")
            tryCompare(dlg, "scope", "series", 3000)
            compare(dlg.description, "Các chương nghe được của cả 2 phần sẽ vào bản xuất.")
            tryVerify(function() { return hasText(dlg, "Mỗi phần một thư mục con trong thư mục của bộ.") }, 3000)
            pickKind(dlg, "abook")
            tryVerify(function() { return has(dlg, "exportLayout") && shown(one(dlg, "exportLayout")) }, 3000)
            verify(hasText(dlg, "Cả bộ trong một file .abook, nghe nối tiếp các phần."))
            one(dlg, "exportLayout").picked("perPart")
            tryCompare(dlg, "layout", "perPart", 3000)
            tryVerify(function() { return hasText(dlg, "Mỗi phần một file, cùng thư mục của bộ.") }, 3000)
            goExport(dlg)
            tryVerify(function() { return calls("POST", base + "/bookfile-job").length === 1 }, 3000)
            compare(calls("POST", base + "/bookfile-job")[0].body, {target: "D:/Đã xuất", series: true, single: false})
            compare(calls("GET", base + "/export-size?series=1").length >= 1, true)
            stepJob("bookfile-job", {state: "done", result: {folder: "D:\\Đã xuất\\Bộ", parts: [{part: 1, title: "a"}, {part: 2, title: "b"}], skipped: [{part: 3}]}})
            tryCompare(dlg, "phase", "finished", 4000)
            compare(one(dlg, "exportDoneTitle").text, "Đã xuất 2 file sách")
            verify(one(dlg, "exportDoneDetail").text.indexOf("D:\\Đã xuất\\Bộ · mỗi phần một file .abook riêng · chưa có chương nào nên bỏ qua: Phần 3") === 0)
            tryVerify(function() { return has(dlg, "exportDoneNote") }, 3000)
        }
        function test_m4bNeedsTheMixingToolAndOffersToDownloadIt() {
            serve({ffmpeg: ffmpegStatus()})
            const page = openExport()
            const dlg = exportDlg(page)
            pickKind(dlg, "m4b")
            tryVerify(function() { return has(dlg, "ffmpegNeeded") && shown(one(dlg, "ffmpegNeeded")) }, 3000)
            compare(one(dlg, "ffmpegTitle").text, "Thiếu công cụ ghép")
            verify(one(dlg, "ffmpegLine").text.indexOf("Tải một lần để ghép MP3 / M4B (khoảng ") === 0)
            compare(one(dlg, "confirm_go").enabled, false)
            both("export_ffmpeg", page)
            one(dlg, "ffmpegDownload").clicked()
            tryVerify(function() { return calls("POST", "/api/ffmpeg").length === 1 }, 3000)
            tryVerify(function() { return has(dlg, "ffmpegBar") && shown(one(dlg, "ffmpegBar")) && one(dlg, "ffmpegPercent").text === "25%" }, 3000)
            one(dlg, "ffmpegStop").clicked()
            tryVerify(function() { return calls("POST", "/api/ffmpeg/cancel").length === 1 }, 3000)
            server.ffmpeg = ffmpegStatus({ready: true})
            tryVerify(function() { return dlg.ffmpeg !== null && dlg.ffmpeg.ready === false }, 3000)
            dlg.loadFfmpeg()
            tryVerify(function() { return one(dlg, "confirm_go").enabled }, 3000)
        }
        function test_ffmpegFailureShowsTheErrorWithDetailAndRetry() {
            serve({ffmpeg: ffmpegStatus({error: "Chưa tải được công cụ ghép - kiểm tra mạng rồi bấm Thử lại.", errorDetail: "URLError: getaddrinfo failed"})})
            const page = openExport()
            const dlg = exportDlg(page)
            pickKind(dlg, "m4b")
            tryVerify(function() { return has(dlg, "ffmpegError") && shown(one(dlg, "ffmpegError")) }, 3000)
            compare(one(dlg, "ffmpegDownload").text, "Thử lại")
            noCut(dlg)
        }
        function test_mixingMusicRaisesTheSameToolPromptAndTheBodyAsksForMusic() {
            serve({music: {available: true, enabled: true}, ffmpeg: ffmpegStatus({ready: true})})
            const page = openExport()
            const dlg = exportDlg(page)
            tryVerify(function() { return has(dlg, "exportMusic") && shown(one(dlg, "exportMusic")) }, 3000)
            compare(one(dlg, "exportMusic").checked, true)
            verify(hasText(dlg, "Nhạc được trộn thẳng vào file, không tắt riêng được khi nghe."))
            goExport(dlg)
            tryVerify(function() { return calls("POST", base + "/mp3-job").length === 1 }, 3000)
            compare(calls("POST", base + "/mp3-job")[0].body, {target: "D:/Đã xuất", music: true})
        }
        function test_untickingMusicOmitsItAndTheChoiceIsRememberedForThatBook() {
            serve({music: {available: true, enabled: true}})
            const page = openExport()
            const dlg = exportDlg(page)
            tryVerify(function() { return has(dlg, "exportMusic") && shown(one(dlg, "exportMusic")) }, 3000)
            one(dlg, "exportMusic").toggled(false)
            tryCompare(one(dlg, "exportMusic"), "checked", false, 3000)
            goExport(dlg)
            tryVerify(function() { return calls("POST", base + "/mp3-job").length === 1 }, 3000)
            compare(calls("POST", base + "/mp3-job")[0].body, {target: "D:/Đã xuất"})
        }
        function test_staleExportsOfferToRedoOnlyTheChangedChapters() {
            serve({history: [{kind: "mp3", target: "D:\\Đã xuất\\Cuốn a", chapters: {}, changed: [1, 3]}, {kind: "m4b", target: "D:\\Đã xuất\\a.m4b", chapters: {}, changed: [2]}]})
            const page = openExport()
            const dlg = exportDlg(page)
            tryVerify(function() { return has(dlg, "exportStale") && all(dlg, "exportStale").filter(shown).length === 2 }, 3000)
            verify(hasText(dlg, "Bản xuất đã cũ"))
            verify(hasText(dlg, "D:\\Đã xuất\\Cuốn a · 2 chương đã đổi"))
            verify(hasText(dlg, "M4B gộp cả cuốn: bạn cần dựng lại cả file và thay bản đã chép hoặc gửi."))
            verify(hasText(dlg, "Xuất chương đổi") && hasText(dlg, "Xuất lại M4B"))
            compare(one(dlg, "exportChangedOnly").label, "Xuất 2 chương đổi")
            both("export_stale", page)
            const redo = all(dlg, "exportStaleRedo").filter(shown)[0]
            redo.clicked()
            tryCompare(dlg, "changedOnly", true, 3000)
            compare(dlg.description, "2 chương sẽ vào bản xuất.")
            goExport(dlg)
            tryVerify(function() { return calls("POST", base + "/mp3-job").length === 1 }, 3000)
            compare(calls("POST", base + "/mp3-job")[0].body, {target: "D:/Đã xuất", chapterIds: [1, 3]})
        }
        function test_pendingChangesWarnAndOfferToApplyFirst() {
            serve()
            const page = openExport(book("a", {pendingChanges: 3, chapters: {total: 3, completed: 3, redo: 2, missingAudio: 0, failed: 0, working: 0}}))
            const dlg = exportDlg(page)
            tryVerify(function() { return has(dlg, "exportPending") && shown(one(dlg, "exportPending")) }, 3000)
            verify(hasText(dlg, "Còn 3 thay đổi chưa áp - bản xuất đọc như TRƯỚC khi sửa."))
            verify(hasPart(dlg, "2 chương đang chờ thu lại theo sửa của bạn - sách xuất dùng bản thu cũ của các chương ấy."))
            one(dlg, "exportApplyFirst").clicked()
            tryVerify(function() { return !dlg.open && applyDlg(page) !== undefined }, 3000)
            compare(applyDlg(page).title, "Áp dụng 3 thay đổi?")
        }
        function test_wordTimingsRowOnlyExistsForAbookAndStartsTheAlignment() {
            serve()
            const page = openExport()
            const dlg = exportDlg(page)
            verify(!has(dlg, "wordTimings"))
            compare(calls("GET", base + "/word-timings").length, 0)
            pickKind(dlg, "abook")
            tryVerify(function() { return has(dlg, "wordTimings") && shown(one(dlg, "wordTimings")) }, 3000)
            tryVerify(function() { return calls("GET", base + "/word-timings").length >= 1 }, 3000)
            tryVerify(function() { return textOf(dlg, "wordTimingsNote") !== "Thêm chữ sáng theo giọng đọc, chạy nền vài phút." }, 3000)
            compare(textOf(dlg, "wordTimingsNote"), "0/120 câu đã có chữ sáng theo giọng đọc.")
            one(dlg, "wordTimingsStart").clicked()
            tryVerify(function() { return calls("POST", base + "/word-timings").length === 1 }, 3000)
            tryVerify(function() { return textOf(dlg, "wordTimingsNote") === "Đang thêm chữ sáng… 25%" }, 3000)
            server.wordTimings = {state: "running", lines: 120, words: 0, done: 60, total: 120}
            tryVerify(function() { return textOf(dlg, "wordTimingsNote") === "Đang thêm chữ sáng… 50%" }, 4000)
            both("export_words", page)
            pickKind(dlg, "mp3")
            tryVerify(function() { return !has(dlg, "wordTimings") || !shown(one(dlg, "wordTimings")) }, 3000)
        }
        function test_wordTimingsLogicNotesAndDisabledRule() {
            compare(Export.wordTimingsNote(null), "Thêm chữ sáng theo giọng đọc, chạy nền vài phút.")
            compare(Export.wordTimingsNote({state: "error", error: "Hết bộ nhớ"}), "Hết bộ nhớ")
            compare(Export.wordTimingsNote({state: "done", file: "x.abook", lines: 3, words: 3}), "Xong - file sách của dự án đã được làm lại kèm chữ sáng theo giọng đọc.")
            compare(Export.wordTimingsNote({state: "idle", lines: 1200, words: 1100}), "1.100/1.200 câu đã có chữ sáng theo giọng đọc.")
            compare(Export.wordTimingsDisabled({state: "idle", lines: 3, words: 3}, false), true)
            compare(Export.wordTimingsDisabled({state: "idle", lines: 3, words: 1}, false), false)
            compare(Export.wordTimingsDisabled({state: "idle", lines: 3, words: 1}, true), true)
        }

        function test_peerExportRoutesThroughThePeerAndSendsNoFolderDialog() {
            serve()
            const row = book("a")
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn phòng làm việc"}}})
            reply("GET " + peerBase + "/api/library", library([row]))
            reply("GET " + peerBase + base, {status: 200, data: {book: row, chapters: [chapter(1)]}})
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            screenOf(page).dialogs.perform("export", row)
            tryVerify(function() { return exportDlg(page) !== undefined }, 3000)
            const dlg = exportDlg(page)
            // dự án gói ở máy tính, không gói từ máy xem
            verify(!has(dlg, "exportKind_abookproj"))
            verify(hasPart(dlg, "file nằm ở máy tính, không tải về máy này."))
            compare(one(dlg, "confirm_go").text, "Xuất")
            pickKind(dlg, "abook")
            tryVerify(function() { return has(dlg, "onComputerText") && one(dlg, "onComputerText").text === "Chữ sáng theo giọng ở máy tính Máy bàn phòng làm việc" }, 3000)
            goExport(dlg)
            tryVerify(function() { return calls("POST", peerBase + base + "/bookfile-job").length === 1 }, 3000)
            compare(calls("POST", peerBase + base + "/bookfile-job")[0].body, {target: "", series: false})
            compare(DesktopApi.folders.length, 0)
            stepJob("bookfile-job", {state: "done", result: {file: "Cuốn a.abook", folder: "Đã xuất", size: 5000000}})
            tryCompare(dlg, "phase", "finished", 4000)
            compare(one(dlg, "exportDoneTitle").text, "Đã xuất file sách")
            compare(one(dlg, "exportDoneDetail").text, "Đã xuất vào máy tính Máy bàn phòng làm việc: Cuốn a.abook · 4,8 MB")
            verify(!has(dlg, "confirm_reveal"))
            // KHÔNG một lời gọi nào đi thẳng vào máy này
            const direct = DesktopApi.requests.filter(r => (/^\/api\/books\/a\//).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct.slice(0, 3)))
            compare(calls("POST", "/api/reveal-export").length, 0)
        }
        function test_longTextWrapsInTheExportDialogAtBothWidths() {
            const lengthy = longText()
            serve({history: [{kind: "mp3", target: "D:\\Đã xuất\\" + lengthy, chapters: {}, changed: [1]}]})
            for (const width of [1024, 1920]) {
                const page = openExport(book("a", {title: lengthy, pendingChanges: 2, chapters: {total: 4, completed: 3, redo: 1, missingAudio: 1, failed: 0, working: 0}, running: true}), width)
                const dlg = exportDlg(page)
                tryVerify(function() { return has(dlg, "exportStale") && has(dlg, "exportPending") }, 3000)
                noCut(dlg)
                shot("export_long_" + width, page)
                pickKind(dlg, "abookproj")
                noCut(dlg)
                page.destroy()
                Nav.layers = []
            }
        }
        function test_longFinishedPathAndFailureWrapAtBothWidths() {
            const lengthy = longText()
            serve()
            for (const width of [1024, 1920]) {
                const page = openExport(null, width)
                const dlg = exportDlg(page)
                pickKind(dlg, "abook")
                goExport(dlg)
                tryCompare(dlg, "phase", "busy", 3000)
                stepJob("bookfile-job", {state: "done", result: {file: "D:\\Đã xuất\\" + lengthy + ".abook", folder: "D:\\Đã xuất", size: 5000000, missingSources: ["a", "b"]}})
                tryCompare(dlg, "phase", "finished", 4000)
                tryVerify(function() { return has(dlg, "exportDoneNote") }, 3000)
                noCut(dlg)
                shot("export_done_long_" + width, page)
                page.destroy()
                Nav.layers = []
                DesktopApi.folders = []
                server.jobs["bookfile-job"] = {state: "idle"}
            }
        }

        // ================= C. hộp Áp dụng =================
        function openApply(b, width) {
            const row = b || book("a", {pendingChanges: 3})
            const page = openProject(width, row)
            screenOf(page).dialogs.perform("apply", row)
            tryVerify(function() { return applyDlg(page) !== undefined }, 3000)
            tryVerify(function() { return has(applyDlg(page), "pendingRow") }, 3000)
            return page
        }
        function test_applyListsEveryChangeAndSaysWhatIsRecordedAndHowLong() {
            serve()
            const page = openApply()
            const dlg = applyDlg(page)
            compare(dlg.title, "Áp dụng 3 thay đổi?")
            compare(dlg.description, "Máy chỉ thu lại những câu bị ảnh hưởng, rồi dựng lại các chương có câu ấy - không làm lại cả cuốn.")
            tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 3 }, 3000)
            verify(hasText(dlg, "“Lucien” đọc là “lu-xi-ăng”"))
            verify(hasText(dlg, "“Đi thôi,” - Natasha · Chương 2 · từ Máy bàn"))
            verify(hasText(dlg, "4 câu thu lại") && hasText(dlg, "1 câu thu lại") && hasText(dlg, "chưa thu - không tốn gì"))
            compare(one(dlg, "applySummary").text, "Thu lại 5 câu ở 2 chương (Chương 1, Chương 2) - khoảng 3 phút trên máy này.")
            compare(one(dlg, "confirm_later").text, "Để sau")
            compare(one(dlg, "confirm_go").text, "Áp dụng")
            const names = all(dlg, "pendingDrop").filter(shown).map(b => b.Accessible.name)
            compare(names, ["Bỏ cách đọc “Lucien”", "Bỏ đổi người nói: “Đi thôi,” - Natasha", "Bỏ đổi giọng: Lan đổi sang giọng Hương"])
            noCut(dlg)
            both("apply_list", page)
        }
        function test_applyGoStartsTheBookAfterClosing() {
            serve()
            reply("POST " + base + "/start", {status: 200, data: {}})
            const page = openApply()
            const dlg = applyDlg(page)
            tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 3 }, 3000)
            compare(calls("POST", base + "/start").length, 0)
            dlg.chosen("go")
            tryVerify(function() { return calls("POST", base + "/start").length === 1 }, 3000)
            tryVerify(function() { return !dlg.open }, 3000)
        }
        function test_applyDropWithdrawsOneChangeAndTheListShrinks() {
            serve()
            const page = openApply()
            const dlg = applyDlg(page)
            tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 3 }, 3000)
            all(dlg, "pendingDrop").filter(shown)[1].clicked()
            tryVerify(function() { return calls("POST", base + "/pending-changes/withdraw").length === 1 }, 3000)
            const body = calls("POST", base + "/pending-changes/withdraw")[0].body
            compare(body.section, "speakers")
            compare(body.key, "c2s4")
            compare(body.requestedAt, 2)
            tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 2 }, 4000)
            verify(!hasText(dlg, "“Đi thôi,” - Natasha · Chương 2 · từ Máy bàn"))
        }
        function test_applyDropOfTheLastOneClosesTheDialog() {
            serve({pending: pendingFixture({items: [pendingFixture().items[0]], lines: 4, chapters: ["Chương 1"]})})
            const page = openApply(book("a", {pendingChanges: 1}))
            const dlg = applyDlg(page)
            tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 1 }, 3000)
            all(dlg, "pendingDrop").filter(shown)[0].clicked()
            tryVerify(function() { return !dlg.open }, 3000)
        }
        function test_applyWithoutRecordedLinesSaysNothingIsRecorded() {
            serve({pending: pendingFixture({lines: 0, chapters: [], seconds: 0})})
            const page = openApply()
            tryVerify(function() { return one(applyDlg(page), "applySummary").text === "Chỉ ghi thay đổi, không thu lại câu nào." }, 3000)
        }
        function test_applyWhileTheBookRunsIsLockedToViewingAndDropping() {
            serve()
            const page = openApply(book("a", {pendingChanges: 3, running: true, phase: "synthesizing", statusLabel: "Đang thu"}))
            const dlg = applyDlg(page)
            compare(dlg.title, "3 thay đổi đang chờ áp")
            compare(dlg.description, "Tự áp ở chương kế tiếp; chỉ bỏ được việc chưa áp.")
            compare(one(dlg, "confirm_later").text, "Đóng")
            verify(!has(dlg, "confirm_go"))
            tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 3 }, 3000)
            for (const drop of all(dlg, "pendingDrop").filter(shown)) verify(drop.enabled)
            both("apply_locked", page)
        }
        function test_applyTriesAPendingVoiceOnALineOfTheSameCharacter() {
            serve()
            const page = openApply()
            const dlg = applyDlg(page)
            tryVerify(function() { return has(dlg, "pendingTry") }, 3000)
            compare(all(dlg, "pendingTry").filter(shown).length, 1)
            all(dlg, "pendingTry").filter(shown)[0].clicked()
            tryVerify(function() { return calls("POST", base + "/voice/preview").length === 1 }, 3000)
            compare(calls("POST", base + "/voice/preview")[0].body, {character: "Lan", preset: "huong"})
            tryVerify(function() { return DesktopApi.previews.length === 1 }, 3000)
            compare(DesktopApi.previews[0], "/media/previews/p1.wav")
            tryVerify(function() { return hasPart(dlg, "Anh đi đâu thế?") }, 3000)
        }
        function test_applyPeerRoutesThroughThePeer() {
            serve()
            const row = book("a", {pendingChanges: 3})
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn"}}})
            reply("GET " + peerBase + "/api/library", library([row]))
            reply("GET " + peerBase + base, {status: 200, data: {book: row, chapters: [chapter(1)]}})
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            screenOf(page).dialogs.perform("apply", row)
            tryVerify(function() { return applyDlg(page) !== undefined && all(applyDlg(page), "pendingRow").filter(shown).length === 3 }, 3000)
            all(applyDlg(page), "pendingDrop").filter(shown)[0].clicked()
            tryVerify(function() { return calls("POST", peerBase + base + "/pending-changes/withdraw").length === 1 }, 3000)
            all(applyDlg(page), "pendingTry").filter(shown)[0].clicked()
            tryVerify(function() { return calls("POST", peerBase + base + "/voice/preview").length === 1 }, 3000)
            const direct = DesktopApi.requests.filter(r => (/^\/api\/books\/a\//).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct.slice(0, 3)))
        }
        function test_longTextWrapsInTheApplyDialogAtBothWidths() {
            const lengthy = longText()
            const items = pendingFixture().items.map(i => Object.assign({}, i, {label: i.label + " " + lengthy, chapter: "Chương 12 " + lengthy.slice(0, 60)}))
            serve({pending: pendingFixture({items: items, chapters: ["Chương 1 " + lengthy.slice(0, 40), "Chương 2", "Chương 3", "Chương 4", "Chương 5", "Chương 6"]})})
            for (const width of [1024, 1920]) {
                const page = openApply(null, width)
                const dlg = applyDlg(page)
                tryVerify(function() { return all(dlg, "pendingRow").filter(shown).length === 3 }, 3000)
                tryVerify(function() { return hasPart(dlg, "và 2 chương khác") }, 3000)
                noCut(dlg)
                shot("apply_long_" + width, page)
                page.destroy()
                Nav.layers = []
            }
        }
        function test_applyLogicShowsAtMostFourChaptersThenCountsTheRest() {
            compare(Export.shownChapters(["a", "b", "c", "d"]), "a, b, c, d")
            compare(Export.shownChapters(["a", "b", "c", "d", "e", "f"]), "a, b, c, d, và 2 chương khác")
            compare(Export.applyHeading(2, false), "Áp dụng 2 thay đổi?")
            compare(Export.applyHeading(2, true), "2 thay đổi đang chờ áp")
            compare(Export.applyClose(true), "Đóng")
            compare(Export.applyClose(false), "Để sau")
            compare(Export.applyRunning({running: true, paused: "listener", status: "paused"}), "checkpoint")
            compare(Export.applyRunning({running: true}), "busy")
            compare(Export.applyRunning({running: false}), "")
        }

        // ================= D. khung Lỗi chương =================
        function test_chapterErrorOpensWithTheNextStepAndTheRawText() {
            serve()
            const chapters = [chapter(1), chapter(2, {status: "failed", statusLabel: "Lỗi", lastError: "RuntimeError: CUDA out of memory. Tried to allocate 2.00 GiB", playable: false, completedAt: null})]
            const page = openProject(1280, book("a", {chapters: {total: 2, completed: 1, redo: 0, missingAudio: 0, failed: 1, working: 0}}), chapters)
            tryVerify(function() { return has(page, "chapterErrorMore") }, 3000)
            verify(hasText(page, "Card đồ hoạ hết bộ nhớ."))
            one(page, "chapterErrorMore").clicked()
            tryVerify(function() { return has(page, "chapterError") && shown(one(page, "chapterError")) }, 3000)
            verify(one(page, "chapterErrorHint").text.indexOf("bấm Tiếp tục") >= 0)
            verify(one(page, "chapterErrorDetail").text.indexOf("CUDA out of memory") >= 0)
            both("chapter_error", page)
            Nav.back()
            tryVerify(function() { return !shown(one(page, "chapterError")) }, 3000)
        }
        function test_chapterErrorLongRawTextWrapsAtBothWidths() {
            serve()
            const raw = "RuntimeError: " + longText() + longText()
            const chapters = [chapter(1, {status: "failed", statusLabel: "Lỗi", lastError: raw, playable: false, completedAt: null})]
            for (const width of [1024, 1920]) {
                const page = openProject(width, book("a", {chapters: {total: 1, completed: 0, redo: 0, missingAudio: 0, failed: 1, working: 0}}), chapters)
                tryVerify(function() { return has(page, "chapterErrorMore") }, 3000)
                one(page, "chapterErrorMore").clicked()
                tryVerify(function() { return has(page, "chapterError") && shown(one(page, "chapterError")) }, 3000)
                noCut(page)
                shot("chapter_error_long_" + width, page)
                page.destroy()
                Nav.layers = []
            }
        }
    }
}
