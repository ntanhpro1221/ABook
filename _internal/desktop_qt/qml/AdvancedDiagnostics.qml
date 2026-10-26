import QtQuick
import ABook
import "MyMusicText.js" as Music

// Nội dung khối "Chẩn đoán" (OwnDiagnostics của desktop/OwnDiagnostics.tsx): "Gửi nhật ký" của chính máy tính - gói .zip (thông tin máy, phiên bản, đuôi
// nhật ký của app) ghi vào thư mục bạn chọn để bạn tự gửi cho người sửa lỗi. App không gửi gì đi (POST /api/diagnostics/save).
Column {
    id: root
    objectName: "advancedDiagnostics"
    property bool busy: false
    // Bấm "Gửi nhật ký": hộp chọn thư mục của hệ điều hành rồi ghi gói vào đó (đóng hộp mà không chọn thì thôi)
    function send() {
        if (busy) return
        busy = true
        folders.choose("Chọn nơi lưu gói nhật ký", "")
    }
    function save(target) {
        Api.call("POST", "/api/diagnostics/save", target ? {target: target} : {}, function(data, error) {
            root.busy = false
            if (error) Api.notice = Music.toast("Chưa lưu được gói nhật ký", error)
            else Api.notice = data.folder ? "Đã lưu gói nhật ký trong " + data.folder : "Đã lưu gói nhật ký"
        })
    }
    NativeFolders { id: folders; onPicked: path => root.save(path); onCancelled: root.busy = false }
    Item {
        width: parent.width
        height: Math.max(hint.implicitHeight, send.height)
        Text {
            id: hint
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - send.width - 24
            text: "Xem lại trước khi gửi; bạn tự gửi đi."
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: 13
        }
        Button {
            id: send
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: "Gửi nhật ký"; icon: "save"; kind: "ghost"; size: "sm"
            busy: root.busy
            onActivated: root.send()
        }
    }
    MoreInfo {
        width: parent.width
        HintText { width: parent.width; text: "Gồm thông tin máy và nhật ký gần nhất; tự che khoá, mã ghép, đường dẫn và IP nhận ra được." }
    }
}
