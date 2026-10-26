import QtQuick
import ABook
Column {
    id: root
    property string title: ""
    property bool fold: false
    property bool expanded: !fold
    default property alias rows: body.data
    spacing: 8
    topPadding: 24
    Interactive {
        visible: root.title !== ""
        width: parent.width
        height: Math.max(32, heading.implicitHeight + 8)
        activeFocusOnTab: root.fold
        enabled: root.fold
        Accessible.name: root.title
        onClicked: root.expanded = !root.expanded
        FormLabel { id: heading; width: parent.width - 28; anchors.verticalCenter: parent.verticalCenter; text: root.title; font.weight: Theme.weightMedium; font.pixelSize: Theme.sizeSection }
        Icon { visible: root.fold; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; name: "chevron-down"; rotation: root.expanded ? 180 : 0; color: Theme.text2; size: 18; Behavior on rotation { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } } }
    }
    Item {
        width: parent.width
        height: body.implicitHeight * reveal
        property real reveal: root.expanded ? 1 : 0
        clip: true
        Behavior on reveal { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        Column { id: body; width: parent.width; visible: parent.reveal > 0; enabled: root.expanded; y: -8 * (1 - parent.reveal); opacity: parent.reveal }
    }
}
