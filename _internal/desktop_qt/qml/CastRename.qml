import QtQuick
import ABook
import "CastLogic.js" as Logic

// "Đổi tên {người}" (RenamePersonDialog của studio/CastEdits.tsx): chỉ là cái tên trên màn hình (POST /api/books/<id>/characters/rename) - giọng và audio
// không đổi, có hiệu lực ngay. "Về tên gốc" gửi tên rỗng.
CastModal {
    id: root
    panelWidth: 448
    property var person: null
    property string typed: ""
    readonly property string shownName: person ? Logic.cleanName(person.displayName) : ""
    title: "Đổi tên " + shownName
    description: "Chỉ đổi tên hiển thị, giữ giọng và audio."

    function begin(data) {
        generation++
        bookId = data.bookId; person = data.person; saving = false
        typed = Logic.cleanName(person.displayName)
        nameField.text = typed
        show()
        nameField.forceActiveFocus(Qt.TabFocusReason)
        nameField.selectAll()
    }
    function save(next) {
        if (saving || !person) return
        saving = true
        const mine = generation
        Api.quiet("POST", "/api/books/" + bookId + "/characters/rename", {character: person.name, name: next}, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail("Chưa đổi được tên", error); return }
            root.saved()
            Api.notice = data && data.renamed ? "Đã đổi tên thành " + Logic.cleanName(data.name) : "Đã trở về tên gốc: " + Logic.cleanName(data ? data.name : "")
            root.dismiss()
        })
    }
    function submit() { if (typed.trim()) save(typed) }

    Column {
        width: parent.width
        spacing: 8
        FormField {
            id: nameField
            objectName: "personName"
            width: parent.width
            label: "Tên mới của " + root.shownName
            onTextChanged: {
                if (text.length > 80) { text = text.slice(0, 80); return }
                root.typed = text
            }
            onAccepted: root.submit()
        }
        Text {
            visible: !!(root.person && root.person.originalName)
            width: parent.width
            text: "Tên gốc: " + (root.person ? Logic.cleanName(root.person.originalName) : "")
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "personNameOriginal"; visible: !!(root.person && root.person.originalName); text: "Về tên gốc"; kind: "ghost"; enabled: !root.saving; onClicked: root.save("") }
            Button { objectName: "personNameCancel"; text: "Thôi"; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "personNameSave"; text: "Lưu"; busy: root.saving; enabled: root.typed.trim() !== ""; onActivated: root.submit() }
        }
    ]
}
