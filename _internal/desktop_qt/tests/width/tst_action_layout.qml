import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 400; height: 300
    Component {
        id: fixture
        Item {
            property alias actions: actions
            property alias first: first
            property alias second: second
            width: host.width; height: host.height
            EditBookActions {
                id: actions
                width: parent.width
                Button { id: first; text: "Keep selection" }
                Button { id: second; text: "Save selection" }
            }
        }
    }
    Loader { id: loader; sourceComponent: fixture }
    TestCase {
        name: "ActionLayout"
        when: windowShown
        function init() { loader.active = false; host.width = 400; loader.active = true; tryVerify(() => loader.item !== null) }
        function test_wrapsAndKeepsEveryButtonInside() {
            const item = loader.item
            tryVerify(() => item.actions.height > 0)
            const oneLine = item.actions.height
            host.width = 150
            tryVerify(() => item.actions.height > oneLine)
            for (const button of [item.first, item.second]) {
                verify(button.x >= 0)
                verify(button.x + button.width <= item.actions.width + 0.1)
                verify(button.y + button.height <= item.actions.height + 0.1)
            }
            host.width = 400
            tryCompare(item.actions, "height", oneLine)
        }
        function test_dropsQueuedLayoutWithItsComponent() {
            for (let index = 0; index < 40; ++index) {
                loader.active = true
                verify(loader.item !== null)
                host.width = index % 2 ? 150 : 400
                loader.item.first.text = "Keep selection " + index
                loader.active = false
                compare(loader.item, null)
            }
            loader.active = true
            tryVerify(() => loader.item.actions.height > 0)
        }
    }
}
