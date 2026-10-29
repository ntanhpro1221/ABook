import QtQuick
import ABook

// Dòng thu gọn kiểu <details> của tab Nhạc nền ("Bài đã bỏ (N)", "Ghi công (N)"): mũi tên nhỏ + một dòng chữ mực phụ, bấm thì phần dưới mở tại chỗ.
Column {
    id: root
    property string summary: ""
    property int fontSize: Theme.sizeBodySmall
    property bool expanded: false
    default property alias content: body.content
    Interactive {
        id: toggle
        objectName: "detailsToggle"
        width: Math.min(head.implicitWidth, root.width)
        height: Math.max(28, head.implicitHeight)
        pressScaling: false
        Accessible.role: Accessible.Button
        Accessible.name: root.summary
        Accessible.checkable: true
        Accessible.checked: root.expanded
        onClicked: root.expanded = !root.expanded
        Row {
            id: head
            spacing: 4
            anchors.verticalCenter: parent.verticalCenter
            Icon {
                name: "chevron-right"; size: 12; color: Theme.text2
                anchors.verticalCenter: parent.verticalCenter
                rotation: root.expanded ? 90 : 0
                Behavior on rotation { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            }
            Text { text: root.summary; color: toggle.hovered ? Theme.text : Theme.text2; font.pixelSize: root.fontSize }
        }
    }
    Collapse {
        id: body
        width: parent.width
        open: root.expanded
    }
}
