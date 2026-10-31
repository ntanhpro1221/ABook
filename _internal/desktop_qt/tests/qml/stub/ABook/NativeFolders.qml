import QtQuick

// Hộp chọn thư mục giả cho test (NativeFolders thật mở hộp của hệ điều hành, không bao giờ được mở trong test): ghi lại lời hỏi vào DesktopApi.folders rồi
// trả lời ngay bằng DesktopApi.folderAnswer ("" = đóng hộp mà không chọn).
QtObject {
    id: root
    signal picked(string path)
    signal cancelled()
    function choose(heading, start) {
        DesktopApi.folders = DesktopApi.folders.concat([{title: heading, start: start || ""}])
        if (DesktopApi.folderAnswer !== "") picked(DesktopApi.folderAnswer)
        else cancelled()
    }
}
