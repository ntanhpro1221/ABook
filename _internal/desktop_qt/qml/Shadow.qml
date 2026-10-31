import QtQuick
import ABook

// Bóng chung của mọi lớp nổi (DESIGN.md 5.5) - hộp thoại, popover, menu, danh sách chọn, thông báo dùng "float" (= shadow-float
// của web), nút tròn trên bìa dùng "card" (= shadow-card). Đặt làm con ĐẦU TIÊN của khung, trước nền: nó tự phủ ra ngoài khung.
// Gauss tính đúng cỡ ở ShadowProvider; đừng chồng Rectangle đen mờ để giả bóng (thành dải bậc thang - Lead soát 0.4.151).
Image {
    id: root
    property string kind: "float"
    property real radius: Theme.radiusCover
    readonly property Item target: parent
    // 3 sigma + độ dời - độ co của lớp xa nhất, như token ở ShadowProvider.
    readonly property int pad: kind === "card" ? (Theme.dark ? 41 : 32) : (Theme.dark ? 130 : 96)
    readonly property int frameWidth: target ? Math.round(target.width) : 0
    readonly property int frameHeight: target ? Math.round(target.height) : 0
    x: -pad
    y: -pad
    width: frameWidth + 2 * pad
    height: frameHeight + 2 * pad
    source: frameWidth > 0 && frameHeight > 0
            ? "image://shadow/%1/%2/%3/%4/%5/%6".arg(kind).arg(Theme.dark ? 1 : 0).arg(frameWidth).arg(frameHeight).arg(Math.round(radius)).arg(pad)
            : ""
    fillMode: Image.Stretch
    smooth: true
    asynchronous: false        // có bóng ngay khung đầu tiên lớp nổi hiện; mỗi cỡ chỉ tính một lần (bộ đệm ảnh của Qt)
}
