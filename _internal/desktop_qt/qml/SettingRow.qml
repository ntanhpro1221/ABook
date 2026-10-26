import QtQuick
import ABook

// Nhãn (15/500) + lời nhắc (12, mực phụ) bên trái, điều khiển bên phải canh giữa hàng (SettingsRow của shared/SettingsNav.tsx: lưới
// minmax(0,1fr) | auto, py-3, cách 16). Điều khiển rộng (hàng lựa chọn) co về tối đa 60 % hàng và tự xuống dòng; nhãn không bao giờ cắt.
// Vạch chia với mục trước như SettingsItem.
Item {
    id: root
    property string label: ""
    property string hint: ""
    property color hintColor: Theme.text2
    default property alias controls: control.data
    readonly property real controlWidth: {
        let w = 0
        for (let i = 0; i < control.children.length; ++i) {
            const c = control.children[i]
            if (c.visible) w = Math.max(w, c.implicitWidth > 0 ? c.implicitWidth : c.width)
        }
        return Math.min(w, Math.max(0, root.width * 0.6))
    }
    readonly property bool firstShown: {
        const kids = parent ? parent.children : []
        for (let i = 0; i < kids.length; ++i)
            if (kids[i].visible && kids[i].height > 0) return kids[i] === root
        return true
    }
    Accessible.name: label
    implicitHeight: Math.max(words.implicitHeight, control.childrenRect.height) + 24
    Rectangle { width: parent.width; height: 1; color: Theme.line; visible: !root.firstShown }
    Column {
        id: words
        width: root.width - (root.controlWidth > 0 ? root.controlWidth + Theme.s16 : 0)
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text { width: parent.width; text: root.label; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: 15; font.weight: Theme.weightMedium }
        Text { width: parent.width; text: root.hint; visible: text !== ""; color: root.hintColor; wrapMode: Text.WrapAnywhere; font.pixelSize: Theme.sizeCaption; lineHeight: 1.25 }
    }
    Item {
        id: control
        x: root.width - root.controlWidth
        width: root.controlWidth
        height: childrenRect.height
        anchors.verticalCenter: parent.verticalCenter
    }
}
