import QtQuick
import QtQuick.Dialogs
import ABook

// Hộp chọn thư mục của hệ điều hành (pickFolder của studio/data.ts). Máy tính Qt luôn có hộp này nên không cần hỏi `info.dialogs`.
// `choose(title, start)` mở hộp; chọn xong thì `picked(đường dẫn)`, đóng mà không chọn thì `cancelled()`.
FolderDialog {
    id: root
    signal picked(string path)
    signal cancelled()
    function choose(heading, start) {
        title = heading
        if (start) currentFolder = "file:///" + String(start).replace(/\\/g, "/").replace(/^\/+/, "")
        open()
    }
    onAccepted: picked(DesktopApi.localPath(selectedFolder))
    onRejected: cancelled()
}
