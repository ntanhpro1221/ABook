import QtQuick
import ABook

// Chữ giải thích nhỏ (text-xs / 12 px, mực phụ, dãn dòng vừa) dùng trong Cài đặt và hộp thoại; không bao giờ cắt, bẻ cả chuỗi liền.
Text {
    color: Theme.text2
    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
    font.pixelSize: Theme.sizeCaption
    lineHeight: 1.3
    textFormat: Text.PlainText
}
