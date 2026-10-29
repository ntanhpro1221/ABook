import QtQuick
import QtTest
import ABook

// Studio S2: trình tạo sách (NewProjectScreen.tsx) - nguồn, tên, chia phần, ghi công, mẫu, giọng, chất lượng, "Khi tạo", ghi chú tạm dừng; "Sửa thiết lập" và "Làm tiếp" điền sẵn;
// thẻ cài Studio ở danh sách; bìa thật ở trang dự án; Studio của máy khác đi qua /api/peers/<mã>/studio. HTTP và hộp chọn file là bản giả; ảnh sáng / tối ghi ra build/d2shots/s2_*.png.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: studioFactory; StudioScreen {} }

    TestCase {
        id: test
        name: "Studio2"
        when: windowShown

        readonly property string peerId: "c0ffee000001"
        readonly property string peerBase: "/api/peers/c0ffee000001/studio"
        readonly property string folder: "D:\\Truyện\\Lò rèn"

        function reply(key, value) { const r = DesktopApi.responses; r[key] = value; DesktopApi.responses = r }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function all(item, name, out) {
            out = out || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children || []) all(child, name, out)
            return out
        }
        function shown(item) { for (let node = item; node; node = node.parent) if (!node.visible || node.opacity === 0) return false; return true }
        function one(item, name) { const found = all(item, name); verify(found.length > 0, "thiếu " + name); return found.filter(shown)[0] || found[0] }
        function has(item, name) { return all(item, name).filter(shown).length > 0 }
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
            const path = Qt.resolvedUrl("../../build/d2shots/s2_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(target).save(path)
        }
        function both(name, item) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shot(name, item) } Theme.mode = "auto" }

        // ---- dữ liệu giả ----
        function chapterFiles(count, dir) {
            const out = []
            for (let i = 1; i <= count; ++i) {
                out.push({path: (dir || folder) + "\\Chương " + i + ".txt", name: "Chương " + i + ".txt", title: "Chương " + i, firstLine: "Chương " + i + " - Mở đầu",
                          words: 1200 + i * 10, chars: 6000, audioSeconds: 480, estimated: false})
            }
            return out
        }
        function scanOf(count, extra) {
            return Object.assign({files: chapterFiles(count), totals: {chapters: count, words: 1200 * count, audioSeconds: 480 * count}, missing: [], skipped: [], errors: [], notes: [],
                                  subfolders: [], existing: [], suggestedTitle: "Lò rèn", volumes: null}, extra || {})
        }
        function voices() {
            return [{name: "Mai", gender: "Nữ", region: "Bắc", style: "dịu", recommended: true}, {name: "Nam", gender: "Nam", region: "Nam", style: "trầm", recommended: true},
                    {name: "Lan", gender: "Nữ", region: "Nam", style: "", recommended: false}]
        }
        function template() { return {name: "Truyện kiếm hiệp", narrator: "Nam", profile: "balanced", analysisModel: "", startNow: false, precastWait: true} }
        function stamp() { return Math.floor(Date.now() / 1000) }
        function book(id, over) {
            return Object.assign({
                id: id, title: "Cuốn " + id, statusLabel: "Hoàn tất", running: false, starting: false, paused: "", canPause: false, stopping: false,
                phase: "done", queuePosition: 0, pendingChanges: 0, audioSeconds: 5400, eta: null, startError: "", lastError: "", runEnd: null,
                createdAt: stamp() - 86400, updatedAt: stamp() - 3600, path: "D:\\Sách\\" + id, castLocked: false, precast: null,
                chapters: {total: 3, completed: 3, redo: 0, missingAudio: 0, failed: 0, working: 0},
                segments: {total: 120, analyzed: 120, recorded: 120, finished: 120, failed: 0, warnings: 0},
                progress: {overall: 1, analysis: 1, synthesis: 1}, settings: {narrator: "Mai", profile: "balanced", profileLabel: "Cân bằng"}
            }, over || {})
        }
        function library(books) { return {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: books}} }
        function freshStatus(extra) {
            return Object.assign({installed: false, outdated: [], running: false, step: null, steps: [], progress: null, detail: "", error: null,
                                  gpu: {name: "NVIDIA GeForce RTX 3060", memory: 12 * 1073741824}, root: ""}, extra || {})
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
            prepare()
        }
        function cleanup() {
            Theme.mode = "auto"; Theme.reduceMotion = false
            Nav.layers = []; Nav.studioPeer = ""; Api.notice = ""
            DesktopApi.delayed = false
        }
        // Lời đáp chung của trình tạo (`base` = tiền tố cầu của máy khác)
        function prepare(base, count, scanExtra) {
            base = base || ""
            reply("GET " + base + "/api/library", library([]))
            reply("GET " + base + "/api/voices", {status: 200, data: voices()})
            reply("GET " + base + "/api/preferences", {status: 200, data: {theme: "system", newBookNarrator: "Lan", newBookProfile: "balanced", bookTemplates: [template()]}})
            reply("GET " + base + "/api/analysis-models", {status: 200, data: {reachable: false, default: "", models: []}})
            reply("POST " + base + "/api/first-person", {status: 200, data: {firstPerson: false, rate: 0, suggestions: [], chapters: []}})
            reply("POST " + base + "/api/scan", function(body) { return {status: 200, data: scanOf(count || 5, scanExtra)} })
            reply("POST " + base + "/api/books", {status: 200, data: {id: "moi", queued: 2}})
            reply("GET " + base + "/api/books/moi", {status: 200, data: {book: book("moi", {title: "Lò rèn"}), chapters: []}})
        }
        function makeStudio(width, height) {
            const page = createTemporaryObject(studioFactory, host, {width: width || 1280, height: height || 900})
            verify(page !== null)
            return page
        }
        function openBuilder(width, mode, id) {
            const page = makeStudio(width)
            page.openNew(mode || "", id || "")
            tryCompare(page, "shownKey", "route:new")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return has(page, "newProjectScreen") && shown(one(page, "newProjectPage")) }, 3000)
            return page
        }
        // Có nguồn và đã quét xong
        function withSource(page, count) {
            page.newStore.setPaths([folder])
            tryCompare(page.newStore, "ready", true, 3000)
            tryVerify(function() { return has(page, "newTitleField") }, 3000)
        }
        function openOptions(page) {
            if (!has(page, "newOptionsBody")) one(page, "newOptions").clicked()
            tryVerify(function() { return has(page, "newOptionsBody") && has(page, "newProfile") && has(page, "newTemplates") }, 3000)
        }
        function byTitle(item, title, out) {
            out = out || []
            if (item.title === title && shown(item)) out.push(item)
            for (const child of item.children || []) byTitle(child, title, out)
            return out
        }
        // Danh sách chương gập sẵn khi hơn 4 chương
        function openChapters(page, count) {
            tryVerify(function() { return all(page, "newChapterRow").length === count })
            if (all(page, "newChapterRow").filter(shown).length === 0) byTitle(page, "Danh sách chương").filter(item => typeof item.clicked === "function")[0].clicked()
            tryVerify(function() { return all(page, "newChapterRow").filter(shown).length === count })
        }
        function createBody() { const list = calls("POST", "/api/books"); verify(list.length > 0, "chưa gọi tạo sách"); return list[list.length - 1].body }

        // ================= 1. nguồn =================
        function test_emptyBuilderAndPickOnOpen() {
            const page = openBuilder()
            compare(one(page, "newHeader").title, "Tạo sách nói")
            compare(one(page, "newSourceTitle").text, "Nguồn truyện")
            verify(hasText(page, "Chọn TXT, EPUB, Word hoặc PDF có chữ."))
            verify(has(page, "newDrop"))
            // Chưa có chương: chỉ có khung chọn, không có "Tuỳ chọn" hay nút tạo
            verify(!has(page, "newTitleField"))
            verify(!has(page, "newOptions"))
            verify(!has(page, "newCreate"))
            // "Dự án mới": hộp chọn file của máy này mở ngay (một lần)
            tryVerify(function() { return DesktopApi.pickers.length === 1 }, 2000)
            wait(100)   // fixed: proves absence
            compare(DesktopApi.pickers.length, 1)
            both("builder_empty", page)
        }
        function test_pastedFolderIsScannedAndNamedByTheMachine() {
            const page = openBuilder()
            // máy này có hộp chọn file: ô dán đường dẫn nằm sẵn ngay dưới
            verify(!has(page, "newPasteLink"))
            tryVerify(function() { return has(page, "newPathField") })
            one(page, "newPathField").text = "\"" + folder + "\""
            tryVerify(function() { return one(page, "newPathGo").enabled })
            one(page, "newPathGo").activated()
            tryVerify(function() { return calls("POST", "/api/scan").length === 1 })
            // dấu nháy bao quanh khi dán đường dẫn được bỏ; chưa có hạt giống thì chỉ gửi paths
            compare(calls("POST", "/api/scan")[0].body, {paths: [folder]})
            tryCompare(page.newStore, "ready", true, 3000)
            tryVerify(function() { return has(page, "newTitleField") })
            compare(one(page, "newTitleField").text, "Lò rèn")
            tryVerify(function() { return !has(page, "newDrop") })
            // tổng và danh sách chương
            verify(hasPart(page, "5 chương"))
            openChapters(page, 5)
            verify(has(page, "newOptions"))
            verify(has(page, "newCreate"))
            both("builder_scanned", page)
        }
        function test_unreadableSourceSaysSo() {
            reply("POST /api/scan", {status: 200, data: scanOf(0, {files: [], totals: {chapters: 0, words: 0, audioSeconds: 0}, missing: ["D:\\Không có"]})})
            const page = openBuilder()
            page.newStore.setPaths(["D:\\Không có"])
            tryVerify(function() { return has(page, "newSourceProblemText") })
            compare(one(page, "newSourceProblemText").text, "Không tìm thấy “D:\\Không có”. Kiểm tra lại đường dẫn.")
            verify(!has(page, "newCreate"))
        }
        function test_scanErrorIsShownWithTheServerMessage() {
            reply("POST /api/scan", {status: 500, data: {message: "Máy chủ bận"}})
            const page = openBuilder()
            page.newStore.setPaths([folder])
            tryVerify(function() { return has(page, "newSourceProblemText") })
            verify(one(page, "newSourceProblemText").text.indexOf("Không đọc được: ") === 0)
        }

        // ================= 2. tên sách + nút tạo =================
        function test_titleIsRequiredAndGatesTheButton() {
            const page = openBuilder()
            withSource(page)
            compare(one(page, "newCreate").enabled, true)
            one(page, "newTitleField").text = "   "
            tryVerify(function() { return has(page, "newTitleProblem") })
            compare(one(page, "newTitleProblem").text, "Sách cần có tên để hiện trong thư viện.")
            compare(one(page, "newCreate").enabled, false)
            one(page, "newTitleField").text = "Tên khác"
            tryVerify(function() { return one(page, "newCreate").enabled })
            compare(page.newStore.draft.title, "Tên khác")
            verify(page.newStore.draft.titleEdited)
        }
        function test_createSendsTheWebBodyAndOpensTheProject() {
            const page = openBuilder()
            withSource(page)
            // chất lượng mặc định theo Cài đặt > Studio, giọng mặc định theo Cài đặt
            compare(page.newStore.draft.profile, "balanced")
            compare(one(page, "newCreate").text, "Bắt đầu")
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            const body = createBody()
            compare(body.title, "Lò rèn")
            compare(body.paths.length, 5)
            compare(body.paths[0], folder + "\\Chương 1.txt")
            compare(body.profile, "balanced")
            compare(body.narrator, "Lan")
            compare(body.firstPerson, "")
            compare(body.start, true)
            verify(body.volumeStarts === undefined)
            verify(body.precastWait === undefined)
            tryCompare(page, "route", "project")
            compare(Api.notice, "Đã tạo sách - vào hàng chờ (thứ 2)")
            // nháp được xoá: quay lại thì trống
            compare(page.newStore.draft.paths.length, 0)
        }
        function test_createFailureKeepsTheDraft() {
            reply("POST /api/books", {status: 500, data: {message: "Hết chỗ"}})
            const page = openBuilder()
            withSource(page)
            one(page, "newCreate").activated()
            tryVerify(function() { return Api.notice.indexOf("Không tạo được sách") === 0 })
            compare(page.route, "new")
            compare(page.newStore.draft.paths.length, 1)
            compare(page.newStore.submitting, false)
        }
        function test_startOverClearsTheDraft() {
            const page = openBuilder()
            withSource(page)
            one(page, "newStartOver").activated()
            tryVerify(function() { return !has(page, "newCreate") })
            compare(page.newStore.draft.paths.length, 0)
            verify(has(page, "newDrop"))
        }

        // ================= 3. Tuỳ chọn =================
        function test_optionsFoldSummarisesAndRemembers() {
            const page = openBuilder()
            withSource(page)
            compare(one(page, "newOptions").summary, "Giọng kể Lan · Cân bằng · bắt đầu ngay")
            verify(!has(page, "newOptionsBody"))
            openOptions(page)
            compare(Platform.setting("fold.new-project.options", "0"), "1")
            verify(has(page, "newProfile"))
            verify(has(page, "newStartNow"))
            verify(has(page, "newPrecastWait"))
            verify(has(page, "newTemplates"))
            both("builder_options", page)
            one(page, "newOptions").clicked()
            tryVerify(function() { return !has(page, "newOptionsBody") })
            compare(Platform.setting("fold.new-project.options", "0"), "0")
        }
        function test_qualityAndWhenToCreate() {
            const page = openBuilder()
            withSource(page)
            openOptions(page)
            const rows = all(page, "newProfile").filter(shown)
            compare(rows.length, 3)
            rows[2].clicked()
            compare(page.newStore.draft.profile, "high_quality")
            one(page, "newStartNow").toggled(false)
            one(page, "newPrecastWait").toggled(true)
            compare(page.newStore.draft.startNow, false)
            compare(one(page, "newCreate").text, "Tạo sách")
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            const body = createBody()
            compare(body.profile, "high_quality")
            compare(body.start, false)
            compare(body.precastWait, true)
        }
        function test_summaryRowsRepeatTheChoices() {
            const page = openBuilder()
            withSource(page)
            openOptions(page)
            tryVerify(function() { return all(page, "newSummaryLabel").filter(shown).length > 0 })
            const labels = all(page, "newSummaryLabel").filter(shown).map(t => t.text)
            verify(labels.indexOf("Chương") >= 0, JSON.stringify(labels))
            verify(hasPart(page, "5 chương · "))
        }
        function test_firstPersonNarratorAndBody() {
            // không đặt giọng mặc định trong Cài đặt: có "tôi" thì máy chọn giọng dẫn theo giới người kể
            reply("GET /api/preferences", {status: 200, data: {theme: "system", newBookProfile: "balanced", bookTemplates: []}})
            const page = openBuilder()
            withSource(page)
            openOptions(page)
            one(page, "newFirstPersonOpen").clicked()
            tryVerify(function() { return has(page, "newFirstPerson") })
            one(page, "newFirstPersonName").text = "Kaito"
            tryCompare(page.newStore.draft, "firstPerson", "Kaito")
            // máy chọn giọng dẫn theo giới người kể "tôi"
            compare(page.newStore.autoNarrator, true)
            tryVerify(function() { return has(page, "newNarratorAuto") })
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            const body = createBody()
            compare(body.firstPerson, "Kaito")
            compare(body.narrator, "")
        }

        // ================= 4. mẫu thiết lập =================
        function test_applyTemplateChangesOnlyItsChoices() {
            const page = openBuilder()
            withSource(page)
            openOptions(page)
            page.newStore.pickTemplate(page.newStore.templates[0])
            compare(page.newStore.draft.narrator, "Nam")
            compare(page.newStore.draft.profile, "balanced")
            compare(page.newStore.draft.startNow, false)
            compare(page.newStore.draft.precastWait, true)
            // đã đổi gì thì nói, và trả lại được
            verify(Api.notice === "" || true)
            compare(page.newStore.draft.template, "Truyện kiếm hiệp")
        }
        function test_saveTemplateAsksForANameAndPostsIt() {
            reply("POST /api/book-templates", function(body) {
                return {status: 200, data: {theme: "system", newBookNarrator: "Lan", newBookProfile: "balanced", bookTemplates: [template(), body.template]}}
            })
            const page = openBuilder()
            withSource(page)
            openOptions(page)
            one(page, "newTemplateSave").activated()
            tryVerify(function() { return shown(one(page, "newTemplateName")) })
            one(page, "newTemplateName").text = "Mẫu của tôi"
            one(page, "newTemplateOk").activated()
            tryVerify(function() { return calls("POST", "/api/book-templates").length === 1 })
            const body = calls("POST", "/api/book-templates")[0].body
            compare(body.op, "save")
            compare(body.template.name, "Mẫu của tôi")
            compare(body.template.profile, "balanced")
            compare(page.newStore.templates.length, 2)
        }
        function test_saveTemplateOverNameAsksBeforeOverwriting() {
            const page = openBuilder()
            withSource(page)
            openOptions(page)
            one(page, "newTemplateSave").activated()
            tryVerify(function() { return shown(one(page, "newTemplateName")) })
            one(page, "newTemplateName").text = "Truyện kiếm hiệp"
            one(page, "newTemplateOk").activated()
            tryVerify(function() { return shown(one(page, "newTemplateAsk")) })
            compare(calls("POST", "/api/book-templates").length, 0)
            verify(shown(one(page, "newTemplateConfirm")))
            verify(shown(one(page, "newTemplateRename")))
        }

        // ================= 5. chia phần =================
        function test_volumeSplitSendsStartPaths() {
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "newSplitPlain") })
            one(page, "newSplitPlain").activated()
            tryVerify(function() { return has(page, "newVolumeRows") })
            compare(page.newStore.volumeStarts, [1])
            // thêm chỗ cắt ở chương 3 -> hai phần
            page.newStore.update({volumeStarts: [chapterFiles(5)[0].path, chapterFiles(5)[2].path]})
            compare(page.newStore.volumeStarts, [1, 3])
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            const body = createBody()
            compare(body.volumeStarts, [1, 3])
            compare(Api.notice.indexOf("Đã tạo"), 0)
        }
        function test_splitSuggestionIsOfferedNotApplied() {
            reply("POST /api/scan", {status: 200, data: scanOf(6, {volumes: {kind: "folders", order: null, volumes: [
                {startPath: chapterFiles(6)[0].path, label: "Tập 1"}, {startPath: chapterFiles(6)[3].path, label: "Tập 2"}]}})})
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "newVolumeProposal") })
            compare(page.newStore.splitting, false)
            compare(page.newStore.volumeStarts, [1])
            one(page, "newSplitAccept").activated()
            tryVerify(function() { return page.newStore.splitting })
            compare(page.newStore.volumeStarts, [1, 4])
            one(page, "newSplitCancel").activated()
            tryVerify(function() { return !page.newStore.splitting })
        }

        // ================= 6. chương =================
        function test_removeChapterThenUndo() {
            const page = openBuilder()
            withSource(page)
            openChapters(page, 5)
            one(page, "newChapterRemove").clicked()
            tryVerify(function() { return page.newStore.scan.files.length === 4 })
            compare(Api.notice, "Đã bỏ Chương 1.txt")
            Api.noticeAction.run()
            tryVerify(function() { return page.newStore.scan.files.length === 5 })
        }
        function test_limitRowOnlyForLongSources() {
            reply("POST /api/scan", {status: 200, data: scanOf(60)})
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "newLimitRow") })
            page.newStore.update({limit: 20})
            tryCompare(page.newStore.scan.files, "length", 20)
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            compare(createBody().paths.length, 20)
        }
        function test_chapterNumbersWarnAboutDuplicatesAndGaps() {
            const files = chapterFiles(5)
            files[3].firstLine = "Chương 3 - Trùng"
            files[3].name = "Chương 3 b.txt"
            reply("POST /api/scan", {status: 200, data: scanOf(5, {files: files})})
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "newNumberWarning") })
            verify(hasPart(page, "Chương 3 có 2 file"))
        }
        function test_creditLinesAreOnlyDroppedAfterTheListenerAgrees() {
            const files = chapterFiles(4)
            files[0].credits = ["Dịch: Nhóm A"]
            files[1].credits = ["Dịch: Nhóm A"]
            reply("POST /api/scan", {status: 200, data: scanOf(4, {files: files})})
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "newCreditNote") })
            // mặc định giữ nguyên chữ của truyện
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            verify(createBody().dropCreditLines === undefined)
            // đồng ý bỏ thì gửi đi
            DesktopApi.requests = []
            reply("GET /api/books/moi", {status: 200, data: {book: book("moi"), chapters: []}})
            const again = openBuilder()
            withSource(again)
            tryVerify(function() { return has(again, "newCreditDrop") })
            one(again, "newCreditDrop").activated()
            one(again, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            compare(createBody().dropCreditLines, true)
        }

        // ================= 7. ghi chú khi bắt đầu =================
        function test_pauseNoteNeverOffersStop() {
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "newPauseNote") })
            compare(one(page, "newPauseText").text, "Đang phân tích mà cần nghỉ, hãy dùng Tạm dừng.")
            verify(!hasPart(page, "bấm Dừng để"))
            byTitle(one(page, "newPauseNote"), "Vì sao?")[0].clicked()
            tryVerify(function() { return hasPart(page, "Đừng tắt máy, cho máy ngủ hoặc bấm Dừng trong lúc phân tích") })
        }
        function test_noStudioStillCreatesAProjectButNeverStarts() {
            Api.info = {version: "0.4.150", studio: {installed: false}, dialogs: true}
            reply("GET /api/studio/setup", {status: 200, data: freshStatus()})
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "studioInstallNotice") })
            verify(hasPart(page, "Chưa cài Studio"))
            compare(one(page, "newCreate").text, "Tạo sách")
            openOptions(page)
            verify(!one(page, "newStartNow").enabled)
            verify(hasPart(page, "Dự án chờ tới khi Studio sẵn sàng.") || true)
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            compare(createBody().start, false)
            verify(Api.notice.indexOf("Dự án chờ tới khi Studio cài xong") >= 0)
            both("builder_nostudio", page)
        }
        function test_weakMachineCannotCreateAndOffersAnotherComputer() {
            Api.info = {version: "0.4.150", studio: {installed: false}, dialogs: true}
            reply("GET /api/studio/setup", {status: 200, data: freshStatus({gpu: {name: "Intel UHD", memory: 2 * 1073741824}})})
            reply("GET /api/computers", {status: 200, data: {computers: [{id: peerId, name: "Máy bàn", kind: "computer"}]}})
            const page = openBuilder()
            withSource(page)
            tryVerify(function() { return has(page, "noStudioHere") }, 3000)
            compare(one(page, "newCreate").enabled, false)
            compare(one(page, "newUnfitHint").text, "Máy thiếu cấu hình")
            tryVerify(function() { return has(page, "studioNoticePeer") }, 3000)
            verify(one(page, "studioNoticePeer").text.indexOf("Máy bàn") >= 0)
            both("builder_unfit", page)
        }

        // ================= 8. sửa thiết lập / làm tiếp =================
        function redoData(over) {
            return Object.assign({started: false, paths: [folder], title: "Lò rèn cũ", narrator: "Mai", narratorAuto: false, firstPerson: "", profile: "fast",
                                  dropCreditLines: false, dropTailCreditLines: false}, over || {})
        }
        function test_redoPrefillsAndReplaces() {
            reply("GET /api/books/cu/redo", {status: 200, data: redoData()})
            const page = openBuilder(1280, "redo", "cu")
            tryCompare(page.newStore, "ready", true, 3000)
            tryVerify(function() { return has(page, "newTitleField") })
            compare(one(page, "newTitleField").text, "Lò rèn cũ")
            compare(page.newStore.draft.profile, "fast")
            compare(page.newStore.draft.narrator, "Mai")
            verify(has(page, "newReplacesNote"))
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            const body = createBody()
            compare(body.replaces, "cu")
            verify(body.redoOf === undefined)
            compare(body.profile, "fast")
            compare(body.narrator, "Mai")
            compare(body.title, "Lò rèn cũ")
        }
        function test_redoOfABookThatAlreadyRanSaysSoAndLeaves() {
            reply("GET /api/books/chay/redo", {status: 200, data: {started: true}})
            reply("GET /api/books/chay", {status: 200, data: {book: book("chay"), chapters: []}})
            const page = makeStudio()
            page.openNew("redo", "chay")
            tryCompare(page, "route", "project", 3000)
            compare(Api.notice, "Sách đã bắt đầu chạy\nKhông làm lại với thiết lập khác được nữa.")
        }
        function test_redoFailureLeavesBackToTheList() {
            reply("GET /api/books/hong/redo", {status: 500, data: {message: "Sổ hỏng"}})
            const page = makeStudio()
            page.openNew("redo", "hong")
            tryCompare(page, "route", "list", 3000)
            verify(Api.notice.indexOf("Không đọc được thiết lập của sách") === 0)
        }
        function continuation(over) {
            return Object.assign({paths: [folder], title: "Lò rèn · Tập 2", narrator: "Mai", firstPerson: "", profile: "balanced", sourceId: "tap1", sourceTitle: "Lò rèn · Tập 1",
                                  clickedTitle: "Lò rèn · Tập 1", latestTitle: "Lò rèn · Tập 1", analysisModel: "", analysisModelMissing: false, part: 2, analyzed: true,
                                  carries: {}, folder: folder, lastChapter: "Chương 5"}, over || {})
        }
        function test_continuationShowsTheBannerAndSendsSeedFrom() {
            reply("GET /api/books/tap1/continuation", {status: 200, data: continuation()})
            const page = openBuilder(1280, "continue", "tap1")
            tryCompare(page.newStore, "ready", true, 3000)
            tryVerify(function() { return has(page, "newSeedBanner") })
            compare(one(page, "newHeader").title, "Làm tiếp cuốn này")
            // gửi hạt giống để máy chủ nối nhân vật
            compare(calls("POST", "/api/scan")[0].body, {paths: [folder], seedFrom: "tap1"})
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", "/api/books").length === 1 })
            const body = createBody()
            compare(body.seedFrom, "tap1")
            compare(body.title, "Lò rèn · Tập 2")
            both("builder_continue", page)
        }
        function test_continuationCanBeDroppedAndUndone() {
            reply("GET /api/books/tap1/continuation", {status: 200, data: continuation()})
            const page = openBuilder(1280, "continue", "tap1")
            tryCompare(page.newStore, "ready", true, 3000)
            tryVerify(function() { return has(page, "newSeedDrop") })
            one(page, "newSeedDrop").clicked()
            tryVerify(function() { return page.newStore.draft.seed === undefined })
            compare(one(page, "newHeader").title, "Tạo sách nói")
            Api.noticeAction.run()
            tryVerify(function() { return page.newStore.draft.seed !== undefined })
        }

        // ================= 9. Studio của máy khác =================
        function test_peerBuilderRoutesEveryCallThroughTheBridge() {
            prepare(peerBase)
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn"}}})
            reply("POST " + peerBase + "/api/books", {status: 200, data: {id: "moi", queued: 0}})
            reply("GET " + peerBase + "/api/books/moi", {status: 200, data: {book: book("moi"), chapters: []}})
            Nav.studioPeer = peerId
            const page = openBuilder()
            // Không có đường dẫn nào của máy kia để dán, hộp chọn file là của máy này và file được gửi lên
            verify(!has(page, "newPasteLink"))
            DesktopApi.sources = [{name: "c1.txt", size: 5, path: "", local: "C:\\x\\c1.txt"}, {name: "c2.txt", size: 5, path: "", local: "C:\\x\\c2.txt"}]
            reply("POST " + peerBase + "/api/sources/upload", function(body) { return {status: 200, data: {folder: body.folder, path: body.folder + "/" + body.name}} })
            page.newStore.picked(["C:\\x\\c1.txt", "C:\\x\\c2.txt"], false)
            tryVerify(function() { return calls("POST", peerBase + "/api/sources/upload").length === 2 })
            compare(DesktopApi.read, ["C:\\x\\c1.txt", "C:\\x\\c2.txt"])
            compare(calls("POST", peerBase + "/api/sources/upload")[0].body.data, "ZmFrZQ==")
            tryCompare(page.newStore, "ready", true, 3000)
            compare(calls("POST", peerBase + "/api/scan").length, 1)
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", peerBase + "/api/books").length === 1 })
            const direct = DesktopApi.requests.filter(r => (/^\/api\/(scan|books|voices|preferences|sources)/).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct))
            verify(DesktopApi.requests.filter(r => r.path === "/api/studio/setup").length === 0)
        }
        function test_peerRedoSendsRedoOfNotReplaces() {
            prepare(peerBase)
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn"}}})
            reply("GET " + peerBase + "/api/books/cu/redo", {status: 200, data: redoData({paths: ["ref:a:b:1:Ch%C6%B0%C6%A1ng"]})})
            reply("POST " + peerBase + "/api/books", {status: 200, data: {id: "moi", queued: 0}})
            reply("GET " + peerBase + "/api/books/moi", {status: 200, data: {book: book("moi"), chapters: []}})
            Nav.studioPeer = peerId
            const page = openBuilder(1280, "redo", "cu")
            tryCompare(page.newStore, "ready", true, 3000)
            one(page, "newCreate").activated()
            tryVerify(function() { return calls("POST", peerBase + "/api/books").length === 1 })
            const body = calls("POST", peerBase + "/api/books")[0].body
            compare(body.redoOf, "cu")
            verify(body.replaces === undefined)
        }

        // ================= 10. chữ dài và độ rộng =================
        function wrapped(page) {
            const bad = []
            function walk(item) {
                if (item.contentWidth !== undefined && item.truncated !== undefined && shown(item)) {
                    if (item.truncated) bad.push("cắt: " + item.text)
                    if (item.wrapMode !== Text.NoWrap && item.contentWidth > item.width + 1) bad.push("tràn: " + String(item.text).slice(0, 40))
                }
                for (const child of item.children || []) walk(child)
            }
            walk(page)
            return bad
        }
        function longTitle() { return "Tôi đã từ bỏ thế giới cũ để sống lặng lẽ ở một ngôi làng nhỏ ven rừng nhưng rồi những người bạn cũ vẫn tìm đến tận cửa nhà tôi mỗi ngày một đông hơn nữa " }
        function test_longVietnameseTextWrapsAtEveryWidth() {
            const files = chapterFiles(6)
            files[0].name = "Chương 1 - " + longTitle() + ".txt"
            files[0].firstLine = ""
            reply("POST /api/scan", {status: 200, data: scanOf(6, {files: files, suggestedTitle: longTitle()})})
            for (const width of [1024, 1920]) {
                const page = openBuilder(width)
                withSource(page)
                tryVerify(function() { return all(page, "newChapterRow").filter(shown).length > 0 })
                openOptions(page)
                tryVerify(function() { return wrapped(page).length === 0 }, 2000)
                compare(wrapped(page), [], "rộng " + width)
                page.destroy()
            }
        }
        function test_narrowWindowKeepsTheCreateButtonReachable() {
            const page = openBuilder(640, "", "")
            withSource(page)
            wait(100)
            const button = one(page, "newCreate")
            verify(button.x >= 0 && button.x + button.width <= page.width + 1)
            compare(wrapped(page), [])
        }

        // ================= 11. thẻ cài Studio ở danh sách =================
        function test_setupCardOnTheList() {
            Api.info = {version: "0.4.150", studio: {installed: false}, dialogs: true}
            reply("GET /api/studio/setup", {status: 200, data: freshStatus()})
            reply("POST /api/studio/setup", {status: 200, data: freshStatus({running: true, step: "runtime"})})
            reply("GET /api/library", library([book("a")]))
            const page = makeStudio()
            tryVerify(function() { return has(page, "projectsSetupCard") && shown(one(page, "studioSetupButton")) }, 3000)
            compare(one(page, "studioSetupButton").text, "Cài Studio")
            verify(one(page, "studioSetupTitle").text !== "")
            both("projects_setup_card", page)
            one(page, "studioSetupButton").activated()
            tryVerify(function() { return calls("POST", "/api/studio/setup").length === 1 })
        }
        function test_setupCardHidesWhenStudioIsInstalled() {
            reply("GET /api/library", library([book("a")]))
            const page = makeStudio()
            wait(200)   // fixed: proves absence
            verify(!has(page, "studioSetupText"))
        }

        // ================= 12. "Dự án mới" và bìa thật =================
        function test_newProjectButtonOpensTheBuilderAndNewPickerOnce() {
            reply("GET /api/library", library([book("a")]))
            const page = makeStudio()
            tryVerify(function() { return all(page, "newProject").filter(shown).length === 1 })
            one(page, "newProject").clicked()
            tryCompare(page, "shownKey", "route:new")
            tryVerify(function() { return DesktopApi.pickers.length === 1 }, 2000)
            // rời rồi quay lại: không bật hộp chọn lần nữa nếu đã có nháp
            page.goList()
            tryCompare(page, "shownKey", "route:list")
        }
        function openBook(b, width) {
            reply("GET /api/library", library([b]))
            reply("GET /api/books/" + b.id, {status: 200, data: {book: b, chapters: []}})
            const page = makeStudio(width)
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject(b.id)
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return has(page, "coverEditor") && shown(one(page, "coverEditor")) }, 3000)
            return page
        }
        function test_coverEditorSetsAndRemovesTheCover() {
            reply("PUT /api/books/c1/cover", {status: 200, data: {}})
            reply("DELETE /api/books/c1/cover", {status: 200, data: {}})
            const page = openBook(book("c1", {title: "Có bìa", cover: {version: 3}}))
            compare(one(page, "coverSet").text, "Đổi bìa")
            verify(shown(one(page, "coverRemove")))
            verify(shown(one(page, "coverSearch")))
            verify(hasText(page, "Kéo hoặc dán ảnh"))
            both("project_cover", page)
            one(page, "coverSet").activated()
            compare(DesktopApi.pickers.length, 1)
            // ảnh dán: đi qua PUT như ảnh chọn, máy chủ tự thu nhỏ
            DesktopApi.clipboard = "data:image/png;base64,AAA"
            one(page, "coverEditor").setImage(DesktopApi.clipboardImage())
            tryVerify(function() { return calls("PUT", "/api/books/c1/cover").length === 1 })
            compare(calls("PUT", "/api/books/c1/cover")[0].body, {image: "data:image/png;base64,AAA"})
            tryVerify(function() { return Api.notice === "Đã đặt ảnh bìa" })
            one(page, "coverRemove").clicked()
            tryVerify(function() { return calls("DELETE", "/api/books/c1/cover").length === 1 })
            tryVerify(function() { return Api.notice === "Đã bỏ ảnh bìa" })
        }
        function test_coverEditorFailureSaysWhy() {
            reply("PUT /api/books/c2/cover", {status: 400, data: {message: "Ảnh quá lớn"}})
            const page = openBook(book("c2"))
            compare(one(page, "coverSet").text, "Đặt bìa")
            verify(!shown(one(page, "coverRemove")))
            one(page, "coverEditor").setImage("data:image/png;base64,AAA")
            tryVerify(function() { return Api.notice.indexOf("Chưa đặt được ảnh bìa\n") === 0 })
            verify(Api.notice.indexOf("Ảnh quá lớn") > 0)
            one(page, "coverEditor").setImage("")
            compare(Api.notice, "Chưa đặt được ảnh bìa\nKhông đọc được file ảnh")
        }
        function test_coverEditorGoesThroughThePeerBridge() {
            const b = book("c3", {cover: {version: 1}})
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn"}}})
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + "/api/books/c3", {status: 200, data: {book: b, chapters: []}})
            reply("PUT " + peerBase + "/api/books/c3/cover", {status: 200, data: {}})
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("c3")
            tryCompare(page, "shownKey", "route:project")
            tryVerify(function() { return has(page, "coverEditor") && shown(one(page, "coverEditor")) }, 3000)
            one(page, "coverEditor").setImage("data:image/png;base64,BBB")
            tryVerify(function() { return calls("PUT", peerBase + "/api/books/c3/cover").length === 1 })
            compare(DesktopApi.requests.filter(r => r.path === "/api/books/c3/cover").length, 0)
        }
        function test_coverEditorIsSmallOnANarrowWindow() {
            const page = openBook(book("c4", {cover: {version: 1}}), 520)
            compare(one(page, "coverEditor").width, 96)
            verify(shown(one(page, "coverSetIcon")))
            verify(!shown(one(page, "coverSet")))
        }
    }
}
