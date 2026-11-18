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
            tryVerify(() => host.built > 0 && host.built <= 24, 5000, "Initial heavy rows")
            view.contentY = 10000
            tryVerify(() => host.alive > 0 && host.alive <= 24, 5000, "Live rows after scrolling")
            view.contentY = 0
            tryCompare(view, "contentHeight", 16000)
            tryVerify(() => host.alive > 0 && host.alive <= 24)
        }
        function test_productionCastDoesNotInstantiateTwoHundredRevealingPeople() {
            const view = createTemporaryObject(castFactory, host)
            verify(view !== null)
            function names(item) {
                let count = item.objectName === "castName" ? 1 : 0
                for (let i = 0; i < item.children.length; i++) count += names(item.children[i])
                return count
            }
            tryVerify(() => names(view) > 0 && names(view) <= 24, 5000, "Production CastPerson nodes")
            view.contentY = view.contentHeight - view.height
            tryVerify(() => names(view) > 0 && names(view) <= 24, 5000, "Production CastPerson nodes at the bottom")
        }
        function test_productionHistoryBoundsRowsWhenTheDayOpens() {
            const view = createTemporaryObject(historyFactory, host)
            verify(view !== null)
            tryVerify(() => findChild(view, "historyDay") !== null)
            const day = findChild(view, "historyDay")
            verify(day !== null)
            day.expanded = true
            function countRows(item) {
                let count = item.objectName === "historySession" ? 1 : 0
                for (let i = 0; i < item.children.length; i++) count += countRows(item.children[i])
                return count
            }
            tryVerify(() => countRows(view) > 0 && countRows(view) <= 24, 5000, "Production history rows")
            const flick = findChild(view, "historyFlick")
            flick.contentY = flick.contentHeight - flick.height
            tryVerify(() => countRows(view) > 0 && countRows(view) <= 24, 5000, "History at the bottom")
        }
    }
}
