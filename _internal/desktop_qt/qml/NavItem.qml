import QtQuick
import ABook

// Một mục của thanh bên. Mục đang mở = nền trung tính nhạt (do Sidebar vẽ, trượt giữa các mục) + chữ đậm màu thường;
// không nền hổ phách, không dấu tích (DESIGN.md mục 6, "Điều hướng").
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property bool current: false
    property string shortcut: ""
    readonly property real iconInset: 11     // tâm biểu tượng ở 28 = nửa dải thu gọn 56 (mục lệch lề 8)

    implicitHeight: Theme.buttonHeight
    tip: shortcut ? text + " (" + shortcut + ")" : ""

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.current ? 0 : (root.pressed ? 0.10 : (root.hovered ? 0.05 : 0))
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Icon {
        x: root.iconInset
        anchors.verticalCenter: parent.verticalCenter
        name: root.icon
        size: 18
        color: root.current ? Theme.text : Theme.text2
    }
    // Nhãn nằm trong khung cắt theo bề rộng mục: dải thu gọn không lộ nửa chữ, khi mở rộng chữ hé ra dần (không bị rút gọn "…")
    Item {
        x: root.iconInset + 18 + Theme.s12
        width: Math.max(0, root.width - x)
        height: parent.height
        clip: true
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.current ? Theme.text : Theme.text2
            font.pixelSize: Theme.sizeBodySmall
            font.weight: root.current ? Theme.weightMedium : Theme.weightRegular
        }
    }
}
