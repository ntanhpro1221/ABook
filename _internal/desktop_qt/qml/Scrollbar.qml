import QtQuick
import ABook

// Thanh cuộn mảnh cho Flickable / GridView: hiện khi cuộn hay rê chuột, kéo được, tự ẩn sau 1 giây.
Item {
    id: root
    required property Flickable target
    width: 14
    anchors.top: target.top
    anchors.bottom: target.bottom
    anchors.right: target.right

    readonly property real range: target.contentHeight - target.height + target.topMargin + target.bottomMargin
    readonly property bool scrollable: range > 1
    property bool active: target.moving || target.flicking || hover.hovered || drag.active || recent.running
    visible: scrollable && opacity > 0
    opacity: active ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: active ? Theme.motionFast : Theme.motionSlow } }

    Timer { id: recent; interval: 1000 }
    Connections {
        target: root.target
        function onContentYChanged() { recent.restart() }
    }
    HoverHandler { id: hover }

    Rectangle {
        id: thumb
        readonly property real minH: 40
        width: hover.hovered || drag.active ? 8 : 4
        Behavior on width { NumberAnimation { duration: Theme.motionFast } }
        anchors.right: parent.right
        anchors.rightMargin: 3
        radius: width / 2
        color: Theme.text
        opacity: drag.active ? 0.5 : 0.28
        height: Math.max(minH, root.height * root.target.height / Math.max(1, root.target.contentHeight))
        y: root.scrollable
            ? (root.target.contentY - root.target.originY + root.target.topMargin) / root.range * (root.height - height)
            : 0
        DragHandler {
            id: drag
            target: null
            yAxis.enabled: true
            xAxis.enabled: false
            onTranslationChanged: {
                // translation.y: pixel đã kéo từ lúc nhấn; đổi sang contentY theo tỉ lệ rãnh
                const travel = root.height - thumb.height
                if (travel > 0)
                    root.target.contentY = Math.max(0, Math.min(root.range, start + translation.y / travel * root.range)) + root.target.originY - root.target.topMargin
            }
            onActiveChanged: if (active) start = root.target.contentY - root.target.originY + root.target.topMargin
            property real start: 0
        }
    }
}
