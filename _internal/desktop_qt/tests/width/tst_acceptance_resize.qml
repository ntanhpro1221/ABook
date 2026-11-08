import QtQuick
import QtTest
import ABook
import "VisualReady.js" as VisualReady

// Resize the same live screen: rebuilding it would hide lost focus/scroll.
Item {
    id: host
    width: 1680; height: 900
    Rectangle { anchors.fill: parent; color: Theme.bg }
    Component { id: library; LibraryScreen {} }
    Component { id: book; BookPage { book: ({bookId: "width", title: "Hành trình qua miền đất mới"}) } }
    Component { id: settings; SettingsScreen {} }
    Component { id: studio; StudioScreen {} }
    Component { id: now; NowPlaying {} }
    TestCase {
        name: "AcceptanceResize"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.info = {studio: {installed: true}, version: "0.4.165"}
            Api.preferences = {}; Nav.layers = []; Nav.uiVisible = true
            Backend.library.count = 200; Backend.libraryLoaded = true; Backend.state = Backend.Ready
            Player.open("width", 1, 0, false)
            Theme.reduceMotion = false
        }
        function cleanup() { Player.pause(); Nav.layers = []; Theme.mode = "auto"; Theme.reduceMotion = false }
        function shown(item) {
            for (let p = item; p; p = p.parent) if (!p.visible || p.opacity < 0.99) return false
            return true
        }
        function descendants(item, predicate) {
            let result = predicate(item) ? [item] : []
            for (const c of item.children || []) result = result.concat(descendants(c, predicate))
            return result
        }
        function frameErrors(page) {
            const bad = []
            for (const item of descendants(page, p => shown(p) && p.paintedWidth !== undefined && String(p.text || "") !== "")) {
                const at = item.mapToItem(page, 0, 0)
                if (at.x < -1 || at.x + item.width > page.width + 1 || item.paintedWidth > item.width + 1 || item.paintedHeight > item.height + 1)
                    bad.push(String(item.text) + " " + JSON.stringify({x:at.x, width:item.width, ink:item.paintedWidth, page:page.width}))
            }
            return bad
        }
        function test_resize_data() {
            const screens = ["library", "book", "studio", "listen", "read", "voice", "listen-settings", "sleep", "look", "devices", "studio-settings", "advanced"]
            const rows = []
            for (const mode of ["light", "dark"]) for (const screen of screens)
                rows.push({tag: mode + "_" + screen, screen: screen, mode: mode})
            return rows
        }
        function ready(page) { VisualReady.waitForSettledFrame(this, host.Window.window, page, qtVisualReady) }
        function test_resize(d) {
            Theme.mode = d.mode
            const factory = d.screen === "library" ? library : d.screen === "book" ? book : d.screen === "studio" ? studio : ["listen", "read"].includes(d.screen) ? now : settings
            const page = createTemporaryObject(factory, host, {width: 840, height: 840})
            verify(page)
            if (factory === settings) page.active = d.screen === "listen-settings" ? "listen" : d.screen === "studio-settings" ? "studio" : d.screen
            if (factory === now) { page.show(); if (d.screen === "read") page.page = 1 }
            ready(page)
            const controls = descendants(page, p => shown(p) && p.enabled && p.activeFocusOnTab === true)
            verify(controls.length > 0, "fixture must expose a keyboard control")
            const focused = controls[0]
            focused.forceActiveFocus(Qt.TabFocusReason)
            verify(focused.activeFocus, "fixture must really hold focus")
            const scrollers = descendants(page, p => shown(p) && p.contentY !== undefined && p.contentHeight > p.height + 100)
            const scroller = scrollers.length ? scrollers[0] : null
            if (d.screen === "read") findChild(page, "nowReadAlong").manual()
            if (scroller) { scroller.contentY = (scroller.originY || 0) + (d.screen === "read" ? 400 : 80); ready(page) }
            const before = scroller ? scroller.contentY - (scroller.originY || 0) : 0
            const readingIndex = d.screen === "read" && scroller ? scroller.indexAt(scroller.width / 2, scroller.contentY + 1) : -1
            const readingOffset = readingIndex >= 0 ? scroller.itemAtIndex(readingIndex).y - scroller.contentY : 0
            if (d.screen === "read") console.log("READ_ANCHOR " + JSON.stringify({initial: readingIndex, offset: readingOffset, saved: findChild(page, "nowReadAlong").viewportAnchor}))
            for (const width of [560, 839, 840, 1199, 1200, 1600, 840]) {
                page.width = width
                ready(page)
                compare(frameErrors(page), [], d.tag + " at " + width)
                verify(focused.activeFocus, "resize lost focus: " + d.tag + " at " + width)
                if (readingIndex >= 0) {
                    console.log("READ_RESIZE " + JSON.stringify({width: width, index: scroller.indexAt(scroller.width / 2, scroller.contentY + 1), y: scroller.contentY, saved: findChild(page, "nowReadAlong").viewportAnchor, following: findChild(page, "nowReadAlong").following}))
                    // Wrapped text changes paragraph heights. Preserve the same
                    // paragraph and its viewport offset, not a stale pixel count.
                    compare(scroller.indexAt(scroller.width / 2, scroller.contentY + 1), readingIndex, "resize lost reading paragraph at " + width)
                    fuzzyCompare(scroller.itemAtIndex(readingIndex).y - scroller.contentY, readingOffset, 1, "resize moved reading anchor at " + width)
                } else if (scroller && scroller.contentHeight - scroller.height >= before)
                    fuzzyCompare(scroller.contentY - (scroller.originY || 0), before, 1, "resize lost scroll: " + d.tag + " at " + width + " (" + scroller.objectName + ")")
                if (qtWideShotDir !== "" && [560, 840, 1200, 1600].includes(width))
                    grabImage(page).save(qtWideShotDir + "/acceptance_" + d.tag + "_" + width + ".png")
            }
        }
        function test_geometryControlCatchesShift() {
            const page = createTemporaryObject(settings, host, {width: 840, height: 840, active: "look"})
            ready(page)
            compare(frameErrors(page), [])
            const text = descendants(page, p => shown(p) && p.paintedWidth > 0)[0]
            verify(text)
            text.x += page.width
            verify(frameErrors(page).length > 0, "geometry control must reject a shifted label")
        }
    }
}
