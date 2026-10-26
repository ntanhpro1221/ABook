import QtQuick
import ABook

// Cài đặt › Studio › Cách đọc chung (SharedReadingsSettings của studio/sharedReadings.tsx): xem, thêm, bỏ cách đọc dùng chung cho mọi sách
// (GET / POST /api/readings). Nằm trong khối gập "Cách đọc chung": lời dẫn trước, ô tìm chỉ khi danh sách đủ dài để cần tìm (> 8 mục).
SettingsItem {
    id: root
    property var entries: []
    property string filter: ""
    property int shown: 12
    property string problem: ""
    property bool saving: false
    readonly property int searchFrom: 8
    readonly property var filtered: entries.filter(e => (e.surface + " " + e.spokenForm).toLocaleLowerCase("vi").includes(filter.toLocaleLowerCase("vi")))
    padding: 12
    objectName: "sharedReadings"

    // Chữ đầu mỗi từ viết hoa - chỉ để HIỆN (shownReading của shared/format.ts); dữ liệu giữ nguyên cách đọc đã lưu
    function shownReading(spoken) {
        return String(spoken).replace(/(^|\s)(\S)/g, (m, gap, letter) => gap + letter.toUpperCase())
    }
    function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;") }
    function line(entry) {
        return "<span style=\"font-weight:500\">" + esc(entry.surface) + "</span> <span style=\"color:" + Theme.text3 + "\">→</span> “" + esc(shownReading(entry.spokenForm)) + "”"
            + (entry.from ? "<span style=\"font-size:12px; color:" + Theme.text3 + "\"> · từ " + esc(entry.from) + "</span>" : "")
    }
    function load() {
        if (!Api.transport) return
        Api.transport.request("GET", "/api/readings", null, function(status, data) {
            if (status >= 200 && status < 300) root.entries = (data && data.entries) || []
        })
    }
    function save(body) {
        if (!Api.transport || saving) return
        saving = true
        Api.transport.request("POST", "/api/readings", body, function(status, data) {
            saving = false
            if (status < 200 || status >= 300) { problem = data && (data.message || data.error) || "Không làm được lúc này."; return }
            load()
            if (body.remove) { Api.notice = "Đã bỏ “" + body.surface + "” khỏi cách đọc chung"; return }
            surfaceField.text = ""
            spokenField.text = ""
            Api.notice = "“" + body.surface + "” đọc là “" + shownReading(body.spokenForm || "") + "” cho mọi sách"
        })
    }
    function add() {
        problem = ""
        if (surfaceField.text.trim() && spokenField.text.trim()) save({surface: surfaceField.text.trim(), spokenForm: spokenField.text.trim()})
    }
    Component.onCompleted: load()

    Text { width: parent.width; text: "Sửa cách đọc một tên một lần, sách mới tự dùng."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: 13 }
    Collapse {
        width: parent.width
        open: root.entries.length > root.searchFrom
        Item { width: 1; height: 8 }
        FormField {
            objectName: "readingsFilter"
            width: parent.width
            label: "Tìm cách đọc"
            placeholderText: "Tìm tên…"
            fill: Theme.panel
            onTextChanged: { root.filter = text; root.shown = 12 }
        }
    }
    Item {
        width: parent.width
        height: list.height > 0 ? list.height + 8 : 0
        StudioRows {
            id: list
            y: 8
            width: parent.width
            items: root.filtered.slice(0, root.shown)
            keyField: "surface"
            delegate: Component {
                Item {
                    id: row
                    property var modelData: ({surface: "", spokenForm: "", from: ""})
                    width: parent ? parent.width : 0
                    implicitHeight: Math.max(entry.implicitHeight, trash.height) + 12
                    height: implicitHeight
                    Text {
                        id: entry
                        objectName: "readingLine"
                        x: 0
                        width: parent.width - trash.width - 12
                        anchors.verticalCenter: parent.verticalCenter
                        textFormat: Text.RichText
                        text: root.line(row.modelData)
                        color: Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                    IconButton {
                        id: trash
                        objectName: "removeReading"
                        x: parent.width - width
                        anchors.verticalCenter: parent.verticalCenter
                        icon: "trash-2"
                        iconSize: 16
                        ink: Theme.text2
                        hoverInk: Theme.text
                        tip: "Bỏ “" + row.modelData.surface + "” khỏi cách đọc chung"
                        Accessible.name: tip
                        onClicked: root.save({surface: row.modelData.surface, remove: true})
                    }
                }
            }
        }
    }
    Collapse {
        width: parent.width
        open: root.filtered.length > root.shown
        Item {
            width: parent.width
            height: more.height
            Button { id: more; objectName: "readingsMore"; text: "Xem thêm"; kind: "ghost"; size: "sm"; onClicked: root.shown += 12 }
        }
    }
    Flow {
        width: parent.width
        topPadding: 8
        spacing: 8
        FormField {
            id: surfaceField
            objectName: "readingSurface"
            width: Math.min(224, parent.width)
            label: "Từ trong sách"
            placeholderText: "Từ trong sách, vd Nasdell"
            fill: Theme.panel
            onAccepted: root.add()
        }
        FormField {
            id: spokenField
            objectName: "readingSpoken"
            width: Math.min(224, parent.width)
            label: "Cách đọc"
            placeholderText: "Đọc là, vd Hên-cơ"
            fill: Theme.panel
            onAccepted: root.add()
        }
        Button {
            objectName: "addReading"
            text: "Thêm"
            kind: "ghost"
            size: "sm"
            busy: root.saving
            enabled: surfaceField.text.trim() !== "" && spokenField.text.trim() !== ""
            onActivated: root.add()
        }
    }
    Collapse {
        width: parent.width
        open: root.problem !== ""
        Text { objectName: "readingsProblem"; width: parent.width; topPadding: 4; text: root.problem; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: 13 }
    }
}
