import QtQuick
import ABook

// Ô chọn 16 x 16 để xem (input checkbox accent của VieneuModuleCard): trống thì viền --control-line, đã chọn thì nền --accent với dấu tích
// mực-trên-nhấn. Không bo (luật bo của app: 0 hoặc tròn). Đổi trạng thái mờ chéo trong motionFast. Việc bấm thuộc hàng chứa nó (như <label>).
Item {
    id: root
    property bool checked: false
    implicitWidth: 16
    implicitHeight: 16
    Rectangle {
        anchors.fill: parent
        radius: 0
        color: root.checked ? Theme.accent : "transparent"
        border.width: root.checked ? 0 : 1
        border.color: Theme.controlLine
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
    }
    Icon {
        anchors.centerIn: parent
        name: "check"
        size: 12
        color: Theme.accentInk
        opacity: root.checked ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
}
