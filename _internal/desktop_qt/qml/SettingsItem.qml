import QtQuick
import ABook

// Một mục trong khối Cài đặt (thân của SettingsBlock là `divide-y divide-line` của bản web): vạch 1 px trên đầu mọi mục trừ mục thấy được đầu
// tiên. Nội dung là một cột, đệm trên / dưới mặc định 14 (py-3.5 của web); hàng có nhãn dùng SettingRow (py-3).
Item {
    id: root
    property real padding: 14
    property alias spacing: body.spacing
    default property alias content: body.data
    readonly property bool firstShown: {
        const kids = parent ? parent.children : []
        for (let i = 0; i < kids.length; ++i)
            if (kids[i].visible && kids[i].height > 0) return kids[i] === root
        return true
    }
    implicitHeight: body.implicitHeight + 2 * padding
    Rectangle { width: parent.width; height: 1; color: Theme.line; visible: !root.firstShown }
    Column { id: body; y: root.padding; width: root.width }
}
