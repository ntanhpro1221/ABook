import QtQuick
import ABook

// Ô nhập một dòng gọn của thẻ việc / dòng cách đọc (h-8 của bản web: cao 32). Chữ dài xuống dòng, ô cao thêm - không cắt.
FormField {
    topPadding: 6
    bottomPadding: 6
    implicitHeight: Math.max(32, contentHeight + 12)
}
