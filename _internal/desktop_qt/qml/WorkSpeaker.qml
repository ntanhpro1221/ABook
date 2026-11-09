import "UiStrings.js" as S
import QtQuick
import ABook
import "WorkLogic.js" as W

// Gán người nói (SpeakerFix): một câu ("Ai nói câu này", người gọi) hay mọi câu của một vai phụ - mỗi ứng viên một nút, người máy nghi nhất đứng đầu (gạch chân). Ghi xong là xong
// phần người; dây chuyền gán câu cho người ấy ở ranh giới chương, câu đã thu thì thu lại. "Người khác…" mở ô gõ tên + giới cho người máy chưa từng gán câu nào.
Column {
    id: root
    property var work: null
    property var item: ({})
    property string scope: "alternate"
    property bool scoped: false                 // thẻ có hai phạm vi (câu xen kẽ / cả chuỗi)
    property var picked: null                   // thẻ vai phụ cả cuốn: các câu còn chọn
    property bool scriptLinks: false
    property bool voicePick: false
    property bool creating: false
    property bool busy: false
    signal scopeChosen(string scope)
    signal openScript(int chapterId, string stableId, bool pick)
    signal pickVoice(var person)

    readonly property var lines: picked ? picked : (scope === "all" && item.allLines ? item.allLines : item.lines)
    readonly property bool none: !lines || lines.length === 0
    readonly property var shown: W.shownChoices(item)
    readonly property var more: W.moreChoices(item)
    readonly property string sample: W.sampleName(item)
    readonly property string typed: nameField.text.trim()

    function choose(request) {
        if (busy) return
        busy = true
        work.saveSpeaker(item, lines, scope, request, function() { root.busy = false })
    }
    function keepAll() {
        if (busy) return
        busy = true
        work.keepAllSpeakers(item, W.keepRequests(item), function() { root.busy = false })
    }
    onCreatingChanged: if (creating) Later.call(root, function() { nameField.forceActiveFocus() })

    spacing: 0
    Item { width: 1; height: 12 }
    WorkRequested {
        width: parent.width
        text: root.item.requested ? W.speakerAppliedLine(root.item, root.work.pendingNote) : ""
    }
    Collapse {
        width: parent.width
        open: root.scoped
        Item {
            width: parent.width
            height: scopeRow.height + scopeText.height + 12
            Flow {
                id: scopeRow
                width: parent.width
                spacing: 8
                Text { height: 40; verticalAlignment: Text.AlignVCenter; text: S.s_doi_nguoi_noi_cho_214fb622; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                ChoiceRow {
                    objectName: "workScope"
                    label: S.s_doi_nguoi_noi_cho_nhung_cau_nao_88602af5
                    value: root.scope
                    options: root.item.allLines && root.item.lines ? [
                        {value: "alternate", label: (root.item.scopeLabels ? root.item.scopeLabels[0] : S.s_cau_xen_ke_a9442401) + "\u00a0·\u00a0" + root.item.lines.length},
                        {value: "all", label: (root.item.scopeLabels ? root.item.scopeLabels[1] : S.s_ca_chuoi_2a2c3bbf) + "\u00a0·\u00a0" + root.item.allLines.length}
                    ] : []
                    onPicked: value => root.scopeChosen(value)
                }
            }
            Text {
                id: scopeText
                y: scopeRow.height + 4
                width: parent.width
                text: W.scopeNote(root.item)
                color: Theme.text3
                wrapMode: Text.Wrap
                font.pixelSize: Theme.sizeCaption
            }
        }
    }
    Flow {
        id: chips
        objectName: "workChips"
        width: parent.width
        spacing: 6
        Repeater {
            model: root.shown
            delegate: DecisionButton {
                required property var modelData
                required property int index
                text: modelData.label
                marked: W.chipMarked(root.item, modelData, index)
                enabled: !root.busy && !root.none
                onClicked: root.choose({speaker: modelData.value})
            }
        }
        DecisionButton {
            objectName: "speakerKeep"
            visible: Boolean(root.item.currentValue)
            text: W.keepButtonLabel(root.item)
            enabled: !root.busy
            onClicked: root.choose({speaker: root.item.currentValue})
        }
        // Vai phụ ngôi ba (lính gác) không phải ai trong danh sách - cả nhóm có thể là MỘT người mới, có giọng riêng
        DecisionButton {
            objectName: "speakerNew"
            visible: Boolean(root.item.newPerson)
            text: root.item.newPersonLabel || S.s_tao_nhan_vat_18e9a09a
            enabled: !root.busy && !root.none
            onClicked: root.choose({speaker: root.item.newPerson, newGender: "unknown"})
        }
        DecisionButton {
            objectName: "speakerKeepGroups"
            visible: Boolean(root.item.keepGroups) && root.item.keepGroups.length > 0
            text: root.item.keepLabel || S.s_giu_nguyen_1b550a12
            enabled: !root.busy
            onClicked: root.keepAll()
        }
        Button {
            objectName: "speakerVoice"
            visible: root.voicePick && root.item.kind === "unnamed" && Boolean(root.item.pickVoice)
            size: "sm"
            kind: "ghost"
            text: S.s_gioi_giong_a5c7c7b7
            onClicked: root.pickVoice(root.item.pickVoice)
        }
        // Thẻ "một người hai tên" hỏi hai tên có phải một người - chọn người thứ ba lạc chủ đề
        Button {
            objectName: "speakerOther"
            visible: root.item.kind !== "alias"
            size: "sm"
            kind: "ghost"
            icon: root.item.suggestedName || root.item.kind === "caller" ? "" : "user-plus"
            text: root.item.suggestedName ? S.s_dat_ten_519d84a1 : S.s_nguoi_khac_36be042b
            Accessible.description: root.creating ? S.s_dang_mo_98235c77 : S.s_dang_dong_4886d4e7
            onClicked: root.creating = !root.creating
        }
        // Thẻ chỉ gợi vài người; tab Kịch bản tìm được mọi nhân vật trong sách - mở đúng câu này ở đó
        Button {
            objectName: "speakerFind"
            visible: root.scriptLinks && Boolean(root.item.lines) && root.item.lines.length === 1 && Boolean(root.item.examples) && root.item.examples.length > 0
            size: "sm"
            kind: "ghost"
            icon: "search"
            text: S.s_tim_nguoi_khac_ebe0232b
            onClicked: root.openScript(root.item.examples[0].chapterId, root.item.lines[0].stableId, true)
        }
        // Thẻ nhóm chỉ in vài câu làm ví dụ: đọc đủ ngữ cảnh ở tab Kịch bản trước khi quyết, mở đúng chương, tại câu đầu của nhóm
        Button {
            objectName: "speakerRead"
            visible: root.scriptLinks && Boolean(root.item.lines) && Boolean(root.item.examples) && root.item.lines.length > root.item.examples.length && root.item.examples.length > 0
            size: "sm"
            kind: "ghost"
            icon: "search"
            text: root.item.lines ? S.s_xem_e7ed16f8 + root.item.lines.length + S.s_cau_b07e1008 : ""
            onClicked: root.openScript(root.item.examples[0].chapterId, root.item.lines[0].stableId, false)
        }
    }
    Collapse {
        objectName: "speakerCreate"
        width: parent.width
        open: root.creating
        Item {
            width: parent.width
            height: createBox.height + 8
            Column {
                id: createBox
                y: 8
                width: parent.width
                spacing: 6
                Flow {
                    width: parent.width
                    spacing: 6
                    visible: root.more.length > 0
                    Accessible.role: Accessible.Grouping
                    Accessible.name: S.s_nhung_nguoi_khac_trong_sach_43124252
                    Repeater {
                        model: root.more
                        delegate: Button {
                            required property var modelData
                            size: "sm"
                            kind: "ghost"
                            text: modelData.label
                            enabled: !root.busy && !root.none
                            onClicked: root.choose({speaker: modelData.value})
                        }
                    }
                    Text { height: 40; verticalAlignment: Text.AlignVCenter; text: S.s_hay_dat_ten_mot_nguoi_moi_10597c08; color: Theme.text3; font.pixelSize: Theme.sizeCaption }
                }
                Flow {
                    width: parent.width
                    spacing: 6
                    Item {
                        width: Math.min(createBox.width, 240)
                        height: 40
                        WorkField {
                            id: nameField
                            objectName: "speakerName"
                            y: 4
                            width: parent.width
                            label: S.s_ten_nguoi_noi_moi_9be83401
                            text: root.item.suggestedName || ""
                            placeholderText: root.sample ? S.s_ten_nguoi_noi_vd_e8a70692 + root.sample + ")" : S.s_ten_nguoi_noi_d3caf277
                            onTextChanged: if (text.length > 80) text = text.slice(0, 80)
                        }
                    }
                    Text { height: 40; verticalAlignment: Text.AlignVCenter; text: S.s_gioi_bam_de_luu_e314c934; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
                    Repeater {
                        model: [{gender: "male", label: S.s_nam_22dd59c8}, {gender: "female", label: S.s_nu_e15bc11c}, {gender: "unknown", label: S.s_khong_ro_8af7da78}]
                        delegate: Button {
                            required property var modelData
                            objectName: "speakerGender_" + modelData.gender
                            size: "sm"
                            kind: "ghost"
                            text: modelData.label
                            enabled: root.typed !== "" && !root.busy && !root.none
                            Accessible.name: S.s_luu_nguoi_noi_moi_gioi_32008e47 + modelData.label.toLowerCase()
                            onClicked: root.choose({speaker: root.typed, newGender: modelData.gender})
                        }
                    }
                }
            }
        }
    }
}
