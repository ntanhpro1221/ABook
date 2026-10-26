import QtQuick
import ABook

// Giải thích dài người dùng cần biết (quyền riêng tư, an toàn dữ liệu) gập sau một hàng "?" (MoreInfo của shared/SettingsNav.tsx): hàng
// DisclosureRow có icon dấu hỏi, thân là chữ 12 mực phụ mở ra tại chỗ. Nội dung đặt thẳng vào trong (thường một hay vài Text).
Column {
    id: root
    property string label: "Tìm hiểu thêm"
    property bool open: false
    default property alias content: body.content
    DisclosureRow {
        width: parent.width
        title: root.label
        icon: "circle-question-mark"
        expanded: root.open
        onClicked: root.open = !root.open
    }
    Collapse {
        id: body
        width: parent.width
        open: root.open
        spacing: 8
    }
}
