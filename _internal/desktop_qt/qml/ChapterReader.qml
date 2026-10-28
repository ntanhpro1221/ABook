import QtQuick
import ABook

// Reading layer shared by library tiles and chapter menus. It opens above the
// current screen, so Back returns to the exact listening/scroll position. The
// wider 720 px reader reserves a 640 px reading measure and selectable text.
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
    SequentialAnimation {
        id: textMotion
        NumberAnimation { target: root; property: "textOpacity"; to: 0; duration: Theme.reduceMotion ? 60 : Theme.motionFastOut }
        ScriptAction { script: { root.paragraphs = root.pendingParagraphs; root.loading = false; reading.positionViewAtBeginning() } }
        NumberAnimation { target: root; property: "textOpacity"; to: 1; duration: Theme.reduceMotion ? 90 : Theme.motionMedium }
    }
    function begin(id, chapterId) {
        textMotion.stop(); textOpacity = 1
        bookId = id; chapters = []; chapter = null; paragraphs = []; error = ""; loading = true
        show()
        const seq = ++generation
        Api.quiet("GET", "/api/listen/books/" + encodeURIComponent(id), null, function(data, err) {
            if (seq !== root.generation || !root.open) return
            if (err) { root.error = err; root.loading = false; return }
            root.chapters = data.chapters || []
            const selected = root.chapters.find(c => c.id === chapterId) || root.chapters[0]
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
            const skipped = next.skip || []
            root.pendingParagraphs = typeof data.text === "string" ? data.text.split(/\r?\n/).filter(line => skipped.indexOf(line.trim()) < 0).join("\n").split(/\n\s*\n/).filter(p => p.trim()) : (data.segments || []).map(s => s.text || "").filter(Boolean)
            textMotion.restart()
        })
    }
    onClosed: { ++generation; loading = false; textMotion.stop() }
    Column {
        width: parent.width; spacing: Theme.s16
        Select {
            objectName: "readerChapters"
            width: parent.width; label: "Chương"
            options: root.chapters.map(c => ({value: c.id, label: c.fullTitle || c.title}))
            value: root.chapter ? root.chapter.id : -1
            onPicked: value => root.load(root.chapters.find(c => c.id === value))
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
                required property string modelData
                width: ListView.view.width
                text: modelData; textFormat: TextEdit.PlainText
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                color: Theme.read.fg
                font.family: Theme.family; font.pixelSize: Theme.sizeReading
                Component.onCompleted: ReadAlong.setLineHeight(textDocument, Theme.sizeReading * Theme.lineHeightReading)
                selectionColor: Theme.accentSoft
            }
            Rectangle { anchors.fill: parent; z: -1; color: Theme.read.bg }
            SmoothWheel { flick: reading }
            Scrollbar { parent: reading; target: reading }
        }
    }
}
