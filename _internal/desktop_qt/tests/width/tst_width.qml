import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 2560
    height: 1080
    Component { id: bookFactory; BookPage {} }
    Component { id: libraryFactory; LibraryScreen {} }
    Component { id: nowFactory; NowPlaying {} }
    Component { id: settingsFactory; SettingsScreen {} }
    Component { id: studioFactory; StudioScreen {} }
    Component { id: rowFactory; ChapterRow {} }

    TestCase {
        name: "Width"
        when: windowShown
        function init() { Theme.reduceMotion = true; Platform.reset(); Backend.library.count = 200 }
        function cleanup() { Theme.reduceMotion = false }
        function sizes() {
            return [
                {tag: "1024x700", w: 1024, h: 700, sidebar: 232},
                {tag: "1440x900", w: 1440, h: 900, sidebar: 232},
                {tag: "1920x1080", w: 1920, h: 1080, sidebar: 232},
                {tag: "rail1024", w: 1024, h: 700, sidebar: 56},
                {tag: "rail1920", w: 1920, h: 1080, sidebar: 56},
                {tag: "compact", w: 560, h: 700, sidebar: 56}
            ]
        }
        function make(factory, data, extra) {
            let props = {width: data.w - data.sidebar, height: data.h - 120}
            if (extra) for (let k in extra) props[k] = extra[k]
            let item = createTemporaryObject(factory, host, props)
            verify(item !== null)
            wait(50)
            return item
        }
        function test_book_data() { return sizes().concat([{tag: "2560", w: 2560, h: 1080, sidebar: 232}]) }
        // Measure painted text, not the row/background/Column width. Right-aligned
        // Text has a leading offset inside its box; wrapped text uses paintedWidth.
        function textInkRight(item, page) {
            if (!item.visible || item.opacity === 0) return 0
            let right = 0
            if (item.text !== undefined && item.paintedWidth !== undefined && item.text !== "") {
                let offset = 0
                if (item.horizontalAlignment === Text.AlignRight) offset = item.width - item.paintedWidth
                else if (item.horizontalAlignment === Text.AlignHCenter) offset = (item.width - item.paintedWidth) / 2
                right = item.mapToItem(page, offset + item.paintedWidth, 0).x
            }
            for (let child of item.children) right = Math.max(right, textInkRight(child, page))
            return right
        }
        function test_bookInk_data() {
            return [{tag: "1920", w: 1920, h: 1080, sidebar: 232},
                    {tag: "2560", w: 2560, h: 1080, sidebar: 232}]
        }
        function test_bookInk(data) {
            const page = make(bookFactory, data, {book: {bookId: "width", title: "Sách"}})
            const list = findChild(page, "bookChapters")
            tryCompare(list, "count", 32)
            let right = 0
            let rows = 0
            let worstEmpty = 0
            for (let row of list.contentItem.children) {
                if (row.objectName !== "bookChapterRow" || row.y < list.contentY
                    || row.y + row.height > list.contentY + list.height) continue
                const rowRight = textInkRight(row, page)
                right = Math.max(right, rowRight)
                worstEmpty = Math.max(worstEmpty, (page.width - rowRight) / page.width)
                rows++
            }
            verify(rows >= 4)
            const empty = (page.width - right) / page.width
            console.log("ROW_INK window=" + data.w + " content=" + page.width
                        + " right=" + right.toFixed(2) + " empty=" + (empty * 100).toFixed(2) + "%")
            verify(empty <= 0.35, "empty band after painted row text: " + (empty * 100).toFixed(2) + "% > 35%")
            verify(worstEmpty <= 0.35, "every visible row must reach the ink threshold")
        }
        function test_trackRow_data() {
            return [{tag: "compact-dark", w: 300, mode: "dark"},
                    {tag: "wide-dark", w: 940, mode: "dark"},
                    {tag: "compact-light", w: 300, mode: "light"},
                    {tag: "wide-light", w: 940, mode: "light"}]
        }
        function test_trackRow(data) {
            Theme.mode = data.mode
            const row = createTemporaryObject(rowFactory, host, {width: data.w,
                title: "Chương 12", subtitle: "Con đường rất dài bên bờ sông trong buổi sáng đầu mùa",
                length: "1 giờ 12 phút", progress: 0.4})
            verify(row !== null)
            const duration = findChild(row, "chapterDuration")
            const fill = findChild(row, "chapterFill")
            const progress = findChild(row, "chapterProgress")
            fuzzyCompare(duration.x + duration.paintedWidth, row.width - Theme.s12, 0.5)
            compare(duration.font.features.tnum, 1)
            compare(fill.width, row.width)
            fuzzyCompare(progress.width, (row.width - progress.x - Theme.s12) * 0.4, 0.5)
            verify(progress.visible)
            // Render at the far end of the row, beyond the short title's ink.
            mouseMove(host, 1500, 1000)
            wait(200)
            const plain = grabImage(row).red(data.w - 20, 5)
            mouseMove(row, data.w - 20, 5)
            tryCompare(row, "hovered", true)
            wait(200)
            verify(grabImage(row).red(data.w - 20, 5) !== plain, "hover must paint the row end")
            row.current = true
            wait(200)
            compare(fill.opacity, 1)
            verify(grabImage(row).red(data.w - 20, 5) !== plain, "current fill must paint the row end")
            row.done = true
            compare(progress.visible, false)
            row.status = "Chưa có audio"
            compare(duration.visible, false)
            verify(row.detail.indexOf("Chưa có audio") >= 0)
            Theme.mode = "auto"
        }
        function test_book(data) {
            const page = make(bookFactory, data, {book: {bookId: "width", title: "Hành trình qua những miền đất mới", author: "Người kể chuyện", chapters: 32, detail: "8 giờ", progress: 0.2}})
            const cover = findChild(page, "bookCover")
            const list = findChild(page, "bookChapters")
            tryCompare(list, "count", 32)
            verify(cover.height <= data.h * 0.45, "cover exceeds window cap")
            fuzzyCompare(cover.height / cover.width, 1.5, 0.01)
            let visible = 0
            for (let c of list.contentItem.children) {
                if (c.objectName !== "bookChapterRow") continue
                if (c.y >= list.contentY - 0.5 && c.y + c.height <= list.contentY + list.height + 0.5) visible++
                fuzzyCompare(c.width, list.width, 0.5, "row must fill the column")
            }
            if (data.w >= 1024) verify(visible >= 4, "only " + visible + " complete chapter rows")
            const summary = findChild(page, "bookSummary")
            const region = findChild(page, "bookChapterRegion")
            const a = summary.mapToItem(page, 0, 0)
            const b = region.mapToItem(page, 0, 0)
            verify(Math.min(a.x, b.x) <= page.width * 0.35)
            verify(page.width - Math.max(a.x + summary.width, b.x + region.width) <= page.width * 0.35)
            if (page.expanded) {
                verify(summary.width + Theme.s32 + region.width <= 1360.5, "composition exceeds cap")
                fuzzyCompare(a.x, page.width - b.x - region.width, 0.5, "composition must be centred")
                const title = findChild(page, "bookTitle")
                fuzzyCompare(cover.mapToItem(page, 0, 0).x, title.mapToItem(page, 0, 0).x, 1,
                             "cover and title must share their left edge")
            } else {
                fuzzyCompare(b.x + region.width, page.width - Theme.margin, 0.5)
            }
            const top = findChild(page, "scrollFadeTop")
            const bottom = findChild(page, "scrollFadeBottom")
            compare(top.visible, false)
            compare(bottom.visible, true)
            const coverY = cover.mapToItem(page, 0, 0).y
            list.positionViewAtEnd()
            list.contentY = list.originY + list.contentHeight - list.height + list.bottomMargin
            wait(30)
            compare(top.visible, true)
            compare(bottom.visible, false)
            compare(cover.mapToItem(page, 0, 0).y, coverY, "summary must stay fixed while chapters scroll")
        }
        function test_library_data() {
            return sizes().concat([{tag: "2560", w: 2560, h: 1080, sidebar: 232}])
        }
        function test_library(data) {
            const page = make(libraryFactory, data)
            verify(page.coverW >= 160 && page.coverW <= 200, "cover width " + page.coverW)
            const row = findChild(page, "libraryGridRow")
            verify(row !== null)
            const p = row.mapToItem(page, 0, 0)
            fuzzyCompare(p.x, page.width - p.x - row.width, 0.5, "grid margins differ")
            verify(p.x <= page.width * 0.35)
        }
        function test_shortLibraryCentred() {
            Backend.library.count = 3
            const page = make(libraryFactory, sizes()[2])
            const row = findChild(page, "libraryGridRow")
            const p = row.mapToItem(page, 0, 0)
            fuzzyCompare(p.x, page.width - p.x - row.width, 0.5)
        }
        function test_nowPlaying_data() { return sizes() }
        function test_nowPlaying(data) {
            const page = make(nowFactory, data, {height: data.h - 40})
            page.show()
            tryCompare(page, "p", 1)
            const region = findChild(page, "nowReadAlongRegion")
            const read = findChild(page, "nowReadAlong")
            const beside = page.width >= Theme.widthLarge
            compare(region.visible, beside)
            if (beside) {
                verify(read.visible)
                verify(region.x >= page.colX + page.colW)
                fuzzyCompare(region.x + region.width, page.width - Theme.margin, 0.5)
                verify(region.width > 500)
            } else {
                page.page = 1
                tryCompare(region, "visible", true)
            }
            page.close()
        }
        function test_settings_data() { return sizes() }
        function test_settings(data) {
            const page = make(settingsFactory, data)
            const a = findChild(page, "settingsGroups")
            const b = findChild(page, "settingsContent")
            if (page.width >= Theme.widthExpanded) {
                verify(a.visible && b.visible)
                verify(b.x >= a.width + Theme.s32 - 1)
            } else {
                verify(a.visible && !b.visible)
                page.active = "look"
                wait(20)
                verify(!a.visible && b.visible)
                fuzzyCompare(b.x, a.x, 0.5)
            }
            const p = a.mapToItem(page, 0, 0)
            const q = b.mapToItem(page, b.width, 0)
            fuzzyCompare(p.x, page.width - q.x, 0.5)
        }
        function test_transitionAndReducedMotion() {
            Theme.reduceMotion = false
            const page = make(bookFactory, {w: 839, h: 900, sidebar: 0}, {book: {bookId: "width", title: "Sách"}})
            const cover = findChild(page, "bookCover")
            const info = findChild(page, "bookInfo")
            const summary = findChild(page, "bookSummary")
            const chapters = findChild(page, "bookChapterRegion")
            page.width = 1200
            wait(40)
            verify(page.split > 0 && page.split < 1, "class transition must have intermediate geometry")
            for (let direction = 0; direction < 2; direction++) {
                for (let frame = 0; frame < 12; frame++) {
                    verify(info.x >= cover.x + cover.width - 0.5 || info.y >= cover.height - 0.5,
                           "moving text must stay clear of the cover")
                    verify(chapters.x >= summary.width - 0.5 || chapters.y >= summary.height - 0.5,
                           "moving chapters must stay clear of the summary")
                    wait(20)
                }
                if (direction === 0) page.width = 839
            }
            page.width = 1200
            tryCompare(page, "split", 1)
            Theme.reduceMotion = true
            page.width = 700
            tryCompare(page, "split", 0, 50)
        }
        function test_sidebarChangesContentClass() {
            const page = make(bookFactory, {w: 1024, h: 700, sidebar: 232})
            compare(page.expanded, false)
            page.width = 1024 - 56
            compare(page.expanded, true)
        }
        function test_studioCentred() {
            const page = make(studioFactory, sizes()[2])
            for (let c of page.children) {
                verify(c.width <= 880)
                fuzzyCompare(c.x, (page.width - c.width) / 2, 0.5)
            }
        }
    }
}
