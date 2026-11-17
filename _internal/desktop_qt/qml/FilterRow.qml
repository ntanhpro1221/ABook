import QtQuick
import ABook

// Hàng lọc (FilterRow của shared/ui.tsx; DESIGN.md 6 "Bộ lọc", "Mục đang chọn của tab và bộ lọc"): chữ trơn 14/500 cao 36, mục đang chọn chữ
// --text, mục khác --accent-text (rê chuột thì --text), gạch chân hổ phách 2 px trượt giữa các mục; không hộp segmented. MỘT hàng: khe 24
// co tới 8 khi hàng gần đủ chỗ (RowGap của web); thật sự không vừa thì cuộn ngang, mép còn cuộn được mờ dần 24 (useRowFade), mục được chọn
// tự cuộn vào tầm nhìn. Cùng vai với hàng lọc của điện thoại (LibraryChrome FilterRow: Role.Tab): hàng tab, mỗi mục một tab.
// Mũi tên trái / phải đổi mục; tiêu điểm Tab vào đúng mục đang chọn.
Item {
    id: root
    property var options: []          // [{value, label}]
    property var value: ""
    property string label: ""
    property color fadeColor: Theme.bg  // nền dưới hàng (hộp thoại: Theme.panel) - mép mờ vẽ bằng màu này
    signal picked(var value)
    readonly property int currentIndex: {
        for (let i = 0; i < options.length; ++i) if (String(options[i].value) === String(value)) return i
        return -1
    }
    // Tổng bề ngang chữ; khe co từ 24 xuống 8 trước khi cả hàng phải cuộn
    readonly property real ink: {
        let w = 0
        for (let i = 0; i < repeater.count; ++i) { const it = repeater.itemAt(i); if (it) w += it.implicitWidth }
        return w
    }
    readonly property real gap: repeater.count < 2 ? 0 : Math.max(8, Math.min(24, (width - ink) / (repeater.count - 1)))
    implicitWidth: ink + 24 * Math.max(0, repeater.count - 1)
    implicitHeight: 36
    Accessible.role: Accessible.PageTabList
    Accessible.name: label
    opacity: enabled ? 1 : 0.5

    function step(direction) {
        if (!options.length) return
        const next = Math.max(0, Math.min(options.length - 1, (currentIndex < 0 ? 0 : currentIndex) + direction))
        if (next !== currentIndex) root.picked(options[next].value)
        const it = repeater.itemAt(next)
        if (it) it.forceActiveFocus(Qt.TabFocusReason)
    }
    // Mục được chọn nằm ngoài tầm nhìn (hàng đang cuộn): trượt hàng tới vừa đủ thấy trọn mục, chừa mép mờ
    function reveal() {
        const it = currentIndex >= 0 ? repeater.itemAt(currentIndex) : null
        if (!it || !scroller.interactive) return
        const edge = 24
        let target = scroller.contentX
        if (it.x - edge < target) target = it.x - edge
        else if (it.x + it.width + edge > target + scroller.width) target = it.x + it.width + edge - scroller.width
        target = Math.max(0, Math.min(scroller.contentWidth - scroller.width, target))
        if (Math.abs(target - scroller.contentX) < 0.5) return
        if (Theme.reduceMotion) scroller.contentX = target
        else { scrollTo.to = target; scrollTo.restart() }
    }
    onCurrentIndexChanged: Later.call(root, reveal)
    onWidthChanged: Later.call(root, reveal)

    Flickable {
        id: scroller
        objectName: "filterViewport"
        anchors.fill: parent
        contentWidth: row.width
        contentHeight: height
        interactive: contentWidth > width + 0.5
        flickableDirection: Flickable.HorizontalFlick
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        NumberAnimation { id: scrollTo; target: scroller; property: "contentX"; duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard }
        Row {
            id: row
            height: root.height
            spacing: root.gap
            Repeater {
                id: repeater
                model: root.options
                Interactive {
                    id: choice
                    required property var modelData
                    required property int index
                    objectName: "filterTab_" + index
                    readonly property bool selected: index === root.currentIndex
                    implicitWidth: word.implicitWidth
                    width: implicitWidth
                    height: root.height
                    pressScaling: false
                    activeFocusOnTab: selected || (root.currentIndex < 0 && index === 0) || activeFocus
                    Accessible.role: Accessible.PageTab
                    Accessible.name: modelData.label
                    Accessible.selected: selected
                    onClicked: root.picked(modelData.value)
                    onActiveFocusChanged: if (activeFocus) Later.call(root, root.reveal)
                    Keys.onRightPressed: root.step(1)
                    Keys.onLeftPressed: root.step(-1)
                    Text {
                        id: word
                        anchors.verticalCenter: parent.verticalCenter
                        text: choice.modelData.label
                        font.pixelSize: Theme.sizeBodySmall
                        font.weight: Theme.weightMedium
                        color: choice.selected || choice.hovered ? Theme.text : Theme.accentText
                        Behavior on color { ColorAnimation { duration: Theme.motionMedium } }
                    }
                }
            }
        }
        // Gạch chân của mục đang chọn: trượt (x, bề ngang) khi đổi mục, cuộn cùng hàng; giảm chuyển động thì nhảy, chỉ mờ.
        Rectangle {
            id: underline
            objectName: "filterUnderline"
            // repeater.count trong biểu thức: tính lại khi các mục vừa dựng xong (itemAt không báo đổi)
            readonly property Item target: repeater.count > 0 && root.currentIndex >= 0 ? repeater.itemAt(root.currentIndex) : null
            Reveal { shown: underline.target !== null }
            x: target ? target.x : 0
            y: root.height - height
            width: target ? target.width : 0
            height: 2
            color: Theme.accent
            Behavior on x { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
            Behavior on width { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
        }
    }
    // Mép mờ 24 chỉ ở phía còn cuộn được (useRowFade của web): dải màu nền, không đục với máy dò (gradient)
    Rectangle {
        objectName: "filterFadeLeft"
        width: 24
        height: parent.height
        Reveal { shown: scroller.interactive && !scroller.atXBeginning }
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: root.fadeColor }
            GradientStop { position: 1; color: Qt.alpha(root.fadeColor, 0) }
        }
    }
    Rectangle {
        objectName: "filterFadeRight"
        anchors.right: parent.right
        width: 24
        height: parent.height
        Reveal { shown: scroller.interactive && !scroller.atXEnd }
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: Qt.alpha(root.fadeColor, 0) }
            GradientStop { position: 1; color: root.fadeColor }
        }
    }
}
