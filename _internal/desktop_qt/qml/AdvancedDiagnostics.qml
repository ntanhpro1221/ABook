import "UiStrings.js" as S
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
        folders.choose(S.s_chon_noi_luu_goi_nhat_ky_17fab271, "")
    }
    function save(target) {
        Api.call("POST", "/api/diagnostics/save", target ? {target: target} : {}, function(data, error) {
            root.busy = false
            if (error) Api.notice = Music.toast(S.s_chua_luu_duoc_goi_nhat_ky_ec27bfaf, error)
            else Api.notice = data.folder ? S.s_da_luu_goi_nhat_ky_trong_5982b4bb + data.folder : S.s_da_luu_goi_nhat_ky_82b1b295
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
            text: S.s_xem_lai_truoc_khi_gui_ban_tu_gui_di_755dd05a
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: 13
        }
        Button {
            id: send
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            text: S.s_gui_nhat_ky_2e35a4f8; icon: "save"; kind: "ghost"; size: "sm"
            busy: root.busy
            onActivated: root.send()
        }
    }
    MoreInfo {
        width: parent.width
        HintText { width: parent.width; text: S.s_gom_thong_tin_may_va_nhat_ky_gan_nhat_tu_c_888894b2 }
    }
}
