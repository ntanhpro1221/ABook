import "UiStrings.js" as S
import QtQuick
import ABook
import "StudioLogic.js" as Studio

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

    // Chữ đầu mỗi từ viết hoa - chỉ để HIỆN; dữ liệu giữ nguyên cách đọc đã lưu (một hàm chung với mục "Cách đọc tên" của Studio)
    function shownReading(spoken) { return Studio.shownReading(spoken) }
    function esc(text) { return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\u00a0/g, "&nbsp;") }
    function line(entry) {
        return "<span style=\"font-weight:500\">" + esc(entry.surface) + "</span> <span style=\"color:" + Theme.text3 + S.s_doc_la_span_604b6689 + esc(shownReading(entry.spokenForm)) + "”"
            + (entry.from ? "<span style=\"font-size:12px; color:" + Theme.text3 + S.s_nbsp_nbsp_tu_4205cd1e + esc(entry.from) + "</span>" : "")
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
            if (status < 200 || status >= 300) { problem = data && (data.message || data.error) || S.s_chua_lam_duoc_luc_nay_2e7cacde; return }
            load()
            if (body.remove) { Api.notice = S.s_da_bo_8ccb2051 + body.surface + S.s_khoi_cach_doc_chung_c5d82684; return }
            surfaceField.text = ""
            spokenField.text = ""
            Api.notice = "“" + body.surface + S.s_doc_la_4c516fb0 + shownReading(body.spokenForm || "") + S.s_cho_moi_sach_8d2e1857
        })
    }
    function add() {
        problem = ""
        if (surfaceField.text.trim() && spokenField.text.trim()) save({surface: surfaceField.text.trim(), spokenForm: spokenField.text.trim()})
    }
    Component.onCompleted: load()

    Text { width: parent.width; text: S.s_sua_cach_doc_mot_ten_mot_lan_sach_moi_tu_d_f1569d6e; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: 14 }
    Collapse {
        width: parent.width
        open: root.entries.length > root.searchFrom
        Item { width: 1; height: 8 }
        FormField {
            objectName: "readingsFilter"
            width: parent.width
            label: S.s_tim_cach_doc_690f3c7e
            placeholderText: S.s_tim_ten_f777d5ea
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
                        icon: "trash"
                        iconSize: 16
                        ink: Theme.text2
                        hoverInk: Theme.text
                        tip: S.s_bo_76ce0117 + row.modelData.surface + S.s_khoi_cach_doc_chung_c5d82684
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
            Button { id: more; objectName: "readingsMore"; text: S.s_xem_them_e0ac1b1e; kind: "ghost"; size: "sm"; onClicked: root.shown += 12 }
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
            label: S.s_tu_trong_sach_e93bdaec
            placeholderText: S.s_tu_trong_sach_vd_nasdell_e5609228
            fill: Theme.panel
            onAccepted: root.add()
        }
        FormField {
            id: spokenField
            objectName: "readingSpoken"
            width: Math.min(224, parent.width)
            label: S.s_cach_doc_94265da7
            placeholderText: S.s_doc_la_vd_hen_co_6e778b3d
            fill: Theme.panel
            onAccepted: root.add()
        }
        Button {
            objectName: "addReading"
            text: S.s_them_dd92626f
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
        Text { objectName: "readingsProblem"; width: parent.width; topPadding: 4; text: root.problem; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: 14 }
    }
}
