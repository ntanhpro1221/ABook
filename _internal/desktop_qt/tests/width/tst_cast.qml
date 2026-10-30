import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook

// Tab "Nhân vật" của trang sách (BookPage + CastList/CastPerson/CastSample + các hộp Gộp / Đổi tên / Giới tính / Giọng): danh sách, trạng thái trống, nghe thử,
// gộp / bỏ gộp, đổi giọng, đổi giới tính, chữ dài xuống dòng ở 1024 và 1920, và lớp Back. Máy chủ giả: DesktopApi giả (tests/qml/stub/ABook/DesktopApi.qml).
// Ảnh offscreen ghi ra build/d2shots/cast_*.png.
Item {
    id: host
    width: 1440
    height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: pageFactory; BookPage {} }
    Component { id: dialogsFactory; CastDialogs {} }

    TestCase {
        id: test
        name: "CastTab"
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        when: windowShown

        property var server: ({})
        property var castReply: ({})
        property var page: null
        property var dialogs: null
        readonly property string longName: "Nguyễn Thị Hạ Vy Của Vương Quốc Phía Đông Xa Xôi Và Những Ngày Tháng Không Thể Nào Quên Được"

        function workshopBook() {
            return {id: "b1", stage: "audio", title: "Sách có giọng", author: "", cover: null, edits: 0,
                    capabilities: {workshop: true, toolchain: true, link: false},
                    chapters: [{id: 1, title: "Chương 1", fullTitle: "Chương 1"}, {id: 2, title: "Chương 2", fullTitle: "Chương 2"}, {id: 3, title: "Chương 3", fullTitle: "Chương 3"}]}
        }
        function waitingBook() {
            return Object.assign(workshopBook(), {capabilities: {workshop: false, toolchain: false, link: false}})
        }
        function castFixture() {
            return {
                narrator: {voice: "Minh Quân", lines: 120, seconds: 3600, redo: 4, pendingVoice: {preset: "huong", label: "Hương"}},
                characters: [
                    {name: "Lan", displayName: "Lan", gender: "Nữ", voice: {preset: "ngoc-linh", label: "Ngọc Linh"}, lines: 40, seconds: 300, firstChapter: "Chương 1", sampleId: 3},
                    {name: "Hạ_Vy", displayName: "Hạ Vy", gender: "Nữ", voice: {preset: "hoai-my", label: "Hoài My"}, lines: 25, seconds: 150, firstChapter: "Chương 1", sampleId: 4,
                     pendingVoice: {preset: "huong", label: "Hương"}},
                    {name: "Tuấn", displayName: "Tuấn", gender: "Nam", voice: {preset: "nam-minh", label: "Nam Minh"}, lines: 10, seconds: 60, firstChapter: "Chương 1",
                     mergedInto: "Lan", mergedAt: 1700.5}],
                extras: [], carried: []}
        }
        function voicesFixture() {
            return {character: {value: "Lan", label: "Lan", gender: "female", lines: 40, chapters: 3}, current: "Ngọc Linh", pending: null,
                    voices: [
                        {key: "ngoc-linh", name: "Ngọc Linh", gender: "female", genderLabel: "Nữ", engine: "vieneu", installed: true, current: true, preview: true},
                        {key: "hoai-my", name: "Hoài My", gender: "female", genderLabel: "Nữ", engine: "vieneu", installed: true, preview: true, suggested: true},
                        {key: "nam-minh", name: "Nam Minh", gender: "male", genderLabel: "Nam", engine: "vieneu", installed: true, preview: true}]}
        }
        function reply(path, handler) { const r = DesktopApi.responses; r[path] = handler; DesktopApi.responses = r }
        function init() {
            Theme.reduceMotion = false
            DesktopApi.reset()
            Api.bind(DesktopApi, Theme)
            Api.preferences = {theme: "system"}
            Api.info = {version: "fixture", dialogs: true}
            Api.loaded = true
            Api.notice = ""
            Nav.layers = []
            Clip.stop()
            server = workshopBook()
            castReply = castFixture()
            reply("GET /api/listen/books/b1", function() { return {status: 200, data: server} })
            reply("GET /api/books/b1/cast", function() { return {status: 200, data: castReply} })
            reply("GET /api/books/b1/voices?character=Lan", function() { return {status: 200, data: voicesFixture()} })
            reply("POST /api/books/b1/voice", {status: 200, data: {requestedAt: 99}})
            reply("POST /api/books/b1/characters/merge", {status: 200, data: {lines: 10}})
            reply("POST /api/books/b1/characters/rename", {status: 200, data: {renamed: true, name: "Lan Anh"}})
            reply("POST /api/books/b1/speaker", {status: 200, data: {}})
            reply("GET /api/books/b1/pending-changes", {status: 200, data: {items: [
                {section: "speakers", requestedAt: 1700.5, key: "s1", keys: ["s1", "s2"]}]}})
        }
        function cleanup() {
            Clip.stop()
            Nav.layers = []
            Theme.reduceMotion = false
            if (page) page.destroy()
            if (dialogs) dialogs.destroy()
            page = null
            dialogs = null
            host.width = 1440
        }
        function calls(method, path) { return DesktopApi.requests.filter(r => r.method === method && r.path === path) }
        function render() { ready() }
        function all(item, name, found) {
            const out = found || []
            if (item.objectName === name) out.push(item)
            for (const child of item.children) all(child, name, out)
            return out
        }
        // Mở trang sách + tab Nhân vật; hộp của Main.qml dựng bằng CastDialogs nối vào castRequested
        function openCast(width) {
            host.width = width || 1440
            dialogs = createTemporaryObject(dialogsFactory, host, {})
            page = createTemporaryObject(pageFactory, host, {width: host.width, height: host.height, book: {bookId: "b1", title: "Sách có giọng"}})
            verify(page !== null && dialogs !== null)
            page.castRequested.connect((kind, data) => dialogs.begin(kind, data))
            tryVerify(function() { return findChild(page, "bookTabs").visible })
            findChild(page, "bookTabs").picked(2)
            tryCompare(findChild(page, "castList"), "status", "ready")
            render()
        }
        function person(name) {
            return all(page, "castName").filter(item => item.text === name)[0]
        }
        // Dòng (CastPerson) của một người: leo từ tên lên tới phần tử có `person`
        function rowOf(name) {
            let node = person(name)
            while (node && node.person === undefined) node = node.parent
            return node
        }
        function child(row, name) { return all(row, name)[0] }
        function dialog(name) { return findChild(dialogs, name) }

        // ---------- danh sách ----------
        function test_listRenders() {
            openCast()
            compare(findChild(page, "bookTabs").labels.join("|"), "Chương|Lịch sử|Nhân vật")
            compare(findChild(page, "castNarratorVoice").text, "Minh Quân")
            compare(findChild(page, "castNarratorPending").text, "Chờ áp dụng: giọng Hương")
            compare(all(page, "castName").map(item => item.text).join("|"), "Lan|Hạ Vy|Tuấn")
            const lan = rowOf("Lan")
            compare(child(lan, "castVoice").text, "Ngọc Linh")
            compare(child(lan, "castCounts").text.indexOf("40 câu"), 0)
            verify(child(lan, "castSample").visible)
            verify(child(lan, "castVoiceButton").visible)
            const vy = rowOf("Hạ Vy")
            compare(child(vy, "castPending").text, "Chờ áp dụng: giọng Hương")
            const tuan = rowOf("Tuấn")
            compare(child(tuan, "castMerged").visible, true)
            verify(child(tuan, "castUnmerge").visible)
            verify(!findChild(page, "castEmpty").visible)
            shot("cast_list", host)
        }
        function test_waitingBookSaysMachineIsBusy() {
            server = waitingBook()
            openCast()
            compare(child(rowOf("Hạ Vy"), "castPending").text, "Đang chờ máy làm sách: giọng Hương")
            verify(!child(rowOf("Lan"), "castVoiceButton").visible)       // đổi giọng cần xưởng
            verify(!child(rowOf("Tuấn"), "castUnmerge").visible)
            verify(!findChild(page, "castNarratorPending").visible)
            verify(!findChild(page, "castNarratorVoiceButton").visible)
            verify(child(rowOf("Lan"), "castMore").visible)               // đổi tên / giới tính / gộp vẫn có
        }
        function test_emptyCast() {
            castReply = {narrator: {}, characters: [], extras: [], carried: []}
            openCast()
            const empty = findChild(page, "castEmpty")
            tryVerify(function() { return empty.visible })
            compare(empty.title, "Chưa có dàn nhân vật")
            compare(all(page, "castName").length, 0)
        }
        function test_textOnlyBookHasNoCastTab() {
            server = Object.assign(workshopBook(), {stage: "text"})
            dialogs = createTemporaryObject(dialogsFactory, host, {})
            page = createTemporaryObject(pageFactory, host, {width: host.width, height: host.height, book: {bookId: "b1", title: "Sách chữ"}})
            tryVerify(function() { return page.fullBook.id === "b1" })
            compare(findChild(page, "bookTabs").labels.join("|"), "Chương|Lịch sử")      // chưa có giọng thì chưa có tab Nhân vật
            compare(calls("GET", "/api/books/b1/cast").length, 0)
        }
        function test_castLoadsOnlyWhenOpened() {
            dialogs = createTemporaryObject(dialogsFactory, host, {})
            page = createTemporaryObject(pageFactory, host, {width: host.width, height: host.height, book: {bookId: "b1", title: "Sách có giọng"}})
            tryVerify(function() { return findChild(page, "bookTabs").visible })
            compare(calls("GET", "/api/books/b1/cast").length, 0)
            findChild(page, "bookTabs").picked(2)
            tryCompare(findChild(page, "castList"), "status", "ready")
            compare(calls("GET", "/api/books/b1/cast").length, 1)
            findChild(page, "bookTabs").picked(0)
            findChild(page, "bookTabs").picked(2)
            compare(calls("GET", "/api/books/b1/cast").length, 1)
        }

        // ---------- nghe thử ----------
        function test_sampleStartsAndStops() {
            openCast()
            const button = child(rowOf("Lan"), "castSample")
            compare(button.Accessible.name, "Nghe Lan nói")
            button.clicked()
            compare(DesktopApi.previews.length, 1)
            compare(DesktopApi.previews[0], "/media/books/b1/samples/3")
            compare(Clip.current, "sample-b1-3")
            verify(Clip.loading)
            DesktopApi.previewStarted()
            verify(!Clip.loading)
            compare(button.Accessible.name, "Dừng nghe thử")
            button.clicked()
            compare(DesktopApi.stops, 1)
            compare(Clip.current, "")
            compare(button.Accessible.name, "Nghe Lan nói")
        }
        function test_oneClipAtATime() {
            openCast()
            child(rowOf("Lan"), "castSample").clicked()
            DesktopApi.previewStarted()
            child(rowOf("Hạ Vy"), "castSample").clicked()
            compare(Clip.current, "sample-b1-4")
            compare(DesktopApi.previews.length, 2)
            verify(!child(rowOf("Lan"), "castSample").active)
            findChild(page, "castNarratorSample").clicked()
            compare(Clip.current, "voice-Minh Quân")
            compare(DesktopApi.previews[2], "/media/voices/" + encodeURIComponent("Minh Quân"))
            DesktopApi.previewEnded()
            compare(Clip.current, "")
        }
        function test_sampleFailureSaysSo() {
            openCast()
            child(rowOf("Lan"), "castSample").clicked()
            DesktopApi.previewFailed("404")
            compare(Clip.current, "")
            compare(Api.notice, "Chưa nghe thử được\nCâu mẫu này chưa có bản thu.")
        }

        // ---------- gộp / bỏ gộp ----------
        function openMenu(name) {
            child(rowOf(name), "castMore").clicked()
            tryVerify(function() { return findChild(page, "castMenu").open })
            render()
        }
        function test_menuListsThePossibleActions() {
            openCast()
            openMenu("Lan")
            verify(findChild(page, "castMerge").visible)
            verify(findChild(page, "castRename").visible)
            verify(findChild(page, "castGender").visible)
            compare(findChild(page, "castMerge").text, "Gộp vào người khác…")
            compare(findChild(page, "castRename").text, "Đổi tên")
            compare(findChild(page, "castGender").text, "Đổi giới tính")
            compare(Nav.layers.length, 1)               // bảng nổi là một lớp Back
            Nav.back()
            tryVerify(function() { return !findChild(page, "castMenu").open })
            compare(Nav.layers.length, 0)
        }
        function test_mergeFlow() {
            openCast()
            openMenu("Lan")
            findChild(page, "castMerge").clicked()
            tryVerify(function() { return dialog("castMergeDialog").open })
            render()
            const dlg = dialog("castMergeDialog")
            const choices = all(dlg, "mergeChoice")
            compare(choices.length, 2)                  // Hạ Vy và Tuấn; Lan không gộp vào chính mình
            const target = choices.filter(c => c.Accessible.name === "Hạ Vy")[0]
            verify(target !== undefined)
            verify(!all(dlg, "mergeDo")[0].enabled)     // chưa chọn người nhận
            target.clicked()
            verify(all(dlg, "mergeDo")[0].enabled)
            tryVerify(function() { return findChild(dlg, "mergeSummary").text !== "" })
            all(dlg, "mergeDo")[0].activated()
            const sent = calls("POST", "/api/books/b1/characters/merge")
            compare(sent.length, 1)
            compare(sent[0].body.from, "Lan")
            compare(sent[0].body.into, "Hạ_Vy")
            compare(Api.notice, "Đã ghi: 10 câu của Lan là của Hạ Vy")
            tryVerify(function() { return !dlg.open })
            compare(Nav.layers.length, 0)
        }
        function test_unmergeWithdrawsTheMergeVote() {
            openCast()
            child(rowOf("Tuấn"), "castUnmerge").clicked()
            const sent = calls("POST", "/api/books/b1/speaker")
            compare(sent.length, 1)
            compare(JSON.stringify(sent[0].body.lines), JSON.stringify([{stableId: "s1"}, {stableId: "s2"}]))
            compare(sent[0].body.withdraw, true)
            compare(sent[0].body.requestedAt, 1700.5)
            compare(Api.notice, "Đã bỏ gộp Tuấn")
        }
        function test_unmergeStaleSaysSo() {
            reply("GET /api/books/b1/pending-changes", {status: 200, data: {items: []}})
            openCast()
            child(rowOf("Tuấn"), "castUnmerge").clicked()
            compare(calls("POST", "/api/books/b1/speaker").length, 0)
            verify(Api.notice.indexOf("Chưa bỏ gộp được") === 0)
        }

        // ---------- đổi tên, giới tính ----------
        function test_renameSendsNewName() {
            openCast()
            openMenu("Lan")
            findChild(page, "castRename").clicked()
            tryVerify(function() { return dialog("castRenameDialog").open })
            render()
            const field = findChild(dialog("castRenameDialog"), "personName")
            compare(field.text, "Lan")
            field.text = "Lan Anh"
            all(dialog("castRenameDialog"), "personNameSave")[0].activated()
            const sent = calls("POST", "/api/books/b1/characters/rename")
            compare(sent.length, 1)
            compare(sent[0].body.character, "Lan")
            compare(sent[0].body.name, "Lan Anh")
            compare(Api.notice, "Đã đổi tên thành Lan Anh")
        }
        function test_genderSendsChoice() {
            openCast()
            openMenu("Lan")
            findChild(page, "castGender").clicked()
            tryVerify(function() { return dialog("castGenderDialog").open })
            render()
            const dlg = dialog("castGenderDialog")
            verify(!all(dlg, "genderSave")[0].enabled)  // đang là nữ
            findChild(dlg, "genderChoice").picked("male")
            verify(all(dlg, "genderSave")[0].enabled)
            all(dlg, "genderSave")[0].activated()
            const sent = calls("POST", "/api/books/b1/voice")
            compare(sent.length, 1)
            compare(sent[0].body.character, "Lan")
            compare(sent[0].body.gender, "male")
        }

        // ---------- đổi giọng ----------
        function test_voiceChangeSendsPreset() {
            openCast()
            child(rowOf("Lan"), "castVoiceButton").clicked()
            tryVerify(function() { return dialog("castVoiceDialog").open })
            const dlg = dialog("castVoiceDialog")
            tryCompare(dlg, "status", "ready")
            tryVerify(function() { return (calls("GET", "/api/books/b1/voices?character=Lan").length) === (1) })
            tryCompare(dlg, "title", "Giọng của Lan")
            const actions = all(dlg, "voiceAction")
            compare(actions.length, 2)                  // cùng giới nữ: Nam Minh không hiện
            compare(actions[0].text, "Đang dùng")
            verify(!actions[0].enabled)
            compare(actions[1].text, "Chọn")
            actions[1].activated()
            const sent = calls("POST", "/api/books/b1/voice")
            compare(sent.length, 1)
            compare(sent[0].body.character, "Lan")
            compare(sent[0].body.preset, "hoai-my")
            tryVerify(function() { return !dlg.open })
        }
        function test_voicePreviewUsesVoicePath() {
            openCast()
            child(rowOf("Lan"), "castVoiceButton").clicked()
            const dlg = dialog("castVoiceDialog")
            tryCompare(dlg, "status", "ready")
            render()
            all(dlg, "voicePreview")[1].clicked()
            compare(DesktopApi.previews[0], "/media/voices/hoai-my")
            dlg.close()
            compare(DesktopApi.stops, 1)                // đóng hộp thì clip dừng
        }
        function test_narratorVoiceButtonOpensTheSameDialog() {
            reply("GET /api/books/b1/voices?character=NARRATOR", function() {
                const answer = voicesFixture()
                answer.character = {value: "NARRATOR", label: "Người kể chuyện", gender: "male", lines: 120, chapters: 3}
                return {status: 200, data: answer}
            })
            openCast()
            findChild(page, "castNarratorVoiceButton").clicked()
            tryVerify(function() { return dialog("castVoiceDialog").open })
            tryCompare(dialog("castVoiceDialog"), "status", "ready")
            compare(calls("GET", "/api/books/b1/voices?character=NARRATOR").length, 1)
        }

        // ---------- "Nghe thử bằng câu của sách" ----------
        function openVoices(answer) {
            if (answer) reply("GET /api/books/b1/voices?character=Lan", function() { return {status: 200, data: answer} })
            openCast()
            child(rowOf("Lan"), "castVoiceButton").clicked()
            tryVerify(function() { return dialog("castVoiceDialog").open })
            tryCompare(dialog("castVoiceDialog"), "status", "ready")
            render()
            return dialog("castVoiceDialog")
        }
        function withLine() { return Object.assign(voicesFixture(), {tryLine: "Anh đi đâu thế?"}) }
        function triesOf(dlg) { return all(dlg, "voiceTry") }
        function test_tryButtonsOnlyWhenThePersonHasALine() {
            const dlg = openVoices()
            compare(triesOf(dlg).filter(button => button.visible).length, 0)
            compare(findChild(dlg, "voiceTryHint").text, "Lan chưa có câu nào để đọc thử - nút ▶ là câu mẫu chung của giọng.")
            verify(!findChild(dlg, "voiceTryNote").visible)
        }
        function test_tryHintExplainsTheTwoButtons() {
            const dlg = openVoices(withLine())
            compare(triesOf(dlg).filter(button => button.visible).length, 2)
            compare(findChild(dlg, "voiceTryHint").text, "Nút sách đọc câu của Lan; ▶ đọc mẫu chung.")
            compare(triesOf(dlg)[1].Accessible.name, "Nghe giọng Hoài My đọc một câu của sách")
            shot("cast_voice_try", host)
        }
        function test_trySendsTheLineRequestAndPlaysTheAnswer() {
            reply("POST /api/books/b1/voice/preview", {status: 200, data: {url: "/media/previews/p1.wav", text: "“Anh đi đâu thế?”"}})
            const dlg = openVoices(withLine())
            const button = triesOf(dlg)[1]
            button.requested()
            const sent = calls("POST", "/api/books/b1/voice/preview")
            compare(sent.length, 1)
            compare(sent[0].body.character, "Lan")
            compare(sent[0].body.preset, "hoai-my")
            compare(DesktopApi.previews[0], "/media/previews/p1.wav")
            compare(Clip.current, "voice-try-/media/previews/p1.wav")
            compare(findChild(dlg, "voiceTryNote").text, "Lúc thu thật sẽ nghe gần như vậy · câu “Anh đi đâu thế?” · giọng Hoài My")
            tryVerify(function() { return findChild(dlg, "voiceTryNote").visible })
            // Bấm lại lúc đang phát thì dừng; bấm nữa thì phát lại bản đã nghe, không hỏi máy chủ lần hai
            button.requested()
            compare(Clip.current, "")
            button.requested()
            compare(Clip.current, "voice-try-/media/previews/p1.wav")
            compare(calls("POST", "/api/books/b1/voice/preview").length, 1)
            dlg.close()
            compare(Clip.current, "")
        }
        function test_tryAsksOneVoiceAtATime() {
            reply("POST /api/books/b1/voice/preview", {status: 200, data: {url: "/media/previews/p2.wav", text: "Em về rồi."}})
            const dlg = openVoices(withLine())
            findChild(dlg, "voiceGenderFilter").picked("all")
            render()
            const buttons = triesOf(dlg)
            compare(buttons.length, 3)
            DesktopApi.delayed = true
            buttons[2].requested()                                        // Nam Minh
            verify(buttons[2].busy)
            compare(findChild(dlg, "voiceTryNote").text, "Máy đang đọc thử giọng Nam Minh - lần đầu có thể mất vài chục giây")
            verify(!buttons[0].enabled && !buttons[1].enabled)            // đang chờ một câu thì giọng khác chưa bấm được
            verify(buttons[2].enabled)
            DesktopApi.delayed = false
            DesktopApi.finish()
            verify(!buttons[2].busy)
            verify(buttons[0].enabled && buttons[1].enabled)
            compare(Clip.current, "voice-try-/media/previews/p2.wav")
        }
        function test_tryRefusalKeepsTheCommonSample() {
            reply("POST /api/books/b1/voice/preview", {status: 409, data: {message: "Máy bận", reason: "producing"}})
            const dlg = openVoices(withLine())
            triesOf(dlg)[0].requested()
            compare(findChild(dlg, "voiceTryNote").text, "Máy đang làm sách; thử lại khi xong. - nút ▶ vẫn nghe được câu mẫu chung của giọng")
            compare(Clip.current, "")
            verify(!triesOf(dlg)[0].busy)
        }
        function test_tryWithoutALinePlaysTheCommonSample() {
            reply("POST /api/books/b1/voice/preview", {status: 409, data: {message: "Chưa có câu", reason: "no-line"}})
            const dlg = openVoices(withLine())
            triesOf(dlg)[0].requested()
            compare(Clip.current, "voice-Ngọc Linh")
            compare(DesktopApi.previews[0], "/media/voices/ngoc-linh")
            compare(findChild(dlg, "voiceTryNote").text, "Người này chưa có câu nào để đọc thử - đang phát câu mẫu chung của giọng")
        }
        function test_tryNoteWrapsLongServerMessages_data() { return [{tag: "1024", w: 1024}, {tag: "1920", w: 1920}] }
        function test_tryNoteWrapsLongServerMessages(data) {
            reply("POST /api/books/b1/voice/preview", {status: 500, data: {message: "Máy chưa đọc thử được vì card đồ hoạ đang bận làm việc khác và bộ nhớ không còn đủ chỗ cho giọng này, bạn thử lại sau ít phút nữa nhé"}})
            host.width = data.w
            const dlg = openVoices(withLine())
            triesOf(dlg)[1].requested()
            const note = findChild(dlg, "voiceTryNote")
            verify(note.lineCount > 1)
            verify(note.paintedWidth <= note.width + 0.5)
            fuzzyCompare(note.height, note.contentHeight, 1)
            shot("cast_voice_try_long_" + data.w, host)
        }

        // ---------- tải thêm giọng của máy đọc khác ----------
        function twoEngines() {
            const answer = withLine()
            answer.voices = answer.voices.concat([
                {key: "thu-ha", name: "Thu Hà", gender: "female", genderLabel: "Nữ", engine: "zerotts", installed: false, preview: true}])
            answer.modules = {zerotts: {state: "missing", bytes: 52428800, cancellable: false}}
            return answer
        }
        function test_singleEngineHasNoModuleHeader() {
            const dlg = openVoices(withLine())
            compare(all(dlg, "voiceEngine").filter(item => item.visible).length, 0)
            compare(all(dlg, "voiceGroup").filter(item => item.visible).length, 1)
            compare(all(dlg, "voiceGroup")[0].text, "Giọng chính")
        }
        function test_otherEngineOffersTheDownload() {
            reply("POST /api/studio/zerotts", {status: 200, data: {state: "downloading", total: 52428800, done: 5242880, bytes: 52428800, cancellable: true}})
            reply("POST /api/studio/zerotts/cancel", {status: 200, data: {state: "missing", bytes: 52428800, cancelled: true, cancellable: false}})
            const dlg = openVoices(twoEngines())
            const headers = all(dlg, "voiceEngine")
            compare(headers.length, 2)
            verify(headers[0].visible && headers[1].visible)
            compare(all(headers[0], "engineLabel")[0].text, "Giọng chính")
            verify(!all(headers[0], "engineStart")[0].visible)             // VieNeu sẵn có
            compare(all(headers[1], "engineLabel")[0].text, "Giọng thêm")
            const start = all(headers[1], "engineStart")[0]
            verify(start.visible)
            compare(start.text, "Tải giọng")
            verify(all(headers[1], "engineNote")[0].text.indexOf("Máy đọc khác: cần tải thêm ") === 0)
            // giọng của máy đọc chưa tải thì chưa chọn được
            const actions = all(dlg, "voiceAction")
            verify(!actions[actions.length - 1].enabled)
            shot("cast_voice_module", host)
            start.activated()
            const sent = calls("POST", "/api/studio/zerotts")
            compare(sent.length, 1)
            verify(all(headers[1], "engineNote")[0].text.indexOf("Đang tải giọng (") === 0)
            const cancel = all(headers[1], "engineCancel")[0]
            tryVerify(function() { return cancel.visible })
            compare(cancel.text, "Huỷ")
            cancel.activated()
            compare(calls("POST", "/api/studio/zerotts/cancel").length, 1)
        }
        function test_downloadedEngineReloadsTheVoices() {
            reply("GET /api/studio/zerotts", {status: 200, data: {state: "ready", bytes: 52428800}})
            const dlg = openVoices(twoEngines())
            compare(calls("GET", "/api/books/b1/voices?character=Lan").length, 1)
            const header = all(dlg, "voiceEngine")[1]
            header.refresh()                                              // người dùng đang xem: hỏi lại trạng thái như mỗi giây lúc tải
            tryVerify(function() { return calls("GET", "/api/books/b1/voices?character=Lan").length === 2 })
            compare(dlg.status, "ready")                                  // không quay về khung chờ
            verify(!all(header, "engineStart")[0].visible)
        }

        // ---------- chữ dài xuống dòng, không cắt ----------
        function test_longNamesWrap_data() { return [{tag: "1024", w: 1024}, {tag: "1920", w: 1920}] }
        function test_longNamesWrap(data) {
            const fixture = castFixture()
            fixture.characters[0].displayName = longName
            fixture.characters[0].name = "dai"
            castReply = fixture
            openCast(data.w)
            const name = person(longName)
            verify(name !== undefined)
            verify(name.lineCount > 1, "tên dài phải xuống dòng")
            verify(name.paintedWidth <= name.width + 0.5)
            fuzzyCompare(name.height, name.contentHeight, 1)
            const row = rowOf(longName)
            verify(name.mapToItem(row, 0, name.height).y <= row.height)      // dòng người ôm hết tên
            const buttons = child(row, "castMore").mapToItem(page, 0, 0)
            verify(buttons.x + 36 <= page.width)
            // Không chữ nào nhô ra ngoài trang
            const names = all(page, "castName").concat(all(page, "castVoice"), all(page, "castCounts"))
            for (const item of names) {
                const right = item.mapToItem(page, item.paintedWidth, 0).x
                verify(right <= page.width, item.objectName + " nhô ra ngoài")
            }
            shot("cast_long_" + data.w, host)
        }
        function test_longNameInDialogs() {
            const fixture = castFixture()
            fixture.characters[0].displayName = longName
            castReply = fixture
            openCast()
            openMenu(longName)
            findChild(page, "castRename").clicked()
            tryVerify(function() { return dialog("castRenameDialog").open })
            render()
            const dlg = dialog("castRenameDialog")
            verify(dlg.title.indexOf(longName) >= 0)
            shot("cast_rename_long", host)
        }

        function shot(name, item) {
            if (!item.Window.window) return
            item.Window.window.update()
            VisualReady.render(this, host.Window.window, item, qtVisualReady)
            const img = grabImage(item)
            const path = Qt.resolvedUrl("../../build/d2shots/" + name + "_" + (Theme.dark ? "dark" : "light") + ".png").toString()
                .replace(/^file:\/\/\/([A-Za-z]:)/, "$1").replace(/^file:\/\//, "")
            img.save(path)
        }
    }
}
