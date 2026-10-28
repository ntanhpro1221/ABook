import QtQuick
import QtTest
import ABook

// Real screens, deterministic HTTP/audio fixtures. Render through offscreen QPA.
Item {
    id: host
    width: 1920; height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Sidebar { id: sidebar; width: 232; height: parent.height }
    Item { id: content; x: 232; width: host.width - x; height: host.height }
    Component { id: library; LibraryScreen {} }
    Component { id: book; BookPage {} }
    Component { id: now; NowPlaying {} }
    Component { id: add; AddBook {} }
    Component { id: edit; EditBook {} }
    Component { id: settings; SettingsScreen {} }
    Component { id: studio; StudioScreen {} }
    Component { id: mini; MiniPlayer {} }

    TestCase {
        name: "WideScreens"
        when: windowShown
        function init() {
            Theme.reduceMotion = true
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.loaded = true; Api.preferences = {theme: "light"}
            Api.info = {version: "fixture", studio: {installed: true}}
            Nav.layers = []; Nav.studioPeer = ""
            DesktopApi.responses = {
                "/api/sync": {status: 200, data: {enabled: true, wanted: true, name: "Máy nghe sách", addresses: ["192.168.1.20"],
                    devices: [{id: "phone", name: "Điện thoại của bạn", lastSeen: 1793000000, studio: true}]}},
                "/api/sync/peers": {status: 200, data: {peers: []}}
            }
        }
        function cleanup() { Nav.layers = []; Theme.reduceMotion = false; Theme.mode = "auto" }
        function disjoint(a, b, page) {
            verify(a !== null && b !== null, "missing layout columns")
            const p = a.mapToItem(page, 0, 0), q = b.mapToItem(page, 0, 0)
            verify(q.x >= p.x + a.width - 0.6 || q.y >= p.y + a.height - 0.6
                   || p.x >= q.x + b.width - 0.6 || p.y >= q.y + b.height - 0.6,
                   a.objectName + " overlaps " + b.objectName)
            for (let column of [a, b]) {
                verify(column.width >= 0 && column.width <= page.width + 0.6)
                const at = column.mapToItem(page, 0, 0)
                verify(at.x >= -0.6 && at.x + column.width <= page.width + 0.6,
                       column.objectName + " leaves screen")
            }
        }
        function textFits(item, column) {
            if (!item.visible || item.opacity === 0 || item.width <= 0 || item.height <= 0) return
            if (item.text !== undefined && item.paintedWidth !== undefined && String(item.text) !== "") {
                const label = column.objectName + ": " + String(item.text).slice(0, 90)
                verify(item.width <= column.width + 1, "element wider than column: " + label)
                verify(item.paintedWidth <= item.width + 1, "text clipped horizontally: " + label)
                verify(item.paintedHeight <= item.height + 1, "text clipped vertically: " + label)
                let offset = 0
                if (item.horizontalAlignment === Text.AlignRight) offset = item.width - item.paintedWidth
                else if (item.horizontalAlignment === Text.AlignHCenter) offset = (item.width - item.paintedWidth) / 2
                const ink = item.mapToItem(column, offset, 0)
                verify(ink.x >= -1 && ink.x + item.paintedWidth <= column.width + 1,
                       "text leaves column: " + label)
            } else if (item.text !== undefined && item.contentWidth !== undefined && item.wrapMode !== undefined) {
                const pad = (item.leftPadding || 0) + (item.rightPadding || 0)
                verify(item.width <= column.width + 1, "field wider than column: " + column.objectName)
                verify(item.contentWidth <= item.width - pad + 1, "wrapped field clips text: " + column.objectName)
                verify(item.contentHeight <= item.height + 1, "wrapped field clips vertically: " + column.objectName)
            }
            for (const child of item.children || []) textFits(child, column)
        }
        function columns(page, first, second) {
            const a = findChild(page, first), b = findChild(page, second)
            disjoint(a, b, page); textFits(a, a); textFits(b, b)
        }
        function verifyLayout(page, screen) {
            if (screen === "add") {
                columns(page, "importDetailsColumn", "importChapterColumn")
                const opts = findChild(page, "importOptionsColumn")
                textFits(opts, opts)
            }
            if (screen === "edit") columns(page, "editDetailsColumn", "editExtrasColumn")
            if (screen === "devices") {
                columns(page, "thisDeviceColumn", "pairedDeviceColumn")
                verify(findChild(page, "thisDeviceColumn").width <= Theme.listMeasure + 0.5)
                verify(findChild(page, "pairedDeviceColumn").width <= Theme.listMeasure + 0.5)
                compare(findChild(page, "thisDeviceColumn").parent.expanded,
                        Theme.widthClass(findChild(page, "thisDeviceColumn").parent.width) >= 2)
            }
            if (screen === "settings" && page.layoutExpanded) columns(page, "settingsGroups", "settingsContent")
            if (screen === "mini") {
                columns(page, "miniDetails", "miniPlayback")
                const details = findChild(page, "miniDetails")
                verify(details.width <= 640)
                verify(page.height >= details.y + details.height)
            }
            if (screen === "studio") {
                const body = findChild(page, "projectsBody")
                textFits(body, body)
                verify(body.width <= 1180 && body.width <= page.width)
                const header = findChild(page, "projectsHeader")
                fuzzyCompare(header.x, body.x, 0.5)
            }
            if (screen === "book") {
                columns(page, "bookSummary", "bookChapterRegion")
                verify(findChild(page, "bookChapters").width <= Theme.listMeasure + 0.5)
            }
            if (screen === "library") {
                verify(page.coverW <= 200 && page.coverW >= 160)
                const row = findChild(page, "libraryGridRow")
                textFits(row, row)
            }
            if (screen === "now") {
                const region = findChild(page, "nowReadAlongRegion")
                if (page.wide) verify(region.x >= page.colX + page.colW)
                verify(findChild(page, "nowReadAlong").textMax <= 640)
            }
        }
        function test_screens_data() {
            let rows = []
            for (const mode of ["light", "dark"])
                for (const w of [1024, 1366, 1630, 1920])
                    for (const screen of ["library", "book", "now", "add", "edit", "settings", "devices", "studio", "mini"])
                        rows.push({tag: mode + "_" + screen + "_" + w, mode: mode, w: w, screen: screen})
            return rows
        }
        function test_screens(d) {
            host.width = d.w; Theme.mode = d.mode
            sidebar.visible = d.screen !== "mini"
            content.x = sidebar.visible ? 232 : 0
            const factories = {library: library, book: book, now: now, add: add, edit: edit,
                settings: settings, devices: settings, studio: studio, mini: mini}
            let props = {width: content.width, height: content.height}
            if (d.screen === "settings") props.active = "look"
            if (d.screen === "devices") props.active = "devices"
            let page = createTemporaryObject(factories[d.screen], content, props)
            verify(page !== null)
            if (d.screen === "book") page.book = {bookId: "width", title: "Hành trình qua những miền đất mới", author: "Người kể chuyện", chapters: 32, detail: "8 giờ", progress: 0.2}
            if (d.screen === "now") page.show()
            if (d.screen === "settings") page.active = "look"
            if (d.screen === "devices") page.active = "devices"
            if (d.screen === "add") {
                page.show()
                let chapters = []
                for (let i = 1; i <= 12; i++) chapters.push({index: i, title: "Chương " + i + " · Con đường bên bờ sông", words: 1250, included: true})
                page.showPreview({title: "Hành trình qua những miền đất mới", author: "Người kể chuyện", chapters: chapters,
                    totals: {chapters: 12, words: 15000}, notes: [], suggestions: [], sourceFingerprint: "fixture"}, false)
            }
            if (d.screen === "edit") page.begin({id: "width", title: "Hành trình qua những miền đất mới", author: "Người kể chuyện", stage: "text", capabilities: {}, edits: 2})
            if (d.screen === "mini") { page.height = page.naturalHeight; page.y = (content.height - page.height) / 2 }
            wait(600)
            verifyLayout(page, d.screen)
            console.log("WIDE_METRIC " + JSON.stringify({screen: d.screen, width: d.w, mode: d.mode,
                content: content.width, expanded: !!page.expanded, columns: page.cols || 0, cover: page.coverW || 0,
                panel: page.panelWidth || 0}))
            if (qtWideShotDir !== "") {
                host.Window.window.update(); waitForRendering(host)
                qtGlyphAudit.scan()
                grabImage(host).save(qtWideShotDir + "/" + d.tag + ".png")
            }
            verify(page.width <= content.width + 0.5)
            page.destroy()
        }

        function test_reflow_data() {
            return ["add", "edit", "devices", "settings", "studio", "mini"].map(s => ({tag: s, screen: s}))
        }
        function test_reflow(d) {
            const factories = {add: add, edit: edit, devices: settings, settings: settings, studio: studio, mini: mini}
            sidebar.visible = d.screen !== "mini"
            content.x = sidebar.visible ? 232 : 0
            const narrow = d.screen === "mini" ? 360 : 792
            host.width = narrow + content.x
            if (d.screen === "devices") {
                DesktopApi.responses["/api/sync"].data.name = "Máy nghe sách của gia đình ".repeat(8)
                DesktopApi.responses["/api/sync"].data.devices[0].name = "Điện thoại với tên rất dài ".repeat(8)
            }
            let props = {width: content.width, height: 780}
            if (d.screen === "devices") props.active = "devices"
            if (d.screen === "settings") props.active = "look"
            const page = createTemporaryObject(factories[d.screen], content, props)
            verify(page !== null)
            page.width = Qt.binding(() => content.width)
            if (d.screen === "add") {
                page.show(); page.showPreview({title: "Bản nháp", author: "Tác giả", chapters: [{index: 1, title: "Một tên chương dài ".repeat(12), included: true, words: 1234}],
                    totals: {chapters: 1, words: 1234}, notes: [], suggestions: []}, false)
            }
            if (d.screen === "edit") page.begin({id: "width", title: "Tên sách", author: "Tác giả", stage: "text", capabilities: {}, edits: 2})
            if (d.screen === "mini") { page.bookTitle = "Một tên sách dài ".repeat(12); page.chapterTitle = "Tên chương dài ".repeat(15); page.height = Qt.binding(() => page.naturalHeight) }
            wait(600)
            if (d.screen === "edit") { page.titleDraft = "Bản nháp đang viết ".repeat(5); page.authorDraft = "Tác giả đang viết" }
            Theme.reduceMotion = false
            for (const width of [1688, narrow, 1688]) {
                host.width = width + content.x
                wait(40)
                if (d.screen !== "settings" && d.screen !== "devices") verify(page.wideT > 0 && page.wideT < 1, "reflow must animate")
                if (d.screen === "add" || d.screen === "edit" || d.screen === "mini") {
                    for (let frame = 0; frame < 14; frame++) {
                        if (d.screen === "add") disjoint(findChild(page, "importDetailsColumn"), findChild(page, "importChapterColumn"), page)
                        if (d.screen === "edit") disjoint(findChild(page, "editDetailsColumn"), findChild(page, "editExtrasColumn"), page)
                        if (d.screen === "mini") disjoint(findChild(page, "miniDetails"), findChild(page, "miniPlayback"), page)
                        wait(20)
                    }
                } else wait(360)
                verifyLayout(page, d.screen)
            }
            if (d.screen === "edit") { compare(page.titleDraft, "Bản nháp đang viết ".repeat(5)); compare(page.authorDraft, "Tác giả đang viết") }
            if (d.screen === "add") { compare(page.bookTitle, "Bản nháp"); compare(page.picked.join(), "1") }
            Theme.reduceMotion = true
            host.width = narrow + content.x; wait(30)
            if (page.wideT !== undefined) compare(page.wideT, page.expanded ? 1 : 0)
            page.destroy()
        }
    }
}
