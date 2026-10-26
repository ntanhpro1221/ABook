import QtQuick
import ABook

// Thanh tua. `compact`: đường mảnh ở mép trên thanh phát (2 px, rê chuột dày 4 px); không thì thanh 4 px của màn Đang nghe (rê: 6 px + núm).
// Rê chuột hiện giờ ở chỗ con trỏ; bấm hay kéo là tua (thả chuột mới tua thật, trong lúc kéo hiện giờ sẽ tới).
Item {
    id: root
    property bool compact: false
    readonly property real total: Player.clock.duration
    property bool dragging: false
    property real dragFraction: 0
    property real hoverFraction: 0
    readonly property bool hovered: area.containsMouse
    readonly property real fraction: dragging ? dragFraction : (total > 0 ? Math.max(0, Math.min(1, Player.clock.position / total)) : 0)
    /// Giây đang hiện (trong lúc kéo là chỗ sẽ tới).
    readonly property real shownPosition: dragging ? dragFraction * total : Player.clock.position
    readonly property bool active: hovered || dragging
    implicitHeight: compact ? 12 : 24
    enabled: Player.loaded && total > 0

    ClockUser { wanted: root.visible }

    Rectangle {
        id: track
        width: parent.width
        height: root.compact ? (root.active ? 4 : 2) : (root.active ? 6 : 4)
        anchors.verticalCenter: parent.verticalCenter
        radius: height / 2
        color: root.compact ? Theme.line : Theme.sunken
        Behavior on height { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }
        Rectangle {
            width: parent.width * root.fraction
            height: parent.height
            radius: parent.radius
            color: Theme.accent
        }
    }
    Rectangle {
        visible: !root.compact && opacity > 0
        opacity: root.active ? 1 : 0
        width: 14
        height: 14
        radius: width / 2
        color: Theme.accent
        x: root.width * root.fraction - width / 2
        anchors.verticalCenter: parent.verticalCenter
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    // Giờ ở chỗ con trỏ (hay chỗ đang kéo tới)
    Rectangle {
        id: bubble
        opacity: root.active ? 1 : 0
        visible: opacity > 0
        width: bubbleText.implicitWidth + 16
        height: bubbleText.implicitHeight + 8
        radius: Theme.radiusControl
        color: Theme.dark ? Theme.text : "#2a2723"
        readonly property real at: root.dragging ? root.dragFraction : root.hoverFraction
        x: Math.max(0, Math.min(root.width - width, root.width * at - width / 2))
        y: -height - (root.compact ? 2 : 4)
        Behavior on opacity { NumberAnimation { duration: root.active ? Theme.motionFast : Theme.motionFastOut } }
        Text {
            id: bubbleText
            anchors.centerIn: parent
            text: Player.clockText(bubble.at * root.total)
            color: Theme.dark ? Theme.bg : "#f5f3ef"
            font.pixelSize: Theme.sizeCaption
        }
    }
    MouseArea {
        id: area
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        cursorShape: Qt.PointingHandCursor
        function fractionAt(x) { return Math.max(0, Math.min(1, x / width)) }
        // Kéo qua một mốc (mỗi 15 giây, hay chạm đầu / cuối chương): tiếng "tích" (crossedSeekMark của shared/feedback.ts). Chỉ khi đang kéo.
        function crossedMark(from, to) {
            if (from === to) return false
            const edge = value => value <= 0 || (root.total > 0 && value >= root.total)
            if (edge(to)) return !edge(from)
            return Math.floor(from / 15) !== Math.floor(to / 15)
        }
        onPositionChanged: (mouse) => {
            root.hoverFraction = fractionAt(mouse.x)
            if (pressed) {
                if (crossedMark(Math.round(root.dragFraction * root.total), Math.round(root.hoverFraction * root.total))) Feedback.play("tick")
                root.dragFraction = root.hoverFraction
            }
        }
        onPressed: (mouse) => {
            root.dragFraction = fractionAt(mouse.x)
            root.hoverFraction = root.dragFraction
            root.dragging = true
        }
        onReleased: {
            if (root.dragging) Player.seek(root.dragFraction * root.total)
            root.dragging = false
        }
        onCanceled: root.dragging = false
    }
}
