import QtQuick
import ABook
import "LibraryLogic.js" as Logic

// One compact composition at the grid's leading edge (DESIGN 5.5: complete
// text/action rows <= listMeasure), even when the grid has many columns.
Item {
    id: root
    objectName: "libraryContinue"
    property var book: ({})
    signal openRequested()
    readonly property bool here: Player.loaded && Player.bookId === book.bookId
    readonly property bool waiting: !!Logic.progress(book).caughtUp && !here
    readonly property real measure: Math.min(width, Theme.listMeasure)
    implicitHeight: Math.max(128, copy.implicitHeight)
    CoverView { width: 80; height: 120; title: root.book.title || ""; coverKey: root.book.coverKey || "" }
    Column {
        id: copy
        objectName: "libraryContinueCopy"
        x: 104; width: Math.max(0, root.measure - x - action.width - Theme.s16); spacing: Theme.s8
        Text { text: "Đang nghe"; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        Interactive {
            objectName: "libraryContinueTitle"
            width: parent.width; implicitHeight: title.implicitHeight
            Accessible.role: Accessible.Button
            Accessible.name: title.text
            onClicked: root.openRequested()
            Text {
                id: title
                width: parent.width; text: root.book.title || ""
                wrapMode: Text.Wrap; color: Theme.accentText
                font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium
            }
        }
        Text { width: parent.width; text: root.here ? Player.chapterTitle : root.book.lastChapter || ""; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
        Text { width: parent.width; text: root.book.author || root.book.subtitle || (root.book.source ? "Trên " + root.book.source : ""); color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
    }
    Button {
        id: action; objectName: "libraryContinuePlay"
        x: root.measure - width; anchors.verticalCenter: parent.verticalCenter
        text: root.waiting ? "Chờ chương mới" : (root.here && Player.playing ? "Tạm dừng" : "Nghe tiếp")
        icon: root.waiting ? "" : root.here && Player.playing ? "pause" : "play"
        Accessible.name: root.waiting ? "Chờ chương mới" : root.here && Player.playing ? `Tạm dừng ${root.book.title}` : `Nghe tiếp ${root.book.title}${root.book.lastChapter ? ", " + root.book.lastChapter : ""}`
        enabled: !root.waiting
        onClicked: root.here ? Player.toggle() : Player.playBook(root.book.bookId)
    }
}
