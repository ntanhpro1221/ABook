import QtQuick
import ABook
import "TextWrap.js" as TextWrap

// Khối "chưa có gì / chưa vào được" giữa màn (EmptyState của shared/ui.tsx): ô icon 56 bo bìa nền nhấn nhạt, tiêu đề 16 đậm, lời mực phụ tối đa
// 448 px, nút việc bên dưới (đặt thẳng vào trong). Đổi chữ lúc đang hiện thì mờ qua tại chỗ, không đổi cứng.
// `fillHeight` > 0: trạng thái là cả màn (DESIGN §2, web `fill`) - khối đứng giữa vùng cao chừng ấy tính từ đỉnh của nó, không dính góc
// trên để trống quá nửa màn bên dưới (design_lint R10).
Column {
    id: root
    property string icon: ""
    property string title: ""
    property string text: ""
    property real fillHeight: 0
    default property alias actions: actionRow.data
    readonly property real blockHeight: iconTile.height + iconGap.height + titleText.height + textGap.height + bodyText.height
                                        + actionGap.height + actionRow.height
    spacing: 0
    topPadding: fillHeight > 0 ? Math.max(Theme.s24, Math.round((fillHeight - blockHeight) / 2)) : 64
    bottomPadding: fillHeight > 0 ? Math.max(Theme.s24, fillHeight - blockHeight - topPadding) : 64

    Rectangle {
        id: iconTile
        anchors.horizontalCenter: parent.horizontalCenter
        width: 56
        height: 56
        radius: Theme.radiusCover
        color: Theme.accentSoft
        Icon { anchors.centerIn: parent; name: root.icon; size: 28; color: Theme.accentText }
    }
    Item { id: iconGap; width: 1; height: 16 }
    Text {
        id: titleText
        objectName: "emptyTitle"
        width: root.width
        horizontalAlignment: Text.AlignHCenter
        text: TextWrap.keepDots(root.title)
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: 16
        font.weight: Theme.weightBold
    }
    // Khe theo thang (DESIGN 5.5): tiêu đề -> lời 8 (web mt-2), lời -> nút 24 (web mt-6).
    Item { id: textGap; width: 1; height: root.text !== "" ? Theme.s8 : 0 }
    Text {
        id: bodyText
        objectName: "emptyText"
        Reveal { shown: root.text !== "" }
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(root.width, 448)
        horizontalAlignment: Text.AlignHCenter
        text: root.text
        color: Theme.text2
        wrapMode: Text.Wrap
        lineHeight: 1.625
        font.pixelSize: Theme.sizeBodySmall
    }
    Item { id: actionGap; width: 1; height: actionRow.children.length ? Theme.s24 : 0 }
    Row {
        id: actionRow
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 8
    }
}
