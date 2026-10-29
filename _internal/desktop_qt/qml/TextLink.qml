import QtQuick
import ABook

// Chữ bấm được trơn (nút chữ gạch chân của trang): "Dán đường dẫn", "Bỏ nối tiếp", "Dùng lại <giọng>", "Bỏ lọc". Chữ xuống dòng khi hẹp, nền bấm cao tối thiểu 32.
Interactive {
    id: root
    property string text: ""
    property bool accent: false          // chữ màu nhấn (đường dẫn tới việc) thay vì mực phụ
    property bool small: false
    implicitWidth: label.implicitWidth
    implicitHeight: Math.max(Theme.hit, label.height + 8)
    width: Math.min(implicitWidth, parent ? parent.width : implicitWidth)
    Accessible.role: Accessible.Button
    Accessible.name: text
    Text {
        id: label
        width: parent.width
        anchors.verticalCenter: parent.verticalCenter
        text: root.text
        color: root.accent ? Theme.accentText : root.hovered ? Theme.text : Theme.text2
        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
        font.pixelSize: root.small ? 13 : Theme.sizeBodySmall
        font.weight: root.accent ? Theme.weightMedium : Theme.weightRegular
        font.underline: true
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
    }
}
