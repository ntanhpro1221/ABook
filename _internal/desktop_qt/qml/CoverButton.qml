import QtQuick
import ABook

// Nút đặt TRÊN bìa / ảnh (web LibraryScreen.tsx: tròn 44 px, nền panel, mực thường, shadow-card): tranh bìa tối hay sáng thì nút vẫn
// nổi rõ. IconButton trơn (icon không nền) chìm vào bìa tối - Lead soát 0.4.151; máy dò IconText bắt IconButton nằm trên bìa.
Interactive {
    id: root
    property string icon: ""
    property int iconSize: 16
    implicitWidth: 44
    implicitHeight: 44
    ringRadius: width / 2
    Shadow { kind: "card"; radius: root.ringRadius }
    Rectangle { anchors.fill: parent; radius: width / 2; color: Theme.panel }
    Rectangle {
        anchors.fill: parent
        radius: width / 2
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
