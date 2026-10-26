import QtQuick
import ABook

// Lời nhắn ngắn của bộ phát ("Đã tới 12:30" + "Quay lại", "Nghe từ “…”", "Chương sau chưa có audio"): một viên thuốc đảo màu nổi ở giữa khung, tự tắt sau 8 giây
// (bộ phát tắt), hiện / ẩn bằng trượt 12 px + mờ. Giữ chữ cũ trong lúc mờ đi để không nhấp nháy.
Item {
    id: root
    readonly property bool shown: Player.notice !== ""
    property string text: ""
    property string action: ""
    width: pill.width
    height: pill.height
    visible: pill.opacity > 0

    onShownChanged: if (shown) { text = Player.notice; action = Player.noticeAction }
    Connections {
        target: Player
        function onNoticeChanged() {
            if (Player.notice !== "") { root.text = Player.notice; root.action = Player.noticeAction }
        }
    }

    Rectangle {
        id: pill
        width: Math.min(row.implicitWidth + 2 * Theme.s16, 560)
        height: Math.max(40, row.implicitHeight + 2 * Theme.s8)
        radius: Math.min(20, height / 2)
        color: Theme.dark ? Theme.text : "#2a2723"
        opacity: root.shown ? 1 : 0
        transform: Translate { y: root.shown ? 0 : 12 }
        Behavior on opacity { NumberAnimation { duration: root.shown ? Theme.motionMedium : Theme.motionFastOut } }
        Row {
            id: row
            anchors.centerIn: parent
            spacing: Theme.s12
            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, 560 - 2 * Theme.s16 - (actionLabel.visible ? actionLabel.width + Theme.s12 : 0))
                text: root.text
                wrapMode: Text.Wrap
                color: Theme.dark ? Theme.bg : "#f5f3ef"
                font.pixelSize: Theme.sizeBodySmall
            }
            Interactive {
                id: actionLabel
                visible: root.action !== ""
                anchors.verticalCenter: parent.verticalCenter
                width: actionText.implicitWidth + 2 * Theme.s8
                height: 32
                enabled: root.shown
                onClicked: Player.runNoticeAction()
                Text {
                    id: actionText
                    anchors.centerIn: parent
                    text: root.action
                    color: Theme.dark ? Theme.accentText : Theme.accent
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                }
            }
        }
    }
}
