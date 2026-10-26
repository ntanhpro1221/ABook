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
                text: "Mức nhạc dưới giọng đọc"
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                font.weight: Theme.weightMedium
            }
            Column {
                width: parent.width
                topPadding: Theme.s4
                bottomPadding: Theme.s4
                spacing: 2
                Repeater {
                    model: Music.levels
                    LevelRow {
                        required property var modelData
                        width: parent.width
                        name: modelData.name
                        note: modelData.note
                        selected: Math.abs(modelData.value - Music.levelDb) < 0.001
                        enabled: Music.enabled && !Music.busy
                        onClicked: Music.setLevel(modelData.value)
                    }
                }
            }
        }
        Text {
            x: Theme.s8
            width: parent.width - 2 * Theme.s8
            topPadding: 6
            bottomPadding: Theme.s4
            text: Music.project ? "Nhạc của cuốn này. Đổi ở đây là đổi luôn trong Studio."
                                : "Nhạc do người làm sách chọn. Đổi ở đây chỉ trên máy này."
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

    // Một mức (CHOICE_ROW của bản web): cao tối thiểu 36, dấu ✓ + tên + ghi chú nhỏ; mức đang chọn đậm, màu nhấn.
    component LevelRow: Interactive {
        id: row
        property string name: ""
        property string note: ""
        property bool selected: false
        implicitHeight: Math.max(36, content.implicitHeight + 2 * Theme.s4)
        pressScaling: enabled

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusControl
            color: Theme.text
            opacity: row.enabled ? (row.pressed ? 0.10 : (row.hovered ? 0.05 : 0)) : 0
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        }
        Row {
            id: content
            x: Theme.s8
            width: row.width - 2 * Theme.s8
            anchors.verticalCenter: parent.verticalCenter
            spacing: Theme.s8
            Icon {
                name: "check"
                size: 16
                color: Theme.accentText
                opacity: row.selected ? 1 : 0
                anchors.verticalCenter: parent.verticalCenter
                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            }
            Text {
                id: label
                text: row.name
                color: row.selected ? Theme.accentText : Theme.text
                font.pixelSize: Theme.sizeBodySmall
                font.weight: row.selected ? Font.DemiBold : Theme.weightRegular
                anchors.verticalCenter: parent.verticalCenter
                Behavior on color { ColorAnimation { duration: Theme.motionFast } }
            }
            Text {
                visible: row.note !== ""
                width: Math.min(implicitWidth, content.width - 16 - label.implicitWidth - 2 * Theme.s8)
                text: row.note
                color: Theme.text2
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
                anchors.verticalCenter: parent.verticalCenter
            }
        }
    }
}
