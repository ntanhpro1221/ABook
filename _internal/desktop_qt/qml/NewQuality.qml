import QtQuick
import ABook
import "NewProjectLogic.js" as Logic

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
        if (next !== index) { setProfile(Logic.PROFILE_VALUES[next]); Qt.callLater(function() { rows.itemAt(next).forceActiveFocus(Qt.TabFocusReason) }) }
    }

    Text { objectName: "newQualityTitle"; width: parent.width; text: "Chất lượng"; color: Theme.text; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeSection; font.weight: Theme.weightMedium }
    Prose { topPadding: 4; text: "Không đổi được sau khi tạo, để mọi chương đọc giống nhau." }
    Item { width: 1; height: 24 }
    Column {
        width: parent.width
        Accessible.role: Accessible.RadioButton
        Accessible.name: "Chất lượng"
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
                        Text { text: "Nên dùng"; color: Theme.text2; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
                    }
                    Text {
                        width: parent.width
                        text: option.modelData.title
                        color: option.selected ? Theme.accentText : Theme.text
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBody
                        font.weight: Theme.weightBold
                        Behavior on color { ColorAnimation { duration: Theme.motionFast } }
                    }
                    Row {
                        spacing: 6
                        topPadding: 4
                        Icon { y: 3; name: "gauge"; size: 14; color: Theme.text2 }
                        Text { width: col.width - 20; text: option.modelData.pace; color: Theme.text2; wrapMode: Text.WrapAtWordBoundaryOrAnywhere; font.pixelSize: Theme.sizeCaption; font.weight: Theme.weightMedium }
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
        title: "Chi tiết"
        summary: root.chosen ? root.chosen.title : ""
        Item { width: 1; height: 12 }
        Repeater {
            model: root.chosen ? root.chosen.points : []
            delegate: Item {
                required property string modelData
                width: parent.width
                height: pointText.height + 8
                Icon { y: 3; name: "check"; size: 14; color: Theme.success }
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
            title: "Bộ phân tích truyện"
            expanded: root.modelOpen
            onClicked: root.modelOpen = !root.modelOpen
        }
        Collapse {
            width: parent.width
            open: root.modelOpen
            Prose { topPadding: 8; small: true; text: "Chỉ chọn bản khác khi muốn thử trên cuốn này." }
            Item { width: 1; height: 8 }
            Select {
                objectName: "newModelSelect"
                width: Math.min(parent.width, 512)
                label: "Bộ phân tích truyện"
                options: root.picker.options
                value: root.draft.analysisModel || ""
                onPicked: value => root.form.update({analysisModel: value})
            }
            Prose {
                objectName: "newModelNote"
                topPadding: 6
                small: true
                text: root.draft.analysisModel ? "Bản thử nghiệm: chưa được kiểm trên nhiều truyện, kết quả có thể kém hơn mặc định."
                                               : "Mặc định: máy đề xuất cho hầu hết các truyện, không cần chỉnh gì."
            }
        }
    }
}
