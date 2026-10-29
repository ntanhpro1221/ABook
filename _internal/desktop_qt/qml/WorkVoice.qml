import QtQuick
import ABook
import "WorkLogic.js" as W

// Giọng / giới của một nhân vật (VoiceFix): một lần bấm. Dây chuyền chọn giọng mới như bước phân vai (mọi người khác giữ giọng) và chỉ thu lại khi giọng thật sự đổi - ghi chú dưới
// mỗi nút nói trước cái giá ấy. "Giữ nguyên" ghi yêu cầu rỗng cho từng người trong `keepCharacters` (thẻ thôi hỏi).
Column {
    id: root
    property var work: null
    property var item: ({})
    property bool busy: false

    function request(choice) {
        const body = {character: choice.character}
        if (choice.gender !== undefined) body.gender = choice.gender
        if (choice.preset !== undefined) body.preset = choice.preset
        if (choice.avoid !== undefined) body.avoid = choice.avoid
        return body
    }
    function choose(choice) {
        if (busy) return
        busy = true
        work.saveVoice(item, [request(choice)], choice.done !== undefined ? choice.done : choice.label, false, function() { root.busy = false })
    }
    function keepAll() {
        if (busy) return
        busy = true
        work.saveVoice(item, item.keepCharacters.map(function(character) { return {character: character} }), item.keepLabel || "Giữ nguyên", true, function() { root.busy = false })
    }

    spacing: 0
    Item { width: 1; height: 12 }
    WorkRequested { width: parent.width; text: root.item.requested ? "Đã ghi: " + root.item.requested + " - " + root.work.pendingNote + "." : "" }
    Flow {
        width: parent.width
        spacing: 8
        Repeater {
            model: root.item.voiceChoices || []
            delegate: Column {
                required property var modelData
                spacing: 2
                DecisionButton {
                    text: modelData.label
                    marked: W.voiceChoiceMarked(root.item, modelData)
                    enabled: !root.busy
                    onClicked: root.choose(modelData)
                }
                Text {
                    visible: Boolean(modelData.note)
                    x: 2
                    width: Math.min(implicitWidth, 260)
                    text: modelData.note || ""
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: 11
                }
            }
        }
        DecisionButton {
            objectName: "voiceKeep"
            visible: Boolean(root.item.keepCharacters) && root.item.keepCharacters.length > 0
            text: root.item.keepLabel || "Giữ nguyên"
            enabled: !root.busy
            onClicked: root.keepAll()
        }
    }
}
