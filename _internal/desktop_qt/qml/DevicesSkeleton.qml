import QtQuick
import ABook

// Khung chờ theo hình dòng danh sách (ContentSkeleton shape="rows" của shared/ui.tsx): ô vuông 40 + hai vạch, đập nhẹ khi đang chờ.
Column {
    id: root
    property int count: 2
    property string label: "Đang tải"
    spacing: Theme.s16
    Accessible.role: Accessible.StaticText
    Accessible.name: label
    opacity: 1
    SequentialAnimation on opacity {
        running: root.visible && !Theme.reduceMotion
        loops: Animation.Infinite
        NumberAnimation { to: 0.6; duration: 800; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1; duration: 800; easing.type: Easing.InOutSine }
    }
    Repeater {
        model: root.count
        Row {
            spacing: Theme.s12
            Rectangle { width: 40; height: 40; radius: Theme.radiusControl; color: Theme.line }
            Column {
                width: root.width - 52
                anchors.verticalCenter: parent.verticalCenter
                spacing: Theme.s8
                Rectangle { width: parent.width * 0.75; height: 12; radius: Theme.radiusControl; color: Theme.line }
                Rectangle { width: parent.width * 0.5; height: 12; radius: Theme.radiusControl; color: Theme.line }
            }
        }
    }
}
