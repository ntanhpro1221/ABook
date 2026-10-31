import QtQuick
import QtTest
import ABook

// Thanh bên thu gọn / mở rộng (qml/Sidebar.qml), dựng với Theme + Nav thật và Platform / Backend giả (tests/qml/stub).
// Đo: nút và Ctrl+B đổi trạng thái, rê vào dải hẹp mở tạm ĐÈ LÊN mà không đổi chỗ khung nội dung, bấm mục trong lớp đè thì đi tới và đóng,
// trạng thái nhớ qua Platform, khối nền mục đang mở bám theo cả hai trạng thái.
Item {
    id: host
    width: 900
    height: 600

    Component { id: sidebarFactory; Sidebar { height: 600 } }
    Component { id: spyFactory; SignalSpy {} }
    Component { id: contentFactory; Rectangle { property Item sbRef: null; x: sbRef ? sbRef.x + sbRef.width : 0; color: "#eeeeee"; y: 0; width: 600; height: 600 } }

    TestCase {
        id: test
        name: "Sidebar"
        when: windowShown
        property var sb: null
        property var content: null
        property var spy: null

        function init() {
            mouseMove(host, 850, 500)             // con trỏ ra khỏi chỗ thanh bên của bài trước
            Platform.reset()
            make()
        }
        function make() {
            sb = createTemporaryObject(sidebarFactory, host)
            content = createTemporaryObject(contentFactory, host, { sbRef: sb })
            spy = createTemporaryObject(spyFactory, host, { target: sb, signalName: "sectionRequested" })
        }

        function collapse() {
            sb.toggle()
            tryCompare(sb, "width", 56, 1500)
            tryCompare(sb.panel, "width", 56, 1500)
        }

        function test_startsExpandedAndWritesNothing() {
            compare(sb.expanded, true)
            compare(sb.width, 232)
            compare(sb.panel.width, 232)
            compare(Platform.writes, 0)
            compare(sb.toggleButton.tip, "Thu gọn (Ctrl+B)")
        }

        function test_toggleCollapsesExpandsAndPersists() {
            sb.toggle()
            compare(sb.expanded, false)
            compare(Platform.store["sidebarExpanded"], "0")
            tryCompare(sb, "width", 56, 1500)
            compare(sb.toggleButton.tip, "Mở rộng (Ctrl+B)")
            sb.toggle()
            compare(Platform.store["sidebarExpanded"], "1")
            tryCompare(sb, "width", 232, 1500)
            compare(sb.toggleButton.tip, "Thu gọn (Ctrl+B)")
        }

        function test_ctrlBToggles() {
            keyClick(Qt.Key_B, Qt.ControlModifier)
            tryCompare(sb, "expanded", false, 1000)
            compare(Platform.store["sidebarExpanded"], "0")
            keyClick(Qt.Key_B, Qt.ControlModifier)
            tryCompare(sb, "expanded", true, 1000)
            compare(Platform.store["sidebarExpanded"], "1")
        }

        function test_contentTakesTheFreedWidth() {
            compare(content.x, 232)
            collapse()
            compare(content.x, 56)
        }

        function test_hoverOverlaysWithoutMovingContent() {
            collapse()
            const x0 = content.x
            mouseMove(sb, 20, 200)
            wait(60) // fixed: proves absence
            compare(sb.peek, false)               // chưa đủ ~150 ms
            tryCompare(sb, "peek", true, 1000)
            tryCompare(sb.panel, "width", 232, 1500)
            compare(sb.width, 56)                 // chỗ chiếm trong bố cục không đổi
            compare(content.x, x0)                // khung nội dung không nhúc nhích
            verify(sb.overlay > 100)
            mouseMove(host, 700, 300)             // rê ra
            wait(100) // fixed: proves absence
            compare(sb.peek, true)                // chưa đủ ~300 ms
            tryCompare(sb, "peek", false, 1500)
            tryCompare(sb.panel, "width", 56, 1500)
            compare(content.x, x0)
        }

        function test_shortHoverDoesNotOpen() {
            collapse()
            mouseMove(sb, 20, 200)
            wait(60) // fixed: proves absence
            mouseMove(host, 700, 300)
            wait(400) // fixed: proves absence
            compare(sb.peek, false)
            compare(sb.panel.width, 56)
        }

        function test_clickInOverlayNavigatesAndCloses() {
            collapse()
            mouseMove(sb, 20, 200)
            tryCompare(sb, "peek", true, 1000)
            tryCompare(sb.panel, "width", 232, 1500)
            mouseClick(sb, 100, 112)              // mục "Studio" (y 92..132) trong phần đè
            compare(spy.count, 1)
            compare(spy.signalArguments[0][0], 1)
            compare(sb.peek, false)
            wait(450) // fixed: proves absence
            compare(sb.peek, false)               // con trỏ còn trên thanh nhưng không mở lại cho tới khi rời
            tryCompare(sb.panel, "width", 56, 1500)
            compare(sb.width, 56)
        }

        function test_expandedHoverNeverPeeks() {
            mouseMove(sb, 20, 200)
            wait(400) // fixed: proves absence
            compare(sb.peek, false)
            compare(sb.panel.width, 232)
        }

        function test_stateIsRemembered() {
            sb.toggle()
            const other = createTemporaryObject(sidebarFactory, host)
            compare(other.expanded, false)
            compare(other.width, 56)              // dựng xong là đã thu gọn, không trượt từ 232
            compare(other.panel.width, 56)
            sb.toggle()
            const third = createTemporaryObject(sidebarFactory, host)
            compare(third.expanded, true)
            compare(third.width, 232)
        }

        function test_selectorTracksInBothStates() {
            sb.currentSection = 1
            compare(sb.selector.target.text, "Studio")
            tryCompare(sb.selector, "y", sb.selector.target.y, 1000)
            compare(sb.selector.width, sb.selector.target.width)
            collapse()
            tryCompare(sb.selector, "width", 40, 1000)
            compare(sb.selector.height, sb.selector.target.height)
            sb.currentSection = 2
            compare(sb.selector.target.text, "Cài đặt")
            tryCompare(sb.selector, "y", sb.selector.target.y, 1000)
        }

        function test_iconsKeepTheirRowWhenCollapsed() {
            const y0 = sb.selector.target.y
            collapse()
            compare(sb.selector.target.y, y0)     // cùng độ cao như lúc mở
        }
    }
}
