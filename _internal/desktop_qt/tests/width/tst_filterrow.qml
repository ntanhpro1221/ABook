import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 900; height: 400
    Component {
        id: factory
        FilterRow {
            id: filters
            width: 220
            options: [
                {value: "all", label: "Tất cả"}, {value: "names", label: "Tên riêng"},
                {value: "speaker", label: "Ai nói câu này"}, {value: "voice", label: "Giọng đọc"},
                {value: "reading", label: "Cách đọc"}, {value: "split", label: "Tách nhóm"},
                {value: "other", label: "Việc khác"}
            ]
            value: "all"
            onPicked: value => { filters.value = value }
        }
    }
    TestCase {
        name: "FilterRow"
        when: windowShown
        function cleanup() { Theme.reduceMotion = false }
        function test_sevenFiltersScrollAndKeyboardSelectionStaysVisible() {
            Theme.reduceMotion = true
            const row = createTemporaryObject(factory, host)
            const view = findChild(row, "filterViewport")
            verify(waitForPolish(host.Window.window))
            compare(row.Accessible.role, Accessible.PageTabList)
            verify(view.interactive)
            compare(row.gap, 8)
            compare(row.height, 36)
            row.value = "other"
            const last = findChild(row, "filterTab_6")
            tryVerify(() => last.x >= view.contentX && last.x + last.width <= view.contentX + view.width + 1)
            compare(last.Accessible.role, Accessible.PageTab)
            compare(last.Accessible.selected, true)
            last.forceActiveFocus()
            keyClick(Qt.Key_Left)
            // The component emits the requested value; the caller owns selection.
            compare(row.value, "split")
            const previous = findChild(row, "filterTab_5")
            tryVerify(() => previous.x >= view.contentX && previous.x + previous.width <= view.contentX + view.width + 1)
            keyClick(Qt.Key_Right)
            compare(row.value, "other")
            row.width = row.ink + 6 * 12
            verify(waitForPolish(host.Window.window))
            tryVerify(() => Math.abs(row.gap - 12) < 0.01)
            tryCompare(view, "interactive", false)
            row.width = 900
            verify(waitForPolish(host.Window.window))
            tryCompare(view, "interactive", false)
            compare(row.gap, 24)
            tryCompare(view, "contentX", 0)
            row.width = 220
            verify(waitForPolish(host.Window.window))
            tryVerify(() => last.x >= view.contentX && last.x + last.width <= view.contentX + view.width + 1)
        }
    }
}
