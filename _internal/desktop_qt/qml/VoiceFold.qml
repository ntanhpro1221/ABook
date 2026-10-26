import QtQuick
import ABook

// Khối gấp / mở trong một màn dài (Fold của shared/Collapse.tsx): đầu là DisclosureRow kiểu mục (tên + một dòng tóm tắt + mũi tên xoay), thân là
// Collapse đệm dưới 12 (bodyClassName "pb-3"), mặc định gập, nhớ gấp / mở theo từng khối (Platform "fold.<khoá>" như localStorage abook.fold.<khoá>).
Column {
    id: root
    property string storageKey: ""
    property string title: ""
    property string summary: ""
    property bool defaultOpen: false
    property real bottomGap: 12             // bodyClassName pb-3
    property bool expanded: Platform.setting("fold." + storageKey, defaultOpen ? "1" : "0") === "1"
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
