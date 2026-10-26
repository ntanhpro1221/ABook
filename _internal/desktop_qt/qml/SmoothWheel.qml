import QtQuick
import ABook

// Cuộn bằng bánh xe chuột có quán tính ngắn (mỗi nấc ~ 110 px, trượt 160 ms) thay vì nhảy từng nấc. Bàn di chuột chính xác
// (pixelDelta) vẫn do Flickable xử lý.
WheelHandler {
    id: root
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
        glide.from = flick.contentY
        glide.to = target
        glide.start()
    }
    property NumberAnimation glide: NumberAnimation {
        target: root.flick
        property: "contentY"
        duration: 160
        easing.type: Easing.BezierSpline
        easing.bezierCurve: Theme.easeDecelerate
    }
}
