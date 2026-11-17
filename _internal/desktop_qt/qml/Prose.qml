import QtQuick
import ABook

// Đoạn chữ của trình tạo sách: rộng bằng cột cha, xuống dòng (kể cả tên dài không có dấu cách), không bao giờ cắt. `strong`: đậm màu thường (câu đầu của
// khối); `small`: cỡ 12 (phụ chú, DESIGN 5.5); `tone`: màu (mặc định mực phụ).
Text {
    property bool strong: false
    property bool small: false
    property color tone: strong ? Theme.text : Theme.text2
    width: parent ? parent.width : implicitWidth
    color: tone
    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
    lineHeight: small ? 1.45 : 1.4
    font.pixelSize: small ? Theme.sizeCaption : Theme.sizeBodySmall
    font.weight: strong ? Theme.weightBold : Theme.weightRegular
}
