import QtQuick
import QtTest
import ABook
import "../../qml/PlayerLineLogic.js" as L
import "../../qml/ScriptLogic.js" as Script
import "ModalLayer.js" as Layers
import "VisualReady.js" as VisualReady

Item {
    id: host
    width: 1000; height: 900
    Component { id: factory; PlayerLineEditor {} }
    Component { id: readingFactory; ReadAlongView {} }
    Component { id: chapterFactory; ChapterReader {} }
    TestCase {
        name: "PlayerLine"
        when: windowShown
        property var cases: []
        function initTestCase() {
            const request = new XMLHttpRequest()
            request.open("GET", Qt.resolvedUrl("../../../tests/fixtures/player_line/cases.json"), false)
            request.send()
            cases = JSON.parse(request.responseText)
            compare(cases.length, 12)
        }
        function init() {
            DesktopApi.reset(); Api.bind(DesktopApi, Theme); Api.info = {}; Api.notice = ""; Nav.layers = []; Theme.reduceMotion = true
        }
        function cleanup() { Nav.layers = []; Theme.reduceMotion = false; Clip.stop(); ReadAlong.active = false; Player.pause(); WidthNet.resetBooks() }
        function serve(row, id) {
            const responses = {
                "/api/listen/books/a": {status: 200, data: {capabilities: {workshop: false, toolchain: false, link: false}}},
                "/api/books/a/cast": {status: 200, data: row.cast},
                "/api/books/a/wishes": {status: 200, data: row.wishes},
                "POST /api/books/a/speaker": {status: 200, data: {requestedAt: 17, lines: 1}},
                "POST /api/books/a/line": {status: 200, data: {requestedAt: 18}},
                "POST /api/books/a/review": {status: 200, data: {requestedAt: 19, lines: 1}}
            }
            const mapped = {}
            for (const key of Object.keys(responses)) mapped[key.replace("/books/a", "/books/" + id)] = responses[key]
            DesktopApi.responses = mapped
        }
        function prepare(row) {
            serve(row, "a")
            Api.info = {listenOnly: !!row.listenOnly}
            const editor = createTemporaryObject(factory, host)
            verify(editor !== null)
            editor.begin({bookId: "a", chapterId: 1, source: row.source}, true)
            tryVerify(() => !editor.loading)
            return editor
        }
        function test_contract_data() { return cases.map(row => ({tag: row.name, row: row})) }
        function test_contract(data) {
            const row = data.row, editor = prepare(row), commands = editor.scriptCommands
            if (row.action === "blocked") { verify(!editor.identified || !!editor.problem); editor.dismiss(); return }
            verify(editor.line !== null)
            if (row.action === "speaker") commands.assign([editor.line], row.person)
            else if (row.action === "delivery") {
                const d = row.delivery
                commands.fixLine(editor.line, Script.deliveryChange(editor.line, d.kind, d.emotion, d.intensity, row.person || null, editor.line.text))
            } else if (row.action === "spoken") commands.fixLine(editor.line, {spoken: row.spoken})
            else commands.retake([editor.line])
            const posted = DesktopApi.requests.filter(r => r.method === "POST").map(r => ({endpoint: r.path.split("/").pop(), body: r.body}))
            // Studio accepts either single-line or batch retake refs. Other requests are byte-for-field equal.
            if (row.action === "review") {
                compare(posted[0].body.lines, [{stableId: row.source.stableId}]); compare(posted[0].body.seen, row.expectedSteps[0].body.seen)
                compare(posted[0].body.chapterId, 1); compare(posted[0].body.verdict, "redo")
            } else compare(posted, row.expectedSteps)
            editor.dismiss()
        }
        function test_backAndThreeClicksDoNotSeek() {
            const row = cases[0], editor = prepare(row), before = Player.position
            function one(name) { const all = Layers.findAll(host, name); verify(all.length > 0, name); return all[0] }
            // Starting from a visible sentence: hold -> Who -> person (three deliberate operations).
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            mouseClick(one("playerLineWho")); compare(editor.step, "speaker")
            const options = Layers.findAll(host, "speakerOption")
            const choice = options.find(item => item.person.value === "AN")
            verify(choice !== undefined)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            mouseClick(choice)
            compare(DesktopApi.requests.filter(r => r.method === "POST" && r.path.endsWith("/speaker")).length, 1)
            editor.close(); compare(Player.position, before)
        }
        // Soát 0.4.173 B10/B13b: hàng "Sửa cách đọc một từ" như web, mở được cả với câu chưa nhận ra (file ABook bản cũ); "Nghe thử" chỉ xét audio.
        function test_wordRowOpensTheReadingEditorEvenForAnUnidentifiedLine() {
            const row = cases.find(item => item.name === "missing-stable-id"), editor = prepare(row)
            verify(!editor.identified); compare(editor.problem, "")
            function one(name) { const all = Layers.findAll(host, name); verify(all.length > 0, name); return all[0] }
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            verify(!one("playerLineWho").enabled); verify(!one("playerLineRetake").enabled)
            verify(one("playerLineSample").enabled)
            compare(L.wordsOf("Rô-bốt nói: rô-bốt l’ami, 10 giờ!"), ["Rô-bốt", "nói", "l’ami", "10", "giờ"])
            mouseClick(one("playerLineWord")); compare(editor.step, "word")
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            const chips = Layers.findAll(host, "playerLineWordChip")
            compare(chips.map(chip => chip.text), L.wordsOf(row.source.text))
            mouseClick(chips[0]); compare(editor.word, chips[0].text)
            const wordRow = one("playerLineWordRow")
            compare(wordRow.surface, chips[0].text); verify(wordRow.fresh)
            editor.close(); compare(editor.step, "menu")
            compare(DesktopApi.requests.filter(r => r.method === "POST").length, 0)
            editor.close()
        }
        function test_backFromChildOnlyReturnsToMenu() {
            const editor = prepare(cases[0]), before = Player.position
            editor.step = "speaker"; editor.close(); verify(editor.open); compare(editor.step, "menu")
            editor.close(); verify(!editor.open); compare(Player.position, before)
            compare(DesktopApi.requests.filter(r => r.method === "POST").length, 0)
        }
        function test_undoRetainsItsBookAfterOpeningAnotherSentence() {
            const row = cases[0], editor = prepare(row)
            editor.scriptCommands.assign([editor.line], row.person)
            const action = Api.noticeAction
            verify(action !== null)
            editor.close()
            serve(row, "b")
            const next = DesktopApi.responses
            next["POST /api/books/a/speaker"] = {status: 200, data: {restored: true}}
            DesktopApi.responses = next
            editor.begin({bookId: "b", chapterId: 2, source: row.source}, true)
            tryVerify(() => !editor.loading)
            action.run()
            const posts = DesktopApi.requests.filter(r => r.method === "POST")
            compare(posts.length, 2)
            compare(posts[1].path, "/api/books/a/speaker")
            compare(posts[1].body.requestedAt, 17)
            verify(posts[1].body.withdraw)
            compare(editor.bookId, "b"); compare(editor.chapterId, 2)
            editor.close()
        }
        function test_textOnlyParagraphsCannotBorrowSegmentIdentityByIndex() {
            const row = cases[0]
            DesktopApi.responses = {
                "/api/listen/books/a": {status: 200, data: {chapters: [{id: 1, state: "text"}]}},
                "/api/listen/books/a/chapters/1/text": {status: 200, data: {text: row.source.text, segments: [row.source]}}
            }
            const reader = createTemporaryObject(chapterFactory, host)
            verify(reader !== null); reader.begin("a", 1)
            tryVerify(() => !reader.loading)
            compare(reader.paragraphs.length, 1)
            compare(reader.paragraphs[0].source.text, row.source.text)
            verify(!L.identified(reader.paragraphs[0].source))
            reader.close()
        }
        function test_realReadAlongContextGestureAndTwoPicksKeepTheCursor() {
            const row = cases[0]
            WidthNet.setBook({id: "lineplayer", title: "Hộp kiểm thử", narrator: "Giọng thử", complete: true,
                chapters: [{id: 1, index: 1, title: "Một", duration: 20, available: true}], records: [{id: "r1", active: true}], state: {}})
            WidthNet.setScript("lineplayer", 1, {chapterId: 1, timed: true, segments: [row.source]})
            serve(row, "lineplayer")
            Player.open("lineplayer", 1, 5, true)
            tryVerify(() => Player.loaded && Player.bookId === "lineplayer")
            Player.pause()
            ReadAlong.active = true
            tryCompare(ReadAlong, "status", "ready")
            const reading = createTemporaryObject(readingFactory, host, {width: 1000, height: 700})
            verify(reading !== null)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            const text = Layers.findAll(host, "readAlongParagraphText")[0]
            verify(text !== undefined)
            const list = findChild(reading, "readAlongParagraphs"), scroll = list.contentY, before = Player.position
            mouseClick(text, 12, 12, Qt.RightButton) // operation 1: edit, not seek
            const editor = Layers.findAll(host, "playerLineEditor").find(item => item.open)
            verify(editor !== undefined)
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            grabImage(host.Window.window.contentItem).save(Qt.resolvedUrl("../../build/player-line-dialog.png").toString().replace(/^file:\/\/\/([A-Za-z]:)/, "$1"))
            mouseClick(Layers.findAll(host, "playerLineWho")[0]) // operation 2
            VisualReady.render(this, host.Window.window, host, qtVisualReady)
            mouseClick(Layers.findAll(host, "speakerOption").find(item => item.person.value === "AN")) // operation 3
            editor.close()
            compare(Player.position, before); compare(list.contentY, scroll)
            compare(DesktopApi.requests.filter(r => r.method === "POST" && r.path === "/api/books/lineplayer/speaker").length, 1)
        }
    }
}
