import QtQuick
import ABook
import "FindLogic.js" as Find

// Reading layer shared by library tiles and chapter menus. It opens above the
// current screen, so Back returns to the exact listening/scroll position. The
// wider 720 px reader reserves a 640 px reading measure and selectable text.
// `at` (từ ô "Tìm trong sách"): đoạn ấy cuộn tới đầu khung và sáng lên; `play` (đang nghe cuốn này) thì nghe tiếp từ chính câu ấy.
// Đoạn chia bằng FindLogic.paragraphs - cùng cách với ô tìm, nên chỉ số kết quả là chỉ số đoạn ở đây.
Modal {
    id: root
    objectName: "chapterReader"
    panelWidth: 720
    title: chapter ? chapter.fullTitle || chapter.title : "Đọc"
    property string bookId: ""
    property var chapters: []
    property var chapter: null
    property var paragraphs: []
    property var pendingParagraphs: []
    property real textOpacity: 1
    property string error: ""
    property bool loading: false
    property int generation: 0
    property int at: -1                     // đoạn được yêu cầu (-1: đầu chương)
    property bool play: false
    property bool marked: false             // đoạn `at` sáng lên (chỗ vừa tìm thấy); chỗ đọc dở thì chỉ cuộn tới
    SequentialAnimation {
        id: textMotion
        NumberAnimation { target: root; property: "textOpacity"; to: 0; duration: Theme.reduceMotion ? 60 : Theme.motionFastOut }
        ScriptAction { script: { root.paragraphs = root.pendingParagraphs; root.loading = false; root.reveal() } }
        NumberAnimation { target: root; property: "textOpacity"; to: 1; duration: Theme.reduceMotion ? 90 : Theme.motionMedium }
    }
    function begin(id, chapterId, place, listen, mark) {
        textMotion.stop(); textOpacity = 1
        bookId = id; chapters = []; chapter = null; paragraphs = []; error = ""; loading = true
        at = place === undefined ? -1 : place; play = Boolean(listen); marked = Boolean(mark)
        show()
        const seq = ++generation
        Api.quiet("GET", "/api/listen/books/" + encodeURIComponent(id), null, function(data, err) {
            if (seq !== root.generation || !root.open) return
            if (err) { root.error = err; root.loading = false; return }
            root.chapters = data.chapters || []
            const selected = root.chapters.find(c => c.id === chapterId) || root.chapters[0]
            if (selected && selected.id !== chapterId) root.at = -1
            if (!selected) { root.error = "Chưa có chương để đọc."; root.loading = false; return }
            root.load(selected)
        })
    }
    function load(next) {
        textMotion.stop()
        chapter = next; error = ""; loading = true
        const seq = ++generation
        const path = (next.state === "text" ? "/api/listen/books/" : "/api/books/") + encodeURIComponent(bookId) + "/chapters/" + next.id
        Api.quiet("GET", path + (next.state === "text" ? "/text" : "/script"), null, function(data, err) {
            if (seq !== root.generation || !root.open) return
            if (err) { root.error = err; root.pendingParagraphs = []; textMotion.restart(); return }
            // Skip is the explicit reading edit layer; the original source stays
            // intact. Reloading book metadata on begin gives the latest choices.
            root.pendingParagraphs = Find.paragraphs(data, next.skip).map((p, index) => ({text: p.text, index: index, start: p.start})).filter(p => p.text)
            textMotion.restart()
        })
    }
    // Tới đoạn được yêu cầu (hay đầu chương); nghe từ câu ấy khi được bảo và cuốn đang nạp trong bộ phát.
    function reveal() {
        const row = root.at >= 0 ? root.paragraphs.findIndex(p => p.index === root.at) : -1
        if (row <= 0) reading.positionViewAtBeginning()
        else reading.positionViewAtIndex(row, ListView.Beginning)
        if (row < 0 || !root.play) return
        const target = root.paragraphs[row]
        root.play = false
        if (typeof target.start === "number" && Player.loaded && Player.bookId === root.bookId)
            Player.jumpTo(root.chapter.id, target.start, "Nghe từ “" + Find.snippetOf(target.text, null).after + "”")
    }
    onClosed: { ++generation; loading = false; textMotion.stop() }
    Column {
        width: parent.width; spacing: Theme.s16
        Select {
            objectName: "readerChapters"
            width: parent.width; label: "Chương"
            options: root.chapters.map(c => ({value: c.id, label: c.fullTitle || c.title}))
            value: root.chapter ? root.chapter.id : -1
            onPicked: value => { root.at = -1; root.load(root.chapters.find(c => c.id === value)) }
        }
        Collapse {
            width: parent.width; open: root.loading
            Text { width: parent.width; text: "Đang tải chương…"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        }
        Collapse {
            width: parent.width; open: root.error !== ""
            Text { width: parent.width; text: root.error; color: Theme.danger; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            Button { text: "Thử lại"; kind: "ghost"; onClicked: root.chapter ? root.load(root.chapter) : root.begin(root.bookId, -1) }
        }
        ListView {
            id: reading; objectName: "readerText"
            width: Math.min(parent.width, 640); height: Math.max(120, Math.min(620, root.height - 260))
            anchors.horizontalCenter: parent.horizontalCenter
            clip: true; spacing: Theme.s16
            opacity: root.textOpacity
            model: root.paragraphs
            delegate: TextEdit {
                required property var modelData
                readonly property bool found: root.marked && modelData.index === root.at
                objectName: found ? "readerFound" : ""
                width: ListView.view.width
                text: modelData.text; textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: Theme.read.fg
                font.family: Theme.family; font.pixelSize: Theme.sizeReading
                Component.onCompleted: ReadAlong.setLineHeight(textDocument, Theme.sizeReading * Theme.lineHeightReading)
                selectionColor: Theme.accentSoft
                // Đoạn vừa tìm thấy: nền nhấn nhạt tràn ra hai bên một chút (như câu được chọn ở màn đọc web).
                Rectangle {
                    z: -1; x: -8; y: -4; width: parent.width + 16; height: parent.height + 8
                    radius: Theme.radiusControl; color: Theme.accentSoft
                    opacity: parent.found ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionMedium } }
                }
            }
            Rectangle { anchors.fill: parent; z: -1; color: Theme.read.bg }
            SmoothWheel { flick: reading }
            Scrollbar { parent: reading; target: reading }
        }
    }
}
