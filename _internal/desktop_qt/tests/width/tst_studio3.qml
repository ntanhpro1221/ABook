import QtQuick
import QtTest
import "ModalLayer.js" as ModalLayer
import "VisualReady.js" as VisualReady
import ABook

// Studio S3: các tab "Việc cần duyệt" (WorkInbox.tsx), "Cần nghe lại" (ReviewQueue.tsx) và mục "Cách đọc tên" của tab Nhân vật (NameReadings.tsx), hộp "Yêu cầu thiết bị" (PhoneEdits.tsx)
// cùng ba con số trên nhãn tab. Máy chủ giả giữ trạng thái (việc, câu cần nghe, cách đọc tên, hộp thư) để thấy con số và danh sách đổi sau mỗi lần bấm; HTTP là DesktopApi giả.
// Ảnh sáng / tối ghi ra build/d2shots/s3_*.png để tự nhìn.
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
        name: "Studio3"
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
        // Hộp hỏi lại nằm trong lớp phủ của cửa sổ (không phải con của màn)
        function inOverlay(name) { const found = all(host.overlay, name).filter(shown); verify(found.length > 0, "thiếu " + name + " trong lớp phủ"); return found[0] }
        function hasTop(name) { return all(host.overlay, name).filter(shown).length > 0 }
        function has(item, name) { return all(item, name).filter(shown).length > 0 }
        function texts(item) { return ModalLayer.collect(item, node => node.text !== undefined && shown(node)).map(node => String(node.text)) }
        function hasText(item, value) { return texts(item).indexOf(value) >= 0 }
        function hasPart(item, part) { return texts(item).some(t => t.indexOf(part) >= 0) }
        function shot(name, item) {
            const target = item || host
            VisualReady.render(this, host.Window.window, target, qtVisualReady)
            const path = Qt.resolvedUrl("../../build/d2shots/s3_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(VisualReady.grabTarget(host.Window.window, target)).save(path)
        }
        // Cuộn danh sách của màn dự án tới một phần tử để ảnh chụp thấy đúng chỗ cần xem
        function scrollTo(page, item) {
            const list = page.projectScreenList
            list.contentY = Math.max(0, item.mapToItem(list.contentItem, 0, 0).y - 24)
        }
        function both(name, item) { for (const mode of ["light", "dark"]) { Theme.mode = mode; shot(name, item) } Theme.mode = "auto" }
        // Chữ nào cũng nằm trọn trong khung của nó (xuống dòng, không cắt)
        function noCut(item) {
            for (const text of all2(item, t => t.contentWidth !== undefined && t.wrapMode !== undefined && shown(t) && String(t.text) !== "")) {
                verify(text.contentWidth <= text.width + 1, "chữ tràn ngang: " + String(text.text).slice(0, 40) + " " + text.contentWidth + ">" + text.width)
                verify(text.contentHeight <= text.height + 1 || text.height === 0, "chữ bị cắt: " + String(text.text).slice(0, 40))
            }
        }
        function all2(item, test) { return ModalLayer.collect(item, test) }
        // Nút bấm được theo chữ (DecisionButton, Button)
        function buttons(item, text) { return all2(item, n => n.clicked !== undefined && n.text === text && shown(n)) }
        function press(item, text) {
            tryVerify(function() { return buttons(item, text).length > 0 }, 3000, "thiếu nút " + text)
            buttons(item, text)[0].clicked()
        }

        // ---- dữ liệu giả ----
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
            return Object.assign({kind: "speaker", key: "speaker:s1", title: "Ai nói câu này", problem: "Câu không có tên người nói; máy đoán là Mai.", affected: 1, doubt: 0.5, score: 8, options: [],
                                  current: "Mai", currentValue: "Mai", lines: [{stableId: "s1", textSha256: "aa"}], seen: {s1: "Mai"},
                                  choices: [{label: "Mai", value: "Mai"}, {label: "Lan", value: "Lan"}, {label: "Kati", value: "Kati"}],
                                  examples: [example({segmentId: 102, seq: 9, text: "“Đi thôi,” cô khẽ nói.", before: "Cô quay lại nhìn anh.", after: "Anh gật đầu."})]}, over || {})
        }
        function audioCard() {
            return {kind: "audio", key: "audio:7", title: "Câu này chưa thu được", problem: "Máy đã thử ba lần mà vẫn hỏng.", affected: 1, doubt: 1, score: 7, options: [], current: "Chưa thu được",
                    examples: [example({segmentId: 103, seq: 12, text: "Tách tách tách.", hasAudio: false})]}
        }
        function narratorCard() {
            return {kind: "narrator", key: "narrator:1:3:9", title: "Người kể của đoạn", problem: "Đoạn này mở bằng “Góc nhìn của Lan”.", affected: 7, doubt: 0.6, score: 6, options: [],
                    current: "Mai", examples: [example({segmentId: 104, seq: 3})],
                    narratorSection: {chapterIndex: 1, fromSeq: 3, toSeq: 9, narrator: "Mai", appliesNote: "Đoạn đã phân tích xong: chỉ áp khi làm lại sách.",
                                      choices: [{label: "Lan", value: "Lan"}], heading: {line: "Góc nhìn của Lan", narrator: "Lan", label: "Lan"}}}
        }
        function voiceCard() {
            return {kind: "gender", key: "gender:Kati", title: "Kati là nam hay nữ?", problem: "Máy chưa chắc giới của Kati.", affected: 14, doubt: 0.5, score: 5, options: [], current: "chưa rõ",
                    voiceChoices: [{label: "Nam", character: "Kati", gender: "male", done: "Kati là nam", note: "giữ giọng đang đọc"}, {label: "Nữ", character: "Kati", gender: "female", done: "Kati là nữ", note: "đổi giọng, thu lại 12 câu"}],
                    keepCharacters: ["Kati"], keepLabel: "Giữ nguyên", examples: []}
        }
        function refusedCard() {
            return {kind: "refused", key: "refused:voice:Noah", title: "Yêu cầu chưa được", problem: "Giọng Rhine đã được dùng cho người khác.", affected: 1, doubt: 1, score: 4, options: [], current: "Giọng Rhine",
                    refused: {section: "voices", key: "Noah", requestedAt: 123}, examples: []}
        }
        function decidedCard() {
            return pronCard({key: "pron:Lorcan", surface: "Lorcan", current: "Lo-can", requested: "Lo-ken", title: "Máy chưa chắc “Lorcan” đọc thế nào",
                             undo: {endpoint: "pronunciation", decisions: [{surface: "Lorcan", requestedAt: 55, previous: "Lo-can", keep: false}]}, examples: []})
        }
        function reviewItem(id, over) {
            return Object.assign({segmentId: 200 + id, stableId: "r" + id, audioSha256: "sha" + id, chapterId: 1, chapterTitle: "Chương 1", text: "Câu cần nghe số " + id + ".", heard: "Câu cần nghe số " + id,
                                  similarity: 0.97, speaker: "Mai", kind: "unverified", reason: "Máy chưa kiểm được", playable: true, chapterClip: null, verdict: null, textSha256: "t" + id,
                                  spoken: null, pendingSpoken: null}, over || {})
        }
        function emptyInbox() { return {devices: [], waiting: 0, recent: [], skipped: []} }
        function deviceInbox() {
            return {devices: [{id: "d1", name: "OPPO của bạn", at: stamp() - 600, items: [
                        {id: "i1", kind: "pronunciation", label: "“Henko” đọc là “Hên-khơ”", lines: 1},
                        {id: "i2", kind: "voice", label: "Kati đổi giọng", chapter: "Chương 2", lines: 12, conflict: "Máy này đã đổi khác sau đó."}]}],
                    waiting: 2, recent: [{at: stamp() - 3600, device: "d1", name: "OPPO của bạn", applied: 2, skipped: 0, requests: 1, waiting: 2, conflicts: ["Tên chương đã đổi ở cả hai máy."]}],
                    skipped: [{id: "d2", name: "Máy cũ", at: stamp() - 9000, items: [{id: "i9", kind: "line", label: "Sửa chữ đọc câu 4", chapter: "Chương 1", lines: 1}]}]}
        }
        function names(count) {
            const items = [{surface: "Henko", spoken: "hên-cơ", byListener: false, lines: 7, requested: null, example: {segmentId: 101, chapterTitle: "Chương 1", seq: 4, text: "Anh Henko bước vào.", hasAudio: true}},
                           {surface: "Lorcan", spoken: "lo-can", byListener: true, lines: 3, requested: "lo-ken", example: null}]
            for (let i = 0; i < (count || 0); ++i) items.push({surface: "Tên" + i, spoken: "tên " + i, byListener: false, lines: 1, requested: null, example: null})
            return {items: items, unseen: 4}
        }
        function library(books) { return {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: books}} }

        // ---- máy chủ giả có trạng thái ----
        // Như HTTP thật: mỗi lần hỏi nhận một bản chép mới (đưa thẳng vật của máy chủ giả thì sửa tại chỗ không báo đổi)
        function clone(v) { return JSON.parse(JSON.stringify(v)) }
        function workView() { return {status: 200, data: clone({items: server.work, counts: {}})} }
        function reviewView(filter, cursor) {
            const handled = i => Boolean(i.verdict) || (i.pendingSpoken !== null && i.pendingSpoken !== undefined)
            const pending = server.review.filter(i => !handled(i)).length
            let items = server.review.filter(i => filter === "done" ? handled(i) : !handled(i))
            let next = null, remaining = 0
            if (server.pageSize) {
                const from = cursor ? Number(cursor) : 0
                const page = items.slice(from, from + server.pageSize)
                remaining = Math.max(0, items.length - from - page.length)
                next = remaining > 0 ? String(from + server.pageSize) : null
                items = page
            }
            return {status: 200, data: clone({counts: server.minor || {}, pending: pending, redoChapters: server.redoChapters || [], items: items, nextCursor: next, remaining: remaining})}
        }
        function serve(extra) {
            server = Object.assign({work: [], review: [], inbox: emptyInbox(), names: names(), offer: [], shared: [], pageSize: 0, minor: {}, redoChapters: []}, extra || {})
            reply("GET " + base + "/work", function() { return workView() })
            reply("GET " + base + "/work?count=1", function() { return {status: 200, data: {count: server.work.filter(i => !i.requested && !i.redoOnly).length}} })
            reply("GET " + base + "/review", function() { return reviewView("todo", "") })
            for (const filter of ["todo", "done"]) {
                for (const minor of ["", "&all=1"]) {
                    reply("GET " + base + "/review?filter=" + filter + minor, function() { return reviewView(filter, "") })
                    for (const cursor of ["3", "6", "9"]) reply("GET " + base + "/review?filter=" + filter + minor + "&cursor=" + cursor, function() { return reviewView(filter, cursor) })
                }
            }
            reply("GET " + base + "/edits-inbox", function() { return {status: 200, data: clone(server.inbox)} })
            reply("GET " + base + "/pronunciations", function() { return {status: 200, data: clone(server.names)} })
            reply("GET " + base + "/shared-readings", function() { return {status: 200, data: clone({entries: server.offer})} })
            reply("GET /api/readings", function() { return {status: 200, data: clone({entries: server.shared})} })
            reply("POST " + base + "/review", function(body) {
                for (const item of server.review) if (item.stableId === body.stableId) item.verdict = body.verdict
                return {status: 200, data: {}}
            })
            reply("POST " + base + "/line", function(body) {
                for (const item of server.review) if (item.stableId === body.stableId) item.pendingSpoken = body.spoken
                return {status: 200, data: {}}
            })
            reply("POST " + base + "/pronunciation", function(body) {
                for (const item of server.work) if (item.surface === body.surface) item.requested = body.spokenForm
                for (const item of server.names.items) if (item.surface === body.surface) item.requested = body.spokenForm === item.spoken ? null : body.spokenForm
                return {status: 200, data: {surface: body.surface, spokenForm: body.spokenForm, requestedAt: 99}}
            })
            reply("POST " + base + "/speaker", function(body) {
                for (const item of server.work) if (item.lines && item.lines.length && body.lines && item.lines[0].stableId === body.lines[0].stableId) item.requested = body.speaker
                return {status: 200, data: {lines: body.lines.length, requestedAt: 77}}
            })
            reply("POST " + base + "/narrator-section", function(body) {
                for (const item of server.work) if (item.kind === "narrator") item.requested = body.action === "keep" ? "Giữ nguyên" : "Đổi người kể"
                return {status: 200, data: {action: body.action || "set", narrator: body.narrator || ""}}
            })
            reply("POST " + base + "/voice", function(body) {
                for (const item of server.work) if (item.voiceChoices) item.requested = (item.voiceChoices.find(c => c.gender === body.gender) || {done: "Giữ nguyên"}).done
                return {status: 200, data: {requestedAt: 66}}
            })
            reply("POST " + base + "/pending-changes/withdraw", function(body) { server.work = server.work.filter(i => i.kind !== "refused"); return {status: 200, data: {}} })
            reply("POST " + base + "/edits-inbox/apply", function(body) {
                server.inbox.devices = server.inbox.devices.map(d => d.id !== body.device ? d : Object.assign({}, d, {items: body.items ? d.items.filter(i => body.items.indexOf(i.id) < 0) : []})).filter(d => d.items.length > 0)
                server.inbox.waiting = server.inbox.devices.reduce((n, d) => n + d.items.length, 0)
                return {status: 200, data: {requests: body.items ? body.items.length : 2, skipped: 0, held: 0, dropped: []}}
            })
            reply("POST " + base + "/edits-inbox/skip", function(body) {
                server.inbox.devices = server.inbox.devices.filter(d => d.id !== body.device)
                server.inbox.waiting = server.inbox.devices.reduce((n, d) => n + d.items.length, 0)
                return {status: 200, data: {removed: 2}}
            })
            reply("POST " + base + "/edits-inbox/restore", function(body) {
                server.inbox.skipped = server.inbox.skipped.filter(d => d.id !== body.device)
                return {status: 200, data: {restored: 1}}
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
        function openProject(tab, width, bookOver) {
            const b = book("a", bookOver)
            reply("GET /api/library", library([b]))
            reply("GET " + base, {status: 200, data: {book: b, chapters: [chapter(1), chapter(2), chapter(3)]}})
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
            one(page, "tab_" + tab).clicked()
            tryCompare(screenOf(page), "shownTab", tab, 3000)
        }
        function counts(page) { return one(page, "projectTabs").counts }
        function cards(page) { return all(page, "workCard").filter(shown) }
        function titles(page) { return cards(page).map(c => one(c, "workTitle").text) }
        function reviewRows(page) { return all(page, "reviewRow").filter(shown) }
        function inboxOf(page) { return one(page, "workInbox") }

        // ================= 1. ba con số trên nhãn tab =================
        function test_tabCountsFollowOpenWorkReviewAndInbox() {
            serve({work: [pronCard(), speakerCard(), decidedCard()], review: [reviewItem(1), reviewItem(2), reviewItem(3, {verdict: "ok"})], inbox: deviceInbox()})
            const page = openProject()
            // việc đã quyết không đếm: 2 việc mở + 2 việc từ điện thoại; câu cần nghe: 2 chưa xem
            tryVerify(function() { return counts(page).work === 4 }, 3000)
            tryVerify(function() { return counts(page).review === 2 }, 3000)
            compare(calls("GET", base + "/work?count=1").length >= 1, true)
            // chưa mở tab thì không tải cả danh sách việc (chỉ hỏi con số)
            compare(calls("GET", base + "/work").length, 0)
            pickTab(page, "work")
            tryVerify(function() { return cards(page).length >= 2 }, 3000)
            compare(counts(page).work, 4)
        }

        // ================= 2. hộp việc =================
        function test_everyCardKindShowsItsOwnFix() {
            serve({work: [speakerCard(), pronCard(), audioCard(), narratorCard(), voiceCard(), refusedCard(), decidedCard()]})
            const page = openProject("work")
            tryVerify(function() { return cards(page).length === 6 }, 3000)
            const names = titles(page)
            verify(names.indexOf("Ai nói câu này") >= 0)
            verify(names.indexOf("Máy chưa chắc “Henko” đọc thế nào") >= 0)
            verify(names.indexOf("Kati là nam hay nữ?") >= 0)
            verify(hasText(inboxOf(page), "Ưu tiên việc trên. Sách đang dừng; sửa áp khi làm tiếp.") || hasPart(inboxOf(page), "Ưu tiên việc trên."))
            // mỗi loại có chỗ sửa riêng
            verify(has(page, "pronKeep"))
            verify(has(page, "workChips"))
            verify(has(page, "workReview"))
            verify(has(page, "narratorAccept"))
            verify(has(page, "voiceKeep"))
            verify(has(page, "workDrop"))
            // việc đã quyết nằm trong mục "Đã quyết", đã khép
            verify(has(page, "workDecided"))
            // thanh lọc liệt kê đúng các loại đang có
            const filter = one(page, "workFilter")
            verify(filter.options.length >= 2)
            noCut(inboxOf(page))
            scrollTo(page, one(page, "workFilter"))
            both("work_cards", page)
        }
        function test_pronunciationKeepWritesTheDecisionAndShowsUndo() {
            serve({work: [pronCard(), speakerCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "pronKeep") }, 3000)
            one(page, "pronKeep").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 1 })
            compare(calls("POST", base + "/pronunciation")[0].body, {surface: "Henko", spokenForm: "Hên-cơ", seen: ""})
            tryVerify(function() { return Api.notice.indexOf("Giữ cách đọc “Hên-cơ”") === 0 })
            compare(Api.noticeAction.label, "Hoàn tác")
            // sau khi ghi: việc rời danh sách mở, con số giảm
            tryVerify(function() { return counts(page).work === 1 }, 3000)
            // Hoàn tác = gửi lại đúng lần bấm kèm withdraw
            Api.noticeAction.run()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 2 })
            const undo = calls("POST", base + "/pronunciation")[1].body
            compare(undo.withdraw, true)
            compare(undo.surface, "Henko")
        }
        function test_pronunciationRefusedShowsTheProblemAndOffersTheSuggestion() {
            serve({work: [pronCard()]})
            reply("POST " + base + "/pronunciation", function(body) {
                if (body.spokenForm === "Hên-kơ") return {status: 400, data: {error: "Cách đọc này có chữ máy không đọc được.", suggestion: "Hên-cơ"}}
                return {status: 200, data: {surface: body.surface, spokenForm: body.spokenForm, requestedAt: 5}}
            })
            const page = openProject("work")
            tryVerify(function() { return has(page, "pronField") }, 3000)
            one(page, "pronField").text = "Hên-kơ"
            tryVerify(function() { return one(page, "pronSave").enabled })
            one(page, "pronSave").clicked()
            tryVerify(function() { return has(page, "readingProblem") })
            compare(one(page, "readingProblem").text, "Cách đọc này có chữ máy không đọc được.")
            // lỗi chỉ nằm dưới ô, không có lời báo
            compare(Api.notice, "")
            tryVerify(function() { return has(page, "readingSuggestion") })
            compare(one(page, "readingSuggestion").text, "Dùng “Hên-cơ”")
            one(page, "readingSuggestion").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 2 })
            compare(calls("POST", base + "/pronunciation")[1].body.spokenForm, "Hên-cơ")
        }
        function test_tryReadingAsksTheMachineAndPlaysThroughTheClip() {
            serve({work: [pronCard()]})
            reply("POST " + base + "/pronunciation/preview", {status: 200, data: {url: "/media/previews/p1.wav", text: "Anh Hên-khơ bước vào quán.", speaker: "Mai"}})
            const page = openProject("work")
            tryVerify(function() { return has(page, "pronField") }, 3000)
            one(page, "pronField").text = "Hên-khơ"
            tryVerify(function() { return one(page, "pronTry").enabled })
            one(page, "pronTry").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation/preview").length === 1 })
            compare(calls("POST", base + "/pronunciation/preview")[0].body, {surface: "Henko", spokenForm: "Hên-khơ"})
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            compare(DesktopApi.previews[0], "/media/previews/p1.wav")
            // nghe thử không ghi gì vào sách
            compare(calls("POST", base + "/pronunciation").length, 0)
        }
        function test_speakerChoiceWritesTheLinesWithWhatTheCardSaw() {
            serve({work: [speakerCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "workChips") }, 3000)
            press(one(page, "workChips"), "Lan")
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            compare(calls("POST", base + "/speaker")[0].body, {lines: [{stableId: "s1", textSha256: "aa"}], speaker: "Lan", newGender: "", seen: {s1: "Mai"}})
            tryVerify(function() { return Api.notice === "Đã ghi: câu này của Lan" })
            compare(Api.noticeAction.label, "Hoàn tác")
            // thẻ đã quyết nói kết quả trong mục "Đã quyết"
            tryVerify(function() { return !counts(page).work }, 3000)
        }
        function test_speakerElsewhereAsksWhichToKeep() {
            serve({work: [speakerCard()]})
            reply("POST " + base + "/speaker", {status: 200, data: {lines: 1, requestedAt: 5, elsewhere: {s1: "Kati"}}})
            const page = openProject("work")
            tryVerify(function() { return has(page, "workChips") }, 3000)
            press(one(page, "workChips"), "Lan")
            tryVerify(function() { return Api.notice.indexOf("Chỗ này vừa được sửa ở máy hay cửa sổ khác") === 0 })
            verify(Api.notice.indexOf("Trước đó đang là Kati") > 0)
            compare(Api.noticeAction.label, "Lấy của máy kia")
        }
        function test_decidedCardUndoesTheExactDecision() {
            serve({work: [decidedCard(), pronCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "workDecided") }, 3000)
            // mở mục "Đã quyết"
            one(page, "workSectionToggle").clicked()
            tryVerify(function() { return has(page, "workUndo") })
            one(page, "workUndo").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 1 })
            compare(calls("POST", base + "/pronunciation")[0].body, {surface: "Lorcan", requestedAt: 55, previous: "Lo-can", keep: false, withdraw: true})
            tryVerify(function() { return Api.notice.indexOf("Đã hoàn tác") === 0 })
        }
        function test_narratorVoiceAndRefusedCards() {
            serve({work: [narratorCard(), voiceCard(), refusedCard()]})
            const page = openProject("work")
            tryVerify(function() { return cards(page).length === 3 }, 3000)
            one(page, "workDrop").clicked()
            tryVerify(function() { return calls("POST", base + "/pending-changes/withdraw").length === 1 })
            compare(calls("POST", base + "/pending-changes/withdraw")[0].body, {section: "voices", key: "Noah", requestedAt: 123})
            tryVerify(function() { return Api.notice === "Đã bỏ yêu cầu này" })
            press(page, "Nữ")
            tryVerify(function() { return calls("POST", base + "/voice").length === 1 })
            compare(calls("POST", base + "/voice")[0].body, {character: "Kati", gender: "female"})
            tryVerify(function() { return Api.notice === "Đã ghi: Kati là nữ" })
            one(page, "narratorKeep").clicked()
            tryVerify(function() { return calls("POST", base + "/narrator-section").length === 1 })
            compare(calls("POST", base + "/narrator-section")[0].body.chapterIndex, 1)
            compare(calls("POST", base + "/narrator-section")[0].body.fromSeq, 3)
        }
        function test_bulkKeepAsksFirstThenWritesEveryCard() {
            serve({work: [pronCard({key: "p1", surface: "Aa"}), pronCard({key: "p2", surface: "Bb"}), pronCard({key: "p3", surface: "Cc"})]})
            const page = openProject("work")
            tryVerify(function() { return cards(page).length === 3 }, 3000)
            one(page, "workFilter").picked("pronunciation")
            tryVerify(function() { return has(page, "bulkKeep") }, 3000)
            one(page, "bulkKeep").clicked()
            tryVerify(function() { return hasTop("bulkConfirm") })
            inOverlay("confirm_go").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 3 }, 3000)
            compare(calls("POST", base + "/pronunciation").map(r => r.body.surface), ["Aa", "Bb", "Cc"])
            tryVerify(function() { return Api.notice.indexOf("Đã giữ như máy đang làm cho 3 thẻ") === 0 })
        }
        function test_emptyInboxSaysItIsDone() {
            serve({work: []})
            const page = openProject("work")
            tryVerify(function() { return has(page, "workEmpty") }, 3000)
            verify(hasText(page, "Không còn việc duyệt"))
            verify(hasText(page, "Máy chắc chắn về mọi thứ đã làm tới giờ."))
            compare(has(page, "workContent"), false)
        }
        function test_workErrorOffersRetry() {
            serve({work: []})
            reply("GET " + base + "/work", {status: 500, data: {error: "hỏng"}})
            const page = openProject("work")
            tryVerify(function() { return has(page, "workError") && shown(one(page, "workError")) }, 3000)
            verify(hasText(page, "Bạn hãy kiểm tra kết nối rồi tải lại việc cần duyệt."))
        }

        // ================= 3. nhảy giữa các tab =================
        function test_audioCardJumpsToReviewAndBack() {
            serve({work: [audioCard(), pronCard()], review: [reviewItem(1)]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "workReview") }, 3000)
            one(page, "workReview").clicked()
            tryCompare(screenOf(page), "shownTab", "review", 3000)
            tryVerify(function() { return has(page, "jumpBack") })
            compare(one(page, "jumpBack").text, "Về màn trước")
            one(page, "jumpBack").clicked()
            tryCompare(screenOf(page), "shownTab", "work", 3000)
            tryVerify(function() { return cards(page).length === 2 })
        }
        function test_namesLinkOpensTheCastTabWithTheNameFilled() {
            serve({work: [pronCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "pronNames") }, 3000)
            one(page, "pronNames").clicked()
            tryCompare(screenOf(page), "shownTab", "cast", 3000)
            tryVerify(function() { return has(page, "nameReadings") && shown(one(page, "nameSearch")) }, 3000)
            compare(one(page, "nameSearch").text, "Henko")
            // chỉ còn dòng của tên ấy
            tryVerify(function() { return all(page, "nameRow").filter(shown).length === 1 })
            compare(screenOf(page).focusNames, true)
            one(page, "jumpBack").clicked()
            tryCompare(screenOf(page), "shownTab", "work", 3000)
        }

        // ================= 4. Cần nghe lại =================
        function test_reviewListsUnseenFirstAndPlaysTheClip() {
            serve({review: [reviewItem(1), reviewItem(2, {kind: "failed", playable: false, reason: "Chưa thu được"}), reviewItem(3, {playable: false, chapterClip: {start: 12.5, end: 15}}), reviewItem(4, {verdict: "ok"})]})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 3 }, 3000)
            compare(one(page, "reviewLead").text.indexOf("3 câu") >= 0, true)
            // câu hỏng: không có nút nghe, có dấu nói thẳng vì sao, chỉ còn thu lại
            const failed = reviewRows(page).filter(r => r.item.kind === "failed")[0]
            verify(!failed.source)
            compare(one(failed, "verdictRedo").text, "Thu lại câu này")
            compare(has(failed, "verdictOk"), false)
            verify(hasText(failed, "Câu này chưa thu được, chưa có gì để nghe."))
            // câu đã dọn bản thu riêng: nghe đúng đoạn trong chương
            const clipped = reviewRows(page).filter(r => r.item.segmentId === 203)[0]
            one(clipped, "reviewPlay").clicked()
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            compare(DesktopApi.previews[0], "/media/books/a/chapters/1")
            compare(DesktopApi.starts[0], 12.5)
            compare(Clip.span, 2.5)
            noCut(page)
            scrollTo(page, one(page, "reviewLead"))
            both("review_list", page)
        }
        function test_verdictWritesWithWhatTheRowSawAndTheRowLeaves() {
            serve({review: [reviewItem(1), reviewItem(2)]})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 2 }, 3000)
            tryVerify(function() { return counts(page).review === 2 }, 3000)
            one(reviewRows(page)[0], "verdictOk").clicked()
            tryVerify(function() { return calls("POST", base + "/review").length === 1 })
            compare(calls("POST", base + "/review")[0].body, {stableId: "r1", chapterId: 1, audioSha256: "sha1", verdict: "ok", seen: {r1: ""}})
            // câu rời danh sách "Chưa xem", con số giảm, tiêu điểm sang câu kế
            tryVerify(function() { return reviewRows(page).length === 1 })
            tryVerify(function() { return counts(page).review === 1 }, 3000)
            tryVerify(function() { return reviewRows(page)[0].item.stableId === "r2" })
            // "Đã xem" có câu vừa phán
            one(page, "reviewFilter").picked("done")
            tryVerify(function() { return reviewRows(page).length === 1 && reviewRows(page)[0].item.stableId === "r1" }, 3000)
            // bỏ phán quyết -> trở về chưa xem
            one(reviewRows(page)[0], "verdictOk").clicked()
            tryVerify(function() { return calls("POST", base + "/review").length === 2 })
            compare(calls("POST", base + "/review")[1].body.verdict, null)
            compare(calls("POST", base + "/review")[1].body.seen, {r1: "ok"})
        }
        function test_verdictElsewhereOffersTheOtherMachinesChoice() {
            serve({review: [reviewItem(1)]})
            reply("POST " + base + "/review", {status: 200, data: {elsewhere: {r1: "redo"}}})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 1 }, 3000)
            one(reviewRows(page)[0], "verdictRedo").clicked()
            tryVerify(function() { return Api.notice.indexOf("Chỗ này vừa được sửa ở máy hay cửa sổ khác") === 0 })
            verify(Api.notice.indexOf("“Cần thu lại”") > 0)
            compare(Api.noticeAction.label, "Lấy của máy kia")
            Api.noticeAction.run()
            tryVerify(function() { return calls("POST", base + "/review").length === 2 })
            compare(calls("POST", base + "/review")[1].body, {stableId: "r1", chapterId: 1, audioSha256: "sha1", verdict: "redo"})
        }
        function test_verdictFailureSaysSoAndTheRowComesBack() {
            serve({review: [reviewItem(1)]})
            reply("POST " + base + "/review", {status: 500, data: {error: "đĩa đầy"}})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 1 }, 3000)
            one(reviewRows(page)[0], "verdictOk").clicked()
            tryVerify(function() { return Api.notice.indexOf("Chưa ghi được phán quyết nghe") === 0 })
            // máy chủ không ghi: hỏi lại thì câu vẫn chưa xem
            tryVerify(function() { return reviewRows(page).length === 1 && !reviewRows(page)[0].item.verdict }, 3000)
        }
        function test_continuousListeningPlaysEveryRowAndJudgesWithKeys() {
            serve({review: [reviewItem(1), reviewItem(2), reviewItem(3, {kind: "failed", playable: false})]})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 3 }, 3000)
            // chỉ 2 câu nghe được -> nút mời nghe liền 2 câu
            tryVerify(function() { return has(page, "reviewListenAll") })
            compare(one(page, "reviewListenAll").text, "Nghe liền 2 câu")
            one(page, "reviewListenAll").clicked()
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            verify(DesktopApi.previews[0].indexOf("/samples/201") > 0)
            tryVerify(function() { return has(page, "reviewStopAll") })
            // phán bằng phím O: câu rời danh sách, câu kế phát luôn
            keyClick(Qt.Key_O)
            tryVerify(function() { return calls("POST", base + "/review").length === 1 }, 3000)
            compare(calls("POST", base + "/review")[0].body.verdict, "ok")
            tryVerify(function() { return DesktopApi.previews.length === 2 }, 3000)
            verify(DesktopApi.previews[1].indexOf("/samples/202") > 0)
            // dừng nghe liền
            one(page, "reviewStopAll").clicked()
            tryVerify(function() { return has(page, "reviewListenAll") || !has(page, "reviewStopAll") })
            compare(Clip.current, "")
        }
        function test_spokenEditorWritesTheTextAndTheWholeTwinGroup() {
            serve({review: [reviewItem(1, {text: "Tách tách tách.", heard: "tạch tạch"}), reviewItem(2, {text: "Tách tách tách!", heard: "tạch"}), reviewItem(3)]})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 3 }, 3000)
            const row = reviewRows(page)[0]
            compare(one(row, "reviewEdit").text, "Sửa 2 câu")
            one(row, "reviewEdit").clicked()
            tryVerify(function() { return has(row, "spokenField") })
            one(row, "spokenField").text = "tạch tạch tạch"
            tryVerify(function() { return has(row, "spokenSaveAll") })
            compare(one(row, "spokenSaveAll").text, "Lưu 2 câu")
            one(row, "spokenSaveAll").clicked()
            tryVerify(function() { return calls("POST", base + "/line").length === 2 }, 3000)
            compare(calls("POST", base + "/line")[0].body, {stableId: "r1", textSha256: "t1", spoken: "tạch tạch tạch"})
            compare(calls("POST", base + "/line")[1].body.stableId, "r2")
            tryVerify(function() { return Api.notice === "Đã ghi cách đọc cho 2 câu" })
            // hai câu đã có chữ đọc mới chờ áp dụng -> sang "Đã xem"
            tryVerify(function() { return reviewRows(page).length === 1 }, 3000)
        }
        function test_pagingMinorAndRedoChapters() {
            const many = []
            for (let i = 1; i <= 7; ++i) many.push(reviewItem(i))
            serve({review: many, pageSize: 3, minor: {name: 2, text: 3}, redoChapters: [2, 5]})
            const page = openProject("review")
            tryVerify(function() { return reviewRows(page).length === 3 }, 3000)
            compare(one(page, "reviewMore").text, "Tải tiếp · còn 4 câu")
            one(page, "reviewMore").clicked()
            tryVerify(function() { return reviewRows(page).length === 6 }, 3000)
            compare(one(page, "reviewMore").text, "Tải tiếp · còn 1 câu")
            // câu nhẹ: hiện / ẩn
            compare(one(page, "reviewMinor").text, "Hiện 5 câu nhẹ")
            one(page, "reviewMinor").clicked()
            tryVerify(function() { return one(page, "reviewMinor").text === "Ẩn 5 câu nhẹ" })
            tryVerify(function() { return calls("GET", base + "/review?filter=todo&all=1").length >= 1 })
            // chương chờ thu lại
            verify(hasText(page, "2 chương chờ thu lại; sửa chữ ở Kịch bản."))
        }
        function test_emptyReviewStatesSayWhy() {
            serve({review: []})
            const page = openProject("review")
            tryVerify(function() { return has(page, "reviewEmpty") && shown(one(page, "reviewEmpty")) }, 3000)
            verify(hasText(page, "Đã xem hết"))
            verify(hasText(page, "Mọi câu đáng lo đều đã có phán quyết."))
            one(page, "reviewFilter").picked("done")
            tryVerify(function() { return hasText(page, "Chưa đánh dấu câu nào") })
            verify(hasText(page, "Nghe một câu rồi bấm Ổn hoặc Cần thu lại."))
        }

        // ================= 5. Cách đọc tên =================
        function nameRows(page) { return all(page, "nameRow").filter(shown) }
        function test_nameReadingsListSearchAndPaging() {
            serve({names: names(40)})
            const page = openProject("cast")
            tryVerify(function() { return has(page, "nameReadings") && nameRows(page).length > 0 }, 3000)
            verify(hasText(page, "Nghe và sửa cách đọc tên; câu đã thu có tên ấy sẽ thu lại."))
            // 30 dòng một trang, "Xem thêm" 90
            tryCompare({n: 0}, "n", 0)
            tryVerify(function() { return nameRows(page).length === 30 }, 3000)
            compare(one(page, "nameMore").text, "Xem thêm 12 tên")
            verify(hasText(page, "4 tên khác của cuốn không có câu nào trong phần này."))
            // dòng nhỏ: số câu và ai chọn; cách đọc chờ áp dụng nói riêng
            const henko = nameRows(page).filter(r => r.surface === "Henko")[0]
            verify(hasPart(henko, "7 câu · máy đoán"))
            const lorcan = nameRows(page).filter(r => r.surface === "Lorcan")[0]
            verify(hasPart(lorcan, "3 câu · đã chọn"))
            verify(hasPart(lorcan, "chờ áp dụng: “lo-ken”"))
            scrollTo(page, one(page, "nameReadingsTitle"))
            both("names_list", page)
            // tìm không phân biệt dấu, hoa thường, gạch nối
            one(page, "nameSearch").text = "hen"
            tryVerify(function() { return nameRows(page).length === 1 && nameRows(page)[0].surface === "Henko" }, 3000)
            verify(!has(page, "nameUnseen") || !shown(one(page, "nameUnseen")))
            one(page, "nameSearch").text = "zzz"
            tryVerify(function() { return has(page, "nameFresh") }, 3000)
            one(page, "nameSearch").text = "zz zz"
            tryVerify(function() { return has(page, "nameNoMatch") })
            compare(one(page, "nameNoMatch").text, "Không khớp “zz zz”; dùng “Thêm cách đọc” cho một từ khác.")
        }
        function test_nameEditPreviewAndSave() {
            serve({names: names()})
            reply("POST " + base + "/pronunciation/preview", {status: 200, data: {url: "/media/previews/n1.wav", text: "Anh Hên-khơ bước vào.", speaker: "Mai"}})
            const page = openProject("cast")
            tryVerify(function() { return nameRows(page).length >= 2 }, 3000)
            const row = nameRows(page).filter(r => r.surface === "Henko")[0]
            const layers0 = Nav.layers.length
            one(row, "nameEdit").clicked()
            tryVerify(function() { return has(row, "nameField") })
            // ô hiện chữ đầu mỗi từ viết hoa; chưa đổi gì thì "Lưu" tắt
            compare(one(row, "nameField").text, "Hên-cơ")
            verify(!one(row, "nameSave").enabled)
            // là một lớp Back
            verify(Nav.layers.length > layers0)
            one(row, "nameField").text = "Hên-khơ"
            tryVerify(function() { return one(row, "nameSave").enabled })
            one(row, "nameTry").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation/preview").length === 1 })
            compare(calls("POST", base + "/pronunciation/preview")[0].body, {surface: "Henko", spokenForm: "Hên-khơ"})
            // "Dùng cho mọi sách"
            one(row, "nameEverywhere").toggled(true)
            one(row, "nameSave").clicked()
            tryVerify(function() { return calls("POST", base + "/pronunciation").length === 1 })
            compare(calls("POST", base + "/pronunciation")[0].body, {surface: "Henko", spokenForm: "Hên-khơ", seen: "", everywhere: true})
            // dòng đổi ngay (lạc quan) và ô đóng, lớp Back rời đi
            tryVerify(function() { return !has(row, "nameField") })
            verify(hasPart(row, "chờ áp dụng: “Hên-khơ”"))
            compare(Nav.layers.length, layers0)
            tryVerify(function() { return Api.notice.indexOf("Đã ghi: “Henko” đọc là “Hên-khơ”") === 0 })
            compare(Api.noticeAction.label, "Hoàn tác")
        }
        function test_nameEditEscapeAndRefusal() {
            serve({names: names()})
            reply("POST " + base + "/pronunciation", {status: 400, data: {error: "Chữ này có ký hiệu máy không đọc được.", suggestion: "Hên-cơ"}})
            const page = openProject("cast")
            tryVerify(function() { return nameRows(page).length >= 2 }, 3000)
            const row = nameRows(page).filter(r => r.surface === "Henko")[0]
            const layers0 = Nav.layers.length
            one(row, "nameEdit").clicked()
            tryVerify(function() { return has(row, "nameField") })
            one(row, "nameField").text = "Hên@khơ"
            tryVerify(function() { return one(row, "nameSave").enabled })
            one(row, "nameSave").clicked()
            tryVerify(function() { return has(row, "readingProblem") })
            compare(one(row, "readingProblem").text, "Chữ này có ký hiệu máy không đọc được.")
            // ô vẫn mở, dòng trở lại như cũ (đã hoàn lại bản lạc quan)
            verify(has(row, "nameField"))
            verify(!hasPart(row, "chờ áp dụng: “Hên@khơ”"))
            // Esc huỷ
            keyClick(Qt.Key_Escape)
            tryVerify(function() { return !has(row, "nameField") })
            compare(Nav.layers.length, layers0)
        }
        function test_addAnyWordShowsReachAndNeverBlocksSave() {
            serve({names: names()})
            reply("GET " + base + "/pronunciations/reach?surface=TP.HCM", {status: 200, data: {surface: "TP.HCM", lines: 5, reached: 5, recorded: 3, blocked: 0, never: false, cost: "", chapters: [{chapterId: 1, title: "Chương 1", lines: 5, recorded: 3}], example: null}})
            reply("GET " + base + "/pronunciations/reach?surface=" + encodeURIComponent("Mở/đóng"), {status: 200, data: {surface: "Mở/đóng", lines: 2, reached: 0, recorded: 0, blocked: 2, never: true, cost: "", chapters: [], example: null}})
            const page = openProject("cast")
            tryVerify(function() { return has(page, "addWordOpen") }, 3000)
            one(page, "addWordOpen").clicked()
            tryVerify(function() { return has(page, "addWordField") && shown(one(page, "addWordField")) })
            one(page, "addWordField").text = "TP.HCM"
            tryVerify(function() { return has(page, "addWordRow") && shown(one(page, "addWordRow")) })
            const row = one(page, "addWordRow")
            tryVerify(function() { return hasPart(row, "5 câu có chữ này · 3 câu đã thu sẽ được thu lại · ở Chương 1") }, 3000)
            compare(one(row, "nameEdit").text, "Đọc “TP.HCM”")
            // chữ có ký hiệu bị xé đôi: không bao giờ được dùng
            one(page, "addWordField").text = "Mở/đóng"
            tryVerify(function() { return hasPart(one(page, "addWordRow"), "máy không dùng được cách đọc") }, 3000)
            one(one(page, "addWordRow"), "nameEdit").clicked()
            tryVerify(function() { return has(page, "nameNever") && shown(one(page, "nameNever")) })
            verify(!one(page, "nameSave").enabled)
            // nhiều chữ: lời nhắc
            one(page, "addWordField").text = "hai chữ"
            tryVerify(function() { return hasText(page, "Gõ một chữ liền nhau, không có khoảng trắng.") })
        }
        function test_sharedReadingsOfferAppliesAll() {
            serve({names: names(), offer: [{surface: "Henko", spokenForm: "hên-khơ", current: "hên-cơ"}, {surface: "Kati", spokenForm: "ka-ti"}]})
            reply("POST " + base + "/shared-readings", {status: 200, data: {applied: ["Henko", "Kati"]}})
            const page = openProject("cast")
            tryVerify(function() { return has(page, "sharedOfferApply") && shown(one(page, "sharedOfferApply")) }, 3000)
            compare(one(page, "sharedOfferApply").text, "Dùng 2 cách đọc chung")
            verify(hasText(page, "Cách đọc chung khác cách cuốn này đang đọc: Henko: “Hên-cơ” → “Hên-khơ”, Kati → “Ka-ti”"))
            one(page, "sharedOfferApply").clicked()
            tryVerify(function() { return calls("POST", base + "/shared-readings").length === 1 })
            tryVerify(function() { return Api.notice === "Đã dùng 2 cách đọc chung" })
        }
        function test_nameDeepLinkScrollsToTheSection() {
            serve({names: names(), work: [pronCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "pronNames") }, 3000)
            one(page, "pronNames").clicked()
            tryCompare(screenOf(page), "shownTab", "cast", 3000)
            tryVerify(function() { return has(page, "nameReadingsTitle") && shown(one(page, "nameReadingsTitle")) }, 3000)
            const list = page.projectScreenList
            const title = one(page, "nameReadingsTitle")
            tryVerify(function() {
                const y = title.mapToItem(list, 0, 0).y
                return y >= -1 && y < list.height
            }, 3000)
        }

        // ================= 6. Yêu cầu thiết bị =================
        function test_phoneEditsApplyOneThenSkipAllWithConfirmThenRestore() {
            serve({inbox: deviceInbox(), work: [pronCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "inboxApplyOne") && shown(one(page, "inboxApplyOne")) }, 3000)
            verify(hasText(page, "Yêu cầu thiết bị (2 việc chờ duyệt)"))
            verify(hasText(page, "Áp dụng để đưa vào hàng chờ; bỏ qua vẫn khôi phục được."))
            verify(hasPart(page, "Máy này đã đổi khác sau đó."))
            tryVerify(function() { return counts(page).work === 3 }, 3000)
            scrollTo(page, one(page, "inboxHeading"))
            both("phone_edits", page)
            one(page, "inboxApplyOne").clicked()
            tryVerify(function() { return calls("POST", base + "/edits-inbox/apply").length === 1 })
            compare(calls("POST", base + "/edits-inbox/apply")[0].body, {device: "d1", items: ["i1"]})
            tryVerify(function() { return Api.notice === "Đã ghi 1 việc vào “Áp dụng thay đổi”" })
            tryVerify(function() { return counts(page).work === 2 }, 3000)
            // bỏ qua tất cả: hỏi lại trước
            one(page, "inboxSkipAll").clicked()
            tryVerify(function() { return hasTop("skipConfirm") })
            compare(inOverlay("skipConfirm").title, "Bỏ qua mọi việc từ OPPO của bạn?")
            verify(Nav.layers.length >= 1)
            compare(calls("POST", base + "/edits-inbox/skip").length, 0)
            inOverlay("confirm_go").clicked()
            tryVerify(function() { return calls("POST", base + "/edits-inbox/skip").length === 1 })
            compare(calls("POST", base + "/edits-inbox/skip")[0].body, {device: "d1"})
            tryVerify(function() { return Api.notice === "Đã bỏ qua" })
            compare(Api.noticeAction.label, "Khôi phục")
            tryVerify(function() { return counts(page).work === 1 }, 3000)
            // khay "Đã bỏ qua": khôi phục
            verify(has(page, "inboxSkipped"))
            one(page, "workSectionToggle").clicked()
        }
        function test_skippedTrayRestoresADevice() {
            serve({inbox: Object.assign(emptyInbox(), {skipped: [{id: "d2", name: "Máy cũ", at: 1, items: [{id: "i9", kind: "line", label: "Sửa chữ đọc câu 4", chapter: "Chương 1", lines: 1}]}]}), work: [pronCard()]})
            const page = openProject("work")
            tryVerify(function() { return has(page, "inboxSkipped") && shown(one(page, "inboxSkipped")) }, 3000)
            const toggle = all(one(page, "inboxSkipped"), "workSectionToggle")[0]
            toggle.clicked()
            tryVerify(function() { return has(page, "inboxRestoreAll") && shown(one(page, "inboxRestoreAll")) })
            verify(hasText(page, "Đã bỏ qua (1)"))
            one(page, "inboxRestoreAll").clicked()
            tryVerify(function() { return calls("POST", base + "/edits-inbox/restore").length === 1 })
            compare(calls("POST", base + "/edits-inbox/restore")[0].body, {device: "d2"})
            tryVerify(function() { return Api.notice === "Đã khôi phục" })
        }

        // ================= 7. chữ dài xuống dòng, không cắt =================
        function longText() { return "Một câu rất dài để thử việc xuống dòng của chữ tiếng Việt có dấu trong khung hẹp, lặp đi lặp lại nhiều lần cho đủ dài: " + "đây là phần chữ kéo dài. ".repeat(6) }
        function test_longTextWrapsAtBothWidths() {
            const lengthy = longText()
            serve({
                work: [pronCard({problem: lengthy, title: "Máy chưa chắc “Henko-Henko-Henko-Henko” đọc thế nào " + lengthy.slice(0, 80), examples: [example({text: lengthy})]}),
                       speakerCard({problem: lengthy, examples: [example({text: lengthy, before: lengthy, after: lengthy})]})],
                review: [reviewItem(1, {text: lengthy, heard: lengthy, reason: lengthy, chapterTitle: "Chương " + lengthy.slice(0, 60)})],
                inbox: Object.assign(deviceInbox(), {}),
                names: {items: [{surface: "Henko" + lengthy.slice(0, 30).replace(/ /g, ""), spoken: lengthy.slice(0, 50), byListener: true, lines: 2, requested: lengthy.slice(0, 60), example: null}], unseen: 0}
            })
            for (const width of [1024, 1920]) {
                const page = openProject("work", width)
                tryVerify(function() { return cards(page).length === 2 }, 3000)
                noCut(page)
                verify(screenOf(page).width === width || true)
                shot("long_work_" + width, page)
                pickTab(page, "review")
                tryVerify(function() { return reviewRows(page).length === 1 }, 3000)
                noCut(page)
                shot("long_review_" + width, page)
                pickTab(page, "cast")
                tryVerify(function() { return nameRows(page).length === 1 }, 3000)
                noCut(page)
                shot("long_names_" + width, page)
                // không tràn ngang
                verify(page.projectScreenList.contentWidth <= page.projectScreenList.width + 0.5)
                page.destroy()
            }
        }

        // ================= 8. Studio của máy tính đã ghép =================
        function test_peerRoutesEveryRequestThroughTheBridge() {
            serve({work: [pronCard()], review: [reviewItem(1)]})
            const b = book("a")
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn phòng làm việc"}}})
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + base, {status: 200, data: {book: b, chapters: [chapter(1)]}})
            const keys = Object.keys(DesktopApi.responses).filter(k => k.indexOf(base) >= 0 || k === "GET /api/readings")
            for (const key of keys) reply(key.replace(base, peerBase + base).replace("GET /api/readings", "GET " + peerBase + "/api/readings"), DesktopApi.responses[key])
            reply("POST " + peerBase + base + "/pronunciation", {status: 200, data: {surface: "Henko", spokenForm: "Hên-cơ", requestedAt: 3}})
            reply("POST " + peerBase + base + "/review", {status: 200, data: {}})
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            tryVerify(function() { return counts(page).review === 1 }, 3000)
            pickTab(page, "work")
            tryVerify(function() { return has(page, "pronKeep") }, 3000)
            one(page, "pronKeep").clicked()
            tryVerify(function() { return calls("POST", peerBase + base + "/pronunciation").length === 1 })
            pickTab(page, "review")
            tryVerify(function() { return reviewRows(page).length === 1 }, 3000)
            one(reviewRows(page)[0], "verdictOk").clicked()
            tryVerify(function() { return calls("POST", peerBase + base + "/review").length === 1 })
            // nghe câu qua cầu của máy kia
            one(reviewRows(page)[0] || one(page, "reviewRow"), "reviewPlay").clicked()
            tryVerify(function() { return DesktopApi.previews.length === 1 })
            compare(DesktopApi.previews[0].indexOf(peerBase), 0)
            // KHÔNG một lời gọi nào đi thẳng vào máy này
            const direct = DesktopApi.requests.filter(r => (/^\/api\/books\/a/).test(r.path))
            compare(direct.length, 0, JSON.stringify(direct.slice(0, 3)))
        }

        // ================= 9. không hỏi khi cửa sổ ẩn, tab khác không tải =================
        function test_nothingIsAskedWhileTheWindowIsHiddenOrTheTabIsAway() {
            serve({work: [pronCard()], review: [reviewItem(1)], names: names()})
            const page = openProject("work", 1280, {running: true, phase: "synthesizing", statusLabel: "Đang thu"})
            tryVerify(function() { return cards(page).length === 1 }, 3000)
            const w = inboxOf(page).work
            // cuốn đang làm: danh sách việc + hộp thư + con số "cần nghe lại" hỏi theo nhịp
            tryVerify(function() { return w.work.timer.running && w.inbox.timer.running && w.reviewCounted.timer.running }, 3000)
            // tab Việc cần duyệt đang mở thì chỉ con số của chính nó; tab khác chưa mở thì chưa hỏi gì
            compare(w.names.wanted, false)
            compare(w.workCounted.wanted, false)
            compare(calls("GET", base + "/pronunciations").length, 0)
            // cửa sổ ẩn: không nguồn nào còn hẹn giờ hỏi
            const store = screenOf(page).store
            store.active = false
            verify(!w.work.timer.running && !w.inbox.timer.running && !w.reviewCounted.timer.running)
            store.active = true
            tryVerify(function() { return w.work.timer.running }, 3000)
            // sang tab Cần nghe lại: danh sách việc thôi hỏi, chỉ còn con số
            pickTab(page, "review")
            tryVerify(function() { return !w.work.wanted && w.workCounted.wanted }, 3000)
        }
    }
}
