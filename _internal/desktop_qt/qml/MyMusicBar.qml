import QtQuick
import ABook

// Thanh tiến độ cỡ sm của Progress (shared/ui.tsx): rãnh cao 6 bo tròn màu --line, phần đã tải màu nhấn; phần trăm đổi thì thanh trượt theo.
Rectangle {
    id: root
    property real value: 0              // 0..1
    property string label: ""
    height: 6
    radius: height / 2
    color: Theme.line
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Rectangle {
        width: parent.width * Math.max(0, Math.min(1, root.value))
        height: parent.height
        radius: height / 2
        color: Theme.accent
        Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    }
}
