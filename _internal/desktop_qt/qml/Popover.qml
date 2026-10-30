import QtQuick
import ABook

// Bảng nổi neo vào một nút: nội dung đặt thẳng vào trong. Mở trên nút nếu đủ chỗ, không thì dưới; trượt 8 px + thu 0,96 -> 1 khi mở, ngược lại khi đóng
// (ra nhanh hơn vào, DESIGN.md 5.2). Là một lớp của ngăn xếp Back: Esc, Alt+Left, nút Back của chuột hay bấm ra ngoài đều đóng.
FocusScope {
    id: root
    anchors.fill: parent
    property bool open: false
    property Item anchorItem: null
    property int panelWidth: 280
    property int pad: Theme.s12
    property real maxHeight: 420
    property real shown: open ? 1 : 0
    property bool below: false
    property var opener: null
    property bool focusPending: false
    property real panelLimit: Math.max(0, height - 16)
    default property alias content: holder.data
    readonly property real contentHeight: holder.childrenRect.height
    visible: shown > 0
    z: 50
    enabled: open
    onShownChanged: if (shown > 0 && focusPending && open) {
        focusPending = false
        Later.call(root, function() { if (root.open) root.focusChoice(0, true) })
    }
    onContentHeightChanged: if (open) Later.call(root, place)
    onWidthChanged: if (open) Later.call(root, place)
    onHeightChanged: if (open) Later.call(root, place)
    onMaxHeightChanged: if (open) Later.call(root, place)
    Component.onDestruction: Nav.closedLayer(root)

    Behavior on shown {
        NumberAnimation {
            duration: Theme.reduceMotion ? Math.min(Theme.motionFast, 120) : (root.open ? Theme.motionFast : Theme.motionFastOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: root.open ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }

    function show() {
        if (open) return
        opener = Window.window ? Window.window.activeFocusItem : null
        place()
        focusPending = true
        open = true
        Nav.openLayer(root)
    }
    function close() {
        if (!open) return
        open = false
        focusPending = false
        Nav.closedLayer(root)
        if (opener && opener.visible && opener.enabled) opener.forceActiveFocus(Qt.BacktabFocusReason)
        opener = null
    }
    function toggle() { open ? close() : show() }
    function choices() {
        const rows = []
        function visit(item) {
            if (!item.visible || !item.enabled || item.opacity <= 0) return
            if (item.activeFocusOnTab) rows.push(item)
            for (const child of item.children || []) visit(child)
        }
        visit(holder)
        return rows
    }
    function focusChoice(step, initial) {
        const rows = choices()
        if (!rows.length) { forceActiveFocus(); return }
        if (initial) {
            const selected = rows.find(item => item.selected === true || item.current === true)
            ;(selected || rows[0]).forceActiveFocus(Qt.TabFocusReason)
            return
        }
        const at = rows.findIndex(item => item.activeFocus)
        rows[(at + step + rows.length) % rows.length].forceActiveFocus(Qt.TabFocusReason)
    }
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Tab || event.key === Qt.Key_Backtab) {
            focusChoice(event.key === Qt.Key_Backtab || (event.modifiers & Qt.ShiftModifier) ? -1 : 1, false)
            event.accepted = true
        } else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up) {
            focusChoice(event.key === Qt.Key_Down ? 1 : -1, false)
            event.accepted = true
        }
    }
    function place() {
        if (!anchorItem) return
        const a = anchorItem.mapToItem(root, 0, 0)
        const h = Math.min(maxHeight, contentHeight + 2 * pad, Math.max(0, root.height - 16))
        const aboveRoom = Math.max(0, a.y - Theme.s8 - 8)
        const belowRoom = Math.max(0, root.height - a.y - anchorItem.height - Theme.s8 - 8)
        below = h > aboveRoom && (h <= belowRoom || belowRoom > aboveRoom)
        panelLimit = below ? belowRoom : aboveRoom
        panel.x = Math.max(8, Math.min(root.width - panel.width - 8, a.x + anchorItem.width / 2 - panel.width / 2))
        panel.y = Math.max(8, Math.min(root.height - panel.height - 8, below ? a.y + anchorItem.height + Theme.s8 : a.y - panel.height - Theme.s8))
    }

    MouseArea {
        anchors.fill: parent
        enabled: root.open
        onPressed: root.close()
    }

    Item {
        id: panel
        objectName: "popoverPanel"
        width: Math.min(root.panelWidth, Math.max(0, root.width - 16))
        height: Math.min(root.maxHeight, root.panelLimit, holder.childrenRect.height + 2 * root.pad)
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
        Flickable {
            id: viewport
            x: root.pad
            y: root.pad
            width: panel.width - 2 * root.pad
            height: Math.max(0, panel.height - 2 * root.pad)
            contentWidth: width
            contentHeight: holder.childrenRect.height
            boundsBehavior: Flickable.StopAtBounds
            clip: true
            Item { id: holder; width: viewport.width; height: childrenRect.height }
            SmoothWheel { flick: viewport }
        }
        Scrollbar { target: viewport }
    }
}
