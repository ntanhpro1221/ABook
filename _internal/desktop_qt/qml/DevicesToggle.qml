import QtQuick
import ABook

// Hàng "tên + dòng mô tả bên trái, công tắc bên phải" của Cài đặt › Thiết bị (flex items-center justify-between gap-6 của PhoneSync.tsx):
// bấm vào chữ cũng bật tắt như <label htmlFor>. Chữ không bao giờ cắt, xuống dòng. `hintRich`: mô tả là HTML (địa chỉ in đậm vừa).
Item {
    id: root
    property string label: ""
    property string hint: ""
    property bool hintRich: false
    property color hintColor: Theme.text2
    property real labelSize: 15
    property real hintSize: Theme.sizeCaption
    property bool checked: false
    property string switchLabel: label
    property alias switchItem: toggle
    signal toggled(bool checked)
    implicitHeight: Math.max(words.implicitHeight, toggle.height)
    height: implicitHeight

    Column {
        id: words
        width: root.width - toggle.width - 24
        anchors.verticalCenter: parent.verticalCenter
        spacing: 2
        Text {
            width: parent.width
            text: root.label
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: root.labelSize
            font.weight: Theme.weightMedium
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: root.hint
            textFormat: root.hintRich ? Text.RichText : Text.PlainText
            color: root.hintColor
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: root.hintSize
            lineHeight: 1.3
            Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        }
        TapHandler { enabled: toggle.enabled; onTapped: root.toggled(!root.checked) }
        HoverHandler { cursorShape: Qt.PointingHandCursor }
    }
    Switch {
        id: toggle
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        label: root.switchLabel
        checked: root.checked
        onToggled: value => root.toggled(value)
    }
}
