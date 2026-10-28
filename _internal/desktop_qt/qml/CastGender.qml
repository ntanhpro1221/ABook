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
    title: "Giới tính của " + shownName
    description: current ? "Hiện đang là nhân vật " + Logic.genderWord(current) + "." : "Máy chưa xác định được giới của người này."

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
        Api.quiet("POST", "/api/books/" + bookId + "/voice", {character: who.name, gender: picked}, function(data, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail("Chưa đổi được giới tính", error); return }
            root.saved()
            root.offerUndo("Đã ghi: " + name + " là nhân vật " + Logic.genderWord(picked), who.name, data ? data.requestedAt : 0,
                           name + " trở lại như trước khi đổi giới tính.")
            root.dismiss()
        })
    }

    Column {
        width: parent.width
        spacing: 12
        ChoiceRow {
            objectName: "genderChoice"
            width: parent.width
            label: "Giới tính"
            value: root.choice
            options: [{value: "male", label: "Nam"}, {value: "female", label: "Nữ"}]
            onPicked: value => root.choice = value
        }
        Text {
            objectName: "genderWaiting"
            visible: root.waiting
            width: parent.width
            text: "Giọng đọc của " + root.shownName + " chưa đổi ngay - Studio sẽ làm khi bạn mở file này ở máy có Studio."
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        // Chưa có câu nào được thu: vẫn nói giọng sẽ đổi - đổi giới là đổi giọng
        Text {
            objectName: "genderNote"
            visible: !root.waiting && root.recorded === 0 && root.person !== null && root.choice !== "" && root.choice !== root.current
            width: parent.width
            text: root.person ? "Nếu giọng " + (Logic.voiceToUse(root.person) ? Logic.voiceToUse(root.person) + " " : "") + "đang đọc " + root.shownName
                + " không hợp giới mới, máy chọn một giọng " + Logic.genderWord(root.choice) + " khác cho người ấy khi áp dụng." : ""
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
        Text {
            objectName: "genderRecorded"
            visible: root.recorded > 0
            width: parent.width
            text: "Áp dụng sẽ thu lại " + Logic.formatNumber(root.recorded) + " câu của " + root.shownName + " nếu giọng chưa hợp giới mới."
            color: Theme.text
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeBodySmall
        }
    }
    footer: [
        EditBookActions {
            width: root.bodyWidth
            Button { objectName: "genderCancel"; text: "Thôi"; kind: "ghost"; onClicked: root.close() }
            Button { objectName: "genderSave"; text: "Ghi lại"; busy: root.saving; enabled: root.choice !== "" && root.choice !== root.current; onActivated: root.save() }
        }
    ]
}
