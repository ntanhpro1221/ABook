import QtQuick
import ABook

// Trạng thái của "bộ máy" bên dưới (backend Python), một dòng nhỏ cuối thanh bên: chấm + chữ. Bấm mở bảng chi tiết.
// Chữ nói theo người nghe: Đang mở / Sẵn sàng / Gặp lỗi.
Interactive {
    id: root
    implicitHeight: Theme.hit
    tip: "Trạng thái ABook"

    readonly property bool starting: Backend.state === Backend.Starting
    readonly property bool failed: Backend.state === Backend.Failed
    readonly property color dotColor: failed ? Theme.danger : (starting ? Theme.accent : Theme.success)

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.text
        opacity: root.pressed ? 0.10 : (root.hovered ? 0.05 : 0)
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Row {
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: parent.left
        anchors.leftMargin: Theme.s12
        spacing: Theme.s12
        Item {
            width: 18
            height: 18
            anchors.verticalCenter: parent.verticalCenter
            Rectangle {
                id: dot
                anchors.centerIn: parent
                width: 8
                height: 8
                radius: 4
                color: root.dotColor
                SequentialAnimation on opacity {
                    running: root.starting && !Theme.reduceMotion
                    loops: Animation.Infinite
                    onRunningChanged: if (!running) dot.opacity = 1
                    NumberAnimation { to: 0.35; duration: 700; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1; duration: 700; easing.type: Easing.InOutSine }
                }
            }
        }
        Text {
            anchors.verticalCenter: parent.verticalCenter
            text: root.failed ? "Gặp lỗi" : (root.starting ? "Đang mở…" : "Sẵn sàng")
            color: Theme.text2
            font.pixelSize: Theme.sizeBodySmall
        }
    }
}
