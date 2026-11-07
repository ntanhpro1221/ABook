import QtQuick
import QtTest
import ABook
import "LayoutAudit.js" as Audit

Item {
    id: host
    width: 1440; height: 1000
    Component { id: continueFactory; LibraryContinue { width: 640; book: ({bookId: "width", title: "Hành trình qua miền đất mới", lastChapter: "Chương 1"}) } }
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
                contentShift: -now.g * 12
                contentOpacity: 1 - Math.min(1, now.g * 3)
                thumbShown: now.p <= 0
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
        function test_sharedPartsFollowTheirOwnPaths_data() { return sizes() }
        function test_sharedPartsFollowTheirOwnPaths(data) {
            const content = makeScene(data), page = content.now
            const chapterFrom = Audit.box(content.bar.chapterLabel, page)
            const bookFrom = Audit.box(content.bar.bookLabel, page)
            const playFrom = Audit.box(content.bar.playButton, page)
            page.show()
            sameBox({x: page.sharedFrames[0].from.x, y: page.sharedFrames[0].from.y, w: page.sharedFrames[0].from.width, h: page.sharedFrames[0].from.height}, chapterFrom, "chapter source")
            sameBox({x: page.sharedFrames[1].from.x, y: page.sharedFrames[1].from.y, w: page.sharedFrames[1].from.width, h: page.sharedFrames[1].from.height}, bookFrom, "book source")
            tryVerify(() => page.p > 0 && page.p < 1)
            const chapter = findChild(page, "nowChapterMorph"), play = findChild(page, "nowPlayMorph")
            const g = page.g, path = page.sharedFrames[0]
            fuzzyCompare(chapter.x, path.from.x + (path.to.x - path.from.x) * g, 0.01)
            fuzzyCompare(chapter.y, path.from.y + (path.to.y - path.from.y) * g, 0.01)
            fuzzyCompare(play.x, page.playFrom.x + (page.playTo.x - page.playFrom.x) * g, 0.01)
            fuzzyCompare(play.y, page.playFrom.y + (page.playTo.y - page.playFrom.y) * g, 0.01)
            fuzzyCompare(play.width * play.scale, playFrom.w + (56 - playFrom.w) * g, 0.01)
            compare(content.bar.sharedShown, false)
            tryCompare(page, "p", 1)
            page.close()
            // The mini's temporary -12 px exit transform must not change the
            // return endpoint; otherwise the last frame jumps back down.
            fuzzyCompare(page.playFrom.y, playFrom.y, 0.01)
            fuzzyCompare(page.sharedFrames[0].from.y, chapterFrom.y, 0.01)
            tryCompare(page, "p", 0)
            compare(content.bar.sharedShown, true)
        }
        function test_playPauseKeepsPlayerGeometry_data() { return sizes() }
        function test_playPauseKeepsPlayerGeometry(data) {
            const content = makeScene(data), page = content.now
            page.show(); tryCompare(page, "p", 1)
            const names = ["nowCover", "nowControls", "nowChapterTitle", "nowPlay"]
            const items = names.map(name => findChild(page, name))
            const boxes = items.map(item => Audit.box(item, host))
            for (let i = 0; i < 4; ++i) {
                Player.resume(); compare(Player.playing, true)
                for (let k = 0; k < items.length; ++k) sameBox(Audit.box(items[k], host), boxes[k], names[k] + " playing")
                Player.pause(); compare(Player.playing, false)
                for (let k = 0; k < items.length; ++k) sameBox(Audit.box(items[k], host), boxes[k], names[k] + " paused")
            }
            page.close(); tryCompare(page, "p", 0)
        }
        function test_continueButtonReservesBothLabels() {
            const row = createTemporaryObject(continueFactory, host)
            const button = findChild(row, "libraryContinuePlay"), copy = findChild(row, "libraryContinueCopy")
            const before = Audit.box(button, host), copyBefore = Audit.box(copy, host)
            for (let i = 0; i < 4; ++i) {
                Player.resume(); compare(button.text, "Tạm dừng")
                sameBox(Audit.box(button, host), before, "continue playing")
                sameBox(Audit.box(copy, host), copyBefore, "copy playing")
                Player.pause(); compare(button.text, "Nghe tiếp")
                sameBox(Audit.box(button, host), before, "continue paused")
                sameBox(Audit.box(copy, host), copyBefore, "copy paused")
            }
        }
        function test_readingHintHasItsOwnHeaderSpace() {
            const content = makeScene({width: 1200, height: 900}), page = content.now
            page.show(); tryCompare(page, "p", 1)
            tryCompare(ReadAlong, "status", "ready")
            const reader = findChild(page, "nowReadAlong")
            const hint = findChild(reader, "readerHint"), list = findChild(reader, "readAlongParagraphs")
            verify(hint.visible)
            verify(list.y >= hint.y + hint.height + Theme.s8, "Reading text must not scroll under its fixed hint")
            Player.resume(); Player.pause()
            verify(list.y >= hint.y + hint.height + Theme.s8)
            page.close(); tryCompare(page, "p", 0)
        }
        function test_readModeKeepsChapterAndTransport_data() { return sizes() }
        function test_readModeKeepsChapterAndTransport(data) {
            const content = makeScene(data), page = content.now
            page.show(); tryCompare(page, "p", 1)
            const chapter = findChild(page, "nowChapterTitle"), titles = chapter.parent
            page.page = 1; tryCompare(page, "pageT", 1)
            compare(chapter.opacity, 1)
            compare(titles.opacity, 1)
            verify(chapter.visible)
            verify(findChild(page, "nowControls").visible)
            if (!page.wide) {
                const text = findChild(page, "nowReadAlongRegion")
                verify(text.y >= titles.mapToItem(page, 0, 0).y + titles.height + Theme.s8)
            }
            page.page = 0; tryCompare(page, "pageT", 0)
            compare(titles.opacity, 1)
            page.close(); tryCompare(page, "p", 0)
        }
    }
}
