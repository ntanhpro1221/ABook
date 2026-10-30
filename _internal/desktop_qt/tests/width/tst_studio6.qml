import QtQuick
import QtTest
import QtQuick.Controls.Basic as C
import ABook
import "../../qml/ScriptLogic.js" as S

// Studio S6: tab "Kịch bản" của dự án (ScriptTab.tsx): đọc cả chương như kịch bản, đổi người nói (phím số, ô chọn người, tạo người mới), "Duyệt N câu",
// thu lại câu, sửa cách đọc câu (lời kể thành lời thoại với người mới: hai bước /line rồi /speaker), tìm chữ, bộ lọc, chip người nói, mở từ thẻ việc,
// Studio của máy khác. Kèm bản chép test của web: scriptFind.test.ts, scriptFilter.test.ts. Ảnh sáng / tối ghi ra build/d2shots/s6_*.png.
Item {
    id: host
    width: 1280
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    readonly property var overlay: C.Overlay.overlay
    Component { id: studioFactory; StudioScreen {} }

    // ---- scriptFind.test.ts + scriptFilter.test.ts (cùng ca, cùng chữ) ----
    TestCase {
        name: "ScriptLogic"

        function line(stableId, kind, current, extra) {
            return Object.assign({segmentId: 1, stableId: stableId, textSha256: stableId, seq: 0, paragraph: 0, text: stableId, kind: kind, speaker: current, current: current,
                                  label: current, editable: kind !== "narration", hasAudio: false, hint: null, wish: null, emotion: null, intensity: null, lineWish: null, spoken: null}, extra || {})
        }
        function lines() {
            return [
                line("a", "narration", "NARRATOR"),
                line("b", "dialogue", "LUCIEN"),
                line("c", "dialogue", "HEIDI", {hint: {kind: "turn", note: "x"}}),
                line("d", "thought", "LUCIEN", {hint: {kind: "unsure", note: "y"}}),
                line("e", "dialogue", S.UNNAMED),
                line("f", "dialogue", "HEIDI", {wish: {value: "LUCIEN", label: "Lucien", state: "pending"}})
            ]
        }
        function ids(shown) { return shown.map(entry => entry.line.stableId) }

        // ô tìm chữ trong kịch bản
        function test_findIgnoresCaseAndMarksAndReturnsOriginalRanges() {
            const text = "Tuấn nhìn Đác-lát rồi Tuấn đi."
            compare(S.findRanges(text, "tuan").map(r => text.slice(r[0], r[1])), ["Tuấn", "Tuấn"])
            compare(S.findRanges(text, "dac-lat").map(r => text.slice(r[0], r[1])), ["Đác-lát"])
            compare(S.findRanges(text, "  "), [])
            compare(S.findRanges(text, "xyz"), [])
        }
        function test_findCoversTheWholeDecomposedCharacter() {
            const text = "Tuấn".normalize("NFD") + " đi"
            const range = S.findRanges(text, "tuan")[0]
            compare(text.slice(range[0], range[1]), "Tuấn".normalize("NFD"))
        }
        function test_findSplitsForHighlightAndWraps() {
            compare(S.splitByRanges("abcabc", [[1, 2], [4, 5]]), [["a", false], ["b", true], ["ca", false], ["b", true], ["c", false]])
            compare([S.wrapIndex(3, 3), S.wrapIndex(-1, 3), S.wrapIndex(0, 0)], [0, 2, 0])
        }
        // chip người nói lọc câu
        function test_filterWithoutPersonIsAsBefore() {
            compare(ids(S.visibleLines(lines(), "all", null)), ["a", "b", "c", "d", "e", "f"])
            compare(ids(S.visibleLines(lines(), "speech", null)), ["b", "c", "d", "e", "f"])
        }
        function test_filterByPersonKeepsOnlyTheirSpeechCountingPendingChanges() {
            compare(ids(S.visibleLines(lines(), "all", "LUCIEN")), ["b", "d", "f"])
            compare(ids(S.visibleLines(lines(), "all", "HEIDI")), ["c"])
        }
        function test_unnamedChipAndDoubtFilter() {
            compare(ids(S.visibleLines(lines(), "all", S.UNNAMED)), ["e"])
            compare(ids(S.visibleLines(lines(), "doubt", "LUCIEN")), ["d"])
            compare(S.visibleLines(lines(), "doubt", null).map(entry => [entry.line.stableId, entry.context]), [["b", true], ["c", false], ["d", false]])
        }
        // phần riêng của bản Qt: ô đếm, chương mở đầu, chú giải
        function test_countStartChapterAndLegend() {
            compare(S.findCount("", 0, 0), "")
            compare(S.findCount("x", 0, 0), "Không có")
            compare(S.findCount("x", 3, 2), "2/2")
            compare(S.startChapter([{chapterId: 1, hints: 0, speech: 0}, {chapterId: 2, hints: 0, speech: 3}, {chapterId: 3, hints: 2, speech: 1}], 0), 3)
            compare(S.startChapter([{chapterId: 1, hints: 0, speech: 0}, {chapterId: 2, hints: 0, speech: 3}], 1), 1)
            compare(S.legend([{value: "A", label: "A", lines: 1}], 2).map(item => item.badge), ["1", "?"])
            compare(S.markedHtml("a<b", [[2, 3]], "#ff0"), "a&lt;<span style=\"background-color:#ff0\">b</span>")
        }
    }

    TestCase {
        id: test
        name: "Studio6"
        when: windowShown

        readonly property string peerId: "c0ffee000001"
        readonly property string peerBase: "/api/peers/c0ffee000001/studio"
        readonly property string base: "/api/books/a"
        property var server: ({})

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
        function all2(item, test, out) {
            out = out || []
            if (test(item)) out.push(item)
            for (const child of item.children || []) all2(child, test, out)
            return out
        }
        function shot(name, item) {
            const target = item || host
            tryVerify(function() { return all2(target, n => n.settled === false && n.reveal !== undefined).length === 0 }, 3000)
            // Chờ khung hình đứng yên (chuyển tiếp đổi giao diện sáng / tối còn đang mờ dần thì ảnh lẫn bóng của khung trước)
            tryVerify(function() { waitForRendering(target); const a = grabImage(target); waitForRendering(target); return a.equals(grabImage(target)) }, 3000)
            const path = Qt.resolvedUrl("../../build/d2shots/s6_" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            grabImage(target).save(path)
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
        function book(over) {
            return Object.assign({
                id: "a", title: "Cuốn a", statusLabel: "Đang dừng", running: false, starting: false, paused: "", canPause: false, stopping: false,
                phase: "done", queuePosition: 0, pendingChanges: 0, audioSeconds: 5400, eta: null, startError: "", lastError: "", runEnd: null,
                createdAt: stamp() - 86400, updatedAt: stamp() - 3600, path: "D:\\Sách\\a", castLocked: true, precast: null,
                chapters: {total: 2, completed: 2, redo: 0, missingAudio: 0, failed: 0, working: 0},
                segments: {total: 120, analyzed: 120, recorded: 120, finished: 120, failed: 0, warnings: 0},
                progress: {overall: 1, analysis: 1, synthesis: 1}, settings: {narrator: "Mai", profile: "balanced", profileLabel: "Cân bằng"}
            }, over || {})
        }
        function chapter(id) {
            return {id: id, index: id, title: "Chương " + id, displayTitle: "Chương " + id, subtitle: "", fullTitle: "Chương " + id, status: "completed", statusLabel: "Đã thu",
                    segments: {total: 10, analyzed: 10, recorded: 10, finished: 10, failed: 0, warnings: 0}, seconds: 300, playable: true, redo: false,
                    startedAt: stamp() - 7200, completedAt: stamp() - 3600, lastError: ""}
        }
        function line(stableId, seq, paragraph, kind, current, text, extra) {
            const label = {NARRATOR: "Người kể", LUCIEN: "Lucien", HEIDI: "Heidi", UNNAMED: "Chưa rõ"}[current] || current
            return Object.assign({segmentId: 100 + seq, stableId: stableId, textSha256: "h-" + stableId, seq: seq, paragraph: paragraph, text: text, kind: kind, speaker: current,
                                  current: current, label: label, editable: kind !== "narration", hasAudio: true, hint: null, wish: null, emotion: "neutral", intensity: 1,
                                  lineWish: null, spoken: null, retake: null, verdict: null}, extra || {})
        }
        function chapterOne(over) {
            return Object.assign({
                chapterId: 1, index: 1, title: "Chương 1", previous: null, next: 2, castReady: true, firstPerson: null,
                cast: [{value: "LUCIEN", label: "Lucien", lines: 2}, {value: "HEIDI", label: "Heidi", lines: 1}],
                others: [{value: "MAI", label: "Mai", lines: 9}, {value: "TUAN_ANH", label: "Tuấn Anh", lines: 4}],
                lines: [
                    line("n1", 0, 0, "narration", "NARRATOR", "Tuấn nhìn ra cửa."),
                    line("d1", 1, 1, "dialogue", "LUCIEN", "“Ai đó?” Tuấn hỏi."),
                    line("d2", 2, 1, "dialogue", "HEIDI", "“Là tôi đây.”", {hint: {kind: "turn", note: "Máy nghi câu này là của người khác.", suggest: "LUCIEN"}}),
                    line("t1", 3, 2, "thought", "LUCIEN", "Lạ thật.", {hasAudio: false}),
                    line("d3", 4, 3, "dialogue", "UNNAMED", "“Mở cửa!”", {hasAudio: false, hint: {kind: "unsure", note: "Máy chưa biết ai nói."}}),
                    line("n2", 5, 4, "narration", "NARRATOR", "Gió lùa vào phòng.")
                ]}, over || {})
        }
        function chapterTwo() {
            return {chapterId: 2, index: 2, title: "Chương 2", previous: 1, next: null, castReady: true, firstPerson: null,
                    cast: [{value: "HEIDI", label: "Heidi", lines: 1}], others: [{value: "LUCIEN", label: "Lucien", lines: 2}],
                    lines: [line("x0", 0, 0, "narration", "NARRATOR", "Sáng hôm sau."), line("x1", 1, 1, "dialogue", "HEIDI", "“Đi thôi.”", {hint: {kind: "turn", note: "Máy nghi."}})]}
        }
        function contents() {
            return {castReady: true, chapters: [{chapterId: 1, index: 1, title: "Chương 1", lines: 6, speech: 4, hints: 2, decided: 0},
                                                {chapterId: 2, index: 2, title: "Chương 2", lines: 2, speech: 1, hints: 1, decided: 0}]}
        }
        function library(books) { return {status: 200, data: {root: "D:\\Sách", rootMissing: false, books: books}} }
        function clone(v) { return JSON.parse(JSON.stringify(v)) }

        // ---- máy chủ giả có trạng thái (prefix: đường của máy khác) ----
        function serve(extra, prefix) {
            const p = prefix || ""
            server = Object.assign({contents: contents(), chapters: {1: chapterOne(), 2: chapterTwo()}, stamp: 1, speakerFails: false}, extra || {})
            reply("GET " + p + base + "/casting", function() { return {status: 200, data: clone(server.contents)} })
            reply("GET " + p + base + "/casting/1", function() { return {status: 200, data: clone(server.chapters[1])} })
            reply("GET " + p + base + "/casting/2", function() { return {status: 200, data: clone(server.chapters[2])} })
            reply("GET " + p + base + "/casting/stamp", function() { return {status: 200, data: {stamp: server.stamp}} })
            reply("GET " + p + base + "/work", {status: 200, data: {items: [], counts: {}}})
            reply("GET " + p + base + "/work?count=1", {status: 200, data: {count: 0}})
            reply("GET " + p + base + "/pronunciations", {status: 200, data: {items: [{surface: "Tuấn", spoken: "tuấn", byListener: false, lines: 3, requested: null, example: null}], unseen: 0}})
            reply("POST " + p + base + "/speaker", function(body) {
                if (server.speakerFails && !body.withdraw) return {status: 500, data: {detail: "Máy bận"}}
                return {status: 200, data: {lines: (body.lines || []).length, requestedAt: 77}}
            })
            reply("POST " + p + base + "/review", function(body) {
                const ids = (body.lines || []).map(item => item.stableId)
                for (const item of server.chapters[1].lines) if (ids.indexOf(item.stableId) >= 0) { item.retake = body.verdict === "redo" ? "pending" : null; item.verdict = body.verdict }
                return {status: 200, data: {lines: ids.length, requestedAt: 55}}
            })
            reply("POST " + p + base + "/line", function(body) { return {status: 200, data: {requestedAt: body.withdraw ? 0 : 88}} })
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
        function makeStudio(width) {
            const page = createTemporaryObject(studioFactory, host, {width: width || 1280, height: 900})
            verify(page !== null)
            return page
        }
        function openProject(width, b) {
            const row = b || book()
            reply("GET /api/library", library([row]))
            reply("GET " + base, {status: 200, data: {book: row, chapters: [chapter(1), chapter(2)]}})
            const page = makeStudio(width)
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            tryVerify(function() { return all(page, "projectHeader").filter(shown).length > 0 }, 3000)
            return page
        }
        function screenOf(page) { return page.projectScreenList.parent }
        function openScript(width, b) {
            const page = openProject(width, b)
            screenOf(page).pickTab("script")
            tryCompare(screenOf(page), "shownTab", "script", 3000)
            return page
        }
        function tabOf(page) { const loader = one(page, "scriptTab"); tryVerify(function() { return loader.item !== null }, 3000); return loader.item }
        function rows(page) { return all(page, "scriptRow").filter(shown) }
        function ready(page, count) { tryVerify(function() { return rows(page).length === count }, 3000, "số câu hiện ra") }
        function rowOf(page, stableId) { return rows(page).filter(r => r.line.stableId === stableId)[0] }
        function scrollTo(page, item) {
            const list = page.projectScreenList
            list.contentY = Math.max(list.originY, Math.min(list.originY + list.contentHeight - list.height + list.bottomMargin, item.mapToItem(list.contentItem, 0, 0).y - 24))
        }
        function focusLine(page, stableId) {
            const tab = tabOf(page)
            tab.focusRow(tab.speechRows.find(item => item.stableId === stableId), false)
            tryCompare(tab, "active", stableId)
            tryVerify(function() { return rowOf(page, stableId).activeFocus })
        }

        // ================= 1. dựng tab =================
        function test_tabShowsTheChapterLinesLegendAndFooter() {
            serve()
            const page = openScript()
            ready(page, 6)
            // chương mở đầu: chương đầu tiên có chỗ máy nghi
            compare(calls("GET", base + "/casting/1").length >= 1, true)
            verify(hasText(page, "Bấm tên để đổi người nói; dấu vàng là câu cần xem."))
            compare(one(page, "scriptChapter").Accessible.name, "Chương")
            verify(hasText(page, "Chương 1"))
            // chú giải: người theo số, rồi "Chưa rõ" với dấu ?
            compare(all(page, "legendName").filter(shown).map(t => t.text), ["Lucien", "Heidi", "Chưa rõ"])
            verify(hasText(page, "?"))
            // bộ lọc như web, có số chỗ nghi
            verify(hasText(page, "Cả chương"))
            verify(hasText(page, "Chỉ lời nói"))
            verify(hasText(page, "Máy nghi · 2"))
            // câu nghi có lời nghi + nút gán theo gợi ý
            verify(hasText(page, "Máy nghi câu này là của người khác."))
            verify(has(page, "hintAssign"))
            // chân chương
            verify(hasText(page, "Duyệt 2 câu"))
            compare(one(page, "scriptFooterNote").text, "Coi người nói của các câu chưa ai quyết là đúng, trừ 2 câu máy còn nghi: máy thôi hỏi; Ctrl+Z để hoàn tác.")
            verify(has(page, "scriptNextChapter"))
            // không còn câu "chưa mở"
            verify(!hasText(page, "Mục này chưa mở trong bản này."))
            noCut(page)
            scrollTo(page, one(page, "scriptIntro"))
            both("tab", page)
        }
        function test_emptyBookAndNotReadyChapterSaySo() {
            serve({contents: {castReady: false, chapters: []}})
            const page = openScript()
            tryVerify(function() { return has(page, "scriptEmpty") }, 3000)
            verify(hasText(page, "Chưa có kịch bản"))
            verify(hasText(page, "Kịch bản hiện ra khi máy đã phân tích xong chương đầu tiên: câu nào là lời kể, câu nào của ai."))
        }
        function test_chapterBeforeCastingCannotBeEdited() {
            serve({chapters: {1: chapterOne({castReady: false}), 2: chapterTwo()}})
            const page = openScript()
            ready(page, 6)
            tryVerify(function() { return has(page, "scriptNotReady") })
            verify(hasText(page, "Sửa người nói được sau bước phân vai."))
            verify(!has(page, "scriptConfirm"))
            one(rowOf(page, "d1"), "speakerChip").clicked()
            verify(!has(page, "scriptSpeakerMenu"), "chưa phân vai: không mở ô chọn người")
            focusLine(page, "d1")
            keyClick(Qt.Key_2)
            compare(calls("POST", base + "/speaker").length, 0)
        }

        // ================= 2. lọc, chip người nói, tìm chữ =================
        function test_filterAndPersonChipNarrowTheLines() {
            serve()
            const page = openScript()
            ready(page, 6)
            one(page, "scriptFilter").picked("speech")
            ready(page, 4)
            one(page, "scriptFilter").picked("doubt")
            ready(page, 4)
            // "Máy nghi": câu nói liền trước là ngữ cảnh
            compare(rows(page).map(r => [r.line.stableId, r.context]), [["d1", true], ["d2", false], ["t1", true], ["d3", false]])
            one(page, "scriptFilter").picked("all")
            ready(page, 6)
            const lucien = all(page, "legendChip").filter(shown).filter(c => c.modelData.person.value === "LUCIEN")[0]
            lucien.clicked()
            ready(page, 2)
            compare(rows(page).map(r => r.line.stableId), ["d1", "t1"])
            verify(has(page, "legendAll"))
            one(page, "legendAll").clicked()
            ready(page, 6)
            // chip "Chưa rõ" lọc được; lọc trống thì nói vì sao
            all(page, "legendChip").filter(shown).filter(c => c.modelData.person.value === "UNNAMED")[0].clicked()
            ready(page, 1)
            one(page, "scriptFilter").picked("doubt")
            ready(page, 1)
            const heidi = all(page, "legendChip").filter(shown).filter(c => c.modelData.person.value === "UNNAMED")[0]
            heidi.clicked()
            all(page, "legendChip").filter(shown).filter(c => c.modelData.person.value === "HEIDI")[0].clicked()
            ready(page, 1)
            one(page, "scriptFilter").picked("all")
            ready(page, 1)
        }
        function test_findCountsMatchesAndEnterCycles() {
            serve()
            const page = openScript()
            ready(page, 6)
            const find = one(page, "scriptFind")
            find.text = "tuan"
            tryCompare(one(page, "scriptFindCount"), "text", "1/2")
            verify(rowOf(page, "n1").markNow)
            verify(one(rowOf(page, "n1"), "lineText").text.indexOf("<span") >= 0, "chỗ khớp được tô")
            find.forceActiveFocus()
            keyClick(Qt.Key_Return)
            tryCompare(one(page, "scriptFindCount"), "text", "2/2")
            verify(rowOf(page, "d1").markNow)
            keyClick(Qt.Key_Return, Qt.ShiftModifier)
            tryCompare(one(page, "scriptFindCount"), "text", "1/2")
            find.text = "khongco"
            tryCompare(one(page, "scriptFindCount"), "text", "Không có")
            find.text = ""
            tryCompare(one(page, "scriptFindCount"), "text", "")
            // "/" từ một câu nhảy vào ô tìm
            focusLine(page, "d1")
            keyClick(Qt.Key_Slash)
            tryVerify(function() { return find.activeFocus })
        }

        // ================= 3. gán người nói =================
        function test_numberKeyAssignsMovesOnAndCtrlZUndoes() {
            serve()
            const page = openScript()
            ready(page, 6)
            focusLine(page, "d1")
            keyClick(Qt.Key_2)
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            const body = calls("POST", base + "/speaker")[0].body
            compare(body.lines, [{stableId: "d1", textSha256: "h-d1"}])
            compare(body.speaker, "HEIDI")
            compare(body.newGender, "")
            compare(body.seen, {d1: ""})
            tryCompare(Api, "notice", "Đã ghi: câu này của Heidi")
            compare(Api.noticeAction.label, "Hoàn tác")
            // sang câu nói kế
            tryCompare(tabOf(page), "active", "d2")
            // Ctrl+Z rút đúng lần vừa ghi
            keySequence(StandardKey.Undo)
            tryVerify(function() { return calls("POST", base + "/speaker").length === 2 })
            const undo = calls("POST", base + "/speaker")[1].body
            compare(undo.withdraw, true)
            compare(undo.requestedAt, 77)
            compare(undo.lines, [{stableId: "d1", textSha256: "h-d1"}])
            // nút trên lời báo dùng chung lần hoàn tác: không rút lần hai
            tryVerify(function() { return Api.notice !== "Đã ghi: câu này của Heidi" })
            keySequence(StandardKey.Undo)
            tryCompare(Api, "notice", "Không còn gì để hoàn tác")
            compare(calls("POST", base + "/speaker").length, 2)
        }
        function test_shiftSelectsAGroupAndOneKeyAssignsAll() {
            serve()
            const page = openScript()
            ready(page, 6)
            focusLine(page, "d1")
            keyClick(Qt.Key_Down, Qt.ShiftModifier)
            keyClick(Qt.Key_Down, Qt.ShiftModifier)
            tryCompare(tabOf(page), "selected", ["d1", "d2", "t1"])
            tryVerify(function() { return has(page, "scriptSelection") && one(page, "scriptSelection").open })
            verify(hasText(page, "Đang chọn 3 câu"))
            verify(hasText(page, "Thu lại 2 câu"))
            keyClick(Qt.Key_1)
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            // cả nhóm, như web: câu đã là của Lucien thì thành "xác nhận"
            compare(calls("POST", base + "/speaker")[0].body.lines, [{stableId: "d1", textSha256: "h-d1"}, {stableId: "d2", textSha256: "h-d2"}, {stableId: "t1", textSha256: "h-t1"}])
            compare(calls("POST", base + "/speaker")[0].body.speaker, "LUCIEN")
        }
        function test_speakerMenuFindsSomeoneElseInTheBook() {
            serve()
            const page = openScript()
            ready(page, 6)
            one(rowOf(page, "d2"), "speakerChip").clicked()
            tryVerify(function() { return has(page, "scriptSpeakerMenu") }, 3000)
            const menu = one(page, "scriptSpeakerMenu")
            verify(hasText(menu, "Máy gợi ý"))
            verify(hasText(menu, "Trong chương này"))
            noCut(menu)
            both("speaker_menu", page)
            one(menu, "speakerSearch").text = "tuan"
            tryVerify(function() { return all(menu, "speakerOptionName").filter(shown).some(t => t.text === "Tuấn Anh") })
            const option = all(menu, "speakerOption").filter(shown).filter(o => all(o, "speakerOptionName")[0].text === "Tuấn Anh")[0]
            option.clicked()
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            compare(calls("POST", base + "/speaker")[0].body.speaker, "TUAN_ANH")
            tryCompare(Api, "notice", "Đã ghi: câu này của Tuấn Anh")
            tryVerify(function() { return !has(page, "scriptSpeakerMenu") })
            // người vừa gán vào chú giải với số kế tiếp
            tryVerify(function() { return all(page, "legendName").filter(shown).map(t => t.text).indexOf("Tuấn Anh") === 2 })
        }
        function test_hintButtonAssignsTheSuggestion() {
            serve()
            const page = openScript()
            ready(page, 6)
            one(rowOf(page, "d2"), "hintAssign").clicked()
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            compare(calls("POST", base + "/speaker")[0].body.speaker, "LUCIEN")
        }
        function test_failedAssignRestoresTheLineAndSaysWhy() {
            serve({speakerFails: true})
            const page = openScript()
            ready(page, 6)
            focusLine(page, "d1")
            keyClick(Qt.Key_2)
            tryVerify(function() { return Api.notice.indexOf("Chưa ghi được người nói") === 0 })
            tryVerify(function() { return rowOf(page, "d1").line.wish === null })
        }

        // ================= 4. "Duyệt N câu", thu lại =================
        function test_confirmChapterSendsOneRequestPerSpeaker() {
            serve()
            const page = openScript()
            ready(page, 6)
            one(page, "scriptConfirm").clicked()
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            const body = calls("POST", base + "/speaker")[0].body
            compare(body.speaker, "LUCIEN")
            compare(body.lines, [{stableId: "d1", textSha256: "h-d1"}, {stableId: "t1", textSha256: "h-t1"}])
            tryCompare(Api, "notice", "Đã xác nhận 2 câu là đúng")
            compare(Api.noticeAction.label, "Hoàn tác")
        }
        function test_retakeOnlyRecordedLines() {
            serve()
            const page = openScript()
            ready(page, 6)
            focusLine(page, "d1")
            keyClick(Qt.Key_R)
            tryVerify(function() { return calls("POST", base + "/review").length === 1 })
            compare(calls("POST", base + "/review")[0].body, {verdict: "redo", chapterId: 1, lines: [{stableId: "d1"}], seen: {d1: ""}})
            tryCompare(Api, "notice", "Đã ghi: thu lại câu này")
            tryVerify(function() { return has(rowOf(page, "d1"), "retakeNote") })
            // câu chưa thu: không gửi, nói vì sao
            focusLine(page, "t1")
            keyClick(Qt.Key_R)
            tryCompare(Api, "notice", "Chưa thu câu này nên chưa có gì để thu lại - sẽ thu lần đầu khi sách làm tới đó")
            compare(calls("POST", base + "/review").length, 1)
        }

        // ================= 5. cách đọc câu =================
        function test_narrationToDialogueWithANewPersonPostsLineThenSpeaker() {
            serve()
            const page = openScript()
            ready(page, 6)
            const tab = tabOf(page)
            tab.openDelivery(rowOf(page, "n1").line, rowOf(page, "n1").deliveryAnchor)
            tryVerify(function() { return has(page, "scriptDelivery") }, 3000)
            const panel = one(page, "scriptDelivery")
            verify(!one(panel, "deliverySave").enabled)
            one(panel, "deliveryKind").picked("dialogue")
            tryVerify(function() { return one(panel, "deliverySpeaker").open })
            compare(one(panel, "deliverySave").text, "Chọn người nói trước")
            verify(!one(panel, "deliverySave").enabled)
            one(panel, "speakerSearch").text = "Bà Tư"
            tryVerify(function() { return has(panel, "speakerNew_female") })
            one(panel, "speakerNew_female").clicked()
            tryVerify(function() { return has(panel, "deliveryPicked") })
            compare(one(panel, "deliveryPicked").text, "Bà Tư · người mới")
            compare(one(panel, "deliverySave").text, "Lưu cho câu này")
            noCut(panel)
            both("delivery", page)
            one(panel, "deliverySave").clicked()
            tryVerify(function() { return calls("POST", base + "/speaker").length === 1 })
            compare(calls("POST", base + "/line")[0].body, {stableId: "n1", textSha256: "h-n1", kind: "dialogue", seen: S.seenDelivery(null)})
            compare(calls("POST", base + "/speaker")[0].body, {lines: [{stableId: "n1", textSha256: "h-n1"}], speaker: "Bà Tư", newGender: "female"})
            tryCompare(Api, "notice", "Đã ghi cách đọc câu này")
            compare(Api.noticeAction.label, "Hoàn tác")
        }
        function test_newPersonFailureWithdrawsTheFirstStep() {
            serve({speakerFails: true})
            const page = openScript()
            ready(page, 6)
            tabOf(page).openDelivery(rowOf(page, "n1").line, rowOf(page, "n1").deliveryAnchor)
            tryVerify(function() { return has(page, "scriptDelivery") }, 3000)
            const panel = one(page, "scriptDelivery")
            one(panel, "deliveryKind").picked("thought")
            one(panel, "speakerSearch").text = "Bà Tư"
            tryVerify(function() { return has(panel, "speakerNew_male") })
            one(panel, "speakerNew_male").clicked()
            one(panel, "deliverySave").clicked()
            tryVerify(function() { return calls("POST", base + "/line").length === 2 })
            compare(calls("POST", base + "/line")[1].body, {stableId: "n1", withdraw: true, requestedAt: 88})
            tryVerify(function() { return Api.notice.indexOf("Chưa ghi được") === 0 })
        }
        function test_emotionChangeOnDialogueIsOneStep() {
            serve()
            const page = openScript()
            ready(page, 6)
            focusLine(page, "d1")
            keyClick(Qt.Key_E)
            tryVerify(function() { return has(page, "scriptDelivery") }, 3000)
            const panel = one(page, "scriptDelivery")
            one(panel, "deliveryEmotion").expanded = true
            tryVerify(function() { return has(panel, "deliveryEmotion_angry") })
            one(panel, "deliveryEmotion_angry").clicked()
            one(panel, "deliverySave").clicked()
            tryVerify(function() { return calls("POST", base + "/line").length === 1 })
            compare(calls("POST", base + "/line")[0].body.emotion, "angry")
            compare(calls("POST", base + "/line")[0].body.stableId, "d1")
            compare(calls("POST", base + "/speaker").length, 0)
        }
        function test_closingWithUnsavedChoicesSaysTheyWereDropped() {
            serve()
            const page = openScript()
            ready(page, 6)
            focusLine(page, "d1")
            keyClick(Qt.Key_E)
            tryVerify(function() { return has(page, "scriptDelivery") }, 3000)
            one(one(page, "scriptDelivery"), "deliveryKind").picked("thought")
            one(page, "scriptDeliveryPop").close()
            tryCompare(Api, "notice", "Chưa lưu cách đọc của câu này\nLựa chọn vừa rồi đã bỏ. Mở lại và bấm “Lưu cho câu này” để giữ.")
            compare(calls("POST", base + "/line").length, 0)
        }

        // ================= 6. chương, mở từ thẻ việc, máy khác, nhịp đổi =================
        function test_chapterMenuAndNextChapter() {
            serve()
            const page = openScript()
            ready(page, 6)
            one(page, "scriptChapter").clicked()
            tryVerify(function() { return all(page, "scriptChapterOption").filter(shown).length === 2 })
            verify(hasText(page, "2 chỗ nghi"))
            all(page, "scriptChapterOption").filter(shown)[1].clicked()
            ready(page, 2)
            tryVerify(function() { return calls("GET", base + "/casting/2").length >= 1 })
            verify(!has(page, "scriptNextChapter"))
            one(page, "scriptPrevious").clicked()
            ready(page, 6)
            one(page, "scriptNextChapter").clicked()
            ready(page, 2)
        }
        function test_openFromAWorkCardGoesToTheLineAndOpensTheMenu() {
            serve()
            const page = openProject()
            const screen = screenOf(page)
            screen.scriptAt = {chapter: 2, line: "x1", pick: true}
            screen.jump("script", "work", "speaker:x1", "", false)
            tryCompare(screen, "shownTab", "script", 3000)
            ready(page, 2)
            tryCompare(tabOf(page), "active", "x1")
            tryVerify(function() { return has(page, "scriptSpeakerMenu") }, 3000)
            verify(has(page, "jumpBack"))
            // đổi tab ở hàng tab thì quên câu
            screen.pickTab("chapters")
            compare(screen.scriptAt, null)
        }
        function test_chapterMenuOfTheChaptersTabOpensThatChapter() {
            serve()
            const page = openProject()
            const screen = screenOf(page)
            screen.menuChapter = chapter(2)
            one(page, "chapterMenu").picked("script")
            tryCompare(screen, "shownTab", "script", 3000)
            ready(page, 2)
            verify(hasText(page, "Chương 2"))
        }
        function test_stampChangeReloadsTheChapter() {
            serve()
            const page = openScript()
            ready(page, 6)
            const store = tabOf(page).scriptStore
            tryVerify(function() { return store.stamp.last !== null }, 3000)
            const before = calls("GET", base + "/casting/1").length
            server.stamp = 2
            store.stamp.load()
            tryVerify(function() { return calls("GET", base + "/casting/1").length > before })
        }
        function test_remoteStudioGoesThroughThePeer() {
            serve({}, peerBase)
            const b = book()
            reply("GET " + peerBase + "/api/app", {status: 200, data: {version: "0.4.150", dialogs: false, remote: true, studio: {installed: true}, peer: {id: peerId, name: "Máy bàn phòng làm việc"}}})
            reply("GET " + peerBase + "/api/library", library([b]))
            reply("GET " + peerBase + base, {status: 200, data: {book: b, chapters: [chapter(1), chapter(2)]}})
            Nav.studioPeer = peerId
            const page = makeStudio()
            tryVerify(function() { return all(page, "projectName").filter(shown).length >= 1 }, 3000)
            page.openProject("a")
            tryCompare(page, "shownKey", "route:project")
            tryCompare(page, "phase", 1)
            screenOf(page).pickTab("script")
            ready(page, 6)
            verify(calls("GET", peerBase + base + "/casting").length >= 1)
            verify(calls("GET", base + "/casting").length === 0)
            focusLine(page, "d1")
            keyClick(Qt.Key_2)
            tryVerify(function() { return calls("POST", peerBase + base + "/speaker").length === 1 })
            // nghe câu đi đường media của máy kia
            keyClick(Qt.Key_P)
            tryVerify(function() { return DesktopApi.previews.length > 0 || Clip.current !== "" })
        }

        // ================= 7. chữ dài xuống dòng ở cả hai cỡ =================
        function test_longTextWrapsAtBothWidths() {
            const longText = "Một câu thoại rất dài của nhân vật, nói liền một mạch không ngắt để thử xem kịch bản xuống dòng đúng chỗ hay tràn ra ngoài khung: "
                + "Nguyễn Thị Hạ Vy Của Vương Quốc Phía Đông Xa Xôi Và Những Ngày Tháng Không Thể Nào Quên Được cùng những người bạn đồng hành."
            const one1 = chapterOne()
            one1.title = "Chương 1: Một tiêu đề chương rất dài để thử nút chọn chương xuống dòng chứ không cắt chữ"
            one1.cast.push({value: "HA_VY", label: "Nguyễn Thị Hạ Vy Của Vương Quốc Phía Đông", lines: 1})
            one1.lines.push(line("d9", 6, 5, "dialogue", "HA_VY", longText, {label: "Nguyễn Thị Hạ Vy Của Vương Quốc Phía Đông"}))
            const c = contents()
            c.chapters[0].title = one1.title
            for (const width of [1024, 1920]) {
                serve({chapters: {1: one1, 2: chapterTwo()}, contents: c})
                const page = openScript(width)
                ready(page, 7)
                noCut(page)
                scrollTo(page, rowOf(page, "d9"))
                both("long_" + width, page)
                page.destroy()
            }
        }
    }
}
