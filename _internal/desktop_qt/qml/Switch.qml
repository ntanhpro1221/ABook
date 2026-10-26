import QtQuick
import ABook

// Công tắc (như .ui-switch của bản web): rãnh 44 x 24 bo tròn, núm 20 cách mép 2. Bật: rãnh màu tiêu điểm (--focus: >= 3:1 trên mọi nền, --accent thì
// không đạt); tắt: --switch-off. Núm trượt và rãnh đổi màu trong motionFast; giảm chuyển động thì núm đứng yên chỗ mới, chỉ mờ chéo.
Interactive {
    id: root
    property bool checked: false
    signal toggled(bool checked)

    implicitWidth: 44
    implicitHeight: 24
    ringRadius: height / 2
    opacity: enabled ? 1 : 0.5
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    onClicked: if (enabled) root.toggled(!root.checked)

    Rectangle {
        anchors.fill: parent
        radius: height / 2
        color: root.checked ? Theme.focus : Theme.switchOff
        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
    }
    Rectangle {
        width: 20
        height: 20
        radius: height / 2
        y: 2
        x: root.checked ? root.width - width - 2 : 2
        color: Theme.switchThumb
        Behavior on x {
            enabled: !Theme.reduceMotion
            NumberAnimation { duration: Theme.motionFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        }
    }
}
