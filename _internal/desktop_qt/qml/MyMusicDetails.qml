import QtQuick
import ABook

// "Chi tiết" thu gọn dưới một lời báo lỗi (ErrorDetails của shared/ErrorDetails.tsx): nguyên văn lỗi kỹ thuật để gửi cho người hỗ trợ, mở ra tại chỗ;
// không có gì thì khép lại (vẫn giữ chữ cuối cho tới khi khép xong).
Collapse {
    id: root
    property string technical: ""
    property color ink: Theme.danger
    property bool detailsOpen: false
    property string kept: ""
    onTechnicalChanged: if (technical !== "") kept = technical
    open: technical !== ""
    Item {
        width: parent.width
        height: toggle.height + more.height
        Interactive {
            id: toggle
            width: head.implicitWidth
            height: Math.max(24, head.implicitHeight)
            Accessible.role: Accessible.Button
            Accessible.name: "Chi tiết"
            onClicked: root.detailsOpen = !root.detailsOpen
            Row {
                id: head
                spacing: 4
                anchors.verticalCenter: parent.verticalCenter
                Icon {
                    name: "chevron-right"; size: 12; color: root.ink
                    anchors.verticalCenter: parent.verticalCenter
                    rotation: root.detailsOpen ? 90 : 0
                    Behavior on rotation { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
                }
                Text { text: "Chi tiết"; color: root.ink; font.pixelSize: Theme.sizeCaption }
            }
        }
        Collapse {
            id: more
            y: toggle.height
            width: parent.width
            open: root.detailsOpen
            TextEdit {
                width: parent.width
                topPadding: 4
                readOnly: true
                selectByMouse: true
                text: root.kept
                color: root.ink
                wrapMode: TextEdit.WrapAtWordBoundaryOrAnywhere
                font.family: "monospace"
                font.pixelSize: Theme.sizeCaption
            }
        }
    }
}
