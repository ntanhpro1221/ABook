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
            (!existing && Templates.isFull(templates) ? "Đã có đủ 20 mẫu - xoá bớt một mẫu trong Cài đặt trước" : "")
        if (wrong) { problem = wrong; return }
        if (existing && !confirming) { confirming = true; return }
        const saved = Templates.templateFromDraft(draft, name, form.autoNarrator)
        form.templateOp({op: "save", template: saved, replace: Boolean(existing)}, function(ok, message) {
            if (ok) {
                Api.toast("Đã lưu mẫu “" + saved.name + "”")
                form.pickTemplate(saved)
                root.close()
            } else root.problem = message
        })
    }

    Item { width: 1; height: 12 }
    Flow {
        width: parent.width
        spacing: 12
        Text { height: 36; verticalAlignment: Text.AlignVCenter; text: "Mẫu thiết lập"; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
        ChoiceRow {
            objectName: "newTemplates"
            visible: root.templates.length > 0
            width: Math.min(implicitWidth, root.width - 140)
            label: "Mẫu thiết lập"
            options: [{value: "", label: Templates.DEFAULT_LABEL}].concat(root.templates.map(item => ({value: item.name, label: item.name === (root.active ? root.active.name : "") && root.modified ? item.name + " (đã sửa)" : item.name})))
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
                visible: !root.saving
                text: "Lưu thành mẫu…"
                icon: "bookmark-plus"
                kind: "ghost"
                size: "sm"
                onActivated: root.open()
            }
        }
    }
    Prose {
        objectName: "newTemplateModified"
        visible: root.modified && Boolean(root.active)
        topPadding: visible ? 8 : 0
        small: true
        text: root.active ? "Bấm lại mẫu “" + root.active.name + "” để khôi phục thiết lập đã lưu." : ""
    }
    Prose { objectName: "newTemplateLostVoice"; visible: root.lostVoice !== ""; topPadding: visible ? 8 : 0; small: true; text: Templates.missingVoiceNote(root.lostVoice) }
    Prose { objectName: "newTemplateLostModel"; visible: root.lostModel !== ""; topPadding: visible ? 8 : 0; small: true; text: Templates.missingModelNote() }
    Prose {
        objectName: "newTemplateHint"
        visible: !root.templates.length && !root.saving
        topPadding: visible ? 8 : 0
        small: true
        text: "Lưu các lựa chọn dưới đây thành mẫu để dùng lại cho những cuốn sau."
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
                label: "Tên mẫu"
                placeholderText: "Tên mẫu, ví dụ Light novel"
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
            Button { objectName: "newTemplateConfirm"; visible: root.confirming; text: "Ghi đè"; kind: "primary"; size: "sm"; busy: root.busy; onActivated: root.submit() }
            Button { objectName: "newTemplateRename"; visible: root.confirming; text: "Đặt tên khác"; kind: "ghost"; size: "sm"; onActivated: { root.confirming = false; nameField.forceActiveFocus() } }
            Button { objectName: "newTemplateOk"; visible: !root.confirming; text: "Lưu"; kind: "primary"; size: "sm"; busy: root.busy; enabled: Templates.cleanName(root.name) !== ""; onActivated: root.submit() }
            Button { objectName: "newTemplateCancel"; visible: !root.confirming; text: "Huỷ"; kind: "ghost"; size: "sm"; onActivated: root.close() }
        }
        Prose {
            objectName: "newTemplateAsk"
            visible: root.confirming
            topPadding: visible ? 8 : 0
            small: true
            text: root.existing ? "Đã có mẫu “" + root.existing.name + "”. Ghi đè bằng các lựa chọn hiện tại?" : ""
        }
        Prose { objectName: "newTemplateProblem"; visible: root.problem !== ""; topPadding: visible ? 8 : 0; small: true; tone: Theme.danger; text: root.problem }
        Prose { topPadding: 8; small: true; tone: Theme.text3; text: "Mẫu lưu giọng, chất lượng và cách tạo sách." }
        MoreInfo {
            width: parent.width
            label: "Tìm hiểu thêm"
            Prose { small: true; text: "Gồm bộ phân tích, bắt đầu ngay và duyệt trước khi thu. Không lưu truyện, tên sách hay dòng ghi công." }
        }
    }
    Item { width: 1; height: 12 }
}
