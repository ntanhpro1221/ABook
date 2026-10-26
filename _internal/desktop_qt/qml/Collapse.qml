import QtQuick
import ABook

// Thân gấp / mở (như Collapse / MotionPresence của bản web): chiều cao tween theo nội dung + mờ, không bật tắt cứng. Mở: motionMedium,
// đường cong standard; khép: motionMediumOut, accelerate. Giảm chuyển động: không tween chiều cao, chỉ mờ <= 120 ms. Gập thì ra khỏi Tab.
// Nội dung đặt thẳng vào trong (một cột, bề ngang = bề ngang của Collapse).
Item {
    id: root
    property bool open: false
    default property alias content: body.data
    property alias spacing: body.spacing
    property real reveal: open ? 1 : 0
    readonly property bool settled: reveal === (open ? 1 : 0)
    implicitHeight: Theme.reduceMotion ? (open || reveal > 0 ? body.implicitHeight : 0) : body.implicitHeight * reveal
    height: implicitHeight
    clip: !settled || !open
    visible: reveal > 0
    Behavior on reveal {
        NumberAnimation {
            duration: Theme.reduceMotion ? Theme.motionFast : (root.open ? Theme.motionMedium : Theme.motionMediumOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeStandard : Theme.easeAccelerate
        }
    }
    Column {
        id: body
        width: root.width
        opacity: root.reveal
        enabled: root.open
    }
}
