import QtQuick
import ABook

// Công tắc hai lựa chọn ("Bìa" / "Đọc theo"): nền chìm, khối sáng trượt sang lựa chọn mới.
Item {
    id: root
    property var labels: ["", ""]
    property int index: 0
    signal picked(int index)
    readonly property real cell: 84
    implicitWidth: 2 * cell + 4
    implicitHeight: 36

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.sunken
    }
    Rectangle {
        x: 2 + root.index * root.cell
        y: 2
        width: root.cell
        height: root.height - 4
        radius: Theme.radiusControl
        color: Theme.panel
        Behavior on x {
            NumberAnimation {
                duration: Theme.reduceMotion ? 0 : Theme.motionMedium
                easing.type: Easing.BezierSpline
                easing.bezierCurve: Theme.easeStandard
            }
        }
    }
    Repeater {
        model: 2
        Interactive {
            required property int index
            x: 2 + index * root.cell
            y: 2
            width: root.cell
            height: root.height - 4
            pressScaling: false
            ringRadius: Theme.radiusControl - 2
            onClicked: root.picked(index)
            Text {
                anchors.centerIn: parent
                text: root.labels[index]
                color: root.index === index ? Theme.text : Theme.text2
                font.pixelSize: Theme.sizeBodySmall
                font.weight: root.index === index ? Theme.weightMedium : Theme.weightRegular
            }
        }
    }
}
