import QtQuick
import QtQuick.Controls.Basic as C
import ABook
C.TextArea {
    id: root
    property string label: ""
    Accessible.name: label
    color: Theme.text
    placeholderTextColor: Theme.text3
    selectionColor: Theme.accent
    selectedTextColor: Theme.accentInk
    font.pixelSize: Theme.sizeBodySmall
    wrapMode: TextEdit.Wrap
    selectByMouse: true
    activeFocusOnTab: true
    topPadding: 10
    bottomPadding: 10
    leftPadding: 12
    rightPadding: 12
    implicitHeight: Math.max(40, contentHeight + 20)
    background: Rectangle {
        color: Theme.bg
        radius: Theme.radiusControl
        border.width: root.activeFocus ? 2 : 1
        border.color: root.activeFocus ? Theme.focus : Theme.line
    }
    Keys.onPressed: event => {
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) {
            root.accepted(); event.accepted = true
        }
    }
    signal accepted()
}
