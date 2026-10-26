import QtQuick
import ABook
import "EditBookLogic.js" as Logic

// "Đổi tên chương" (RenameChapterDialog của listen/EditBook.tsx): nhãn ("Chương 12") và tên ("Hồi kết"); "Về tên gốc" trả lại tên của người làm sách.
// Sách chữ (nhập từ file) chỉ có MỘT tên - dòng đầu chương: một ô "Tên chương" điền sẵn tên đang thấy, lưu thì tên mới thay hẳn (nhãn = tên mới, tên
// phụ trống). Sách Studio giữ hai ô. Là hộp riêng (một lớp Back của chính nó): Back đóng hộp, tiêu điểm về chỗ đã mở.
Modal {
    id: root
    panelWidth: 448
    property var book: ({})
    property var chapter: null
    property string label: ""
    property string name: ""
    property bool saving: false
    property int generation: 0
    readonly property bool single: book.stage === "text" && !(book.capabilities && book.capabilities.workshop)
    title: "Đổi tên chương"
    description: "Chỉ đổi cái tên hiện trên màn hình - audio không đổi."

    function begin(data, chosen) {
        generation++
        book = data; chapter = chosen; saving = false
        label = single ? Logic.chapterShownName(chosen) : (chosen.title || "")
        name = single ? "" : (chosen.subtitle || "")
        show()
        labelField.forceActiveFocus(Qt.TabFocusReason)
    }
    function save(body) {
        if (saving || !chapter) return
        saving = true
        const mine = generation
        Api.call("PUT", "/api/books/" + (book.id || book.bookId) + "/chapters/" + chapter.id + "/title", body, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { Api.notice = Logic.toastText("Chưa đổi được tên chương", error); return }
            Api.editedBook(book.id || book.bookId)
            Api.notice = "Đã đổi tên chương: " + data.fullTitle
            root.dismiss()
        })
    }
    function submit() { if (label.trim()) save({title: label, subtitle: name}) }
    onClosed: generation++

    Column {
        width: parent.width
        spacing: 12
        Column {
            width: parent.width
            spacing: 4
            Text { width: parent.width; text: root.single ? "Tên chương" : "Số chương hay nhãn"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            FormField {
                id: labelField
                objectName: "renameLabel"
                width: parent.width
                label: root.single ? "Tên chương" : "Số chương hay nhãn"
                topPadding: 8
                bottomPadding: 8
                implicitHeight: Math.max(36, contentHeight + 16)
                text: root.label
                onTextChanged: {
                    if (text.length > 160) { text = text.slice(0, 160); return }
                    root.label = text
                }
                onAccepted: root.submit()
            }
        }
        Collapse {
            width: parent.width
            open: !root.single
            Column {
                width: parent.width
                spacing: 4
                Text { width: parent.width; text: "Tên chương (có thể để trống)"; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                FormField {
                    objectName: "renameName"
                    width: parent.width
                    label: "Tên chương (có thể để trống)"
                    topPadding: 8
                    bottomPadding: 8
                    implicitHeight: Math.max(36, contentHeight + 16)
                    text: root.name
                    onTextChanged: {
                        if (text.length > 160) { text = text.slice(0, 160); return }
                        root.name = text
                    }
                    onAccepted: root.submit()
                }
            }
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "renameRevert"; text: "Về tên gốc"; kind: "ghost"; enabled: !root.saving; onClicked: root.save({revert: true}) }
            Button { objectName: "renameCancel"; text: "Thôi"; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "renameSave"; text: "Lưu"; busy: root.saving; enabled: root.label.trim() !== ""; onActivated: root.submit() }
        }
    ]
}
