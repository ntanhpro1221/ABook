import "UiStrings.js" as S
import QtQuick
import ABook
import "WorkLogic.js" as W

// Sửa cách đọc một tên ngay trên thẻ (PronunciationFix): "Đúng rồi, giữ …" / "hoặc đọc là" + ô + "Nghe thử" + "Đọc thế này". Ghi xong là xong phần người; dây chuyền áp ở ranh
// giới chương kế tiếp và thu lại đúng những câu có tên ấy. Lỗi nằm ngay dưới ô nhập (kèm bản sửa máy chủ mời), không thêm lời báo.
Column {
    id: root
    property var work: null
    property var item: ({})
    property bool namesLink: false
    property bool saving: false
    property string problem: ""
    property string suggestion: ""
    readonly property string typed: field.text.trim()
    signal openNames(string name)

    function save(spoken) {
        if (saving) return
        saving = true
        work.savePronunciationCard(item, spoken, function(message, hint) { root.saving = false; root.problem = message; root.suggestion = hint })
    }
    function use(spoken) { field.text = spoken; problem = ""; suggestion = ""; save(spoken) }
    Component.onCompleted: field.text = item.requested !== null && item.requested !== undefined ? item.requested : item.current

    spacing: 0
    Item { width: 1; height: 12 }
    WorkRequested { width: parent.width; text: root.item.requested ? W.pronunciationAppliedLine(root.item, root.work.pendingNote) : "" }
    Flow {
        width: parent.width
        spacing: 8
        DecisionButton {
            objectName: "pronKeep"
            text: S.s_dung_roi_giu_b3493ad3 + root.item.current + "”"
            enabled: !root.saving
            onClicked: root.save(root.item.current)
        }
        Text {
            height: 40
            verticalAlignment: Text.AlignVCenter
            text: S.s_hoac_doc_la_376990a8
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
        }
        Item {
            width: 160
            height: 40
            WorkField {
                id: field
                objectName: "pronField"
                y: 4
                width: parent.width
                label: S.s_cach_doc_moi_cho_c1e4a60a + root.item.surface
                placeholderText: S.s_vd_76c4de6f + root.item.current
                invalid: root.problem !== ""
                onTextChanged: { root.problem = ""; root.suggestion = "" }
                onAccepted: if (root.typed && root.typed !== root.item.current && root.typed !== root.item.requested) root.save(root.typed)
            }
        }
        TryButton { objectName: "pronTry"; reading: tryIt }
        Button {
            objectName: "pronSave"
            size: "sm"
            text: S.s_doc_the_nay_b9d202fe
            busy: root.saving
            enabled: root.typed !== "" && root.typed !== root.item.current && root.typed !== root.item.requested
            onActivated: root.save(root.typed)
        }
        // Thẻ chỉ hỏi tên máy kém chắc; mọi tên khác sửa ở tab Nhân vật, mục "Cách đọc tên"
        Button {
            objectName: "pronNames"
            Reveal { shown: root.namesLink }
            size: "sm"
            kind: "ghost"
            text: S.s_moi_cach_doc_ten_85347e60
            onClicked: root.openNames(root.item.surface || "")
        }
    }
    TryNote { reading: tryIt; width: parent.width }
    ReadingProblem { width: parent.width; problem: root.problem; suggestion: root.suggestion; onUsed: spoken => root.use(spoken) }
    TryReading {
        id: tryIt
        work: root.work
        surface: root.item.surface || ""
        spoken: root.typed
        blocked: root.problem !== ""
        onRejected: (message, hint) => { root.problem = message; root.suggestion = hint }
    }
}
