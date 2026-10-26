import QtQuick
import ABook

// Nút phụ: icon trơn, vùng bấm 40x40 trên máy tính, chú thích khi rê chuột (DESIGN.md mục 6b).
Interactive {
    id: root
    property string icon: ""
    property int iconSize: 20
    implicitWidth: Theme.buttonHeight
    implicitHeight: Theme.buttonHeight
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
    }
    Icon {
        anchors.centerIn: parent
        name: root.icon
        size: root.iconSize
        color: Theme.text
    }
}
