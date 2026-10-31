import QtQuick
import ABook

// Hộp chọn ảnh bìa giả của test: không mở cửa sổ hệ điều hành, chỉ đếm số lần được gọi (DesktopApi.pickers).
Item {
    id: root
    signal picked(url file)
    function choose() { DesktopApi.pickers = DesktopApi.pickers.concat([{kind: "cover"}]) }
}
