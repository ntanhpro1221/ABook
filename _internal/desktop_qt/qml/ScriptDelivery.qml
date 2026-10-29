import QtQuick
import ABook
import "ScriptLogic.js" as S

// Bảng sửa cách đọc một câu (DeliveryMenu của ScriptTab.tsx): loại đoạn, cảm xúc, mức, chữ đem đọc. Lời kể thành lời thoại / nội tâm thì phải chọn người
// nói (một câu thoại luôn có chủ) - bằng chính ô chọn người của "Ai nói câu này". Mức do khâu phân tích hiệu chỉnh lại theo cảm xúc. Tên riêng trong câu
// đọc sai là sai ở MỌI câu có tên ấy: mục "Tên trong câu" sửa cho cả cuốn (hàng của "Cách đọc tên"), tách khỏi nút lưu chỉ cho câu này.
// Bảng dựng lại mỗi lần mở (Loader), nên lựa chọn bắt đầu từ cách đọc đang có hay đang chờ áp.
Column {
    id: root
    property var line: ({})
    property var script: ({cast: [], others: []})
    property var work: null
    signal save(var change)

    readonly property var waiting: line.lineWish && line.lineWish.state === "pending" ? line.lineWish : null
    readonly property string reading: line.spoken !== null && line.spoken !== undefined ? line.spoken : line.text
    readonly property string startKind: waiting && waiting.kind ? waiting.kind : line.kind
    readonly property string startEmotion: waiting && waiting.emotion ? waiting.emotion : line.emotion || "neutral"
    readonly property int startLevel: waiting && waiting.intensity !== undefined && waiting.intensity !== null ? waiting.intensity : line.intensity || 0
    readonly property string startWords: waiting && waiting.spoken ? waiting.spoken : reading
    property string kind: startKind
    property string emotion: startEmotion
    property int level: startLevel
    property var picked: null
    readonly property string words: wordsField.text
    readonly property bool needsSpeaker: line.kind === "narration" && kind !== "narration"
    readonly property var change: S.deliveryChange(line, kind, emotion, level, picked, words)
    readonly property bool ready: S.deliveryReady(line, kind, change)
    // Khác lúc mở bảng (kể cả lựa chọn đang chờ áp đã điền sẵn) = còn thứ chưa lưu
    readonly property bool unsaved: kind !== startKind || emotion !== startEmotion || level !== startLevel || Boolean(needsSpeaker && picked) || words !== startWords
    readonly property var names: work && work.names.data ? S.namesInLine(work.names.data.items, line.text) : []
    spacing: 12
    Component.onCompleted: if (work) work.namesOpened = true

    Column {
        width: parent.width
        spacing: 6
        Label_ { text: "Loại đoạn" }
        ChoiceRow {
            objectName: "deliveryKind"
            width: parent.width
            label: "Loại đoạn"
            value: root.kind
            options: S.KINDS
            onPicked: value => root.kind = value
        }
    }
    Collapse {
        objectName: "deliverySpeaker"
        width: parent.width
        open: root.needsSpeaker
        Column {
            width: parent.width
            spacing: 6
            Label_ { text: "Ai nói?" }
            Item {
                visible: !!root.picked
                width: parent.width
                height: visible ? Math.max(32, pickedName.implicitHeight + 8) : 0
                Icon { anchors.verticalCenter: parent.verticalCenter; name: "check"; size: 16; color: Theme.accentText }
                Text {
                    id: pickedName
                    objectName: "deliveryPicked"
                    x: 24
                    width: parent.width - x - changeLink.width - 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.picked ? root.picked.label + (root.picked.newGender ? " · người mới" : "") : ""
                    color: Theme.accentText
                    wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: Theme.weightMedium
                }
                TextLink {
                    id: changeLink
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    accent: true
                    text: "Đổi"
                    onClicked: root.picked = null
                }
            }
            ScriptSpeakerMenu {
                visible: !root.picked
                width: parent.width
                line: root.line
                script: root.script
                embedded: true
                onPicked: person => root.picked = person
            }
        }
    }
    ImportFold {
        objectName: "deliveryEmotion"
        width: parent.width
        prefix: "fold."
        storageKey: "delivery.emotion"
        title: "Cảm xúc"
        summary: S.deliveryText(root.emotion, root.level)
        Column {
            width: parent.width
            spacing: 12
            Column {
                visible: root.line.emotion !== null
                width: parent.width
                spacing: 6
                Label_ { text: "Cảm xúc" }
                Flow {
                    width: parent.width
                    spacing: 6
                    Repeater {
                        model: S.EMOTIONS
                        delegate: ChoiceChip {
                            required property var modelData
                            objectName: "deliveryEmotion_" + modelData[0]
                            text: modelData[1]
                            selected: root.emotion === modelData[0]
                            onClicked: root.emotion = modelData[0]
                        }
                    }
                }
            }
            Column {
                visible: root.line.intensity !== null
                width: parent.width
                spacing: 6
                Label_ { text: "Mức" }
                ChoiceRow {
                    objectName: "deliveryLevel"
                    width: parent.width
                    label: "Mức"
                    value: String(root.level)
                    options: S.LEVELS.map((label, index) => ({value: String(index), label: label}))
                    onPicked: value => root.level = Number(value)
                }
                Text {
                    width: parent.width
                    text: "Máy giữ mức trong tầm giọng đọc được: thì thầm, dịu dàng tối đa \"Vừa\"."
                    color: Theme.text3
                    wrapMode: Text.Wrap
                    font.pixelSize: 11
                }
            }
        }
    }
    Column {
        width: parent.width
        spacing: 6
        Label_ { text: "Chữ đem đọc" }
        FormField {
            id: wordsField
            objectName: "deliveryWords"
            width: parent.width
            multiline: true
            label: "Chữ máy sẽ đọc thay cho câu này"
            placeholderText: "Gõ chữ muốn máy đọc (để trống: đọc đúng chữ của sách)"
            text: root.startWords
            escapeLocal: false
        }
        Text {
            width: parent.width
            text: "Chỉ sửa chữ đem đọc; sách giữ nguyên" + (root.line.spoken ? "; xoá hết để dùng chữ gốc." : "")
            color: Theme.text3
            wrapMode: Text.Wrap
            font.pixelSize: 11
        }
        TextLink {
            objectName: "deliveryOriginal"
            visible: !!root.line.spoken
            accent: true
            text: "Dùng chữ gốc"
            onClicked: wordsField.text = root.line.text
        }
    }
    Button {
        objectName: "deliverySave"
        width: parent.width
        size: "sm"
        kind: "primary"
        enabled: root.ready
        text: root.needsSpeaker && !root.picked ? "Chọn người nói trước" : "Lưu cho câu này"
        onClicked: root.save(root.change)
    }
    ImportFold {
        objectName: "deliveryNames"
        visible: root.names.length > 0
        width: parent.width
        prefix: "fold."
        storageKey: "delivery.names"
        title: "Tên trong câu"
        summary: root.names.length + " tên"
        Column {
            width: parent.width
            spacing: 8
            Label_ { text: "Tên cả cuốn" }
            Repeater {
                model: root.names
                delegate: NameRow {
                    required property var modelData
                    width: parent.width
                    work: root.work
                    item: modelData
                }
            }
        }
    }

    component Label_: Text {
        width: parent.width
        color: Theme.text2
        font.pixelSize: Theme.sizeCaption
        font.weight: Theme.weightMedium
        wrapMode: Text.Wrap
    }
}
