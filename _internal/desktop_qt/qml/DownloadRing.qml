import QtQuick
import ABook

// A shared download status: fixed footprint, a percentage ring, unknown size shown by the loader.
Item {
    id: root
    property real percent: -1
    implicitWidth: 36
    implicitHeight: 36
    onPercentChanged: ring.requestPaint()
    Listen { target: Theme; function onDarkChanged() { ring.requestPaint() } }
    Canvas {
        id: ring
        anchors.fill: parent

        RotationAnimator on rotation { from: 0; to: 360; duration: Theme.spinMs; loops: Animation.Infinite; running: root.percent < 0 && root.visible && Nav.uiVisible && !Theme.reduceMotion }
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const r = Math.min(width, height) / 2 - 2
            ctx.lineWidth = 2
            ctx.strokeStyle = Theme.line
            ctx.beginPath(); ctx.arc(width / 2, height / 2, r, 0, 2 * Math.PI); ctx.stroke()
            ctx.strokeStyle = Theme.accent
            ctx.lineCap = "round"
            ctx.beginPath(); ctx.arc(width / 2, height / 2, r, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * (root.percent < 0 ? 25 : Math.max(0, Math.min(100, root.percent))) / 100); ctx.stroke()
        }
    }
    Rectangle { anchors.centerIn: parent; width: 8; height: 8; color: Theme.accentText }
}
