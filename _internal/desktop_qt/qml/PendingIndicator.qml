import QtQuick
import ABook

Item {
    id: root
    property bool pending: false
    property bool shown: false
    property color color: Theme.accentText
    implicitWidth: 20
    implicitHeight: 20
    onPendingChanged: { delay.stop(); shown = false; if (pending) delay.start() }
    Component.onCompleted: if (pending) delay.start()
    Timer { id: delay; interval: 180; onTriggered: root.shown = root.pending }
    Icon {
        anchors.centerIn: parent; name: "loader-circle"; color: root.color; size: Math.min(root.width, root.height)
        opacity: root.shown ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 180 } }
        RotationAnimator on rotation { from: 0; to: 360; loops: Animation.Infinite; duration: Theme.spinMs; running: root.shown && Nav.uiVisible && !Theme.reduceMotion }
    }
}
