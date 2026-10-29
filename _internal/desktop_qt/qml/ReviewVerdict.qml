import QtQuick
import ABook

// Một trong hai phán quyết của hàng "Cần nghe lại" (DecisionButton ghost): "Ổn" / "Cần thu lại". Có biểu tượng, cao bằng điều khiển; đã chọn thì mang sắc trạng thái
// (xanh cho Ổn, đỏ cho Cần thu lại), chưa chọn là chữ nhấn.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property bool on: false
    property string tone: "ok"                  // "ok" | "redo"
    readonly property color ink: on ? (tone === "ok" ? Theme.success : Theme.danger) : Theme.accentText
    Accessible.role: Accessible.CheckBox
    Accessible.name: text
    Accessible.checked: on
    implicitHeight: Theme.buttonHeight
    implicitWidth: row.width + 28
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: root.on ? (root.tone === "ok" ? Qt.alpha(Theme.success, 0.14) : Theme.dangerSoft) : Theme.hover
        opacity: root.on || root.hovered || root.pressed ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
    }
    Row {
        id: row
        anchors.centerIn: parent
        spacing: 6
        Icon { anchors.verticalCenter: parent.verticalCenter; name: root.icon; size: 16; color: root.ink }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.text
            color: root.ink
            font.pixelSize: Theme.sizeBodySmall
            font.weight: Theme.weightMedium
        }
    }
}
