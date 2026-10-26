import QtQuick
import ABook

// Một phím trong danh sách phím tắt (Kbd của shared/ui.tsx): ô cao 20, rộng tối thiểu 20, viền --line, nền --panel, chữ 11 / 500 mực phụ, đệm ngang 6.
Rectangle {
    id: root
    property string text: ""
    property bool struck: false         // gạch ngang qua chữ (phím tắt đã tắt: line-through của dd)
    implicitWidth: Math.max(20, word.implicitWidth + 12)
    implicitHeight: 20
    width: implicitWidth
    height: implicitHeight
    radius: Theme.radiusControl
    color: Theme.panel
    border.width: 1
    border.color: Theme.line
    Text {
        id: word
        anchors.centerIn: parent
        text: root.text
        color: Theme.text2
        font.pixelSize: 11
        font.weight: Theme.weightMedium
        Rectangle { visible: root.struck; anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 1; color: Theme.text2 }
    }
}
