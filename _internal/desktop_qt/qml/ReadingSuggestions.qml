import QtQuick
import ABook

// The same /suggestions and /skip boundary as ReadingSuggestions.tsx. Each
// repeated credit line is one choice across its chapters. Never edit raw text.
Modal {
    id: root
    title: "Gợi ý cho phần đọc"
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
            width: parent.width; text: "Bỏ khỏi phần đọc, giữ chữ gốc; bỏ chọn để đọc lại. Chương đang nghe sẽ đổi từ lần nghe sau; các chương khác đổi ngay."
            color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption
        }
        Repeater {
            model: root.groups
            SettingRow {
                required property var modelData
                width: parent.width
                label: "Bỏ dòng"
                hint: "“" + modelData.line + "” · " + modelData.chapters.length + " chương"
                Switch {
                    objectName: "suggestionSkip"
                    label: "Bỏ dòng"
                    Accessible.description: modelData.line
                    checked: modelData.skipped
                    enabled: !root.saving && !Api.info.listenOnly
                    onToggled: on => root.setSkipped(modelData, on)
                }
            }
        }
        Collapse {
            width: parent.width; open: root.error !== ""
            Text { width: parent.width; text: root.error; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            Button { text: "Thử lại"; kind: "ghost"; onClicked: root.refresh() }
        }
        Collapse {
            width: parent.width; open: !!Api.info.listenOnly
            Text { width: parent.width; text: "Bạn đổi phần đọc trên máy làm sách."; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
        }
    }
    footer: Button { text: "Đóng"; kind: "ghost"; onClicked: root.close() }
}
