import QtQuick
import ABook

// Công tắc hai lựa chọn ("Bìa" / "Đọc theo"): nền chìm, khối sáng trượt sang lựa chọn mới.
Item {
    id: root
    property var labels: ["", ""]
    property int index: 0
    property string label: "Bảng"
    Accessible.role: Accessible.PageTabList
    Accessible.name: label
    signal picked(int index)
    readonly property real firstWidth: Math.max(40, firstText.advanceWidth + 2 * Theme.s12)
    readonly property real secondWidth: Math.max(40, secondText.advanceWidth + 2 * Theme.s12)
    implicitWidth: firstWidth + secondWidth + 4
    implicitHeight: 36
    TextMetrics { id: firstText; text: root.labels[0]; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
    TextMetrics { id: secondText; text: root.labels[1]; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.sunken
    }
    Rectangle {
        x: 2 + (root.index === 0 ? 0 : root.firstWidth)
        y: 2
        width: root.index === 0 ? root.firstWidth : root.secondWidth
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
        id: tabs
        model: 2
        Interactive {
            required property int index
            x: 2 + (index === 0 ? 0 : root.firstWidth)
            y: 2
            implicitWidth: index === 0 ? root.firstWidth : root.secondWidth
            width: implicitWidth
            height: root.height - 4
            pressScaling: false
            Accessible.role: Accessible.PageTab
            Accessible.name: root.labels[index]
            Accessible.checkable: true
            Accessible.checked: root.index === index
            activeFocusOnTab: root.index === index || activeFocus
            Keys.onPressed: event => {
                let next = -1
                if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) next = 1 - root.index
                else if (event.key === Qt.Key_Home) next = 0
                else if (event.key === Qt.Key_End) next = 1
                if (next >= 0) { root.picked(next); tabs.itemAt(next).forceActiveFocus(); event.accepted = true }
            }
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
