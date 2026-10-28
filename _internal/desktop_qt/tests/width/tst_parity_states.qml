import QtQuick
import QtTest
import ABook
import "ParityFixtures.js" as Fixture
import "LayoutAudit.js" as Audit

// Reviewable state matrix. Run with ABOOK_WIDE_SHOTS to also export PNGs;
// geometry and glyph checks run on the same actual QML in the normal build.
Item {
    id: host
    width: 1920; height: 1080
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Sidebar { width: 232; height: parent.height }
    Item { id: content; x: 232; width: host.width - x; height: host.height }
    Component { id: library; LibraryScreen {} }
    Component { id: now; NowPlaying {} }
    TestCase {
        name: "ParityStates"
        when: windowShown
        function init() {
            Theme.reduceMotion = true; Nav.layers = []; Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.preferences = {sleepFadeSeconds: 30, sleepExtendMinutes: 10}
            Player.configure(Api.preferences)
            Backend.state = Backend.Ready; Backend.libraryLoaded = true; Backend.library.error = ""
            Backend.library.items = Fixture.books(); Backend.library.count = Backend.library.items.length; Backend.library.revision++
            DesktopApi.responses = Fixture.responses()
            WidthNet.setBook(Fixture.playerBook(false))
            Player.open("width", 1, 40, true); Player.pause(); Player.setSleep("off"); Player.setVolume(0.7)
        }
        function cleanup() {
            Player.pause(); Player.setSleep("off"); WidthNet.resetBooks(); Player.open("width", 1, 0, false)
            Backend.library.items = null; Backend.library.count = 200; Backend.library.revision++; Backend.library.error = ""
            Backend.state = Backend.Ready; Backend.libraryLoaded = true
            Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto"
        }
        function geometry(item, page) {
            if (!item.visible || item.opacity < 0.01) return
            if (item.objectName === "popoverPanel" || item.objectName === "modalPanel") {
                const at = item.mapToItem(page, 0, 0)
                verify(at.y >= -1 && at.y + item.height <= page.height + 1, "layer leaves screen vertically")
            }
            if (item.paintedWidth !== undefined && String(item.text || "") !== "") {
                verify(item.paintedWidth <= item.width + 1, "text overflows: " + item.text)
                verify(item.paintedHeight <= item.height + 1, "text too tall: " + item.text)
                // Only compare to the screen when inside its non-scrolling view.
                const p = item.mapToItem(page, 0, 0)
                verify(p.x >= -1 && p.x + item.width <= page.width + 1, "text leaves screen: " + item.text)
            }
            for (const child of item.children || []) geometry(child, page)
        }
        function test_states_data() {
            const library = ["all", "listening", "new", "finished", "search", "no-results", "sort", "series", "playing", "waiting", "empty", "loading", "error", "reader"]
            const player = ["main", "more", "muted", "keys", "history", "speed", "sleep-off", "sleep-minutes", "sleep-chapter", "fading", "stopped", "chapters", "chapter-menu", "reader", "finished", "caught-up", "recommendations", "suggestions"]
            let rows = []
            for (const mode of ["light", "dark"]) for (const w of [1024, 1440, 1920]) {
                for (const state of library) rows.push({tag: mode + "_library_" + state + "_" + w, screen: "library", state: state, mode: mode, w: w})
                for (const state of player) rows.push({tag: mode + "_now_" + state + "_" + w, screen: "now", state: state, mode: mode, w: w})
            }
            return rows
        }
        function test_states(d) {
            host.width = d.w; host.height = d.w === 1024 ? 900 : 1080; Theme.mode = d.mode
            const page = createTemporaryObject(d.screen === "library" ? library : now, content, {width: content.width, height: content.height})
            verify(page)
            if (d.screen === "library") {
                if (["listening", "new", "finished"].indexOf(d.state) >= 0) page.filter = d.state
                if (d.state === "search" || d.state === "no-results") {
                    findChild(page, "librarySearch").clicked()
                    page.query = d.state === "search" ? "dang an" : "cuon sach chua co"
                }
                if (d.state === "sort") findChild(page, "librarySort").clicked()
                if (d.state === "series") page.activate(0)
                if (d.state === "playing") Player.resume()
                if (d.state === "waiting") {
                    Player.close()
                    const books = Fixture.books(); books[0].listeningProgress.caughtUp = true
                    Backend.library.items = books; Backend.library.revision++
                }
                if (d.state === "empty") { Backend.library.items = []; Backend.library.count = 0; Backend.library.revision++ }
                if (d.state === "loading") Backend.libraryLoaded = false
                if (d.state === "error") Backend.library.error = "Máy chưa trả lời. Bạn thử tải lại thư viện nhé."
                if (d.state === "reader") page.readRequested(Fixture.books()[2])
            } else {
                page.show()
                if (["more", "muted", "keys", "history"].indexOf(d.state) >= 0) {
                    if (d.state === "history") { Player.jumpTo(2, 0); Player.pause() }
                    findChild(page, "nowMore").clicked()
                    if (d.state === "muted") Player.toggleMute()
                    if (d.state === "keys") findChild(page, "nowKeys").clicked()
                }
                if (d.state === "speed") {
                    // The existing speed chip has the accessible label, no duplicate button.
                    for (const child of findChild(page, "nowSleep").parent.children) if (child.tip === "Tốc độ đọc") child.clicked()
                }
                if (d.state.indexOf("sleep-") === 0) {
                    if (d.state === "sleep-minutes") Player.setSleep("minutes", 15)
                    if (d.state === "sleep-chapter") Player.setSleep("chapter")
                    findChild(page, "nowSleep").clicked()
                }
                if (d.state === "fading" || d.state === "stopped") {
                    Player.seek(0); Player.resume(); Player.setSleep("minutes", 1); WidthNet.advance(d.state === "fading" ? 45 : 61)
                    if (d.state === "fading") verify(Player.fading)
                    else { compare(Player.sleepKind, "off"); verify(Player.sleepStoppedText !== "") }
                    if (d.state === "stopped") findChild(page, "nowSleep").clicked()
                }
                if (d.state === "chapters" || d.state === "chapter-menu") {
                    if (page.wide) page.sidePage = 0
                    else findChild(page, "nowChapters").clicked()
                    wait(200)
                    if (d.state === "chapter-menu") {
                        const list = page.wide ? findChild(page, "nowChapterList") : findChild(page, "nowChapterListPopover")
                        verify(list); const row = list.itemAtIndex(2); verify(row)
                        row.menuRequested(findChild(row, "chapterMore"))
                    }
                }
                if (d.state === "reader") findChild(page, "chapterReader").begin("width", 3)
                if (d.state === "suggestions") { findChild(page, "nowMore").clicked(); findChild(page, "nowSuggestionsButton").clicked() }
                if (["finished", "caught-up", "recommendations"].indexOf(d.state) >= 0) {
                    WidthNet.setBook(Fixture.playerBook(d.state !== "caught-up"))
                    Player.open("width", 2, 0, true); WidthNet.finishChapter()
                    if (d.state === "recommendations") findChild(page, "nowRecommendations").show()
                }
            }
            wait(420)
            geometry(page, page)
            const hits = Audit.scan(page)
            console.log("LAYOUT_AUDIT " + JSON.stringify({scene: "parity_" + d.tag, hits: hits}))
            compare(hits.length, 0, JSON.stringify(hits))
            qtGlyphAudit.scan()
            if (qtWideShotDir !== "" && d.w !== 1440) { host.Window.window.update(); waitForRendering(host); grabImage(host).save(qtWideShotDir + "/parity_" + d.tag + ".png") }
            if (d.screen === "now") page.close()
            page.destroy()
        }
    }
}
