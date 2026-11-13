import "UiStrings.js" as S
import QtQuick
import ABook
import "WorkLogic.js" as W

// Người kể của một ĐOẠN khác người kể "tôi" của sách (NarratorFix): ba lựa chọn - đúng (đoạn không do người ấy kể; đoạn mở bằng dòng tiêu đề góc nhìn thì: do người dòng ấy gọi kể),
// không (giữ nguyên), hay chọn người khác. Lô phân tích chưa chạy sẽ theo lựa chọn; đoạn đã phân tích xong thì chỉ áp khi làm lại sách (thẻ nói rõ).
Column {
    id: root
    property var work: null
    property var item: ({})
    property bool choosing: false
    property bool busy: false
    readonly property var section: item.narratorSection
    readonly property var buttons: W.narratorButtons(section.narrator, section.heading)
    readonly property string typed: nameField.text.trim()

    function save(request) {
        if (busy) return
        busy = true
        work.saveNarrator(item, request, function() { root.busy = false })
    }
    onChoosingChanged: if (choosing) Later.call(root, function() { nameField.forceActiveFocus() })

    spacing: 0
    Item { width: 1; height: 12 }
    Collapse {
        width: parent.width
        open: Boolean(root.section.appliesNote) && !(root.item.requested && root.item.redoOnly)
        Text {
            objectName: "narratorNote"
            width: parent.width
            bottomPadding: 8
            text: root.section.appliesNote || ""
            color: Theme.text2
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
    WorkRequested {
        width: parent.width
        text: root.item.requested ? (root.item.redoOnly ? S.s_da_ghi_ap_khi_lam_lai_phan_tich_tu_dau_4ed021d7 : S.s_da_ghi_85094402 + root.item.requested + ".") : ""
    }
    Flow {
        width: parent.width
        spacing: 8
        DecisionButton {
            objectName: "narratorAccept"
            text: root.buttons.accept
            marked: root.item.requested === root.buttons.accepted
            enabled: !root.busy
            onClicked: root.save({action: "accept"})
        }
        DecisionButton {
            objectName: "narratorKeep"
            text: root.buttons.keep
            marked: root.item.requested === S.s_giu_nguyen_1b550a12
            enabled: !root.busy
            onClicked: root.save({action: "keep"})
        }
        Button {
            objectName: "narratorOther"
            size: "sm"
            kind: "ghost"
            icon: "user-plus"
            text: S.s_nguoi_ke_khac_7291e079
            Accessible.description: root.choosing ? S.s_dang_mo_98235c77 : S.s_dang_dong_4886d4e7
            onClicked: root.choosing = !root.choosing
        }
    }
    Collapse {
        width: parent.width
        open: root.choosing
        Item {
            width: parent.width
            height: choose.height + 8
            Flow {
                id: choose
                y: 8
                width: parent.width
                spacing: 8
                Repeater {
                    model: root.section.choices
                    delegate: Button {
                        required property var modelData
                        size: "sm"
                        kind: "ghost"
                        text: modelData.label
                        enabled: !root.busy
                        onClicked: root.save({action: "choose", narrator: modelData.value})
                    }
                }
                Item {
                    width: Math.min(choose.width, 220)
                    height: 40
                    WorkField {
                        id: nameField
                        objectName: "narratorName"
                        y: 4
                        width: parent.width
                        label: S.s_ten_nguoi_ke_d492ccfb
                        placeholderText: S.s_ten_nguoi_ke_d492ccfb
                        onTextChanged: if (text.length > 80) text = text.slice(0, 80)
                        onAccepted: if (root.typed) root.save({action: "choose", narrator: root.typed})
                    }
                }
                Button {
                    objectName: "narratorSet"
                    size: "sm"
                    text: S.s_dat_nguoi_ke_d4ae9aa6
                    enabled: root.typed !== "" && !root.busy
                    onActivated: root.save({action: "choose", narrator: root.typed})
                }
            }
        }
    }
}
