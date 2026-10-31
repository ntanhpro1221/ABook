import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// Một hàng cho cả đi tới và gập mở (shared/DisclosureRow.tsx): icon (tuỳ), tên 16 + một dòng tóm tắt 14 mực phụ, mũi tên neo mép phải
// (mũi tên phải chỉ cho hàng mở trang con; hàng gập mở tại chỗ - `expanded` có gán - mang mũi tên xuống, lật lên khi mở). Mục đang mở của danh sách nhóm là điều hướng (DESIGN 6): nền trung tính nhạt + chữ đậm màu thường. Nền rê chuột tràn
// 12 px ra hai bên, bố cục hàng không đổi. `section`: đầu khối gập của Cài đặt (tên cỡ tiêu đề mục 18/500).
Interactive {
    id: root
    property string title: ""
    property string summary: ""
    property string icon: ""
    // undefined = hàng đi tới (mũi tên phải); true / false = hàng gập mở tại chỗ (mũi tên xuống), như `expanded` của bản web
    property var expanded: undefined
    readonly property bool toggles: expanded !== undefined
    property bool current: false
    property bool section: false
    Accessible.role: Accessible.Button
    Accessible.name: title
    implicitHeight: Math.max(56, words.height + (section ? 0 : 12))
    pressScaling: false
    ringMargin: 14

    Rectangle {
        x: -12
        width: root.width + 24
        height: root.height
        radius: Theme.radiusControl
        color: Theme.hover
        opacity: root.current || root.hovered ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Icon {
        id: lead
        visible: root.icon !== ""
        name: root.icon
        size: 20
        color: root.current ? Theme.text : Theme.text2
        anchors.verticalCenter: parent.verticalCenter
    }
    Column {
        id: words
        x: lead.visible ? lead.width + 14 : 0
        width: Math.min(640, root.width - x - 14 - 16)
        anchors.verticalCenter: parent.verticalCenter
        Text {
            width: parent.width
            text: root.title
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: root.section ? Theme.sizeSection : Theme.sizeBody
            font.weight: root.section ? Theme.weightMedium : (root.current ? 600 : Theme.weightMedium)
            lineHeight: root.section ? 24 : 1
            lineHeightMode: root.section ? Text.FixedHeight : Text.ProportionalHeight
        }
        Text {
            width: parent.width
            visible: root.summary !== ""
            text: TextWrap.pretty(root.summary)
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
    Icon {
        anchors.right: parent.right
        anchors.rightMargin: root.toggles ? 1 : -1     // mực của chevron (14 px trong ô 16) thẳng mép cột; mũi tên xuống rộng hơn 2 px mỗi bên
        anchors.verticalCenter: parent.verticalCenter
        name: root.toggles ? "chevron-down" : "chevron-right"
        size: 16
        color: Theme.text3
        rotation: root.expanded === true ? 180 : 0
        Behavior on rotation { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    }
}
