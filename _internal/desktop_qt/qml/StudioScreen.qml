import QtQuick
import ABook

// Studio: chỗ giữ cho D3 (bảng dự án gọn: tên · trạng thái · tiến độ · cập nhật, DESIGN.md mục 7).
Item {
    id: root
    readonly property real bodyWidth: Math.min(width - 2 * Theme.margin, 800)
    ScreenHeader {
        x: (parent.width - root.bodyWidth) / 2
        width: root.bodyWidth
        title: "Studio"
    }
    Text {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 40
        width: root.bodyWidth
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        text: "Studio chưa mở trong bản này."
        color: Theme.text2
        font.pixelSize: Theme.sizeBodySmall
    }
}
