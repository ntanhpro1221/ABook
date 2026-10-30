import QtQuick
import ABook
import "WorkLogic.js" as W

// Một câu ví dụ của thẻ việc (Example của WorkInbox.tsx): nút nghe (khi câu đã có bản thu), dòng nhỏ chương · câu · máy gán, chữ của câu (tên ứng viên tô nền nhạt), câu liền
// trước / sau làm ngữ cảnh (vạch bên trái đánh dấu đúng câu đang hỏi). `picks`: thẻ vai phụ cả cuốn - ô chọn đứng đầu hàng, câu bỏ chọn mờ đi.
Item {
    id: root
    property var example: ({})
    property var work: null
    property bool picks: false
    property bool picked: true
    property bool changes: false
    signal pickToggled()
    readonly property bool framed: Boolean(example.before) || Boolean(example.after)
    readonly property real gutter: (picks ? 24 + 8 : 0) + 36 + 8
    width: parent ? parent.width : 400
    height: Math.max(36, body.height)
    opacity: picks && !picked ? 0.6 : 1
    Behavior on opacity { NumberAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionFast } }

    ImportBox {
        id: tick
        objectName: "exampleTick"
        visible: root.picks
        x: 2
        y: 8
        checked: root.picked
        label: "Gồm câu này: " + root.example.text
        onToggled: root.pickToggled()
    }
    Item {
        id: lead
        x: root.picks ? 32 : 0
        width: 36
        height: 36
        CastSample {
            objectName: "exampleSample"
            visible: Boolean(root.example.hasAudio)
            clipId: "work-" + root.example.segmentId
            url: root.work && root.example.hasAudio ? root.work.store.path("/media/books/" + root.work.bookId + "/samples/" + root.example.segmentId) : ""
            label: "Nghe câu: " + root.example.text
        }
    }
    Column {
        id: body
        x: root.gutter
        width: root.width - root.gutter
        spacing: 2
        Text {
            objectName: "exampleBefore"
            visible: Boolean(root.example.before)
            width: parent.width
            text: root.example.before || ""
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            Accessible.description: "Câu liền trước"
        }
        Item {
            width: parent.width
            height: inner.height
            Rectangle { visible: root.framed; width: 2; height: parent.height; color: Theme.accent }
            Column {
                id: inner
                x: root.framed ? 10 : 0
                width: parent.width - x
                Text {
                    objectName: "exampleMeta"
                    width: parent.width
                    textFormat: Text.RichText
                    text: W.exampleMeta(root.example, root.changes, true, W.cssColor(Theme.accentText))
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
                Text {
                    objectName: "exampleText"
                    width: parent.width
                    textFormat: root.example.names && root.example.names.length ? Text.RichText : Text.PlainText
                    text: root.example.names && root.example.names.length ? W.exampleHtml(root.example, W.cssColor(Theme.accentSoft), W.cssColor(Theme.accentText)) : (root.example.text || "")
                    color: root.example.narration ? Theme.text2 : Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                }
            }
        }
        Text {
            objectName: "exampleAfter"
            visible: Boolean(root.example.after)
            width: parent.width
            text: root.example.after || ""
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
            Accessible.description: "Câu liền sau"
        }
    }
}
