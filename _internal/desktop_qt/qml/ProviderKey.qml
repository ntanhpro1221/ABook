import QtQuick
import QtQuick.Controls.Basic as C
import ABook
SectionBlock {
    id: root
    property var info: ({limits: {}})
    property bool busy: false
    property string result: ""
    title: info.name || ""
    fold: true
    expanded: Boolean(info.hasKey)
    signal changed()
    function act(action) {
        busy = true
        const path = "/api/readaloud/online/" + info.id
        function finish(data, error) {
            root.busy = false
            if (error) { root.result = error; return }
            secret.text = ""
            root.result = action === "check" ? (data.ok ? "Dùng được · " + (data.voices ?? data.provider.voices) + " giọng tiếng Việt" : (data.message || "Khóa chưa dùng được.")) : action === "save" ? "Đã lưu khoá. Bấm “Kiểm tra” để thử." : ""
            root.changed()
        }
        function check() { Api.call("POST", path + "/check", {}, finish) }
        if (action === "remove") Api.call("DELETE", path, null, finish)
        else if (action === "check" && !secret.text.trim() && region.text === (info.region || "")) check()
        else Api.call("PUT", path, {key: secret.text.trim(), region: region.text.trim()}, function(data, error) { if (action === "check" && !error) check(); else finish(data, error) })
    }
    FormLabel { width: parent.width; text: (root.info.limits?.free || "") + (root.info.limits?.timings === "exact" ? ". Tô đúng từng chữ đang đọc." : ". Tô từng chữ đang đọc theo ước lượng."); color: Theme.text2 }
    SectionBlock {
        width: parent.width; title: "Nhận khoá"; fold: true
        FormLabel { width: parent.width; color: Theme.text2; text: ({azure: "Azure: tạo Speech (F0 miễn phí) › Keys and Endpoint. Chép Key 1 và Location/Region (ví dụ southeastasia).", google: "Google Cloud: bật Cloud Text-to-Speech API. Vào APIs & Services › Credentials › Create credentials › API key.", fpt: "Trên console.fpt.ai: đăng nhập, mở mục “Text to Speech” (Chuyển văn bản thành giọng nói), chép “API key” (khoá API).", viettel: "Trên viettelai.vn: đăng nhập, mở Tài khoản › Token, chép token."})[root.info.id] || "" }
    }
    C.TextField {
        id: secret
        width: parent.width; height: 40
        Accessible.name: "Khóa " + root.title
        echoMode: TextInput.Password
        color: Theme.text; placeholderTextColor: Theme.text3
        font.pixelSize: Theme.sizeBodySmall
        placeholderText: root.info.hasKey ? "Đã lưu " + root.info.masked + " - dán khóa mới để thay" : "Dán khóa của bạn"
        background: Rectangle { color: Theme.bg; radius: Theme.radiusControl; border.width: secret.activeFocus ? 2 : 1; border.color: secret.activeFocus ? Theme.focus : Theme.line }
    }
    FormField { id: region; width: parent.width; label: "Vùng " + root.title; visible: Boolean(root.info.limits?.region); placeholderText: "Vùng, ví dụ southeastasia"; text: root.info.region || "" }
    Flow {
        width: parent.width; spacing: 8
        Button { text: "Lưu"; kind: "text"; enabled: !root.busy && (secret.text.trim() !== "" || region.text !== (root.info.region || "")); onClicked: root.act("save") }
        Button { text: "Kiểm tra"; icon: "key-round"; enabled: !root.busy && (root.info.hasKey || secret.text.trim() !== ""); onClicked: root.act("check") }
        Button { text: "Xóa khóa"; icon: "trash-2"; kind: "text"; visible: Boolean(root.info.hasKey); enabled: !root.busy; onClicked: root.act("remove") }
    }
    FormLabel { width: parent.width; text: root.result; visible: text !== ""; color: Theme.text2 }
}
