import QtQuick
import ABook

// Choice marks stay visible and cross-fade at the same position.
Item {
    id: root
    property bool selected: false
    property bool circled: false
    property int size: 20
    implicitWidth: size; implicitHeight: size
    Icon {
        anchors.centerIn: parent; name: "circle"; size: root.size; color: Theme.text3
        opacity: root.selected ? 0 : 1
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionFast } }
    }
    Icon {
        anchors.centerIn: parent; name: root.circled ? "circle-check" : "check"; size: root.size; color: Theme.accentText
        opacity: root.selected ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionFast } }
    }
}
