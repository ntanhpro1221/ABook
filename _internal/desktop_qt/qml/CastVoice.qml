import "UiStrings.js" as S
import QtQuick
import ABook
import "CastLogic.js" as Logic
import "TextWrap.js" as TextWrap

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
    // "Nghe thử bằng câu của sách" làm ở VoiceTry (dùng chung với hộp "Áp dụng"): khoá bản đang chờ máy thu, dòng dưới ô lọc, bản vừa phát theo khoá giọng
    property alias asking: voiceTry.asking
    property alias said: voiceTry.said
    property alias tried: voiceTry.tried
    readonly property string shownName: person ? (person.displayName || (choices ? choices.character.label : "")) : ""
    readonly property bool narrator: choices !== null && choices.character.value === "NARRATOR"
    readonly property string currentGender: {
        const voices = choices ? choices.voices : []
        for (const voice of voices) if (voice.current) return voice.gender
        return ""
    }
    readonly property string shownGender: filter !== "" ? filter : currentGender !== "" ? currentGender : choices && choices.character.gender === "female" ? "female" : "male"
    readonly property var groups: choices ? Logic.groupByEngine(Logic.byGender(choices.voices, shownGender)) : []
    readonly property var labels: Logic.groupLabels(groups)
    title: S.s_giong_cua_851e2a41 + (person ? person.displayName : "")
    description: choices ? Logic.formatNumber(choices.character.lines) + S.s_cau_o_b6fbfb19 + choices.character.chapters + S.s_chuong_u00a0_u00a0dang_doc_bang_dd5c355e + (choices.current || S.s_chua_co_giong_93574f94) : ""
    keepOpen: function() { if (root.crossing) { root.crossing = null; return true } return false }
    onClosed: { Clip.stop(); voiceTry.reset() }
    VoiceTry { id: voiceTry; store: root.store; bookId: root.bookId }

    function begin(info) {
        generation++
        bookId = info.bookId; person = info.person
        choices = null; status = "loading"; filter = ""; crossing = null; saving = false
        voiceTry.reset()
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
    function tryKey(voice) { return voiceTry.key(tryRequest(voice)) }
    function tryVoice(voice) {
        // Người chưa có câu nào: phát câu mẫu chung của giọng
        voiceTry.ask(tryRequest(voice), voice.name, voice.key, voice.preview ? function() { Clip.toggle(Logic.voiceId(voice.name), media(Logic.voiceUrl(voice.key))) } : null)
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
            if (error) { root.fail(S.s_chua_doi_duoc_giong_5b5ed91f, error); return }
            root.saved()
            root.offerUndo(S.s_da_ghi_85094402 + name + S.s_doc_bang_giong_3ab6963c + voice.name + (withGender ? S.s_va_la_dde34d8d + Logic.genderWord(voice.gender) : ""),
                           info.character.value, answer ? answer.requestedAt : 0,
                           S.s_giong_e2c28b04 + (withGender ? S.s_va_gioi_c20b236e : "") + S.s_cua_ae306eb2 + name + S.s_tro_lai_nhu_truoc_khi_doi_1e8c9d3d)
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
            if (error) { root.fail(S.s_chua_bo_duoc_lua_chon_c0844396, error); return }
            root.saved()
            Api.notice = info.pending.name ? S.s_da_bo_lua_chon_ebd5d466 + info.pending.name : S.s_da_bo_lua_chon_giong_1aff3c76
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
                Accessible.name: S.s_dang_tai_giong_doc_ac8359a5
                SequentialAnimation {
                    running: skeleton.visible && Nav.uiVisible && !Theme.reduceMotion
                    loops: Animation.Infinite
                    OpacityAnimator { target: skeleton; from: 1; to: Theme.skeletonLow; duration: Theme.skeletonHalf; easing.type: Easing.InOutSine }
                    OpacityAnimator { target: skeleton; from: Theme.skeletonLow; to: 1; duration: Theme.skeletonHalf; easing.type: Easing.InOutSine }
                }
                Repeater { model: 4; Rectangle { width: skeleton.width; height: 48; radius: Theme.radiusCover; color: Theme.line } }
            }
        }
        // Không hỏi được danh sách giọng
        InlineError {
            objectName: "voiceFailed"
            width: parent.width
            open: root.status === "failed"
            message: S.s_ban_hay_kiem_tra_ket_noi_roi_tai_lai_danh_a542de69
            onRetry: { root.status = "loading"; root.load(false) }
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
                            text: TextWrap.keepDots(root.choices && root.choices.pending ? S.s_cho_ap_dung_doi_sang_d280f3e4 + (root.choices.pending.name || S.s_giong_khac_95c40f55) : "")
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Button {
                            objectName: "voiceKeep"
                            text: S.s_giu_d3777f80 + (root.choices ? (root.choices.current || S.s_giong_dang_dung_4e5460a7) : "")
                            size: "sm"; kind: "ghost"; wrap: true
                            enabled: !root.saving
                            onClicked: root.keep()
                        }
                    }
                }
                Text {
                    Reveal { shown: root.choices !== null && !!root.choices.rerecord }
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
                                ? root.shownName + S.s_dang_la_8bd58298 + Logic.genderWord(root.choices.character.gender) + S.s_giong_b5e0ec31 + crossingBox.keptVoice.name + S.s_la_giong_a07d5815
                                    + Logic.genderWord(crossingBox.keptVoice.gender) + S.s_doi_ca_gioi_cua_a6dfa69e + root.shownName + S.s_thanh_3acad264 + Logic.genderWord(crossingBox.keptVoice.gender) + "?" : ""
                            color: Theme.text
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeBodySmall
                        }
                        Flow {
                            width: parent.width
                            spacing: 8
                            Button { objectName: "voiceCrossGender"; text: S.s_doi_giong_va_gioi_21985f64; size: "sm"; busy: root.saving; onActivated: root.save(root.crossing, true) }
                            Button { objectName: "voiceCrossKeep"; text: S.s_giu_nhu_cu_4fecf996; size: "sm"; kind: "ghost"; enabled: !root.saving; onClicked: root.crossing = null }
                        }
                    }
                }
                ChoiceRow {
                    objectName: "voiceGenderFilter"
                    width: parent.width
                    label: S.s_loc_giong_theo_gioi_93d59ab4
                    value: root.shownGender
                    options: [{value: "male", label: S.s_nam_22dd59c8}, {value: "female", label: S.s_nu_e15bc11c}, {value: "all", label: S.s_tat_ca_49c73a31}]
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
                            Reveal { shown: Logic.groupHasHeader(root.groups, group.modelData) }
                            width: parent.width
                            engine: group.modelData.engine
                            label: root.labels[group.index] || ""
                            initial: root.choices && root.choices.modules ? (root.choices.modules[group.modelData.engine] || null) : null
                            onReady: root.load(true)
                        }
                        Text {
                            objectName: "voiceGroup"
                            Reveal { shown: !Logic.groupHasHeader(root.groups, group.modelData) }
                            width: parent.width
                            topPadding: 4
                            text: root.labels[group.index] || ""
                            color: Theme.text3
                            wrapMode: Text.Wrap
                            font.pixelSize: Theme.sizeCaption
                            font.weight: Theme.weightMedium
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
                                    Reveal { shown: row.voice.preview }
                                    clipId: Logic.voiceId(row.voice.name)
                                    url: root.media(Logic.voiceUrl(row.voice.key))
                                    label: S.s_nghe_thu_giong_d06e1a82 + row.voice.name
                                }
                                // "Nghe thử bằng câu của sách": một câu của chính người này đọc bằng giọng ấy (chỉ khi người ấy có câu)
                                CastSample {
                                    id: tryButton
                                    objectName: "voiceTry"
                                    x: 44
                                    anchors.verticalCenter: parent.verticalCenter
                                    Reveal { shown: Boolean(root.choices.tryLine) }
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
                                    spacing: 4
                                    Flow {
                                        width: parent.width
                                        spacing: 8
                                        Text {
                                            width: Math.min(implicitWidth, parent.width)
                                            text: TextWrap.keepDots(row.voice.name)
                                            color: row.voice.current ? Theme.accentText : Theme.text
                                            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                            font.pixelSize: Theme.sizeBodySmall
                                            font.weight: Theme.weightMedium
                                        }
                                        Text {
                                            Reveal { shown: Boolean(row.voice.current && root.choices.pending) }
                                            text: S.s_dang_dung_275ca289
                                            color: Theme.accentText
                                            font.pixelSize: 12
                                            font.weight: Theme.weightMedium
                                        }
                                        Text {
                                            Reveal { shown: Boolean(row.voice.pending && !row.voice.current) }
                                            text: S.s_cho_ap_dung_77a52853
                                            color: Theme.warning
                                            font.pixelSize: 12
                                            font.weight: Theme.weightMedium
                                        }
                                        Text {
                                            Reveal { shown: Boolean(row.voice.suggested && !row.voice.current && !row.voice.pending) }
                                            text: S.s_may_goi_y_1e7f4cfa
                                            color: Theme.text2
                                            font.pixelSize: 12
                                            font.weight: Theme.weightMedium
                                        }
                                    }
                                    Text {
                                        width: parent.width
                                        text: Logic.voiceMeta(row.voice, root.shownGender === "all")
                                        Reveal { shown: target.text !== "" }
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
                                    text: row.voice.current && root.choices.pending ? S.s_giu_giong_nay_2bc52cde : Logic.voiceAction(row.voice)
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
                    text: root.narrator ? S.s_doi_giong_se_thu_lai_loi_ke_3d190924 : S.s_nghe_thu_truoc_khi_doi_giong_9d5e986a
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: Theme.sizeCaption
                }
                // Vì sao (MoreInfo của VoicePicker.tsx): người kể cần giọng riêng; giọng thêm có thể làm hai nhân vật nghe giống nhau
                MoreInfo {
                    objectName: "voiceMoreInfo"
                    width: parent.width
                    label: root.narrator ? S.s_tim_hieu_them_032fe408 : S.s_dung_chung_giong_ccea62a1
                    HintText {
                        width: parent.width
                        text: root.narrator ? S.s_nguoi_ke_can_giong_rieng_nen_khong_chon_gi_c145ea51
                                            : S.s_giong_them_co_the_khien_hai_nhan_vat_nghe_ec79eba6
                    }
                }
            }
        }
    }
}
