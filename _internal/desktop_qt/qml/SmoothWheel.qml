import QtQuick
import ABook

// Cuộn bằng bánh xe chuột có quán tính ngắn (mỗi nấc ~ 110 px, trượt 160 ms) thay vì nhảy từng nấc. Bàn di chuột chính xác
// (pixelDelta) vẫn do Flickable xử lý.
WheelHandler {
    id: root
    Component.onCompleted: Keep.hold(root)
    required property Flickable flick
    property real step: 110
    property real target: 0
    signal scrolled()   // người vừa lăn bánh xe (khung chữ dùng để thôi "đi theo giọng")
    acceptedDevices: PointerDevice.Mouse
    blocking: true

    function clampY(y) {
        const top = flick.originY - flick.topMargin
        const bottom = flick.originY + flick.contentHeight - flick.height + flick.bottomMargin
        return Math.max(top, Math.min(Math.max(top, bottom), y))
    }
    onWheel: (event) => {
        scrolled()
        const base = glide.running ? target : flick.contentY
        target = clampY(base - event.angleDelta.y / 120 * step)
        if (Theme.reduceMotion) {
            flick.contentY = target
            return
        }
        glide.stop()
        glide.target = flick
        glide.from = flick.contentY
        glide.to = target
        glide.start()
    }
    // The target is set on each wheel turn, never bound to `flick`: when the Flickable dies first (teardown), the guard of
    // `flick` notifies, and a binding on it would read this object's property storage while it is being torn down
    // ("Cannot find member data", gate 22). Nothing outside a real wheel event may read `flick`.
    property NumberAnimation glide: NumberAnimation {
        property: "contentY"
        duration: 160
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Theme.easeDecelerate
    }
}
