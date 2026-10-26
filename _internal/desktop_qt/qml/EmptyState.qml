import QtQuick
import ABook

// Khối "chưa có gì / chưa vào được" giữa màn (EmptyState của shared/ui.tsx): ô icon 56 bo bìa nền nhấn nhạt, tiêu đề 16 đậm, lời mực phụ tối đa
// 448 px, nút việc bên dưới (đặt thẳng vào trong). Đổi chữ lúc đang hiện thì mờ qua tại chỗ, không đổi cứng.
Column {
    id: root
    property string icon: ""
    property string title: ""
    property string text: ""
    default property alias actions: actionRow.data
    spacing: 0
    topPadding: 56
    bottomPadding: 56

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 56
        height: 56
        radius: Theme.radiusCover
        color: Theme.accentSoft
        Icon { anchors.centerIn: parent; name: root.icon; size: 28; color: Theme.accentText }
    }
    Item { width: 1; height: 16 }
    Text {
        objectName: "emptyTitle"
        width: root.width
        horizontalAlignment: Text.AlignHCenter
        text: root.title
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: 16
        font.weight: Theme.weightBold
    }
    Item { width: 1; height: root.text !== "" ? 6 : 0 }
    Text {
        objectName: "emptyText"
        visible: root.text !== ""
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(root.width, 448)
        horizontalAlignment: Text.AlignHCenter
        text: root.text
        color: Theme.text2
        wrapMode: Text.Wrap
        lineHeight: 1.625
        font.pixelSize: Theme.sizeBodySmall
    }
    Item { width: 1; height: actionRow.children.length ? 20 : 0 }
    Row {
        id: actionRow
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: 8
    }
}
