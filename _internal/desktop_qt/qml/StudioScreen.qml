import QtQuick
import ABook

// Studio: chỗ giữ cho D3 (bảng dự án gọn: tên · trạng thái · tiến độ · cập nhật, DESIGN.md mục 7).
Item {
    ScreenHeader {
        x: Theme.margin
        width: parent.width - 2 * Theme.margin
        title: "Studio"
    }
    Text {
        anchors.centerIn: parent
        anchors.verticalCenterOffset: 40
        text: "Studio chưa mở trong bản này."
        color: Theme.text2
        font.pixelSize: Theme.sizeBodySmall
    }
}
