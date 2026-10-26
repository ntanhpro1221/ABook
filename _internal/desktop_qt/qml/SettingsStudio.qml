import QtQuick
import ABook
Column {
    id: root
    property var status: ({})
    property var voices: []
    property var readings: []
    property bool armed: false
    function load() {
        if (!Api.info.studio) return
        Api.call("GET", "/api/studio/setup", null, function(data, error) { if (!error) root.status = data })
        Api.call("GET", "/api/voices", null, function(data, error) { if (!error) root.voices = data })
        Api.call("GET", "/api/readings", null, function(data, error) { if (!error) root.readings = data.entries || [] })
    }
    onVisibleChanged: if (visible) load()
    SectionBlock {
        width: parent.width; title: "Máy này"
        SettingRow { width: parent.width; label: "Studio trên máy này"; hint: root.status.installed ? "Đã cài" + (root.status.gpu ? " · " + root.status.gpu.name : "") + "\n" + (root.status.root || "") : root.status.running ? "Đang cài." : "Chưa cài."; Button { text: root.status.installed ? (root.armed ? "Xác nhận gỡ" : "Gỡ Studio") : "Cài Studio"; kind: "text"; icon: root.status.installed ? "trash-2" : "download"; onClicked: { if (root.status.installed && !root.armed) { root.armed = true; return } Api.call(root.status.installed ? "DELETE" : "POST", "/api/studio/setup", {}, function(data, error) { if (!error) { root.armed = false; root.status = data } }) } } }
        FormLabel { width: parent.width; visible: root.armed; text: "Xoá runtime/model (15–20 GB), giữ sách và hồ sơ; cuốn đang làm phải làm lại sau khi cài."; color: Theme.text2 }
        SettingRow { width: parent.width; label: "Tạm dừng dùng pin"; hint: "Cắm sạc lại thì tự làm tiếp đúng chỗ."; Switch { label: "Tạm dừng dùng pin"; checked: Api.preferences.pauseOnBattery !== false; onToggled: value => Api.update({pauseOnBattery: value}) } }
    }
    FormLabel { width: parent.width; visible: !root.status.installed; text: "Tuỳ chọn ở trang này dùng khi đã cài Studio."; color: Theme.text2 }
    SectionBlock {
        width: parent.width; title: "Sách mới"; fold: true
        SettingChoices { width: parent.width; label: "Giọng kể"; value: Api.preferences.newBookNarrator || ""; options: [{value: "", label: "Máy đề xuất"}].concat(root.voices.map(v => ({value: v.name, label: v.name + " · " + v.gender + ", miền " + v.region}))); onPicked: value => Api.update({newBookNarrator: value}) }
        SettingChoices { width: parent.width; label: "Chất lượng"; value: Api.preferences.newBookProfile || "high_quality"; options: [{value: "high_quality", label: "Chất lượng cao"}, {value: "balanced", label: "Cân bằng"}]; onPicked: value => Api.update({newBookProfile: value}) }
        FormLabel { width: parent.width; text: "Mẫu sách mới"; font.weight: Theme.weightMedium }
        FormLabel { width: parent.width; text: "Ở Tạo sách, chọn “Lưu thành mẫu…” để dùng lại."; color: Theme.text2 }
        FormLabel { width: parent.width; visible: !(Api.preferences.bookTemplates || []).length; text: "Chưa có mẫu nào."; color: Theme.text3 }
        Repeater { model: Api.preferences.bookTemplates || []; SettingRow { required property var modelData; width: parent.width; label: modelData.name; Button { text: "Xoá"; kind: "text"; onClicked: Api.call("POST", "/api/book-templates", {op: "delete", name: modelData.name}, function(data, error) { if (!error) Api.preferences = data }) } } }
    }
    SectionBlock {
        width: parent.width; title: "Cách đọc chung"; fold: true
        FormLabel { width: parent.width; text: "Sửa cách đọc một tên một lần, sách mới tự dùng."; color: Theme.text2 }
        Repeater { model: root.readings; SettingRow { required property var modelData; width: parent.width; label: modelData.surface + " → “" + modelData.spokenForm + "”"; Button { text: "Bỏ"; kind: "text"; onClicked: Api.call("POST", "/api/readings", {surface: modelData.surface, remove: true}, function(data, error) { if (!error) root.load() }) } } }
        FormField { id: surface; width: parent.width; label: "Tên trong sách"; placeholderText: "Tên trong sách" }
        FormField { id: spoken; width: parent.width; label: "Đọc là"; placeholderText: "Đọc là" }
        Button { text: "Thêm"; kind: "text"; enabled: surface.text.trim() !== "" && spoken.text.trim() !== ""; onClicked: Api.call("POST", "/api/readings", {surface: surface.text, spokenForm: spoken.text}, function(data, error) { if (!error) { surface.text = ""; spoken.text = ""; root.load() } }) }
    }
}
