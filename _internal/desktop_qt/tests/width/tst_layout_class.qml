import QtQuick
import QtTest
import ABook
import "../../qml" as UI
import "ParityFixtures.js" as Fixture
import "LayoutAudit.js" as Audit

// Entire Qt route inventory, all settings groups, modal screens and player
// surfaces. Geometry uses the real QML; only HTTP/audio/platform are fixtures.
Item {
    id: host
    width: 1920; height: 1080
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Sidebar { id: sidebar; width: 232; height: parent.height }
    Item { id: content; x: sidebar.visible ? 232 : 0; width: host.width - x; height: host.height }
    Item { id: anchor; x: 500; y: 120; width: 40; height: 40 }
    Component { id: library; LibraryScreen {} }
    Component { id: book; BookPage {} }
    Component { id: now; NowPlaying {} }
    Component { id: studio; StudioScreen {} }
    Component { id: settings; SettingsScreen {} }
    Component { id: add; AddBook {} }
    Component { id: edit; EditBook {} }
    Component { id: rename; EditBookRename {} }
    Component { id: save; EditBookSaveAs {} }
    Component { id: reader; ChapterReader {} }
    Component { id: suggestions; ReadingSuggestions {} }
    Component { id: shortcuts; ShortcutsDialog {} }
    Component { id: speed; SpeedPopover { anchorItem: anchor } }
    Component { id: sleep; SleepPopover { anchorItem: anchor } }
    Component { id: music; MusicPopover { anchorItem: anchor } }
    Component { id: chapters; ChaptersPopover { anchorItem: anchor } }
    Component { id: connection; UI.ConnectionPopover { anchorItem: anchor } }
    Component { id: mini; MiniPlayer {} }
    Component { id: bar; UI.PlayerBar {} }
    Component {
        id: broken
        Item {
            width: 1600; height: 200
            Item { objectName: "edgeA"; width: 100; height: 40 }
            Item { objectName: "edgeB"; x: 10; y: 50; width: 100; height: 40 }
            Button { anchors.centerIn: parent; width: parent.width; text: "Detached" }
            ChoiceChip { y: 150; width: 350; text: "Wide" }
            ControlChip { y: 150; x: 400; width: 350; text: "Wide action" }
            PageSwitch { y: 150; x: 800; width: 350; labels: ["One", "Two"] }
        }
    }
    TestCase {
        name: "LayoutClass"
        when: windowShown
        function init() {
            Theme.reduceMotion = true; Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.loaded = true; Api.preferences = {theme: "light"}; Api.info = {version: "fixture", studio: {installed: true}}
            Nav.layers = []; Nav.studioPeer = ""
            Backend.state = Backend.Ready; Backend.libraryLoaded = true; Backend.library.error = ""
            Backend.library.items = Fixture.books(); Backend.library.count = Backend.library.items.length; Backend.library.revision++
            DesktopApi.responses = Object.assign(Fixture.responses(), {
                "/api/sync": {status: 200, data: {enabled: true, wanted: true, name: "Máy nghe sách", addresses: ["192.168.1.20"], devices: [{id: "phone", name: "Điện thoại", lastSeen: 1793000000}]}},
                "/api/sync/peers": {status: 200, data: {peers: []}}
            })
            WidthNet.setBook(Fixture.playerBook(false)); Player.open("width", 1, 40, true); Player.pause()
        }
        function cleanup() {
            Player.pause(); Player.setSleep("off"); WidthNet.resetBooks()
            Backend.library.items = null; Backend.library.count = 200; Backend.library.revision++
            Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto"
        }
        function sectionGroups(page, screen, tag) {
            function group(label, names) { return {label: label, items: names.map(n => findChild(page, n))} }
            if (screen === "library") return [group("library-content", ["libraryHeader", "libraryTools", "libraryContinue", "libraryFilterRow", "libraryGridRow"])]
            if (screen === "book") return [group("book-content", ["bookHeader", "bookStage"])]
            if (screen === "studio") return tag === "studio-closed" || tag === "studio-trouble" ? [group("studio-content", ["studioHeader", "studioBody"])]
                                                                                                 : [group("studio-content", ["projectsHeader", "projectsBody"])]
            if (screen === "settings") return page.layoutExpanded
                ? [group("settings-navigation", ["settingsHeader", "settingsGroups"]), group("settings-body", ["settingsGroupHeading", "settingsContent"])]
                : [group("settings-content", ["settingsHeader", "settingsGroups", "settingsContent"])]
            return []
        }
        function test_negative_control() {
            const page = createTemporaryObject(broken, host)
            const hits = Audit.scan(page, [{label: "fixture", items: [findChild(page, "edgeA"), findChild(page, "edgeB")]}])
            for (const rule of ["section-left", "detached-text", "stretched-chip", "stretched-segment"])
                verify(hits.some(h => h.rule === rule), "detector must catch " + rule + ": " + JSON.stringify(hits))
            verify(hits.filter(h => h.rule === "stretched-chip").length >= 2, "both choice and player chips are checked")
        }
        function test_routes_data() {
            let rows = []
            const screens = ["library", "library-short", "library-many", "book", "now", "now-chapters", "studio", "studio-peer", "studio-closed", "studio-trouble", "settings-root",
                "settings-voice", "settings-listen", "settings-sleep", "settings-look", "settings-devices", "settings-studio", "settings-advanced",
                "add", "add-review", "edit", "rename", "save", "reader", "suggestions", "shortcuts", "speed", "sleep", "music", "chapters", "connection", "mini", "bar"]
            for (const mode of ["light", "dark"]) for (const w of [1024, 1440, 1920]) for (const screen of screens)
                rows.push({tag: mode + "_" + screen + "_" + w, screen: screen, mode: mode, w: w})
            return rows
        }
        function test_routes(d) {
            host.width = d.w; host.height = d.w === 1024 ? 900 : 1080; Theme.mode = d.mode
            sidebar.visible = d.screen !== "mini"
            let screen = d.screen.split("-")[0]
            const factories = {library: library, book: book, now: now, studio: studio, settings: settings, add: add, edit: edit, rename: rename,
                save: save, reader: reader, suggestions: suggestions, shortcuts: shortcuts, speed: speed, sleep: sleep, music: music,
                chapters: chapters, connection: connection, mini: mini, bar: bar}
            let props = {width: content.width, height: content.height}
            if (screen === "settings") props.active = d.screen.slice(9) === "root" ? "" : d.screen.slice(9)
            const page = createTemporaryObject(factories[screen], content, props)
            verify(page !== null)
            if (d.screen === "library-short") { page.books = Fixture.books().slice(2, 3) }
            if (d.screen === "library-many") { Backend.library.items = null; Backend.library.count = 31; Backend.library.revision++ }
            if (screen === "book") page.book = {bookId: "width", title: "Miền đất", author: "Đặng An", chapters: 3}
            if (screen === "now") { page.show(); if (d.screen === "now-chapters") { if (page.wide) page.sidePage = 0; else page.page = 1 } }
            if (d.screen === "studio-peer") { Nav.studioPeer = "fixture"; page.peerInfo = {peer: {name: "Máy của bạn"}} }
            if (d.screen === "studio-closed") { Nav.studioPeer = "fixture"; page.peerInfo = {listenOnly: true, peer: {name: "Máy của bạn"}} }
            if (d.screen === "studio-trouble") { Nav.studioPeer = "fixture"; page.trouble = "Máy kia chưa trả lời" }
            if (screen === "add") {
                page.show()
                if (d.screen === "add-review") page.showPreview({title: "Miền đất", author: "Đặng An", chapters: [{index: 1, title: "Lên đường", words: 1250, included: true}], totals: {chapters: 1, words: 1250}, notes: [], suggestions: []}, false)
            }
            if (screen === "edit" || screen === "save") page.begin({id: "width", title: "Miền đất", author: "Đặng An", stage: "text", capabilities: {}, edits: 2})
            if (screen === "rename") page.begin({id: "width", stage: "text"}, {id: 1, title: "Chương 1", subtitle: "Lên đường"})
            if (screen === "reader") page.begin("fresh", 1)
            if (screen === "suggestions") { page.bookId = "width"; page.show() }
            if (["shortcuts", "speed", "sleep", "music", "chapters", "connection"].includes(screen)) page.show()
            if (screen === "mini") { page.height = page.naturalHeight; page.y = (content.height - page.height) / 2 }
            if (screen === "bar") { page.height = page.natural; page.y = content.height - page.height }
            wait(460)
            const hits = Audit.scan(page, sectionGroups(page, screen, d.screen)).concat(sidebar.visible ? Audit.scan(sidebar) : [])
            if (screen === "library") {
                const header = findChild(page, "libraryHeader")
                // Check every virtualised row, including partially filled rows.
                for (const row of page.list.contentItem.children) for (const child of row.children || [])
                    if (child.objectName === "libraryGridRow") Audit.aligned([header, child], page, hits, "library-grid")
                const hero = findChild(page, "libraryContinue")
                verify(hero.measure <= Theme.listMeasure + 2, "continue row exceeds content measure")
            }
            console.log("LAYOUT_AUDIT " + JSON.stringify({scene: d.tag, hits: hits}))
            qtGlyphAudit.scan()
            if (qtWideShotDir !== "" && d.w !== 1440) {
                host.Window.window.update(); waitForRendering(host)
                // QtQuickTest Image.save returns void; verify PNGs on disk.
                grabImage(host).save(qtWideShotDir + "/layout_" + d.tag + ".png")
            }
            compare(hits.length, 0, JSON.stringify(hits))
            if (page.close) page.close()
            page.destroy()
        }
    }
}
