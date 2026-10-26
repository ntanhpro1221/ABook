import QtQuick
import ABook

// Một lựa chọn tích được kèm lời nhắc (nhãn <label> của FootnoteChoices / ô "Tách theo…" / gợi ý bỏ dòng ở bản web): ô tích 16 px bên trái, nhãn 14/500 và
// lời nhắc 12 mực phụ bên phải. Bấm cả hàng là tích. Chữ không bao giờ bị cắt: nhãn và lời nhắc xuống dòng, bẻ cả chuỗi liền.
Item {
    id: root
    property bool checked: false
    property string label: ""
    property string help: ""
    property bool inView: true
    signal toggled(bool checked)
    implicitHeight: Math.max(40, words.height + 16)
    opacity: enabled ? 1 : 0.5
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }

    ImportBox {
        x: 0
        y: 11
        checked: root.checked
        label: root.label
        enabled: root.enabled
        inView: root.inView
        onToggled: value => root.toggled(value)
    }
    Column {
        id: words
        x: 28
        y: 8
        width: root.width - x
        Text {
            width: parent.width
            text: root.label
            color: Theme.text
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
            textFormat: Text.PlainText
        }
        Text {
            width: parent.width
            visible: text !== ""
            text: root.help
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
            textFormat: Text.PlainText
        }
    }
    TapHandler { enabled: root.enabled; onTapped: root.toggled(!root.checked) }
}
