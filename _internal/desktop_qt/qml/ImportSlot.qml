import QtQuick
import ABook

// Chỗ của một nút ở chân hộp: hiện / ẩn thì bề ngang nở ra / co lại trong motionMedium (cùng đường cong với Collapse) cùng mờ dần, các nút bên cạnh trượt theo,
// không bật tắt cứng. Giảm chuyển động: chỉ mờ <= motionFast. Nút gập thì ra khỏi Tab. Đặt đúng một nút vào trong.
Item {
    id: root
    property bool open: true
    default property alias content: holder.data
    property real reveal: open ? 1 : 0
    readonly property Item child: holder.children.length ? holder.children[0] : null
    visible: reveal > 0
    opacity: reveal
    width: child ? (Theme.reduceMotion ? (open ? child.implicitWidth : 0) : child.implicitWidth * reveal) : 0
    height: child ? child.implicitHeight : 0
    clip: reveal < 1
    enabled: open
    Behavior on reveal {
        NumberAnimation {
            duration: Theme.reduceMotion ? Theme.motionFast : (root.open ? Theme.motionMedium : Theme.motionMediumOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeStandard : Theme.easeAccelerate
        }
    }
    Item {
        id: holder
        width: root.child ? root.child.implicitWidth : 0
        height: root.child ? root.child.implicitHeight : 0
    }
}
