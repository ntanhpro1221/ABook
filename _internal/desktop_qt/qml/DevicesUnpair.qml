import QtQuick
import ABook

// Hộp hỏi khi thôi ghép một máy còn dữ liệu sẽ mất (UnpairDialog của shared/UnpairDialog.tsx, chữ từ unpairCopy của shared/unpair.ts):
// nói mất gì, giữ gì; ba lựa chọn xếp dọc - "Gửi trước rồi thôi ghép" (nút chính khi máy kia trả lời), "Vẫn thôi ghép, bỏ thay đổi"
// (nguy hiểm), "Huỷ" (nút chính khi máy kia tắt - gửi lúc này sẽ hỏng). Đang chạy thì không đóng được; lỗi lần gửi hiện ngay trong hộp,
// hộp ở nguyên để chọn lại. Là một lớp của Back (Modal).
Modal {
    id: root
    property var copy: null             // kết quả unpairCopy; null khi không hỏi
    property string busyChoice: ""      // "send" | "discard" | ""
    property string error: ""
    // Giữ lời hỏi cuối để chữ không trống trong lúc hộp khép lại
    property var shownCopy: null
    onCopyChanged: if (copy) shownCopy = copy
    signal choose(string choice)
    title: shownCopy ? shownCopy.title : ""
    dismissable: busyChoice === ""
    keepOpen: function() { return root.busyChoice !== "" }

    Column {
        width: parent.width
        spacing: 8
        Repeater {
            model: root.shownCopy ? root.shownCopy.lines : []
            Text {
                required property string modelData
                width: parent.width
                text: modelData
                color: Theme.text2
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
                lineHeight: 1.25
            }
        }
        Collapse {
            width: parent.width
            open: root.error !== ""
            Text {
                objectName: "unpairError"
                width: parent.width
                text: root.error
                color: Theme.danger
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: Theme.sizeBodySmall
                lineHeight: 1.25
            }
        }
    }
    Column {
        width: parent.width
        topPadding: 4
        spacing: 8
        Button {
            objectName: "unpairSend"
            width: parent.width
            visible: Boolean(root.shownCopy && root.shownCopy.send)
            kind: root.shownCopy && root.shownCopy.sendPrimary ? "primary" : "ghost"
            text: root.shownCopy && root.shownCopy.send ? root.shownCopy.send : ""
            busy: root.busyChoice === "send"
            enabled: root.busyChoice === "" || busy
            onActivated: root.choose("send")
        }
        Button {
            objectName: "unpairDiscard"
            width: parent.width
            kind: "danger"
            text: root.shownCopy ? root.shownCopy.discard : ""
            busy: root.busyChoice === "discard"
            enabled: root.busyChoice === "" || busy
            onActivated: root.choose("discard")
        }
        // Máy kia tắt: nút chính là Huỷ (gửi lúc này sẽ hỏng), không phải "Gửi trước".
        Button {
            objectName: "unpairCancel"
            width: parent.width
            kind: root.shownCopy && root.shownCopy.send && !root.shownCopy.sendPrimary ? "primary" : "ghost"
            text: root.shownCopy ? root.shownCopy.cancel : ""
            enabled: root.busyChoice === ""
            onClicked: root.dismiss()
        }
    }
}
