import QtQuick
import ABook

// Một mục của hộp "Sửa sách" (Section / FoldedSection của EditBook.tsx): vạch trên + đệm 16 (mục gập: đệm 8), tên mục 18/500 trong hàng cao 56,
// lời nhắc 12 mực phụ dưới tên, nội dung cách tên 8 khi không có lời nhắc. `fold` (khoá nhớ): mục ít dùng gập sau tên bấm được, mở rồi lần
// sau vẫn mở. `shown`: mục có điều kiện hiện / ẩn bằng Collapse (chiều cao chạy theo nội dung), không bật tắt cứng. `first`: mục đầu không vạch.
// Khoảng cách 16 giữa các mục (space-y-4) nằm TRONG mục, nên mục đang ẩn không để lại khe trống.
Item {
    id: root
    property string title: ""
    property string hint: ""
    property string fold: ""
    property bool shown: true
    property bool first: false
    property bool expanded: fold === "" || Platform.setting("fold." + fold, "0") === "1"
    default property alias rows: body.data
    implicitHeight: wrap.height
    height: implicitHeight
    Collapse {
        id: wrap
        width: parent.width
        open: root.shown
        Item { width: 1; height: root.first ? 0 : 16 }
        Rectangle { visible: !root.first; width: parent.width; height: root.first ? 0 : 1; color: Theme.line }
        Item { width: 1; height: root.first ? 0 : (root.fold !== "" ? 8 : 16) }
        Item {
            visible: root.fold === ""
            width: parent.width
            height: visible ? Math.max(56, heading.implicitHeight) : 0
            Text {
                id: heading
                width: parent.width
                anchors.verticalCenter: parent.verticalCenter
                text: root.title
                color: Theme.text
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeSection
                font.weight: Theme.weightMedium
            }
        }
        DisclosureRow {
            visible: root.fold !== ""
            width: parent.width
            height: visible ? implicitHeight : 0
            section: true
            title: root.title
            expanded: root.expanded
            onClicked: {
                root.expanded = !root.expanded
                Platform.setSetting("fold." + root.fold, root.expanded ? "1" : "0")
            }
        }
        Collapse {
            width: parent.width
            open: root.fold === "" || root.expanded
            Item {
                width: parent.width
                height: root.hint !== "" ? hintText.implicitHeight + 8 : 0
                visible: root.hint !== ""
                HintText { id: hintText; width: parent.width; text: root.hint }
            }
            Item { width: 1; height: root.hint === "" ? 8 : 0 }
            Column { id: body; width: parent.width; spacing: 12 }
        }
    }
}
