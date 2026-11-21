import QtQuick
import QtTest
import ABook

// Objects outside the visual tree keep their QML property storage while they live. The collector marks that storage only
// through the object's JS wrapper; a QQuickItem wrapper marks its visual children, so a Reveal (after `parent = null`), a
// pointer handler declared in QML, a Connections (Listen) or a non-visual store declared as a child is kept only by the weak
// QObject-wrapper pass, which gives up when the topmost QObject ancestor is JS-owned. The scene below is exactly that:
// its owner is created without a parent and dropped, while the visible part lives on in the window. Before Keep.hold the
// first gc() freed the storage: progress/step/path read as 0 or "", and the Reveal no longer controlled its target.
Item {
    id: host
    width: 400
    height: 300

    Component {
        id: ownerFactory
        Item {
            property alias visiblePart: part
            Item {
                id: part
                width: 300
                height: 200
                property int heard: 0
                signal ping()
                Rectangle {
                    objectName: "faded"
                    width: 20
                    height: 20
                    Reveal { objectName: "reveal"; shown: true }
                }
                Flickable {
                    id: flick
                    width: 100
                    height: 100
                    contentHeight: 1000
                    SmoothWheel { objectName: "wheel"; flick: flick }
                }
                Item {
                    objectName: "other"
                    signal ping()
                }
                Listen {
                    objectName: "listen"
                    target: part
                    function onPing() { part.heard += 1 }
                }
                StudioQuery { objectName: "query"; path: "kept"; wanted: false }
            }
        }
    }

    TestCase {
        name: "Keep"
        when: windowShown

        // The owner is JS-owned and unreferenced; only the visible part stays (in the window and in this function).
        function floatingPart() {
            let owner = ownerFactory.createObject(null)
            verify(owner !== null)
            const part = owner.visiblePart
            part.parent = host
            owner = null
            // A later creation, so nothing about the last created object can still reference the owner.
            ownerFactory.createObject(host).destroy()
            return part
        }

        // gc() finishes a collection that may already be running (objects created during it are marked); the second
        // gc() is a whole new collection that sees the dropped owner.
        function collect() {
            gc()
            gc()
        }

        // Checked before any event is processed: the dropped owner is deleted (deleteLater) on the next turn of the loop.
        function test_revealKeepsItsStateAndStillControlsItsTarget() {
            const part = floatingPart()
            collect()
            const reveal = findChild(part, "reveal")
            compare(reveal.progress, 1)
            reveal.shown = false
            compare(reveal.shown, false)
            compare(findChild(part, "faded").enabled, false)
        }
        function test_smoothWheelKeepsItsStep() {
            const part = floatingPart()
            collect()
            compare(findChild(part, "wheel").step, 110)
        }
        // A new target connects the handler functions again, read from the property storage.
        function test_listenReconnectsItsHandlers() {
            const part = floatingPart()
            collect()
            const other = findChild(part, "other")
            findChild(part, "listen").target = other
            other.ping()
            compare(part.heard, 1)
        }
        function test_storeKeepsItsProperties() {
            const part = floatingPart()
            collect()
            compare(findChild(part, "query").path, "kept")
        }
        // The anchor never outlives the object: deleting the scene releases every held wrapper.
        function test_deletedObjectsAreReleased() {
            const before = Keep.count()
            const owner = ownerFactory.createObject(host)
            verify(Keep.count() >= before + 3)
            owner.destroy()
            tryVerify(function() { return Keep.count() === before }, 3000)
        }
    }
}
