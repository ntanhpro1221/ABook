import QtQuick
import ABook

// Ô tích 16 px của hộp Thêm sách (input checkbox + accent-color của bản web, bộ nút của Qt không có sẵn). Nền hổ phách khi tích, dấu ✓ mực-trên-nhấn;
// chưa tích: viền điều khiển. Bo nhỏ theo bước 4 của lưới. Vùng bấm 20 px; tích / bỏ tích đổi màu trong motionFast.
Interactive {
    id: root
    property bool checked: false
    property string label: ""
    property bool inView: true            // ô nằm trong khung cuộn mà đã trôi ra ngoài thì thôi vẽ dấu ✓ (Shape không theo khung cắt của bộ vẽ phần mềm)
    Accessible.role: Accessible.CheckBox
    Accessible.name: label
    Accessible.checked: checked
    signal toggled(bool checked)
    implicitWidth: 20
    implicitHeight: 20
    ringMargin: 0
    ringRadius: Theme.s4 + 2
    opacity: enabled ? 1 : 0.5
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    onClicked: if (enabled) root.toggled(!root.checked)

    Rectangle {
        anchors.centerIn: parent
        width: 16
        height: 16
        radius: Theme.s4
        color: root.checked ? Theme.accent : "transparent"
        border.width: root.checked ? 0 : 1
        border.color: Theme.controlLine
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        Icon {
            anchors.centerIn: parent
            name: "check"
            size: 12
            color: Theme.accentInk
            visible: root.inView
            opacity: root.checked ? 1 : 0
            scale: root.checked || Theme.reduceMotion ? 1 : 0.6
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Behavior on scale { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        }
    }
}
