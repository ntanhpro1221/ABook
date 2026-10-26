import QtQuick
import ABook

// Ba trạng thái của vùng danh sách "Nhạc của tôi" (MotionRegion của MyMusicSection): đang tải (ContentSkeleton 2 hàng), lỗi tải (InlineError) và
// chưa có bài nào (EmptyState + nút thêm). Mỗi trạng thái mở / khép tại chỗ; không có gì thì vùng cao 0.
Column {
    id: root
    property string state: "ready"      // "loading" | "error" | "empty" | "ready"
    property bool adding: false
    signal retry()
    signal add()

    // ---- đang tải: hai hàng khung chờ (ô 40 + hai vạch 12), nhấp nháy nhẹ ----
    Collapse {
        width: parent.width
        open: root.state === "loading"
        Column {
            id: skeleton
            width: parent.width
            spacing: 16
            Accessible.role: Accessible.StaticText
            Accessible.name: "Đang tải nhạc riêng"
            property real pulse: 1
            SequentialAnimation on pulse {
                running: root.state === "loading" && !Theme.reduceMotion
                loops: Animation.Infinite
                NumberAnimation { to: 0.5; duration: 800; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1; duration: 800; easing.type: Easing.InOutSine }
            }
            Repeater {
                model: 2
                Item {
                    width: skeleton.width
                    height: 40
                    opacity: skeleton.pulse
                    Rectangle { width: 40; height: 40; radius: Theme.radiusControl; color: Theme.line }
                    Rectangle { x: 52; y: 6; width: (parent.width - 52) * 0.75; height: 12; radius: Theme.radiusControl; color: Theme.line }
                    Rectangle { x: 52; y: 26; width: (parent.width - 52) * 0.5; height: 12; radius: Theme.radiusControl; color: Theme.line }
                }
            }
        }
    }

    // ---- lỗi tải ----
    Collapse {
        width: parent.width
        open: root.state === "error"
        Item {
            width: parent.width
            height: Math.max(failure.implicitHeight, 40) + 24
            Icon { x: 0; y: 12 + 12; name: "triangle-alert"; size: 16; color: Theme.danger }
            Flow {
                id: failure
                x: 16 + 12
                y: 12
                width: parent.width - x
                spacing: 12
                Item {
                    width: Math.min(sentence.implicitWidth, failure.width)
                    height: Math.max(40, sentence.implicitHeight)
                    Text {
                        id: sentence
                        width: parent.width
                        anchors.verticalCenter: parent.verticalCenter
                        text: "Bạn hãy thử tải lại nhạc của bạn."
                        color: Theme.text2
                        wrapMode: Text.Wrap
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
                Button { text: "Thử lại"; icon: "rotate-cw"; kind: "ghost"; size: "sm"; onClicked: root.retry() }
            }
        }
    }

    // ---- chưa có bài nào ----
    Collapse {
        width: parent.width
        open: root.state === "empty"
        Column {
            width: parent.width
            topPadding: 24
            bottomPadding: 24
            spacing: 0
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                width: 56; height: 56
                radius: Theme.radiusCover
                color: Theme.accentSoft
                Icon { anchors.centerIn: parent; name: "eighth-note"; size: 28; color: Theme.accentText }
            }
            Item { width: 1; height: 16 }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                text: "Chưa có bài nào"
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeBody
                font.weight: 600
            }
            Item { width: 1; height: 20 }
            Button {
                anchors.horizontalCenter: parent.horizontalCenter
                text: "Thêm nhạc của bạn"; icon: "upload"; kind: "ghost"
                busy: root.adding
                onActivated: root.add()
            }
        }
    }
}
