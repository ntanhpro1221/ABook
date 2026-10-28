import QtQuick
import ABook
import "StudioLogic.js" as Logic

// "Đổi tên sách" (RenameDialog của ProjectScreen.tsx): chỉ đổi tên HIỆN, thư mục dự án và sổ của dây chuyền giữ nguyên nên làm được cả lúc đang chạy.
// Một ô "Tên sách" điền sẵn tên đang có; "Đổi tên" chỉ bấm được khi tên mới khác tên cũ và không trống. Enter = Đổi tên.
Modal {
    id: root
    panelWidth: 448
    property var store: null
    property var book: ({})
    property string typed: ""
    property bool saving: false
    property int generation: 0
    readonly property bool changed: typed.trim() !== "" && typed.trim() !== (book.title || "")
    title: "Đổi tên sách"
    description: Logic.renameDescription()

    function begin(target) {
        generation++
        book = target; saving = false; typed = target.title || ""
        field.text = typed
        show()
        field.forceActiveFocus(Qt.TabFocusReason)
        field.selectAll()
    }
    function submit() {
        if (saving || !changed || !store) return
        saving = true
        const mine = generation
        store.rename(book.id, typed.trim(), function(ok) {
            if (mine !== root.generation) return
            root.saving = false
            if (ok) root.dismiss()
        })
    }
    onClosed: generation++

    Column {
        width: parent.width
        spacing: 6
        Text { width: parent.width; text: "Tên sách"; color: Theme.text; wrapMode: Text.Wrap; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
        FormField {
            id: field
            objectName: "studioRenameField"
            width: parent.width
            label: "Tên sách"
            topPadding: 8
            bottomPadding: 8
            implicitHeight: Math.max(36, contentHeight + 16)
            onTextChanged: {
                if (text.length > 160) { text = text.slice(0, 160); return }
                root.typed = text
            }
            onAccepted: root.submit()
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "studioRenameCancel"; text: "Huỷ"; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "studioRenameSave"; text: "Đổi tên"; busy: root.saving; enabled: root.changed; onActivated: root.submit() }
        }
    ]
}
