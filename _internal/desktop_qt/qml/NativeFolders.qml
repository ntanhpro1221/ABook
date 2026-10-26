import QtQuick
import QtQuick.Dialogs
import ABook
FolderDialog {
    id: root
    property string purpose: ""
    function choose(why) { purpose = why; title = why === "library" ? "Chọn thư mục thư viện" : "Chọn nơi lưu gói nhật ký"; open() }
    onAccepted: {
        const path = DesktopApi.localPath(selectedFolder)
        if (purpose === "library") Api.update({libraryRoot: path}, function(data, error) { if (!error) { Api.notice = "Đã đổi thư mục thư viện"; DesktopApi.refreshLibrary() } })
        else Api.call("POST", "/api/diagnostics/save", {target: path}, function(data, error) { if (!error) Api.notice = data.folder ? "Đã lưu gói nhật ký trong " + data.folder : "Đã lưu gói nhật ký" })
    }
}
