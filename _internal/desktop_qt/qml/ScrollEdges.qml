import QtQuick
import ABook

// Only mask the edge that still has content beyond it. No offscreen texture.
Item {
    id: root
    required property Flickable target
    property color color: Theme.bg      // nền dưới khung cuộn (hộp thoại: Theme.panel)
    Rectangle {
        objectName: "scrollFadeTop"
        width: parent.width
        height: Theme.s16
        visible: !root.target.atYBeginning
        gradient: Gradient {
            GradientStop { position: 0; color: root.color }
            GradientStop { position: 1; color: Qt.alpha(root.color, 0) }
        }
    }
    Rectangle {
        objectName: "scrollFadeBottom"
        anchors.bottom: parent.bottom
        width: parent.width
        height: Theme.s16
        visible: !root.target.atYEnd
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.alpha(root.color, 0) }
            GradientStop { position: 1; color: root.color }
        }
    }
}
