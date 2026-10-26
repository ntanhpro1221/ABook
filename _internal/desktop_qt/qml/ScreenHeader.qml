import QtQuick
import ABook

// Đầu màn (DESIGN.md mục 6): đệm trên 32, hàng tiêu đề cao 40, tiêu đề 32, dòng phụ ngay dưới, nút bên phải căn giữa hàng.
// Màn con có nút ← (Back) thẳng mép nội dung; chân chữ tiêu đề không đổi giữa màn gốc và màn con.
Item {
    id: root
    property string title: ""
    property string subtitle: ""
    property bool showBack: false
    default property alias trailing: trailingRow.data

    implicitHeight: Theme.s32 + titleText.height + (subtitle !== "" ? 24 : 0)

    IconButton {
        id: back
        visible: root.showBack
        icon: "arrow-left"
        x: -10                      // nét mũi tên (lùi 10 trong vùng bấm 40) thẳng mép nội dung
        y: Theme.s32
        tip: "Quay lại  (Esc)"
        onClicked: Nav.back()
    }
    Text {
        id: titleText
        x: root.showBack ? back.width - 10 + Theme.s8 : 0
        y: Theme.s32
        height: Math.max(Theme.headerRow, implicitHeight)     // tên dài xuống dòng, không cắt
        verticalAlignment: Text.AlignVCenter
        width: parent.width - x - trailingRow.width - Theme.s16
        text: root.title
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeTitleDesktop
        font.weight: Theme.weightBold
    }
    Text {
        visible: root.subtitle !== ""
        x: titleText.x
        y: Theme.s32 + titleText.height + 2
        text: root.subtitle
        color: Theme.text2
        font.pixelSize: Theme.sizeBodySmall
    }
    Row {
        id: trailingRow
        anchors.right: parent.right
        y: Theme.s32
        height: Theme.headerRow
        spacing: Theme.s8
    }
}
