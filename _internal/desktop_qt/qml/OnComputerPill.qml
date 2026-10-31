import QtQuick
import ABook
import "StudioLogic.js" as Logic

// Thay cho một việc Studio từ xa không làm được và chỉ làm được ngay trên máy tính (OnComputerOnly của shared/OnComputerOnly.tsx): nói thẳng
// "Xoá dự án ở máy tính <tên máy>" thay vì ẩn nút im lặng hay để nút bấm ra lỗi 403. Chữ xuống dòng, không cắt.
Rectangle {
    id: root
    property string verb: "Làm"
    property string computer: "máy tính"
    implicitWidth: Math.min(maxWidth, icon.width + 6 + line.implicitWidth + 20)
    implicitHeight: Math.max(26, line.implicitHeight + 8)
    property real maxWidth: 480
    width: implicitWidth
    height: implicitHeight
    radius: height / 2
    color: Theme.sunken
    Icon { id: icon; x: 10; y: (root.height - 14) / 2; name: "monitor"; size: 14; color: Theme.text2 }
    Text {
        id: line
        objectName: "onComputerText"
        x: icon.x + icon.width + 6
        y: (root.height - height) / 2
        width: root.width - x - 10
        text: Logic.onComputerLine(root.verb, root.computer)
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
    }
}
