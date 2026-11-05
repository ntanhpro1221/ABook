import QtQuick
import ABook

// Nhạc nền của cuốn (như PackagedMusicMenu của bản web): bật/tắt, mức nhạc dưới giọng đọc, lời nhắc đổi ở đâu. Chọn mức không đóng bảng:
// dấu ✓ mờ qua, nền đổi dần. Tắt nhạc thì các mức mờ đi và không bấm được.
Popover {
    id: root
    panelWidth: 256

    Column {
        width: parent.width
        spacing: 0

        Item {
            width: parent.width
            height: Math.max(header.implicitHeight, toggle.height) + 2 * Theme.s8
            Text {
                id: header
                anchors.left: parent.left
                anchors.leftMargin: Theme.s8
                anchors.right: toggle.left
                anchors.rightMargin: Theme.s12
                anchors.verticalCenter: parent.verticalCenter
                textFormat: Text.StyledText
                text: "Nhạc nền: <b>" + (Music.enabled ? "Bật" : "Tắt") + "</b>"
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBodySmall
                font.weight: Theme.weightMedium
            }
            Switch {
                id: toggle
                anchors.right: parent.right
                anchors.rightMargin: Theme.s8
                anchors.verticalCenter: parent.verticalCenter
                tip: "Nhạc nền"
                checked: Music.enabled
                enabled: !Music.busy
                onToggled: (on) => Music.setEnabled(on)
            }
        }
        Warning { shown: Music.enabled && Music.broken; text: "Bài nhạc chương này không phát được." }
        Warning { shown: Music.problem !== ""; text: Music.problem }

        Column {
            width: parent.width
            opacity: Music.enabled ? 1 : 0.5
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Text {
                x: Theme.s8
                width: parent.width - 2 * Theme.s8
                topPadding: Theme.s4
                bottomPadding: Theme.s4
                text: "Mức nhạc nền"
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            MusicLevelSlider {
                x: Theme.s8
                width: parent.width - 2 * Theme.s8
                value: Music.levelDb
                enabled: Music.enabled && !Music.busy
                onPicked: value => Music.setLevel(value)
            }
        }
        Text {
            x: Theme.s8
            width: parent.width - 2 * Theme.s8
            topPadding: 6
            bottomPadding: Theme.s4
            text: Music.project ? "Đổi luôn trong Studio."
                                : "Chỉ đổi trên máy này."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }

    // Dòng cảnh báo hiện / ẩn dần (chiều cao và độ mờ cùng đi), không bật tắt cứng.
    component Warning: Item {
        id: warning
        property bool shown: false
        property alias text: line.text
        width: parent.width
        height: shown ? line.implicitHeight : 0
        opacity: shown ? 1 : 0
        clip: height < line.implicitHeight
        Behavior on height { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        Text {
            id: line
            x: Theme.s8
            width: warning.width - 2 * Theme.s8
            bottomPadding: Theme.s4
            color: Theme.warning
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }

}
