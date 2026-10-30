import QtQuick
import ABook

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
            visible: root.fraction >= 0
            width: parent.width
            size: "md"
            value: root.fraction
            label: root.title
        }
        Rectangle {
            id: track
            objectName: "exportIndeterminate"
            visible: root.fraction < 0
            width: parent.width
            height: 8
            radius: height / 2
            color: Theme.line
            clip: true
            Rectangle {
                id: runner
                width: parent.width * 0.3
                height: parent.height
                radius: height / 2
                color: Theme.accent
                x: parent.width * 0.35
                SequentialAnimation on x {
                    running: track.visible && Nav.uiVisible && !Theme.reduceMotion
                    loops: Animation.Infinite
                    NumberAnimation { from: -runner.width; to: track.width; duration: 1400; easing.type: Easing.InOutSine }
                }
            }
        }
    }
    Text {
        objectName: "exportBusyTitle"
        width: parent.width
        topPadding: 12
        text: root.title
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
