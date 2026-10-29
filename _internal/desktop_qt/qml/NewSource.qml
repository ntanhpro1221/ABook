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
        sourceComponent: NewPicker { onPicked: (paths, append) => root.form.picked(paths, append) }
        onLoaded: {
            if (!root.pending) return
            if (root.pending.files) item.chooseFiles(root.pending.add); else item.chooseFolder()
            root.pending = null
        }
    }

    Text { objectName: "newSourceTitle"; width: parent.width; text: "Nguồn truyện"; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Prose { topPadding: 4; text: "Chọn TXT, EPUB, Word hoặc PDF có chữ." }
    Item { width: 1; height: 12 }
    ImportFold {
        width: parent.width
        storageKey: "formats"
        prefix: "fold.new-project."
        title: "Định dạng"
        Item { width: 1; height: 8 }
        Repeater {
            model: [
                "Mỗi file TXT là một chương, xếp theo tên file (2 đứng trước 10).",
                "EPUB, Word, PDF (có chữ): chọn thẳng, máy tự tách chương.",
                "Cả truyện nằm trong một file TXT thì máy gợi ý tách theo các dòng “Chương N”."
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
            Text { width: parent.width; text: "Tên sách"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Item { width: 1; height: 6 }
            FormField {
                id: titleField
                objectName: "newTitleField"
                width: parent.width
                label: "Tên sách"
                placeholderText: "Tên hiển thị trong thư viện"
                invalid: root.title.trim() === ""
                text: root.title
                font.weight: Theme.weightMedium
                onTextChanged: if (text !== root.title) root.form.update({title: text, titleEdited: true})
            }
            Collapse {
                width: parent.width
                open: root.title.trim() === ""
                Prose { objectName: "newTitleProblem"; topPadding: 4; small: true; tone: Theme.danger; text: "Sách cần có tên để hiện trong thư viện." }
            }
            NewHints { width: parent.width; form: root.form; onProjectRequested: id => root.projectRequested(id) }
            // Gợi ý chia phần đứng TRƯỚC lời nhắc số chương: truyện nhiều tập đánh số lại từ 1 ở mỗi tập, lời nhắc "trùng số" chỉ là hệ quả của việc chưa chia
            NewVolumes { width: parent.width; form: root.form }
            NewCredits { width: parent.width; form: root.form }
            NewChapters { width: parent.width; form: root.form; onFilesRequested: root.chooseFiles(true) }
        }
    }
}
