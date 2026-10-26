import QtQuick
import ABook
Column {
    id: root
    property string bookId: ""
    property var view: ({})
    property bool busy: false
    spacing: 8
    function load() { if (bookId) Api.call("GET", "/api/books/" + bookId + "/music", null, function(data, error) { if (!error) root.view = data }) }
    function change(body) { busy = true; Api.call("PUT", "/api/books/" + bookId + "/music", body, function(data, error) { root.busy = false; if (!error) { root.view = data; Api.editedBook(root.bookId) } }) }
    onVisibleChanged: if (visible) load()
    FormLabel { width: parent.width; visible: !root.view.hasMusic; text: "Người làm sách không gắn nhạc nền cho cuốn này."; color: Theme.text2 }
    SettingRow { width: parent.width; visible: Boolean(root.view.hasMusic); label: "Nhạc nền: " + (root.view.enabled ? "Bật" : "Tắt"); Switch { label: "Nhạc nền"; checked: root.view.enabled !== false; enabled: !root.busy; onToggled: value => root.change({enabled: value}) } }
    SettingChoices { width: parent.width; visible: Boolean(root.view.hasMusic); label: "Mức nhạc dưới giọng đọc"; value: root.view.levelDb ?? -20; options: [{value: -26,label: "Rất nhẹ"},{value: -20,label: "Nhẹ"},{value: -14,label: "Rõ hơn"}]; onPicked: value => root.change({levelDb: value}) }
    Repeater {
        model: root.view.cues || []
        SettingRow { required property var modelData; width: parent.width; label: modelData.title || "Nhạc nền"; hint: modelData.chapter + (modelData.creator ? " · " + modelData.creator : ""); Button { text: modelData.silenced ? "Có nhạc lại" : "Im đoạn này"; kind: "text"; enabled: !root.busy; onClicked: { const silence = {}; silence[modelData.key] = !modelData.silenced; root.change({silence: silence}) } } }
    }
}
