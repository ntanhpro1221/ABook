import QtQuick
import ABook

// Một hàng hành động trong bảng nổi (kiểu menu của Windows): biểu tượng + chữ thường, cả hàng là vùng bấm, rê chuột thì nền nhạt.
// Footer actions use accent ink; destructive actions use danger ink.
Interactive {
    id: root
    property string text: ""
    property string icon: ""
    property string note: ""
    property bool chevron: false
    property bool solidIcon: icon === "play" || icon === "pause"
    property string value: ""
    property real valueLimit: 0
    property bool danger: false
    property bool action: false

    property bool selected: false
    implicitHeight: Math.max(action ? 48 : Theme.buttonHeight, Math.max(words.implicitHeight, valueLabel.implicitHeight) + 2 * Theme.s8)
    Accessible.name: text
    Accessible.role: Accessible.MenuItem
    Accessible.checked: selected

    Rectangle {
        anchors.fill: parent
        radius: root.ringRadius
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.06 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Row {
        width: parent.width - 2 * Theme.s8 - (root.chevron ? 24 : 0)
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Theme.s8
        spacing: Theme.s12
        Icon {
            name: root.icon !== "" ? root.icon : root.selected ? "circle-check" : "chevron-right"
            solid: root.solidIcon
            size: 16
            color: root.danger ? Theme.danger : root.action ? Theme.accentText : Theme.text2
            y: words.y + label.firstLineHeight / 2 - height / 2
            Icon {
                anchors.centerIn: parent
                name: "check"; size: 12; color: Theme.accentText
                opacity: root.icon === "circle" && root.selected ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionFast } }
            }
        }
        Column {
            id: words
            width: parent.width - 16 - parent.spacing - (root.value !== "" ? valueLabel.width + parent.spacing : 0)
            anchors.verticalCenter: parent.verticalCenter
            spacing: root.note ? 2 : 0
            OneLineFit {
                id: label
                objectName: "menuRowName"
                room: parent.width
                text: root.text
                color: root.danger ? Theme.danger : root.action ? Theme.accentText : Theme.text
                baseSize: Theme.sizeBodySmall
                font.weight: root.action ? Theme.weightMedium : Theme.weightRegular
            }
            Text {
                width: parent.width
                Reveal { shown: root.note !== "" }
                text: root.note
                wrapMode: Text.Wrap
                color: Theme.text2
                font.pixelSize: Theme.sizeCaption
            }
        }
        Text {
            id: valueLabel
            width: root.valueLimit > 0 ? Math.min(implicitWidth, root.valueLimit) : implicitWidth
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            Reveal { shown: root.value !== "" }
            text: root.value
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
            anchors.verticalCenter: parent.verticalCenter
        }
    }
    Icon { anchors.right: parent.right; anchors.rightMargin: Theme.s8; anchors.verticalCenter: parent.verticalCenter; name: "chevron-right"; size: 16; color: Theme.text3; Reveal { shown: root.chevron && root.enabled } }
}
