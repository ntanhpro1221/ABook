import QtQuick
import ABook

// Khối gập của Cài đặt › Thiết bị (Fold của shared/Collapse.tsx): đầu là DisclosureRow cỡ tiêu đề mục (tên + một dòng tóm tắt + mũi tên xoay),
// thân là Collapse đệm dưới 12. Mặc định gập (hoặc `defaultOpen`); mở rồi thì lần sau vẫn mở (Platform.setting "fold.<khoá>", như
// localStorage abook.fold.<khoá> của web). Nội dung đặt thẳng vào trong (bề ngang = bề ngang khối).
Column {
    id: root
    property string storageKey: ""
    property string title: ""
    property string summary: ""
    property bool defaultOpen: false
    property real bottomGap: 12
    property bool expanded: {
        const saved = Platform.setting("fold." + storageKey, "")
        return saved === "" ? defaultOpen : saved === "1"
    }
    default property alias content: inner.data

    DisclosureRow {
        width: parent.width
        section: true
        title: root.title
        summary: root.summary
        expanded: root.expanded
        onClicked: {
            root.expanded = !root.expanded
            Platform.setSetting("fold." + root.storageKey, root.expanded ? "1" : "0")
        }
    }
    Collapse {
        width: parent.width
        open: root.expanded
        Column { id: inner; width: parent.width; bottomPadding: root.bottomGap }
    }
}
