import QtQuick
import ABook
Column {
    id: root
    property var sync: ({})
    property var computers: []
    property var found: []
    property var bluetooth: []
    property bool busy: false
    property bool confirmStudio: false
    property string revokeId: ""
    property string revokeKind: ""
    property var unsent: ({})
    property int now: Date.now() / 1000
    function load() {
        Api.call("GET", "/api/sync", null, function(data, error) { if (!error) root.sync = data })
        Api.call("GET", "/api/computers", null, function(data, error) { if (!error) root.computers = data.computers || [] })
        Api.call("GET", "/api/computers/bluetooth", null, function(data, error) { if (!error) root.bluetooth = data.devices || [] })
    }
    function change(method, path, body, computer) {
        busy = true
        Api.call(method, path, body, function(data, error) { root.busy = false; if (!error) { if (computer) { root.computers = data.computers || []; DesktopApi.refreshLibrary() } else root.sync = data } })
    }
    onVisibleChanged: if (visible) load()
    Timer { interval: root.sync.pairing ? 1500 : 10000; running: root.visible; repeat: true; onTriggered: root.load() }
    Timer { interval: 1000; running: root.visible && Boolean(root.sync.pairing); repeat: true; onTriggered: root.now = Date.now() / 1000 }
    SectionBlock {
        width: parent.width; title: "Máy này"
        SettingRow { width: parent.width; label: "Kết nối Wi-Fi"; hint: root.sync.enabled ? "Máy cùng mạng thấy máy này là “" + root.sync.name + "”." : root.sync.wanted ? root.sync.error || "Chưa mở được cổng đồng bộ." : "Đang tắt - máy khác không thấy máy này."; Switch { label: "Kết nối Wi-Fi"; checked: Boolean(root.sync.wanted); enabled: !root.busy; onToggled: value => root.change("POST", "/api/sync", {enabled: value}, false) } }
        SectionBlock {
            id: pair
            width: parent.width; visible: Boolean(root.sync.enabled); title: "Ghép thiết bị"; fold: "wip"; expanded: Boolean(root.sync.pairing)
            FormLabel { width: parent.width; visible: Boolean(root.sync.pairing); text: "Mã ghép thiết bị"; font.weight: Theme.weightMedium }
            FormLabel { width: parent.width; visible: Boolean(root.sync.pairing); text: "Trên máy kia: Cài đặt › Thiết bị → chọn " + (root.sync.name || "") + " → nhập mã."; color: Theme.text2 }
            FormLabel { width: parent.width; visible: Boolean(root.sync.pairing); text: root.sync.pairing?.code || ""; font.pixelSize: 34; font.letterSpacing: 5; color: Theme.accentText }
            FormLabel { width: parent.width; visible: Boolean(root.sync.pairing); readonly property int seconds: Math.max(0, Math.floor((root.sync.pairing?.expiresAt || 0) - root.now)); text: "Hết hạn sau " + Math.floor(seconds / 60) + ":" + String(seconds % 60).padStart(2,"0"); color: Theme.text2 }
            FormLabel { width: parent.width; visible: Boolean(root.sync.fingerprint); text: "Vân tay: " + (root.sync.fingerprint || ""); font.pixelSize: Theme.sizeCaption; color: Theme.text3 }
            FormLabel { width: parent.width; visible: Boolean(root.sync.pairingBlocked); text: "Mã bị khoá" }
            FormLabel { width: parent.width; visible: Boolean(root.sync.pairingBlocked); text: "Sai 5 lần; chỉ tạo mã mới khi bạn đang ghép thiết bị."; color: Theme.text2 }
            Button { kind: "text"; text: root.sync.pairing ? "Huỷ mã này" : root.sync.pairingBlocked ? "Tạo mã mới" : "Ghép thiết bị mới"; enabled: !root.busy; onClicked: root.change(root.sync.pairing ? "DELETE" : "POST", "/api/sync/pairing", null, false) }
        }
        SectionBlock {
            width: parent.width; visible: Boolean(root.sync.enabled); title: "Quyền điều khiển"; fold: "wip"
            SettingRow { width: parent.width; label: "Điều khiển từ xa"; hint: "Tắt: thiết bị đã ghép chỉ tải và nghe sách."; Switch { label: "Điều khiển từ xa"; checked: Boolean(root.sync.remoteStudio); enabled: !root.busy; onToggled: value => { if (value) root.confirmStudio = true; else root.change("POST", "/api/sync/studio", {enabled: false}, false) } } }
            Column { width: parent.width; visible: root.confirmStudio; spacing: 8
                FormLabel { width: parent.width; text: "Bật Studio từ xa?" }
                FormLabel { width: parent.width; text: "Bật quyền riêng cho từng thiết bị để mở Studio trong trình duyệt."; color: Theme.text2 }
                Flow { width: parent.width; spacing: 8
                    Button { text: "Để sau"; kind: "text"; onClicked: root.confirmStudio = false }
                    Button { text: "Cho phép"; onClicked: { root.confirmStudio = false; root.change("POST", "/api/sync/studio", {enabled: true}, false) } }
                }
            }
        }
        SectionBlock {
            width: parent.width; visible: Boolean(root.sync.enabled); title: "Kết nối"; fold: "wip"
            FormLabel { width: parent.width; text: (root.sync.addresses || []).map(a => a + ":" + root.sync.port).join(" hoặc "); color: Theme.text2 }
            FormLabel { width: parent.width; text: root.sync.bluetooth?.running ? "Bluetooth: điện thoại đã ghép nối được cả khi khác Wi-Fi." : root.sync.bluetooth?.error || ""; color: Theme.text2; visible: text !== "" }
            FormLabel { width: parent.width; text: "Ngoài nhà: nghe sách đã tải, hoặc nối mạng riêng ảo để nghe thẳng."; color: Theme.text2 }
        }
    }
    SectionBlock {
        width: parent.width; title: "Máy đã ghép"; visible: Boolean(root.sync.enabled)
        FormLabel { width: parent.width; visible: !(root.sync.devices || []).length; text: "Chưa có thiết bị nào đã ghép."; color: Theme.text2 }
        Repeater {
            model: root.sync.devices || []
            SectionBlock {
                required property var modelData
                width: parent.width; title: modelData.name; fold: "wip"
                FormField { id: nameField; width: parent.width; label: "Tên thiết bị"; text: modelData.name }
                Button { text: "Lưu tên"; kind: "text"; enabled: !root.busy && nameField.text.trim() !== "" && nameField.text !== modelData.name; onClicked: root.change("POST", "/api/sync/devices/" + modelData.id + "/name", {name: nameField.text}, false) }
                SettingRow { width: parent.width; label: "Điều khiển từ xa"; visible: Boolean(root.sync.remoteStudio); Switch { label: "Điều khiển từ xa"; checked: Boolean(modelData.studio); enabled: !root.busy; onToggled: value => root.change("POST", "/api/sync/devices/" + modelData.id + "/studio", {enabled: value}, false) } }
                Button { text: "Thôi ghép"; kind: "text"; icon: "unplug"; onClicked: { root.revokeId = modelData.id; root.revokeKind = "device" } }
                Flow { width: parent.width; visible: root.revokeKind === "device" && root.revokeId === modelData.id; spacing: 8
                    Button { text: "Thôi ghép"; enabled: !root.busy; onClicked: { root.change("DELETE", "/api/sync/devices/" + modelData.id, null, false); root.revokeId = "" } }
                    Button { text: "Giữ lại"; kind: "text"; onClicked: root.revokeId = "" }
                }
            }
        }
    }
    SectionBlock {
        width: parent.width; title: "Máy tính khác"
        Repeater {
            model: root.computers
            SectionBlock {
                required property var modelData
                width: parent.width; title: modelData.name; fold: "wip"
                FormLabel { width: parent.width; text: modelData.error || modelData.host + ":" + modelData.port; color: modelData.error ? Theme.danger : Theme.text2 }
                FormLabel { width: parent.width; text: "Vân tay " + (modelData.fingerprint || ""); visible: Boolean(modelData.fingerprint); color: Theme.text3 }
                Button { text: "Hỏi lại"; kind: "text"; icon: "refresh-cw"; enabled: !root.busy; onClicked: root.change("POST", "/api/computers/refresh", null, true) }
                Button { text: "Thôi chờ"; kind: "text"; visible: Boolean(modelData.waking); enabled: !root.busy; onClicked: root.change("POST", "/api/computers/" + modelData.id + "/stop-waiting", null, true) }
                Button { text: "Thôi ghép"; kind: "text"; icon: "unplug"; onClicked: { root.revokeKind = "computer"; root.revokeId = modelData.id; Api.call("GET", "/api/computers/" + modelData.id + "/unsent", null, function(data, error) { if (!error) root.unsent = data }) } }
                Column { width: parent.width; visible: root.revokeKind === "computer" && root.revokeId === modelData.id
                    FormLabel { width: parent.width; text: "Thôi ghép"; color: Theme.text2 }
                    Button { text: "Thôi ghép"; enabled: !root.busy; onClicked: { root.change("DELETE", "/api/computers/" + modelData.id, null, true); root.revokeId = "" } }
                    Button { text: "Giữ lại"; kind: "text"; onClicked: root.revokeId = "" }
                }
            }
        }
        SectionBlock {
            width: parent.width; title: "Ghép máy"; fold: "wip"
            Button { text: "Tìm máy trong mạng"; icon: "radar"; kind: "text"; onClicked: Api.call("GET", "/api/computers/discover", null, function(data, error) { if (!error) root.found = data.found || [] }) }
            Repeater { model: root.found; SettingRow { required property var modelData; width: parent.width; label: modelData.name; hint: modelData.host + ":" + modelData.port; Button { text: modelData.paired ? "Đã ghép" : "Chọn"; kind: "text"; enabled: !modelData.paired; onClicked: address.text = modelData.host + ":" + modelData.port } } }
            FormLabel { text: "Địa chỉ máy kia" }
            FormField { id: address; width: parent.width; label: "Địa chỉ máy kia"; placeholderText: "192.168.1.20 hoặc địa chỉ Bluetooth" }
            FormLabel { text: "Mã 6 số" }
            FormField { id: code; width: 140; label: "Mã 6 số"; placeholderText: "123456" }
            Button { text: "Kết nối"; kind: "text"; enabled: !root.busy && address.text.trim() !== "" && /^\d{6}$/.test(code.text); onClicked: root.change("POST", "/api/computers", {address: address.text, code: code.text}, true) }
        }
    }
}
