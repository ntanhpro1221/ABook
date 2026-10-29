import QtQuick
import ABook
import "TellerLogic.js" as T

// Dưới hàng "Người kể chuyện" của tab Nhân vật trong Studio (NarratorNote + TellerModeSwitch của ProjectScreen.tsx): nói đổi giọng kể ở đâu hay vì sao chưa đổi được, rồi công tắc
// "Nhân vật tự kể". Cuốn chưa chạy thì có đường tắt "Đổi giọng kể" mở lại trình tạo (redoRequested).
Column {
    id: root
    objectName: "castNote"
    property var store: null
    property var book: null
    signal redoRequested()
    readonly property var note: book ? T.narratorNote(book) : ({text: "", link: ""})
    topPadding: 8

    Text {
        objectName: "narratorNote"
        width: parent.width
        textFormat: Text.StyledText
        text: root.note.text + (root.note.link ? " <a href=\"redo\">" + root.note.link + "</a>" : "")
        linkColor: Theme.accentText
        color: Theme.text2
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeCaption
        onLinkActivated: root.redoRequested()
        HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
    }
    TellerMode {
        store: root.store
        book: root.book
    }
}
