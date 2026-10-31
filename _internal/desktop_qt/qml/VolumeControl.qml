import QtQuick
import QtQuick.Controls.Basic as C
import ABook

// Directly in the player's More menu: the label, mute and slider remain one
// level. Mouse drag and arrow/Home/End keys all call the shared Player.
Column {
    id: root
    spacing: Theme.s4
    Item {
        width: parent.width; height: 24
        Text { text: "Âm lượng"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall }
        ClockLabel { anchors.right: parent.right; text: Math.round(Player.volume * 100) + "%"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
    }
    Row {
        width: parent.width; spacing: Theme.s8
        IconButton {
            objectName: "volumeMute"
            icon: Player.volume === 0 ? "volume-x" : Player.volume < 0.5 ? "volume-1" : "volume-2"
            tip: Player.volume === 0 ? "Bật tiếng (M)" : "Tắt tiếng (M)"
            onClicked: Player.toggleMute()
        }
        C.Slider {
            id: slider; objectName: "volumeSlider"
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 44 - Theme.s8; height: 44
            from: 0; to: 1; stepSize: 0.05
            value: Player.volume
            onMoved: Player.setVolume(value)
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                    Player.setVolume(event.key === Qt.Key_End ? 1 : 0)
                    event.accepted = true
                }
            }
            Accessible.name: "Âm lượng"
            Accessible.description: `Âm lượng ${Math.round(Player.volume * 100)}%`
            background: Rectangle {
                x: slider.leftPadding; y: (slider.height - height) / 2
                width: slider.availableWidth; height: 4; radius: height / 2; color: Theme.line
                Rectangle { width: slider.visualPosition * parent.width; height: parent.height; radius: height / 2; color: Theme.accent }
            }
            handle: Rectangle {
                x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
                y: (slider.height - height) / 2
                width: 14; height: 14; radius: width / 2; color: Theme.text
                border.width: slider.activeFocus ? 2 : 0; border.color: Theme.focus
                scale: slider.pressed ? 1.15 : 1
                Behavior on scale { NumberAnimation { duration: Theme.motionFast } }
            }
        }
    }
}
