import QtQuick
import ABook

// Bảng nổi neo vào một nút: nội dung đặt thẳng vào trong. Mở trên nút nếu đủ chỗ, không thì dưới; trượt 8 px + thu 0,96 -> 1 khi mở, ngược lại khi đóng
// (ra nhanh hơn vào, DESIGN.md 5.2). Là một lớp của ngăn xếp Back: Esc, Alt+Left, nút Back của chuột hay bấm ra ngoài đều đóng.
Item {
    id: root
    readonly property bool coversWindow: true       // lớp phủ cả cửa sổ: bấm ra ngoài là đóng, không chạm nút bên dưới (Nav.coveredFor)
    anchors.fill: parent
    property bool open: false
    property Item anchorItem: null
    property int panelWidth: 280
    property int pad: Theme.s12
    property real maxHeight: 420
    property real shown: open ? 1 : 0
    property bool below: false
    default property alias content: holder.data
    readonly property real contentHeight: holder.childrenRect.height
    visible: shown > 0
    z: 50

    Behavior on shown {
        NumberAnimation {
            duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : (root.open ? Theme.motionFast : Theme.motionFastOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }

    function show() {
        if (open) return
        place()
        open = true
        Nav.openLayer(root)
    }
    function close() {
        if (!open) return
        open = false
        Nav.closedLayer(root)
    }
    function toggle() { open ? close() : show() }
    function place() {
        if (!anchorItem) return
        const a = anchorItem.mapToItem(root, 0, 0)
        const h = Math.min(maxHeight, contentHeight + 2 * pad)
        panel.x = Math.max(8, Math.min(root.width - panelWidth - 8, a.x + anchorItem.width / 2 - panelWidth / 2))
        below = a.y - h - Theme.s8 < 8
        panel.y = below ? a.y + anchorItem.height + Theme.s8 : a.y - h - Theme.s8
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.open
        onPressed: root.close()
    }

    Item {
        id: panel
        width: root.panelWidth
        height: Math.min(root.maxHeight, holder.childrenRect.height + 2 * root.pad)
        opacity: root.shown
        transform: Translate { y: (root.below ? -8 : 8) * (1 - root.shown) }
        scale: Theme.reduceMotion ? 1 : 0.96 + 0.04 * root.shown
        transformOrigin: root.below ? Item.Top : Item.Bottom

        // Bóng nhẹ cho lớp nổi (DESIGN.md 5.5: bóng chỉ cho lớp nổi)
        Rectangle { anchors.fill: parent; anchors.margins: -8; radius: Theme.radiusCover + 8; color: "#000000"; opacity: 0.04 }
        Rectangle { anchors.fill: parent; anchors.margins: -3; anchors.topMargin: -1; anchors.bottomMargin: -5; radius: Theme.radiusCover + 3; color: "#000000"; opacity: 0.06 }
        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusCover
            color: Theme.panel
            border.width: Theme.dark ? 1 : 0
            border.color: Theme.line
        }
        MouseArea { anchors.fill: parent }   // bấm trong bảng không đóng
        Item {
            id: holder
            x: root.pad
            y: root.pad
            width: panel.width - 2 * root.pad
            height: panel.height - 2 * root.pad
        }
    }
}
