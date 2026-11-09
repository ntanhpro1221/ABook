import "UiStrings.js" as S
import QtQuick
import ABook
import "NewProjectLogic.js" as Logic
import "TextWrap.js" as TextWrap

// "Chất lượng" của trình tạo sách (QualityStep + AnalysisModelPicker): ba mức chọn một (radiogroup, mũi tên đổi mức), "Chi tiết" của mức đang chọn kèm thời gian tham khảo,
// và "Bộ phân tích truyện" (chỉ khi máy có model khác mặc định). Số đo là của MỘT máy: máy khác / model khác chỉ được khoảng rộng, có nhãn tham khảo.
Column {
    id: root
    property var form: null
    readonly property var draft: form ? form.draft : ({})
    readonly property var scan: form ? form.scan : null
    readonly property string profile: draft.profile || "high_quality"
    readonly property var chosen: Logic.profileOf(profile)
    readonly property bool exact: Logic.matchesMeasured(form ? form.gpu : null, draft.analysisModel || "")
    readonly property var guess: Logic.estimate(scan ? scan.totals.words : 0, scan ? scan.files.length : 0, exact)
    readonly property var picker: Logic.modelOptions(form ? form.models : null)
    property bool modelOpen: Boolean(draft.analysisModel)
    onDraftChanged: if (draft.analysisModel && !modelOpen) modelOpen = true

    function setProfile(value) { form.update({profile: value}) }
    function step(direction) {
        const index = Logic.PROFILE_VALUES.indexOf(profile)
        const next = Math.max(0, Math.min(Logic.PROFILE_VALUES.length - 1, index + direction))
        if (next !== index) { setProfile(Logic.PROFILE_VALUES[next]); Later.call(root, function() { rows.itemAt(next).forceActiveFocus(Qt.TabFocusReason) }) }
    }

    Text { objectName: "newQualityTitle"; width: parent.width; text: S.s_chat_luong_a12ed26c; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Prose { topPadding: 4; text: S.s_co_dinh_sau_khi_tao_de_moi_chuong_doc_gion_165eeae2 }
    Item { width: 1; height: 24 }
    Column {
        width: parent.width
        Accessible.role: Accessible.RadioButton
        Accessible.name: S.s_chat_luong_a12ed26c
        Repeater {
            id: rows
            model: Logic.PROFILES
            delegate: Interactive {
                id: option
                required property var modelData
                required property int index
                readonly property bool selected: modelData.value === root.profile
                objectName: "newProfile"
                width: parent.width
                height: 16 + col.height + 16 + 1
                activeFocusOnTab: selected
                pressScaling: false
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.title
                Accessible.checked: selected
                onClicked: root.setProfile(modelData.value)
                Keys.onDownPressed: root.step(1)
                Keys.onRightPressed: root.step(1)
                Keys.onUpPressed: root.step(-1)
                Keys.onLeftPressed: root.step(-1)
                Column {
                    id: col
                    y: 16
                    width: parent.width - 32
                    Row {
                        visible: option.modelData.value === "high_quality"
                        spacing: 4
                        bottomPadding: visible ? 8 : 0
                        Icon { y: 2; name: "sparkles"; size: 12; color: Theme.text2 }
                        Text { text: S.s_nen_dung_84e3ecf2; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
                    }
                    Text {
                        width: parent.width
                        text: TextWrap.keepDots(option.modelData.title)
                        color: option.selected ? Theme.accentText : Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBody
                        font.weight: Theme.weightBold
                        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                    }
                    Item {
                        width: col.width
                        height: 4 + pace.height
                        LineIcon { line: pace; name: "gauge"; size: 14; color: Theme.text2 }
                        Text { id: pace; x: 20; y: 4; width: col.width - 20; text: option.modelData.pace; color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
                    }
                    Prose { topPadding: 12; text: option.modelData.summary }
                }
                Icon {
                    x: parent.width - 24
                    y: 16 + (option.modelData.value === "high_quality" ? 22 : 2)
                    name: "check"
                    size: 16
                    color: Theme.accentText
                    opacity: option.selected ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
                Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.line }
            }
        }
    }
    Item { width: 1; height: 16 }
    ImportFold {
        width: parent.width
        storageKey: "quality"
        prefix: "fold.new-project."
        title: S.s_chi_tiet_e762d926
        summary: root.chosen ? root.chosen.title : ""
        Item { width: 1; height: 12 }
        Repeater {
            model: root.chosen ? root.chosen.points : []
            delegate: Item {
                required property string modelData
                width: parent.width
                height: pointText.height + 8
                LineIcon { line: pointText; name: "check"; size: 14; color: Theme.success }
                Text { id: pointText; x: 22; width: parent.width - 22; text: modelData; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBodySmall; lineHeight: 1.4 }
            }
        }
        Prose {
            objectName: "newQualityTime"
            topPadding: 4
            text: Logic.qualityDetail(root.form ? root.form.noStudio : false, root.profile, root.scan ? root.scan.files.length : 0, root.guess, root.exact)
        }
    }
    // Bộ phân tích truyện: chỉ khi có bản khác mặc định
    Collapse {
        width: parent.width
        open: root.picker.others.length > 0
        Item { width: 1; height: 32 }
        DisclosureRow {
            objectName: "newModelToggle"
            width: parent.width
            title: S.s_bo_phan_tich_truyen_9a52f60b
            expanded: root.modelOpen
            onClicked: root.modelOpen = !root.modelOpen
        }
        Collapse {
            width: parent.width
            open: root.modelOpen
            Prose { topPadding: 8; small: true; text: S.s_chi_chon_ban_khac_khi_muon_thu_tren_cuon_n_d2d4143b }
            Item { width: 1; height: 8 }
            Select {
                objectName: "newModelSelect"
                width: Math.min(parent.width, 512)
                label: S.s_bo_phan_tich_truyen_9a52f60b
                options: root.picker.options
                value: root.draft.analysisModel || ""
                onPicked: value => root.form.update({analysisModel: value})
            }
            Prose {
                objectName: "newModelNote"
                topPadding: 6
                small: true
                text: root.draft.analysisModel ? S.s_ban_thu_nghiem_chua_duoc_kiem_tren_nhieu_t_32fc14af
                                               : S.s_mac_dinh_may_de_xuat_cho_hau_het_cac_truye_ea11fe13
            }
        }
    }
}
