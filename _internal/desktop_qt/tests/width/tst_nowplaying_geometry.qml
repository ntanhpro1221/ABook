import QtQuick
import QtTest
import ABook
import "LayoutAudit.js" as Audit

Item {
    id: host
    width: 1440; height: 1000
    Component {
        id: scene
        Item {
            id: content
            x: 96; y: 32
            property alias bar: mini
            property alias now: now
            PlayerBar {
                id: mini
                anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
                onOpenRequested: now.show()
            }
            NowPlaying { id: now; anchors.fill: parent; bar: mini }
        }
    }
    TestCase {
        name: "NowPlayingGeometry"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.preferences = {}; Nav.layers = []; Nav.uiVisible = true
            Theme.reduceMotion = false
            Player.open("width", 1, 0, true); Player.pause(); Player.setSleep("off")
        }
        function cleanup() { Nav.layers = []; Player.pause(); Theme.reduceMotion = false }
        function sizes() {
            return [{tag: "narrow", width: 792, height: 900}, {tag: "wide", width: 1200, height: 900}]
        }
        function makeScene(data) {
            const content = createTemporaryObject(scene, host, {width: data.width, height: data.height})
            verify(content !== null)
            tryCompare(content.bar, "appear", 1)
            tryVerify(function() { return content.bar.height > 0 && content.now.coverW > 0 })
            return content
        }
        function sameBox(actual, expected, label, tolerance) {
            for (const key of ["x", "y", "w", "h"])
                fuzzyCompare(actual[key], expected[key], tolerance === undefined ? 0.01 : tolerance, label + "." + key)
        }
        function test_expandsFromMini_data() { return sizes() }
        function test_expandsFromMini(data) {
            const content = makeScene(data), page = content.now
            const mini = Audit.box(content.bar, host)
            let first = null, startP = -1
            // Synchronous opening edge: before the animation advances, read the real clip item.
            // Sampling after tryVerify(p > 0) would already miss the first frame.
            page.openChanged.connect(function() {
                if (page.open) { first = Audit.box(findChild(page, "nowMorphPanel"), host); startP = page.p }
            })
            mouseClick(content.bar, 8, content.bar.height / 2)
            tryCompare(page, "open", true)
            verify(first !== null)
            compare(startP, 0)
            sameBox(first, mini, "opening frame = mini in window", 2)
            tryVerify(function() { return page.p > 0 })
            tryCompare(page, "p", 1)
            sameBox(Audit.box(findChild(page, "nowMorphPanel"), host), Audit.box(page, host), "fully open", 2)
            page.close(); tryCompare(page, "p", 0)
        }
        function test_sheetsKeepContent_data() {
            const rows = []
            for (const size of sizes()) for (const sheet of ["Speed", "Sleep"])
                rows.push({tag: size.tag + sheet, width: size.width, height: size.height, sheet: sheet})
            return rows
        }
        function test_sheetsKeepContent(data) {
            const content = makeScene(data), page = content.now
            page.show(); tryCompare(page, "p", 1)
            const cover = findChild(page, "nowCover"), controls = findChild(page, "nowControls")
            verify(cover !== null && controls !== null)
            const beforeCover = Audit.box(cover, host), beforeControls = Audit.box(controls, host)
            const sheet = findChild(page, "now" + data.sheet + "Sheet")
            mouseClick(findChild(page, "now" + data.sheet))
            tryCompare(sheet, "open", true); tryCompare(sheet, "shown", 1)
            sameBox(Audit.box(cover, host), beforeCover, "cover under sheet")
            sameBox(Audit.box(controls, host), beforeControls, "controls under sheet")
            Nav.back(); tryCompare(sheet, "open", false); tryCompare(sheet, "shown", 0)
            compare(page.open, true)
            sameBox(Audit.box(cover, host), beforeCover, "cover after Back")
            sameBox(Audit.box(controls, host), beforeControls, "controls after Back")
            page.close(); tryCompare(page, "p", 0)
        }
    }
}
