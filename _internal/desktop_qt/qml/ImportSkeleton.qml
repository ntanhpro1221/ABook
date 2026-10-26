import QtQuick
import ABook

// Khung xám đúng hình việc đang chờ (ContentSkeleton của bản web): "cards" = tiêu đề + hai vạch, "rows" = ô vuông + hai vạch. Nhịp mờ 0,6 <-> 1 chu kỳ 1,6 s, không
// vòng xoay; giảm chuyển động thì đứng yên. `label` là lời cho trình đọc màn hình.
Column {
    id: root
    property string shape: "rows"        // "rows" | "cards"
    property int count: 1
    property string label: "Đang tải"
    spacing: 16
    Accessible.role: Accessible.StaticText
    Accessible.name: label
    SequentialAnimation on opacity {
        running: root.visible && !Theme.reduceMotion
        loops: Animation.Infinite
        NumberAnimation { from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
        NumberAnimation { from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
    }
    Repeater {
        model: root.count
        Item {
            width: root.width
            height: root.shape === "cards" ? 24 + 16 + 12 + 12 + 8 + 12 : 40
            Rectangle { visible: root.shape === "rows"; width: 40; height: 40; radius: Theme.radiusControl; color: Theme.sunken }
            Rectangle { visible: root.shape === "cards"; y: 12; width: parent.width / 3; height: 16; radius: Theme.radiusControl; color: Theme.sunken }
            Column {
                x: root.shape === "rows" ? 52 : 0
                y: root.shape === "rows" ? 4 : 12 + 16 + 12
                width: parent.width - x
                spacing: 8
                Rectangle { width: parent.width * 0.75; height: 12; radius: Theme.radiusControl; color: Theme.sunken }
                Rectangle { width: root.shape === "cards" ? parent.width : parent.width * 0.5; height: 12; radius: Theme.radiusControl; color: Theme.sunken }
            }
        }
    }
}
