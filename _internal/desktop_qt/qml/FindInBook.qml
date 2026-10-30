import QtQuick
import ABook
import "FindLogic.js" as Find

// "Tìm trong sách" (listen/FindInBook.tsx + bookSearch.ts): gõ một chữ / một câu (không cần dấu, hoa thường), bấm một kết quả là mở màn đọc đúng đoạn
// ấy; đang nghe cuốn này thì nghe tiếp từ câu đó. Chữ lấy gộp tới 64 chương một lần (GET .../search-texts); máy chủ không gộp được (sách của máy khác)
// thì nạp từng chương như màn đọc. Chương đi lần lượt, nhường luồng giao diện giữa các lô (Later.call) - ô gõ không treo, kết quả hiện dần. Chữ đã
// chuẩn hoá giữ trong lúc hộp mở cho lần gõ kế; đóng hộp là thả. Bàn phím: Enter mở kết quả đầu, ↓ xuống danh sách, ↑ ở kết quả đầu về ô tìm.
Modal {
    id: root
    objectName: "findInBook"
    panelWidth: 560
    title: "Tìm trong sách"
    description: bookTitle
    property string bookId: ""
    property string bookTitle: ""
    property var chapters: []               // chương của cuốn theo thứ tự ({id, title, fullTitle, state, skip})
    property string query: ""
    property var progress: null             // {hits, total, scanned, chapters, failed, done}
    property var cache: ({})                // mã chương -> chữ đã chuẩn hoá, hay null khi không đọc được
    property int generation: 0
    readonly property var hits: progress ? progress.hits : []
    signal picked(var hit)

    function begin(id, title, list) {
        if (id !== bookId) cache = {}
        bookId = id; bookTitle = title || ""; chapters = list || []
        field.text = ""; query = ""; progress = null
        show()
        Later.call(root, function() { field.forceActiveFocus(Qt.TabFocusReason) })
    }
    function pick(hit) {
        dismiss()
        root.picked(hit)
    }
    onQueryChanged: {
        progress = null
        ++generation
        if (open && Find.foldedQuery(query)) typing.restart()
        else typing.stop()
    }
    onClosed: { ++generation; typing.stop(); cache = {} }
    // Chờ người gõ ngừng tay 250 ms rồi mới tìm (TYPING_MS của web).
    Timer { id: typing; interval: 250; onTriggered: root.run() }

    function chapterLabel(chapterId) {
        const chapter = chapters.find(c => c.id === chapterId)
        return chapter ? chapter.fullTitle || chapter.title : ""
    }
    function run() {
        const seq = ++generation
        const needle = Find.foldedQuery(query)
        const list = chapters
        const state = {hits: [], total: 0, scanned: 0, chapters: list.length, failed: 0, done: false}
        const store = cache
        const byId = {}
        for (const chapter of list) byId[chapter.id] = chapter
        let from = 0
        let bulk = true
        let reported = 0
        const alive = () => seq === root.generation && root.open
        const report = force => {
            if (!force && Date.now() - reported < 120) return
            reported = Date.now()
            root.progress = Object.assign({}, state, {hits: state.hits.slice()})
        }
        const keep = (chapter, data) => { store[chapter.id] = data ? Find.prepare(Find.paragraphs(data, chapter.skip)) : null }
        const step = function() {
            if (!alive()) return
            const started = Date.now()
            while (from < list.length && store[list[from].id] !== undefined) {
                Find.scan(state, list[from].id, store[list[from].id], needle)
                from += 1
                if (Date.now() - started >= 12) { report(false); Later.call(root, step); return }
            }
            if (from >= list.length) { state.done = true; report(true); return }
            report(false)
            if (bulk) {
                const lot = list.slice(from, from + Find.BULK).filter(c => store[c.id] === undefined).map(c => c.id)
                const text = lot.filter(id => byId[id].state === "text")
                const path = "/api/listen/books/" + encodeURIComponent(root.bookId) + "/search-texts?chapters=" + lot.join(",") + (text.length ? "&text=" + text.join(",") : "")
                Api.quiet("GET", path, null, function(data, error) {
                    if (!alive()) return
                    const got = !error && data && Array.isArray(data.chapters) ? data.chapters : []
                    if (!got.length) bulk = false          // lỗi / sách của máy khác: phần còn lại nạp từng chương
                    for (const item of got) if (byId[item.id]) keep(byId[item.id], item.failed ? null : item)
                    step()
                })
                return
            }
            // Từng chương, cùng đường với màn đọc.
            const chapter = list[from]
            const text = chapter.state === "text"
            const path = (text ? "/api/listen/books/" : "/api/books/") + encodeURIComponent(root.bookId) + "/chapters/" + chapter.id + (text ? "/text" : "/script")
            Api.quiet("GET", path, null, function(data, error) {
                if (!alive()) return
                keep(chapter, error ? null : data)
                step()
            })
        }
        step()
    }

    Column {
        width: parent.width
        spacing: Theme.s8
        Item {
            width: parent.width
            height: field.height
            FormField {
                id: field
                objectName: "findQuery"
                width: parent.width
                leftPadding: 36
                topPadding: 12
                bottomPadding: 12
                font.pixelSize: Theme.sizeBody
                label: "Chữ hay câu cần tìm"
                placeholderText: "Chữ hay câu cần tìm…"
                onTextChanged: root.query = text
                onAccepted: if (root.hits.length) root.pick(root.hits[0])
                Keys.onDownPressed: event => {
                    if (!root.hits.length) { event.accepted = false; return }
                    results.focusRow(0)
                }
            }
            Icon { x: 12; anchors.verticalCenter: parent.verticalCenter; name: "search"; size: 16; color: Theme.text3 }
        }
        Text {
            objectName: "findStatus"
            width: parent.width
            text: Find.findStatus(root.query, root.progress, root.hits.length)
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
            Accessible.role: Accessible.StaticText
            Accessible.name: text
        }
    }
    Collapse {
        width: parent.width
        open: root.hits.length > 0
        // Tối đa 200 kết quả (RESULT_LIMIT): một cột dựng đủ, chiều cao khung theo đúng nội dung tới trần 448 / 55 % cửa sổ.
        Item {
            width: parent.width
            height: Math.min(448, Math.max(0, root.height * 0.55), column.height)
            Flickable {
                id: results
                objectName: "findResults"
                anchors.fill: parent
                contentWidth: width
                contentHeight: column.height
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Accessible.role: Accessible.List
                function focusRow(index) {
                    const item = rows.itemAt(index)
                    if (!item) return
                    if (item.y < contentY) contentY = item.y
                    else if (item.y + item.height > contentY + height) contentY = item.y + item.height - height
                    item.forceActiveFocus(Qt.TabFocusReason)
                }
                Column {
                    id: column
                    width: results.width
                    Repeater {
                        id: rows
                        model: root.hits
                        Interactive {
                            id: row
                            required property var modelData
                            required property int index
                            objectName: "findHit"
                            width: column.width
                            height: words.height + 20
                            Accessible.role: Accessible.Button
                            Accessible.name: root.chapterLabel(modelData.chapterId) + ": " + modelData.snippet.before + modelData.snippet.match + modelData.snippet.after
                            onClicked: root.pick(modelData)
                            Keys.onUpPressed: index === 0 ? field.forceActiveFocus(Qt.TabFocusReason) : results.focusRow(index - 1)
                            Keys.onDownPressed: results.focusRow(Math.min(index + 1, rows.count - 1))
                            Rectangle {
                                anchors.fill: parent
                                radius: Theme.radiusControl
                                color: Theme.hover
                                opacity: row.hovered ? 1 : 0
                                Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                            }
                            Column {
                                id: words
                                x: 6
                                y: 10
                                width: parent.width - 12
                                spacing: 2
                                Text {
                                    width: parent.width
                                    text: root.chapterLabel(row.modelData.chapterId)
                                    color: Theme.text2
                                    wrapMode: Text.Wrap
                                    font.pixelSize: Theme.sizeCaption
                                    font.weight: Theme.weightMedium
                                }
                                Text {
                                    objectName: "findExcerpt"
                                    width: parent.width
                                    textFormat: Text.RichText
                                    text: Find.snippetHtml(row.modelData.snippet, Theme.accentSoft, Theme.accentText)
                                    color: Theme.text
                                    wrapMode: Text.Wrap
                                    lineHeight: 1.4
                                    font.pixelSize: Theme.sizeBodySmall
                                }
                            }
                        }
                    }
                }
                SmoothWheel { flick: results }
            }
            Scrollbar { target: results }
            ScrollEdges { target: results; color: Theme.panel; anchors.fill: results }
        }
    }
}
