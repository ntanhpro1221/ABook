import QtQuick
import ABook

// Hộp chọn file giả của test: không mở cửa sổ hệ điều hành nào, chỉ ghi lại đã được gọi gì (DesktopApi.pickers).
Item {
    id: root
    property bool append: false
    signal picked(var paths, bool append)
    function chooseFiles(add) { append = add; DesktopApi.pickers = DesktopApi.pickers.concat([{kind: "files", add: add}]) }
    function chooseFolder() { append = false; DesktopApi.pickers = DesktopApi.pickers.concat([{kind: "folder", add: false}]) }
}
