import QtQuick
import ABook

// Dòng "Đã ghi …" trên thẻ đã quyết (dấu ✓ xanh + câu nói áp dụng khi nào): khép / mở tại chỗ, chữ cuối ở lại trong lúc khép.
Collapse {
    id: root
    property string text: ""
    property string shown: ""
    open: text !== ""
    onTextChanged: if (text !== "") shown = text
    Item {
        width: root.width
        height: line.height + 8
        Icon { x: 0; y: 2; name: "check"; size: 14; color: Theme.success }
        Text {
            id: line
            objectName: "workRequested"
            x: 20
            width: parent.width - 20
            text: root.shown
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
}
