import "UiStrings.js" as S
import QtQuick
import ABook
import "ScriptLogic.js" as Script
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

    readonly property bool speech: Script.isSpeech(line)
    readonly property bool wide: width >= 640
    readonly property bool shownActions: active || hover.hovered
    readonly property string clipId: "script-" + line.segmentId
    readonly property bool playing: Clip.current === clipId
    readonly property var suggested: Script.suggestedOf(script, line)
    readonly property bool hasEmotion: line.emotion !== null && line.emotion !== undefined
    readonly property bool plain: Script.plainDelivery(line)
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
        Reveal { shown: root.speech || root.wide }
        Interactive {
            id: chip
            objectName: "speakerChip"
            Reveal { shown: root.speech }
            enabled: root.script.castReady && root.line.editable
            width: Math.min(parent.width, chipText.implicitWidth + 20 + 18)
            height: Math.max(28, chipText.implicitHeight + 6)
            activeFocusOnTab: false
            tip: ""
            Accessible.role: Accessible.Button
            Accessible.name: (root.line.kind === "thought" ? S.s_nguoi_nghi_ce1afa0f : S.s_nguoi_noi_9620707b) + ": " + root.speakerShown + S.s_bam_de_doi_ee78d9fa
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
                font.pixelSize: 14
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
            Reveal { shown: !root.speech }
            width: parent.width
            height: 28
            verticalAlignment: Text.AlignVCenter
            text: root.line.label || S.s_nguoi_ke_fd36cd15
            color: Theme.text3
            wrapMode: Text.WrapAtWordBoundaryOrAnywhere
            font.pixelSize: Theme.sizeCaption
        }
    }

    // ---- nút nghe: ngay trước chữ ----
    Interactive {
        objectName: "linePlay"
        Reveal { shown: root.line.hasAudio === true }
        x: root.textX - 36
        y: root.textY - 2
        width: 28; height: 28
        activeFocusOnTab: false
        Accessible.role: Accessible.Button
        Accessible.name: root.playing ? S.s_dung_11554138 : S.s_nghe_cau_22ae467f + root.line.text
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
        spacing: 4
        Item {
            width: parent.width
            height: Math.max(lineText.height, thinkTag.visible ? 22 : 0)
            Icon {
                Reveal { shown: root.selected }
                y: 4
                name: "check"
                size: 16
                color: Theme.accentText
            }
            Rectangle {
                id: thinkTag
                Reveal { shown: root.line.kind === "thought" }
                x: root.selected ? 22 : 0
                y: 3
                width: thinkText.implicitWidth + 12
                height: 18
                radius: Theme.radiusControl
                color: Theme.hover
                Text { id: thinkText; anchors.centerIn: parent; text: S.s_nghi_821be246; color: Theme.text2; font.pixelSize: 12; font.weight: Theme.weightMedium }
            }
            Text {
                id: lineText
                objectName: "lineText"
                x: (root.selected ? 22 : 0) + (thinkTag.visible ? thinkTag.width + 6 : 0)
                width: parent.width - x
                text: root.marks.length ? Script.markedHtml(root.line.text, root.marks, Theme.warningSoft) : root.line.text
                textFormat: root.marks.length ? Text.StyledText : Text.PlainText
                color: root.selected ? Theme.accentText : root.speech ? Theme.text : Theme.text2
                font.pixelSize: 16
                font.italic: root.line.kind === "thought"
                lineHeight: 1.5
                wrapMode: Text.Wrap
            }
        }
        Note_ {
            Reveal { shown: !!root.line.spoken }
            text: S.s_doc_la_4f8195e0 + (root.line.spoken || "")
        }
        Item {
            id: deliveryAnchorItem
            width: parent.width
            height: deliveryInline.visible ? deliveryInline.height : 0
            DeliveryChip_ {
                id: deliveryInline
                Reveal { shown: root.script.castReady && root.hasEmotion && !root.plain }
                quiet: !root.speech && !root.active
            }
        }
        Note_ {
            objectName: "lineWishNote"
            Reveal { shown: !!root.line.lineWish && root.line.lineWish.state === "pending" }
            icon: "clock"
            text: visible ? Script.lineWishText(root.line.lineWish, root.pendingNote) : ""
        }
        Note_ {
            Reveal { shown: !!root.line.lineWish && root.line.lineWish.state === "refused" }
            icon: "triangle-alert"
            tone: Theme.danger
            text: visible ? S.s_cach_doc_moi_khong_ap_duoc_3b993682 + root.line.lineWish.reason : ""
        }
        Item {
            objectName: "lineHint"
            Reveal { shown: !!root.line.hint && !root.context && (!root.line.wish || root.line.wish.state === "refused") }
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
                    Reveal { shown: !!root.suggested && root.script.castReady && root.suggested.value !== root.line.current && !(root.line.wish && root.line.wish.value === root.suggested.value) }
                    size: "sm"
                    kind: "ghost"
                    text: root.suggested ? S.s_gan_cho_6fe48d05 + root.suggested.label : ""
                    onClicked: root.pick(root.suggested)
                }
            }
        }
        Item {
            objectName: "retakeNote"
            Reveal { shown: root.line.retake === "pending" }
            width: parent.width
            height: visible ? retakeFlow.height + 4 : 0
            Flow {
                id: retakeFlow
                y: 4
                width: parent.width
                spacing: 8
                Note_ { width: Math.min(implicitWidth, retakeFlow.width); icon: "clock"; text: S.s_da_xin_thu_lai_cau_nay_7919d78c + root.pendingNote + "." }
                TextLink { objectName: "retakeCancel"; accent: true; small: true; text: S.s_bo_e07d3f4d; onClicked: root.cancelRetake() }
            }
        }
        Note_ {
            objectName: "wishNote"
            Reveal { shown: !!root.line.wish && root.line.wish.state === "pending" }
            icon: "clock"
            text: visible ? S.s_da_ghi_6b67a4c2 + root.line.wish.label + S.s_may_gan_c2531001 + root.line.label + ") - " + root.pendingNote + "." : ""
        }
        Note_ {
            Reveal { shown: !!root.line.wish && root.line.wish.state === "refused" }
            icon: "triangle-alert"
            tone: Theme.danger
            text: visible ? S.s_yeu_cau_6833dc12 + root.line.wish.label + S.s_khong_ap_duoc_1fe639f0 + root.line.wish.reason : ""
        }
    }

    // ---- việc phụ: chỉ khi rê / chọn câu ----
    Row {
        id: actions
        anchors.right: parent.right
        anchors.rightMargin: 8
        y: root.textY - 2
        spacing: 4
        Interactive {
            objectName: "lineRetake"
            Reveal { shown: root.line.hasAudio === true && root.line.retake !== "pending" }
            width: 28; height: 28
            opacity: root.shownActions || activeFocus ? 1 : 0
            activeFocusOnTab: false
            tip: S.s_thu_lai_cau_nay_r_04ccfef4
            Accessible.role: Accessible.Button
            Accessible.name: S.s_thu_lai_cau_a4677ead + root.line.text
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
                Reveal { shown: root.script.castReady && root.hasEmotion && root.plain }
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
        Icon { Reveal { shown: note.icon !== "" } y: 2; name: note.icon || "clock"; size: 14; color: note.tone }
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
        Accessible.name: S.s_cach_doc_0_bam_de_sua_cbabcbd5(deliveryText.text)
        onClicked: { root.activate(); root.openDelivery(delivery) }
        Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
        Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.panel; opacity: delivery.hovered ? 1 : 0 }
        Row {
            id: deliveryRow
            x: 6
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4
            Icon { Reveal { shown: delivery.waiting } anchors.verticalCenter: parent.verticalCenter; name: "clock"; size: 12; color: Theme.text2 }
            Text {
                id: deliveryText
                objectName: "deliveryText"
                text: Script.deliveryChip(root.line)
                color: delivery.waiting ? Theme.text2 : delivery.hovered ? Theme.text : Theme.text3
                font.pixelSize: 12
                font.weight: Theme.weightMedium
            }
        }
    }
}
