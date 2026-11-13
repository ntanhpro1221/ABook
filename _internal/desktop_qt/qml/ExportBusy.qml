import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// Lúc đang xuất (khối `busy` của ExportBook.tsx): thanh tiến độ (chưa biết mẫu số thì một đoạn chạy qua lại), dòng việc đang làm đậm, rồi lời "N chương; đóng hộp vẫn xuất nền
// và báo khi xong". Chữ đổi theo từng nhịp hỏi; trình đọc màn hình đọc mô tả của thanh, không đọc từng giây.
Column {
    id: root
    property real fraction: -1              // < 0: chưa có mẫu số
    property string title: ""
    property string note: ""
    topPadding: 8
    bottomPadding: 8
    Accessible.role: Accessible.StaticText
    Accessible.name: title

    Item {
        width: parent.width
        height: 8
        StudioBar {
            objectName: "exportBar"
            Reveal { shown: root.fraction >= 0 }
            width: parent.width
            size: "md"
            value: root.fraction
            label: root.title
        }
        StudioBar {
            objectName: "exportIndeterminate"
            Reveal { shown: root.fraction < 0 }
            width: parent.width
            size: "md"
            indeterminate: true
            label: root.title
        }
    }
    Text {
        objectName: "exportBusyTitle"
        width: parent.width
        topPadding: 12
        text: TextWrap.keepDots(root.title)
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
        font.weight: Theme.weightBold
    }
    Text {
        objectName: "exportBusyNote"
        width: parent.width
        topPadding: 4
        text: root.note
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
    }
}
