import QtQuick
import ABook

// Thanh tiến độ của Studio (Progress của shared/ui.tsx): rãnh màu --line bo tròn, phần đã làm theo `tone` (accent / muted / success...).
// `size`: xs 4 · sm 6 · md 8.
Rectangle {
    id: root
    property real value: 0              // 0..1
    property string tone: "accent"
    property string size: "sm"
    property string label: ""
    readonly property real clamped: Math.max(0, Math.min(1, value))
    readonly property color fill: tone === "success" ? Theme.success : tone === "danger" ? Theme.danger : tone === "warning" ? Theme.warning
                                  : tone === "muted" ? Theme.text3 : Theme.accent
    height: size === "xs" ? 4 : size === "md" ? 8 : 6
    implicitHeight: height
    radius: height / 2
    color: Theme.line
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Accessible.description: Math.round(clamped * 100) + "%"
    Rectangle {
        objectName: "studioBarFill"
        width: parent.width * root.clamped
        height: parent.height
        radius: height / 2
        color: root.fill
        Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium } }
        // Phần tô theo giá trị tự đổi: vẽ thẳng, không Behavior (luật chủ sách 30-10; điện thoại native cũng vậy)
    }
}
