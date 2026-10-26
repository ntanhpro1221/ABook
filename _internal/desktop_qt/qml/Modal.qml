import QtQuick
import ABook
FocusScope {
    id: root
    anchors.fill: parent
    z: 70
    property bool open: false
    property string title: ""
    property string description: ""
    property real panelWidth: 560
    property var opener: null
    property real shown: open ? 1 : 0
    property bool subpage: false
    default property alias content: body.data
    signal closing()
    visible: shown > 0
    enabled: open
    function show() {
        if (open) return
        opener = Window.window ? Window.window.activeFocusItem : null
        open = true; Nav.openLayer(root); forceActiveFocus(Qt.TabFocusReason)
    }
    function close() { closing(); if (subpage) return; dismiss() }
    function dismiss() {
        if (!open) return
        open = false; Nav.closedLayer(root)
        if (opener) opener.forceActiveFocus(Qt.BacktabFocusReason)
    }
    function containsItem(item) { for (let node = item; node; node = node.parent) if (node === root) return true; return false }
    Component.onDestruction: Nav.closedLayer(root)
    Behavior on shown { NumberAnimation { duration: Theme.reduceMotion ? 0 : (root.open ? Theme.motionMedium : Theme.motionMediumOut); easing.type: Easing.BezierSpline; easing.bezierCurve: root.open ? Theme.easeDecelerate : Theme.easeAccelerate } }
    Rectangle { anchors.fill: parent; color: "#000000"; opacity: root.shown * 0.4 }
    MouseArea { anchors.fill: parent; onPressed: root.close() }
    Rectangle {
        id: panel
        width: Math.min(root.panelWidth, root.width - 48)
        height: Math.min(root.height - 48, body.implicitHeight + heading.height + 64)
        x: (parent.width - width) / 2
        y: (parent.height - height) / 2 + (Theme.reduceMotion ? 0 : 20 * (1 - root.shown))
        scale: Theme.reduceMotion ? 1 : 0.96 + 0.04 * root.shown
        opacity: root.shown
        color: Theme.panel
        radius: Theme.radiusSheet
        MouseArea { anchors.fill: parent }
        Column {
            id: heading
            x: 24; y: 24; width: parent.width - 48
            spacing: 8
            FormLabel { width: parent.width - 40; text: root.title; font.pixelSize: Theme.sizeTitlePhone; font.weight: Theme.weightBold }
            FormLabel { width: parent.width; text: root.description; color: Theme.text2; font.pixelSize: Theme.sizeCaption; visible: text !== "" }
        }
        IconButton { anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 16; icon: "x"; tip: "Đóng"; onClicked: root.close() }
        Flickable {
            id: scroll
            x: 24; y: heading.y + heading.height + 24
            width: parent.width - 48; height: parent.height - y - 24
            contentHeight: body.implicitHeight
            clip: true; boundsBehavior: Flickable.StopAtBounds
            Column { id: body; width: parent.width; spacing: 16 }
            SmoothWheel { flick: scroll }
        }
        Scrollbar { target: scroll }
    }
    // Modal keyboard focus stays in this layer; Back is handled by Nav.
    Keys.onTabPressed: event => {
        const current = Window.window.activeFocusItem
        const next = current ? current.nextItemInFocusChain() : root
        if (!next || !root.containsItem(next)) { root.forceActiveFocus(Qt.TabFocusReason); event.accepted = true }
    }
}
