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
        ListElement { chapterId: 7; title: "Chương 7"; subtitle: "Chưa thu"; fullTitle: "Chương 7 · Chưa thu"; length: ""; status: "Chưa có audio"; playable: false; done: false; current: false; progress: 0 }
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
            Api.preferences = {sleepFadeSeconds: 45, sleepExtendMinutes: 15}
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
            clickReady(findChild(menu, "sleepChoice_15")); compare(Player.sleepKind, "minutes"); verify(!menu.open)
            menu.show(); tryCompare(menu, "open", true); ready()
            const before = Player.clock.sleepLeft
            clickReady(findChild(menu, "sleepExtend"))
            fuzzyCompare(Player.clock.sleepLeft, before + 900, 1)
            clickReady(findChild(menu, "sleepOff")); compare(Player.sleepKind, "off")
            menu.show(); tryCompare(menu, "open", true); ready(); clickReady(findChild(menu, "sleepChapter")); compare(Player.sleepKind, "chapter")
        }
        function test_fade_restart_and_geometric_bounds() {
            const menu = createTemporaryObject(sleep, host, {width: 792, height: 700})
            Player.resume(); Player.setSleep("minutes", 1); WidthNet.advance(45)
            verify(Player.fading)
            WidthNet.advance(20); compare(Player.sleepKind, "off"); verify(Player.sleepStoppedText !== "")
            menu.show(); tryCompare(menu, "open", true); ready()
            clickReady(findChild(menu, "sleepRestart")); compare(Player.sleepKind, "minutes")
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
            keyClick(Qt.Key_Tab); verify(findChild(page, "volumeSlider").activeFocus)
            keyClick(Qt.Key_Right); fuzzyCompare(Player.volume, 0.75, 0.001)
            keyClick(Qt.Key_Tab); keyClick(Qt.Key_Return); tryVerify(function() { return (Nav.layers.length) === (2) })
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
