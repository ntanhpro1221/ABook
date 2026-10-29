import QtQuick
import ABook
import "ExportLogic.js" as Logic

// "Chữ sáng" của hộp Xuất file sách (WordTimingsRow của studio/WordTimings.tsx): sách làm từ trước chưa có mốc từng chữ thì căn một lần - việc chạy ngầm trên
// máy này (`/api/books/<mã>/word-timings`), xong thì file sách của dự án được đóng lại kèm mốc chữ. Hỏi lại mỗi giây CHỈ khi việc đang chạy và cửa sổ đang thấy.
// Dựng khi hộp cần (Loader), nên chưa mở tới thì chưa hỏi gì.
Item {
    id: root
    objectName: "wordTimings"
    property var store: null
    property string bookId: ""
    property bool bookRunning: false
    property var timings: null
    property bool starting: false
    readonly property bool working: (timings !== null && timings.state === "running") || starting
    implicitHeight: flow.height + 24
    height: implicitHeight

    function load() {
        if (!store || bookId === "") return
        store.quiet("GET", "/api/books/" + bookId + "/word-timings", null, function(result, error) { if (!error) root.timings = result })
    }
    function begin() {
        if (!store || starting) return
        starting = true
        store.quiet("POST", "/api/books/" + bookId + "/word-timings", null, function(result, error) {
            root.starting = false
            if (error) store.say("Chưa thêm được chữ sáng", error)
            else root.timings = result
        })
    }
    Component.onCompleted: load()
    Timer {
        interval: 1000
        repeat: true
        running: root.timings !== null && root.timings.state === "running" && root.store !== null && root.store.active
        onTriggered: root.load()
    }

    Flow {
        id: flow
        y: 12
        width: root.width
        spacing: 12
        Item {
            width: Math.min(root.width, Math.max(200, root.width - action.implicitWidth - 12))
            height: Math.max(24, texts.height)
            Icon { x: 0; y: 2; name: "captions"; size: 16; color: Theme.accentText }
            Column {
                id: texts
                x: 28
                width: parent.width - 28
                Text { width: parent.width; text: "Chữ sáng"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightBold }
                Text { objectName: "wordTimingsNote"; width: parent.width; text: Logic.wordTimingsNote(root.timings); color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            }
        }
        Button {
            id: action
            objectName: "wordTimingsStart"
            size: "sm"
            kind: "ghost"
            text: "Thêm chữ sáng"
            busy: root.working
            enabled: !Logic.wordTimingsDisabled(root.timings, root.bookRunning)
            onActivated: root.begin()
        }
    }
}
