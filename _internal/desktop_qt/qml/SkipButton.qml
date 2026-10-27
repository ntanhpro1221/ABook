import QtQuick
import ABook

// Tua 15 giây: cung nông + số 15 bên dưới (SkipGlyph, đúng hình của bản web). Dùng ở thanh phát và màn Đang nghe.
Interactive {
    id: root
    property bool forward: true
    property int iconSize: 28
    implicitWidth: Theme.buttonHeight
    implicitHeight: Theme.buttonHeight
    tip: forward ? `Tới ${Player.skipSeconds} giây (→)` : `Lùi ${Player.skipSeconds} giây (←)`
    onClicked: Player.skip(forward ? Player.skipSeconds : -Player.skipSeconds)
    enabled: Player.loaded
    opacity: enabled ? 1 : 0.4

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
    }
    SkipGlyph {
        anchors.centerIn: parent
        size: root.iconSize
        forward: root.forward
        color: Theme.text
        family: Theme.family
    }
}
