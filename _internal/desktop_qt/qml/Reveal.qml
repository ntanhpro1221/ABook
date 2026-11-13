import QtQuick
import ABook

// A visibility controller for an existing visual item (including anchored and
// inline items). Unlike Collapse it adds no layout wrapper. The target keeps
// its place until the fade finishes; closing immediately blocks input. Callers
// with their own opacity animation use Collapse instead of this controller.
// Inside a component whose children go to a default property (or a Flickable's
// contentItem), name the item explicitly: Reveal { target: someId; shown: ... }.
Item {
    id: reveal
    property Item target: parent
    property bool shown: true
    property real progress: shown ? 1 : 0
    visible: false
    width: 0
    height: 0
    Behavior on progress {
        NumberAnimation {
            duration: Theme.reduceMotion ? Theme.motionReduced : (reveal.shown ? Theme.motionFast : Theme.motionFastOut)
            easing.type: Easing.BezierSpline
            easing.bezierCurve: reveal.shown ? Theme.easeDecelerate : Theme.easeAccelerate
        }
    }
    Binding { target: reveal.target; property: "visible"; value: reveal.shown || reveal.progress > 0 }
    // Only while fading or closed, so a component's own opacity (a dimmed
    // disabled button, say) comes back once fully shown.
    Binding {
        target: reveal.target
        property: "opacity"
        value: reveal.progress
        when: reveal.progress < 1
        restoreMode: Binding.RestoreBindingOrValue
    }
    Binding {
        target: reveal.target
        property: "enabled"
        value: false
        when: !reveal.shown
        restoreMode: Binding.RestoreBindingOrValue
    }
}
