import QtQuick
import QtTest
import ABook

// Gates 22 and 23: "QML SmoothWheel: Cannot find member data" at NowPlaying.qml:225 in full WidthTests runs, at the start of
// the test after a NowPlaying scene was torn down. Qt prints it when a QML-declared OBJECT property (the old QML
// SmoothWheel's `flick` or `glide`) is read or written after the object's QML property storage (MemberData) is gone; real
// properties then read as 0 without a word. Keep.hold anchored the wrapper and gate 22 removed the glide binding, and gate 23
// still printed it once: the path that loses the storage of an anchored handler was not isolated (three full diagnostic runs,
// none reproduced). SmoothWheel is now a C++ type (src/smoothwheel.h) with no QML-declared property, so there is no storage to
// lose. test_wheelHasNoQmlStorageToLose drops the storage the way a collection does: the QML component (8f08a6d6e) printed the
// warning on the wheel turn and did not scroll (4 of 4 runs); the C++ type has none to drop and glides.
Item {
    id: host
    width: 400
    height: 300

    TestCase {
        name: "GuardTeardown"
        when: windowShown

        Component {
            id: realScene
            Item {
                width: 300
                height: 200
                property alias flick: flick
                property alias faded: faded
                Flickable {
                    id: flick
                    width: 200; height: 100; contentHeight: 2000
                    SmoothWheel { objectName: "wheel"; flick: flick }
                }
                Rectangle {
                    id: faded
                    y: 120; width: 20; height: 20
                    property bool open: true
                    Reveal { objectName: "reveal"; shown: faded.open }
                }
            }
        }

        function test_wheelHasNoQmlStorageToLose() {
            failOnWarning(/Cannot find member data/)
            const scene = createTemporaryObject(realScene, host)
            verify(scene !== null)
            const wheel = findChild(scene, "wheel")
            verify(wheel !== null)
            qtStorage.drop(wheel)
            verify(!qtStorage.has(wheel))
            mouseWheel(scene.flick, 50, 50, 0, -120)
            tryVerify(function() { return scene.flick.contentY > 0 })
        }

        // The real types: the wheel still glides, the Reveal still controls its item, and tearing the item down first is quiet.
        function test_realTypesStillWorkAndTearDownQuietly() {
            failOnWarning(/Cannot find member data/)
            const scene = createTemporaryObject(realScene, host)
            verify(scene !== null)
            mouseWheel(scene.flick, 50, 50, 0, -120)
            tryVerify(function() { return scene.flick.contentY > 0 })
            scene.faded.open = false
            tryCompare(scene.faded, "visible", false)
            compare(scene.faded.enabled, false)
            scene.faded.open = true
            tryCompare(scene.faded, "opacity", 1)
            verify(scene.faded.visible)
            const held = Keep.count()
            scene.faded.destroy()
            scene.flick.destroy()
            // The deferred deletes run; the wheel and the Reveal go with their items, and the Reveal releases its anchor.
            tryVerify(function() { return scene.faded === null && scene.flick === null && Keep.count() === held - 1 })
            gc()
            gc()
            compare(Keep.count(), held - 1)
        }
    }
}
