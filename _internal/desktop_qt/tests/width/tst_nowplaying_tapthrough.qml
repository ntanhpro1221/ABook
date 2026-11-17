import QtQuick
import QtTest
import ABook

// Đang nghe phủ lên thư viện (17-11): bấm một nút của nó thì cú bấm không được tới bìa / dòng của thư viện nằm dưới. Mọi thứ bấm được của thư viện
// là Interactive (TapHandler thụ động), nên cảnh thử đặt một Interactive phủ cả khung dưới NowPlaying thật: nó đếm mọi cú bấm lọt xuống.
// Đo trước khi sửa: nút của NowPlaying (TapHandler thụ động) để cú bấm tới cả Interactive nằm dưới dù TapShield đã nhận cú bấm.
// Kèm đối chứng: kéo thanh tua vẫn tua, kéo danh sách chương vẫn cuộn (cú bấm giữ riêng không giành mất cú kéo của Flickable).
Item {
    id: host
    width: 1440; height: 1000
    Component {
        id: scene
        Item {
            id: content
            property alias bar: mini
            property alias now: now
            property int libraryTaps: 0
            // Như Main.qml: nút Back (nút bên) của chuột lùi một lớp ở bất cứ đâu trong cửa sổ
            TapHandler { acceptedButtons: Qt.BackButton; gesturePolicy: TapHandler.ReleaseWithinBounds; onTapped: Nav.back() }
            Interactive {
                objectName: "libraryUnder"
                anchors.fill: parent
                onClicked: content.libraryTaps++
            }
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
        name: "NowPlayingTapThrough"
        when: windowShown
        function init() {
            Platform.reset(); DesktopApi.reset(); Api.bind(DesktopApi, Theme)
            Api.preferences = {}; Nav.layers = []; Nav.uiVisible = true
            Theme.reduceMotion = true
            Player.open("width", 1, 0, true); Player.pause(); Player.setSleep("off")
        }
        function cleanup() { Nav.layers = []; Player.pause(); Theme.reduceMotion = false }
        function sizes() {
            return [{tag: "narrow", width: 792, height: 900}, {tag: "wide", width: 1200, height: 900}]
        }
        function openScene(data) {
            const content = createTemporaryObject(scene, host, {width: data.width, height: data.height})
            verify(content !== null)
            tryCompare(content.bar, "appear", 1)
            content.now.show()
            tryCompare(content.now, "p", 1)
            return content
        }
        function tap(item) {
            verify(item !== null && item.visible, "missing target")
            mouseClick(item, item.width / 2, item.height / 2)
        }

        // Chip mở bảng, nút phát, núm chuyển trang, chỗ trống: việc của chính nút xảy ra, thư viện nằm dưới không nhận gì.
        function test_buttonsKeepTheirTap_data() { return sizes() }
        function test_buttonsKeepTheirTap(data) {
            const content = openScene(data), page = content.now
            for (const name of ["Speed", "Sleep"]) {
                const sheet = findChild(page, "now" + name + "Sheet")
                tap(findChild(page, "now" + name))
                tryCompare(sheet, "open", true)
                compare(content.libraryTaps, 0, name + " chip: the tap reached the library under Now Playing")
                sheet.close(); tryCompare(sheet, "visible", false)
            }
            const more = findChild(page, "nowMore")
            tap(more)
            tryVerify(() => Nav.layers.length > 1, 1000, "the more button opened nothing")
            compare(content.libraryTaps, 0, "more button: the tap reached the library")
            Nav.back(); tryVerify(() => Nav.layers.length === 1)

            verify(!Player.playing)
            tap(findChild(page, "nowPlay"))
            tryCompare(Player, "playing", true)
            compare(content.libraryTaps, 0, "play button: the tap reached the library")
            Player.pause()

            // Chỗ trống của Đang nghe (TapShield)
            mouseClick(page, page.width - 4, page.height / 2)
            compare(content.libraryTaps, 0, "empty space: the tap reached the library")
            compare(page.open, true)
        }

        // Hàng chương (ListView trong Đang nghe): bấm là nghe chương ấy, không tới thư viện.
        function test_chapterRowKeepsItsTap() {
            const content = openScene({width: 1200, height: 900}), page = content.now
            page.sidePage = 0          // cột phải: Chương (mặc định là Đọc theo)
            const list = findChild(page, "nowChapterList")
            tryVerify(() => list.visible && list.count > 3)
            const row = list.itemAtIndex(2)
            verify(row !== null)
            tap(row)
            tryVerify(() => Player.chapters.rowOf(Player.chapterId) === 2, 2000, "the chapter row did not play its chapter")
            compare(content.libraryTaps, 0, "chapter row: the tap reached the library")
        }

        // Soát 17-11: khiên của Đang nghe từng nuốt cả nút Back của chuột, nên Back không đóng được Đang nghe. Back trên chỗ trống hay trên một nút
        // đều thu Đang nghe lại, không tới thư viện.
        function test_mouseBackClosesNowPlaying_data() { return [{tag: "emptySpace"}, {tag: "onButton"}] }
        function test_mouseBackClosesNowPlaying(data) {
            const content = openScene({width: 1200, height: 900}), page = content.now
            if (data.tag === "onButton") {
                const chip = findChild(page, "nowSpeed")
                mouseClick(chip, chip.width / 2, chip.height / 2, Qt.BackButton)
            } else {
                mouseClick(page, page.width - 4, page.height / 2, Qt.BackButton)
            }
            tryCompare(page, "open", false, 1000, "mouse Back did not close Now Playing")
            compare(findChild(page, "nowSpeedSheet").open, false)
            compare(content.libraryTaps, 0)
        }

        // Đối chứng 1: kéo thanh tua vẫn tua tới chỗ thả.
        function test_seekBarStillDrags() {
            const content = openScene({width: 1200, height: 900}), page = content.now
            const seek = findChild(page, "nowSeek")
            tryVerify(() => seek.enabled && Player.clock.duration > 0)
            const y = seek.height / 2
            mousePress(seek, seek.width * 0.1, y)
            for (let k = 1; k <= 10; ++k) mouseMove(seek, seek.width * (0.1 + 0.05 * k), y, -1, Qt.LeftButton)
            mouseRelease(seek, seek.width * 0.6, y, Qt.LeftButton)
            tryVerify(() => Math.abs(Player.clock.position - 0.6 * Player.clock.duration) < 0.02 * Player.clock.duration, 2000,
                      "drag ended at " + Player.clock.position + " of " + Player.clock.duration)
            compare(content.libraryTaps, 0)
        }

        // Đối chứng 2: kéo danh sách chương bắt đầu trên một hàng vẫn cuộn danh sách, không nghe hàng ấy, không tới thư viện.
        function test_chapterListStillScrolls() {
            const content = openScene({width: 1200, height: 700}), page = content.now
            page.sidePage = 0          // cột phải: Chương (mặc định là Đọc theo)
            const list = findChild(page, "nowChapterList")
            tryVerify(() => list.visible && list.contentHeight > list.height + 200)
            list.positionViewAtBeginning()
            const before = Player.chapterId, x = list.width / 2, y0 = list.height * 0.8
            mousePress(list, x, y0)
            for (let k = 1; k <= 12; ++k) { wait(16); mouseMove(list, x, y0 - 25 * k, -1, Qt.LeftButton) }
            mouseRelease(list, x, y0 - 300, Qt.LeftButton)
            tryVerify(() => list.contentY > 150, 2000, "the chapter list did not scroll: contentY " + list.contentY)
            compare(Player.chapterId, before, "dragging the list played the row under the pointer")
            compare(content.libraryTaps, 0)
        }
    }
}
