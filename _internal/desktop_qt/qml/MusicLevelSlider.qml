import QtQuick
import QtQuick.Controls.Basic as C
import ABook

// Same control and track as VolumeControl. Commit when the pointer is released;
// keyboard steps commit immediately. Track labels follow the pointer locally.
Column {
    id: root
    property real value: Music.levelDefault
    signal picked(real value)
    spacing: Theme.s4
    width: 260
    Row {
        width: parent.width
        spacing: Theme.s8
        Text {
            width: parent.width - number.width - Theme.s8
            text: Music.levelLabel(slider.value)
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        ClockLabel {
            id: number
            text: Music.levelNumber(slider.value)
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
        }
    }
    C.Slider {
        id: slider
        objectName: "musicLevelSlider"
        width: parent.width
        height: 44
        from: Music.levelMin
        to: Music.levelMax
        stepSize: Music.levelStep
        value: root.value
        snapMode: C.Slider.SnapAlways
        onMoved: if (!pressed) root.picked(value)
        onPressedChanged: if (!pressed) root.picked(value)
        Accessible.name: "Mức nhạc nền"
        Accessible.description: Music.levelLabel(value) + ", " + Music.levelNumber(value)
        background: Rectangle {
            x: slider.leftPadding
            y: (slider.height - height) / 2
            width: slider.availableWidth
            height: 4
            radius: height / 2
            color: Theme.line
            Rectangle { width: slider.visualPosition * parent.width; height: parent.height; radius: height / 2; color: Theme.accent }
            Rectangle {
                x: (Music.levelDefault - slider.from) / (slider.to - slider.from) * (parent.width - 14) + 7 - width / 2
                anchors.verticalCenter: parent.verticalCenter
                width: 2; height: 12; radius: width / 2; color: Theme.text2
            }
        }
        handle: Rectangle {
            x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
            y: (slider.height - height) / 2
            width: 14; height: 14; radius: width / 2; color: Theme.accent
            border.width: slider.activeFocus ? 2 : 0; border.color: Theme.focus
            scale: slider.pressed ? 1.15 : 1
            Behavior on scale { NumberAnimation { duration: Theme.motionFast } }
        }
    }
    Button {
        objectName: "musicLevelReset"
        text: "Về mặc định"
        kind: "ghost"
        size: "sm"
        opacity: slider.value !== Music.levelDefault ? 1 : 0
        enabled: opacity > 0 && root.enabled
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        onActivated: { slider.value = Music.levelDefault; root.picked(Music.levelDefault) }
    }
}
