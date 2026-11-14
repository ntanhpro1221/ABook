import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 400
    height: 600
    property int built: 0
    property int alive: 0
    Component { id: factory
        Flickable {
            width: host.width; height: host.height
            contentWidth: width; contentHeight: list.height
            WindowedRows {
                id: list
                width: parent.width
                rows: Array.from({length: 200}, (_, i) => i)
                estimate: 80
                delegate: Component {
                    Item {
                        readonly property var rowData: parent.rowData
                        readonly property int rowIndex: parent.rowIndex
                        height: 80
                        Component.onCompleted: { host.built++; host.alive++ }
                        Component.onDestruction: host.alive--
                    }
                }
            }
        }
    }
    Component { id: castFactory
        Flickable {
            width: host.width; height: host.height
            contentWidth: width; contentHeight: cast.height
            CastPeople {
                id: cast
                width: parent.width
                people: Array.from({length: 200}, (_, i) => ({name: "person_" + i, displayName: "Person " + i, lines: 1, seconds: 3}))
            }
        }
    }
    Component { id: historyFactory
        HistoryList {
            width: host.width; height: host.height
            now: 1800000000000
            status: "ready"
            sessions: Array.from({length: 200}, (_, i) => ({id: "session_" + i, startedAt: 1800000000 - i, endedAt: 1800000000,
                listened: i, from: {chapterId: 1, seconds: 0}, to: {chapterId: 1, seconds: i}}))
        }
    }
    TestCase {
        name: "WindowedRows"
        when: windowShown
        function test_viewportBoundsAndScroll() {
            host.built = 0
            host.alive = 0
            const view = createTemporaryObject(factory, host)
            verify(view !== null)
            wait(100)
            verify(host.built > 0 && host.built <= 24, "Initial heavy rows: " + host.built)
            view.contentY = 10000
            wait(100)
            verify(host.alive > 0 && host.alive <= 24, "Live rows after scrolling: " + host.alive)
            view.contentY = 0
            wait(100)
            compare(view.contentHeight, 16000)
            verify(host.alive > 0 && host.alive <= 24)
        }
        function test_productionCastDoesNotInstantiateTwoHundredRevealingPeople() {
            const view = createTemporaryObject(castFactory, host)
            verify(view !== null)
            wait(350)
            function names(item) {
                let count = item.objectName === "castName" ? 1 : 0
                for (let i = 0; i < item.children.length; i++) count += names(item.children[i])
                return count
            }
            const first = names(view)
            verify(first > 0 && first <= 24, "Production CastPerson nodes: " + first)
            view.contentY = view.contentHeight - view.height
            wait(350)
            const last = names(view)
            verify(last > 0 && last <= 24, "Production CastPerson nodes at the bottom: " + last)
        }
        function test_productionHistoryBoundsRowsWhenTheDayOpens() {
            const view = createTemporaryObject(historyFactory, host)
            verify(view !== null)
            wait(300)
            const day = findChild(view, "historyDay")
            verify(day !== null)
            day.expanded = true
            wait(500)
            function countRows(item) {
                let count = item.objectName === "historySession" ? 1 : 0
                for (let i = 0; i < item.children.length; i++) count += countRows(item.children[i])
                return count
            }
            const count = countRows(view)
            verify(count > 0 && count <= 24, "Production history rows: " + count)
            const flick = findChild(view, "historyFlick")
            flick.contentY = flick.contentHeight - flick.height
            wait(350)
            const bottom = countRows(view)
            verify(bottom > 0 && bottom <= 24, "History at the bottom: " + bottom)
        }
    }
}
