import "UiStrings.js" as S
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
    title: S.s_doi_ten_7bbd9ee1 + shownName
    description: S.s_chi_doi_ten_hien_thi_giu_giong_va_audio_1f7110c8

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
        root.ask("POST", "/api/books/" + bookId + "/characters/rename", {character: person.name, name: next}, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail(S.s_chua_doi_duoc_ten_ad5b4df1, error); return }
            root.saved()
            Api.notice = data && data.renamed ? S.s_da_doi_ten_thanh_a1f19e74 + Logic.cleanName(data.name) : S.s_da_tro_ve_ten_goc_8af81ee8 + Logic.cleanName(data ? data.name : "")
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
            label: S.s_ten_moi_cua_b5ff555e + root.shownName
            onTextChanged: {
                if (text.length > 80) { text = text.slice(0, 80); return }
                root.typed = text
            }
            onAccepted: root.submit()
        }
        Text {
            Reveal { shown: !!(root.person && root.person.originalName) }
            width: parent.width
            text: S.s_ten_goc_893370ef + (root.person ? Logic.cleanName(root.person.originalName) : "")
            color: Theme.text2
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "personNameOriginal"; Reveal { shown: !!(root.person && root.person.originalName) } text: S.s_ve_ten_goc_643cd2e0; kind: "ghost"; enabled: !root.saving; onClicked: root.save("") }
            Button { objectName: "personNameCancel"; text: S.s_thoi_e68f9e88; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "personNameSave"; text: S.s_luu_e91f26c0; busy: root.saving; enabled: root.typed.trim() !== ""; onActivated: root.submit() }
        }
    ]
}
