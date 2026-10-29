import QtQuick
import ABook
import "CastLogic.js" as Logic

// "Giọng của …" (VoicePicker của studio/VoicePicker.tsx): mọi giọng dùng được cho một nhân vật (hay người kể), nghe thử từng giọng, giọng đang dùng, giọng máy
// gợi ý, ai đang dùng giọng ấy; chọn xong đi đúng đường của thẻ "Nam hay nữ" (POST /api/books/<id>/voice). Đổi giọng khác giới với nhân vật thì hỏi ngay trong
// hộp (đổi cả giới). Mỗi giọng có thêm nút "Nghe thử bằng câu của sách" (máy thu một câu của chính người này bằng giọng ấy; Logic.heard nhớ bản đã nghe)
// khi người ấy có câu để đọc; nhóm giọng của máy đọc khác có đầu riêng với nút tải giọng (CastEngine).
CastModal {
    id: root
    panelWidth: 560
    property var person: null
    property var choices: null                 // lời đáp GET /api/books/<id>/voices?character=...
    property string status: "loading"       // loading | ready | failed
    property string filter: ""              // "" = theo giới của nhân vật
    property var crossing: null             // giọng khác giới đang chờ xác nhận
    property string asking: ""              // khoá bản nghe thử đang chờ máy thu ("" = không)
    property var said: null                 // {text, status}: dòng dưới ô lọc - máy đang làm gì / đã đọc câu nào / vì sao chưa nghe được
    property var tried: ({})                // bản nghe thử vừa phát theo khoá giọng {khoá: preview}: nút biết bản nào đang ra tiếng
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
        asking = ""; said = null; tried = ({})
        show()
        load(false)
    }
    // `again`: đọc lại danh sách đang hiện (một máy đọc vừa tải xong) mà không đổi sang khung chờ
    function load(again) {
        const mine = generation
        root.ask("GET", "/api/books/" + bookId + "/voices?character=" + encodeURIComponent(person.name), null, function(answer, error) {
            if (mine !== root.generation) return
            if (error || !answer || !answer.character) { if (!again) root.status = "failed"; return }
            root.choices = answer
            root.status = "ready"
        })
    }
    // ---- "Nghe thử bằng câu của sách" (useVoiceTry của VoiceTry.tsx) ----
    function tryRequest(voice) { return {character: choices.character.value, preset: voice.key} }
    function tryKey(voice) { return (store && store.peer ? store.peer + ":" : "") + Logic.tryKey(bookId, tryRequest(voice)) }
    function tryPlay(preview, voice) {
        Clip.toggle(Logic.tryId(preview), media(preview.url))
        tried = Object.assign({}, tried, {[voice.key]: preview})
        said = {text: Logic.previewCaption(preview.text, voice.name), status: false}
    }
    function tryVoice(voice) {
        const key = tryKey(voice)
        const known = Logic.heard[key]
        if (known) { tryPlay(known, voice); return }
        Clip.stop()
        asking = key
        said = {text: Logic.tryAsking(voice.name), status: true}
        const mine = generation
        root.ask("POST", "/api/books/" + bookId + "/voice/preview", tryRequest(voice), function(preview, error, detail) {
            if (mine !== root.generation) return
            root.asking = ""
            if (!error && preview) {
                Logic.heard[key] = preview
                root.tryPlay(preview, voice)
                return
            }
            const reason = detail ? detail.reason : undefined
            // Người chưa có câu nào: phát câu mẫu chung của giọng
            if (reason === "no-line" && voice.preview) {
                Clip.toggle(Logic.voiceId(voice.name), media(Logic.voiceUrl(voice.key)))
                root.said = {text: Logic.NO_LINE, status: true}
                return
            }
            const why = Logic.refusalText(reason, error, Boolean(detail && detail.busyBook))
            root.said = {text: voice.preview ? why + " - nút ▶ vẫn nghe được câu mẫu chung của giọng" : why, status: true}
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
        root.ask("POST", "/api/books/" + bookId + "/voice", body, function(answer, error) {
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
        root.ask("POST", "/api/books/" + bookId + "/voice", {character: info.character.value, withdraw: true, requestedAt: info.pending.requestedAt}, function(answer, error) {
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
                Button { objectName: "voiceRetry"; text: "Thử lại"; icon: "rotate-cw"; size: "sm"; kind: "ghost"; onClicked: { root.status = "loading"; root.load(false) } }
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
                    objectName: "voiceTryHint"
                    width: parent.width
                    text: root.choices ? Logic.tryHint(root.shownName, Boolean(root.choices.tryLine)) : ""
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
                // Máy đang làm gì với câu thử / đã đọc câu nào / vì sao chưa nghe được (giữ chữ cũ lúc dòng khép lại)
                Collapse {
                    width: parent.width
                    open: root.said !== null
                    Text {
                        id: sayText
                        objectName: "voiceTryNote"
                        property var kept: ({text: "", status: false})
                        Connections { target: root; function onSaidChanged() { if (root.said) sayText.kept = root.said } }
                        width: parent.width
                        text: kept.text
                        color: kept.status ? Theme.text2 : Theme.text3
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeCaption
                    }
                }
                Repeater {
                    model: root.groups
                    Column {
                        id: group
                        required property var modelData
                        required property int index
                        width: parent.width
                        spacing: 4
                        // Nhóm của máy đọc khác (hay khi có từ hai nhóm): đầu nhóm có nút tải giọng khi máy đọc ấy chưa có trên máy này
                        CastEngine {
                            objectName: "voiceEngine"
                            store: root.store
                            visible: Logic.groupHasHeader(root.groups, group.modelData)
                            width: parent.width
                            engine: group.modelData.engine
                            label: root.labels[group.index] || ""
                            initial: root.choices && root.choices.modules ? (root.choices.modules[group.modelData.engine] || null) : null
                            onReady: root.load(true)
                        }
                        Text {
                            objectName: "voiceGroup"
                            visible: !Logic.groupHasHeader(root.groups, group.modelData)
                            width: parent.width
                            topPadding: 4
                            text: root.labels[group.index] || ""
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
                                    url: root.media(Logic.voiceUrl(row.voice.key))
                                    label: "Nghe thử giọng " + row.voice.name
                                }
                                // "Nghe thử bằng câu của sách": một câu của chính người này đọc bằng giọng ấy (chỉ khi người ấy có câu)
                                CastSample {
                                    id: tryButton
                                    objectName: "voiceTry"
                                    x: 44
                                    anchors.verticalCenter: parent.verticalCenter
                                    visible: Boolean(root.choices.tryLine)
                                    asks: true
                                    idleIcon: "book-open-text"
                                    readonly property string key: root.tryKey(row.voice)
                                    readonly property var heard: root.tried[row.voice.key]
                                    clipId: heard ? Logic.tryId(heard) : ""
                                    busy: root.asking === key
                                    enabled: row.voice.installed && (root.asking === "" || root.asking === key)
                                    label: Logic.tryLabel(row.voice.name, false)
                                    onRequested: root.tryVoice(row.voice)
                                }
                                Column {
                                    id: texts
                                    x: root.choices.tryLine ? 88 : 48
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
