import "UiStrings.js" as S
import QtQuick
import ABook

// The same /suggestions and /skip boundary as ReadingSuggestions.tsx. Each
// repeated credit line is one choice across its chapters. Never edit raw text.
Modal {
    id: root
    title: S.s_goi_y_phan_doc_b268d95e
    property string bookId: ""
    property var groups: []
    property bool loading: false
    property bool saving: false
    property string error: ""
    property int generation: 0
    onBookIdChanged: { groups = []; refresh() }
    function refresh() {
        const seq = ++generation, id = bookId
        if (!id) { groups = []; return }
        loading = true; error = ""
        Api.quiet("GET", "/api/books/" + encodeURIComponent(id) + "/suggestions", null, function(data, err) {
            if (seq !== root.generation || id !== root.bookId) return
            root.loading = false
            if (err) { root.error = err; return }
            const byLine = {}, rows = []
            for (const item of data.suggestions || []) {
                if (!byLine[item.line]) { byLine[item.line] = {line: item.line, chapters: [], skipped: true}; rows.push(byLine[item.line]) }
                byLine[item.line].chapters.push(item.chapter)
                byLine[item.line].skipped = byLine[item.line].skipped && item.skipped === true
            }
            root.groups = rows
        })
    }
    function setSkipped(group, on) {
        if (saving || Api.info.listenOnly) return
        saving = true; error = ""
        const id = bookId
        Api.quiet("PUT", "/api/books/" + encodeURIComponent(id) + "/skip", {line: group.line, chapters: group.chapters, skip: on}, function(data, err) {
            root.saving = false
            if (id !== root.bookId) return
            if (err) { root.error = err; return }
            root.refresh()
            Api.editedBook(id)
        })
    }
    Column {
        width: parent.width; spacing: Theme.s12
        Text {
            width: parent.width; text: S.s_bo_khoi_phan_doc_giu_chu_goc_bo_chon_de_do_53aadf4d
            color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption
        }
        Repeater {
            model: root.groups
            SettingRow {
                required property var modelData
                width: parent.width
                label: S.s_bo_dong_3643dad2
                hint: "“" + modelData.line + "”\u00a0·\u00a0" + modelData.chapters.length + S.s_chuong_9e6a01dc
                Switch {
                    objectName: "suggestionSkip"
                    label: S.s_bo_dong_3643dad2
                    Accessible.description: modelData.line
                    checked: modelData.skipped
                    enabled: !root.saving && !Api.info.listenOnly
                    onToggled: on => root.setSkipped(modelData, on)
                }
            }
        }
        InlineError {
            objectName: "suggestionsError"
            width: parent.width; open: root.error !== ""
            message: root.error
            onRetry: root.refresh()
        }
        Collapse {
            width: parent.width; open: !!Api.info.listenOnly
            Text { width: parent.width; text: S.s_ban_doi_phan_doc_tren_may_lam_sach_9cc4c3a9; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
        }
    }
    footer: Button { text: S.s_dong_5d54c2a1; kind: "ghost"; onClicked: root.close() }
}
