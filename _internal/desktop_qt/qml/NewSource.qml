import "UiStrings.js" as S
import QtQuick
import ABook
import "NewProjectLogic.js" as Logic

// Bước "Nguồn truyện" của trình tạo sách (SourceStep của NewProjectScreen.tsx): chưa có chương nào thì khung chọn / kéo thả (NewDrop); có rồi thì ô Tên sách, các lời nhắn về nguồn (NewHints),
// chia phần (NewVolumes), số chương lạ và dòng ghi công (NewCredits), tổng và danh sách chương (NewChapters). Hộp chọn file của hệ điều hành dựng muộn - chỉ khi bấm lần đầu.
Column {
    id: root
    property var form: null
    property bool dragging: false
    signal projectRequested(string id)
    readonly property var draft: form ? form.draft : ({})
    readonly property bool hasFiles: Boolean(form && form.scan && form.scan.files.length)
    readonly property string title: draft.title || ""

    // Mở hộp chọn: dựng muộn (NewPicker kéo theo FileDialog / FolderDialog)
    function chooseFiles(add) { picker.active = true; if (picker.item) picker.item.chooseFiles(add); else pending = {files: true, add: add} }
    function chooseFolder() { picker.active = true; if (picker.item) picker.item.chooseFolder(); else pending = {files: false, add: false} }
    property var pending: null
    Loader {
        id: picker
        active: false
        sourceComponent: NewPicker {
            sourceHint: root.form && root.form.dialogs && root.draft.seed ? root.draft.seed.folder || "" : ""
            continuing: Boolean(root.draft.seed)
            onPicked: (paths, append) => root.form.picked(paths, append)
        }
        onLoaded: {
            if (!root.pending) return
            if (root.pending.files) item.chooseFiles(root.pending.add); else item.chooseFolder()
            root.pending = null
        }
    }

    Text { objectName: "newSourceTitle"; width: parent.width; text: S.s_nguon_truyen_ddecd9bb; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Prose { topPadding: 4; text: S.s_chon_txt_epub_word_hoac_pdf_co_chu_5e38434f }
    Item { width: 1; height: 12 }
    ImportFold {
        width: parent.width
        storageKey: "formats"
        prefix: "fold.new-project."
        title: S.s_dinh_dang_36b746b6
        Item { width: 1; height: 8 }
        Repeater {
            model: [
                S.s_moi_file_txt_la_mot_chuong_xep_theo_ten_fi_50c79061,
                S.s_epub_word_pdf_co_chu_chon_thang_may_tu_tac_6fe43d31,
                S.s_ca_truyen_nam_trong_mot_file_txt_thi_may_g_67a7c9cb
            ]
            delegate: Item {
                required property string modelData
                width: parent.width
                height: bullet.height + 4
                Text { x: 6; text: "•"; color: Theme.text2; font.pixelSize: Theme.sizeBodySmall }
                Prose { id: bullet; x: 20; width: parent.width - 20; text: modelData }
            }
        }
    }

    // Chưa có chương: khung chọn / kéo thả
    Collapse {
        width: parent.width
        open: !root.hasFiles
        NewDrop {
            objectName: "newDrop"
            width: parent.width
            form: root.form
            dragging: root.dragging
            onFolderRequested: root.chooseFolder()
            onFilesRequested: root.chooseFiles(false)
        }
    }
    // Có chương
    Collapse {
        width: parent.width
        open: root.hasFiles
        Column {
            width: parent.width
            topPadding: 24
            Text { width: parent.width; text: S.s_ten_sach_d54846eb; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Item { width: 1; height: 6 }
            FormField {
                id: titleField
                objectName: "newTitleField"
                width: parent.width
                label: S.s_ten_sach_d54846eb
                placeholderText: S.s_ten_hien_thi_trong_thu_vien_c48c7ac6
                invalid: root.title.trim() === ""
                text: root.title
                font.weight: Theme.weightMedium
                onTextChanged: if (text !== root.title) root.form.update({title: text, titleEdited: true})
            }
            Collapse {
                width: parent.width
                open: root.title.trim() === ""
                Prose { objectName: "newTitleProblem"; topPadding: 4; small: true; tone: Theme.danger; text: S.s_sach_can_co_ten_de_hien_trong_thu_vien_49495e92 }
            }
            NewHints { width: parent.width; form: root.form; onProjectRequested: id => root.projectRequested(id) }
            // Gợi ý chia phần đứng TRƯỚC lời nhắc số chương: truyện nhiều tập đánh số lại từ 1 ở mỗi tập, lời nhắc "trùng số" chỉ là hệ quả của việc chưa chia
            NewVolumes { width: parent.width; form: root.form }
            NewCredits { width: parent.width; form: root.form }
            NewChapters { width: parent.width; form: root.form; onFilesRequested: root.chooseFiles(true) }
        }
    }
}
