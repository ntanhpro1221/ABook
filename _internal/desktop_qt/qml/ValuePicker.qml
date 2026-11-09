import "UiStrings.js" as S
import "ValuePickerLogic.js" as Logic
import QtQuick
import ABook

// Bộ chọn giá trị số - MỘT kiểu cho cả app (DESIGN mục 6 "Chọn giá trị"; web shared/ValuePicker.tsx, Android ValuePicker.kt cùng cấu trúc), từ trên xuống:
//  1. giá trị hiện tại chữ lớn - bấm vào là gõ số (Enter xác nhận, Esc bỏ, kẹp trong biên và báo nhẹ "Trong khoảng a–b");
//  2. thước kéo tự do giữa nút - / + (giữ để lặp); nấc hút + tiếng ở các giá trị tiêu biểu; mũi tên một bước, PageUp/PageDown mười bước, Home/End hai đầu;
//  3. hàng chip giá trị tiêu biểu, chip trùng giá trị đang chọn tô màu nhấn;
//  4. con của nó (`data` mặc định): lựa chọn đặc biệt không phải số ("Hết chương này"), hàng riêng dưới cùng.
// `picked(value)` là lúc áp (thả tay, chạm chip, -/+, Enter, phím); khi kéo, chữ lớn và thước chạy theo tay, `previewed(value)` nếu cần nghe ngay.
// `dense`: hàng gọn cho danh sách nhiều núm (âm thanh, Cài đặt) - tên + giá trị một hàng, thước, chip nhỏ.
Column {
    id: root
    required property var spec
    property real value: spec.min
    property string label: ""
    property string hint: ""
    property bool dense: false
    // false: giá trị này chưa phải lựa chọn đang áp (hẹn giờ đang "Hết chương") - không tô chip nào, chọn đúng giá trị đang đứng vẫn là đặt.
    property bool current: true
    // Chữ của một giá trị kèm đơn vị ("23 phút", "1,35×"); chữ trên chip (mặc định như `format`).
    property var format: function(v) { return Logic.formatNumber(root.spec, v) }
    property var chipLabel: null
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

    spacing: dense ? 2 : Theme.s8
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
        commit(next)
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

    // 1. Tên + giá trị (hàng gọn) hay chữ lớn ở giữa.
    Item {
        width: root.width
        height: Math.max(root.dense ? 32 : 48, nameColumn.implicitHeight, valueBox.height)
        Column {
            id: nameColumn
            visible: root.dense
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - valueBox.width - Theme.s12
            Text { width: parent.width; text: root.label; wrapMode: Text.Wrap; color: Theme.text; font.pixelSize: Theme.sizeBodySmall; font.weight: Theme.weightMedium }
            Text { visible: root.hint !== ""; width: parent.width; text: root.hint; wrapMode: Text.Wrap; color: Theme.text2; font.pixelSize: Theme.sizeCaption }
        }
        Item {
            id: valueBox
            anchors.verticalCenter: parent.verticalCenter
            x: root.dense ? parent.width - width : (parent.width - width) / 2
            width: root.typing ? input.width : display.width
            height: root.typing ? input.height : display.height
            Interactive {
                id: display
                objectName: "valueDisplay"
                visible: !root.typing
                enabled: root.enabled
                width: bigText.implicitWidth + 2 * Theme.s8
                height: root.dense ? 32 : 48
                tip: S.s_cham_de_go_so_adc1d0d1
                Accessible.role: Accessible.Button
                Accessible.name: root.label + ": " + root.format(root.shown) + ". " + S.s_cham_de_go_so_adc1d0d1
                onClicked: { root.clampNote = false; root.typing = true; input.text = Logic.formatNumber(root.spec, root.shown); input.selectAll(); input.forceActiveFocus() }
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.text; opacity: display.hovered ? 0.05 : 0 }
                Text {
                    id: bigText
                    anchors.centerIn: parent
                    text: root.format(root.shown)
                    color: root.dense ? Theme.text2 : Theme.text
                    font.pixelSize: root.dense ? Theme.sizeBodySmall : Theme.sizeTitlePhone
                    font.weight: root.dense ? Theme.weightRegular : 600
                    font.features: { "tnum": 1 }
                }
            }
            FormField {
                id: input
                objectName: "valueInput"
                visible: root.typing
                label: root.label
                width: root.dense ? 88 : 128
                horizontalAlignment: TextEdit.AlignHCenter
                inputMethodHints: Qt.ImhFormattedNumbersOnly
                escapeLocal: true
                font.features: { "tnum": 1 }
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
        height: 44
        IconButton {
            objectName: "valueDown"
            anchors.verticalCenter: parent.verticalCenter
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
            width: parent.width - 2 * Theme.buttonHeight
            height: parent.height
            activeFocusOnTab: root.enabled
            readonly property real inset: 8
            readonly property real fraction: Logic.toFraction(root.spec, root.shown)
            Accessible.role: Accessible.Slider
            Accessible.name: root.label
            Accessible.description: root.format(root.shown)
            Keys.onPressed: event => {
                if (!root.enabled) return
                const steps = {[Qt.Key_Right]: 1, [Qt.Key_Up]: 1, [Qt.Key_Left]: -1, [Qt.Key_Down]: -1,
                               [Qt.Key_PageUp]: Logic.PAGE_STEPS, [Qt.Key_PageDown]: -Logic.PAGE_STEPS}[event.key]
                if (steps !== undefined) root.nudge(steps)
                else if (event.key === Qt.Key_Home) root.commit(root.spec.min)
                else if (event.key === Qt.Key_End) root.commit(root.spec.max)
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
                model: root.spec.typical
                Rectangle {
                    required property var modelData
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
                onReleased: if (root.moving !== null) root.commit(root.moving)
                onCanceled: root.moving = null
            }
        }
        IconButton {
            objectName: "valueUp"
            anchors.verticalCenter: parent.verticalCenter
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

    // 3. Chip giá trị tiêu biểu.
    Flow {
        visible: root.spec.typical.length > 0
        width: root.width
        spacing: root.dense ? Theme.s4 : Theme.s8
        Repeater {
            model: root.spec.typical
            ChoiceChip {
                required property var modelData
                required property int index
                objectName: "valueChip_" + Logic.formatNumber(root.spec, modelData)
                enabled: root.enabled
                implicitHeight: root.dense ? 28 : 36
                text: root.chipLabel ? root.chipLabel(modelData) : root.format(modelData)
                selected: index === root.selectedChip
                Accessible.name: root.format(modelData)
                onClicked: { Feedback.play("toggle"); root.clampNote = false; root.commit(modelData) }
            }
        }
    }

    // 4. Lựa chọn đặc biệt (con do chỗ dùng đặt vào).
    Item {
        id: specialSlot
        visible: children.length > 0
        width: root.width
        height: childrenRect.height
    }
}
