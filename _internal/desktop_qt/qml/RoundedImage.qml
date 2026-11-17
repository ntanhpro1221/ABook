import QtQuick

// Ảnh cắt kiểu PreserveAspectCrop vào hình chữ nhật bo `radius` (radius = nửa cạnh là hình tròn), vẽ bằng Canvas (QPainter, mép
// khử răng cưa). Không dùng mặt nạ MultiEffect: đó là ShaderEffect, backend phần mềm (QT_QUICK_BACKEND=software - nơi WidthTests
// chụp mọi ảnh soát) không vẽ nó, nên ảnh chân dung giọng và ảnh nhạc biến khỏi ảnh chụp dù app thật có. Canvas vẽ như nhau
// trên RHI và backend phần mềm.
Item {
    id: root
    property alias source: photo.source
    property alias sourceSize: photo.sourceSize
    property alias asynchronous: photo.asynchronous
    property alias cache: photo.cache
    property real radius: 0
    readonly property alias status: photo.status
    readonly property int fillMode: Image.PreserveAspectCrop
    Image {
        id: photo
        visible: false
        asynchronous: true
        onStatusChanged: art.requestPaint()
        onSourceChanged: art.requestPaint()
    }
    Canvas {
        id: art
        anchors.fill: parent
        property real corner: root.radius
        onCornerChanged: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
        // drawImage(Image) nạp lại theo URL vào kho ảnh riêng của Canvas: data:/image:// về chậm một nhịp, vẽ lại khi xong
        onImageLoaded: requestPaint()
        onPaint: {
            const ctx = getContext("2d")
            ctx.reset()
            const iw = photo.implicitWidth, ih = photo.implicitHeight
            if (photo.status !== Image.Ready || iw <= 0 || ih <= 0 || width <= 0 || height <= 0) return
            // Crop bằng cách phủ ảnh (đúng tỉ lệ) lớn hơn khung rồi cắt: không dựa vào cỡ điểm ảnh mà Canvas tự nạp (có thể khác sourceSize)
            const scale = Math.max(width / iw, height / ih), dw = iw * scale, dh = ih * scale
            const r = Math.min(corner, width / 2, height / 2)
            ctx.beginPath()
            ctx.roundedRect(0, 0, width, height, r, r)
            ctx.clip()
            ctx.drawImage(photo, (width - dw) / 2, (height - dh) / 2, dw, dh)
        }
    }
}
