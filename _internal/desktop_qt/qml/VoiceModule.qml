import QtQuick
import ABook
Column {
    id: root
    property string module: "vieneu"
    property string title: ""
    property var status: ({})
    property var selected: []
    property string removing: ""
    property bool busy: false
    readonly property bool working: status.state === "downloading" || Boolean(status.benchmarking)
    signal changed()
    spacing: 8
    function load() { Api.call("GET", "/api/readaloud/" + module, null, function(data, error) { if (!error) { root.status = data; if (!root.selected.length) root.selected = (data.choices || []).filter(c => c.default).map(c => c.id) } }) }
    function act(suffix, body) { busy = true; Api.call("POST", "/api/readaloud/" + module + suffix, body, function(data, error) { root.busy = false; if (!error) { root.status = data; root.removing = ""; root.changed() } }) }
    onVisibleChanged: if (visible) load()
    Timer { interval: 1000; running: root.working; repeat: true; onTriggered: root.load() }
    FormLabel { width: parent.width; text: root.title; font.weight: Theme.weightMedium; font.pixelSize: Theme.sizeBody }
    FormLabel { width: parent.width; text: root.status.error || root.status.reason || ""; color: Theme.text2; visible: text !== "" }
    Repeater {
        model: root.status.choices || []
        Column {
            required property var modelData
            width: parent.width; spacing: 4
            SettingRow {
                width: parent.width; label: modelData.label + (modelData.recommended ? " · Khuyên dùng" : ""); hint: modelData.detail || ""
                Switch { label: modelData.label; checked: root.selected.includes(modelData.id); enabled: !root.busy && !root.working; onToggled: on => { const current = root.selected; root.selected = on ? [...new Set(current.concat([modelData.id], modelData.requires || []))] : current.filter(id => id !== modelData.id && !(root.status.choices.find(c => c.id === id)?.requires || []).includes(modelData.id)) } }
            }
            Button { text: root.removing === modelData.id ? "Gỡ giọng" : "Gỡ"; kind: "text"; visible: Boolean(modelData.removable); enabled: !root.busy && !root.working; onClicked: { if (root.removing === modelData.id) root.act("/remove", {choice: modelData.id}); else root.removing = modelData.id } }
            Button { text: "Giữ lại"; kind: "text"; visible: root.removing === modelData.id; onClicked: root.removing = "" }
        }
    }
    FormLabel { width: parent.width; visible: root.status.state === "downloading"; text: Math.floor(100 * (root.status.done || 0) / Math.max(1, root.status.total || 1)) + "%"; color: Theme.text2 }
    Flow {
        width: parent.width; spacing: 8
        Button { text: root.status.state === "downloading" ? "Huỷ" : root.status.state === "outdated" ? "Cập nhật" : "Tải"; kind: "text"; enabled: !root.busy && (root.status.state === "downloading" || root.status.supported !== false); onClicked: root.act(root.status.state === "downloading" ? "/cancel" : "", root.status.state === "outdated" ? {} : {choices: root.selected}) }
        Button { text: root.status.benchmarking ? "Đang đo…" : "Đo lại"; kind: "text"; enabled: !root.busy && !root.working; onClicked: root.act("/measure", {}) }
    }
    SettingRow { width: parent.width; label: "Dùng bản tăng tốc"; visible: Boolean(root.status.accelerated); Switch { label: "Dùng bản tăng tốc"; checked: Boolean(root.status.accelerated?.on); enabled: !root.busy && !root.working; onToggled: on => root.act("/accelerate", {on: on}) } }
}
