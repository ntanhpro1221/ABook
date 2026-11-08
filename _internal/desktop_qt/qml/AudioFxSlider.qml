import QtQuick
import QtQuick.Controls.Basic as C
import ABook

Column {
    id: root
    property string label
    property real value: 0
    property real from: -12
    property real to: 12
    property real step: 1
    property string suffix: " dB"
    signal picked(real value)
    spacing: 0
    Row {
        width: parent.width
        Text { width: parent.width - number.width; text: root.label; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        ClockLabel { id: number; text: slider.value + root.suffix; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
    }
    C.Slider {
        id: slider
        objectName: "audioFxRange"
        width: parent.width; height: 44
        from: root.from; to: root.to; stepSize: root.step; value: root.value
        snapMode: C.Slider.SnapAlways
        onMoved: root.picked(value)
        Accessible.name: root.label
        Accessible.description: value + root.suffix
        background: Rectangle {
            x: slider.leftPadding; y: (slider.height-height)/2
            width: slider.availableWidth; height: 4; radius: height/2; color: Theme.line
            Rectangle { width: slider.visualPosition*parent.width; height: 4; radius: height/2; color: Theme.accent }
        }
        handle: Rectangle {
            x: slider.leftPadding+slider.visualPosition*(slider.availableWidth-width); y: (slider.height-height)/2
            width: 14; height: 14; radius: width/2; color: Theme.accent
            border.width: slider.activeFocus?2:0; border.color: Theme.focus
            scale: slider.pressed?1.15:1
            Behavior on scale { NumberAnimation { duration: Theme.motionFast } }
        }
    }
}
