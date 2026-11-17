import QtQuick
import QtQuick.Dialogs
import ABook
import "UiStrings.js" as S

// Only chapter boundaries change. The project keeps its chapter ids and global queue.
Column {
    id: root
    property var book: ({})
    property var rows: []
    property bool busy: false
    property string problem: ""
    property int picking: -1
    property string loadedId: ""
    property int generation: 0
    readonly property var chapters: book.chapters || []
    spacing: Theme.s12
    onBookChanged: if (loadedId !== (book.id || "")) reset()
    Component.onCompleted: reset()
    function reset() {
        generation++
        busy = false
        loadedId = book.id || ""
        const volumes = book.volumes || [{id: 1, number: 1, title: S.s_volume_number(1), chapters: chapters}]
        rows = volumes.map(v => ({id: v.id, number: v.number, title: v.title,
            start: chapters.findIndex(c => c.id === (v.chapters || [])[0]?.id) + 1}))
        problem = ""
    }
    function change(id, key, value) {
        rows = rows.map(row => row.id === id ? Object.assign({}, row, {[key]: value}) : row)
    }
    function add() {
        const start = rows.length ? Number(rows[rows.length - 1].start) + 1 : 1
        if (start > chapters.length) return
        // Id mới lớn hơn mọi id đã nạp lẫn đang có: quyển vừa xoá không bị tái dùng (bìa riêng ghép theo id) - một luật cho cả ba nền (soát 0.4.173 B13c).
        rows = rows.concat([{id: Math.max(0, ...rows.map(v => v.id), ...(book.volumes || []).map(v => v.id)) + 1, number: rows.length + 1,
            title: S.s_volume_number(rows.length + 1), start: start}])
    }
    function save() {
        const starts = rows.map(v => Number(v.start))
        if (!rows.length || starts[0] !== 1 || rows.some((v, i) => !v.title.trim() || v.title.length > 240
            || !Number.isInteger(Number(v.number)) || Number(v.number) < 1 || Number(v.number) > 9999
            || !Number.isInteger(starts[i]) || starts[i] > chapters.length || (i > 0 && starts[i] <= starts[i - 1]))) {
            problem = S.s_volume_invalid; return
        }
        const mine = generation, id = loadedId, draft = rows.slice()
        const definitions = draft.map((v, i) => ({id: v.id, number: Number(v.number), title: v.title.trim(),
            chapters: chapters.slice(starts[i] - 1, (starts[i + 1] || chapters.length + 1) - 1).map(c => c.id)}))
        busy = true; problem = ""
        Api.call("PUT", "/api/books/" + id + "/volumes", {volumes: definitions}, function(data, error) {
            if (mine !== root.generation) return
            if (error) { root.busy = false; root.problem = error; return }
            const covers = draft.filter(v => v.image !== undefined)
            function next(index) {
                if (mine !== root.generation) return
                if (index === covers.length) {
                    root.busy = false
                    Api.editedBook(id)
                    return
                }
                const v = covers[index]
                Api.call("PUT", "/api/books/" + id + "/volumes/" + v.id + "/cover", {image: v.image}, function(saved, failure) {
                    if (mine !== root.generation) return
                    if (failure) { root.busy = false; root.problem = failure; return }
                    next(index + 1)
                })
            }
            next(0)
        })
    }
    Prose { width: parent.width; text: S.s_volume_split_help; small: true }
    StudioRows {
        width: parent.width
        keyField: "id"
        items: root.rows
        delegate: Component {
            Column {
                property var modelData: ({})
                width: parent ? parent.width : 0
                spacing: Theme.s8
                enabled: !root.busy
                Prose { width: parent.width; text: S.s_volume_title; small: true; tone: Theme.text }
                FormField { width: parent.width; label: S.s_volume_title; text: modelData.title || ""; onTextChanged: if (modelData.id && text !== String(modelData.title || "")) root.change(modelData.id, "title", text) }
                Prose { width: parent.width; text: S.s_volume_number(modelData.number || 1); small: true; tone: Theme.text }
                FormField { width: parent.width; label: S.s_volume_number(modelData.number || 1); text: String(modelData.number || ""); inputMethodHints: Qt.ImhDigitsOnly; onTextChanged: if (modelData.id && text !== String(modelData.number || "")) root.change(modelData.id, "number", text) }
                Prose { width: parent.width; text: S.s_volume_first_chapter; small: true; tone: Theme.text }
                FormField { width: parent.width; label: S.s_volume_first_chapter; text: String(modelData.start || 1); enabled: modelData.id !== root.rows[0]?.id; inputMethodHints: Qt.ImhDigitsOnly; onTextChanged: if (modelData.id && text !== String(modelData.start || 1)) root.change(modelData.id, "start", text) }
                Flow {
                    width: parent.width; spacing: Theme.s8
                    Button { text: S.s_volume_cover; kind: "ghost"; onActivated: { root.picking = modelData.id; images.open() } }
                    Button { text: S.s_volume_book_cover; kind: "ghost"; onActivated: root.change(modelData.id, "image", null) }
                    Button { text: S.s_xoa_777195ab; kind: "ghost"; Reveal { shown: modelData.id !== root.rows[0]?.id } onActivated: root.rows = root.rows.filter(v => v.id !== modelData.id) }
                }
            }
        }
    }
    Button { text: S.s_volume_add; kind: "ghost"; enabled: !root.busy && root.rows.length < Math.min(99, root.chapters.length); onActivated: root.add() }
    Prose { width: parent.width; text: root.problem; tone: Theme.danger; Reveal { shown: root.problem !== "" } }
    Button { text: S.s_volume_save; busy: root.busy; enabled: !root.busy && root.rows.length > 0; onActivated: root.save() }
    FileDialog {
        id: images
        title: S.s_volume_cover
        nameFilters: [S.s_anh_png_jpg_jpeg_webp_gif_bmp_8ce57f5a]
        onAccepted: {
            const image = DesktopApi.imageData(selectedFile)
            if (image) root.change(root.picking, "image", image)
            else root.problem = S.s_chua_doc_duoc_file_anh_09736d91
        }
    }
}
