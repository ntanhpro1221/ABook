import "UiStrings.js" as S
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Bộ chọn giá trị số - MỘT kiểu cho cả app (DESIGN mục 6 "Chọn giá trị"; web shared/ValuePicker.tsx, Android ValuePicker.kt cùng cấu trúc), từ trên xuống:
//  1. giá trị hiện tại chữ lớn - bấm vào là gõ số (Enter xác nhận, Esc bỏ, kẹp trong biên và báo nhẹ "Trong khoảng a–b");
//  2. thước kéo tự do giữa nút - / + (giữ để lặp); nấc hút + tiếng ở các giá trị tiêu biểu; mũi tên một bước, PageUp/PageDown mười bước, Home/End hai đầu;
//  3. hàng chip giá trị tiêu biểu, chip trùng giá trị đang chọn chữ --text đậm;
//  4. con của nó (`data` mặc định): lựa chọn đặc biệt không phải số ("Hết chương này"), hàng riêng dưới cùng.
// `picked(value)` là lúc áp (thả tay, chạm chip, -/+, Enter, phím); khi kéo, chữ lớn và thước chạy theo tay, `previewed(value)` nếu cần nghe ngay.
// `dense`: two rows: label + editable value, then ruler with numeric labels centred below its detents.
Column {
    id: root
    required property var spec
    property real value: spec.min
    property string label: ""
    property string hint: ""
    property bool dense: false
    // The same editable value and step controls, with a label above, for counts without a ruler.
    property bool stepperOnly: false
    property real fontScale: 1
    // false: giá trị này chưa phải lựa chọn đang áp (hẹn giờ đang "Hết chương") - không tô chip nào, chọn đúng giá trị đang đứng vẫn là đặt.
    property bool current: true
    // Chữ của một giá trị kèm đơn vị ("23 phút", "1,35×"); chữ trên chip (mặc định như `format`).
    property var format: function(v) { return Logic.formatNumber(root.spec, v) }
    property var chipLabel: null
    // Optional draft path; chips and typing continue to confirm through picked().
    property var adjustValue: null
    default property alias extra: specialSlot.data
    signal picked(real value)
    signal previewed(real value)

    property var moving: null
    property bool typing: false
    property bool clampNote: false
    readonly property real shown: Logic.quantize(spec, moving !== null ? moving : value)
    readonly property int selectedChip: current ? Logic.chipIndex(spec, shown) : -1
    readonly property string rangeText: S.s_trong_khoang_0_1_5313ae3f(format(spec.min), format(spec.max))
    property real latest: shown
    // Hosts can reserve one measured shortcut row before deciding their panel width.
    // The shortcuts live between the -/+ buttons (96px), either as captions under their detents or as one chip row - whichever is narrower.
    readonly property real minimumWidth: {
        if (dense) return 0
        const row = chips.widths.reduce(function(sum, width) { return sum + width }, 0) + Math.max(0, chips.widths.length - 1) * 4
        const captions = Logic.minAlignedWidth(spec.typical.map(function(v) { return Logic.toFraction(root.spec, v) }), labelWidths, 8, 4)
        return 96 + (captions > 0 ? Math.min(captions, row) : row)
    }

    // Measured on real Text items in the selected (bold) weight: a Text is up to 2px wider than FontMetrics.advanceWidth, which let "1,5" hang
    // past the ruler. + 1px: a centred Text snaps to whole pixels.
    readonly property var labelWidths: {
        const count = labelMeasure.count
        return spec.typical.map(function(v, i) {
            const item = i < count ? labelMeasure.itemAt(i) : null
            return 1 + (item ? item.implicitWidth : labelMetrics.advanceWidth(Logic.formatNumber(root.spec, v)) + 2)
        })
    }
    Repeater {
        id: labelMeasure
        model: root.spec.typical
        Text {
            required property var modelData
            visible: false
            text: Logic.formatNumber(root.spec, modelData)
            font.pixelSize: (root.dense ? Theme.sizeCaption : Theme.sizeBodySmall) * root.fontScale
            font.weight: Theme.weightMedium
        }
    }
    readonly property var labelPlan: Logic.tickLabels(spec.typical.map(function(v) { return Logic.toFraction(root.spec, v) }), labelWidths, ruler.width, 8, 4)
    FontMetrics { id: labelMetrics; font.pixelSize: (root.dense ? Theme.sizeCaption : Theme.sizeBodySmall) * root.fontScale; font.weight: Theme.weightMedium }

    spacing: dense ? 0 : Theme.s8
    opacity: enabled ? 1 : 0.5
    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
    onShownChanged: if (moving === null) latest = shown

    function commit(next) {
        moving = null
        latest = next
        if (next !== value || !current) picked(next)
    }
    function nudge(steps) {
        const before = latest
        const next = Logic.stepValue(spec, before, steps)
        if (next === before) return
        if (Logic.isDetent(spec, before, next)) Feedback.play("tick")
        adjust(next)
    }
    function adjust(next) {
        if (!adjustValue) { commit(next); return }
        moving = null
        latest = next
        adjustValue(next)
    }
    function dragTo(fraction) {
        const next = Logic.fromFraction(spec, fraction)
        const before = latest
        if (next === before) return
        if (Logic.isDetent(spec, before, next)) Feedback.play("tick")
        latest = next
        moving = next
        previewed(next)
    }
    function finishTyping(text) {
        typing = false
        if (text === null) return
        const parsed = Logic.parseValue(spec, text)
        if (!parsed) return
        clampNote = parsed.clamped
        if (parsed.clamped) Feedback.play("reject")
        commit(parsed.value)
    }

    Text {
        objectName: "valueSectionLabel"
        Reveal { shown: root.stepperOnly }
        text: root.label
        color: Theme.text2
        font.pixelSize: Theme.sizeBodySmall
    }

    // 1. Tên + giá trị (hàng gọn) hay chữ lớn ở giữa.
    Item {
        width: root.width
        height: Math.max(root.dense ? 20 : 48, nameColumn.implicitHeight, valueBox.height)
        IconButton {
            objectName: "valueCountDown"
            Reveal { shown: root.stepperOnly }
            width: 48; height: 48
            icon: "minus"; iconSize: 18; tip: S.s_giam_a6c2901a
            enabled: root.enabled && root.shown > root.spec.min
            onClicked: root.nudge(-1)
        }
        IconButton {
            objectName: "valueCountUp"
            Reveal { shown: root.stepperOnly }
            x: parent.width - width; width: 48; height: 48
            icon: "plus"; iconSize: 18; tip: S.s_tang_a2363bce
            enabled: root.enabled && root.shown < root.spec.max
            onClicked: root.nudge(1)
        }
        Column {
            id: nameColumn
            Reveal { shown: root.dense }
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - valueBox.width - Theme.s12
            Text { width: parent.width; text: root.label; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Text { Reveal { shown: root.hint !== "" } width: parent.width; text: root.hint; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
        Item {
            id: valueBox
            anchors.verticalCenter: parent.verticalCenter
            x: root.dense ? parent.width - width : (parent.width - width) / 2
            width: root.typing ? input.width : display.width
            height: root.typing ? input.height : root.dense ? 20 : 48
            Interactive {
                id: display
                objectName: "valueDisplay"
                Reveal { shown: !root.typing }
                enabled: root.enabled
                width: Math.max(48, bigText.implicitWidth + 2 * Theme.s8)
                height: 48
                y: (valueBox.height - height) / 2
                tip: S.s_cham_de_go_so_adc1d0d1
                Accessible.role: Accessible.Button
                Accessible.name: root.label + ": " + root.format(root.shown) + ". " + S.s_cham_de_go_so_adc1d0d1
                onClicked: { if (root.stepperOnly && !root.current) { root.commit(root.shown); return }; root.clampNote = false; root.typing = true; input.text = Logic.formatNumber(root.spec, root.shown); input.selectAll(); input.forceActiveFocus() }
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.text; opacity: display.hovered ? 0.05 : 0 }
                Text {
                    id: bigText
                    objectName: "valueNumber"
                    anchors.centerIn: parent
                    text: root.format(root.shown)
                    color: root.dense ? Theme.text2 : Theme.text
                    font.pixelSize: root.dense ? Theme.sizeBodySmall : Theme.sizeTitlePhone
                    font.weight: root.dense ? Theme.weightRegular : 600
                }
            }
            FormField {
                id: input
                objectName: "valueInput"
                Reveal { shown: root.typing }
                label: root.label
                width: root.dense ? 88 : 128
                horizontalAlignment: TextEdit.AlignHCenter
                inputMethodHints: Qt.ImhFormattedNumbersOnly
                escapeLocal: true
                onAccepted: root.finishTyping(text)
                onEscaped: root.finishTyping(null)
                onActiveFocusChanged: if (!activeFocus && root.typing) root.finishTyping(text)
            }
        }
    }
    Collapse {
        width: root.width
        open: root.clampNote
        Text {
            objectName: "valueClamped"
            width: parent.width
            text: root.rangeText
            wrapMode: Text.Wrap
            horizontalAlignment: root.dense ? Text.AlignLeft : Text.AlignHCenter
            color: Theme.text2
            font.pixelSize: Theme.sizeCaption
        }
    }

    // 2. Thước giữa nút - / +.
    Row {
        width: root.width
        Reveal { shown: !root.stepperOnly }
        height: !root.labelPlan.aligned ? 48 : root.dense ? 56 : 64
        IconButton {
            objectName: "valueDown"
            width: 48; height: 48
            y: 0
            icon: "minus"; iconSize: 18
            tip: S.s_giam_a6c2901a
            Accessible.name: S.s_giam_a6c2901a
            enabled: root.enabled && root.shown > root.spec.min
            opacity: enabled ? 1 : 0.4
            onClicked: if (!downRepeat.fired) root.nudge(-1)
            onPressedChanged: downRepeat.hold(pressed)
            Timer {
                id: downRepeat
                property bool fired: false
                function hold(on) { if (on) { fired = false; interval = 400; start() } else stop() }
                repeat: true
                onTriggered: { fired = true; interval = 80; root.nudge(-1) }
            }
        }
        Item {
            id: ruler
            objectName: "valueRuler"
            width: parent.width - 96
            height: 48
            activeFocusOnTab: root.enabled
            readonly property real inset: root.labelPlan.inset
            readonly property real fraction: Logic.toFraction(root.spec, root.shown)
            Accessible.role: Accessible.Slider
            Accessible.name: root.label
            Accessible.description: root.format(root.shown)
            Keys.onPressed: event => {
                if (!root.enabled) return
                const steps = {[Qt.Key_Right]: 1, [Qt.Key_Up]: 1, [Qt.Key_Left]: -1, [Qt.Key_Down]: -1,
                               [Qt.Key_PageUp]: Logic.PAGE_STEPS, [Qt.Key_PageDown]: -Logic.PAGE_STEPS}[event.key]
                if (steps !== undefined) root.nudge(steps)
                else if (event.key === Qt.Key_Home) root.adjust(root.spec.min)
                else if (event.key === Qt.Key_End) root.adjust(root.spec.max)
                else return
                event.accepted = true
            }
            Rectangle {
                id: track
                x: ruler.inset; width: ruler.width - 2 * ruler.inset
                anchors.verticalCenter: parent.verticalCenter
                height: 4; radius: height / 2; color: Theme.line
                Rectangle {
                    width: thumb.x + thumb.width / 2; height: parent.height; radius: height / 2; color: Theme.accent
                }
            }
            Repeater {
                model: root.labelPlan.aligned ? root.spec.typical : []
                Rectangle {
                    required property var modelData
                    required property int index
                    objectName: "valueTick_" + index
                    x: ruler.inset + Logic.toFraction(root.spec, modelData) * track.width - width / 2
                    // y theo ruler, không theo parent: lúc tấm bị huỷ, delegate của Repeater mất parent trước (TypeError).
                    y: (ruler.height - height) / 2
                    width: 2; height: 12; radius: width / 2; color: Theme.text2; opacity: 0.6
                }
            }
            Rectangle {
                id: thumb
                property real size: drag.pressed ? 18 : 14
                x: ruler.inset + ruler.fraction * track.width - width / 2 // tick-ok: thước người kéo (khi kéo không có chuyển động); chỉ chip / -,+ trượt êm
                anchors.verticalCenter: parent.verticalCenter
                width: size; height: size; radius: size / 2; color: Theme.accent
                border.width: ruler.activeFocus && Platform.keyboardNav ? 2 : 0; border.color: Theme.focus
                Behavior on x { enabled: root.moving === null && !Theme.reduceMotion; NumberAnimation { duration: Theme.motionFast } }
                Behavior on size { NumberAnimation { duration: Theme.motionFast } }
            }
            MouseArea {
                id: drag
                anchors.fill: parent
                enabled: root.enabled
                cursorShape: Qt.PointingHandCursor
                preventStealing: true
                function at(x) { return (x - ruler.inset) / track.width }
                onPressed: mouse => { ruler.forceActiveFocus(Qt.MouseFocusReason); root.dragTo(at(mouse.x)) }
                onPositionChanged: mouse => { if (pressed) root.dragTo(at(mouse.x)) }
                onReleased: if (root.moving !== null) root.adjust(root.moving)
                onCanceled: root.moving = null
            }
            Repeater {
                model: root.labelPlan.aligned ? root.spec.typical : []
                Item {
                    id: tickLabel
                    required property var modelData
                    required property int index
                    objectName: "valueChip_" + Logic.formatNumber(root.spec, modelData)
                    property bool selected: index === root.selectedChip
                    width: Math.max(48, root.labelWidths[index]); height: 48; y: root.dense ? 8 : 16
                    x: ruler.inset + Logic.toFraction(root.spec, modelData) * track.width - width / 2
                    enabled: root.enabled
                    activeFocusOnTab: root.enabled
                    Accessible.role: Accessible.Button
                    Accessible.name: root.format(modelData)
                    // Same entry point as the fallback ChoiceChip, so keyboard, assistive tech and tests activate either form alike.
                    function clicked() { Feedback.play("toggle"); root.clampNote = false; root.commit(modelData) }
                    Accessible.onPressAction: clicked()
                    Keys.onReturnPressed: clicked()
                    Keys.onEnterPressed: clicked()
                    Keys.onSpacePressed: clicked()
                    Rectangle {
                        anchors.fill: parent; anchors.margins: -2
                        radius: Theme.radiusControl
                        color: "transparent"; border.width: 2; border.color: Theme.accent
                        Reveal { shown: tickLabel.activeFocus && Platform.keyboardNav }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        preventStealing: true
                        property real startX: 0
                        property bool dragged: false
                        function fraction(x) { return (tickLabel.x + x - ruler.inset) / track.width }
                        onPressed: mouse => { startX = mouse.x; dragged = false }
                        onPositionChanged: mouse => {
                            if (!pressed) return
                            if (Math.abs(mouse.x - startX) > 4) dragged = true
                            if (dragged) root.dragTo(fraction(mouse.x))
                        }
                        onReleased: mouse => {
                            if (dragged && root.moving !== null) root.adjust(root.moving)
                            else {
                                const f = fraction(mouse.x)
                                const nearest = root.spec.typical.reduce(function(best, v) { return Math.abs(Logic.toFraction(root.spec, v) - f) < Math.abs(Logic.toFraction(root.spec, best) - f) ? v : best })
                                Feedback.play("toggle"); root.clampNote = false; root.commit(nearest)
                            }
                        }
                        onCanceled: root.moving = null
                    }
                    Text {
                        objectName: "valueLabel_" + tickLabel.index
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 22
                        text: Logic.formatNumber(root.spec, tickLabel.modelData)
                        color: tickLabel.selected ? Theme.text : Theme.text2
                        font.pixelSize: (root.dense ? Theme.sizeCaption : Theme.sizeBodySmall) * root.fontScale
                        font.weight: tickLabel.selected ? 600 : Theme.weightRegular
                    }
                }
            }
        }
        IconButton {
            objectName: "valueUp"
            width: 48; height: 48
            y: 0
            icon: "plus"; iconSize: 18
            tip: S.s_tang_a2363bce
            Accessible.name: S.s_tang_a2363bce
            enabled: root.enabled && root.shown < root.spec.max
            opacity: enabled ? 1 : 0.4
            onClicked: if (!upRepeat.fired) root.nudge(1)
            onPressedChanged: upRepeat.hold(pressed)
            Timer {
                id: upRepeat
                property bool fired: false
                function hold(on) { if (on) { fired = false; interval = 400; start() } else stop() }
                repeat: true
                onTriggered: { fired = true; interval = 80; root.nudge(1) }
            }
        }
    }

    // 3. Numeric chips, balanced with the actual font metrics.
    Item {
        id: chips
        objectName: "valueChips"
        Reveal { shown: !root.stepperOnly && !root.labelPlan.aligned && root.spec.typical.length > 0 }
        x: 48
        width: root.width - 96
        readonly property var widths: root.spec.typical.map(function(v) { return Math.max(48, metrics.advanceWidth(Logic.formatNumber(root.spec, v)) + 16) })
        readonly property var rows: Logic.chipRows(widths, width, 4)
        height: visible ? rows.length * 48 : 0
        FontMetrics { id: metrics; font.pixelSize: Theme.sizeBodySmall * root.fontScale; font.weight: Theme.weightMedium }
        Repeater {
            model: chips.rows
            Item {
                id: chipRow
                required property var modelData
                required property int index
                y: index * 48; width: chips.width; height: 48
                property var indices: modelData
                property real total: indices.reduce(function(sum, i) { return sum + chips.widths[i] }, 0)
                Repeater {
                    model: chipRow.indices
                    ChoiceChip {
                        selectedTextColor: Theme.text
                        selectedTextWeight: 600
                        required property var modelData
                        required property int index
                        readonly property real typical: root.spec.typical[modelData]
                        objectName: "valueChip_" + Logic.formatNumber(root.spec, typical)
                        enabled: root.enabled
                        textScale: root.fontScale
                        implicitWidth: chips.widths[modelData]
                        width: implicitWidth; height: 48
                        x: {
                            var before = 0
                            for (var i = 0; i < index; i++) before += chips.widths[chipRow.indices[i]]
                            return chipRow.indices.length === 1 ? (chips.width - width) / 2 : before + (chips.width - chipRow.total) * index / (chipRow.indices.length - 1)
                        }
                        text: Logic.formatNumber(root.spec, typical)
                        selected: modelData === root.selectedChip
                        Accessible.name: root.format(typical)
                        onClicked: { Feedback.play("toggle"); root.clampNote = false; root.commit(typical) }
                    }
                }
            }
        }
    }

    // 4. Lựa chọn đặc biệt (con do chỗ dùng đặt vào).
    Column {
        id: specialSlot
        Reveal { shown: specialSlot.children.length > 0 }
        width: root.width
        spacing: Theme.s4
    }
}
