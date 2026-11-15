import QtQuick
import ABook

// Ô chọn trong bảng nổi (tốc độ, hẹn giờ): chữ ngắn, ô đang chọn nền nhạt màu nhấn + chữ màu nhấn.
Interactive {
    id: root
    property string text: ""
    property bool selected: false
    property color normalFill: Theme.sunken
    property color selectedTextColor: Theme.accentText
    property int selectedTextWeight: Theme.weightMedium
    property real textScale: 1
    // Full-width is reserved for a single-column menu, never a filter segment.
    property string fullWidthReason: ""
    implicitHeight: 36
    implicitWidth: label.implicitWidth + 2 * Theme.s12
    // Ô chọn-một (DESIGN R1: choice): trợ năng và cây UI thấy đúng vai, như role="radio" của web.
    Accessible.role: Accessible.RadioButton
    Accessible.name: text
    Accessible.checked: selected

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: root.selected ? Theme.accentSoft : root.normalFill
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: Theme.text
            opacity: root.pressed ? 0.10 : (root.hovered ? 0.05 : 0)
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
    }
    Text {
        id: label
        anchors.centerIn: parent
        text: root.text
        color: !root.enabled ? Theme.text3 : root.selected ? root.selectedTextColor : Theme.accentText
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
        font.pixelSize: Theme.sizeBodySmall * root.textScale
        font.weight: root.selected ? root.selectedTextWeight : Theme.weightRegular
    }
}
