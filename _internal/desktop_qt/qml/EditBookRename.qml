import "UiStrings.js" as S
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
    title: S.s_doi_ten_chuong_4c534649
    description: S.s_chi_doi_cai_ten_hien_tren_man_hinh_audio_k_da6efdbd

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
            if (error) { Api.notice = Logic.toastText(S.s_chua_doi_duoc_ten_chuong_1ff36fe9, error); return }
            Api.editedBook(book.id || book.bookId)
            Api.notice = S.s_da_doi_ten_chuong_5b029214 + data.fullTitle
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
            Text { width: parent.width; text: root.single ? S.s_ten_chuong_9edb6c28 : S.s_so_chuong_hay_nhan_435a3d6c; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
            FormField {
                id: labelField
                objectName: "renameLabel"
                width: parent.width
                label: root.single ? S.s_ten_chuong_9edb6c28 : S.s_so_chuong_hay_nhan_435a3d6c
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
                Text { width: parent.width; text: S.s_ten_chuong_co_the_de_trong_8224dabe; color: Theme.text2; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall }
                FormField {
                    objectName: "renameName"
                    width: parent.width
                    label: S.s_ten_chuong_co_the_de_trong_8224dabe
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
            Button { objectName: "renameRevert"; text: S.s_ve_ten_goc_643cd2e0; kind: "ghost"; enabled: !root.saving; onClicked: root.save({revert: true}) }
            Button { objectName: "renameCancel"; text: S.s_thoi_e68f9e88; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "renameSave"; text: S.s_luu_e91f26c0; busy: root.saving; enabled: root.label.trim() !== ""; onActivated: root.submit() }
        }
    ]
}
