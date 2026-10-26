import QtQuick
import QtQuick.Controls.Basic as C
import ABook

// Ô chọn (Select của shared/ui.tsx): ô cao 40, viền điều khiển, nền --panel, chữ 14, chevron 14 bên phải; mặc định trải hết cột như ô nhập,
// `inline` thì rộng theo chữ (giờ / phút đứng cạnh nhau). Danh sách xổ là lớp nổi neo dưới ô (lên trên nếu thiếu chỗ): mục đang chọn có dấu
// tích ĐẦU dòng (SelectionMark), tên dài xuống dòng, mũi tên / Enter chọn, Back / bấm ra ngoài đóng. Mở / đóng: trượt 8 px + mờ.
Interactive {
    id: root
    property var options: []            // [{value, label}]
    property var value: ""
    property string label: ""           // tên cho trình đọc màn hình
    property bool inline: false
    property bool tabular: false
    signal picked(var value)
    readonly property int currentIndex: {
        for (let i = 0; i < options.length; ++i) if (String(options[i].value) === String(value)) return i
        return -1
    }
    readonly property string currentLabel: currentIndex >= 0 ? options[currentIndex].label : ""
    Accessible.role: Accessible.ComboBox
    Accessible.name: label
    Accessible.description: currentLabel
    pressScaling: false
    implicitHeight: Math.max(40, shownText.implicitHeight + 16)
    implicitWidth: inline ? shownText.implicitWidth + 10 + 14 + 8 + 10 : 200
    opacity: enabled ? 1 : 0.5
    onClicked: list.visible ? list.close() : list.show()
    Keys.onDownPressed: list.show()
    Keys.onUpPressed: list.show()

    Rectangle {
        anchors.fill: parent
        radius: Theme.radiusControl
        color: Theme.panel
        border.width: 1
        border.color: list.visible || root.activeFocus ? Theme.focus : Theme.controlLine
        Behavior on border.color { ColorAnimation { duration: Theme.motionFast } }
    }
    Text {
        id: shownText
        x: 10
        width: root.width - x - 10 - 14 - 8
        anchors.verticalCenter: parent.verticalCenter
        text: root.currentLabel
        color: Theme.text
        wrapMode: Text.Wrap
        font.pixelSize: Theme.sizeBodySmall
        font.features: root.tabular ? {"tnum": 1} : {}
    }
    Icon {
        anchors.right: parent.right
        anchors.rightMargin: 10
        anchors.verticalCenter: parent.verticalCenter
        name: "chevron-down"
        size: 14
        color: Theme.text2
    }

    C.Popup {
        id: list
        property real shown: 0
        parent: C.Overlay.overlay
        padding: 6
        modal: false
        focus: true
        closePolicy: C.Popup.CloseOnPressOutside | C.Popup.CloseOnEscape
        width: Math.max(root.width, 160)
        function show() {
            if (visible) return
            const p = root.mapToItem(parent, 0, 0)
            const h = Math.min(implicitHeight, 320)
            const below = p.y + root.height + 4 + h <= parent.height - 8
            x = Math.max(8, Math.min(parent.width - width - 8, p.x))
            y = below ? p.y + root.height + 4 : Math.max(8, p.y - h - 4)
            height = h
            open()
            Nav.openLayer(list)
            rows.currentIndex = Math.max(0, root.currentIndex)
            rows.positionViewAtIndex(rows.currentIndex, ListView.Contain)
            rows.forceActiveFocus()
        }
        onClosed: { Nav.closedLayer(list); root.forceActiveFocus(Qt.OtherFocusReason) }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Theme.motionFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate }
                            NumberAnimation { property: "shown"; from: 0; to: 1; duration: Theme.reduceMotion ? 0 : Theme.motionFast; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeDecelerate } }
        exit: Transition { NumberAnimation { property: "opacity"; from: 1; to: 0; duration: Theme.motionFastOut; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate }
                           NumberAnimation { property: "shown"; from: 1; to: 0; duration: Theme.reduceMotion ? 0 : Theme.motionFastOut; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeAccelerate } }
        background: Item {
            transform: Translate { y: -8 * (1 - list.shown) }
            Rectangle { anchors.fill: parent; anchors.margins: -6; radius: Theme.radiusCover + 6; color: "#000000"; opacity: 0.05 }
            Rectangle { anchors.fill: parent; radius: Theme.radiusCover; color: Theme.panel; border.width: 1; border.color: Theme.line }
        }
        contentItem: ListView {
            id: rows
            transform: Translate { y: -8 * (1 - list.shown) }
            implicitHeight: contentHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: root.options
            keyNavigationEnabled: true
            highlightMoveDuration: 0
            Keys.onReturnPressed: pick(currentIndex)
            Keys.onEnterPressed: pick(currentIndex)
            Keys.onSpacePressed: pick(currentIndex)
            function pick(i) { if (i >= 0 && i < root.options.length) root.picked(root.options[i].value); list.close() }
            delegate: Interactive {
                id: row
                required property var modelData
                required property int index
                readonly property bool selected: index === root.currentIndex
                width: ListView.view.width
                height: Math.max(36, rowText.implicitHeight + 16)
                pressScaling: false
                activeFocusOnTab: false
                externalFocus: ListView.isCurrentItem && rows.activeFocus
                Accessible.role: Accessible.ListItem
                Accessible.name: modelData.label
                Accessible.selected: selected
                onClicked: rows.pick(index)
                Rectangle { anchors.fill: parent; radius: Theme.radiusControl; color: Theme.hover; opacity: row.hovered || row.ListView.isCurrentItem ? 1 : 0 }
                Icon {
                    x: 8
                    anchors.verticalCenter: parent.verticalCenter
                    name: "check"
                    size: 16
                    color: Theme.accentText
                    opacity: row.selected ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: Theme.motionFast } }
                }
                Text {
                    id: rowText
                    x: 8 + 16 + 8
                    width: row.width - x - 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: row.modelData.label
                    wrapMode: Text.Wrap
                    color: row.selected ? Theme.accentText : Theme.text
                    font.pixelSize: Theme.sizeBodySmall
                    font.features: root.tabular ? {"tnum": 1} : {}
                }
            }
        }
    }
}
