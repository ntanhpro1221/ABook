import QtQuick
import ABook

// Menu "…" của một người ở tab Nhân vật: Gộp vào người khác…, Đổi tên, Đổi giới tính (chỉ mục làm được; bảng nổi đo chỗ theo số hàng). Dùng chung cho trang sách
// và tab Nhân vật / "Duyệt trước khi thu" của Studio: chọn xong phát `picked(loại, người)` rồi nơi dùng mở hộp tương ứng (CastDialogs).
Popover {
    id: root
    objectName: "castMenu"
    property var caps: ({})
    property var person: null
    signal picked(string kind, var person)
    panelWidth: 240
    pad: 6
    function openFor(anchor, who) {
        person = who
        anchorItem = anchor
        show()
    }
    Column {
        width: parent.width
        readonly property var p: root.person || ({})
        readonly property bool canMerge: Boolean(root.caps.merge) && p.lines > 0
        readonly property bool canGender: Boolean(root.caps.gender) && Boolean(p.voice) && p.lines > 0
        height: Theme.buttonHeight * ((canMerge ? 1 : 0) + (root.caps.rename ? 1 : 0) + (canGender ? 1 : 0))
        MenuRow {
            objectName: "castMerge"
            visible: parent.canMerge
            width: parent.width; icon: "git-merge"; text: "Gộp vào người khác…"
            onClicked: { root.close(); root.picked("merge", parent.p) }
        }
        MenuRow {
            objectName: "castRename"
            visible: Boolean(root.caps.rename)
            width: parent.width; icon: "text-cursor-input"; text: "Đổi tên"
            onClicked: { root.close(); root.picked("rename", parent.p) }
        }
        MenuRow {
            objectName: "castGender"
            visible: parent.canGender
            width: parent.width; icon: "user-round"; text: "Đổi giới tính"
            onClicked: { root.close(); root.picked("gender", parent.p) }
        }
    }
}
