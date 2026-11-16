import QtQuick
import ABook

// Connections that keep their handlers: a Connections declared as a child lives outside the visual tree, so its handler
// functions (QML property storage) would depend on the collector's weak QObject-wrapper pass. Keep.hold anchors the wrapper
// for the object's lifetime (src/keep.h). Use Listen wherever a Connections would be a child; tests/test_qt_keep_anchor.py
// rejects a bare child Connections in qml/.
Connections {
    id: listen
    Component.onCompleted: Keep.hold(listen)
}
