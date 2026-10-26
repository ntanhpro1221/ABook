import QtQuick
import ABook

// Hàng lựa chọn (ChoiceRow của shared/ui.tsx): chữ trơn 14/500, mục đang chọn đậm màu thường + gạch chân hổ phách 2 px trượt giữa các mục
// (SlidingIndicator "line"); mục khác mực phụ, rê chuột thì đậm lên. Cách 24 ngang / 4 dọc, tự xuống hàng khi hẹp; nhãn không bao giờ cắt.
// Mũi tên trái / phải đổi lựa chọn như radiogroup.
Item {
    id: root
    property var options: []          // [{value, label}]
    property var value: ""
    property string label: ""
    signal picked(var value)
    readonly property int currentIndex: {
        for (let i = 0; i < options.length; ++i) if (String(options[i].value) === String(value)) return i
        return -1
    }
    implicitWidth: {
        let w = 0
        for (let i = 0; i < repeater.count; ++i) { const it = repeater.itemAt(i); if (it) w += it.implicitWidth + (i ? 24 : 0) }
        return w
    }
    implicitHeight: flow.implicitHeight
    width: implicitWidth
    Accessible.role: Accessible.RadioButton
    Accessible.name: label
    opacity: enabled ? 1 : 0.5

    function step(direction) {
        if (!options.length) return
        const next = Math.max(0, Math.min(options.length - 1, (currentIndex < 0 ? 0 : currentIndex) + direction))
        if (next !== currentIndex) root.picked(options[next].value)
        const it = repeater.itemAt(next)
        if (it) it.forceActiveFocus(Qt.TabFocusReason)
    }

    Flow {
        id: flow
        width: root.width
        spacing: 24
        Repeater {
            id: repeater
            model: root.options
            Interactive {
                id: choice
                required property var modelData
                required property int index
                readonly property bool selected: index === root.currentIndex
                implicitWidth: word.implicitWidth
                width: Math.min(implicitWidth, root.width)
                height: Math.max(40, word.height + 8)
                activeFocusOnTab: selected || (root.currentIndex < 0 && index === 0)
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.label
                Accessible.checked: selected
                onClicked: root.picked(modelData.value)
                Keys.onRightPressed: root.step(1)
                Keys.onLeftPressed: root.step(-1)
                Keys.onDownPressed: root.step(1)
                Keys.onUpPressed: root.step(-1)
                Text {
                    id: word
                    width: parent.width
                    anchors.verticalCenter: parent.verticalCenter
                    text: choice.modelData.label
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                    font.pixelSize: Theme.sizeBodySmall
                    font.weight: choice.selected ? Theme.weightBold : Theme.weightMedium
                    color: choice.selected || choice.hovered ? Theme.text : Theme.text2
                    Behavior on color { ColorAnimation { duration: Theme.motionMedium } }
                }
            }
        }
    }
    // Gạch chân của mục đang chọn: trượt (x, bề ngang) khi đổi mục; giảm chuyển động thì nhảy, chỉ mờ.
    Rectangle {
        // repeater.count trong biểu thức: tính lại khi các mục vừa dựng xong (itemAt không báo đổi)
        readonly property Item target: repeater.count > 0 && root.currentIndex >= 0 ? repeater.itemAt(root.currentIndex) : null
        visible: target !== null
        x: target ? target.x : 0
        y: target ? target.y + target.height - height : 0
        width: target ? target.width : 0
        height: 2
        color: Theme.accent
        Behavior on x { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    }
}
