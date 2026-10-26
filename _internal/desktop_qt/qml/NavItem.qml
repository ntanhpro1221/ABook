import QtQuick
import ABook

// Một mục của thanh bên. Mục đang mở = nền trung tính nhạt (do Sidebar vẽ, trượt giữa các mục) + chữ đậm màu thường;
// không nền hổ phách, không dấu tích (DESIGN.md mục 6, "Điều hướng").
Interactive {
    id: root
    property string text: ""
    property string glyph: ""
    property bool current: false
    property string shortcut: ""

    implicitHeight: Theme.buttonHeight
    tip: shortcut ? text + "  (" + shortcut + ")" : ""

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.current ? 0 : (root.pressed ? 0.10 : (root.hovered ? 0.05 : 0))
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Row {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Theme.s12
        spacing: Theme.s12
        Icon {
            glyph: root.glyph
            size: 18
            color: root.current ? Theme.text : Theme.text2
            anchors.verticalCenter: parent.verticalCenter
        }
        Text {
            text: root.text
            color: root.current ? Theme.text : Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            font.weight: root.current ? Theme.weightMedium : Theme.weightRegular
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
