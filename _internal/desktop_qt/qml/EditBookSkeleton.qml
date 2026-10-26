import QtQuick
import ABook

// Khung chờ nội dung (ContentSkeleton của shared/ui.tsx): `rows` = ô vuông 40 + hai vạch; `covers` = lưới ô bìa 2:3 (cột >= 120, cách 16) + hai vạch.
// Nhịp thở chậm của các ô; giảm chuyển động thì đứng yên. `label`: tên cho trình đọc màn hình ("Đang tìm ảnh bìa").
Item {
    id: root
    property string shape: "rows"
    property int count: 3
    property string label: "Đang tải"
    readonly property int columns: shape === "covers" ? Math.max(1, Math.floor((width + 16) / (120 + 16))) : 1
    readonly property real cell: shape === "covers" ? (width - (columns - 1) * 16) / columns : width
    readonly property int lines: Math.ceil(count / columns)
    readonly property real rowHeight: shape === "covers" ? cell * 1.5 + 12 + 12 + 8 + 12 : 40
    implicitHeight: lines * rowHeight + Math.max(0, lines - 1) * 16
    height: implicitHeight
    Accessible.role: Accessible.StaticText
    Accessible.name: label
    property real pulse: 1
    SequentialAnimation on pulse {
        running: root.visible && !Theme.reduceMotion
        loops: Animation.Infinite
        NumberAnimation { to: 0.5; duration: 900; easing.type: Easing.InOutSine }
        NumberAnimation { to: 1; duration: 900; easing.type: Easing.InOutSine }
    }
    Repeater {
        model: root.count
        Item {
            required property int index
            x: root.shape === "covers" ? (index % root.columns) * (root.cell + 16) : 0
            y: Math.floor(index / root.columns) * (root.rowHeight + 16)
            width: root.cell
            height: root.rowHeight
            opacity: root.pulse
            Rectangle {
                visible: root.shape === "covers"
                width: parent.width; height: parent.width * 1.5
                radius: Theme.radiusCover
                color: Theme.sunken
            }
            Rectangle {
                visible: root.shape === "rows"
                width: 40; height: 40
                radius: Theme.radiusControl
                color: Theme.sunken
            }
            Column {
                x: root.shape === "rows" ? 52 : 0
                y: root.shape === "covers" ? parent.width * 1.5 + 12 : 4
                width: parent.width - x
                spacing: 8
                Rectangle { width: parent.width * 0.75; height: 12; radius: Theme.radiusControl; color: Theme.sunken }
                Rectangle { width: parent.width * 0.5; height: 12; radius: Theme.radiusControl; color: Theme.sunken }
            }
        }
    }
}
