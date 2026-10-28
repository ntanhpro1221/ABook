import QtQuick
import ABook
import "CastLogic.js" as Logic

// "Giọng của …" (VoicePicker của studio/VoicePicker.tsx): mọi giọng dùng được cho một nhân vật (hay người kể), nghe thử từng giọng, giọng đang dùng, giọng máy
// gợi ý, ai đang dùng giọng ấy; chọn xong đi đúng đường của thẻ "Nam hay nữ" (POST /api/books/<id>/voice). Đổi giọng khác giới với nhân vật thì hỏi ngay trong
// hộp (đổi cả giới). Chưa làm: tải thêm mô-đun giọng của máy đọc khác và "Nghe thử bằng câu của sách" - việc của Studio.
CastModal {
    id: root
    panelWidth: 560
    property var person: null
    property var choices: null                 // lời đáp GET /api/books/<id>/voices?character=...
    property string status: "loading"       // loading | ready | failed
    property string filter: ""              // "" = theo giới của nhân vật
    property var crossing: null             // giọng khác giới đang chờ xác nhận
    readonly property string shownName: person ? (person.displayName || (choices ? choices.character.label : "")) : ""
    readonly property bool narrator: choices !== null && choices.character.value === "NARRATOR"
    readonly property string currentGender: {
        const voices = choices ? choices.voices : []
        for (const voice of voices) if (voice.current) return voice.gender
        return ""
    }
    readonly property string shown: filter !== "" ? filter : currentGender !== "" ? currentGender : choices && choices.character.gender === "female" ? "female" : "male"
    readonly property var groups: choices ? Logic.groupByEngine(Logic.byGender(choices.voices, shown)) : []
    readonly property var labels: Logic.groupLabels(groups)
    title: "Giọng của " + (person ? person.displayName : "")
    description: choices ? Logic.formatNumber(choices.character.lines) + " câu ở " + choices.character.chapters + " chương · đang đọc bằng " + (choices.current || "chưa có giọng") : ""
    keepOpen: function() { if (root.crossing) { root.crossing = null; return true } return false }
    onClosed: Clip.stop()

    function begin(info) {
        generation++
        bookId = info.bookId; person = info.person
        choices = null; status = "loading"; filter = ""; crossing = null; saving = false
        show()
        load()
    }
    function load() {
        const mine = generation
        Api.quiet("GET", "/api/books/" + bookId + "/voices?character=" + encodeURIComponent(person.name), null, function(answer, error) {
            if (mine !== root.generation) return
            if (error || !answer || !answer.character) { root.status = "failed"; return }
            root.choices = answer
            root.status = "ready"
        })
    }
    // Chọn một giọng: cùng giới (hay chưa biết giới) ghi luôn; khác giới thì hỏi trước. Người kể không có giới để đổi.
    function choose(voice) {
        const known = choices.character.gender
        if (!narrator && (known === "male" || known === "female") && known !== voice.gender) crossing = voice
        else save(voice, false)
    }
    function save(voice, withGender) {
        if (saving || !choices) return
        saving = true
        const mine = generation
        const info = choices, name = shownName || info.character.label
        const body = {character: info.character.value, preset: voice.key, seen: info.pending ? info.pending.requestedAt : 0}
        if (withGender) body.gender = voice.gender
        Api.quiet("POST", "/api/books/" + bookId + "/voice", body, function(answer, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail("Chưa đổi được giọng", error); return }
            root.saved()
            root.offerUndo("Đã ghi: " + name + " đọc bằng giọng " + voice.name + (withGender ? " và là " + Logic.genderWord(voice.gender) : ""),
                           info.character.value, answer ? answer.requestedAt : 0,
                           "Giọng" + (withGender ? " và giới" : "") + " của " + name + " trở lại như trước khi đổi.")
            root.dismiss()
        })
    }
    // Bỏ lựa chọn chưa vào sách (POST /voice withdraw, cùng đường "Hoàn tác")
    function keep() {
        if (saving || !choices || !choices.pending) return
        saving = true
        const mine = generation
        const info = choices
        Api.quiet("POST", "/api/books/" + bookId + "/voice", {character: info.character.value, withdraw: true, requestedAt: info.pending.requestedAt}, function(answer, error) {
            if (mine !== root.generation) return
            root.saving = false
            if (error) { root.fail("Chưa bỏ được lựa chọn", error); return }
            root.saved()
            Api.notice = info.pending.name ? "Đã bỏ lựa chọn " + info.pending.name : "Đã bỏ lựa chọn giọng"
            root.dismiss()
        })
    }

    Column {
        width: parent.width
        spacing: 12
        // Đang tải
        Collapse {
            width: parent.width
            open: root.status === "loading"
            Column {
                id: skeleton
                objectName: "voiceSkeleton"
                width: parent.width
                spacing: 8
                Accessible.role: Accessible.Indicator
                Accessible.name: "Đang tải giọng đọc"
                SequentialAnimation {
                    running: skeleton.visible && Nav.uiVisible && !Theme.reduceMotion
                    loops: Animation.Infinite
                    OpacityAnimator { target: skeleton; from: 1; to: 0.6; duration: 800; easing.type: Easing.InOutSine }
                    OpacityAnimator { target: skeleton; from: 0.6; to: 1; duration: 800; easing.type: Easing.InOutSine }
                }
                Repeater { model: 4; Rectangle { width: skeleton.width; height: 48; radius: Theme.radiusCover; color: Theme.line } }
            }
        }
        // Không hỏi được danh sách giọng
        Collapse {
            width: parent.width
            open: root.status === "failed"
            Column {
                width: parent.width
                spacing: 8
                Text {
                    objectName: "voiceFailed"
                    width: parent.width
                    text: "Bạn hãy kiểm tra kết nối rồi tải lại danh sách giọng."
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                Button { objectName: "voiceRetry"; text: "Thử lại"; icon: "rotate-cw"; size: "sm"; kind: "ghost"; onClicked: { root.status = "loading"; root.load() } }
            }
        }
        Collapse {
            width: parent.width
            open: root.status === "ready"
            Column {
                width: parent.width
                spacing: 12
                // Đã chọn giọng khác mà chưa vào sách
                Collapse {
                    width: parent.width
                    open: root.choices !== null && root.choices.pending !== null && root.choices.pending !== undefined
                    Flow {
                        width: parent.width
                        spacing: 8
                        Text {
                            objectName: "voicePending"
                            width: Math.min(implicitWidth, parent.width)
                            text: root.choices && root.choices.pending ? "Chờ áp dụng: đổi sang " + (root.choices.pending.name || "giọng khác") : ""
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Button {
                            objectName: "voiceKeep"
                            text: "Giữ " + (root.choices ? (root.choices.current || "giọng đang dùng") : "")
                            size: "sm"; kind: "ghost"; wrap: true
                            enabled: !root.saving
                            onClicked: root.keep()
                        }
                    }
                }
                Text {
                    visible: root.choices !== null && !!root.choices.rerecord
                    width: parent.width
                    text: root.choices && root.choices.rerecord ? Logic.rerecordText(root.shownName, root.choices.rerecord) : ""
                    color: Theme.text2
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeBodySmall
                }
                // Giọng khác giới với nhân vật: hỏi trước khi ghi
                Collapse {
                    width: parent.width
                    open: root.crossing !== null
                    Column {
                        id: crossingBox
                        objectName: "voiceCrossing"
                        width: parent.width
                        spacing: 8
                        Accessible.role: Accessible.AlertMessage
                        property var keptVoice: null
                        Connections { target: root; function onCrossingChanged() { if (root.crossing) crossingBox.keptVoice = root.crossing } }
                        Text {
                            width: parent.width
                            text: crossingBox.keptVoice && root.choices
                                ? root.shownName + " đang là " + Logic.genderWord(root.choices.character.gender) + " - giọng " + crossingBox.keptVoice.name + " là giọng "
                                    + Logic.genderWord(crossingBox.keptVoice.gender) + ". Đổi cả giới của " + root.shownName + " thành " + Logic.genderWord(crossingBox.keptVoice.gender) + "?" : ""
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Flow {
                            width: parent.width
                            spacing: 8
                            Button { objectName: "voiceCrossGender"; text: "Đổi giọng và giới"; size: "sm"; busy: root.saving; onActivated: root.save(root.crossing, true) }
                            Button { objectName: "voiceCrossKeep"; text: "Giữ như cũ"; size: "sm"; kind: "ghost"; enabled: !root.saving; onClicked: root.crossing = null }
                        }
                    }
                }
                ChoiceRow {
                    objectName: "voiceGenderFilter"
                    width: parent.width
                    label: "Lọc giọng theo giới"
                    value: root.shown
                    options: [{value: "male", label: "Nam"}, {value: "female", label: "Nữ"}, {value: "all", label: "Tất cả"}]
                    onPicked: value => root.filter = value
                }
                Text {
                    width: parent.width
                    text: root.shownName + " chưa có câu nào để đọc thử - nút ▶ là câu mẫu chung của giọng."
                    visible: root.choices !== null && !root.choices.tryLine
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
                Repeater {
                    model: root.groups
                    Column {
                        id: group
                        required property var modelData
                        required property int index
                        width: parent.width
                        spacing: 4
                        Text {
                            objectName: "voiceGroup"
                            width: parent.width
                            topPadding: 4
                            text: root.labels[group.index]
                            color: Theme.text3
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeCaption
                            font.weight: 600
                        }
                        Repeater {
                            model: group.modelData.voices
                            Item {
                                id: row
                                required property var modelData
                                objectName: "voiceChoice"
                                readonly property var voice: modelData
                                width: group.width
                                height: Math.max(48, texts.height + 16)
                                Rectangle {
                                    anchors.fill: parent
                                    radius: Theme.radiusCover
                                    color: Theme.hover
                                    opacity: rowHover.hovered && !row.voice.current ? 1 : 0
                                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                                }
                                HoverHandler { id: rowHover }
                                CastSample {
                                    id: preview
                                    objectName: "voicePreview"
                                    x: 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: row.voice.preview
                                    clipId: Logic.voiceId(row.voice.name)
                                    url: Logic.voiceUrl(row.voice.key)
                                    label: "Nghe thử giọng " + row.voice.name
                                }
                                Column {
                                    id: texts
                                    x: 48
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width - x - action.width - 20
                                    spacing: 2
                                    Flow {
                                        width: parent.width
                                        spacing: 6
                                        Text {
                                            width: Math.min(implicitWidth, parent.width)
                                            text: row.voice.name
                                            color: row.voice.current ? Theme.accentText : Theme.text
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeBodySmall
                                            font.weight: Theme.weightMedium
                                        }
                                        Text {
                                            visible: Boolean(row.voice.current && root.choices.pending)
                                            text: "Đang dùng"
                                            color: Theme.accentText
                                            font.pixelSize: 11
                                            font.weight: Theme.weightMedium
                                        }
                                        Text {
                                            visible: Boolean(row.voice.pending && !row.voice.current)
                                            text: "Chờ áp dụng"
                                            color: Theme.warning
                                            font.pixelSize: 11
                                            font.weight: Theme.weightMedium
                                        }
                                        Text {
                                            visible: Boolean(row.voice.suggested && !row.voice.current && !row.voice.pending)
                                            text: "Máy gợi ý"
                                            color: Theme.text2
                                            font.pixelSize: 11
                                            font.weight: Theme.weightMedium
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: Logic.voiceMeta(row.voice, root.shown === "all")
                                        visible: text !== ""
                                        color: (row.voice.sharedWith || []).length && !(row.voice.takenBy || []).length ? Theme.warning : Theme.text2
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: Theme.sizeCaption
                                    }
                                }
                                Button {
                                    id: action
                                    objectName: "voiceAction"
                                    x: parent.width - width - 4
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 120
                                    size: "sm"
                                    kind: row.voice.current && root.choices.pending ? "ghost" : row.voice.suggested && !row.voice.current && !row.voice.pending ? "primary" : "ghost"
                                    text: row.voice.current && root.choices.pending ? "Giữ giọng này" : Logic.voiceAction(row.voice)
                                    wrap: true
                                    enabled: row.voice.current && root.choices.pending ? !root.saving
                                        : !(row.voice.current || row.voice.pending || !row.voice.installed || (row.voice.takenBy || []).length || root.saving)
                                    onActivated: row.voice.current && root.choices.pending ? root.keep() : root.choose(row.voice)
                                }
                            }
                        }
                    }
                }
                Text {
                    width: parent.width
                    text: root.narrator ? "Đổi giọng sẽ thu lại lời kể." : "Nghe thử trước khi đổi giọng."
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
            }
        }
    }
}
