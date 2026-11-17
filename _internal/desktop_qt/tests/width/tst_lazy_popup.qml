import QtQuick
import QtTest
import ABook

Item {
    id: host
    width: 900; height: 700
    Item { id: anchor; x: 420; y: 150; width: 40; height: 40 }
    Component {
        id: factory
        LazyPopup {
            sourceComponent: Popover {
                id: body
                anchorItem: anchor
                property int preserved: 0
                Column {
                    width: parent.width
                    Button { text: "Test action"; onActivated: body.preserved++ }
                }
            }
        }
    }
    TestCase {
        name: "LazyPopup"
        when: windowShown
        function cleanup() { Nav.layers = [] }
        function test_firstUseRetainsOwnerAndExitAnimation() {
            const popup = createTemporaryObject(factory, host)
            compare(popup.item, null)
            popup.close()
            compare(popup.item, null, "closing an unused popup creates nothing")
            popup.show()
            const owner = popup.item
            verify(owner !== null && owner.open)
            tryCompare(owner, "shown", 1)
            owner.preserved = 7
            popup.close()
            compare(popup.item, owner)
            tryCompare(owner, "shown", 0)
            compare(popup.open, false)
            popup.toggle()
            compare(popup.item, owner)
            compare(owner.preserved, 7)
            compare(popup.open, true)
            popup.close()
            tryCompare(owner, "shown", 0)
        }
    }
}
