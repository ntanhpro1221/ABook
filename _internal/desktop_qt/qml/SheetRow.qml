import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// One label, value and control rhythm for player sheets.
Interactive {
    id: root
    property string text: ""
    property string value: ""
    property string hint: ""
    property bool toggle: false
    property bool checked: false
    signal toggled(bool value)
    signal activated()
    width: parent.width
    implicitHeight: Math.max(Theme.s48, labels.height + Theme.s8)
    Accessible.name: text
    onClicked: { if (toggle) toggled(!checked); else activated() }
    Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.text; opacity: root.pressed ? .1 : root.hovered ? .06 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
    Row {
        width: parent.width; anchors.verticalCenter: parent.verticalCenter; spacing: Theme.s12
        Column {
            id: labels; anchors.verticalCenter: parent.verticalCenter
            width: parent.width - control.width - parent.spacing - (root.value ? valueLabel.width + parent.spacing : 0)
            Text { width: parent.width; text: root.text; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; wrapMode: Text.Wrap }
            Text { id: hintLabel; width: parent.width; text: TextWrap.pretty(root.hint); color: Theme.text2; font.pixelSize: Theme.sizeCaption; wrapMode: Text.Wrap
                Reveal { shown: hintLabel.text !== "" }
            }
        }
        Text { id: valueLabel; width: Math.min(implicitWidth, root.width * .5); text: root.value; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall; horizontalAlignment: Text.AlignRight; wrapMode: Text.Wrap; anchors.verticalCenter: parent.verticalCenter
            Reveal { shown: root.value !== "" }
        }
        Item {
            id: control; width: root.toggle ? toggleControl.width : 16; height: Theme.s48
            Switch { id: toggleControl; anchors.verticalCenter: parent.verticalCenter; label: root.text; checked: root.checked; onToggled: value => root.toggled(value)
                Reveal { shown: root.toggle }
            }
            Icon { name: "chevron-right"; size: 16; color: Theme.text2; anchors.centerIn: parent
                Reveal { shown: !root.toggle }
            }
        }
    }
}
