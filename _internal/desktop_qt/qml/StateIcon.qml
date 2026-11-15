import QtQuick
import ABook

// State icons crossfade in one fixed slot; values and progress do not restart the transition.
Item {
    id: root
    property string name: ""
    property int size: 20
    property color color: Theme.text
    property bool solid: name === "play" || name === "pause" || name === "square"
    property string displayed: ""
    property string previous: ""
    property real blend: 1
    implicitWidth: size
    implicitHeight: size
    width: size
    height: size
    onNameChanged: {
        if (name === displayed) return
        previous = displayed; displayed = name
        if (previous !== "") { transition.restart() }
    }
    NumberAnimation { id: transition; target: root; property: "blend"; from: 0; to: 1; duration: Theme.reduceMotion ? Theme.motionReduced : 180; easing.type: Easing.OutCubic }
    Icon { anchors.centerIn: parent; name: root.previous; size: root.size; color: root.color; solid: name === "play" || name === "pause" || name === "square"; opacity: 1 - root.blend; scale: Theme.reduceMotion ? 1 : 1 - .2 * root.blend }
    Icon { anchors.centerIn: parent; name: root.displayed; size: root.size; color: root.color; solid: root.solid; opacity: root.blend; scale: Theme.reduceMotion ? 1 : .8 + .2 * root.blend }
}
