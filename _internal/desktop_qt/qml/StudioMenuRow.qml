import QtQuick
import ABook

// Một dòng của menu "…" của Studio (MenuItem của ProjectScreen.tsx): biểu tượng + chữ (xuống dòng khi dài, không cắt), lời phụ nhỏ bên dưới
// ("chạy phần này trước"), mờ khi chưa dùng được, đỏ khi là việc nguy hiểm. Như MenuRow nhưng cao theo chữ.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property string hint: ""
    property bool danger: false
    readonly property color ink: danger ? Theme.danger : Theme.text
    implicitHeight: Math.max(Theme.buttonHeight, label.height + 2 * Theme.s8 + (hintText.visible ? hintText.height + 2 : 0))
    opacity: enabled ? 1 : 0.5
    Accessible.role: Accessible.MenuItem
    Accessible.name: text

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: !root.enabled ? 0 : root.pressed ? 0.10 : (root.hovered || root.activeFocus ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Icon { x: Theme.s8; y: Theme.s8 + (Theme.sizeBodySmall * 1.3 - 16) / 2; name: root.icon; size: 16; color: root.danger ? Theme.danger : Theme.text2 }
    Column {
        x: Theme.s8 + 16 + Theme.s12
        y: Theme.s8
        width: root.width - x - Theme.s8
        spacing: 2
        Text {
            id: label
            width: parent.width
            text: root.text
            color: root.ink
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Text {
            id: hintText
            visible: root.hint !== ""
            width: parent.width
            text: root.hint
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
}
