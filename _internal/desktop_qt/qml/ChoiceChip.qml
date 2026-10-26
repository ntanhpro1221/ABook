import QtQuick
import ABook

// Ô chọn trong bảng nổi (tốc độ, hẹn giờ): chữ ngắn, ô đang chọn nền nhạt màu nhấn + chữ màu nhấn.
Interactive {
    id: root
    property string text: ""
    property bool selected: false
    implicitHeight: 36
    implicitWidth: label.implicitWidth + 2 * Theme.s12

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: root.selected ? Theme.accentSoft : Theme.sunken
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Theme.text
            opacity: root.pressed ? 0.10 : (root.hovered ? 0.05 : 0)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: root.selected ? Theme.accentText : Theme.text
        font.pixelSize: Theme.sizeBodySmall
        font.weight: root.selected ? Theme.weightMedium : Theme.weightRegular
    }
}
