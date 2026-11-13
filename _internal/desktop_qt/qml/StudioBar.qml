import QtQuick
import ABook

// Thanh tiến độ của Studio (Progress của shared/ui.tsx): rãnh màu --line bo tròn, phần đã làm theo `tone` (accent / muted / success...).
// `size`: xs 4 · sm 6 · md 8. `indeterminate`: việc chưa biết tổng - một đoạn chạy qua lại liên tục (.indeterminate-bar của web, 1,4 s),
// không phải số đứng yên; đổi giữa hai dạng mờ chéo, giảm chuyển động thì đoạn đứng giữa rãnh.
Rectangle {
    id: root
    property real value: 0              // 0..1
    property bool indeterminate: false
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
    clip: true
    Accessible.role: Accessible.ProgressBar
    Accessible.name: label
    Accessible.description: indeterminate ? "" : Math.round(clamped * 100) + "%"
    Rectangle {
        objectName: "studioBarFill"
        width: parent.width * root.clamped
        height: parent.height
        radius: height / 2
        color: root.fill
        opacity: root.indeterminate ? 0 : 1
        Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? Theme.motionReduced : Theme.motionMedium } }
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionFast : Theme.motionMedium } }
        // Phần tô theo giá trị tự đổi: vẽ thẳng, không Behavior (luật chủ sách 30-10; điện thoại native cũng vậy)
    }
    Rectangle {
        id: runner
        objectName: "studioBarRunner"
        width: parent.width * 0.4
        height: parent.height
        radius: height / 2
        color: root.fill
        x: (parent.width - width) / 2
        opacity: root.indeterminate ? 1 : 0
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? Theme.motionFast : Theme.motionMedium } }
        SequentialAnimation on x {
            running: root.indeterminate && root.visible && Nav.uiVisible && !Theme.reduceMotion
            loops: Animation.Infinite
            NumberAnimation { from: -runner.width; to: root.width; duration: Theme.indeterminateMs; easing.type: Easing.InOutSine }
        }
    }
}
