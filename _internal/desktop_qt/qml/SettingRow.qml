import QtQuick
import ABook
Item {
    id: root
    property string label: ""
    property string hint: ""
    property bool line: true
    default property alias controls: control.data
    readonly property real controlWidth: Math.min(width * 0.48, control.childrenRect.width)
    implicitHeight: Math.max(words.height, control.childrenRect.height) + 24
    Column {
        id: words
        width: root.width - (root.controlWidth > 0 ? root.controlWidth + 16 : 0)
        y: 12
        spacing: 2
        FormLabel { width: parent.width; text: root.label; font.pixelSize: 15; font.weight: Theme.weightMedium }
        FormLabel { width: parent.width; text: root.hint; visible: text !== ""; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    }
    Item { id: control; x: root.width - root.controlWidth; y: (root.height - childrenRect.height) / 2; width: root.controlWidth; height: childrenRect.height }
    Rectangle { visible: root.line; width: parent.width; height: 1; anchors.bottom: parent.bottom; color: Theme.line }
}
