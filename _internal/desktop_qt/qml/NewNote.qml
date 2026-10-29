import QtQuick
import ABook

// Khối ghi chú / gợi ý của trình tạo sách (mt-4 flex gap-3 py-4 text-sm của bản web): biểu tượng 16 ở cột trái, nội dung ở cột phải (đặt thẳng vào trong,
// thường vài Prose và hàng nút). Không nền, không viền; hẹp thì nội dung xuống dòng.
Item {
    id: root
    property string icon: "info"
    property color tone: Theme.text2
    property int gap: 16                     // khoảng cách phía trên (mt-4)
    property int pad: 16                     // đệm trên / dưới (py-4)
    default property alias content: body.data
    implicitHeight: gap + pad + body.height + pad
    height: implicitHeight
    Icon { x: 0; y: root.gap + root.pad + 2; name: root.icon; size: 16; color: root.tone }
    Column {
        id: body
        x: 28
        y: root.gap + root.pad
        width: root.width - 28
        spacing: 4
    }
}
