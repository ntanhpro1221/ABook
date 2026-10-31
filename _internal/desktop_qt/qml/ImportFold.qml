import QtQuick
import ABook

// Khối gấp / mở trong hộp Thêm sách (Fold của shared/Collapse.tsx): đầu là hàng DisclosureRow cỡ tiêu đề mục (tên, một dòng tóm tắt, mũi tên xoay), thân là Collapse.
// Mặc định gập; mở rồi thì lần sau vẫn mở (Platform.setting "fold.addbook.<khoá>", như localStorage abook.fold.* của web). Nội dung đặt thẳng vào trong.
Column {
    id: root
    property string storageKey: ""
    property string title: ""
    property string summary: ""
    property string prefix: "fold.addbook."      // chỗ nhớ (Platform.setting): trình tạo sách dùng "fold.new-project."
    property bool defaultOpen: false             // mở sẵn khi chưa từng gập / mở (defaultOpen của Fold)
    property bool expanded: Platform.setting(prefix + storageKey, defaultOpen ? "1" : "0") === "1"
    default property alias content: body.content

    DisclosureRow {
        width: parent.width
        section: true
        title: root.title
        summary: root.summary
        expanded: root.expanded
        onClicked: {
            root.expanded = !root.expanded
            Platform.setSetting(root.prefix + root.storageKey, root.expanded ? "1" : "0")
        }
    }
    Collapse {
        id: body
        width: parent.width
        open: root.expanded
        spacing: 0
    }
}
