import QtQuick
import ABook
import "ExportLogic.js" as Logic

// "Kiểu bản xuất" của hộp Xuất (radiogroup chia vạch của ExportBook.tsx): mỗi hàng một biểu tượng + tên đậm + lời giải thích; hàng đang chọn mực nhấn và có gạch chân
// hổ phách trượt giữa các hàng (SlidingIndicator "line"). Mũi tên lên / xuống đổi lựa chọn. Chữ xuống dòng, không bao giờ cắt.
Item {
    id: root
    property var kinds: Logic.KINDS
    property string value: "mp3"
    signal picked(string value)
    implicitHeight: column.height
    height: implicitHeight
    Accessible.role: Accessible.RadioButton
    Accessible.name: "Kiểu bản xuất"
    readonly property int selectedIndex: Math.max(0, root.kinds.findIndex(item => item.value === root.value))

    function step(direction) {
        const next = Math.max(0, Math.min(root.kinds.length - 1, selectedIndex + direction))
        if (next !== selectedIndex) root.picked(root.kinds[next].value)
        const row = rows.itemAt(next)
        if (row) row.forceActiveFocus(Qt.TabFocusReason)
    }
    Column {
        id: column
        width: root.width
        Repeater {
            id: rows
            model: root.kinds
            delegate: Item {
                id: row
                required property var modelData
                required property int index
                readonly property bool selected: modelData.value === root.value
                readonly property bool last: index === root.kinds.length - 1
                objectName: "exportKind_" + modelData.value
                width: column.width
                height: Math.max(40, texts.height + 24) + (last ? 0 : 1)
                activeFocusOnTab: selected
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData.title
                Accessible.description: modelData.detail
                Accessible.checked: selected
                Keys.onDownPressed: root.step(1)
                Keys.onUpPressed: root.step(-1)
                Keys.onReturnPressed: root.picked(modelData.value)
                Keys.onSpacePressed: root.picked(modelData.value)
                function choose() { forceActiveFocus(Qt.MouseFocusReason); root.picked(modelData.value) }
                Rectangle { width: parent.width; height: parent.height - (row.last ? 0 : 1); color: Theme.hover; opacity: hover.hovered && !row.selected ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Theme.motionFast } } }
                Rectangle { y: parent.height - 1; width: parent.width; height: 1; color: Theme.line; visible: !row.last }
                HoverHandler { id: hover; cursorShape: Qt.PointingHandCursor }
                TapHandler { onTapped: row.choose() }
                Icon { x: 0; y: 12 + 2; name: row.modelData.icon; size: 16; color: Theme.accentText }
                Column {
                    id: texts
                    x: 28
                    y: 12
                    width: parent.width - x
                    Text {
                        width: parent.width
                        text: row.modelData.title
                        color: row.selected ? Theme.accentText : Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                        font.weight: Theme.weightBold
                        Behavior on color { ColorAnimation { duration: Theme.reduceMotion ? 0 : Theme.motionMedium } }
                    }
                    Text {
                        width: parent.width
                        text: row.modelData.detail
                        color: Theme.text2
                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                        font.pixelSize: Theme.sizeBodySmall
                    }
                }
            }
        }
    }
    // Gạch chân của hàng đang chọn: trượt giữa các hàng; giảm chuyển động thì nhảy
    Rectangle {
        // rows.count trong biểu thức: tính lại khi các hàng vừa dựng xong (itemAt không báo đổi)
        readonly property Item target: rows.count > 0 ? rows.itemAt(root.selectedIndex) : null
        objectName: "exportKindLine"
        visible: target !== null
        x: 0
        y: target ? target.y + target.height - height - (target.last ? 0 : 1) : 0
        width: root.width
        height: 2
        color: Theme.accent
        Behavior on y { enabled: !Theme.reduceMotion; NumberAnimation { duration: Theme.motionMedium; easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard } }
    }
}
