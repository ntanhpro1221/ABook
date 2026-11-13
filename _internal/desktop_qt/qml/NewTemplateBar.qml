import "UiStrings.js" as S
import QtQuick
import ABook
import "TemplateLogic.js" as Templates

// "Mẫu thiết lập" ở đầu trình tạo sách (TemplateBar.tsx): chọn một mẫu đã lưu thì giọng kể, chất lượng, model đọc hiểu và "bắt đầu ngay" của nháp theo mẫu (nguồn truyện,
// tên sách... không đụng tới); "Lưu thành mẫu…" chụp các lựa chọn hiện tại. Lưu là MỘT thao tác gửi lên máy tính (POST /api/book-templates, `form.templateOp`)
// nên Studio máy khác lưu được như máy này; trùng tên thì hỏi ghi đè. Ô tên có lớp Back riêng.
Column {
    id: root
    property var form: null
    readonly property var draft: form ? form.draft : ({})
    readonly property var templates: form ? form.templates : []
    readonly property var active: Templates.findTemplate(templates, draft.template)
    readonly property bool modified: active ? Templates.isModified(draft, active, form.modelNames) : false
    readonly property string lostModel: Templates.missingModel(active, form ? form.modelNames : null)
    readonly property string lostVoice: Templates.missingVoice(active, form && form.voices.length ? form.voiceNames : null)
    property bool saving: false
    property bool confirming: false
    property string problem: ""
    property string name: ""
    readonly property bool busy: form ? form.templateBusy : false
    readonly property var existing: Templates.findTemplate(templates, name)
    spacing: 0

    property QtObject backLayer: QtObject { function close() { if (root.confirming) root.confirming = false; else root.close() } }
    function open() {
        name = active ? active.name : ""
        problem = ""
        confirming = false
        saving = true
        Nav.openLayer(backLayer)
        nameField.forceActiveFocus()
    }
    function close() {
        Nav.closedLayer(backLayer)
        saving = false
        confirming = false
        problem = ""
        saveButton.forceActiveFocus(Qt.TabFocusReason)
    }
    Component.onDestruction: Nav.closedLayer(backLayer)
    function submit() {
        const wrong = Templates.nameProblem(templates, name, existing ? existing.name : undefined) ||
            (!existing && Templates.isFull(templates) ? S.s_da_co_du_20_mau_xoa_bot_mot_mau_trong_cai_c3b1c3a3 : "")
        if (wrong) { problem = wrong; return }
        if (existing && !confirming) { confirming = true; return }
        const saved = Templates.templateFromDraft(draft, name, form.autoNarrator)
        form.templateOp({op: "save", template: saved, replace: Boolean(existing)}, function(ok, message) {
            if (ok) {
                Api.toast(S.s_da_luu_mau_11c50fd0 + saved.name + "”")
                form.pickTemplate(saved)
                root.close()
            } else root.problem = message
        })
    }

    Item { width: 1; height: 12 }
    Flow {
        width: parent.width
        spacing: 12
        Text { height: 36; verticalAlignment: Text.AlignVCenter; text: S.s_mau_thiet_lap_be32f35e; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
        ChoiceRow {
            objectName: "newTemplates"
            Reveal { shown: root.templates.length > 0 }
            width: Math.min(implicitWidth, root.width - 140)
            label: S.s_mau_thiet_lap_be32f35e
            options: [{value: "", label: Templates.DEFAULT_LABEL}].concat(root.templates.map(item => ({value: item.name, label: item.name === (root.active ? root.active.name : "") && root.modified ? item.name + S.s_da_sua_a7e7e8e8 : item.name})))
            value: root.active ? root.active.name : ""
            onPicked: value => root.form.pickTemplate(value ? Templates.findTemplate(root.templates, value) : null)
        }
        Item {
            width: Math.max(0, root.width - x)
            height: 36
            // Nút nằm cuối hàng (ml-auto); hẹp thì xuống dòng và ôm sát trái
            Button {
                id: saveButton
                objectName: "newTemplateSave"
                Reveal { shown: !root.saving }
                text: S.s_luu_thanh_mau_bd20c55a
                icon: "bookmark-plus"
                kind: "ghost"
                size: "sm"
                onActivated: root.open()
            }
        }
    }
    Prose {
        objectName: "newTemplateModified"
        Reveal { shown: root.modified && Boolean(root.active) }
        topPadding: visible ? 8 : 0
        small: true
        text: root.active ? S.s_bam_lai_mau_26ea82c5 + root.active.name + S.s_de_khoi_phuc_thiet_lap_da_luu_095b8a08 : ""
    }
    Prose { objectName: "newTemplateLostVoice"; Reveal { shown: root.lostVoice !== "" } topPadding: visible ? 8 : 0; small: true; text: Templates.missingVoiceNote(root.lostVoice) }
    Prose { objectName: "newTemplateLostModel"; Reveal { shown: root.lostModel !== "" } topPadding: visible ? 8 : 0; small: true; text: Templates.missingModelNote() }
    Prose {
        objectName: "newTemplateHint"
        Reveal { shown: !root.templates.length && !root.saving }
        topPadding: visible ? 8 : 0
        small: true
        text: S.s_luu_cac_lua_chon_duoi_day_thanh_mau_de_dun_8513aa2f
    }
    // Ô đặt tên mẫu
    Collapse {
        width: parent.width
        open: root.saving
        Item { width: 1; height: 12 }
        Flow {
            width: parent.width
            spacing: 8
            FormField {
                id: nameField
                objectName: "newTemplateName"
                width: Math.min(320, parent.width)
                label: S.s_ten_mau_f037fdd2
                placeholderText: S.s_ten_mau_vi_du_light_novel_aae56cfd
                invalid: root.problem !== ""
                text: root.name
                onTextChanged: {
                    if (text.length > Templates.NAME_MAX) text = text.slice(0, Templates.NAME_MAX)
                    if (text !== root.name) { root.name = text; root.confirming = false; root.problem = "" }
                }
                onAccepted: root.submit()
                escapeLocal: true
                onEscaped: root.close()
            }
            Button { objectName: "newTemplateConfirm"; Reveal { shown: root.confirming } text: S.s_ghi_de_5e4cd1eb; kind: "primary"; size: "sm"; busy: root.busy; onActivated: root.submit() }
            Button { objectName: "newTemplateRename"; Reveal { shown: root.confirming } text: S.s_dat_ten_khac_78e8f19c; kind: "ghost"; size: "sm"; onActivated: { root.confirming = false; nameField.forceActiveFocus() } }
            Button { objectName: "newTemplateOk"; Reveal { shown: !root.confirming } text: S.s_luu_e91f26c0; kind: "primary"; size: "sm"; busy: root.busy; enabled: Templates.cleanName(root.name) !== ""; onActivated: root.submit() }
            Button { objectName: "newTemplateCancel"; Reveal { shown: !root.confirming } text: S.s_huy_96732485; kind: "ghost"; size: "sm"; onActivated: root.close() }
        }
        Prose {
            objectName: "newTemplateAsk"
            Reveal { shown: root.confirming }
            topPadding: visible ? 8 : 0
            small: true
            text: root.existing ? S.s_da_co_mau_8527783b + root.existing.name + S.s_ghi_de_bang_cac_lua_chon_hien_tai_c2f33cd5 : ""
        }
        Prose { objectName: "newTemplateProblem"; Reveal { shown: root.problem !== "" } topPadding: visible ? 8 : 0; small: true; tone: Theme.danger; text: root.problem }
        Prose { topPadding: 8; small: true; tone: Theme.text3; text: S.s_mau_luu_giong_chat_luong_va_cach_tao_sach_143fa4bf }
        MoreInfo {
            width: parent.width
            label: S.s_tim_hieu_them_032fe408
            Prose { small: true; text: S.s_gom_bo_phan_tich_bat_dau_ngay_va_duyet_tru_7f1b3642 }
        }
    }
    Item { width: 1; height: 12 }
}
