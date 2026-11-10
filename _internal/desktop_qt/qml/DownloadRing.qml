import QtQuick
import ABook

// A shared download status: fixed footprint, a percentage ring, unknown size shown by the loader.
Item {
    id: root
    property real percent: -1
    implicitWidth: 36
    implicitHeight: 36
    onPercentChanged: ring.requestPaint()
    Connections { target: Theme; function onDarkChanged() { ring.requestPaint() } }
    Canvas {
        id: ring
        anchors.fill: parent
        visible: root.percent >= 0
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const r = Math.min(width, height) / 2 - 2
            ctx.lineWidth = 2
            ctx.strokeStyle = Theme.line
            ctx.beginPath(); ctx.arc(width / 2, height / 2, r, 0, 2 * Math.PI); ctx.stroke()
            ctx.strokeStyle = Theme.accent
            ctx.lineCap = "round"
            ctx.beginPath(); ctx.arc(width / 2, height / 2, r, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * Math.max(0, Math.min(100, root.percent)) / 100); ctx.stroke()
        }
    }
    ClockLabel {
        anchors.centerIn: parent
        visible: root.percent >= 0
        text: Math.round(root.percent) + " %"
        font.pixelSize: Theme.sizeCaption
        color: Theme.text2
    }
    Icon { anchors.centerIn: parent; visible: root.percent < 0; name: "loader-circle"; size: 20; color: Theme.accentText }
}
