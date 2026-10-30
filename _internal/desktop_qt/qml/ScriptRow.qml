import QtQuick
import ABook
import "ScriptLogic.js" as S
import "CastLogic.js" as Cast

// Một câu của kịch bản (ScriptRow của ScriptTab.tsx): ô người nói (chip bấm được cho câu thoại; câu kể ghi "Người kể" mờ), nút nghe ngay trước chữ,
// chữ câu (chỗ ô tìm khớp tô nền), rồi các dòng trạng thái: chữ đem đọc, cách đọc đang chờ / bị từ chối, chỗ máy nghi (+ "Gán cho …"), yêu cầu thu lại,
// người nói đang chờ / bị từ chối. Việc phụ (thu lại, cách đọc mặc định) chỉ hiện khi rê / chọn câu. Màn rộng: ba cột như kịch bản; hẹp: chip trên chữ.
Item {
    id: root
    property var line: ({})
    property var script: ({cast: [], others: [], castReady: false})
    property string bookId: ""
    property var store: null
    property bool active: false
    property bool selected: false
    property var marks: []
    property bool markNow: false
    property bool context: false
    property string pendingNote: ""
    signal activate()
    signal extend()
    signal openSpeaker(Item anchor)
    signal openDelivery(Item anchor)
    signal pick(var person)
    signal retake()
    signal cancelRetake()

    readonly property bool speech: S.isSpeech(line)
    readonly property bool wide: width >= 640
    readonly property bool shownActions: active || hover.hovered
    readonly property string clipId: "script-" + line.segmentId
    readonly property bool playing: Clip.current === clipId
    readonly property var suggested: S.suggestedOf(script, line)
    readonly property bool hasEmotion: line.emotion !== null && line.emotion !== undefined
    readonly property bool plain: S.plainDelivery(line)
    readonly property string speakerShown: line.wish && line.wish.state === "pending" ? line.wish.label : line.label
    readonly property real textX: wide ? 160 + 8 + 28 + 8 : 28 + 8
    readonly property real textY: wide || !speech ? 6 : chipBox.height + 10
    property alias speakerChip: chip
    property alias deliveryAnchor: deliveryAnchorItem

    objectName: "scriptRow"
    implicitHeight: Math.max(textY + body.height + 6, 40)
    height: implicitHeight
    opacity: context ? 0.45 : 1
    activeFocusOnTab: (speech && active) || activeFocus
    Accessible.role: Accessible.ListItem
    Accessible.name: line.text || ""
    Accessible.selected: speech && selected
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }

    HoverHandler { id: hover }
    // Nền câu đang đứng: mờ dần bằng độ trong (màu chuyển từ "transparent" đi qua xám tối ở giao diện sáng)
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.hover
        opacity: root.active && !root.selected ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    }
    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: "transparent"
        border.width: root.marks.length && !root.selected ? (root.markNow ? 2 : 1) : root.activeFocus ? 2 : 0
        border.color: root.marks.length && !root.selected ? Qt.alpha(Theme.warning, root.markNow ? 0.6 : 0.25) : Theme.focus
    }
    MouseArea {
        anchors.fill: parent
        enabled: root.speech
        cursorShape: Qt.ArrowCursor
        onClicked: mouse => {
            root.forceActiveFocus(Qt.MouseFocusReason)
            if (mouse.modifiers & Qt.ShiftModifier) root.extend(); else root.activate()
        }
    }

    // ---- ô người nói ----
    Item {
        id: chipBox
        x: 8; y: 6
        width: root.wide ? 160 : root.width - 16
        height: 28
        visible: root.speech || root.wide
        Interactive {
            id: chip
            objectName: "speakerChip"
            visible: root.speech
            enabled: root.script.castReady && root.line.editable
            width: Math.min(parent.width, chipText.implicitWidth + 20 + 18)
            height: Math.max(28, chipText.implicitHeight + 6)
            activeFocusOnTab: false
            tip: ""
            Accessible.role: Accessible.Button
            Accessible.name: (root.line.kind === "thought" ? "Người nghĩ" : "Người nói") + ": " + root.speakerShown + ". Bấm để đổi"
            onClicked: { root.activate(); root.openSpeaker(chip) }
            readonly property real hue: Cast.hueOf(root.speakerShown || "")
            Rectangle { anchors.fill: parent; radius: height / 2; color: Cast.avatarFill(chip.hue, Theme.dark) }
            Text {
                id: chipText
                objectName: "speakerChipText"
                x: 10
                width: Math.min(implicitWidth, chip.parent.width - 38)
                anchors.verticalCenter: parent.verticalCenter
                text: root.speakerShown
                color: Cast.avatarInk(chip.hue, Theme.dark)
                wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                font.pixelSize: 13
                font.weight: Theme.weightBold
            }
            Icon {
                x: chipText.x + chipText.width + 4
                anchors.verticalCenter: parent.verticalCenter
                size: 14
                name: root.line.wish && root.line.wish.state === "pending" ? "clock" : root.line.wish && root.line.wish.state === "applied" ? "check" : "chevron-down"
                color: root.line.wish && root.line.wish.state === "applied" ? Theme.success : Cast.avatarInk(chip.hue, Theme.dark)
            }
        }
        Text {
            visible: !root.speech
            width: parent.width
            height: 28
            verticalAlignment: Text.AlignVCenter
            text: root.line.label || "Người kể"
            color: Theme.text3
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
        }
    }

    // ---- nút nghe: ngay trước chữ ----
    Interactive {
        objectName: "linePlay"
        visible: root.line.hasAudio === true
        x: root.textX - 36
        y: root.textY - 2
        width: 28; height: 28
        activeFocusOnTab: false
        Accessible.role: Accessible.Button
        Accessible.name: root.playing ? "Dừng" : "Nghe câu: " + root.line.text
        onClicked: Clip.toggle(root.clipId, root.store ? root.store.path("/media/books/" + root.bookId + "/samples/" + root.line.segmentId) : "")
        Rectangle { anchors.fill: parent; radius: width / 2; color: Theme.panel; opacity: parent.hovered ? 1 : 0 }
        Icon { anchors.centerIn: parent; size: 14; name: root.playing ? "pause" : "play"; color: parent.hovered ? Theme.text : Theme.text3 }
    }

    // ---- chữ và dòng trạng thái ----
    Column {
        id: body
        x: root.textX
        y: root.textY
        width: Math.max(0, Math.min(704, root.width - x - actions.width - 16))
        spacing: 2
        Item {
            width: parent.width
            height: Math.max(lineText.height, thinkTag.visible ? 22 : 0)
            Icon {
                visible: root.selected
                y: 4
                name: "check"
                size: 16
                color: Theme.accentText
            }
            Rectangle {
                id: thinkTag
                visible: root.line.kind === "thought"
                x: root.selected ? 22 : 0
                y: 3
                width: thinkText.implicitWidth + 12
                height: 18
                radius: Theme.radiusControl
                color: Theme.hover
                Text { id: thinkText; anchors.centerIn: parent; text: "nghĩ"; color: Theme.text2; font.pixelSize: 11; font.weight: Theme.weightMedium }
            }
            Text {
                id: lineText
                objectName: "lineText"
                x: (root.selected ? 22 : 0) + (thinkTag.visible ? thinkTag.width + 6 : 0)
                width: parent.width - x
                text: root.marks.length ? S.markedHtml(root.line.text, root.marks, Theme.warningSoft) : root.line.text
                textFormat: root.marks.length ? Text.StyledText : Text.PlainText
                color: root.selected ? Theme.accentText : root.speech ? Theme.text : Theme.text2
                font.pixelSize: 15
                font.italic: root.line.kind === "thought"
                lineHeight: 1.5
                wrapMode: Text.Wrap
            }
        }
        Note_ {
            visible: !!root.line.spoken
            text: "Đọc là: " + (root.line.spoken || "")
        }
        Item {
            id: deliveryAnchorItem
            width: parent.width
            height: deliveryInline.visible ? deliveryInline.height : 0
            DeliveryChip_ {
                id: deliveryInline
                visible: root.script.castReady && root.hasEmotion && !root.plain
                quiet: !root.speech && !root.active
            }
        }
        Note_ {
            objectName: "lineWishNote"
            visible: !!root.line.lineWish && root.line.lineWish.state === "pending"
            icon: "clock"
            text: visible ? S.lineWishText(root.line.lineWish, root.pendingNote) : ""
        }
        Note_ {
            visible: !!root.line.lineWish && root.line.lineWish.state === "refused"
            icon: "triangle-alert"
            tone: Theme.danger
            text: visible ? "Cách đọc mới không áp được: " + root.line.lineWish.reason : ""
        }
        Item {
            objectName: "lineHint"
            visible: !!root.line.hint && !root.context && (!root.line.wish || root.line.wish.state === "refused")
            width: parent.width
            height: visible ? hintFlow.height + 4 : 0
            Flow {
                id: hintFlow
                y: 4
                width: parent.width
                spacing: 8
                // Cao bằng nút "Gán cho" để lời nghi và nút thẳng hàng giữa
                Item {
                    width: Math.min(hintNote.implicitWidth, hintFlow.width)
                    height: Math.max(hintAssign.visible ? hintAssign.height : 0, hintNote.height)
                    Note_ {
                        id: hintNote
                        width: parent.width
                        anchors.verticalCenter: parent.verticalCenter
                        icon: "triangle-alert"
                        tone: Theme.warning
                        text: root.line.hint ? root.line.hint.note : ""
                    }
                }
                Button {
                    id: hintAssign
                    objectName: "hintAssign"
                    visible: !!root.suggested && root.script.castReady && root.suggested.value !== root.line.current && !(root.line.wish && root.line.wish.value === root.suggested.value)
                    size: "sm"
                    kind: "ghost"
                    text: root.suggested ? "Gán cho " + root.suggested.label : ""
                    onClicked: root.pick(root.suggested)
                }
            }
        }
        Item {
            objectName: "retakeNote"
            visible: root.line.retake === "pending"
            width: parent.width
            height: visible ? retakeFlow.height + 4 : 0
            Flow {
                id: retakeFlow
                y: 4
                width: parent.width
                spacing: 6
                Note_ { width: Math.min(implicitWidth, retakeFlow.width); icon: "clock"; text: "Đã xin thu lại câu này - " + root.pendingNote + "." }
                TextLink { objectName: "retakeCancel"; accent: true; small: true; text: "Bỏ"; onClicked: root.cancelRetake() }
            }
        }
        Note_ {
            objectName: "wishNote"
            visible: !!root.line.wish && root.line.wish.state === "pending"
            icon: "clock"
            text: visible ? "Đã ghi " + root.line.wish.label + " (máy gán " + root.line.label + ") - " + root.pendingNote + "." : ""
        }
        Note_ {
            visible: !!root.line.wish && root.line.wish.state === "refused"
            icon: "triangle-alert"
            tone: Theme.danger
            text: visible ? "Yêu cầu " + root.line.wish.label + " không áp được: " + root.line.wish.reason : ""
        }
    }

    // ---- việc phụ: chỉ khi rê / chọn câu ----
    Row {
        id: actions
        anchors.right: parent.right
        anchors.rightMargin: 8
        y: root.textY - 2
        spacing: 2
        Interactive {
            objectName: "lineRetake"
            visible: root.line.hasAudio === true && root.line.retake !== "pending"
            width: 28; height: 28
            opacity: root.shownActions || activeFocus ? 1 : 0
            activeFocusOnTab: false
            tip: "Thu lại câu này (R)"
            Accessible.role: Accessible.Button
            Accessible.name: "Thu lại câu: " + root.line.text
            onClicked: root.retake()
            Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
            Rectangle { anchors.fill: parent; radius: width / 2; color: Theme.panel; opacity: parent.hovered ? 1 : 0 }
            Icon { anchors.centerIn: parent; size: 14; name: "refresh-cw"; color: parent.hovered ? Theme.text : Theme.text3 }
        }
        Item {
            width: plainChip.visible ? plainChip.width : 0
            height: 28
            DeliveryChip_ {
                id: plainChip
                visible: root.script.castReady && root.hasEmotion && root.plain
                quiet: !root.speech && !root.active
            }
        }
    }

    component Note_: Item {
        id: note
        property string icon: ""
        property color tone: Theme.text2
        property alias text: noteText.text
        width: parent ? parent.width : 0
        implicitWidth: noteText.implicitWidth + (icon ? 20 : 0)
        height: visible ? noteText.height + 2 : 0
        Icon { visible: note.icon !== ""; y: 2; name: note.icon || "clock"; size: 14; color: note.tone }
        Text {
            id: noteText
            x: note.icon ? 20 : 0
            width: Math.max(0, note.width - x)
            color: note.tone
            wrapMode: Text.Wrap
            font.pixelSize: Theme.sizeCaption
        }
    }
    // Chip cách đọc ("Vui · mạnh"): bấm mở bảng sửa cách đọc của câu
    component DeliveryChip_: Interactive {
        id: delivery
        property bool quiet: false
        readonly property bool waiting: !!root.line.lineWish && root.line.lineWish.state === "pending"
        readonly property bool hiddenNow: root.plain ? !root.active : quiet
        objectName: "deliveryChip"
        width: deliveryRow.width + 12
        height: 24
        opacity: hiddenNow && !hover.hovered ? 0 : 1
        activeFocusOnTab: false
        Accessible.role: Accessible.Button
        Accessible.name: "Cách đọc: " + deliveryText.text + ". Bấm để sửa"
        onClicked: { root.activate(); root.openDelivery(delivery) }
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.panel; opacity: delivery.hovered ? 1 : 0 }
        Row {
            id: deliveryRow
            x: 6
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4
            Icon { visible: delivery.waiting; anchors.verticalCenter: parent.verticalCenter; name: "clock"; size: 12; color: Theme.text2 }
            Text {
                id: deliveryText
                objectName: "deliveryText"
                text: S.deliveryChip(root.line)
                color: delivery.waiting ? Theme.text2 : delivery.hovered ? Theme.text : Theme.text3
                font.pixelSize: 11
                font.weight: Theme.weightMedium
            }
        }
    }
}
