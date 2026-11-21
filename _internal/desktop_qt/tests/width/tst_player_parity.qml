import QtQuick
import QtTest
import "VisualReady.js" as VisualReady
import ABook
import "ParityFixtures.js" as Fixture

Item {
    id: host
    width: 1920; height: 1080
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: now; NowPlaying {} }
    Component { id: volume; VolumeControl {} }
    Component { id: sleep; SleepPopover {} }
    Component { id: reader; ChapterReader {} }
    Component { id: chapters; ChapterList {} }
    Component { id: suggestions; ReadingSuggestions {} }
    SignalSpy { id: spy }
    ListModel {
        id: textChapters
        ListElement { chapterId: 7; title: "Chương 7"; subtitle: "Chưa thu"; fullTitle: "Chương 7\u00a0·\u00a0Chưa thu"; length: ""; status: "Chưa có audio"; playable: false; done: false; current: false; progress: 0 }
    }
    TestCase {
        name: "PlayerParity"
        function ready() { VisualReady.render(this, host.Window.window, host, qtVisualReady) }
        function clickReady(item, x, y, button, modifiers, delay) {
            ready()
            mouseClick(item, x, y, button, modifiers, delay)
        }
        when: windowShown
        function init() {
            Theme.reduceMotion = false; Nav.layers = []
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            // Player là singleton sống qua các ca: đưa lần hẹn cuối về "chưa từng đặt" (30 phút) cho mỗi ca.
            // (Main.qml không nạp ở đây: báo "đã lưu xong" thay nó, rồi đưa bản đã lưu về rỗng để mốc 30 được nhận lại.)
            Player.lastSleepSaved(); Player.configure({})
            Api.preferences = {sleepFadeSeconds: 45, sleepExtendMinutes: 15, lastSleep: {kind: "minutes", minutes: 30, chapters: 1}}
            Player.configure(Api.preferences)
            Player.open("width", 1, 0, true); Player.pause(); Player.setVolume(0.7); Player.setSleep("off")
            DesktopApi.responses = {
                "/api/listen/books/width": {status: 200, data: {id: "width", chapters: [{id: 1, title: "Chương 1", state: "text"}, {id: 2, title: "Chương 2"}]}},
                "/api/listen/books/width/chapters/1/text": {status: 200, data: {text: "Buổi sáng ấy.\n\nChúng tôi lên đường."}},
                "/api/books/width/chapters/2/script": {status: 200, data: {segments: [{text: "Chương chưa có audio vẫn đọc được."}]}}
            }
        }
        function cleanup() { spy.target = null; Nav.layers = []; Player.pause(); Player.setSleep("off"); Theme.reduceMotion = false }
        function test_volume_mouse_keys_mute() {
            const control = createTemporaryObject(volume, host, {width: 296})
            const slider = findChild(control, "volumeSlider"), mute = findChild(control, "volumeMute")
            clickReady(slider, slider.width / 2, slider.height / 2)
            const changed = Player.volume
            verify(changed > 0.4 && changed < 0.6)
            slider.forceActiveFocus(); keyClick(Qt.Key_Right)
            fuzzyCompare(Player.volume, changed + 0.05, 0.001)
            clickReady(mute); compare(Player.volume, 0)
            clickReady(mute); fuzzyCompare(Player.volume, changed + 0.05, 0.001)
            slider.forceActiveFocus(); keyClick(Qt.Key_End); compare(Player.volume, 1)
        }
        function test_sleep_choices_and_extend() {
            const menu = createTemporaryObject(sleep, host, {width: host.width, height: host.height})
            menu.show(); tryCompare(menu, "fadeSeconds", 45); tryCompare(menu, "extendMinutes", 15)
            // Bộ chọn giá trị: chip "30" là đặt ngay, bảng đứng yên (kéo thước cần bảng không tự đóng).
            clickReady(findChild(menu, "valueChip_30")); compare(Player.sleepKind, "minutes"); compare(Player.sleepMinutes, 30); verify(menu.open)
            // Hẹn lại về số đã chọn (30), không phải "Mỗi lần nghe thêm" (15) và không cộng thêm.
            compare(findChild(menu, "sleepExtend").text, "Hẹn lại 30\u00a0phút")
            clickReady(findChild(menu, "sleepExtend"))
            fuzzyCompare(Player.clock.sleepLeft, 1800, 1)
            clickReady(findChild(menu, "sleepOff")); compare(Player.sleepKind, "off")
            menu.show(); tryCompare(menu, "open", true); ready(); clickReady(findChild(findChild(menu, "sleepChapterPicker"), "valueDisplay")); compare(Player.sleepKind, "chapter")
            compare(Player.sleepChapters, 1)
            clickReady(findChild(findChild(menu, "sleepChapterPicker"), "valueCountUp")); compare(Player.sleepChapters, 2)
            compare(findChild(menu, "sleepCountdown").text, "Hết 2 chương")
            verify(findChild(menu, "sleepExtend").visible)
            clickReady(findChild(menu, "sleepExtend")); compare(Player.sleepKind, "minutes"); compare(Player.sleepMinutes, 15)
        }
        function test_sleep_adjustments_only_draft_until_confirmed() {
            const menu = createTemporaryObject(sleep, host, {width: host.width, height: host.height})
            menu.show(); tryCompare(menu, "open", true); ready()
            const picker = findChild(menu, "sleepPicker")
            picker.nudge(1)
            compare(Player.sleepKind, "off")
            const drafted = picker.value
            picker.adjust(42)
            compare(Player.sleepKind, "off")
            compare(picker.value, 42)
            clickReady(findChild(menu, "sleepConfirm"))
            compare(Player.sleepKind, "minutes"); compare(Player.sleepMinutes, 42)
        }
        // Chủ sách 17-11: hộp hẹn giờ mở sẵn ở lần đặt cuối (tuỳ chọn `lastSleep`), nút "Bật lại" đặt lại đúng lần ấy - số phút hay số chương.
        function test_sleep_opens_at_the_last_choice_and_restarts_it() {
            const menu = createTemporaryObject(sleep, host, {width: 792, height: 700})
            // Mở hộp TRƯỚC khi tuỳ chọn tải xong (soát sleeplast lỗi 5): bộ chọn nhảy theo mốc vừa nạp, như web.
            menu.show(); tryCompare(menu, "open", true); ready()
            compare(findChild(menu, "sleepPicker").value, 30)
            Player.configure({lastSleep: {kind: "minutes", minutes: 45, chapters: 3}})
            compare(findChild(menu, "sleepPicker").value, 45)
            compare(findChild(menu, "sleepChapterPicker").value, 3)
            menu.close()
            menu.show(); tryCompare(menu, "open", true); ready()
            compare(findChild(menu, "sleepPicker").value, 45)
            compare(findChild(menu, "sleepChapterPicker").value, 3)
            menu.close()
            Player.resume(); Player.setSleep("chapter", 2)
            compare(Player.lastSleepKind, "chapter"); compare(Player.lastSleepChapters, 2); compare(Player.lastSleepMinutes, 45)
            Player.setSleep("minutes", 1); WidthNet.advance(70)
            verify(Player.sleepStoppedText !== "")
            // Tự dừng vẫn giữ lựa chọn (0.4.173 B8); "Bật lại" chỉ hiện khi đã tắt hẳn - như web sleepRestartOffered.
            compare(Player.sleepKind, "minutes")
            Player.setSleep("off", 0)
            menu.show(); tryCompare(menu, "open", true); ready()
            compare(findChild(menu, "sleepRestart").text, "Bật lại 1\u00a0phút")
            Player.lastSleepSaved() // (Main.qml: lần lưu đã về)
            Player.configure({lastSleep: {kind: "chapter", minutes: 45, chapters: 2}})
            compare(findChild(menu, "sleepRestart").text, "Bật lại 2 chương")
            clickReady(findChild(menu, "sleepRestart"))
            compare(Player.sleepKind, "chapter"); compare(Player.sleepChapters, 2)
            // Giá trị lưu hỏng: giữ mốc đang có, không văng.
            Player.configure({lastSleep: {kind: "minutes", minutes: 999, chapters: 1}})
            compare(Player.lastSleepKind, "chapter"); compare(Player.lastSleepChapters, 2)
        }
        // Soát sleeplast 18-11 (lỗi 1, 2): đổi số liên tiếp gom một lần lưu, mỗi lúc một lần gửi; phản hồi cũ về muộn không kéo mốc lùi;
        // lưu hỏng thì im lặng (Api.quiet, như web).
        function test_last_sleep_saves_coalesce_and_ignore_a_late_reply() {
            const saves = () => DesktopApi.requests.filter(r => r.method === "PUT" && r.path === "/api/preferences" && r.body.lastSleep)
            const minutes = value => ({kind: "minutes", minutes: value, chapters: 1})
            let settled = 0
            Api.lastSleepTimer.interval = 20
            DesktopApi.delayed = true
            for (const value of [31, 32, 33]) Api.rememberLastSleep(minutes(value), function() { settled++ })
            tryVerify(function() { return saves().length === 1 })
            compare(saves()[0].body.lastSleep.minutes, 33)
            Api.rememberLastSleep(minutes(34), function() { settled++ })
            tryCompare(Api.lastSleepTimer, "running", false) // nhịp gom của 34 đã điểm khi 33 còn bay
            compare(saves().length, 1) // lần 33 còn bay: 34 chưa gửi chồng lên
            compare(Api.lastSleepQueued.minutes, 34)
            DesktopApi.finish() // phản hồi của 33 về khi 34 đã chọn: không áp
            verify(!Api.preferences.lastSleep || Api.preferences.lastSleep.minutes !== 33)
            compare(settled, 0)
            tryVerify(function() { return saves().length === 2 })
            compare(saves()[1].body.lastSleep.minutes, 34)
            DesktopApi.finish()
            compare(Api.preferences.lastSleep.minutes, 34)
            compare(settled, 4)
            // Lưu hỏng: không hiện lời báo, mốc trong tuỳ chọn giữ nguyên.
            DesktopApi.delayed = false
            DesktopApi.responses = {"PUT /api/preferences": {status: 500, data: {message: "hỏng"}}}
            Api.notice = ""
            Api.rememberLastSleep(minutes(45), function() { settled++ })
            tryCompare(Api, "lastSleepFlying", false); tryVerify(function() { return settled === 5 })
            compare(Api.notice, "")
            compare(Api.preferences.lastSleep.minutes, 34)
            Api.lastSleepTimer.interval = 800
        }
        function test_fade_restart_and_geometric_bounds() {
            const menu = createTemporaryObject(sleep, host, {width: 792, height: 700})
            Player.resume(); Player.setSleep("minutes", 1); WidthNet.advance(45)
            verify(Player.fading)
            WidthNet.advance(20); compare(Player.sleepKind, "minutes"); verify(Player.sleepStoppedText !== "")
            menu.show(); tryCompare(menu, "open", true); ready()
            clickReady(findChild(menu, "sleepExtend")); compare(Player.sleepKind, "minutes")
            compare(Player.sleepMinutes, 1)
            menu.show(); tryCompare(menu, "open", true); ready()
            const panel = findChild(menu, "popoverPanel")
            verify(panel.y >= 0 && panel.y + panel.height <= menu.height)
            menu.close()
        }
        function test_reader_text_script_retry_and_back() {
            const page = createTemporaryObject(reader, host, {width: host.width, height: host.height})
            page.begin("width", 1); tryVerify(function() { return (page.paragraphs.length) === (2) }); tryVerify(function() { return (page.chapter.id) === (1) }); tryVerify(function() { return (Nav.layers.length) === (1) })
            page.load(page.chapters[1]); tryVerify(function() { return (page.paragraphs[0] && page.paragraphs[0].text) === ("Chương chưa có audio vẫn đọc được.") })
            const field = findChild(page, "readerChapters")
            clickReady(field); tryVerify(function() { return (Nav.layers.length) === (2) })
            Nav.back(); tryVerify(function() { return (Nav.layers.length) === (1) }); tryVerify(function() { return page.open })
            Nav.back(); tryVerify(function() { return !page.open })
            DesktopApi.responses["/api/books/width/chapters/2/script"] = {status: 503, data: {message: "Máy kia chưa trả lời. Bạn thử lại nhé."}}
            page.begin("width", 2); tryCompare(page, "error", "Máy kia chưa trả lời. Bạn thử lại nhé.")
            DesktopApi.responses["/api/books/width/chapters/2/script"] = {status: 200, data: {segments: [{text: "Đã tải lại"}]}}
            page.load(page.chapter); tryVerify(function() { return (page.paragraphs[0] && page.paragraphs[0].text) === ("Đã tải lại") })
        }
        function test_reader_ignores_late_reply() {
            const page = createTemporaryObject(reader, host)
            DesktopApi.delayed = true
            page.begin("width", 1); page.close(); DesktopApi.finish()
            compare(page.paragraphs.length, 0); verify(!page.open)
        }
        function test_suggestions_group_update_readonly_and_error() {
            let skipped = false
            DesktopApi.responses["/api/books/width/suggestions"] = function() { return {status: 200, data: {suggestions: [
                {chapter: 1, line: "Nguồn: người dịch", skipped: skipped}, {chapter: 2, line: "Nguồn: người dịch", skipped: skipped}
            ]}} }
            DesktopApi.responses["PUT /api/books/width/skip"] = function(body) { skipped = body.skip; return {status: 200, data: {skip: {}}} }
            const dialog = createTemporaryObject(suggestions, host, {width: host.width, height: host.height, bookId: "width"})
            dialog.show(); tryVerify(function() { return (dialog.groups.length) === (1) }); tryVerify(function() { return (dialog.groups[0].chapters.join()) === ("1,2") })
            clickReady(findChild(dialog, "suggestionSkip")); verify(dialog.groups[0].skipped)
            const request = DesktopApi.requests.filter(r => r.method === "PUT")[0]
            compare(request.path, "/api/books/width/skip"); compare(request.body.line, "Nguồn: người dịch"); compare(request.body.chapters.join(), "1,2")
            Api.info = {listenOnly: true}; verify(!findChild(dialog, "suggestionSkip").enabled)
            Api.info = {}; DesktopApi.responses["PUT /api/books/width/skip"] = {status: 503, data: {message: "Bạn thử lại nhé."}}
            clickReady(findChild(dialog, "suggestionSkip")); compare(dialog.error, "Bạn thử lại nhé."); verify(dialog.groups[0].skipped)
            Nav.back(); tryVerify(function() { return !dialog.open })
        }
        function test_unrecorded_chapter_opens_reading() {
            const list = createTemporaryObject(chapters, host, {width: 600, height: 500, model: textChapters})
            tryVerify(function() { return list.itemAtIndex(0) !== null }); spy.signalName = "readRequested"; spy.target = list; spy.clear()
            const row = list.itemAtIndex(0)
            verify(row)
            row.clicked(); compare(spy.count, 1); compare(spy.signalArguments[0][0], 7)
            row.menuRequested(findChild(row, "chapterMore")); tryVerify(function() { return findChild(list, "chapterRead") && findChild(list, "chapterRead").visible })
            clickReady(findChild(list, "chapterRead")); compare(spy.count, 2)
        }
        function test_more_help_history_tabs_and_back() {
            const page = createTemporaryObject(now, host, {width: 1688, height: 900})
            page.show(); tryVerify(function() { return page.wide }); tryVerify(function() { return (Nav.layers.length) === (1) })
            clickReady(findChild(page, "nowMore")); tryVerify(function() { return (Nav.layers.length) === (2) }); ready()
            clickReady(findChild(page, "nowAudioFxButton")); tryCompare(findChild(page, "nowAudioFx"), "open", true); ready()
            const volumeSlider = findChild(findChild(page, "audioFxVoice"), "valueRuler")
            verify(volumeSlider); volumeSlider.forceActiveFocus(); verify(volumeSlider.activeFocus)
            keyClick(Qt.Key_Right); fuzzyCompare(Player.volume, 0.75, 0.001)
            tryVerify(function() { return (Nav.layers.length) === (2) })
            Nav.back(); tryVerify(function() { return page.open }); tryVerify(function() { return (Nav.layers.length) === (1) })
            Player.jumpTo(2, 0); Player.pause(); verify(Player.canGoBack)
            clickReady(findChild(page, "nowMore")); tryCompare(findChild(page, "nowMoreMenu"), "open", true); ready()
            clickReady(findChild(page, "nowHistory")); compare(Player.chapterId, 1)
            page.sidePage = 0; tryCompare(page, "showText", false)
            page.sidePage = 1; tryCompare(page, "showText", true)
            const tabs = findChild(page, "nowSideTabs")
            const selected = tabs.children.filter(c => c.Accessible && c.Accessible.role === Accessible.PageTab && c.activeFocusOnTab)[0]
            verify(selected); selected.forceActiveFocus(); keyClick(Qt.Key_Left); tryCompare(page, "sidePage", 0); tryCompare(Player, "chapterId", 1)
            clickReady(findChild(page, "nowMore")); tryCompare(findChild(page, "nowMoreMenu"), "open", true); ready()
            spy.target = page; spy.signalName = "settingsRequested"; spy.clear()
            clickReady(findChild(page, "nowAddVoice")); compare(spy.count, 1); compare(spy.signalArguments[0][0], "voice")
            page.close(); tryVerify(function() { return (Nav.layers.length) === (0) })
        }
        function test_end_offers_next_volume_and_playable_alternatives() {
            Backend.library.items = Fixture.books(); Backend.library.count = 5; Backend.library.revision++
            const page = createTemporaryObject(now, host, {width: 1688, height: 900})
            page.show(); tryVerify(function() { return (page.nextVolume.bookId) === ("next") }); tryVerify(function() { return (page.otherBooks.map(b => b.bookId).join()) === ("remote") })
            Player.open("width", 32, 0, true); WidthNet.finishChapter(); compare(Player.atEnd, "finished")
            tryVerify(function() { return findChild(page, "nowOtherBooks").visible }); clickReady(findChild(page, "nowOtherBooks")); tryVerify(function() { return findChild(page, "nowRecommendations").open })
            Nav.back(); tryVerify(function() { return page.open })
            const next = Fixture.playerBook(true); next.id = "next"; WidthNet.setBook(next)
            clickReady(findChild(page, "nowNextVolume")); compare(Player.bookId, "next"); verify(Player.playing)
            page.close(); page.destroy()
            WidthNet.resetBooks(); Backend.library.items = null; Backend.library.count = 200; Backend.library.revision++
        }
    }
}
