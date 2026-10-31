import QtQuick
import ABook

// Bản xuất đã xong, hiện ngay trong hộp (khối `finished` của ExportBook.tsx): dấu tích + tên việc đậm, chỗ file nằm (bẻ ở bất kỳ đâu - đường dẫn dài) và, nếu thiếu gì, lời lưu ý.
Column {
    id: root
    property string title: ""
    property string detail: ""
    property string note: ""
    topPadding: 8
    bottomPadding: 8
    spacing: 8

    Row {
        spacing: 8
        width: parent.width
        Icon { name: "circle-check"; size: 16; color: Theme.success; y: 2 }
        Text {
            objectName: "exportDoneTitle"
            width: parent.width - 24
            text: root.title
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightBold
        }
    }
    Text {
        objectName: "exportDoneDetail"
        width: parent.width
        text: root.detail
        color: Theme.text2
        wrapMode: Text.WrapAnywhere
        font.pixelSize: Theme.sizeBodySmall
    }
    Row {
        visible: root.note !== ""
        spacing: 8
        width: parent.width
        Icon { name: "triangle-alert"; size: 16; color: Theme.warning; y: 2 }
        Text { objectName: "exportDoneNote"; width: parent.width - 24; text: root.note; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
    }
}
