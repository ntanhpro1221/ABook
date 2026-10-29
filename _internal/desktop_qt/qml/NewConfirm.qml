import QtQuick
import ABook
import "NewProjectLogic.js" as Logic

// "Khi tạo" (ConfirmStep): hai công tắc - bắt đầu ngay, duyệt trước khi thu - và "Tóm tắt" phẳng mọi lựa chọn sẽ gửi đi, kể cả thời gian tham khảo. Máy chưa có Studio thì không
// ước thời gian và không "bắt đầu ngay".
Column {
    id: root
    property var form: null
    readonly property var draft: form ? form.draft : ({})
    readonly property var scan: form ? form.scan : null
    readonly property bool noStudio: form ? form.noStudio : false
    readonly property bool unfit: form ? Boolean(form.unfit) : false
    readonly property string firstPerson: String(draft.firstPerson || "").trim()
    readonly property bool wide: width >= 560
    readonly property var rows: !scan || !scan.files.length ? [] : Logic.summaryRows({
        scan: scan,
        title: String(draft.title || "").trim(),
        profile: draft.profile,
        gpu: form.gpu,
        analysisModel: draft.analysisModel || "",
        volumes: form.volumeStarts.length > 1 ? Logic.ranges(form.volumeStarts, scan.files.length) : null,
        startNow: draft.startNow,
        credits: form.credits,
        dropCredits: draft.dropCredits || Logic.KEEP_CREDITS,
        narratorAuto: form.autoNarrator,
        narrator: draft.narrator,
        firstPerson: firstPerson,
        firstPersonGender: firstPerson ? draft.firstPersonGender : undefined,
        tellerMode: firstPerson ? Boolean(draft.tellerMode) : false,
        povChapters: form.povChapters,
        seed: draft.seed,
        modelsDefault: Boolean(form.models && form.models.default),
        unfit: root.unfit,
        noStudio: noStudio
    })

    Text { width: parent.width; text: "Khi tạo"; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBody; font.weight: Theme.weightBold }
    Item { width: 1; height: 8 }
    NewSwitchRow {
        objectName: "newStartNow"
        width: parent.width
        name: "Bắt đầu tạo ngay"
        hint: Logic.startNowHint(root.draft.startNow, root.noStudio, root.unfit)
        checked: Boolean(root.draft.startNow) && !root.noStudio
        enabled: !root.noStudio
        onToggled: value => root.form.update({startNow: value})
    }
    Rectangle { width: parent.width; height: 1; color: Theme.line }
    NewSwitchRow {
        objectName: "newPrecastWait"
        width: parent.width
        name: "Duyệt trước khi thu"
        hint: Logic.precastHint(Boolean(root.draft.precastWait))
        checked: Boolean(root.draft.precastWait)
        onToggled: value => root.form.update({precastWait: value})
    }
    Item { width: 1; height: 32 }
    Text { width: parent.width; text: "Tóm tắt"; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeBody; font.weight: Theme.weightBold }
    Item { width: 1; height: 8 }
    Column {
        objectName: "newSummary"
        width: parent.width
        Accessible.role: Accessible.List
        Accessible.name: "Tóm tắt"
        Repeater {
            model: root.rows
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                width: parent.width
                height: 16 + (root.wide ? Math.max(label.height, value.height) : label.height + 2 + value.height)
                Rectangle { visible: row.index > 0; width: parent.width; height: 1; color: Theme.line }
                Text {
                    id: label
                    objectName: "newSummaryLabel"
                    y: 8
                    width: root.wide ? 200 : parent.width
                    text: row.modelData[0]
                    color: Theme.text2
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                    lineHeight: 1.4
                }
                Text {
                    id: value
                    objectName: "newSummaryValue"
                    x: root.wide ? 216 : 0
                    y: root.wide ? 8 : 8 + label.height + 2
                    width: root.wide ? parent.width - 216 : parent.width
                    text: row.modelData[1]
                    color: Theme.text
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                    lineHeight: 1.4
                }
            }
        }
    }
}
