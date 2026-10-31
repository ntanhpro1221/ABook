import QtQuick
import ABook

// = Vu của shared/ui.tsx: bốn vạch nhảy khi đang thu / đang phát (styles.css @keyframes vu: scaleY 0,3 <-> 1 neo đáy, vòng 1 s, lệch pha
// 0 / 0,35 / 0,7 / 0,2). Mặc định h-3 (12) vạch 3 cách 2; viên trạng thái h-2.5 (10), thanh bên h-2.5 vạch 2 cách 1. Giảm chuyển động:
// vạch đứng yên cao hết như web. `still` (ảnh chụp, VisualReady): đứng ở khung đầu của vòng, vạch cao thấp như đang nhảy - icon nét
// mảnh "audio-lines" ở 12 px chỉ là một vệt mờ (Lead soát 0.4.151 lượt 2, viên "Đang thu âm").
Item {
    id: root
    property color color: Theme.text2
    property real barWidth: 3
    property real gap: 2
    property bool still: false
    property real phase: 0
    readonly property var offsets: [0, 0.35, 0.7, 0.2]
    implicitWidth: 4 * barWidth + 3 * gap
    implicitHeight: 12
    width: implicitWidth
    height: implicitHeight
    NumberAnimation on phase { from: 0; to: 1; duration: 1000; loops: Animation.Infinite; running: root.visible && !Theme.reduceMotion && !root.still }
    Repeater {
        model: 4
        Rectangle {
            required property int index
            readonly property real lift: Theme.reduceMotion ? 1 : 0.3 + 0.35 * (1 - Math.cos(2 * Math.PI * ((root.still ? 0 : root.phase) + root.offsets[index])))
            x: index * (root.barWidth + root.gap)
            width: root.barWidth
            height: root.height * lift
            y: root.height - height
            radius: width / 2
            color: root.color
        }
    }
}
