import QtQuick
import ABook

// Hàng công tắc của trình tạo sách (<label> flex gap-3 py-3 của bản web): công tắc bên trái, tên (14/500) và lời nhắc (13, mực phụ) bên phải. Lời nhắc đổi theo lựa chọn
// thì chữ mới thay chữ cũ ngay tại chỗ; chữ không bao giờ bị cắt.
Item {
    id: root
    property string name: ""
    property string hint: ""
    property bool checked: false
    property int pad: 12
    signal toggled(bool checked)
    implicitHeight: 2 * pad + Math.max(toggle.height, words.height)
    height: implicitHeight
    opacity: enabled ? 1 : 0.6

    Switch {
        id: toggle
        y: root.pad
        label: root.name
        checked: root.checked
        enabled: root.enabled
        onToggled: value => root.toggled(value)
    }
    Column {
        id: words
        TapHandler { enabled: root.enabled; onTapped: toggle.clicked() }
        x: toggle.width + 12
        y: root.pad
        width: root.width - x
        Text {
            width: parent.width
            text: root.name
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
        }
        Text {
            objectName: "switchHint"
            width: parent.width
            topPadding: 2
            text: root.hint
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: 13
            lineHeight: 1.45
        }
    }
}
