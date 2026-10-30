import QtQuick
import ABook

// Nút phụ của màn Đang nghe (Tốc độ, Hẹn giờ, Chương, Nhạc nền): biểu tượng + một đến hai chữ, nền chìm. Mở một bảng nổi neo vào nó.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property bool active: false          // đang bật (đang hẹn giờ, đang có nhạc): chữ màu nhấn
    property bool struck: false          // gạch chéo trên biểu tượng (nhạc nền tắt - lucide không có biểu tượng "nhạc tắt")
    property var reserve: []             // chữ mẫu rộng nhất khi chữ là giá trị tự đổi (đếm ngược hẹn giờ): nút không co giãn mỗi nhịp
    implicitHeight: Theme.buttonHeight
    implicitWidth: Math.max(Theme.buttonHeight, content.implicitWidth + 2 * Theme.s12)

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: root.active ? Theme.accentSoft : Theme.sunken
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Theme.text
            opacity: root.pressed ? 0.10 : (root.hovered ? 0.05 : 0)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
    }
    Row {
        id: content
        anchors.centerIn: parent
        spacing: Theme.s8
        Icon {
            id: glyph
            visible: root.icon !== ""
            name: root.icon
            size: 16
            color: root.active ? Theme.accentText : Theme.text2
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                anchors.centerIn: parent
                width: 20
                height: 2
                radius: height / 2
                rotation: 45
                color: glyph.color
                opacity: root.struck ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            }
        }
        ClockLabel {
            visible: root.text !== ""
            text: root.text
            reserve: root.reserve
            color: root.active ? Theme.accentText : Theme.text
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
            anchors.verticalCenter: parent.verticalCenter
        }
    }
}
