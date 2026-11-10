import QtQuick
import ABook

// Flat track, like the app's progress bars. Emotion scores have no input border.
Rectangle {
    id: root
    property real score: 0
    property color ink: Theme.accent
    property string label: ""
    implicitHeight: 6
    radius: height / 2
    color: Theme.line
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Accessible.description: Math.round(score * 100) + " %"
    Rectangle { width: parent.width * Math.max(0, Math.min(1, root.score)); height: parent.height; radius: height / 2; color: root.ink }
}
