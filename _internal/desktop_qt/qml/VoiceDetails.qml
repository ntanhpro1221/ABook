import QtQuick
import ABook

// "Chi tiết" thu gọn dưới một lời báo lỗi (ErrorDetails của shared): nguyên văn lỗi kỹ thuật để gửi cho người hỗ trợ, chữ 12 đơn cách, chọn chép được,
// bẻ ở bất kỳ đâu. Không có gì thì không hiện. Mở / khép theo chiều cao như mọi phần gập.
Column {
    id: root
    property string technical: ""
    property bool open: false
    property string shown: ""
    onTechnicalChanged: if (technical !== "") shown = technical
    VoiceBlock {
        width: parent.width
        show: root.technical !== ""
        gap: 4
        Interactive {
            width: parent.width
            height: Math.max(24, label.height + 4)
            ringMargin: 2
            Accessible.role: Accessible.Button
            Accessible.name: "Chi tiết"
            onClicked: root.open = !root.open
            Icon {
                id: marker
                name: "chevron-right"
                size: 12
                color: Theme.danger
                anchors.verticalCenter: parent.verticalCenter
                rotation: root.open ? 90 : 0
                Behavior on rotation { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            }
            Text {
                id: label
                x: 18
                anchors.verticalCenter: parent.verticalCenter
                text: "Chi tiết"
                color: Theme.danger
                font.pixelSize: Theme.sizeCaption
            }
        }
    }
    Collapse {
        width: parent.width
        open: root.open && root.technical !== ""
        TextEdit {
            width: parent.width
            topPadding: 4
            readOnly: true
            selectByMouse: true
            text: root.shown
            color: Theme.danger
            wrapMode: TextEdit.WrapAnywhere
            font.family: "monospace"
            font.pixelSize: Theme.sizeCaption
        }
    }
}
