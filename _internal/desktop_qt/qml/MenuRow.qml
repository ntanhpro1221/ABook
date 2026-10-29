import QtQuick
import ABook

// Một hàng hành động trong bảng nổi (kiểu menu của Windows): biểu tượng + chữ thường, cả hàng là vùng bấm, rê chuột thì nền nhạt.
// Không chữ màu nhấn: màu nhấn dành cho nút chính của màn. `danger`: việc không hoàn tác được ("Xoá hồ sơ…") - chữ và icon màu --danger.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property bool danger: false

    property bool selected: false
    implicitHeight: Math.max(Theme.buttonHeight, label.implicitHeight + 2 * Theme.s8)
    Accessible.name: text
    Accessible.checked: selected

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Row {
        width: parent.width - 2 * Theme.s8
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Theme.s8
        spacing: Theme.s12
        Icon {
            name: root.icon
            size: 16
            color: root.danger ? Theme.danger : Theme.text2
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            width: parent.width - 16 - parent.spacing
            wrapMode: Text.Wrap
            text: root.text
            color: root.danger ? Theme.danger : Theme.text
            font.pixelSize: Theme.sizeBodySmall
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
