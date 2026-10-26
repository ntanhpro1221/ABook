import QtQuick
import QtQuick.Dialogs
import ABook

Modal {
    id: root
    title: "Thêm sách"
    description: preview ? "Xem lại chương trước khi thêm. Chữ của truyện giữ nguyên." : "EPUB, DOCX, PDF có chữ, TXT, thư mục TXT hay file .abook. Chọn được nhiều file."
    property var preview: null
    property string path: ""
    property string bookTitle: ""
    property string busy: ""
    property string problem: ""
    property string technical: ""
    property bool split: false
    property var footnotes: ({hideMarks: false, notes: ""})
    property var picked: []
    property var names: ({})
    property var skipped: []
    property var queue: []
    property int current: -1
    property int generation: 0
    property bool leave: false
    property bool addRest: false
    property string addedId: ""
    readonly property var known: preview ? (defaultPicks() ? preview.existing : null) || preview.sameSource : null
    readonly property var suggestions: {
        const groups = []
        if (!preview) return groups
        const selected = preview.chapters.filter(c => picked.includes(c.index))
        for (const item of preview.suggestions || []) {
            const index = selected.findIndex(c => c.index === item.chapter)
            if (index < 0) continue
            let group = groups.find(g => g.line === item.line)
            if (!group) { group = {line: item.line, chapters: []}; groups.push(group) }
            group.chapters.push(index + 1)
        }
        return groups
    }
    signal openBook(string id)
    function defaultPicks() { return preview && JSON.stringify(picked.slice().sort()) === JSON.stringify(preview.chapters.filter(c => c.included !== false).map(c => c.index).sort()) }
    function reset() {
        generation++; preview = null; path = ""; bookTitle = ""; problem = ""; technical = ""; busy = ""; queue = []; current = -1; leave = false; addRest = false; addedId = ""
        split = false; footnotes = {hideMarks: false, notes: ""}; picked = []; names = {}; skipped = []
    }
    function begin(paths) {
        reset(); show()
        if (paths && paths.length) start(paths)
        else files.open()
    }
    function start(paths) {
        generation++; current = -1; queue = paths.map(p => ({path: p, state: "waiting", note: ""})); next()
    }
    function settle(state, note) {
        const items = queue.slice(); items[current] = Object.assign({}, items[current], {state: state, note: note || ""}); queue = items
    }
    function next() {
        preview = null; names = {}; picked = []; skipped = []; split = false; footnotes = {hideMarks: false, notes: ""}
        current++
        if (current >= queue.length) {
            busy = ""; DesktopApi.refreshLibrary()
            if (!queue.some(i => i.state === "error")) { dismiss(); if (addedId) openBook(addedId) }
            return
        }
        path = queue[current].path
        if (/\.abook(proj)?$/i.test(path.trim())) {
            busy = "reading"
            const mine = generation
            Api.call("POST", "/api/books/open", {path: path}, function(data, error) {
                if (mine !== root.generation) return
                root.busy = ""
                if (error) root.settle("error", error)
                else { root.settle("opened", "Đã mở"); root.addedId = data.id }
                root.next()
            })
        } else read(false, false)
    }
    function read(reread, forced) {
        const mine = ++generation
        busy = "reading"; problem = ""
        const body = {path: path, splitChapters: split}
        if (footnotes.hideMarks || footnotes.notes) body.footnotes = footnotes
        Api.call("POST", "/api/listen/import/preview", body, function(data, error) {
            if (mine !== root.generation || !root.open) return
            root.busy = ""
            if (error) {
                root.problem = error
                if (root.queue.length > 1) { root.settle("error", error); root.next() }
                return
            }
            if (!reread && !forced && data.splitOffer && (data.splitHeadings ?? data.splitOffer) >= 3) { root.split = true; root.read(false, true); return }
            const same = root.preview && JSON.stringify(root.preview.chapters.map(c => [c.title,c.included])) === JSON.stringify(data.chapters.map(c => [c.title,c.included]))
            root.preview = data
            if (!reread) root.bookTitle = data.title
            if (!same) { root.picked = data.chapters.filter(c => c.included !== false).map(c => c.index); root.names = {}; root.skipped = (data.suggestions || []).filter(s => s.defaultOn).map(s => s.line) }
            titleField.forceActiveFocus(Qt.TabFocusReason)
            if (root.addRest) { if (root.known) { root.settle("existing", "Đã có trong thư viện"); root.next() } else root.add(false) }
        })
    }
    function add(separate) {
        if (!preview || busy || !bookTitle.trim() || !picked.length) return
        busy = "adding"
        const mine = generation
        const body = {path: path, title: bookTitle.trim(), separate: Boolean(separate), splitChapters: split,
            sourceFingerprint: preview.sourceFingerprint, chapters: preview.chapters.filter(c => picked.includes(c.index)).map(c => names[c.index] ? {index: c.index, title: names[c.index]} : {index: c.index})}
        if (footnotes.hideMarks || footnotes.notes) body.footnotes = footnotes
        const skips = suggestions.filter(g => skipped.includes(g.line))
        Api.call("POST", "/api/listen/import", body, function(data, error) {
            if (mine !== root.generation) return
            root.busy = ""
            if (error) { root.problem = error; if (root.addRest) { root.settle("error", error); root.next() }; return }
            if (data.how === "new") for (const group of skips) Api.call("PUT", "/api/books/" + data.id + "/skip", {line: group.line, chapters: group.chapters, skip: true})
            root.addedId = data.id
            root.settle(data.how === "existing" ? "existing" : "added", data.how === "existing" ? "Đã có trong thư viện" : "Đã thêm")
            DesktopApi.refreshLibrary()
            if (root.queue.length === 1) { root.dismiss(); root.openBook(data.id) }
            else root.next()
        })
    }
    keepOpen: function() {
        if (busy === "adding") return true
        if (leave) { leave = false; return true }
        if (queue.filter(q => q.state === "waiting").length > 1) { leave = true; return true }
        generation++
        return false
    }
    onOpenChanged: if (!open) { generation++; files.close(); folder.close() }
    Column {
        width: parent.width; visible: root.leave; spacing: 8
        FormLabel { width: parent.width; text: "Còn " + root.queue.filter(q => q.state === "waiting").length + " cuốn chưa thêm vào thư viện. Đóng bây giờ thì các cuốn ấy sẽ không được thêm." }
        Flow { width: parent.width; spacing: 8
            Button { text: "Bỏ phần còn lại"; kind: "text"; onClicked: { root.generation++; root.dismiss() } }
            Button { text: "Quay lại thêm sách"; onClicked: root.leave = false }
        }
    }
    Column {
        width: parent.width; visible: root.queue.length > 1; spacing: 8
        Repeater { model: root.queue; FormLabel { required property var modelData; required property int index; width: parent.width; text: (index === root.current ? "→ " : "") + modelData.path.split(/[\\/]/).pop() + (modelData.note ? " · " + modelData.note : ""); color: modelData.state === "error" ? Theme.danger : Theme.text2 } }
    }
    Column {
        width: parent.width; spacing: 16; visible: !root.preview
        Flow {
            width: parent.width; spacing: 8
            Button { text: root.busy === "reading" ? "Đang đọc…" : "Chọn file sách"; icon: "file-text"; enabled: !root.busy; onClicked: files.open() }
            Button { text: "Chọn thư mục TXT"; icon: "folder"; kind: "text"; enabled: !root.busy; onClicked: folder.open() }
        }
        FormField { id: typed; width: parent.width; label: "Đường dẫn file hay thư mục"; placeholderText: "…hoặc dán đường dẫn"; enabled: !root.busy; onAccepted: if (text.trim()) root.start([text.trim().replace(/^["']+|["']+$/g, "").trim()]) }
        Button { text: "Mở"; kind: "text"; enabled: !root.busy && typed.text.trim() !== ""; onClicked: root.start([typed.text.trim().replace(/^["']+|["']+$/g, "").trim()]) }
        FormLabel { width: parent.width; text: "PDF phải có chữ - PDF chụp từ máy quét thì ABook chưa đọc được."; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
    }
    Column {
        width: parent.width; spacing: 8; visible: Boolean(root.preview)
        FormLabel { text: "Tên sách"; font.weight: Theme.weightMedium }
        FormField { id: titleField; objectName: "importTitle"; width: parent.width; label: "Tên sách"; text: root.bookTitle; onTextChanged: root.bookTitle = text; placeholderText: "Tên hiển thị trong thư viện" }
        FormLabel { width: parent.width; text: "Tác giả: " + (root.preview?.author || ""); visible: Boolean(root.preview?.author); color: Theme.text2 }
        FormLabel { width: parent.width; text: root.picked.length + " chương · " + (root.preview?.chapters || []).filter(c => root.picked.includes(c.index)).reduce((n,c) => n + c.words,0).toLocaleString(Qt.locale("vi_VN")) + " chữ"; color: Theme.text2 }
        Flow { width: parent.width; spacing: 8; visible: (root.preview?.chapters || []).length > 1
            Button { text: "Chọn hết"; kind: "text"; enabled: !root.busy; onClicked: root.picked = root.preview.chapters.map(c => c.index) }
            Button { text: "Bỏ chọn hết"; kind: "text"; enabled: !root.busy; onClicked: root.picked = [] }
        }
        SettingRow { width: parent.width; visible: Boolean(root.preview?.splitOffer); label: "Tách theo " + (root.preview?.splitHeadings ?? root.preview?.splitOffer ?? 0) + " dòng “Chương N”"; hint: root.split ? "Mỗi dòng “Chương N” mở một chương mới; chữ của truyện giữ nguyên." : "Cả truyện đang là một chương. Tích để tách theo các dòng ấy; chữ giữ nguyên."; Switch { label: "Tách chương"; checked: root.split; enabled: !root.busy; onToggled: value => { root.split = value; root.read(true, true) } } }
        Repeater {
            model: root.preview?.chapters || []
            Column {
                required property var modelData
                width: parent.width; spacing: 4
                SettingRow { width: parent.width; label: modelData.title; hint: modelData.words.toLocaleString(Qt.locale("vi_VN")) + " chữ" + (modelData.matter ? " · " + modelData.matter : ""); Switch { label: modelData.title; checked: root.picked.includes(modelData.index); enabled: !root.busy; onToggled: value => root.picked = value ? root.picked.concat([modelData.index]) : root.picked.filter(n => n !== modelData.index) } }
                FormLabel { width: parent.width; text: modelData.firstLine || ""; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                FormField { width: parent.width; label: "Tên chương"; text: root.names[modelData.index] ?? modelData.title; enabled: !root.busy; onTextEdited: { const next = Object.assign({},root.names); if (text.trim() && text.trim() !== modelData.title) next[modelData.index] = text.trim(); else delete next[modelData.index]; root.names = next } }
            }
        }
        FormLabel { width: parent.width; visible: root.picked.length === 0; text: "Chưa chọn chương nào - tích ít nhất một chương để thêm vào thư viện."; color: Theme.danger }
        SectionBlock { width: parent.width; title: "Định dạng"; fold: "wip"; visible: (root.preview?.notes || []).length > 0; FormLabel { width: parent.width; text: "Máy đã đổi định dạng - chữ của truyện giữ nguyên" } Repeater { model: root.preview?.notes || []; FormLabel { required property string modelData; width: parent.width; text: modelData; color: Theme.text2 } } }
        SectionBlock {
            width: parent.width; title: "Chú thích"; fold: "wip"; visible: Boolean(root.preview?.footnotes)
            FormLabel { width: parent.width; text: "Tìm thấy " + (root.preview?.footnotes?.found || 0) + " chú thích trong sách - ABook không tự bỏ hay sửa chữ của truyện" }
            SettingRow { width: parent.width; label: "Không đọc số chú thích"; hint: "Bỏ các con số như ² hay [3] khỏi phần đọc; lời chú không đổi."; visible: (root.preview?.footnotes?.marks || 0) > 0; Switch { label: "Không đọc số chú thích"; checked: root.footnotes.hideMarks; enabled: !root.busy; onToggled: value => { root.footnotes = {hideMarks: value, notes: root.footnotes.notes}; root.read(true, true) } } }
            SettingRow { width: parent.width; label: "Đọc lời chú ở cuối chương"; hint: "Mỗi lời chú nằm ở cuối chương có số gọi nó, kể cả khi trong sách nó nằm ở chương riêng."; Switch { label: "Đọc lời chú ở cuối chương"; checked: root.footnotes.notes === "end"; enabled: !root.busy; onToggled: value => { root.footnotes = {hideMarks: root.footnotes.hideMarks, notes: value ? "end" : ""}; root.read(true, true) } } }
            SettingRow { width: parent.width; label: "Bỏ lời chú"; hint: "Phần đọc không có lời chú nào. Bỏ tích để có lại."; Switch { label: "Bỏ lời chú"; checked: root.footnotes.notes === "drop"; enabled: !root.busy; onToggled: value => { root.footnotes = {hideMarks: root.footnotes.hideMarks, notes: value ? "drop" : ""}; root.read(true, true) } } }
            FormLabel { width: parent.width; text: "Không tích gì thì sách giữ nguyên như trong file."; color: Theme.text2 }
        }
        SectionBlock {
            width: parent.width; title: "Gợi ý phần đọc"; fold: "wip"; visible: root.suggestions.length > 0
            FormLabel { width: parent.width; text: "Dòng bỏ chỉ bị bỏ qua khi đọc; chữ của sách giữ nguyên."; color: Theme.text2 }
            Repeater { model: root.suggestions; SettingRow { required property var modelData; width: parent.width; label: modelData.line; hint: "Bỏ dòng này khỏi phần đọc"; Switch { label: "Bỏ dòng này khỏi phần đọc"; checked: root.skipped.includes(modelData.line); onToggled: value => root.skipped = value ? root.skipped.concat([modelData.line]) : root.skipped.filter(l => l !== modelData.line) } } }
        }
        FormLabel { width: parent.width; visible: Boolean(root.known); text: root.known ? "Đã có trong thư viện: " + root.known.title : ""; color: Theme.text2 }
        Flow {
            width: parent.width; spacing: 8
            Button { text: "Chọn lại"; kind: "text"; enabled: !root.busy; onClicked: { if (root.queue.filter(q => q.state === "waiting").length > 1) root.leave = true; else { root.reset(); files.open() } } }
            Button { text: "Bỏ cuốn này"; kind: "text"; visible: root.queue.length > 1; enabled: !root.busy; onClicked: { root.settle("skipped", "Bỏ qua"); root.next() } }
            Button { text: "Thêm phần còn lại"; kind: "text"; visible: root.current < root.queue.length - 1; enabled: !root.busy && root.bookTitle.trim() !== "" && root.picked.length > 0; onClicked: { root.addRest = true; root.add(false) } }
            Button { text: root.known ? (root.preview?.existing ? "Thêm bản riêng" : "Vẫn thêm bản mới") : "Thêm vào thư viện"; icon: root.known ? "copy" : "book-plus"; enabled: !root.busy && root.bookTitle.trim() !== "" && root.picked.length > 0; onClicked: root.add(Boolean(root.known)) }
            Button { text: "Mở cuốn đó"; icon: "book-open"; visible: Boolean(root.known) && root.queue.length === 1; enabled: !root.busy; onClicked: { const id = root.known.id; root.dismiss(); root.openBook(id) } }
        }
    }
    FormLabel { width: parent.width; text: root.problem; visible: text !== ""; color: Theme.danger }
    Button { text: "Thử lại"; kind: "text"; visible: root.problem !== ""; enabled: !root.busy; onClicked: root.read(false, false) }
    FileDialog { id: files; title: "Chọn file sách (chọn được nhiều file một lúc)"; fileMode: FileDialog.OpenFiles; nameFilters: ["Sách (*.epub *.docx *.pdf *.txt *.abook *.abookproj)", "Tất cả file (*)"]; onAccepted: root.start(selectedFiles.map(f => DesktopApi.localPath(f))) }
    FolderDialog { id: folder; title: "Chọn thư mục có các chương TXT"; onAccepted: root.start([DesktopApi.localPath(selectedFolder)]) }
}
