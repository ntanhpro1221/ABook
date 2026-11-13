import "UiStrings.js" as S
import QtQuick
import ABook
import "CastLogic.js" as Logic

// "Giới tính của …" (GenderDialog của studio/CastEdits.tsx): đi đúng đường của thẻ "Nam hay nữ" (POST /api/books/<id>/voice): một thay đổi chờ áp dụng,
// hoàn tác được. `waiting`: cuốn không có xưởng (file .abook) - chỉ ghi ý muốn chờ Studio, câu nói và việc thu lại không đúng nữa.
CastModal {
    id: root
    panelWidth: 448
    property var person: null
    property bool waiting: false
    property string choice: ""
    readonly property string shownName: person ? Logic.cleanName(person.displayName) : ""
    readonly property string current: Logic.shownGender(person)
    readonly property int recorded: waiting || !person ? 0 : (person.recorded || 0)
    title: S.s_gioi_tinh_cua_762995db + shownName
    description: current ? S.s_hien_dang_la_nhan_vat_e19de586 + Logic.genderWord(current) + "." : S.s_may_chua_xac_dinh_duoc_gioi_cua_nguoi_nay_ea153abc

    function begin(data) {
        generation++
        bookId = data.bookId; person = data.person; waiting = Boolean(data.waiting)
        choice = Logic.shownGender(person); saving = false
        show()
    }
    function save() {
        if (saving || !person || choice === "") return
        saving = true
        const mine = generation
        const who = person, name = shownName, picked = choice
        root.ask("POST", "/api/books/" + bookId + "/voice", {character: who.name, gender: picked}, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail(S.s_chua_doi_duoc_gioi_tinh_4eefcf7a, error); return }
            root.saved()
            root.offerUndo(S.s_da_ghi_85094402 + name + S.s_la_nhan_vat_115df58b + Logic.genderWord(picked), who.name, data ? data.requestedAt : 0,
                           name + S.s_tro_lai_nhu_truoc_khi_doi_gioi_tinh_d5dd930c)
            root.dismiss()
        })
    }

    Column {
        width: parent.width
        spacing: 12
        ChoiceRow {
            objectName: "genderChoice"
            width: parent.width
            label: S.s_gioi_tinh_46eb9a2c
            value: root.choice
            options: [{value: "male", label: S.s_nam_22dd59c8}, {value: "female", label: S.s_nu_e15bc11c}]
            onPicked: value => root.choice = value
        }
        Text {
            objectName: "genderWaiting"
            Reveal { shown: root.waiting }
            width: parent.width
            text: S.s_giong_doc_cua_5e7d06dc + root.shownName + S.s_chua_doi_ngay_studio_se_lam_khi_ban_mo_fil_cc8fd9a5
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        // Chưa có câu nào được thu: vẫn nói giọng sẽ đổi - đổi giới là đổi giọng
        Text {
            objectName: "genderNote"
            Reveal { shown: !root.waiting && root.recorded === 0 && root.person !== null && root.choice !== "" && root.choice !== root.current }
            width: parent.width
            text: root.person ? S.s_neu_giong_14749bed + (Logic.voiceToUse(root.person) ? Logic.voiceToUse(root.person) + " " : "") + S.s_dang_doc_080a360c + root.shownName
                + S.s_khong_hop_gioi_moi_may_chon_mot_giong_889c64ad + Logic.genderWord(root.choice) + S.s_khac_cho_nguoi_ay_khi_ap_dung_094fb017 : ""
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Text {
            objectName: "genderRecorded"
            Reveal { shown: root.recorded > 0 }
            width: parent.width
            text: S.s_ap_dung_se_thu_lai_adf61f2b + Logic.formatNumber(root.recorded) + S.s_cau_cua_35c4143d + root.shownName + S.s_neu_giong_chua_hop_gioi_moi_dce1d351
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "genderCancel"; text: S.s_thoi_e68f9e88; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "genderSave"; text: S.s_ghi_lai_923c1fd4; busy: root.saving; enabled: root.choice !== "" && root.choice !== root.current; onActivated: root.save() }
        }
    ]
}
