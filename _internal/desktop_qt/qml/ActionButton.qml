import QtQuick
import ABook

// Nút phụ của trang sách (listen/ActionButton.tsx): icon 20 trong khung cao 24 trên nhãn một chữ (12 px vừa), cao ít nhất 56, rộng ít nhất 64.
// Chữ --fg-2 (đang bật: --accent-text); rê chuột nền --hover, chữ --fg; tắt thì mờ 0,4 và vẫn giữ chỗ (hàng nút không nhảy).
// `label` là chữ hiện; tên cho trình đọc màn hình đặt qua `Accessible.name` khi cần nói đủ ("Tìm chữ trong sách").
Interactive {
    id: root
    property string icon: ""
    property string label: ""
    property bool active: false
    readonly property color ink: !enabled ? Theme.text2 : active ? Theme.accentText : hovered ? Theme.text : Theme.text2
    implicitWidth: Math.max(64, labelText.implicitWidth + 16)
    implicitHeight: Math.max(56, 6 + 24 + 4 + labelText.implicitHeight + 6)
    width: implicitWidth
    height: implicitHeight
    opacity: enabled ? 1 : 0.4
    activeFocusOnTab: enabled
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    Accessible.role: Accessible.Button
    Accessible.name: label

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.hover
        opacity: root.enabled && root.hovered ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Icon {
        x: (root.width - 20) / 2
        y: 6 + 2
        name: root.icon
        size: 20
        color: root.ink
    }
    Text {
        id: labelText
        y: 6 + 24 + 4
        width: root.width
        horizontalAlignment: Text.AlignHCenter
        text: root.label
        color: root.ink
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
        font.weight: Theme.weightMedium
    }
}
