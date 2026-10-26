import QtQuick
import ABook

// Only mask the edge that still has content beyond it. No offscreen texture.
Item {
    id: root
    required property Flickable target
    Rectangle {
        objectName: "scrollFadeTop"
        width: parent.width
        height: Theme.s16
        visible: !root.target.atYBeginning
        gradient: Gradient {
            GradientStop { position: 0; color: Theme.bg }
            GradientStop { position: 1; color: Qt.alpha(Theme.bg, 0) }
        }
    }
    Rectangle {
        objectName: "scrollFadeBottom"
        anchors.bottom: parent.bottom
        width: parent.width
        height: Theme.s16
        visible: !root.target.atYEnd
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(Theme.bg, 0) }
            GradientStop { position: 1; color: Theme.bg }
        }
    }
}
