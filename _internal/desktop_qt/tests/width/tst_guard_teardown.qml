import QtQuick
import QtTest
import ABook

// Gate 22: "QML SmoothWheel: Cannot find member data" (twice) at NowPlaying.qml:225 when a NowPlaying scene was torn down in
// the full WidthTests run. Qt prints it when a QML-declared property is read or written after the object's property storage
// was collected. Outside a real wheel turn the only reader of SmoothWheel's storage was the glide binding `target: root.flick`;
// the target is now set when a wheel turn starts. tests/test_qt_keep_anchor.py rejects that binding shape; this file checks
// that the wheel still glides, Reveal still controls its item, and tearing their items down first (then gc()) is quiet.
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
            // The deferred deletes run; the wheel and the Reveal go with their items and release their anchors.
            tryVerify(function() { return scene.faded === null && scene.flick === null && Keep.count() === held - 2 })
            gc()
            gc()
            compare(Keep.count(), held - 2)
        }
    }
}
