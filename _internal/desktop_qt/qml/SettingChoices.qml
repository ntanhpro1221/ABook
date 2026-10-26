import QtQuick
import ABook
Column {
    id: root
    property string label: ""
    property string hint: ""
    property var options: []
    property var value: ""
    signal picked(var value)
    spacing: 8
    topPadding: 12
    bottomPadding: 12
    FormLabel { width: parent.width; text: root.label; font.pixelSize: 15; font.weight: Theme.weightMedium }
    FormLabel { width: parent.width; text: root.hint; visible: text !== ""; font.pixelSize: Theme.sizeCaption; color: Theme.text2 }
    Flow {
        width: parent.width
        spacing: 8
        Repeater {
            model: root.options
            Interactive {
                required property var modelData
                readonly property bool selected: String(root.value) === String(modelData.value)
                width: Math.min(parent.width, choice.implicitWidth + 32)
                height: Math.max(36, choice.height + 16)
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.label
                Accessible.checked: selected
                onClicked: root.picked(modelData.value)
                Keys.onRightPressed: nextItemInFocusChain().forceActiveFocus(Qt.TabFocusReason)
                Keys.onLeftPressed: nextItemInFocusChain(false).forceActiveFocus(Qt.BacktabFocusReason)
                Rectangle { anchors.fill: parent; color: selected ? Theme.accentSoft : (parent.hovered ? Theme.sunken : "transparent"); radius: Theme.radiusControl }
                FormLabel { id: choice; width: Math.min(implicitWidth, parent.width - 32); anchors.centerIn: parent; text: modelData.label; color: parent.selected ? Theme.accentText : Theme.text2 }
            }
        }
    }
    Rectangle { width: parent.width; height: 1; color: Theme.line }
}
