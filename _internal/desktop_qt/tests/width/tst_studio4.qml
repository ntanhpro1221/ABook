import QtQuick
import QtTest
import "ModalLayer.js" as ModalLayer
import "VisualReady.js" as VisualReady
import ABook

// Studio S4: tab "Nhân vật" của dự án (dàn người, đổi giọng / tên / giới / gộp / bỏ gộp, công tắc "Nhân vật tự kể", lời dưới hàng người kể) và màn "Duyệt trước khi thu"
// (dải mời, công tắc chờ duyệt, bốn bước với thẻ việc, số trên nhãn tab, hộp Việc cần duyệt chỉ nói còn bao nhiêu thẻ ở màn duyệt). Máy chủ giả giữ trạng thái; HTTP là DesktopApi giả.
// Ảnh sáng / tối ghi ra build/d2shots/s4_*.png để tự nhìn.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    // Hộp / bảng nổi và hộp chọn đều nằm dưới gốc cửa sổ (WindowLayer, Overlay)
    readonly property var overlay: Window.window ? Window.window.contentItem : null
    Component { id: studioFactory; StudioScreen {} }

    TestCase {
        id: test
        name: "Studio4"
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
        function inOverlay(name) { const found = all(host.overlay, name).filter(shown); verify(found.length > 0, "thiếu " + name + " trong lớp phủ"); return found[0] }
        function hasTop(name) { return all(host.overlay, name).filter(shown).length > 0 }
        function has(item, name) { return all(item, name).filter(shown).length > 0 }
        function texts(item) { return ModalLayer.collect(item, node => node.text !== undefined && shown(node)).map(node => String(node.text)) }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function hasPart(item, part) { return texts(item).some(t => t.indexOf(part) >= 0) }
        function all2(item, test) { return ModalLayer.collect(item, test) }
        function buttons(item, text) { return all2(item, n => n.clicked !== undefined && n.text === text && shown(n)) }
        function press(item, text) {
            tryVerify(function() { return buttons(item, text).length > 0 }, 3000, "thiếu nút " + text)
            buttons(item, text)[0].clicked()
        }
        function shot(name, item) {
            const target = item || host
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            const path = Qt.resolvedUrl("../../build/d2shots/s4_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(VisualReady.grabTarget(host.Window.window, target)).save(path)
        }
        function scrollTo(page, item) {
            waitForRendering(page)   // đầu danh sách đã xếp lại sau khi đổi tab rồi mới tính chỗ cuộn
            const list = page.projectScreenList
            list.contentY = Math.max(0, item.mapToItem(list.contentItem, 0, 0).y - 24)
        }
        function both(name, item) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shot(name, item) } Theme.mode = "auto" }
        function noCut(item) {
            for (const text of all2(item, t => t.contentWidth !== undefined && t.wrapMode !== undefined && shown(t) && String(t.text) !== "")) {
                verify(text.contentWidth <= text.width + 1, "chữ tràn ngang: " + String(text.text).slice(0, 40) + " " + text.contentWidth + ">" + text.width)
                verify(text.contentHeight <= text.height + 1 || text.height === 0, "chữ bị cắt: " + String(text.text).slice(0, 40))
            }
        }

        // ---- dữ liệu giả ----
        function stamp() { return Math.floor(Date.now() / 1000) }
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
        // Cuốn phân tích xong, chưa thu chương nào: có màn duyệt
        function precastBook(over) {
            return book("a", Object.assign({
                phase: "synthesizing", castLocked: true, precast: {ready: true, wait: false, announcedAt: stamp() - 60, held: false},
                chapters: {total: 3, completed: 0, redo: 0, missingAudio: 0, failed: 0, working: 0}, progress: {overall: 0.4, analysis: 1, synthesis: 0}
            }, over || {}))
        }
        function chapter(id) {
            return {id: id, index: id, title: "Chương " + id, displayTitle: "Chương " + id, subtitle: "", fullTitle: "Chương " + id, status: "completed", statusLabel: "Đã thu",
                    segments: {total: 10, analyzed: 10, recorded: 10, finished: 10, failed: 0, warnings: 0}, seconds: 300, playable: true, redo: false,
                    startedAt: stamp() - 7200, completedAt: stamp() - 3600, lastError: ""}
        }
        function example(over) {
            return Object.assign({segmentId: 101, chapterId: 1, chapterTitle: "Chương 1", seq: 4, text: "Anh Henko bước vào quán và gọi một chén trà nóng.", speaker: "Mai", hasAudio: true}, over || {})
        }
        function pronCard(over) {
            return Object.assign({kind: "pronunciation", key: "pron:Henko", title: "Máy chưa chắc “Henko” đọc thế nào", problem: "Tên này xuất hiện 7 lần; máy đoán cách đọc nhưng không chắc.",
                                  affected: 7, doubt: 0.4, score: 9, options: [], current: "Hên-cơ", surface: "Henko", requested: null, examples: [example()]}, over || {})
        }
        function speakerCard(over) {
            return Object.assign({kind: "speaker", key: "speaker:s1", title: "Ai nói câu này", problem: "Câu không có tên người nói; máy đoán là Mai.", affected: 3, doubt: 0.5, score: 8, options: [],
                                  current: "Mai", currentValue: "Mai", lines: [{stableId: "s1", textSha256: "aa"}], seen: {s1: "Mai"}, chapters: [1],
                                  choices: [{label: "Mai", value: "Mai"}, {label: "Lan", value: "Lan"}, {label: "Kati", value: "Kati"}],
                                  examples: [example({segmentId: 102, seq: 9, text: "“Đi thôi,” cô khẽ nói.", before: "Cô quay lại nhìn anh.", after: "Anh gật đầu."})]}, over || {})
        }
        function audioCard() {
            return {kind: "audio", key: "audio:7", title: "Câu này chưa thu được", problem: "Máy đã thử ba lần mà vẫn hỏng.", affected: 1, doubt: 1, score: 7, options: [], current: "Chưa thu được",
                    examples: [example({segmentId: 103, seq: 12, text: "Tách tách tách.", hasAudio: false})]}
        }
        function voiceCard() {
            return {kind: "gender", key: "gender:Kati", title: "Kati là nam hay nữ?", problem: "Máy chưa chắc giới của Kati.", affected: 14, doubt: 0.5, score: 5, options: [], current: "chưa rõ",
                    voiceChoices: [{label: "Nam", character: "Kati", gender: "male", done: "Kati là nam", note: "giữ giọng đang đọc"}, {label: "Nữ", character: "Kati", gender: "female", done: "Kati là nữ", note: "đổi giọng, thu lại 12 câu"}],
                    keepCharacters: ["Kati"], keepLabel: "Giữ nguyên", examples: []}
        }
        function work() { return [voiceCard(), pronCard(), speakerCard(), audioCard(), speakerCard({key: "speaker:s2", lines: [{stableId: "s2", textSha256: "bb"}], seen: {s2: "Mai"}, chapters: [5], affected: 1})] }
        function emptyInbox() { return {devices: [], waiting: 0, recent: [], skipped: []} }
        function names() {
            return {items: [{surface: "Henko", spoken: "hên-cơ", byListener: false, lines: 7, requested: null, example: {segmentId: 101, chapterTitle: "Chương 1", seq: 4, text: "Anh Henko bước vào.", hasAudio: true}},
                            {surface: "Lorcan", spoken: "lo-can", byListener: true, lines: 3, requested: "lo-ken", example: null}], unseen: 0}
        }
        function castFixture() {
            const voice = (preset, label) => ({preset: preset, label: label})
            return {
                narrator: {voice: "Minh Quân", lines: 120, seconds: 3600, redo: 0},
                characters: [
                    {name: "Lan", displayName: "Lan", gender: "Nữ", voice: voice("ngoc-linh", "Ngọc Linh"), lines: 40, seconds: 300, firstChapter: "Chương 1", sampleId: 3},
                    {name: "Hạ_Vy", displayName: "Hạ Vy", gender: "Nữ", voice: voice("hoai-my", "Hoài My"), lines: 25, seconds: 150, firstChapter: "Chương 1", sampleId: 4, pendingVoice: voice("huong", "Hương")},
                    {name: "Lính_gác", displayName: "Lính gác", gender: "Nam", voice: voice("nam-minh", "Nam Minh"), lines: 8, seconds: 40, firstChapter: "Chương 1", sampleId: 5},
                    {name: "Lính_gác_2", displayName: "Lính gác", gender: "Nam", voice: voice("nam-an", "Nam An"), lines: 5, seconds: 30, firstChapter: "Chương 2", sampleId: 6}],
                extras: [{name: "Tuấn", displayName: "Tuấn", gender: "Nam", voice: voice("nam-minh", "Nam Minh"), lines: 10, seconds: 60, firstChapter: "Chương 1", mergedInto: "Lan", mergedAt: 1700.5},
                         {name: "Bà_hàng", displayName: "Bà hàng", gender: "Nữ", voice: voice("hoai-my", "Hoài My"), lines: 2, seconds: 10, firstChapter: "Chương 2"}],
                carried: []}
        }
        function voicesFixture() {
            return {character: {value: "Lan", label: "Lan", gender: "female", lines: 40, chapters: 3}, current: "Ngọc Linh", pending: null, tryLine: true,
                    voices: [
                        {key: "ngoc-linh", name: "Ngọc Linh", gender: "female", genderLabel: "Nữ", engine: "vieneu", installed: true, current: true, preview: true},
                        {key: "hoai-my", name: "Hoài My", gender: "female", genderLabel: "Nữ", engine: "vieneu", installed: true, preview: true, suggested: true},
                        {key: "nam-minh", name: "Nam Minh", gender: "male", genderLabel: "Nam", engine: "vieneu", installed: true, preview: true}]}
        }
        function precastView() {
            return {ready: true, wait: false, announcedAt: stamp() - 60, held: false, chapters: 3, recordedChapters: 0, recordedThrough: null,
                    upcoming: [{id: 1, title: "Chương 1"}, {id: 2, title: "Chương 2"}]}
        }
        function tellerView(over) {
            return Object.assign({available: true, mode: "narrator", castLocked: true, applied: false, editableHere: true,
                                  plan: {direction: "on", lines: 30, recorded: 0, seconds: 0, measured: false, tellers: ["Lan"]}}, over || {})
        }
        function library(books) { return {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: books}} }
        function clone(v) { return JSON.parse(JSON.stringify(v)) }

        // ---- máy chủ giả có trạng thái ----
        function serve(extra) {
            server = Object.assign({work: work(), inbox: emptyInbox(), names: names(), cast: castFixture(), voices: voicesFixture(), precast: precastView(), teller: tellerView(), review: 0}, extra || {})
            reply("GET " + base + "/work", function() { return {status: 200, data: clone({items: server.work, counts: {}})} })
            reply("GET " + base + "/work?count=1", function() { return {status: 200, data: {count: server.work.filter(i => !i.requested && !i.redoOnly).length}} })
            reply("GET " + base + "/review", function() { return {status: 200, data: {counts: {}, pending: server.review, redoChapters: [], items: [], nextCursor: null, remaining: 0}} })
            reply("GET " + base + "/edits-inbox", function() { return {status: 200, data: clone(server.inbox)} })
            reply("GET " + base + "/pronunciations", function() { return {status: 200, data: clone(server.names)} })
            reply("GET " + base + "/shared-readings", function() { return {status: 200, data: {entries: []}} })
            reply("GET /api/readings", function() { return {status: 200, data: {entries: []}} })
            reply("GET " + base + "/precast", function() { return {status: 200, data: clone(server.precast)} })
            reply("PUT " + base + "/precast", function(body) { server.precast.wait = body.wait; return {status: 200, data: clone(server.precast)} })
            reply("GET " + base + "/cast", function() { return {status: 200, data: clone(server.cast)} })
            reply("GET " + base + "/narrator-mode", function() { return {status: 200, data: clone(server.teller)} })
            reply("PUT " + base + "/narrator-mode", function(body) {
                server.teller = Object.assign({}, server.teller, {mode: body.mode, applied: true})
                return {status: 200, data: clone(server.teller)}
            })
            reply("GET " + base + "/voices?character=Lan", function() { return {status: 200, data: clone(server.voices)} })
            reply("POST " + base + "/voice", function(body) {
                for (const item of server.work) if (item.voiceChoices) item.requested = (item.voiceChoices.find(c => c.gender === body.gender) || {done: "Giữ nguyên"}).done
                return {status: 200, data: {requestedAt: 66}}
            })
            reply("POST " + base + "/voice/preview", {status: 200, data: {url: "/media/previews/p1.wav", text: "“Anh đi đâu thế?”"}})
            reply("POST " + base + "/characters/rename", {status: 200, data: {renamed: true, name: "Lan Anh"}})
            reply("POST " + base + "/characters/merge", {status: 200, data: {lines: 5}})
            reply("GET " + base + "/pending-changes", {status: 200, data: {items: [{section: "speakers", requestedAt: 1700.5, key: "s1", keys: ["s1", "s2"]}]}})
            reply("POST " + base + "/speaker", function(body) {
                for (const item of server.work) if (item.lines && item.lines.length && body.lines && item.lines[0].stableId === body.lines[0].stableId) item.requested = body.speaker
                return {status: 200, data: {lines: body.lines.length, requestedAt: 77}}
            })
            reply("POST " + base + "/pronunciation", function(body) {
                for (const item of server.work) if (item.surface === body.surface) item.requested = body.spokenForm
                for (const item of server.names.items) if (item.surface === body.surface) item.requested = body.spokenForm === item.spoken ? null : body.spokenForm
                return {status: 200, data: {surface: body.surface, spokenForm: body.spokenForm, requestedAt: 99}}
            })
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
            Platform.setSetting("fold.book.a.extras", "1")
            Theme.reduceMotion = false
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
        function openProject(tab, width, b) {
            const row = b || book("a")
            reply("GET /api/library", library([row]))
            reply("GET " + base, {status: 200, data: {book: row, chapters: [chapter(1), chapter(2), chapter(3)]}})
            const page = makeStudio(width)
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            if (tab) pickTab(page, tab)
            return page
        }
        function screenOf(page) { return page.projectScreenList.parent }
        function pickTab(page, tab) {
            screenOf(page).pickTab(tab)
            tryCompare(screenOf(page), "shownTab", tab, 3000)
        }
        function counts(page) { return one(page, "projectTabs").counts }
        function cards(page) { return all(page, "workCard").filter(shown) }
        function titles(page) { return cards(page).map(c => one(c, "workTitle").text) }
        function personNames(page) { return all(page, "castName").filter(shown).map(t => t.text) }
        function castReady(page) { tryVerify(function() { return has(page, "studioCastList") && one(page, "studioCastList").status === "ready" }, 3000) }
        function precastReady(page) { tryVerify(function() { return has(page, "precastContent") }, 3000) }
        function openPrecast(over, width) {
            const page = openProject("", width, precastBook(over))
            pickTab(page, "precast")
            precastReady(page)
            return page
        }
        function step(page, key) {
            one(page, "precastStep_" + key).clicked()
            tryCompare(screenOf(page), "precastStep", key, 3000)
        }
        function rowOf(page, name) {
            let node = all(page, "castName").filter(shown).filter(t => t.text === name)[0]
            while (node && node.person === undefined) node = node.parent
            return node
        }
        function longText() {
            return "Một đoạn chữ rất dài của người dùng, viết liền một mạch không ngắt để thử xem giao diện xuống dòng đúng chỗ hay tràn ra ngoài khung: "
                + "Nguyễn Thị Hạ Vy Của Vương Quốc Phía Đông Xa Xôi Và Những Ngày Tháng Không Thể Nào Quên Được cùng những người bạn đồng hành của cô ấy."
        }

        // ================= 1. tab Nhân vật =================
        function test_castTabListsPeopleNarratorNoteAndTellerSwitch() {
            serve()
            const page = openProject("cast")
            castReady(page)
            tryVerify(function() { return personNames(page).length >= 4 }, 3000)
            verify(personNames(page).indexOf("Lan") >= 0)
            verify(personNames(page).indexOf("Hạ Vy") >= 0)
            verify(hasText(page, "Vai chính"))
            verify(hasText(page, "Vai phụ"))
            verify(hasText(page, "Minh Quân"))
            // lời dưới hàng người kể + công tắc tự kể, đúng chữ của bản web
            tryVerify(function() { return hasPart(page, "Đổi giọng kể không phải tạo lại sách") }, 3000)
            tryVerify(function() { return has(page, "tellerRow") }, 3000)
            verify(hasPart(page, "Nhân vật tự kể"))
            verify(hasPart(page, "Giọng dẫn đọc lời kể; nhân vật chỉ đọc lời thoại."))
            // nằm trong khung cuộn của dự án: không cuộn riêng
            verify(one(page, "studioCastList").embedded)
            tryVerify(function() { return one(page, "studioCastList").height > 200 }, 3000)
            // người kể có nút đổi giọng khi đã phân vai
            tryVerify(function() { return has(page, "castNarratorVoiceButton") }, 3000)
            noCut(page)
            scrollTo(page, one(page, "studioCastList"))
            both("cast_tab", page)
        }
        function test_narratorNoteBeforeTheBookRunsOffersTheSetupLink() {
            serve({cast: Object.assign(castFixture(), {})})
            const page = openProject("cast", 1280, book("a", {phase: "idle", castLocked: false}))
            castReady(page)
            tryVerify(function() { return has(page, "narratorNote") }, 3000)
            verify(one(page, "narratorNote").text.indexOf("Giọng kể chọn lúc tạo sách, đổi được vì cuốn này chưa bắt đầu chạy.") === 0)
            verify(one(page, "narratorNote").text.indexOf("Đổi giọng kể") > 0)
            // chưa phân vai: không có nút đổi giọng người kể
            verify(!has(page, "castNarratorVoiceButton"))
        }
        function test_narratorNoteWhileAnalysingSaysWhen() {
            serve()
            const page = openProject("cast", 1280, book("a", {phase: "analyzing", castLocked: false, running: true}))
            castReady(page)
            tryVerify(function() { return hasPart(page, "Đổi được giọng kể khi máy phân vai xong") }, 3000)
        }

        // ================= 2. công tắc "Nhân vật tự kể" =================
        function test_tellerSwitchWithNothingRecordedWritesAtOnce() {
            serve()
            const page = openProject("cast")
            tryVerify(function() { return has(page, "tellerSwitch") }, 3000)
            compare(one(page, "tellerSwitch").checked, false)
            one(page, "tellerSwitch").toggled(true)
            tryVerify(function() { return calls("PUT", base + "/narrator-mode").length === 1 })
            compare(calls("PUT", base + "/narrator-mode")[0].body, {mode: "teller"})
            tryVerify(function() { return one(page, "tellerSwitch").checked })
            tryVerify(function() { return Api.notice === "Đã đổi - những câu đổi giọng sẽ được thu bằng giọng mới" })
            verify(hasPart(page, "Nhân vật xưng “tôi” đọc cả lời kể bằng giọng mình."))
            // đổi xong thì dàn người đọc lại
            tryVerify(function() { return calls("GET", base + "/cast").length >= 2 })
        }
        function test_tellerSwitchWithRecordedLinesAsksFirstAndDeclineWritesNothing() {
            serve({teller: tellerView({plan: {direction: "on", lines: 30, recorded: 12, seconds: 600, measured: true, tellers: ["Lan", "Hạ Vy"]}})})
            const page = openProject("cast")
            tryVerify(function() { return has(page, "tellerSwitch") }, 3000)
            one(page, "tellerSwitch").toggled(true)
            tryVerify(function() { return hasTop("tellerConfirm") })
            verify(hasPart(host.overlay, "Bật giọng tự kể?"))
            verify(hasPart(host.overlay, "30 câu lời kể sẽ đọc bằng giọng của Lan, Hạ Vy. 12 bản thu hiện có của những câu ấy sẽ bị bỏ và thu lại"))
            // "Thôi": không gửi gì
            inOverlay("confirm_later").clicked()
            tryVerify(function() { return !hasTop("tellerConfirm") })
            wait(50) // fixed: proves absence
            compare(calls("PUT", base + "/narrator-mode").length, 0)
            compare(one(page, "tellerSwitch").checked, false)
            // "Bật và thu lại": gửi
            one(page, "tellerSwitch").toggled(true)
            tryVerify(function() { return hasTop("confirm_go") })
            inOverlay("confirm_go").clicked()
            tryVerify(function() { return calls("PUT", base + "/narrator-mode").length === 1 })
            compare(calls("PUT", base + "/narrator-mode")[0].body, {mode: "teller"})
            tryVerify(function() { return Api.notice === "Đã đổi - bấm “Tiếp tục” để thu lại những câu đổi giọng" })
        }
        function test_tellerSwitchIsLockedWhileTheBookRunsAndHiddenWhenUnavailable() {
            serve()
            const page = openProject("cast", 1280, book("a", {running: true, phase: "synthesizing", statusLabel: "Đang thu"}))
            tryVerify(function() { return has(page, "tellerSwitch") }, 3000)
            compare(one(page, "tellerSwitch").enabled, false)
            verify(hasPart(page, "Dừng sau phân tích để đổi, rồi Tiếp tục; Tạm dừng chưa đủ."))
            page.destroy()
            serve({teller: tellerView({available: false})})
            const other = openProject("cast")
            castReady(other)
            tryVerify(function() { return calls("GET", base + "/narrator-mode").length >= 1 })
            verify(!has(other, "tellerSwitch"))
        }

        // ================= 3. việc với một người =================
        function openMenu(page, name) {
            const row = rowOf(page, name)
            verify(row !== undefined && row !== null, "thiếu người " + name)
            one(row, "castMore").clicked()
            tryVerify(function() { return hasTop("castMenu") || findChild(page, "castMenu").open })
        }
        function dialog(page, name) { return findChild(page, name) }
        function test_renameWritesThroughTheStudioPathAndRefreshesTheList() {
            serve()
            const page = openProject("cast")
            castReady(page)
            tryVerify(function() { return rowOf(page, "Lan") !== undefined && rowOf(page, "Lan") !== null }, 3000)
            const before = calls("GET", base + "/cast").length
            openMenu(page, "Lan")
            findChild(page, "castRename").clicked()
            tryVerify(function() { return dialog(page, "castRenameDialog").open })
            const field = findChild(dialog(page, "castRenameDialog"), "personName")
            compare(field.text, "Lan")
            field.text = "Lan Anh"
            all(dialog(page, "castRenameDialog"), "personNameSave")[0].activated()
            tryVerify(function() { return calls("POST", base + "/characters/rename").length === 1 })
            compare(calls("POST", base + "/characters/rename")[0].body, {character: "Lan", name: "Lan Anh"})
            tryVerify(function() { return Api.notice === "Đã đổi tên thành Lan Anh" })
            tryVerify(function() { return calls("GET", base + "/cast").length > before })
            tryVerify(function() { return !dialog(page, "castRenameDialog").open })
        }
        function test_genderAndMergeDialogsSendTheirBodiesAndDeclineSendsNothing() {
            serve()
            const page = openProject("cast")
            castReady(page)
            tryVerify(function() { return rowOf(page, "Lan") !== undefined && rowOf(page, "Lan") !== null }, 3000)
            // giới tính
            openMenu(page, "Lan")
            findChild(page, "castGender").clicked()
            tryVerify(function() { return dialog(page, "castGenderDialog").open })
            all(dialog(page, "castGenderDialog"), "genderChoice")[0].picked("male")
            all(dialog(page, "castGenderDialog"), "genderSave")[0].activated()
            tryVerify(function() { return calls("POST", base + "/voice").length === 1 })
            compare(calls("POST", base + "/voice")[0].body, {character: "Lan", gender: "male"})
            tryVerify(function() { return Api.notice.indexOf("Đã ghi: Lan là nhân vật nam") === 0 })
            tryVerify(function() { return !dialog(page, "castGenderDialog").open })
            // gộp: huỷ thì không gửi gì; chọn người rồi gộp thì gửi đúng from / into
            openMenu(page, "Lan")
            findChild(page, "castMerge").clicked()
            tryVerify(function() { return dialog(page, "castMergeDialog").open })
            all(dialog(page, "castMergeDialog"), "mergeCancel")[0].clicked()
            tryVerify(function() { return !dialog(page, "castMergeDialog").open })
            compare(calls("POST", base + "/characters/merge").length, 0)
            openMenu(page, "Lan")
            findChild(page, "castMerge").clicked()
            tryVerify(function() { return dialog(page, "castMergeDialog").open })
            tryVerify(function() { return all(dialog(page, "castMergeDialog"), "mergeChoice").length >= 2 })
            const choice = all(dialog(page, "castMergeDialog"), "mergeChoice").filter(c => c.modelData.name === "Hạ_Vy")[0]
            choice.clicked()
            all(dialog(page, "castMergeDialog"), "mergeDo")[0].activated()
            tryVerify(function() { return calls("POST", base + "/characters/merge").length === 1 })
            compare(calls("POST", base + "/characters/merge")[0].body, {from: "Lan", into: "Hạ_Vy"})
            tryVerify(function() { return Api.notice === "Đã ghi: 5 câu của Lan là của Hạ Vy" })
        }
        function test_unmergeWithdrawsTheMergeVoteAndStaleSaysSo() {
            serve()
            const page = openProject("cast")
            castReady(page)
            tryVerify(function() { return rowOf(page, "Tuấn") !== undefined && rowOf(page, "Tuấn") !== null }, 3000)
            one(rowOf(page, "Tuấn"), "castUnmerge").clicked()
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            compare(calls("POST", base + "/speaker")[0].body.lines, [{stableId: "s1"}, {stableId: "s2"}])
            compare(calls("POST", base + "/speaker")[0].body.withdraw, true)
            tryVerify(function() { return Api.notice === "Đã bỏ gộp Tuấn" })
            reply("GET " + base + "/pending-changes", {status: 200, data: {items: []}})
            one(rowOf(page, "Tuấn"), "castUnmerge").clicked()
            tryVerify(function() { return Api.notice.indexOf("Chưa bỏ gộp được") === 0 })
            compare(calls("POST", base + "/speaker").length, 1)
        }
        function test_voicePickerListsVoicesPreviewsAndChoosesThroughTheStudioPath() {
            serve()
            const page = openProject("cast")
            castReady(page)
            tryVerify(function() { return rowOf(page, "Lan") !== undefined && rowOf(page, "Lan") !== null }, 3000)
            one(rowOf(page, "Lan"), "castVoiceButton").clicked()
            tryVerify(function() { return dialog(page, "castVoiceDialog").open })
            tryVerify(function() { return all(dialog(page, "castVoiceDialog"), "voiceChoice").length >= 2 }, 3000)
            compare(calls("GET", base + "/voices?character=Lan").length, 1)
            // nghe thử câu mẫu chung của giọng: qua Clip
            all(dialog(page, "castVoiceDialog"), "voicePreview")[0].clicked()
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            compare(DesktopApi.previews[0], "/media/voices/ngoc-linh")
            // nghe thử bằng câu của sách
            all(dialog(page, "castVoiceDialog"), "voiceTry")[1].requested()
            tryVerify(function() { return calls("POST", base + "/voice/preview").length === 1 })
            compare(calls("POST", base + "/voice/preview")[0].body, {character: "Lan", preset: "hoai-my"})
            tryVerify(function() { return DesktopApi.previews.length === 2 })
            compare(DesktopApi.previews[1], "/media/previews/p1.wav")
            // chọn giọng: gửi và hiện "Hoàn tác"
            const choose = all(dialog(page, "castVoiceDialog"), "voiceChoice").filter(c => c.voice.key === "hoai-my")[0]
            all(choose, "voiceAction")[0].activated()
            tryVerify(function() { return calls("POST", base + "/voice").length === 1 })
            compare(calls("POST", base + "/voice")[0].body, {character: "Lan", preset: "hoai-my", seen: 0})
            tryVerify(function() { return Api.notice.indexOf("Đã ghi: Lan đọc bằng giọng Hoài My") === 0 })
            compare(Api.noticeAction.label, "Hoàn tác")
        }
        function test_narratorVoiceButtonOpensTheSamePickerForTheNarrator() {
            serve()
            reply("GET " + base + "/voices?character=NARRATOR", function() {
                const v = clone(server.voices); v.character = {value: "NARRATOR", label: "người kể", gender: "male", lines: 120, chapters: 3}; return {status: 200, data: v}
            })
            const page = openProject("cast")
            castReady(page)
            tryVerify(function() { return has(page, "castNarratorVoiceButton") }, 3000)
            one(page, "castNarratorVoiceButton").clicked()
            tryVerify(function() { return dialog(page, "castVoiceDialog").open })
            tryVerify(function() { return calls("GET", base + "/voices?character=NARRATOR").length === 1 })
        }
        function test_remoteStudioOnlyNamesTheComputerForDownloadingVoices() {
            serve()
            const v = clone(server.voices)
            v.voices.push({key: "zero-1", name: "Zero Một", gender: "female", genderLabel: "Nữ", engine: "zero", installed: false, preview: false})
            v.modules = {zero: {state: "missing", bytes: 5242880, done: 0, total: 0}}
            server.voices = v
            const b = book("a")
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn phòng làm việc"}}})
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + base, {status: 200, data: {book: b, chapters: [chapter(1)]}})
            for (const key of Object.keys(DesktopApi.responses).filter(k => k.indexOf(base) >= 0 || k === "GET /api/readings")) {
                reply(key.replace(base, peerBase + base).replace("GET /api/readings", "GET " + peerBase + "/api/readings"), DesktopApi.responses[key])
            }
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            pickTab(page, "cast")
            castReady(page)
            tryVerify(function() { return rowOf(page, "Lan") !== undefined && rowOf(page, "Lan") !== null }, 3000)
            one(rowOf(page, "Lan"), "castVoiceButton").clicked()
            tryVerify(function() { return dialog(page, "castVoiceDialog").open })
            tryVerify(function() { return has(dialog(page, "castVoiceDialog"), "engineOnComputer") }, 3000)
            verify(!has(dialog(page, "castVoiceDialog"), "engineStart"))
            // tệp nghe thử cũng đi qua máy kia
            all(dialog(page, "castVoiceDialog"), "voicePreview")[0].clicked()
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            compare(DesktopApi.previews[0], peerBase + "/media/voices/ngoc-linh")
            compare(calls("GET", "/api/studio/zero").length, 0)
        }

        // ================= 4. Duyệt trước khi thu =================
        function test_bannerInvitesAndOpensTheReviewScreen() {
            serve()
            const page = openProject("", 1280, precastBook())
            tryVerify(function() { return has(page, "precastBanner") }, 3000)
            verify(hasText(page, "Phân tích xong - duyệt trước khi thu?"))
            verify(hasText(page, "Duyệt giọng, tên và người nói trước để tránh thu lại."))
            noCut(one(page, "precastBanner"))
            scrollTo(page, one(page, "precastBanner"))
            both("precast_banner", page)
            one(page, "precastBannerOpen").activated()
            tryCompare(screenOf(page), "shownTab", "precast", 3000)
            // đã ở màn duyệt thì dải mời khép
            tryVerify(function() { return !has(page, "precastBanner") }, 3000)
        }
        function test_bannerSaysTheBookIsHeldAndHidesWhenChaptersAreRecorded() {
            serve()
            const held = precastBook({precast: {ready: true, wait: true, announcedAt: stamp() - 60, held: true}, paused: "precast"})
            const page = openProject("", 1280, held)
            tryVerify(function() { return has(page, "precastBanner") }, 3000)
            verify(hasText(page, "Phân tích xong - sách đang chờ bạn duyệt"))
            page.destroy()
            const done = openProject("", 1280, precastBook({chapters: {total: 3, completed: 1, redo: 0, missingAudio: 0, failed: 0, working: 0}}))
            VisualReady.render(this, host.Window.window, done, qtVisualReady)
            verify(!has(done, "precastBanner"))
        }
        function test_waitSwitchWritesBeforeTheAnalysisIsAnnounced() {
            serve()
            const page = openProject("", 1280, precastBook({precast: {ready: false, wait: false, announcedAt: null, held: false}, castLocked: false, phase: "analyzing", running: true}))
            tryVerify(function() { return has(page, "precastWaitSwitch") }, 3000)
            compare(one(page, "precastWaitSwitch").checked, false)
            verify(hasPart(page, "Phân tích xong thì thu luôn; duyệt lúc nào cũng được."))
            one(page, "precastWaitSwitch").toggled(true)
            tryVerify(function() { return calls("PUT", base + "/precast").length === 1 })
            compare(calls("PUT", base + "/precast")[0].body, {wait: true})
        }
        function test_reviewShowsFourStepsWithCountsAndTheCastStep() {
            serve()
            const page = openPrecast()
            // đếm: 3 thẻ ở màn duyệt, 2 thẻ còn lại ở Việc cần duyệt
            tryVerify(function() { return counts(page).precast === 3 && counts(page).work === 2 }, 3000)
            const steps = ["cast", "names", "lines", "done"]
            for (const key of steps) verify(has(page, "precastStep_" + key), "thiếu bước " + key)
            verify(hasPart(one(page, "precastStep_cast"), "1 việc"))
            verify(hasPart(one(page, "precastStep_names"), "1 tên"))
            verify(hasPart(one(page, "precastStep_lines"), "3 câu"))
            verify(hasText(page, "Nghe và chỉnh giọng cho 4 nhân vật nói nhiều nhất."))
            tryVerify(function() { return personNames(page).length === 4 }, 3000)
            // hai người trùng tên: hỏi có phải một người không
            tryVerify(function() { return all(page, "precastTwin").filter(shown).length === 2 }, 3000)
            verify(hasText(page, "Cùng tên với người khác trong sách - một người?"))
            // thẻ "Máy chưa chắc" của bước này
            tryVerify(function() { return cards(page).length === 1 }, 3000)
            compare(titles(page)[0], "Kati là nam hay nữ?")
            verify(hasPart(page, "· 1 việc về người và giọng"))
            verify(hasPart(page, "Khi áp dụng"))
            noCut(page)
            both("precast_cast", page)
        }
        function test_twinNoteOffersTheMergeDialog() {
            serve()
            const page = openPrecast()
            tryVerify(function() { return all(page, "precastTwinMerge").filter(shown).length === 2 }, 3000)
            all(page, "precastTwinMerge").filter(shown)[0].clicked()
            tryVerify(function() { return dialog(page, "castMergeDialog").open })
            // người nhận gộp: cả vai chính và vai phụ, trừ chính nó
            tryVerify(function() { return all(dialog(page, "castMergeDialog"), "mergeChoice").length >= 4 })
        }
        function test_namesStepCardsEditorAndSkipAdvance() {
            serve()
            const page = openPrecast()
            step(page, "names")
            tryVerify(function() { return hasText(page, "Nghe và sửa 1 cách đọc tên, tên kém chắc ở trên.") }, 3000)
            tryVerify(function() { return titles(page).indexOf("Máy chưa chắc “Henko” đọc thế nào") >= 0 }, 3000)
            // chấp nhận: ghi đúng cách đọc máy đang dùng
            one(page, "pronKeep").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 1 })
            compare(calls("POST", base + "/pronunciation")[0].body, {surface: "Henko", spokenForm: "Hên-cơ", seen: ""})
            // số trên nhãn tab giảm đúng một thẻ; việc ngoài màn duyệt giữ nguyên
            tryVerify(function() { return counts(page).precast === 2 && counts(page).work === 2 }, 3000)
            tryVerify(function() { return hasPart(one(page, "precastStep_names"), "ổn") }, 3000)
            // mục "Cách đọc tên" gập, mở thì mới tải
            compare(calls("GET", base + "/pronunciations").length, 0)
            one(page, "precastNamesToggle").clicked()
            tryVerify(function() { return has(page, "nameReadings") }, 3000)
            tryVerify(function() { return calls("GET", base + "/pronunciations").length >= 1 })
            // bỏ qua / tiếp tục sang bước kế
            one(page, "precastSkip").clicked()
            tryCompare(screenOf(page), "precastStep", "lines", 3000)
            one(page, "precastNext").clicked()
            tryCompare(screenOf(page), "precastStep", "done", 3000)
            tryVerify(function() { return hasText(page, "Xong lượt duyệt") }, 3000)
            verify(hasText(page, "Sửa nào cũng đã ghi lại; máy áp khi sách chạy tiếp. Những chỗ khác máy chưa chắc vẫn ở “Việc cần duyệt”."))
            // bước cuối không còn nút bỏ qua / tiếp tục
            tryVerify(function() { return !has(page, "precastNext") }, 3000)
        }
        function test_linesStepShowsOnlyDoubtfulLinesOfTheNextChapters() {
            serve()
            const page = openPrecast()
            step(page, "lines")
            tryVerify(function() { return hasPart(page, "3 câu máy chưa chắc ai nói ở Chương 1 → Chương 2 - các chương thu đầu tiên; các chương sau xem ở Việc cần duyệt.") }, 3000)
            tryVerify(function() { return cards(page).length === 1 }, 3000)
            compare(titles(page)[0], "Ai nói câu này")
            // chọn người nói: ghi đúng các câu của thẻ
            press(page, "Lan")
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            compare(calls("POST", base + "/speaker")[0].body.lines, [{stableId: "s1", textSha256: "aa"}])
            compare(calls("POST", base + "/speaker")[0].body.speaker, "Lan")
            tryVerify(function() { return counts(page).precast === 2 }, 3000)
            tryVerify(function() { return hasPart(page, "Không có câu nghi ngờ ở Chương 1 → Chương 2") || cards(page).length === 0 }, 3000)
        }
        function test_castStepDecisionWritesTheVoiceAndTheCardLeaves() {
            serve()
            const page = openPrecast()
            tryVerify(function() { return cards(page).length === 1 }, 3000)
            press(page, "Nữ")
            tryVerify(function() { return calls("POST", base + "/voice").length === 1 })
            compare(calls("POST", base + "/voice")[0].body, {character: "Kati", gender: "female"})
            tryVerify(function() { return Api.notice === "Đã ghi: Kati là nữ" })
            tryVerify(function() { return counts(page).precast === 2 }, 3000)
        }
        function test_inboxOnlyCountsWhatIsLeftAndPointsAtTheReviewScreen() {
            serve()
            const page = openProject("work", 1280, precastBook())
            tryVerify(function() { return has(page, "workPrecast") }, 3000)
            verify(hasText(page, "3 việc của các chương đầu đang chờ ở “Duyệt trước khi thu”."))
            // thẻ của màn duyệt không hiện lại ở đây
            tryVerify(function() { return cards(page).length === 2 }, 3000)
            const names = titles(page)
            verify(names.indexOf("Kati là nam hay nữ?") < 0)
            verify(names.indexOf("Câu này chưa thu được") >= 0)
            // chưa hết thẻ nên chưa có lời "Mọi việc đã có quyết định"
            verify(!has(page, "workEnd") || !shown(one(page, "workEnd")))
            one(page, "workPrecastOpen").clicked()
            tryCompare(screenOf(page), "shownTab", "precast", 3000)
            scrollTo(page, one(page, "precastSteps"))
        }
        function test_jumpingToTheScriptKeepsTheStepForBack() {
            serve()
            const page = openPrecast()
            step(page, "names")
            one(page, "pronNames").clicked()
            tryCompare(screenOf(page), "shownTab", "cast", 3000)
            compare(screenOf(page).cameFrom, "precast")
            tryVerify(function() { return has(page, "nameReadings") && shown(one(page, "nameSearch")) }, 3000)
            compare(one(page, "nameSearch").text, "Henko")
            one(page, "jumpBack").clicked()
            tryCompare(screenOf(page), "shownTab", "precast", 3000)
            compare(screenOf(page).precastStep, "names")
        }
        function test_finishingTheReviewReturnsToTheChapters() {
            serve()
            const page = openPrecast()
            step(page, "done")
            tryVerify(function() { return has(page, "precastClose") }, 3000)
            one(page, "precastClose").clicked()
            tryCompare(screenOf(page), "shownTab", "chapters", 3000)
        }
        function test_reviewNotReadyExplainsWhy() {
            serve()
            const page = openProject("", 1280, book("a"))
            screenOf(page).pickTab("precast")
            tryCompare(screenOf(page), "shownTab", "precast", 3000)
            tryVerify(function() { return hasText(page, "Màn duyệt mở được khi máy đã phân tích xong và phân vai.") }, 3000)
        }

        // ================= 5. chữ dài, Studio máy khác, cửa sổ ẩn =================
        function test_longTextWrapsAtBothWidths() {
            const lengthy = longText()
            const cast = castFixture()
            cast.characters[0].displayName = "Lan " + lengthy.slice(0, 100)
            cast.characters[0].originalName = lengthy.slice(0, 60)
            cast.characters[1].displayName = "Nhân vật " + lengthy.slice(0, 80)
            cast.characters[2].displayName = "Lính gác"
            cast.characters[3].displayName = "Lính gác"
            cast.narrator.voice = "Giọng " + lengthy.slice(0, 70)
            serve({cast: cast, work: [voiceCard(), pronCard({problem: lengthy, examples: [example({text: lengthy})]}), speakerCard({problem: lengthy, examples: [example({text: lengthy, before: lengthy, after: lengthy})]})]})
            for (const width of [1024, 1920]) {
                const page = openProject("cast", width, precastBook())
                castReady(page)
                tryVerify(function() { return personNames(page).length >= 4 }, 3000)
                noCut(page)
                shot("long_cast_" + width, page)
                pickTab(page, "precast")
                precastReady(page)
                tryVerify(function() { return cards(page).length === 1 }, 3000)
                noCut(page)
                shot("long_precast_cast_" + width, page)
                step(page, "names")
                tryVerify(function() { return cards(page).length === 1 }, 3000)
                noCut(page)
                step(page, "lines")
                tryVerify(function() { return cards(page).length === 1 }, 3000)
                noCut(page)
                shot("long_precast_lines_" + width, page)
                verify(page.projectScreenList.contentWidth <= page.projectScreenList.width + 0.5)
                page.destroy()
            }
        }
        function test_narrowWindowFoldsTheIntroAndStacksTheSteps() {
            serve()
            const page = openPrecast({}, 560)
            verify(has(page, "precastIntroToggle"))
            tryVerify(function() { return !shown(one(page, "precastIntro")) }, 3000)
            one(page, "precastIntroToggle").clicked()
            tryVerify(function() { return shown(one(page, "precastIntro")) }, 3000)
            const a = one(page, "precastStep_cast"), b = one(page, "precastStep_names")
            verify(Math.abs(a.y - b.y) < 1)
            noCut(page)
            shot("precast_narrow", page)
        }
        function test_peerRoutesEveryCastAndReviewRequestThroughTheBridge() {
            serve()
            const b = precastBook()
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn phòng làm việc"}}})
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + base, {status: 200, data: {book: b, chapters: [chapter(1)]}})
            for (const key of Object.keys(DesktopApi.responses).filter(k => k.indexOf(base) >= 0 || k === "GET /api/readings")) {
                reply(key.replace(base, peerBase + base).replace("GET /api/readings", "GET " + peerBase + "/api/readings"), DesktopApi.responses[key])
            }
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return counts(page).precast === 3 }, 3000)
            // tab Nhân vật
            pickTab(page, "cast")
            castReady(page)
            tryVerify(function() { return has(page, "tellerSwitch") }, 3000)
            one(page, "tellerSwitch").toggled(true)
            tryVerify(function() { return calls("PUT", peerBase + base + "/narrator-mode").length === 1 })
            tryVerify(function() { return rowOf(page, "Lan") !== undefined && rowOf(page, "Lan") !== null }, 3000)
            openMenu(page, "Lan")
            findChild(page, "castRename").clicked()
            tryVerify(function() { return dialog(page, "castRenameDialog").open })
            all(dialog(page, "castRenameDialog"), "personNameSave")[0].activated()
            tryVerify(function() { return calls("POST", peerBase + base + "/characters/rename").length === 1 })
            // nghe mẫu của một người qua cầu của máy kia
            one(rowOf(page, "Lan"), "castSample").clicked()
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            compare(DesktopApi.previews[0], peerBase + "/media/books/a/samples/3")
            // màn duyệt: công tắc và thẻ
            pickTab(page, "precast")
            precastReady(page)
            tryVerify(function() { return calls("GET", peerBase + base + "/precast").length >= 1 })
            press(page, "Nữ")
            tryVerify(function() { return calls("POST", peerBase + base + "/voice").length === 1 })
            // KHÔNG một lời gọi nào đi thẳng vào máy này
            const direct = DesktopApi.requests.filter(r => (/^\/api\/books\/a/).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct.slice(0, 3)))
        }
        function test_nothingIsAskedWhileTheWindowIsHiddenOrTheTabIsAway() {
            serve()
            const page = openProject("", 1280, precastBook({running: true, phase: "synthesizing", statusLabel: "Đang thu"}))
            tryVerify(function() { return counts(page).precast === 3 }, 3000)
            const w = screenOf(page).store
            const work = one(page, "projectHeader") && null
            // chưa mở tab Nhân vật / màn duyệt: chưa hỏi dàn người, giọng tự kể, cách đọc tên
            compare(calls("GET", base + "/cast").length, 0)
            compare(calls("GET", base + "/narrator-mode").length, 0)
            compare(calls("GET", base + "/pronunciations").length, 0)
            // cửa sổ ẩn: cả nhịp hỏi màn duyệt lẫn giọng tự kể đều dừng
            pickTab(page, "cast")
            castReady(page)
            tryVerify(function() { return has(page, "tellerSwitch") }, 3000)
            const tracked = calls("GET", base + "/narrator-mode").length
            w.active = false
            const before = DesktopApi.requests.length
            wait(60) // fixed: proves absence
            compare(DesktopApi.requests.length, before)
            w.active = true
            compare(calls("GET", base + "/narrator-mode").length, tracked)
        }
    }
}
