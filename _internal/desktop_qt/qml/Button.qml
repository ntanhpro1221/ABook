import QtQuick
import ABook

// Hai kiểu nút theo DESIGN.md mục 6: chính (nền hổ phách, cao 40 trên máy tính, chữ <= 3 từ) và chữ (màu --accent-text).
// Mỗi màn chỉ một nút chính.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property string kind: "primary"     // "primary" | "text"
    readonly property bool primary: kind === "primary"

    implicitHeight: Theme.buttonHeight
    implicitWidth: label.implicitWidth + (icon ? Theme.s8 + 16 : 0) + (primary ? 2 * Theme.s24 : 2 * Theme.s12)
    opacity: enabled ? 1 : 0.45

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: root.primary ? Theme.accent : "transparent"
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: root.primary ? "#000000" : Theme.accentText
            opacity: root.pressed ? (root.primary ? Theme.pressShade : 0.14) : (root.hovered ? (root.primary ? 0.04 : 0.08) : 0)
            Behavior on opacity { NumberAnimation { duration: root.pressed ? Theme.motionFastOut : Theme.motionFast } }
        }
    }
    Row {
        anchors.centerIn: parent
        spacing: Theme.s8
        Icon {
            visible: root.icon !== ""
            name: root.icon
            size: 16
            color: root.primary ? Theme.accentInk : Theme.accentText
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            id: label
            text: root.text
            color: root.primary ? Theme.accentInk : Theme.accentText
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
