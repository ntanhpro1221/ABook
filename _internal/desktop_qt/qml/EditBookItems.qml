import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// Các mục sửa sách trong menu "Thêm" của trang sách (BookScreen.tsx + EditBookItems của listen/EditBook.tsx): "Sửa thông tin", "Lưu thay đổi",
// "Lưu thành…" khi cuốn sửa được ở máy này; cuốn không sửa được (của điện thoại chia sẻ thư viện) và việc cần Studio VẪN HIỆN, mờ đi và nói rõ
// vì sao hay thiếu gì - không giấu ("explain, never hide"). `book`: cuốn đầy đủ của `GET /api/listen/books/<mã>`.
Column {
    id: root
    property var book: ({})
    property bool remoteEdit: false          // Studio từ xa: chỉ những sửa chữ / bìa / nhạc nền chạy được
    property bool saving: false
    readonly property var caps: book.capabilities
    readonly property bool editable: Logic.canEditLayer(caps)
    readonly property bool syncs: Logic.syncsToComputer(caps)
    readonly property bool workshop: Boolean(caps && caps.workshop)
    readonly property string need: Logic.studioNeed(caps) || ""
    readonly property bool hasItems: editable || Logic.editBlockedNote(caps) !== null || (need !== "" && book.stage !== "text")
    readonly property bool showSave: editable && !remoteEdit && !workshop && !syncs && !(caps && caps.local)
    readonly property bool showBlocked: !remoteEdit && Logic.editBlockedNote(caps) !== null
    readonly property bool showStudio: !remoteEdit && need !== "" && book.stage !== "text"
    // Cao đúng tổng các hàng đang hiện: bảng nổi đo chỗ (mở lên hay xuống) ngay lúc mở, khi Column chưa kịp xếp và (vì bảng còn ẩn)
    // `visible` của hàng đọc ra false
    height: (editable ? edit.implicitHeight : 0) + (showSave ? save.implicitHeight + saveAs.implicitHeight : 0)
            + (showBlocked ? blocked.implicitHeight : 0) + (showStudio ? studioOnly.implicitHeight : 0)
    signal editRequested()
    signal saveRequested()
    signal saveAsRequested()

    component NoteRow: Item {
        id: note
        property string icon: ""
        property string label: ""
        property string caption: ""
        width: root.width
        implicitHeight: words.height + 12
        height: implicitHeight
        opacity: 0.6
        Accessible.role: Accessible.StaticText
        Accessible.name: label + ". " + caption
        Icon { x: Theme.s8; y: 6 + 2; name: note.icon; size: 16; color: Theme.text2 }
        Column {
            id: words
            x: Theme.s8 + 16 + Theme.s12
            y: 6
            width: parent.width - x - Theme.s8
            Text { width: parent.width; text: note.label; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            Text { width: parent.width; text: note.caption; color: Theme.text3; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeCaption }
        }
    }

    MenuRow {
        id: edit
        objectName: "menuEdit"
        width: parent.width
        visible: root.editable
        height: root.editable ? implicitHeight : 0
        text: "Sửa thông tin"
        icon: "pencil"
        onClicked: root.editRequested()
    }
    MenuRow {
        id: save
        objectName: "menuSave"
        width: parent.width
        visible: root.showSave
        height: root.showSave ? implicitHeight : 0
        enabled: Boolean(root.book.unsaved !== undefined ? root.book.unsaved : root.book.edits) && !root.saving
        opacity: enabled ? 1 : 0.5
        text: "Lưu thay đổi"
        icon: "save"
        onClicked: if (enabled) root.saveRequested()
    }
    MenuRow {
        id: saveAs
        objectName: "menuSaveAs"
        width: parent.width
        visible: root.showSave
        height: root.showSave ? implicitHeight : 0
        text: "Lưu thành…"
        icon: "file-down"
        onClicked: root.saveAsRequested()
    }
    NoteRow {
        id: blocked
        objectName: "menuBlocked"
        visible: root.showBlocked
        height: root.showBlocked ? implicitHeight : 0
        icon: "pencil"
        label: "Sửa thông tin"
        caption: "Sửa ở máy gốc."
    }
    NoteRow {
        id: studioOnly
        objectName: "menuStudioOnly"
        visible: root.showStudio
        height: root.showStudio ? implicitHeight : 0
        icon: "wrench"
        label: "Giọng và lời đọc"
        caption: root.syncs ? "Làm ở Studio trên máy tính" : root.need.charAt(0).toUpperCase() + root.need.slice(1)
    }
}
