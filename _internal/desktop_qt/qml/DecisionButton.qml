import QtQuick
import ABook

// Nút lựa chọn của thẻ việc (DecisionButton + variant ghost của shared/ui.tsx): nút chữ nhỏ; lựa chọn đã ghi (hay máy đề xuất) có gạch chân hổ phách 2 px để nút thực hiện
// vẫn là điểm nhấn duy nhất. `choice`: phím 1-9 của hộp việc bấm được nút này (data-choice).
Button {
    id: root
    property bool marked: false
    readonly property bool choice: true
    kind: "ghost"
    size: "sm"
    Rectangle {
        anchors.bottom: parent.bottom
        width: parent.width
        height: 2
        color: Theme.accent
        opacity: root.marked ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }
}
