import QtQuick
import ABook

// Một hàng hành động trong bảng nổi (kiểu menu của Windows): biểu tượng + chữ thường, cả hàng là vùng bấm, rê chuột thì nền nhạt.
// Không chữ màu nhấn: màu nhấn dành cho nút chính của màn. `danger`: việc không hoàn tác được ("Xoá hồ sơ…") - chữ và icon màu --danger.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property string note: ""
    property bool chevron: false
    property bool solidIcon: icon === "play" || icon === "pause"
    property string value: ""
    property real valueLimit: 0
    property bool danger: false

    property bool selected: false
    implicitHeight: Math.max(Theme.buttonHeight, Math.max(words.implicitHeight, valueLabel.implicitHeight) + 2 * Theme.s8)
    Accessible.name: text
    Accessible.checked: selected

    Rectangle {
        anchors.fill: parent
        radius: root.ringRadius
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Row {
        width: parent.width - 2 * Theme.s8 - (root.chevron ? 24 : 0)
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Theme.s8
        spacing: Theme.s12
        Icon {
            name: root.icon
            solid: root.solidIcon
            size: 16
            color: root.danger ? Theme.danger : Theme.text2
            anchors.verticalCenter: parent.verticalCenter
        }
        Column {
            id: words
            width: parent.width - 16 - parent.spacing - (root.value !== "" ? valueLabel.width + parent.spacing : 0)
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.note ? 2 : 0
            Text {
                id: label
                width: parent.width
                wrapMode: Text.Wrap
                text: root.text
                color: root.danger ? Theme.danger : Theme.text
                font.pixelSize: Theme.sizeBodySmall
            }
            Text {
                width: parent.width
                visible: root.note !== ""
                text: root.note
                wrapMode: Text.Wrap
                color: Theme.text2
                font.pixelSize: Theme.sizeCaption
            }
        }
        Text {
            id: valueLabel
            width: root.valueLimit > 0 ? Math.min(implicitWidth, root.valueLimit) : implicitWidth
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            Reveal { shown: root.value !== "" }
            text: root.value
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Icon { anchors.right: parent.right; anchors.rightMargin: Theme.s8; anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; size: 16; color: Theme.text3; Reveal { shown: root.chevron && root.enabled } }
}
