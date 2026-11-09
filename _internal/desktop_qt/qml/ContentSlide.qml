import QtQuick
import ABook

// One clock for immutable outgoing pixels and the incoming live page.
// The source stays painted until grabToImage completes; no exit-only interval.
Item {
    id: root
    property Item sourceItem: null
    property real phase: 1
    property int direction: 1
    property var image: null
    property rect from: Qt.rect(0, 0, 0, 0)
    property var pending: null
    property int generation: 0
    property bool capturing: false
    readonly property bool running: capturing || movement.running
    readonly property real incomingShift: Theme.reduceMotion ? 0 : direction * width * (1 - phase)
    clip: true
    z: 90

    function complete() {
        generation++
        movement.stop()
        if (pending) { const apply = pending; pending = null; apply() }
        capturing = false; phase = 1; image = null
    }
    function change(apply, backwards) {
        complete()
        direction = backwards ? -1 : 1
        const source = sourceItem
        if (!source || source.width <= 0 || source.height <= 0) { apply(); return }
        const at = source.mapToItem(root, 0, 0)
        from = Qt.rect(at.x, at.y, source.width, source.height)
        pending = apply
        capturing = true
        const mine = ++generation
        const started = source.grabToImage(function(result) {
            if (mine !== root.generation) return
            root.image = result
            const next = root.pending; root.pending = null
            if (next) next()
            root.capturing = false; root.phase = 0
            movement.restart()
        })
        if (!started) { pending = null; capturing = false; apply(); phase = 1 }
    }
    Image {
        source: root.image ? root.image.url : ""
        x: root.from.x - (Theme.reduceMotion ? 0 : root.direction * root.width * root.phase)
        y: root.from.y; width: root.from.width; height: root.from.height
        visible: root.image !== null && root.phase < 1
        opacity: Theme.reduceMotion ? 1 - root.phase : 1
    }
    NumberAnimation {
        id: movement; target: root; property: "phase"; to: 1
        duration: Theme.reduceMotion ? Theme.motionFast : Theme.motionMedium
        easing.type: Easing.BezierSpline; easing.bezierCurve: Theme.easeStandard
        onFinished: root.image = null
    }
}
